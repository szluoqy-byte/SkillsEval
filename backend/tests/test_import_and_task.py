import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app import db
from app import importer
from app.db import init_db, seed_db
from app.evaluator import create_task, run_task
from app.main import app


def make_zip(files: dict[str, str]) -> bytes:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return payload.getvalue()


def fake_opencode(tmp_path):
    command = tmp_path / "fake-opencode.py"
    command.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "from pathlib import Path\n"
        "skills = list((Path.cwd() / '.opencode' / 'skills').glob('*/SKILL.md'))\n"
        "skill = skills[0].parent.name if skills else 'unknown'\n"
        "query = ' '.join(sys.argv)\n"
        "print(json.dumps({'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'summary valid' if skills else 'baseline'}]}}))\n"
        "if 'analyze' in query or 'trigger' in query:\n"
        "    print(json.dumps({'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'name': 'skill', 'input': {'name': skill}}]}}))\n",
        encoding="utf-8",
    )
    command.chmod(0o755)
    return command


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "skilleval.db")
    monkeypatch.setattr(importer, "IMPORT_DIR", tmp_path / "imports")
    monkeypatch.setattr(importer, "UPLOAD_DIR", tmp_path / "uploads")
    import app.evaluator as evaluator

    monkeypatch.setattr(evaluator, "RUN_DIR", tmp_path / "runs")
    init_db(db.DB_PATH)
    seed_db(db.DB_PATH)
    with db.connect() as conn:
        conn.execute("UPDATE runner_environments SET command_path = ?, timeout_seconds = 5", (str(fake_opencode(tmp_path)),))
    yield


def test_parse_root_skill_md_and_confirm_import():
    draft = importer.create_import_draft(
        "analytical-report.zip",
        make_zip({"SKILL.md": "---\nname: analytical-report\ndescription: Reports from sheets.\n---\n"}),
    )

    assert draft["status"] == "parsed"
    assert draft["suggested_skill_name"] == "analytical-report"

    skill = importer.confirm_import_draft(draft["id"], "analytical-report", "1.0.0", "Data & Analytics")

    assert skill["skill_name"] == "analytical-report"
    assert skill["latest_version"]["version"] == "1.0.0"


def test_multiple_skill_md_blocks_import():
    draft = importer.create_import_draft(
        "bundle.zip",
        make_zip({"one/SKILL.md": "---\nname: one\n---", "two/SKILL.md": "---\nname: two\n---"}),
    )

    assert draft["status"] == "failed"
    assert draft["blocking_errors"][0]["code"] == "MULTIPLE_SKILL_MD"


def test_duplicate_skill_version_is_blocked():
    draft = importer.create_import_draft("a.zip", make_zip({"a/SKILL.md": "---\nname: a\n---"}))
    importer.confirm_import_draft(draft["id"], "a", "1.0.0", "Data & Analytics")
    second = importer.create_import_draft("a-again.zip", make_zip({"a/SKILL.md": "---\nname: a\n---"}))

    with pytest.raises(ValueError):
        importer.confirm_import_draft(second["id"], "a", "1.0.0", "Data & Analytics")


def test_task_uses_bound_evaluation_set_and_generates_evidence():
    draft = importer.create_import_draft("sheet.zip", make_zip({"sheet/SKILL.md": "---\nname: sheet\ndescription: Sheet analysis helper.\n---\nUse for sheet analysis.\n"}))
    skill = importer.confirm_import_draft(draft["id"], "sheet", "1.0.0", "Data & Analytics")

    with db.connect() as conn:
        runner = conn.execute("SELECT * FROM runner_environments LIMIT 1").fetchone()
        eval_set = conn.execute("SELECT * FROM evaluation_sets WHERE skill_id = ?", (skill["id"],)).fetchone()
        conn.execute(
            "INSERT INTO trigger_queries (id, eval_set_id, query, should_trigger, created_at, updated_at) VALUES ('trq_test', ?, 'analyze this sheet', 1, 'now', 'now')",
            (eval_set["id"],),
        )
        conn.execute(
            """
            INSERT INTO effect_cases
              (id, eval_set_id, case_key, prompt, expected_output, files, assertions, created_at, updated_at)
            VALUES ('effect_test', ?, 'case-1', 'analyze', 'summary', '[]', '["contains \\"summary valid\\""]', 'now', 'now')
            """,
            (eval_set["id"],),
        )

    task = create_task(skill["id"], skill["latest_version"]["id"], runner["id"])
    completed = run_task(task["id"])

    assert completed["status"] == "completed"
    assert completed["run"]["overall_score"] is None
    assert completed["run"]["recommendation"] == "recommended"
    assert completed["run"]["result_summary"]["scan_score"] >= 0
    assert completed["run"]["result_summary"]["trigger_score"] == 100.0
    assert completed["run"]["result_summary"]["effect_status"] == "completed"
    assert len(completed["stage_results"]) == 3
    assert any(item["name"] == "report.json" for item in completed["evidence_items"])


