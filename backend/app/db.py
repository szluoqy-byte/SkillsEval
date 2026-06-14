from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import DB_PATH, ensure_data_dirs


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def encode_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def decode_json(value: str | None, default: Any = None) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    for key in ("manifest", "frontmatter", "detected_roots", "warnings", "blocking_errors", "files", "assertions", "metrics", "result_summary", "evidence_refs", "request_payload", "draft_items"):
        if key in data:
            data[key] = decode_json(data[key], [] if key.endswith("s") or key in {"files", "assertions", "detected_roots", "warnings", "blocking_errors", "evidence_refs"} else {})
    return data


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [row_to_dict(row) for row in rows if row is not None]


@contextmanager
def connect(db_path: Path | None = None):
    ensure_data_dirs()
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path | None = None) -> None:
    with connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS categories (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL UNIQUE,
              description TEXT NOT NULL DEFAULT '',
              enabled INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS runner_environments (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL UNIQUE,
              runner_type TEXT NOT NULL,
              model_name TEXT NOT NULL,
              judge_model TEXT NOT NULL,
              command_path TEXT NOT NULL DEFAULT '',
              timeout_seconds INTEGER NOT NULL DEFAULT 60,
              enabled INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS scoring_weights (
              stage TEXT PRIMARY KEY,
              weight REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS model_api_providers (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL UNIQUE,
              provider_type TEXT NOT NULL,
              base_url TEXT NOT NULL,
              api_key TEXT NOT NULL,
              enabled INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS model_api_models (
              id TEXT PRIMARY KEY,
              provider_id TEXT NOT NULL,
              display_name TEXT NOT NULL,
              model_id TEXT NOT NULL,
              enabled INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(provider_id, model_id),
              FOREIGN KEY(provider_id) REFERENCES model_api_providers(id)
            );

            CREATE TABLE IF NOT EXISTS model_role_settings (
              role TEXT PRIMARY KEY,
              model_api_model_id TEXT,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(model_api_model_id) REFERENCES model_api_models(id)
            );

            CREATE TABLE IF NOT EXISTS skills (
              id TEXT PRIMARY KEY,
              skill_name TEXT NOT NULL UNIQUE,
              display_name TEXT NOT NULL,
              description TEXT NOT NULL DEFAULT '',
              card_content TEXT NOT NULL DEFAULT '',
              category TEXT NOT NULL,
              status TEXT NOT NULL,
              latest_version_id TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS skill_versions (
              id TEXT PRIMARY KEY,
              skill_id TEXT NOT NULL,
              version TEXT NOT NULL,
              manifest TEXT NOT NULL DEFAULT '{}',
              artifact_root TEXT NOT NULL,
              static_scan_status TEXT NOT NULL DEFAULT 'not_scanned',
              source_name TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL,
              UNIQUE(skill_id, version),
              FOREIGN KEY(skill_id) REFERENCES skills(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS skill_import_drafts (
              id TEXT PRIMARY KEY,
              source_type TEXT NOT NULL,
              source_name TEXT NOT NULL,
              source_path TEXT NOT NULL,
              status TEXT NOT NULL,
              detected_roots TEXT NOT NULL DEFAULT '[]',
              selected_root_path TEXT,
              suggested_skill_name TEXT NOT NULL DEFAULT '',
              suggested_display_name TEXT NOT NULL DEFAULT '',
              suggested_version TEXT,
              warnings TEXT NOT NULL DEFAULT '[]',
              blocking_errors TEXT NOT NULL DEFAULT '[]',
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS evaluation_sets (
              id TEXT PRIMARY KEY,
              skill_id TEXT NOT NULL UNIQUE,
              name TEXT NOT NULL,
              description TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL DEFAULT 'draft',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(skill_id) REFERENCES skills(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS trigger_queries (
              id TEXT PRIMARY KEY,
              eval_set_id TEXT NOT NULL,
              query TEXT NOT NULL,
              should_trigger INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(eval_set_id) REFERENCES evaluation_sets(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS effect_cases (
              id TEXT PRIMARY KEY,
              eval_set_id TEXT NOT NULL,
              case_key TEXT NOT NULL,
              prompt TEXT NOT NULL,
              expected_output TEXT NOT NULL,
              files TEXT NOT NULL DEFAULT '[]',
              assertions TEXT NOT NULL DEFAULT '[]',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(eval_set_id, case_key),
              FOREIGN KEY(eval_set_id) REFERENCES evaluation_sets(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS evaluation_tasks (
              id TEXT PRIMARY KEY,
              skill_id TEXT NOT NULL,
              skill_version_id TEXT NOT NULL,
              eval_set_id TEXT NOT NULL,
              runner_environment_id TEXT NOT NULL,
              task_scope TEXT NOT NULL DEFAULT 'full',
              status TEXT NOT NULL,
              created_by TEXT NOT NULL DEFAULT 'system',
              created_at TEXT NOT NULL,
              started_at TEXT,
              finished_at TEXT,
              FOREIGN KEY(skill_id) REFERENCES skills(id) ON DELETE CASCADE,
              FOREIGN KEY(skill_version_id) REFERENCES skill_versions(id) ON DELETE CASCADE,
              FOREIGN KEY(eval_set_id) REFERENCES evaluation_sets(id) ON DELETE CASCADE,
              FOREIGN KEY(runner_environment_id) REFERENCES runner_environments(id)
            );

            CREATE TABLE IF NOT EXISTS evaluation_runs (
              id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              status TEXT NOT NULL,
              current_stage TEXT NOT NULL,
              overall_score REAL,
              recommendation TEXT NOT NULL DEFAULT 'not_evaluated',
              result_summary TEXT NOT NULL DEFAULT '{}',
              artifact_root TEXT NOT NULL,
              created_at TEXT NOT NULL,
              started_at TEXT,
              finished_at TEXT,
              FOREIGN KEY(task_id) REFERENCES evaluation_tasks(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS stage_results (
              id TEXT PRIMARY KEY,
              run_id TEXT NOT NULL,
              stage TEXT NOT NULL,
              status TEXT NOT NULL,
              score REAL NOT NULL,
              summary TEXT NOT NULL,
              metrics TEXT NOT NULL DEFAULT '{}',
              artifact_path TEXT NOT NULL,
              FOREIGN KEY(run_id) REFERENCES evaluation_runs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS findings (
              id TEXT PRIMARY KEY,
              run_id TEXT NOT NULL,
              stage TEXT NOT NULL,
              code TEXT NOT NULL,
              severity TEXT NOT NULL,
              title TEXT NOT NULL,
              detail TEXT NOT NULL,
              file_path TEXT,
              line_number INTEGER,
              fix TEXT,
              FOREIGN KEY(run_id) REFERENCES evaluation_runs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS suggestions (
              id TEXT PRIMARY KEY,
              run_id TEXT NOT NULL,
              target TEXT NOT NULL,
              action TEXT NOT NULL,
              title TEXT NOT NULL,
              suggested_change TEXT NOT NULL,
              why TEXT NOT NULL,
              evidence_refs TEXT NOT NULL DEFAULT '[]',
              created_at TEXT NOT NULL,
              FOREIGN KEY(run_id) REFERENCES evaluation_runs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS evidence_items (
              id TEXT PRIMARY KEY,
              run_id TEXT NOT NULL,
              type TEXT NOT NULL,
              name TEXT NOT NULL,
              path TEXT NOT NULL,
              mime_type TEXT NOT NULL,
              size_bytes INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              FOREIGN KEY(run_id) REFERENCES evaluation_runs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS evaluation_set_generation_jobs (
              id TEXT PRIMARY KEY,
              skill_id TEXT NOT NULL,
              eval_set_id TEXT NOT NULL,
              target TEXT NOT NULL,
              status TEXT NOT NULL,
              progress_message TEXT NOT NULL DEFAULT '',
              request_payload TEXT NOT NULL DEFAULT '{}',
              draft_items TEXT NOT NULL DEFAULT '[]',
              error TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              completed_at TEXT,
              FOREIGN KEY(skill_id) REFERENCES skills(id) ON DELETE CASCADE,
              FOREIGN KEY(eval_set_id) REFERENCES evaluation_sets(id) ON DELETE CASCADE
            );
            """
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(categories)").fetchall()}
        if "enabled" not in columns:
            conn.execute("ALTER TABLE categories ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1")
        skill_columns = {row["name"] for row in conn.execute("PRAGMA table_info(skills)").fetchall()}
        if "card_content" not in skill_columns:
            conn.execute("ALTER TABLE skills ADD COLUMN card_content TEXT NOT NULL DEFAULT ''")
        runner_columns = {row["name"] for row in conn.execute("PRAGMA table_info(runner_environments)").fetchall()}
        if "command_path" not in runner_columns:
            conn.execute("ALTER TABLE runner_environments ADD COLUMN command_path TEXT NOT NULL DEFAULT ''")
        if "timeout_seconds" not in runner_columns:
            conn.execute("ALTER TABLE runner_environments ADD COLUMN timeout_seconds INTEGER NOT NULL DEFAULT 60")
        provider_columns = {row["name"] for row in conn.execute("PRAGMA table_info(model_api_providers)").fetchall()}
        if "updated_at" not in provider_columns:
            conn.execute("ALTER TABLE model_api_providers ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")
        model_columns = {row["name"] for row in conn.execute("PRAGMA table_info(model_api_models)").fetchall()}
        if "updated_at" not in model_columns:
            conn.execute("ALTER TABLE model_api_models ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")
        job_columns = {row["name"] for row in conn.execute("PRAGMA table_info(evaluation_set_generation_jobs)").fetchall()}
        if job_columns and "progress_message" not in job_columns:
            conn.execute("ALTER TABLE evaluation_set_generation_jobs ADD COLUMN progress_message TEXT NOT NULL DEFAULT ''")


def seed_db(db_path: Path | None = None) -> None:
    created = now_iso()
    categories = [
        ("cat_data", "Data & Analytics", "CSV, Excel, metrics, reporting, and business analysis skills."),
        ("cat_docs", "Documents & Knowledge", "PDF, Word, knowledge-base, contract, and report parsing skills."),
        ("cat_dev", "Developer Tools", "Code review, testing, PR analysis, and dependency inspection skills."),
        ("cat_research", "Research & Web", "Market research, web research, source collection, and synthesis skills."),
        ("cat_productivity", "Productivity & Office", "Slides, notes, email drafts, and office productivity skills."),
        ("cat_security", "Security & Compliance", "Permission, policy, sensitive-data, and audit skills."),
    ]
    runners = [
        (
            "runner_opencode_codex_spark",
            "OpenCode + GPT-5.3 Codex Spark",
            "opencode_cli",
            "openai/gpt-5.3-codex-spark",
            "not_configured",
            "/Users/yao/.opencode/bin/opencode",
            60,
        ),
    ]
    weights = [("static_scan", 0.20), ("trigger_eval", 0.25), ("effect_eval", 0.40), ("performance_eval", 0.15)]
    with connect(db_path) as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO categories (id, name, description, enabled, created_at) VALUES (?, ?, ?, 1, ?)",
            [(cid, name, desc, created) for cid, name, desc in categories],
        )
        conn.executemany(
            """
            INSERT OR IGNORE INTO runner_environments
              (id, name, runner_type, model_name, judge_model, command_path, timeout_seconds, enabled, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            [(rid, name, rtype, model, judge, command, timeout, created) for rid, name, rtype, model, judge, command, timeout in runners],
        )
        conn.execute(
            "UPDATE runner_environments SET enabled = 0 WHERE id != 'runner_opencode_codex_spark'"
        )
        conn.executemany(
            "INSERT OR IGNORE INTO scoring_weights (stage, weight) VALUES (?, ?)",
            weights,
        )
        conn.executemany(
            "INSERT OR IGNORE INTO model_role_settings (role, model_api_model_id, updated_at) VALUES (?, NULL, ?)",
            [("judge", created), ("data", created)],
        )
