from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .db import connect, encode_json, now_iso, row_to_dict, rows_to_dicts
from .importer import new_id
from .model_client import call_configured_model, get_role_model


GENERATION_TARGETS = {"trigger_queries", "effect_cases"}
MAX_GENERATION_COUNT = 20
DEFAULT_GENERATION_LANGUAGE_INSTRUCTION = "默认使用中文生成用户可见内容；除 case_key 和 assertion DSL 关键字外，query、prompt、expected_output、rationale 都使用中文。"


def clamp_count(value: int) -> int:
    return max(1, min(MAX_GENERATION_COUNT, int(value or 1)))


def get_job(job_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        return row_to_dict(conn.execute("SELECT * FROM evaluation_set_generation_jobs WHERE id = ?", (job_id,)).fetchone())


def list_jobs_for_skill(skill_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        return rows_to_dicts(
            conn.execute(
                """
                SELECT *
                FROM evaluation_set_generation_jobs
                WHERE skill_id = ? AND status IN ('queued', 'running', 'completed', 'failed')
                ORDER BY created_at DESC
                LIMIT 10
                """,
                (skill_id,),
            ).fetchall()
        )


def create_generation_job(skill_id: str, target: str, count: int, instruction: str, include_negative: bool) -> dict[str, Any]:
    if target not in GENERATION_TARGETS:
        raise ValueError("target must be trigger_queries or effect_cases.")
    clean_count = clamp_count(count)
    created = now_iso()
    job_id = new_id("gen")
    request_payload = {
        "target": target,
        "count": clean_count,
        "instruction": instruction.strip(),
        "include_negative": bool(include_negative),
        "context_mode": "skill_md",
    }
    with connect() as conn:
        eval_set = conn.execute("SELECT * FROM evaluation_sets WHERE skill_id = ?", (skill_id,)).fetchone()
        if not eval_set:
            raise ValueError("Evaluation set not found.")
        data_model = get_role_model("data")
        status = "queued" if data_model else "failed"
        error = "" if data_model else "Data model is not configured. Please configure Model Roles in system settings."
        progress = "等待后台生成" if data_model else "数据模型未配置"
        conn.execute(
            """
            INSERT INTO evaluation_set_generation_jobs
              (id, skill_id, eval_set_id, target, status, progress_message, request_payload, draft_items, error, created_at, updated_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, '[]', ?, ?, ?, ?)
            """,
            (job_id, skill_id, eval_set["id"], target, status, progress, encode_json(request_payload), error, created, created, created if error else None),
        )
        return row_to_dict(conn.execute("SELECT * FROM evaluation_set_generation_jobs WHERE id = ?", (job_id,)).fetchone())


def delete_generation_job(job_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM evaluation_set_generation_jobs WHERE id = ?", (job_id,))


def update_job(job_id: str, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = now_iso()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = [encode_json(value) if key in {"draft_items", "request_payload"} else value for key, value in fields.items()]
    with connect() as conn:
        conn.execute(f"UPDATE evaluation_set_generation_jobs SET {assignments} WHERE id = ?", [*values, job_id])


def run_generation_job(job_id: str) -> None:
    job = get_job(job_id)
    if not job or job["status"] == "failed":
        return
    update_job(job_id, status="running", progress_message="正在读取 Skill 上下文")
    try:
        context = build_generation_context(job["skill_id"])
        model = get_role_model("data")
        if not model:
            raise ValueError("Data model is not configured. Please configure Model Roles in system settings.")
        request_payload = job.get("request_payload") or {}
        prompt = build_generation_prompt(
            target=job["target"],
            count=clamp_count(int(request_payload.get("count") or 1)),
            instruction=str(request_payload.get("instruction") or ""),
            include_negative=bool(request_payload.get("include_negative")),
            context=context,
        )
        update_job(job_id, progress_message="正在调用数据模型生成候选样例")
        result = call_configured_model(model, prompt, timeout_seconds=90)
        if result.error:
            raise ValueError(result.error)
        raw_items = extract_items(result.content)
        draft_items = normalize_draft_items(job["target"], raw_items, context, clamp_count(int(request_payload.get("count") or 1)))
        if not draft_items:
            raise ValueError("Data model returned no usable draft items.")
        draft_items = mark_duplicates(job["eval_set_id"], job["target"], draft_items)
        update_job(
            job_id,
            status="completed",
            progress_message=f"已生成 {len(draft_items)} 条候选草稿",
            draft_items=draft_items,
            error="",
            completed_at=now_iso(),
        )
    except Exception as error:
        update_job(
            job_id,
            status="failed",
            progress_message="生成失败",
            error=str(error),
            completed_at=now_iso(),
        )


def build_generation_context(skill_id: str) -> dict[str, Any]:
    with connect() as conn:
        skill = row_to_dict(conn.execute("SELECT * FROM skills WHERE id = ?", (skill_id,)).fetchone())
        if not skill:
            raise ValueError("Skill not found.")
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
            raise ValueError("Skill has no version artifact.")
        version_dict = row_to_dict(version)
        skill_md = read_skill_md(Path(version["artifact_root"]), version_dict.get("manifest") or {})
        return {
            "skill": skill,
            "version": version_dict,
            "skill_md": skill_md[:12000],
        }


def read_skill_md(root: Path, manifest: dict[str, Any]) -> str:
    candidates = [root / "SKILL.md", root / "skill.md"]
    source_path = manifest.get("source_skill_md_path")
    if isinstance(source_path, str):
        candidates.insert(0, root / Path(source_path).name)
    for path in candidates:
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")
    return ""


def build_generation_prompt(target: str, count: int, instruction: str, include_negative: bool, context: dict[str, Any]) -> str:
    skill = context["skill"]
    clean_instruction = instruction.strip() or "无额外要求，按默认中文评测数据生成策略执行。"
    base = f"""你是 SkillsEval 的评测数据生成助手。请基于 Skill 元信息和 SKILL.md 生成高质量评测数据草稿。

输出必须是严格 JSON，不要 Markdown，不要解释文字。
不要引用不存在的文件。优先生成多样、可复核、不过度相似的数据。
{DEFAULT_GENERATION_LANGUAGE_INSTRUCTION}

Skill:
- skill_name: {skill.get("skill_name")}
- display_name: {skill.get("display_name")}
- category: {skill.get("category")}
- description: {skill.get("description")}

SKILL.md:
{context.get("skill_md") or "(empty)"}

用户补充要求:
{clean_instruction}
"""
    if target == "trigger_queries":
        negative = "必须包含 should_trigger=true 和 should_trigger=false 两类样例。" if include_negative else "可以只生成 should_trigger=true 的样例。"
        return base + f"""
请生成 {count} 条 Trigger Query 草稿。{negative}
JSON schema:
{{"items":[{{"query":"用户会输入的自然语言请求","should_trigger":true,"rationale":"为什么这是合理样例"}}]}}
"""
    return base + f"""
请生成 {count} 条 Effect Case 草稿。
assertions 优先使用 deterministic DSL，例如 contains、does not contain、matches regex、is valid json、has at least N lines；语义判断才使用 judge: 前缀。
JSON schema:
{{"items":[{{"case_key":"lower_snake_case_key","prompt":"发给 Runner 的任务","expected_output":"自然语言目标描述","assertions":["contains \\"...\\"","judge: ..."],"rationale":"为什么这个 case 能验证效果"}}]}}
"""


def extract_items(content: str) -> list[dict[str, Any]]:
    payload = extract_json(content)
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return [item for item in payload["items"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def extract_json(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", content)
        if not match:
            raise ValueError("Data model did not return valid JSON.")
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as error:
            raise ValueError(f"Data model returned invalid JSON: {error}") from error


def normalize_draft_items(target: str, items: list[dict[str, Any]], context: dict[str, Any], count: int) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items[:count], start=1):
        if target == "trigger_queries":
            query = str(item.get("query") or "").strip()
            if not query:
                continue
            normalized.append(
                {
                    "id": new_id("draft"),
                    "selected": True,
                    "duplicate": False,
                    "query": query,
                    "should_trigger": bool(item.get("should_trigger")),
                    "rationale": str(item.get("rationale") or "").strip(),
                }
            )
        else:
            prompt = str(item.get("prompt") or "").strip()
            expected_output = str(item.get("expected_output") or "").strip()
            if not prompt or not expected_output:
                continue
            assertions = item.get("assertions") if isinstance(item.get("assertions"), list) else []
            clean_assertions = [str(assertion).strip() for assertion in assertions if str(assertion).strip()]
            case_key = normalize_case_key(str(item.get("case_key") or f"generated_case_{index}"))
            normalized.append(
                {
                    "id": new_id("draft"),
                    "selected": True,
                    "duplicate": False,
                    "case_key": case_key,
                    "prompt": prompt,
                    "expected_output": expected_output,
                    "files": [],
                    "assertions": clean_assertions,
                    "rationale": str(item.get("rationale") or "").strip(),
                }
            )
    return normalized


def normalize_case_key(value: str) -> str:
    key = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return key or "generated_case"


def mark_duplicates(eval_set_id: str, target: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    with connect() as conn:
        if target == "trigger_queries":
            existing = {row["query"].strip().lower() for row in conn.execute("SELECT query FROM trigger_queries WHERE eval_set_id = ?", (eval_set_id,)).fetchall()}
            seen: set[str] = set()
            for item in items:
                key = item["query"].strip().lower()
                item["duplicate"] = key in existing or key in seen
                item["selected"] = not item["duplicate"]
                seen.add(key)
        else:
            existing = {row["case_key"].strip().lower() for row in conn.execute("SELECT case_key FROM effect_cases WHERE eval_set_id = ?", (eval_set_id,)).fetchall()}
            seen = set()
            for item in items:
                key = item["case_key"].strip().lower()
                item["duplicate"] = key in existing or key in seen
                item["selected"] = not item["duplicate"]
                seen.add(key)
    return items


def confirm_generation_job(job_id: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise ValueError("Generation job not found.")
    if job["status"] != "completed":
        raise ValueError("Generation job is not completed.")
    selected = [item for item in items if item.get("selected")]
    if not selected:
        raise ValueError("No draft items selected.")
    created = now_iso()
    inserted: list[dict[str, Any]] = []
    with connect() as conn:
        if job["target"] == "trigger_queries":
            for item in selected:
                query = str(item.get("query") or "").strip()
                if not query:
                    continue
                item_id = new_id("trq")
                conn.execute(
                    "INSERT INTO trigger_queries (id, eval_set_id, query, should_trigger, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (item_id, job["eval_set_id"], query, 1 if item.get("should_trigger") else 0, created, created),
                )
                inserted.append(row_to_dict(conn.execute("SELECT * FROM trigger_queries WHERE id = ?", (item_id,)).fetchone()))
        else:
            for item in selected:
                case_key = normalize_case_key(str(item.get("case_key") or ""))
                prompt = str(item.get("prompt") or "").strip()
                expected_output = str(item.get("expected_output") or "").strip()
                if not case_key or not prompt or not expected_output:
                    continue
                item_id = new_id("effect")
                conn.execute(
                    """
                    INSERT INTO effect_cases
                      (id, eval_set_id, case_key, prompt, expected_output, files, assertions, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item_id,
                        job["eval_set_id"],
                        case_key,
                        prompt,
                        expected_output,
                        encode_json(item.get("files") if isinstance(item.get("files"), list) else []),
                        encode_json(item.get("assertions") if isinstance(item.get("assertions"), list) else []),
                        created,
                        created,
                    ),
                )
                inserted.append(row_to_dict(conn.execute("SELECT * FROM effect_cases WHERE id = ?", (item_id,)).fetchone()))
        if not inserted:
            raise ValueError("No valid draft items selected.")
        conn.execute(
            "UPDATE evaluation_set_generation_jobs SET status = 'confirmed', draft_items = ?, updated_at = ?, completed_at = COALESCE(completed_at, ?) WHERE id = ?",
            (encode_json(items), now_iso(), now_iso(), job_id),
        )
    return {"status": "confirmed", "inserted_count": len(inserted), "items": inserted}
