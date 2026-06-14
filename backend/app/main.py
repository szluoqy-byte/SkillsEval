from __future__ import annotations

import json
import sqlite3
from pathlib import Path, PurePosixPath
from typing import Any, Optional

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .db import connect, encode_json, init_db, now_iso, row_to_dict, rows_to_dicts, seed_db
from .eval_generation import confirm_generation_job, create_generation_job, delete_generation_job, get_job, list_jobs_for_skill, run_generation_job
from .evaluator import create_task, run_task
from .importer import confirm_import_draft, create_import_draft, get_import_draft, new_id
from .model_client import PROVIDER_TYPES, call_configured_model, normalize_base_url, sanitize_provider


app = FastAPI(title="SkillsEval API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConfirmImportRequest(BaseModel):
    skill_name: str
    version: str
    category: str
    display_name: Optional[str] = None


class TriggerQueryRequest(BaseModel):
    query: str
    should_trigger: bool


class EffectCaseRequest(BaseModel):
    case_key: str
    prompt: str
    expected_output: str
    files: list[str] = []
    assertions: list[str] = []


class GenerationJobRequest(BaseModel):
    target: str
    count: int
    instruction: str = ""
    include_negative: bool = True


class GenerationConfirmRequest(BaseModel):
    items: list[dict[str, Any]]


class CreateTaskRequest(BaseModel):
    skill_id: str
    skill_version_id: str
    runner_environment_id: str


class UpdateSkillRequest(BaseModel):
    display_name: str
    description: str = ""
    category: str
    card_content: str = ""


class CategoryRequest(BaseModel):
    name: str
    description: str = ""
    enabled: bool = True


class RunnerRequest(BaseModel):
    name: str
    runner_type: str
    model_name: str
    command_path: str
    timeout_seconds: int = 60
    enabled: bool = True


class ModelProviderRequest(BaseModel):
    name: str
    provider_type: str
    base_url: str
    api_key: Optional[str] = None
    enabled: bool = True


class ModelProfileRequest(BaseModel):
    provider_id: str
    display_name: str
    model_id: str
    enabled: bool = True


class ModelRolesRequest(BaseModel):
    judge_model_id: Optional[str] = None
    data_model_id: Optional[str] = None


class ScoringWeightRequest(BaseModel):
    stage: str
    weight: float


class ScoringWeightsRequest(BaseModel):
    weights: list[ScoringWeightRequest]


SCORING_STAGES = {"static_scan", "trigger_eval", "effect_eval", "performance_eval"}
TEXT_PREVIEW_LIMIT_BYTES = 200_000


def clean_required(value: str, field: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail=f"{field} is required.")
    return cleaned


def clean_optional_id(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def validate_provider_type(value: str) -> str:
    cleaned = clean_required(value, "provider_type")
    if cleaned not in PROVIDER_TYPES:
        raise HTTPException(status_code=400, detail="provider_type must be openai_compatible or anthropic.")
    return cleaned


def validate_scoring_weights(items: list[ScoringWeightRequest]) -> dict[str, float]:
    weights = {item.stage: item.weight for item in items}
    if set(weights) != SCORING_STAGES:
        raise HTTPException(status_code=400, detail="Scoring weights must include static_scan, trigger_eval, effect_eval, performance_eval.")
    if any(value < 0 for value in weights.values()):
        raise HTTPException(status_code=400, detail="Scoring weights must be non-negative.")
    if abs(sum(weights.values()) - 1.0) > 0.000001:
        raise HTTPException(status_code=400, detail="Scoring weights must sum to 100%.")
    return weights


def recommendation_rank(value: str | None) -> int:
    ranks = {
        "recommended": 0,
        "usable": 1,
        "review_required": 2,
        "not_recommended": 3,
        "not_evaluated": 4,
        None: 5,
    }
    return ranks.get(value, 5)


def summary_trigger_score(item: dict[str, Any]) -> float:
    summary = item.get("result_summary") or {}
    return float(summary.get("trigger_score") or 0)


def summary_scan_rank(item: dict[str, Any]) -> int:
    summary = item.get("result_summary") or {}
    ranks = {"passed": 0, "warning": 1, "critical": 2, "not_scanned": 3}
    return ranks.get(summary.get("scan_status"), 4)


def read_run_artifact(run_root: Path, artifact_path: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        target = Path(artifact_path).resolve()
        target.relative_to(run_root)
    except ValueError:
        return None, "Artifact path escapes run root."
    if not target.exists() or not target.is_file():
        return None, "Artifact file is missing."
    try:
        return json.loads(target.read_text(encoding="utf-8")), None
    except json.JSONDecodeError:
        return None, "Artifact file is not valid JSON."


def normalize_static_evidence(stage: dict[str, Any] | None, payload: dict[str, Any] | None, error: str | None) -> dict[str, Any]:
    findings = payload.get("findings", []) if payload else []
    findings_by_code = {item.get("code"): item for item in findings if item.get("code")}
    rules = []
    for rule in payload.get("rules", []) if payload else []:
        finding = findings_by_code.get(rule.get("rule_id"))
        rules.append(
            {
                **rule,
                "status": "failed" if finding else "passed",
                "finding": finding,
            }
        )
    return {
        "status": stage.get("status") if stage else "missing",
        "score": stage.get("score") if stage else 0,
        "summary": stage.get("summary") if stage else "Static scan stage is missing.",
        "metrics": stage.get("metrics") if stage else {},
        "rules": rules,
        "error": error or "",
    }


def normalize_stage_evidence(stage: dict[str, Any] | None, payload: dict[str, Any] | None, error: str | None) -> dict[str, Any]:
    return {
        "status": stage.get("status") if stage else "missing",
        "score": stage.get("score") if stage else 0,
        "summary": stage.get("summary") if stage else "Stage result is missing.",
        "metrics": stage.get("metrics") if stage else {},
        "results": payload.get("results", []) if payload else [],
        "error": error or "",
    }


def normalize_effect_evidence(stage: dict[str, Any] | None, payload: dict[str, Any] | None, error: str | None) -> dict[str, Any]:
    base = normalize_stage_evidence(stage, payload, error)
    base.update(
        {
            "case_results": payload.get("case_results", []) if payload else [],
            "analyzer_notes": payload.get("analyzer_notes", []) if payload else [],
            "cost_efficiency": payload.get("cost_efficiency", {}) if payload else {},
        }
    )
    return base


def build_task_evidence_detail(conn: sqlite3.Connection, task_id: str) -> dict[str, Any]:
    from .evaluator import get_task

    task = get_task(task_id, conn)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    run = task.get("run")
    if not run:
        raise HTTPException(status_code=404, detail="Task has no run evidence yet.")
    run_root = Path(run["artifact_root"]).resolve()
    stages = {stage["stage"]: stage for stage in task.get("stage_results", [])}
    payloads: dict[str, dict[str, Any] | None] = {}
    errors: dict[str, str | None] = {}
    for stage_name, stage in stages.items():
        payloads[stage_name], errors[stage_name] = read_run_artifact(run_root, stage["artifact_path"])

    return {
        "task_id": task_id,
        "run_id": run["id"],
        "static_scan": normalize_static_evidence(stages.get("static_scan"), payloads.get("static_scan"), errors.get("static_scan")),
        "trigger_eval": normalize_stage_evidence(stages.get("trigger_eval"), payloads.get("trigger_eval"), errors.get("trigger_eval")),
        "effect_eval": normalize_effect_evidence(stages.get("effect_eval"), payloads.get("effect_eval"), errors.get("effect_eval")),
        "performance_eval": normalize_stage_evidence(stages.get("performance_eval"), payloads.get("performance_eval"), errors.get("performance_eval")),
        "artifacts": task.get("evidence_items", []),
    }


def build_skill_detail(conn: sqlite3.Connection, skill_id: str) -> dict[str, Any]:
    skill = row_to_dict(conn.execute("SELECT * FROM skills WHERE id = ?", (skill_id,)).fetchone())
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found.")
    skill["versions"] = rows_to_dicts(conn.execute("SELECT * FROM skill_versions WHERE skill_id = ? ORDER BY created_at DESC", (skill_id,)).fetchall())
    skill["latest_task"] = row_to_dict(
        conn.execute(
            """
            SELECT t.*, er.overall_score, er.recommendation, er.result_summary
            FROM evaluation_tasks t
            LEFT JOIN evaluation_runs er ON er.task_id = t.id
            WHERE t.skill_id = ?
            ORDER BY t.created_at DESC
            LIMIT 1
            """,
            (skill_id,),
        ).fetchone()
    )
    return skill


def get_skill_version_row(conn: sqlite3.Connection, skill_id: str, version_id: str | None) -> sqlite3.Row:
    if version_id:
        version = conn.execute("SELECT * FROM skill_versions WHERE id = ? AND skill_id = ?", (version_id, skill_id)).fetchone()
    else:
        version = conn.execute(
            """
            SELECT sv.*
            FROM skill_versions sv
            JOIN skills s ON s.latest_version_id = sv.id
            WHERE s.id = ?
            """,
            (skill_id,),
        ).fetchone()
    if not version:
        raise HTTPException(status_code=404, detail="Skill version not found.")
    return version


def resolve_artifact_root(version: sqlite3.Row) -> Path:
    root = Path(version["artifact_root"]).resolve()
    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=404, detail="Skill artifact root not found.")
    return root


def safe_relative_file(root: Path, path: str) -> Path:
    pure = PurePosixPath(path)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise HTTPException(status_code=400, detail="Invalid file path.")
    target = (root / Path(*pure.parts)).resolve()
    try:
        target.relative_to(root)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="File path escapes skill artifact root.") from error
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    return target


def is_text_bytes(payload: bytes) -> bool:
    if b"\x00" in payload:
        return False
    try:
        payload.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def file_entry(path: Path, root: Path) -> dict[str, Any]:
    relative_path = path.relative_to(root).as_posix()
    stat = path.stat()
    sample = b""
    if path.is_file():
        with path.open("rb") as handle:
            sample = handle.read(4096)
    return {
        "path": relative_path,
        "name": path.name,
        "type": "directory" if path.is_dir() else "file",
        "size_bytes": 0 if path.is_dir() else stat.st_size,
        "extension": "" if path.is_dir() else path.suffix.lower().lstrip("."),
        "is_text": False if path.is_dir() else is_text_bytes(sample),
    }


@app.on_event("startup")
def startup() -> None:
    init_db()
    seed_db()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/categories")
def categories() -> list[dict[str, Any]]:
    with connect() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM categories WHERE enabled = 1 ORDER BY name").fetchall())


@app.get("/api/runners")
def runners() -> list[dict[str, Any]]:
    with connect() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM runner_environments WHERE enabled = 1 ORDER BY name").fetchall())


@app.get("/api/settings/scoring-weights")
def scoring_weights() -> list[dict[str, Any]]:
    with connect() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM scoring_weights ORDER BY stage").fetchall())


@app.get("/api/settings/categories")
def settings_categories() -> list[dict[str, Any]]:
    with connect() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM categories ORDER BY enabled DESC, name").fetchall())


@app.get("/api/settings/model-providers")
def settings_model_providers() -> list[dict[str, Any]]:
    with connect() as conn:
        providers = rows_to_dicts(conn.execute("SELECT * FROM model_api_providers ORDER BY enabled DESC, name").fetchall())
        return [sanitize_provider(provider) for provider in providers]


@app.post("/api/settings/model-providers")
def create_model_provider(request: ModelProviderRequest) -> dict[str, Any]:
    provider_id = new_id("provider")
    created = now_iso()
    name = clean_required(request.name, "provider name")
    provider_type = validate_provider_type(request.provider_type)
    try:
        base_url = normalize_base_url(request.base_url)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    api_key = clean_required(request.api_key or "", "api_key")
    with connect() as conn:
        try:
            conn.execute(
                """
                INSERT INTO model_api_providers
                  (id, name, provider_type, base_url, api_key, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (provider_id, name, provider_type, base_url, api_key, 1 if request.enabled else 0, created, created),
            )
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=400, detail="Provider name already exists.") from error
        return sanitize_provider(row_to_dict(conn.execute("SELECT * FROM model_api_providers WHERE id = ?", (provider_id,)).fetchone()))


@app.put("/api/settings/model-providers/{provider_id}")
def update_model_provider(provider_id: str, request: ModelProviderRequest) -> dict[str, Any]:
    name = clean_required(request.name, "provider name")
    provider_type = validate_provider_type(request.provider_type)
    try:
        base_url = normalize_base_url(request.base_url)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    updated = now_iso()
    with connect() as conn:
        existing = conn.execute("SELECT * FROM model_api_providers WHERE id = ?", (provider_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Model API provider not found.")
        api_key = (request.api_key or "").strip() or existing["api_key"]
        try:
            conn.execute(
                """
                UPDATE model_api_providers
                SET name = ?, provider_type = ?, base_url = ?, api_key = ?, enabled = ?, updated_at = ?
                WHERE id = ?
                """,
                (name, provider_type, base_url, api_key, 1 if request.enabled else 0, updated, provider_id),
            )
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=400, detail="Provider name already exists.") from error
        return sanitize_provider(row_to_dict(conn.execute("SELECT * FROM model_api_providers WHERE id = ?", (provider_id,)).fetchone()))


@app.delete("/api/settings/model-providers/{provider_id}")
def delete_model_provider(provider_id: str) -> dict[str, Any]:
    with connect() as conn:
        provider = conn.execute("SELECT * FROM model_api_providers WHERE id = ?", (provider_id,)).fetchone()
        if not provider:
            raise HTTPException(status_code=404, detail="Model API provider not found.")
        conn.execute("UPDATE model_api_providers SET enabled = 0, updated_at = ? WHERE id = ?", (now_iso(), provider_id))
        return {"status": "disabled", "id": provider_id}


@app.get("/api/settings/model-models")
def settings_model_models() -> list[dict[str, Any]]:
    with connect() as conn:
        return rows_to_dicts(
            conn.execute(
                """
                SELECT m.*, p.name AS provider_name, p.provider_type, p.base_url AS provider_base_url, p.enabled AS provider_enabled
                FROM model_api_models m
                JOIN model_api_providers p ON p.id = m.provider_id
                ORDER BY p.enabled DESC, m.enabled DESC, p.name, m.display_name
                """
            ).fetchall()
        )


@app.post("/api/settings/model-models")
def create_model_model(request: ModelProfileRequest) -> dict[str, Any]:
    model_pk = new_id("model")
    created = now_iso()
    provider_id = clean_required(request.provider_id, "provider_id")
    display_name = clean_required(request.display_name, "display_name")
    model_id = clean_required(request.model_id, "model_id")
    with connect() as conn:
        provider = conn.execute("SELECT * FROM model_api_providers WHERE id = ?", (provider_id,)).fetchone()
        if not provider:
            raise HTTPException(status_code=404, detail="Model API provider not found.")
        ensure_unique_model_base_url(conn, provider_id, model_id)
        try:
            conn.execute(
                """
                INSERT INTO model_api_models
                  (id, provider_id, display_name, model_id, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (model_pk, provider_id, display_name, model_id, 1 if request.enabled else 0, created, created),
            )
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=400, detail="Model id already exists for this provider.") from error
        return row_to_dict(conn.execute("SELECT * FROM model_api_models WHERE id = ?", (model_pk,)).fetchone())


@app.put("/api/settings/model-models/{model_pk}")
def update_model_model(model_pk: str, request: ModelProfileRequest) -> dict[str, Any]:
    provider_id = clean_required(request.provider_id, "provider_id")
    display_name = clean_required(request.display_name, "display_name")
    model_id = clean_required(request.model_id, "model_id")
    with connect() as conn:
        existing = conn.execute("SELECT * FROM model_api_models WHERE id = ?", (model_pk,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Model profile not found.")
        provider = conn.execute("SELECT * FROM model_api_providers WHERE id = ?", (provider_id,)).fetchone()
        if not provider:
            raise HTTPException(status_code=404, detail="Model API provider not found.")
        ensure_unique_model_base_url(conn, provider_id, model_id, model_pk)
        try:
            conn.execute(
                """
                UPDATE model_api_models
                SET provider_id = ?, display_name = ?, model_id = ?, enabled = ?, updated_at = ?
                WHERE id = ?
                """,
                (provider_id, display_name, model_id, 1 if request.enabled else 0, now_iso(), model_pk),
            )
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=400, detail="Model id already exists for this provider.") from error
        return row_to_dict(conn.execute("SELECT * FROM model_api_models WHERE id = ?", (model_pk,)).fetchone())


@app.delete("/api/settings/model-models/{model_pk}")
def delete_model_model(model_pk: str) -> dict[str, Any]:
    with connect() as conn:
        model = conn.execute("SELECT * FROM model_api_models WHERE id = ?", (model_pk,)).fetchone()
        if not model:
            raise HTTPException(status_code=404, detail="Model profile not found.")
        conn.execute("UPDATE model_api_models SET enabled = 0, updated_at = ? WHERE id = ?", (now_iso(), model_pk))
        return {"status": "disabled", "id": model_pk}


@app.get("/api/settings/model-roles")
def settings_model_roles() -> dict[str, Any]:
    with connect() as conn:
        rows = rows_to_dicts(conn.execute("SELECT role, model_api_model_id FROM model_role_settings").fetchall())
        roles = {row["role"]: row["model_api_model_id"] for row in rows}
        return {"judge_model_id": roles.get("judge"), "data_model_id": roles.get("data")}


def ensure_model_exists(conn: sqlite3.Connection, model_id: str | None) -> None:
    if not model_id:
        return
    model = conn.execute("SELECT * FROM model_api_models WHERE id = ?", (model_id,)).fetchone()
    if not model:
        raise HTTPException(status_code=400, detail="Selected model does not exist.")


def ensure_unique_model_base_url(conn: sqlite3.Connection, provider_id: str, model_id: str, current_model_pk: str | None = None) -> None:
    provider = conn.execute("SELECT base_url FROM model_api_providers WHERE id = ?", (provider_id,)).fetchone()
    if not provider:
        raise HTTPException(status_code=404, detail="Model API provider not found.")
    params: list[Any] = [provider["base_url"], model_id]
    exclusion = ""
    if current_model_pk:
        exclusion = "AND m.id != ?"
        params.append(current_model_pk)
    existing = conn.execute(
        f"""
        SELECT m.id
        FROM model_api_models m
        JOIN model_api_providers p ON p.id = m.provider_id
        WHERE p.base_url = ? AND m.model_id = ? {exclusion}
        LIMIT 1
        """,
        params,
    ).fetchone()
    if existing:
        raise HTTPException(status_code=400, detail="Model name and base_url already exist.")


@app.put("/api/settings/model-roles")
def update_model_roles(request: ModelRolesRequest) -> dict[str, Any]:
    judge_model_id = clean_optional_id(request.judge_model_id)
    data_model_id = clean_optional_id(request.data_model_id)
    updated = now_iso()
    with connect() as conn:
        ensure_model_exists(conn, judge_model_id)
        ensure_model_exists(conn, data_model_id)
        conn.executemany(
            """
            INSERT INTO model_role_settings (role, model_api_model_id, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(role) DO UPDATE SET model_api_model_id = excluded.model_api_model_id, updated_at = excluded.updated_at
            """,
            [("judge", judge_model_id, updated), ("data", data_model_id, updated)],
        )
        return {"judge_model_id": judge_model_id, "data_model_id": data_model_id}


@app.post("/api/settings/model-models/{model_pk}/test")
def test_model_model(model_pk: str) -> dict[str, Any]:
    with connect() as conn:
        model = row_to_dict(
            conn.execute(
                """
                SELECT
                  m.*,
                  p.name AS provider_name,
                  p.provider_type,
                  p.base_url,
                  p.api_key,
                  p.enabled AS provider_enabled
                FROM model_api_models m
                JOIN model_api_providers p ON p.id = m.provider_id
                WHERE m.id = ?
                """,
                (model_pk,),
            ).fetchone()
        )
    if not model:
        raise HTTPException(status_code=404, detail="Model profile not found.")
    result = call_configured_model(model, 'Reply with exactly {"ok": true}.', timeout_seconds=30)
    if result.error:
        raise HTTPException(status_code=400, detail=result.error)
    return {
        "status": "ok",
        "content_preview": result.content[:200],
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "total_tokens": result.total_tokens,
    }


@app.post("/api/settings/categories")
def create_category(request: CategoryRequest) -> dict[str, Any]:
    created = now_iso()
    category_id = new_id("cat")
    name = clean_required(request.name, "category name")
    with connect() as conn:
        try:
            conn.execute(
                "INSERT INTO categories (id, name, description, enabled, created_at) VALUES (?, ?, ?, ?, ?)",
                (category_id, name, request.description.strip(), 1 if request.enabled else 0, created),
            )
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=400, detail="Category name already exists.") from error
        return row_to_dict(conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone())


@app.put("/api/settings/categories/{category_id}")
def update_category(category_id: str, request: CategoryRequest) -> dict[str, Any]:
    name = clean_required(request.name, "category name")
    with connect() as conn:
        existing = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Category not found.")
        try:
            conn.execute(
                "UPDATE categories SET name = ?, description = ?, enabled = ? WHERE id = ?",
                (name, request.description.strip(), 1 if request.enabled else 0, category_id),
            )
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=400, detail="Category name already exists.") from error
        return row_to_dict(conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone())