def test_task_evidence_detail_returns_static_rules_trigger_results_and_artifacts():
    draft = importer.create_import_draft(
        "evidence.zip",
        make_zip({"evidence/SKILL.md": "---\nname: evidence\ndescription: Evidence skill.\n---\nUse for trigger evidence.\n"}),
    )
    skill = importer.confirm_import_draft(draft["id"], "evidence", "1.0.0", "Developer Tools")

    with db.connect() as conn:
        runner = conn.execute("SELECT * FROM runner_environments LIMIT 1").fetchone()
        eval_set = conn.execute("SELECT * FROM evaluation_sets WHERE skill_id = ?", (skill["id"],)).fetchone()
        conn.execute(
            "INSERT INTO trigger_queries (id, eval_set_id, query, should_trigger, created_at, updated_at) VALUES ('trq_positive', ?, 'please trigger evidence skill', 1, 'now', 'now')",
            (eval_set["id"],),
        )
        conn.execute(
            "INSERT INTO trigger_queries (id, eval_set_id, query, should_trigger, created_at, updated_at) VALUES ('trq_negative', ?, 'near miss', 0, 'now', 'now')",
            (eval_set["id"],),
        )

    task = create_task(skill["id"], skill["latest_version"]["id"], runner["id"])
    completed = run_task(task["id"])
    response = TestClient(app).get(f"/api/tasks/{completed['id']}/evidence-detail")

    assert response.status_code == 200
    detail = response.json()
    assert detail["run_id"] == completed["run"]["id"]
    assert detail["static_scan"]["rules"]
    assert {rule["status"] for rule in detail["static_scan"]["rules"]} == {"passed"}
    assert detail["trigger_eval"]["metrics"]["total_queries"] == 2
    assert {item["query_id"] for item in detail["trigger_eval"]["results"]} == {"trq_positive", "trq_negative"}
    assert detail["effect_eval"]["status"] == "no_cases"
    assert detail["performance_eval"]["status"] == "missing"
    assert any(item["type"] == "trigger_eval" for item in detail["artifacts"])


def test_scan_trigger_recommendation_policy_uses_three_metric_model():
    draft = importer.create_import_draft(
        "policy.zip",
        make_zip({"policy/SKILL.md": "---\nname: policy\ndescription: Policy skill.\n---\nUse for trigger policy.\n"}),
    )
    skill = importer.confirm_import_draft(draft["id"], "policy", "1.0.0", "Developer Tools")

    with db.connect() as conn:
        runner = conn.execute("SELECT * FROM runner_environments LIMIT 1").fetchone()
        eval_set = conn.execute("SELECT * FROM evaluation_sets WHERE skill_id = ?", (skill["id"],)).fetchone()
        conn.execute(
            "INSERT INTO trigger_queries (id, eval_set_id, query, should_trigger, created_at, updated_at) VALUES ('trq_policy', ?, 'please trigger policy skill', 1, 'now', 'now')",
            (eval_set["id"],),
        )

    task = create_task(skill["id"], skill["latest_version"]["id"], runner["id"])
    completed = run_task(task["id"])

    assert completed["run"]["overall_score"] is None
    assert completed["run"]["recommendation"] == "review_required"
    assert completed["run"]["result_summary"]["scan_status"] == "passed"
    assert completed["run"]["result_summary"]["trigger_score"] == 100.0


