from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from .config import RUN_DIR, WORKSPACE_DIR
from .db import connect, encode_json, now_iso, row_to_dict, rows_to_dicts
from .effect_evaluator import run_effect_eval
from .runner_adapter import run_trigger_eval
from .static_scanner import dumps_artifact, scan_skill_version


STAGES = ["static_scan", "trigger_eval", "effect_eval"]
NON_DELETABLE_TASK_STATUSES = {"queued", "running"}


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def evidence_record(run_id: str, evidence_type: str, name: str, path: Path) -> tuple:
    return (
        new_id("ev"),
        run_id,
        evidence_type,
        name,
        str(path),
        "application/json",
        path.stat().st_size,
        now_iso(),
    )


def cleanup_path_if_safe(path: Path, allowed_root: Path) -> str | None:
    resolved_root = allowed_root.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError:
        return f"Skipped unsafe cleanup path outside {resolved_root}: {resolved_path}"
    if not resolved_path.exists():
        return None
    try:
        if resolved_path.is_dir():
            shutil.rmtree(resolved_path)
        else:
            resolved_path.unlink()
    except OSError as error:
        return f"Failed to clean {resolved_path}: {error}"
    return None


def delete_task(task_id: str) -> dict[str, Any]:
    with connect() as conn:
        task = conn.execute("SELECT * FROM evaluation_tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            raise KeyError("Task not found.")
        if str(task["status"]) in NON_DELETABLE_TASK_STATUSES:
            raise RuntimeError("Queued or running tasks cannot be deleted.")
        runs = rows_to_dicts(conn.execute("SELECT id, artifact_root FROM evaluation_runs WHERE task_id = ?", (task_id,)).fetchall())
        artifact_paths = [Path(str(run["artifact_root"])) for run in runs if run.get("artifact_root")]
        workspace_paths = [WORKSPACE_DIR / str(run["id"]) for run in runs]
        conn.execute("DELETE FROM evaluation_tasks WHERE id = ?", (task_id,))

    cleanup_errors: list[str] = []
    for path in artifact_paths:
        error = cleanup_path_if_safe(path, RUN_DIR)
        if error:
            cleanup_errors.append(error)
    for path in workspace_paths:
        error = cleanup_path_if_safe(path, WORKSPACE_DIR)
        if error:
            cleanup_errors.append(error)

    return {
        "status": "deleted",
        "id": task_id,
        "deleted_runs": len(runs),
        "cleanup_errors": cleanup_errors,
    }


def recommendation_for(
    scan_status: str,
    trigger_score: float,
    trigger_total: int,
    effect_score: float | None = None,
    effect_valid_cases: int = 0,
    skill_lift: float = 0.0,
    cost_efficiency: str = "",
    run_failed: bool = False,
) -> str:
    if run_failed or trigger_total <= 0 or trigger_score < 50:
        return "not_recommended"
    if effect_score is not None and effect_score < 50:
        return "not_recommended"
    if skill_lift < -0.05:
        return "not_recommended"
    if scan_status == "critical":
        return "review_required"
    if scan_status == "warning":
        return "review_required"
    if effect_valid_cases <= 0:
        return "review_required"
    if effect_score is not None and effect_score >= 80 and trigger_score >= 80 and skill_lift > 0 and cost_efficiency != "PARETO_WORSE":
        return "recommended"
    if trigger_score >= 80 and effect_score is not None and effect_score >= 60:
        return "usable"
    return "review_required"


def create_task(skill_id: str, skill_version_id: str, runner_environment_id: str) -> dict[str, Any]:
    created = now_iso()
    task_id = new_id("task")
    with connect() as conn:
        eval_set = conn.execute("SELECT * FROM evaluation_sets WHERE skill_id = ?", (skill_id,)).fetchone()
        if not eval_set:
            raise ValueError("Skill does not have a bound evaluation set.")
        version = conn.execute(
            "SELECT * FROM skill_versions WHERE id = ? AND skill_id = ?",
            (skill_version_id, skill_id),
        ).fetchone()
        if not version:
            raise ValueError("Skill version does not belong to this skill.")
        runner = conn.execute("SELECT * FROM runner_environments WHERE id = ? AND enabled = 1", (runner_environment_id,)).fetchone()
        if not runner:
            raise ValueError("Runner environment is not available.")
        conn.execute(
            """
            INSERT INTO evaluation_tasks
              (id, skill_id, skill_version_id, eval_set_id, runner_environment_id, task_scope, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'full', 'queued', ?)
            """,
            (task_id, skill_id, skill_version_id, eval_set["id"], runner_environment_id, created),
        )
        return get_task(task_id, conn)


def run_task(task_id: str) -> dict[str, Any]:
    with connect() as conn:
        task = conn.execute("SELECT * FROM evaluation_tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            raise ValueError("Task not found.")
        if task["status"] == "completed":
            return get_task(task_id, conn)

        started = now_iso()
        conn.execute("UPDATE evaluation_tasks SET status = 'running', started_at = ? WHERE id = ?", (started, task_id))
        run_id = new_id("run")
        run_root = RUN_DIR / run_id
        conn.execute(
            """
            INSERT INTO evaluation_runs
              (id, task_id, status, current_stage, artifact_root, created_at, started_at)
            VALUES (?, ?, 'running', 'static_scan', ?, ?, ?)
            """,
            (run_id, task_id, str(run_root), started, started),
        )

        task_data = row_to_dict(task)
        skill = row_to_dict(conn.execute("SELECT * FROM skills WHERE id = ?", (task["skill_id"],)).fetchone())
        version = row_to_dict(conn.execute("SELECT * FROM skill_versions WHERE id = ?", (task["skill_version_id"],)).fetchone())
        runner = row_to_dict(conn.execute("SELECT * FROM runner_environments WHERE id = ?", (task["runner_environment_id"],)).fetchone())
        triggers = rows_to_dicts(conn.execute("SELECT * FROM trigger_queries WHERE eval_set_id = ?", (task["eval_set_id"],)).fetchall())
        effect_cases = rows_to_dicts(conn.execute("SELECT * FROM effect_cases WHERE eval_set_id = ?", (task["eval_set_id"],)).fetchall())

    try:
        static_scan = scan_skill_version(version["artifact_root"], version.get("manifest", {}))
        static_score = static_scan["score"]
        trigger_eval = run_trigger_eval(
            runner=runner,
            artifact_root=version["artifact_root"],
            skill_name=skill["skill_name"],
            trigger_queries=triggers,
            run_root=run_root,
            workspace_root=WORKSPACE_DIR / run_id / "trigger",
        )
        trigger_score = trigger_eval["score"]
        effect_eval = run_effect_eval(
            runner=runner,
            artifact_root=version["artifact_root"],
            skill_name=skill["skill_name"],
            effect_cases=effect_cases,
            run_root=run_root,
            workspace_root=WORKSPACE_DIR / run_id / "effect",
        )
    except Exception:
        with connect() as conn:
            finished = now_iso()
            conn.execute(
                "UPDATE evaluation_runs SET status = 'failed', current_stage = 'failed', finished_at = ? WHERE id = ?",
                (finished, run_id),
            )
            conn.execute("UPDATE evaluation_tasks SET status = 'failed', finished_at = ? WHERE id = ?", (finished, task_id))
        raise

    effect_score = effect_eval.get("score")
    effect_metrics = effect_eval.get("metrics", {})
    scores = {
        "static_scan": static_score,
        "trigger_eval": trigger_score,
        "effect_eval": effect_score or 0.0,
    }
    overall = None
    recommendation = recommendation_for(
        static_scan["status"],
        trigger_score,
        int(trigger_eval["metrics"]["total_queries"]),
        float(effect_score) if effect_score is not None else None,
        int(effect_metrics.get("valid_cases") or 0),
        float(effect_metrics.get("skill_lift") or 0.0),
        str(effect_metrics.get("cost_efficiency_classification") or ""),
        any(item.get("error") for item in trigger_eval.get("results", [])),
    )

    artifacts = {
        "static_scan": run_root / "static" / "findings.json",
        "trigger_eval": run_root / "trigger" / "report.json",
        "effect_eval": run_root / "effect" / "report.json",
    }
    static_metrics_path = run_root / "static" / "static_metrics.json"
    write_json(artifacts["static_scan"], dumps_artifact(static_scan))
    write_json(static_metrics_path, static_scan["metrics"])
    write_json(artifacts["trigger_eval"], trigger_eval)

    stage_summaries = {
        "static_scan": static_scan["summary"],
        "trigger_eval": trigger_eval["summary"],
        "effect_eval": effect_eval["summary"],
    }
    stage_statuses = {
        "static_scan": "completed",
        "trigger_eval": "completed",
        "effect_eval": effect_eval["status"],
    }
    stage_metrics = {
        "static_scan": static_scan["metrics"],
        "trigger_eval": trigger_eval["metrics"],
        "effect_eval": effect_eval["metrics"],
    }

    with connect() as conn:
        for stage in STAGES:
            conn.execute(
                """
                INSERT INTO stage_results
                  (id, run_id, stage, status, score, summary, metrics, artifact_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("stage"),
                    run_id,
                    stage,
                    stage_statuses[stage],
                    scores[stage],
                    stage_summaries[stage],
                    encode_json(stage_metrics[stage]),
                    str(artifacts[stage]),
                ),
            )

        finding_rows = [
            (
                new_id("finding"),
                run_id,
                "static_scan",
                item["code"],
                item["severity"],
                item["title"],
                item["detail"],
                item.get("file_path"),
                item.get("line_number"),
                item.get("fix"),
            )
            for item in static_scan["findings"]
        ]
        if finding_rows:
            conn.executemany(
                """
                INSERT INTO findings
                  (id, run_id, stage, code, severity, title, detail, file_path, line_number, fix)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                finding_rows,
            )
        conn.execute(
            """
            INSERT INTO suggestions
              (id, run_id, target, action, title, suggested_change, why, evidence_refs, created_at)
            VALUES (?, ?, 'evaluation_set', 'add_case', ?, ?, ?, ?, ?)
            """,
            (
                new_id("sug"),
                run_id,
                "补齐 hard negative trigger queries",
                "为当前 Skill 增加 3-5 条相邻但不应触发的负样本。",
                "真实 trigger_eval 会按正负样本是否实际触发 Skill 计算 trigger_score。",
                encode_json(["trigger.report.json"]),
                now_iso(),
            ),
        )
        evidence = [evidence_record(run_id, stage, path.name, path) for stage, path in artifacts.items()]
        evidence.append(evidence_record(run_id, "static_scan", "static_metrics.json", static_metrics_path))
        report_path = run_root / "report.json"
        result_summary = {
            "scan_score": static_score,
            "scan_status": static_scan["status"],
            "static_score": static_score,
            "trigger_score": trigger_score,
            "effect_score": effect_score,
            "effect_status": effect_eval["status"],
            "effect_valid_cases": effect_metrics.get("valid_cases", 0),
            "effect_total_cases": effect_metrics.get("total_cases", 0),
            "with_skill_pass_rate": effect_metrics.get("with_skill_pass_rate"),
            "without_skill_pass_rate": effect_metrics.get("without_skill_pass_rate"),
            "skill_lift": effect_metrics.get("skill_lift"),
            "cost_efficiency_classification": effect_metrics.get("cost_efficiency_classification"),
            "trigger_matched_queries": trigger_eval["metrics"]["matched_queries"],
            "trigger_passed_queries": trigger_eval["metrics"]["passed_queries"],
            "trigger_total_queries": trigger_eval["metrics"]["total_queries"],
        }
        write_json(report_path, {"run_id": run_id, "recommendation": recommendation, "result_summary": result_summary})
        evidence.append(evidence_record(run_id, "report", "report.json", report_path))
        conn.executemany(
            """
            INSERT INTO evidence_items
              (id, run_id, type, name, path, mime_type, size_bytes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            evidence,
        )
        finished = now_iso()
        conn.execute(
            """
            UPDATE evaluation_runs
            SET status = 'completed', current_stage = 'done', overall_score = ?, recommendation = ?,
                result_summary = ?, finished_at = ?
            WHERE id = ?
            """,
            (overall, recommendation, encode_json(result_summary), finished, run_id),
        )
        conn.execute("UPDATE evaluation_tasks SET status = 'completed', finished_at = ? WHERE id = ?", (finished, task_id))
        conn.execute("UPDATE skill_versions SET static_scan_status = ? WHERE id = ?", (static_scan["status"], task_data["skill_version_id"]))
        conn.execute("UPDATE skills SET status = 'report_ready', updated_at = ? WHERE id = ?", (finished, task_data["skill_id"]))
        return get_task(task_id, conn)


def get_task(task_id: str, conn=None) -> dict[str, Any] | None:
    own_conn = conn is None
    if own_conn:
        ctx = connect()
        conn = ctx.__enter__()
    try:
        row = conn.execute(
            """
            SELECT t.*, s.skill_name, s.display_name AS skill_display_name, sv.version, r.name AS runner_name
            FROM evaluation_tasks t
            JOIN skills s ON s.id = t.skill_id
            JOIN skill_versions sv ON sv.id = t.skill_version_id
            JOIN runner_environments r ON r.id = t.runner_environment_id
            WHERE t.id = ?
            """,
            (task_id,),
        ).fetchone()
        if not row:
            return None
        task = row_to_dict(row)
        run = conn.execute("SELECT * FROM evaluation_runs WHERE task_id = ? ORDER BY created_at DESC LIMIT 1", (task_id,)).fetchone()
        task["run"] = row_to_dict(run)
        if task["run"]:
            run_id = task["run"]["id"]
            task["stage_results"] = rows_to_dicts(conn.execute("SELECT * FROM stage_results WHERE run_id = ? ORDER BY rowid", (run_id,)).fetchall())
            task["findings"] = rows_to_dicts(conn.execute("SELECT * FROM findings WHERE run_id = ?", (run_id,)).fetchall())
            task["suggestions"] = rows_to_dicts(conn.execute("SELECT * FROM suggestions WHERE run_id = ?", (run_id,)).fetchall())
            task["evidence_items"] = rows_to_dicts(conn.execute("SELECT * FROM evidence_items WHERE run_id = ?", (run_id,)).fetchall())
        else:
            task["stage_results"] = []
            task["findings"] = []
            task["suggestions"] = []
            task["evidence_items"] = []
        return task
    finally:
        if own_conn:
            ctx.__exit__(None, None, None)