@app.delete("/api/settings/categories/{category_id}")
def delete_category(category_id: str) -> dict[str, Any]:
    with connect() as conn:
        category = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
        if not category:
            raise HTTPException(status_code=404, detail="Category not found.")
        references = conn.execute("SELECT COUNT(*) AS count FROM skills WHERE category = ?", (category["name"],)).fetchone()["count"]
        if references:
            conn.execute("UPDATE categories SET enabled = 0 WHERE id = ?", (category_id,))
            return {"status": "disabled", "id": category_id}
        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        return {"status": "deleted", "id": category_id}


@app.get("/api/settings/runners")
def settings_runners() -> list[dict[str, Any]]:
    with connect() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM runner_environments ORDER BY enabled DESC, name").fetchall())


@app.post("/api/settings/runners")
def create_runner(request: RunnerRequest) -> dict[str, Any]:
    created = now_iso()
    runner_id = new_id("runner")
    name = clean_required(request.name, "runner name")
    runner_type = clean_required(request.runner_type, "runner_type")
    model_name = clean_required(request.model_name, "model_name")
    command_path = clean_required(request.command_path, "command_path")
    timeout_seconds = max(1, request.timeout_seconds)
    with connect() as conn:
        try:
            conn.execute(
                """
                INSERT INTO runner_environments
                  (id, name, runner_type, model_name, judge_model, command_path, timeout_seconds, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (runner_id, name, runner_type, model_name, "not_configured", command_path, timeout_seconds, 1 if request.enabled else 0, created),
            )
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=400, detail="Runner name already exists.") from error
        return row_to_dict(conn.execute("SELECT * FROM runner_environments WHERE id = ?", (runner_id,)).fetchone())


@app.put("/api/settings/runners/{runner_id}")
def update_runner(runner_id: str, request: RunnerRequest) -> dict[str, Any]:
    name = clean_required(request.name, "runner name")
    runner_type = clean_required(request.runner_type, "runner_type")
    model_name = clean_required(request.model_name, "model_name")
    command_path = clean_required(request.command_path, "command_path")
    timeout_seconds = max(1, request.timeout_seconds)
    with connect() as conn:
        existing = conn.execute("SELECT * FROM runner_environments WHERE id = ?", (runner_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Runner not found.")
        try:
            conn.execute(
                """
                UPDATE runner_environments
                SET name = ?, runner_type = ?, model_name = ?, judge_model = ?, command_path = ?, timeout_seconds = ?, enabled = ?
                WHERE id = ?
                """,
                (name, runner_type, model_name, existing["judge_model"] or "not_configured", command_path, timeout_seconds, 1 if request.enabled else 0, runner_id),
            )
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=400, detail="Runner name already exists.") from error
        return row_to_dict(conn.execute("SELECT * FROM runner_environments WHERE id = ?", (runner_id,)).fetchone())


@app.delete("/api/settings/runners/{runner_id}")
def delete_runner(runner_id: str) -> dict[str, Any]:
    with connect() as conn:
        runner = conn.execute("SELECT * FROM runner_environments WHERE id = ?", (runner_id,)).fetchone()
        if not runner:
            raise HTTPException(status_code=404, detail="Runner not found.")
        conn.execute("UPDATE runner_environments SET enabled = 0 WHERE id = ?", (runner_id,))
        return {"status": "disabled", "id": runner_id}


@app.put("/api/settings/scoring-weights")
def update_scoring_weights(request: ScoringWeightsRequest) -> list[dict[str, Any]]:
    weights = validate_scoring_weights(request.weights)
    with connect() as conn:
        conn.executemany(
            "UPDATE scoring_weights SET weight = ? WHERE stage = ?",
            [(weight, stage) for stage, weight in weights.items()],
        )
        return rows_to_dicts(conn.execute("SELECT * FROM scoring_weights ORDER BY stage").fetchall())


@app.post("/api/imports/skill-zip")
async def upload_skill_zip(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip skill packages are supported.")
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded ZIP is empty.")
    return create_import_draft(file.filename, payload)


@app.get("/api/imports/{draft_id}")
def import_draft(draft_id: str) -> dict[str, Any]:
    draft = get_import_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Import draft not found.")
    return draft


@app.post("/api/imports/{draft_id}/confirm")
def confirm_import(draft_id: str, request: ConfirmImportRequest) -> dict[str, Any]:
    try:
        return confirm_import_draft(draft_id, request.skill_name, request.version, request.category, request.display_name)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/skills")
def skills() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT s.*, sv.version AS latest_version, er.overall_score, er.recommendation,
                   er.result_summary, er.finished_at AS last_evaluated_at
            FROM skills s
            LEFT JOIN skill_versions sv ON sv.id = s.latest_version_id
            LEFT JOIN evaluation_tasks t ON t.id = (
              SELECT t2.id
              FROM evaluation_tasks t2
              JOIN evaluation_runs er2 ON er2.task_id = t2.id AND er2.status = 'completed'
              WHERE t2.skill_id = s.id AND t2.skill_version_id = s.latest_version_id
              ORDER BY er2.finished_at DESC, er2.id DESC
              LIMIT 1
            )
            LEFT JOIN evaluation_runs er ON er.task_id = t.id AND er.status = 'completed'
            ORDER BY s.updated_at DESC
            """
        ).fetchall()
        return rows_to_dicts(rows)