def test_critical_scan_caps_recommendation_at_review_required():
    draft = importer.create_import_draft("critical.zip", make_zip({"critical/SKILL.md": "---\nname: critical\n---\n"}))
    skill = importer.confirm_import_draft(draft["id"], "critical", "1.0.0", "Developer Tools")

    with db.connect() as conn:
        runner = conn.execute("SELECT * FROM runner_environments LIMIT 1").fetchone()
        eval_set = conn.execute("SELECT * FROM evaluation_sets WHERE skill_id = ?", (skill["id"],)).fetchone()
        conn.execute(
            "INSERT INTO trigger_queries (id, eval_set_id, query, should_trigger, created_at, updated_at) VALUES ('trq_critical', ?, 'please trigger critical skill', 1, 'now', 'now')",
            (eval_set["id"],),
        )

    completed = run_task(create_task(skill["id"], skill["latest_version"]["id"], runner["id"])["id"])

    assert completed["run"]["result_summary"]["scan_status"] == "critical"
    assert completed["run"]["result_summary"]["trigger_score"] == 100.0
    assert completed["run"]["recommendation"] == "review_required"


def test_scan_finding_review_no_risk_recalculates_score_status_and_recommendation():
    draft = importer.create_import_draft("review-risk.zip", make_zip({"review-risk/SKILL.md": "---\nname: review-risk\n---\nUse for review checks.\n"}))
    skill = importer.confirm_import_draft(draft["id"], "review-risk", "1.0.0", "Developer Tools")

    with db.connect() as conn:
        runner = conn.execute("SELECT * FROM runner_environments LIMIT 1").fetchone()
        eval_set = conn.execute("SELECT * FROM evaluation_sets WHERE skill_id = ?", (skill["id"],)).fetchone()
        conn.execute(
            "INSERT INTO trigger_queries (id, eval_set_id, query, should_trigger, created_at, updated_at) VALUES ('trq_review', ?, 'please trigger review-risk skill', 1, 'now', 'now')",
            (eval_set["id"],),
        )
        conn.execute(
            """
            INSERT INTO effect_cases
              (id, eval_set_id, case_key, prompt, expected_output, files, assertions, created_at, updated_at)
            VALUES ('effect_review', ?, 'case-review', 'analyze', 'summary', '[]', '["contains \\"summary valid\\""]', 'now', 'now')
            """,
            (eval_set["id"],),
        )

    completed = run_task(create_task(skill["id"], skill["latest_version"]["id"], runner["id"])["id"])
    finding = next(item for item in completed["findings"] if item["code"] == "FRONTMATTER-006")
    assert completed["run"]["result_summary"]["scan_status"] == "critical"
    assert completed["run"]["recommendation"] == "review_required"

    client = TestClient(app)
    response = client.put(
        f"/api/tasks/{completed['id']}/scan-findings/{finding['id']}/review",
        json={"review_severity": "no_risk", "review_note": "Confirmed false positive."},
    )
    missing_response = client.put(
        f"/api/tasks/{completed['id']}/scan-findings/fdg_missing/review",
        json={"review_severity": "no_risk"},
    )

    assert response.status_code == 200
    assert missing_response.status_code == 404
    detail = response.json()
    reviewed_rule = next(rule for rule in detail["static_scan"]["rules"] if rule["rule_id"] == "FRONTMATTER-006")
    reviewed_finding = reviewed_rule["finding"]
    assert detail["static_scan"]["score"] == 100.0
    assert detail["static_scan"]["status"] == "completed"
    assert detail["static_scan"]["metrics"]["critical_count"] == 0
    assert detail["static_scan"]["metrics"]["no_risk_count"] == 1
    assert reviewed_rule["status"] == "reviewed_no_risk"
    assert reviewed_finding["original_severity"] == "critical"
    assert reviewed_finding["effective_severity"] == "no_risk"
    assert reviewed_finding["review_note"] == "Confirmed false positive."

    updated = client.get(f"/api/tasks/{completed['id']}").json()
    assert updated["run"]["result_summary"]["scan_score"] == 100.0
    assert updated["run"]["result_summary"]["scan_status"] == "passed"
    assert updated["run"]["recommendation"] == "recommended"

    cleared = client.delete(f"/api/tasks/{completed['id']}/scan-findings/{finding['id']}/review")
    assert cleared.status_code == 200
    restored = client.get(f"/api/tasks/{completed['id']}").json()
    assert restored["run"]["result_summary"]["scan_status"] == "critical"
    assert restored["run"]["recommendation"] == "review_required"


