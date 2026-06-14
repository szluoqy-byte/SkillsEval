import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from app import db
from app import eval_generation
from app import importer
from app.db import init_db, seed_db
from app.eval_generation import confirm_generation_job, create_generation_job, get_job, run_generation_job
from app.main import app
from app.model_client import ModelCallResult


def make_zip(files: dict[str, str]) -> bytes:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return payload.getvalue()


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "skilleval.db")
    monkeypatch.setattr(importer, "IMPORT_DIR", tmp_path / "imports")
    monkeypatch.setattr(importer, "UPLOAD_DIR", tmp_path / "uploads")
    init_db(db.DB_PATH)
    seed_db(db.DB_PATH)
    yield


@pytest.fixture
def skill():
    draft = importer.create_import_draft(
        "data-helper.zip",
        make_zip(
            {
                "data-helper/SKILL.md": (
                    "---\n"
                    "name: data-helper\n"
                    "description: Helps analyze CSV and spreadsheet data.\n"
                    "---\n"
                    "Use this skill when users ask for data analysis, CSV summaries, or spreadsheet insights.\n"
                )
            }
        ),
    )
    return importer.confirm_import_draft(draft["id"], "data-helper", "1.0.0", "Data & Analytics")


def configured_data_model(monkeypatch, content: str):
    monkeypatch.setattr(eval_generation, "get_role_model", lambda role: {"id": "model_data"} if role == "data" else None)
    monkeypatch.setattr(eval_generation, "call_configured_model", lambda model, prompt, timeout_seconds=90: ModelCallResult(content=content))


def test_generation_prompt_defaults_to_chinese(skill):
    context = eval_generation.build_generation_context(skill["id"])

    prompt = eval_generation.build_generation_prompt("trigger_queries", 2, "", True, context)

    assert "默认使用中文生成用户可见内容" in prompt
    assert "query、prompt、expected_output、rationale 都使用中文" in prompt
    assert "无额外要求，按默认中文评测数据生成策略执行" in prompt


def test_generation_job_without_data_model_is_persisted_failed(skill, monkeypatch):
    monkeypatch.setattr(eval_generation, "get_role_model", lambda role: None)

    job = create_generation_job(skill["id"], "trigger_queries", 3, "", True)

    assert job["status"] == "failed"
    assert "Data model is not configured" in job["error"]
    assert get_job(job["id"])["status"] == "failed"


def test_trigger_generation_marks_duplicates_and_confirms_selected_items(skill, monkeypatch):
    with db.connect() as conn:
        eval_set = conn.execute("SELECT * FROM evaluation_sets WHERE skill_id = ?", (skill["id"],)).fetchone()
        conn.execute(
            "INSERT INTO trigger_queries (id, eval_set_id, query, should_trigger, created_at, updated_at) VALUES ('trq_existing', ?, 'analyze this csv', 1, 'now', 'now')",
            (eval_set["id"],),
        )
    configured_data_model(
        monkeypatch,
        json.dumps(
            {
                "items": [
                    {"query": "analyze this csv", "should_trigger": True, "rationale": "existing duplicate"},
                    {"query": "tell me a joke", "should_trigger": False, "rationale": "negative example"},
                ]
            }
        ),
    )

    job = create_generation_job(skill["id"], "trigger_queries", 5, "include edge cases", True)
    run_generation_job(job["id"])
    completed = get_job(job["id"])

    assert completed["status"] == "completed"
    duplicate, unique = completed["draft_items"]
    assert duplicate["duplicate"] is True
    assert duplicate["selected"] is False
    assert unique["duplicate"] is False
    assert unique["selected"] is True

    result = confirm_generation_job(job["id"], completed["draft_items"])

    assert result["status"] == "confirmed"
    assert result["inserted_count"] == 1
    with db.connect() as conn:
        count = conn.execute("SELECT COUNT(*) AS count FROM trigger_queries WHERE eval_set_id = ?", (completed["eval_set_id"],)).fetchone()["count"]
    assert count == 2


def test_effect_generation_normalizes_drafts_and_confirms(skill, monkeypatch):
    configured_data_model(
        monkeypatch,
        json.dumps(
            {
                "items": [
                    {
                        "case_key": "CSV Summary",
                        "prompt": "Summarize the uploaded CSV.",
                        "expected_output": "A concise data summary.",
                        "assertions": ['contains "summary"', "has at least 3 lines"],
                        "rationale": "checks useful output shape",
                    }
                ]
            }
        ),
    )

    job = create_generation_job(skill["id"], "effect_cases", 2, "deterministic assertions", False)
    run_generation_job(job["id"])
    completed = get_job(job["id"])

    assert completed["status"] == "completed"
    assert completed["draft_items"][0]["case_key"] == "csv_summary"
    result = confirm_generation_job(job["id"], completed["draft_items"])

    assert result["inserted_count"] == 1
    assert result["items"][0]["assertions"] == ['contains "summary"', "has at least 3 lines"]


def test_generation_invalid_json_marks_job_failed(skill, monkeypatch):
    configured_data_model(monkeypatch, "not json")

    job = create_generation_job(skill["id"], "effect_cases", 2, "", False)
    run_generation_job(job["id"])
    failed = get_job(job["id"])

    assert failed["status"] == "failed"
    assert "valid JSON" in failed["error"] or "invalid JSON" in failed["error"]


def test_generation_job_endpoints_restore_recent_jobs(skill, monkeypatch):
    configured_data_model(monkeypatch, json.dumps({"items": [{"query": "analyze the sales csv", "should_trigger": True}]}))
    client = TestClient(app)

    created = client.post(
        f"/api/skills/{skill['id']}/evaluation-set/generation-jobs",
        json={"target": "trigger_queries", "count": 1, "instruction": "", "include_negative": True},
    ).json()
    jobs = client.get(f"/api/skills/{skill['id']}/evaluation-set/generation-jobs").json()

    assert created["id"] in {job["id"] for job in jobs}
    assert client.get(f"/api/evaluation-set-generation-jobs/{created['id']}").json()["id"] == created["id"]