@app.get("/api/skills/{skill_id}")
def skill_detail(skill_id: str) -> dict[str, Any]:
    with connect() as conn:
        return build_skill_detail(conn, skill_id)


@app.put("/api/skills/{skill_id}")
def update_skill(skill_id: str, request: UpdateSkillRequest) -> dict[str, Any]:
    display_name = clean_required(request.display_name, "display_name")
    category = clean_required(request.category, "category")
    description = request.description.strip()
    card_content = request.card_content.strip()
    updated = now_iso()
    with connect() as conn:
        existing = conn.execute("SELECT * FROM skills WHERE id = ?", (skill_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Skill not found.")
        category_row = conn.execute("SELECT * FROM categories WHERE name = ? AND enabled = 1", (category,)).fetchone()
        if not category_row:
            raise HTTPException(status_code=400, detail="Category does not exist or is disabled.")
        conn.execute(
            "UPDATE skills SET display_name = ?, description = ?, card_content = ?, category = ?, updated_at = ? WHERE id = ?",
            (display_name, description, card_content, category, updated, skill_id),
        )
        return build_skill_detail(conn, skill_id)


@app.get("/api/skills/{skill_id}/files")
def skill_files(skill_id: str, version_id: Optional[str] = None) -> dict[str, Any]:
    with connect() as conn:
        version = get_skill_version_row(conn, skill_id, version_id)
        root = resolve_artifact_root(version)
        entries: list[dict[str, Any]] = []
        for path in sorted(root.rglob("*"), key=lambda item: (item.relative_to(root).as_posix().lower(), item.is_file())):
            try:
                resolved = path.resolve()
                resolved.relative_to(root)
            except ValueError:
                continue
            if resolved == root:
                continue
            entries.append(file_entry(resolved, root))
        return {
            "version_id": version["id"],
            "version": version["version"],
            "files": entries,
        }


@app.get("/api/skills/{skill_id}/files/content")
def skill_file_content(skill_id: str, path: str, version_id: Optional[str] = None) -> dict[str, Any]:
    with connect() as conn:
        version = get_skill_version_row(conn, skill_id, version_id)
        root = resolve_artifact_root(version)
        target = safe_relative_file(root, path)
        size_bytes = target.stat().st_size
        with target.open("rb") as handle:
            payload = handle.read(TEXT_PREVIEW_LIMIT_BYTES + 1)
        truncated = len(payload) > TEXT_PREVIEW_LIMIT_BYTES
        preview_payload = payload[:TEXT_PREVIEW_LIMIT_BYTES]
        is_text = is_text_bytes(preview_payload)
        return {
            "path": target.relative_to(root).as_posix(),
            "content": preview_payload.decode("utf-8") if is_text else "",
            "size_bytes": size_bytes,
            "is_text": is_text,
            "truncated": truncated,
        }


@app.get("/api/skills/{skill_id}/evaluation-set")
def get_evaluation_set(skill_id: str) -> dict[str, Any]:
    with connect() as conn:
        eval_set = row_to_dict(conn.execute("SELECT * FROM evaluation_sets WHERE skill_id = ?", (skill_id,)).fetchone())
        if not eval_set:
            raise HTTPException(status_code=404, detail="Evaluation set not found.")
        eval_set["trigger_queries"] = rows_to_dicts(conn.execute("SELECT * FROM trigger_queries WHERE eval_set_id = ? ORDER BY created_at", (eval_set["id"],)).fetchall())
        eval_set["effect_cases"] = rows_to_dicts(conn.execute("SELECT * FROM effect_cases WHERE eval_set_id = ? ORDER BY created_at", (eval_set["id"],)).fetchall())
        eval_set["generation_jobs"] = list_jobs_for_skill(skill_id)
        return eval_set


@app.get("/api/skills/{skill_id}/evaluation-set/generation-jobs")
def generation_jobs(skill_id: str) -> list[dict[str, Any]]:
    return list_jobs_for_skill(skill_id)


@app.post("/api/skills/{skill_id}/evaluation-set/generation-jobs")
def create_eval_generation_job(skill_id: str, request: GenerationJobRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    try:
        job = create_generation_job(skill_id, request.target, request.count, request.instruction, request.include_negative)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if job["status"] == "queued":
        background_tasks.add_task(run_generation_job, job["id"])
    return job


@app.get("/api/evaluation-set-generation-jobs/{job_id}")
def evaluation_generation_job(job_id: str) -> dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Generation job not found.")
    return job


@app.post("/api/evaluation-set-generation-jobs/{job_id}/confirm")
def confirm_eval_generation_job(job_id: str, request: GenerationConfirmRequest) -> dict[str, Any]:
    try:
        return confirm_generation_job(job_id, request.items)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.delete("/api/evaluation-set-generation-jobs/{job_id}")
def delete_eval_generation_job(job_id: str) -> dict[str, str]:
    delete_generation_job(job_id)
    return {"status": "deleted"}


@app.post("/api/skills/{skill_id}/evaluation-set/trigger-queries")
def add_trigger_query(skill_id: str, request: TriggerQueryRequest) -> dict[str, Any]:
    created = now_iso()
    with connect() as conn:
        eval_set = conn.execute("SELECT * FROM evaluation_sets WHERE skill_id = ?", (skill_id,)).fetchone()
        if not eval_set:
            raise HTTPException(status_code=404, detail="Evaluation set not found.")
        item_id = new_id("trq")
        conn.execute(
            "INSERT INTO trigger_queries (id, eval_set_id, query, should_trigger, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (item_id, eval_set["id"], request.query, 1 if request.should_trigger else 0, created, created),
        )
        return row_to_dict(conn.execute("SELECT * FROM trigger_queries WHERE id = ?", (item_id,)).fetchone())


@app.delete("/api/trigger-queries/{query_id}")
def delete_trigger_query(query_id: str) -> dict[str, str]:
    with connect() as conn:
        conn.execute("DELETE FROM trigger_queries WHERE id = ?", (query_id,))
    return {"status": "deleted"}


@app.post("/api/skills/{skill_id}/evaluation-set/effect-cases")
def add_effect_case(skill_id: str, request: EffectCaseRequest) -> dict[str, Any]:
    created = now_iso()
    with connect() as conn:
        eval_set = conn.execute("SELECT * FROM evaluation_sets WHERE skill_id = ?", (skill_id,)).fetchone()
        if not eval_set:
            raise HTTPException(status_code=404, detail="Evaluation set not found.")
        item_id = new_id("effect")
        try:
            conn.execute(
                """
                INSERT INTO effect_cases
                  (id, eval_set_id, case_key, prompt, expected_output, files, assertions, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    eval_set["id"],
                    request.case_key,
                    request.prompt,
                    request.expected_output,
                    encode_json(request.files),
                    encode_json(request.assertions),
                    created,
                    created,
                ),
            )
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return row_to_dict(conn.execute("SELECT * FROM effect_cases WHERE id = ?", (item_id,)).fetchone())


@app.delete("/api/effect-cases/{case_id}")
def delete_effect_case(case_id: str) -> dict[str, str]:
    with connect() as conn:
        conn.execute("DELETE FROM effect_cases WHERE id = ?", (case_id,))
    return {"status": "deleted"}


@app.get("/api/tasks")
def tasks() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT t.*, s.skill_name, sv.version, r.name AS runner_name,
                   er.overall_score, er.recommendation, er.result_summary
            FROM evaluation_tasks t
            JOIN skills s ON s.id = t.skill_id
            JOIN skill_versions sv ON sv.id = t.skill_version_id
            JOIN runner_environments r ON r.id = t.runner_environment_id
            LEFT JOIN evaluation_runs er ON er.task_id = t.id
            ORDER BY t.created_at DESC
            """
        ).fetchall()
        return rows_to_dicts(rows)


@app.post("/api/tasks")
def create_evaluation_task(request: CreateTaskRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    try:
        task = create_task(request.skill_id, request.skill_version_id, request.runner_environment_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    background_tasks.add_task(run_task, task["id"])
    return task


@app.post("/api/tasks/{task_id}/run-now")
def run_now(task_id: str) -> dict[str, Any]:
    try:
        return run_task(task_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/tasks/{task_id}")
def task_detail(task_id: str) -> dict[str, Any]:
    from .evaluator import get_task

    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    return task


@app.get("/api/tasks/{task_id}/evidence-detail")
def task_evidence_detail(task_id: str) -> dict[str, Any]:
    with connect() as conn:
        return build_task_evidence_detail(conn, task_id)


@app.get("/api/overview")
def overview(category: str = "Data & Analytics") -> dict[str, Any]:
    with connect() as conn:
        skill_count = conn.execute("SELECT COUNT(*) AS count FROM skills").fetchone()["count"]
        evaluated_count = conn.execute(
            """
            SELECT COUNT(DISTINCT t.skill_id) AS count
            FROM evaluation_tasks t
            JOIN evaluation_runs r ON r.task_id = t.id
            WHERE r.status = 'completed'
            """
        ).fetchone()["count"]
        task_count = conn.execute("SELECT COUNT(*) AS count FROM evaluation_tasks").fetchone()["count"]
        leaderboard = rows_to_dicts(
            conn.execute(
                """
                SELECT s.id, s.skill_name, s.display_name, s.category, sv.version, r.overall_score, r.recommendation,
                       r.result_summary, r.finished_at AS last_evaluated_at
                FROM skills s
                JOIN skill_versions sv ON sv.id = s.latest_version_id
                JOIN evaluation_tasks t ON t.skill_id = s.id AND t.skill_version_id = sv.id
                JOIN evaluation_runs r ON r.task_id = t.id AND r.status = 'completed'
                WHERE s.category = ?
                  AND r.id = (
                    SELECT er2.id
                    FROM evaluation_tasks t2
                    JOIN evaluation_runs er2 ON er2.task_id = t2.id AND er2.status = 'completed'
                    WHERE t2.skill_id = s.id AND t2.skill_version_id = sv.id
                    ORDER BY er2.finished_at DESC, er2.id DESC
                    LIMIT 1
                  )
                ORDER BY r.finished_at DESC, r.id DESC
                """,
                (category,),
            ).fetchall()
        )
        leaderboard.sort(key=lambda item: (recommendation_rank(item.get("recommendation")), -summary_trigger_score(item), summary_scan_rank(item)))
        leaderboard = leaderboard[:10]
        categories = rows_to_dicts(conn.execute("SELECT * FROM categories WHERE enabled = 1 ORDER BY name").fetchall())
        return {
            "metrics": {
                "skills_total": skill_count,
                "evaluated_skills": evaluated_count,
                "evaluation_tasks": task_count,
                "users": 1,
            },
            "default_category": category,
            "categories": categories,
            "leaderboard": leaderboard,
        }