def test_scan_finding_review_can_raise_minor_to_critical():
    draft = importer.create_import_draft(
        "review-upgrade.zip",
        make_zip({"review-upgrade/SKILL.md": "---\nname: review-upgrade\ndescription: Review upgrade skill.\nallowed-tools: Bash(git:*)\n---\nUse for review upgrade checks.\n"}),
    )
    skill = importer.confirm_import_draft(draft["id"], "review-upgrade", "1.0.0", "Developer Tools")

    with db.connect() as conn:
        runner = conn.execute("SELECT * FROM runner_environments LIMIT 1").fetchone()
        eval_set = conn.execute("SELECT * FROM evaluation_sets WHERE skill_id = ?", (skill["id"],)).fetchone()
        conn.execute(
            "INSERT INTO trigger_queries (id, eval_set_id, query, should_trigger, created_at, updated_at) VALUES ('trq_upgrade', ?, 'please trigger review-upgrade skill', 1, 'now', 'now')",
            (eval_set["id"],),
        )

    completed = run_task(create_task(skill["id"], skill["latest_version"]["id"], runner["id"])["id"])
    finding = next(item for item in completed["findings"] if item["code"] == "AWS-PERM-002")
    assert finding["severity"] == "minor"

    client = TestClient(app)
    response = client.put(
        f"/api/tasks/{completed['id']}/scan-findings/{finding['id']}/review",
        json={"review_severity": "critical"},
    )

    assert response.status_code == 200
    updated = client.get(f"/api/tasks/{completed['id']}").json()
    assert updated["run"]["result_summary"]["scan_status"] == "critical"
    assert updated["run"]["result_summary"]["scan_score"] == 75.0


def test_no_trigger_queries_are_not_recommended():
    draft = importer.create_import_draft(
        "empty-trigger.zip",
        make_zip({"empty-trigger/SKILL.md": "---\nname: empty-trigger\ndescription: Empty trigger skill.\n---\nUse for empty trigger checks.\n"}),
    )
    skill = importer.confirm_import_draft(draft["id"], "empty-trigger", "1.0.0", "Developer Tools")

    with db.connect() as conn:
        runner = conn.execute("SELECT * FROM runner_environments LIMIT 1").fetchone()

    completed = run_task(create_task(skill["id"], skill["latest_version"]["id"], runner["id"])["id"])

    assert completed["run"]["overall_score"] is None
    assert completed["run"]["result_summary"]["trigger_total_queries"] == 0
    assert completed["run"]["recommendation"] == "not_recommended"


def test_skill_and_task_lists_do_not_duplicate_after_multiple_runs():
    draft = importer.create_import_draft(
        "rerun.zip",
        make_zip({"rerun/SKILL.md": "---\nname: rerun\ndescription: Rerun skill.\n---\nUse for rerun checks.\n"}),
    )
    skill = importer.confirm_import_draft(draft["id"], "rerun", "1.0.0", "Developer Tools")

    with db.connect() as conn:
        runner = conn.execute("SELECT * FROM runner_environments LIMIT 1").fetchone()
    task = create_task(skill["id"], skill["latest_version"]["id"], runner["id"])

    with db.connect() as conn:
        for index, recommendation in enumerate(["review_required", "not_recommended"], start=1):
            run_id = f"run_rerun_{index}"
            conn.execute(
                """
                INSERT INTO evaluation_runs
                  (id, task_id, status, current_stage, overall_score, recommendation, result_summary, artifact_root, created_at, started_at, finished_at)
                VALUES (?, ?, 'completed', 'done', NULL, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    task["id"],
                    recommendation,
                    f'{{"trigger_score": {60 + index}}}',
                    f"/tmp/{run_id}",
                    f"2026-01-01T00:00:0{index}+00:00",
                    f"2026-01-01T00:00:0{index}+00:00",
                    f"2026-01-01T00:00:0{index}+00:00",
                ),
            )

    client = TestClient(app)
    skills_payload = client.get("/api/skills").json()
    rerun_rows = [item for item in skills_payload if item["id"] == skill["id"]]
    tasks_payload = client.get("/api/tasks").json()
    rerun_task_rows = [item for item in tasks_payload if item["id"] == task["id"]]

    assert len(rerun_rows) == 1
    assert rerun_rows[0]["recommendation"] == "not_recommended"
    assert rerun_rows[0]["result_summary"]["trigger_score"] == 62
    assert len(rerun_task_rows) == 1
    assert rerun_task_rows[0]["recommendation"] == "not_recommended"
