import io
import json
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db
from app import importer
from app.db import init_db, seed_db
from app.effect_evaluator import run_effect_eval
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
        "content = [{'type': 'tool_use', 'name': 'skill', 'input': {'name': skill}}] if 'trigger' in query else []\n"
        "print(json.dumps({'type': 'assistant', 'message': {'content': content}}))\n",
        encoding="utf-8",
    )
    command.chmod(0o755)
    return command


def start_model_server(response_payload: dict, status: int = 200):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            requests.append({"path": self.path, "headers": dict(self.headers), "body": json.loads(body)})
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response_payload).encode("utf-8"))

        def log_message(self, format, *args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, requests


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


@pytest.fixture
def client():
    return TestClient(app)


def test_category_create_update_duplicate_and_public_filter(client):
    created = client.post("/api/settings/categories", json={"name": "Audio", "description": "Voice skills"}).json()

    assert created["name"] == "Audio"
    assert created["enabled"] == 1
    duplicate = client.post("/api/settings/categories", json={"name": "Audio", "description": ""})
    assert duplicate.status_code == 400

    updated = client.put(
        f"/api/settings/categories/{created['id']}",
        json={"name": "Audio & Speech", "description": "Speech skills", "enabled": False},
    ).json()

    assert updated["name"] == "Audio & Speech"
    assert updated["enabled"] == 0
    public_names = [item["name"] for item in client.get("/api/categories").json()]
    assert "Audio & Speech" not in public_names


def test_delete_unreferenced_category_hard_deletes(client):
    created = client.post("/api/settings/categories", json={"name": "Temporary", "description": ""}).json()

    deleted = client.delete(f"/api/settings/categories/{created['id']}").json()

    assert deleted["status"] == "deleted"
    all_ids = [item["id"] for item in client.get("/api/settings/categories").json()]
    assert created["id"] not in all_ids


def test_delete_referenced_category_disables(client):
    draft = importer.create_import_draft("a.zip", make_zip({"a/SKILL.md": "---\nname: a\n---"}))
    importer.confirm_import_draft(draft["id"], "a", "1.0.0", "Data & Analytics")
    categories = client.get("/api/settings/categories").json()
    category = next(item for item in categories if item["name"] == "Data & Analytics")

    deleted = client.delete(f"/api/settings/categories/{category['id']}").json()

    assert deleted["status"] == "disabled"
    refreshed = client.get("/api/settings/categories").json()
    assert next(item for item in refreshed if item["id"] == category["id"])["enabled"] == 0
    public_names = [item["name"] for item in client.get("/api/categories").json()]
    assert "Data & Analytics" not in public_names


def test_runner_create_update_duplicate_disable_and_public_filter(client):
    created = client.post(
        "/api/settings/runners",
        json={
            "name": "Local Test Runner",
            "runner_type": "local_cli",
            "model_name": "test-model",
            "judge_model": "judge",
            "command_path": "/tmp/fake-opencode",
            "timeout_seconds": 5,
        },
    ).json()

    assert created["enabled"] == 1
    duplicate = client.post(
        "/api/settings/runners",
        json={
            "name": "Local Test Runner",
            "runner_type": "local_cli",
            "model_name": "test-model",
            "judge_model": "judge",
            "command_path": "/tmp/fake-opencode",
            "timeout_seconds": 5,
        },
    )
    assert duplicate.status_code == 400

    updated = client.put(
        f"/api/settings/runners/{created['id']}",
        json={
            "name": "Local Test Runner 2",
            "runner_type": "local_cli",
            "model_name": "test-model-2",
            "judge_model": "judge",
            "command_path": "/tmp/fake-opencode-2",
            "timeout_seconds": 7,
            "enabled": True,
        },
    ).json()
    assert updated["model_name"] == "test-model-2"
    assert updated["timeout_seconds"] == 7

    disabled = client.delete(f"/api/settings/runners/{created['id']}").json()
    assert disabled["status"] == "disabled"
    public_names = [item["name"] for item in client.get("/api/runners").json()]
    assert "Local Test Runner 2" not in public_names


def test_model_provider_model_roles_mask_key_and_openai_judge(client, tmp_path):
    server, requests = start_model_server(
        {
            "choices": [
                {"message": {"content": json.dumps({"results": [{"text": "judge assertion", "passed": True, "evidence": "ok", "confidence": 0.9, "uncertain": False}]})}}
            ],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
        }
    )
    try:
        provider = client.post(
            "/api/settings/model-providers",
            json={
                "name": "DeepSeek",
                "provider_type": "openai_compatible",
                "base_url": f"http://127.0.0.1:{server.server_port}/v1",
                "api_key": "sk-test-secret-1234",
            },
        ).json()
        assert provider["api_key_configured"] is True
        assert provider["api_key_preview"].endswith("1234")
        assert "api_key" not in provider

        duplicate = client.post(
            "/api/settings/model-providers",
            json={
                "name": "DeepSeek",
                "provider_type": "openai_compatible",
                "base_url": f"http://127.0.0.1:{server.server_port}/v1",
                "api_key": "sk-test-secret-1234",
            },
        )
        assert duplicate.status_code == 400

        model = client.post(
            "/api/settings/model-models",
            json={"provider_id": provider["id"], "display_name": "DeepSeek Chat", "model_id": "deepseek-chat"},
        ).json()
        roles = client.put("/api/settings/model-roles", json={"judge_model_id": model["id"], "data_model_id": model["id"]}).json()
        assert roles == {"judge_model_id": model["id"], "data_model_id": model["id"]}

        test_result = client.post(f"/api/settings/model-models/{model['id']}/test").json()
        assert test_result["status"] == "ok"
        assert requests[-1]["path"] == "/v1/chat/completions"
        assert requests[-1]["headers"]["Authorization"] == "Bearer sk-test-secret-1234"

        artifact = tmp_path / "artifact"
        artifact.mkdir()
        (artifact / "SKILL.md").write_text("---\nname: sample-skill\ndescription: Sample.\n---\n", encoding="utf-8")
        result = run_effect_eval(
            runner={"runner_type": "opencode_cli", "command_path": str(fake_opencode(tmp_path)), "model_name": "model", "timeout_seconds": 5},
            artifact_root=str(artifact),
            skill_name="sample-skill",
            effect_cases=[{"id": "case-1", "case_key": "case-1", "prompt": "do task", "expected_output": "good output", "files": [], "assertions": []}],
            run_root=tmp_path / "run",
        )
        assertion = result["case_results"][0]["with_skill"]["assertion_results"][0]
        assert assertion["method"] == "llm_judge"
        assert assertion["passed"] is True
    finally:
        server.shutdown()


def test_openai_compatible_base_url_appends_chat_completions(monkeypatch):
    from app.model_client import call_configured_model
    import app.model_client as model_client

    captured = {}

    def fake_post_json(url, payload, headers, timeout_seconds):
        captured["url"] = url
        return {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }, ""

    monkeypatch.setattr(model_client, "post_json", fake_post_json)
    result = call_configured_model(
        {
            "id": "model_1",
            "enabled": 1,
            "provider_enabled": 1,
            "provider_type": "openai_compatible",
            "base_url": "https://example.test/openai",
            "api_key": "sk-test",
            "model_id": "custom-model",
        },
        "hello",
    )

    assert result.content == "ok"
    assert captured["url"] == "https://example.test/openai/chat/completions"


def test_model_provider_preserves_key_and_anthropic_test(client):
    server, requests = start_model_server(
        {
            "content": [{"type": "text", "text": json.dumps({"results": []})}],
            "usage": {"input_tokens": 3, "output_tokens": 2},
        }
    )
    try:
        provider = client.post(
            "/api/settings/model-providers",
            json={
                "name": "Anthropic Compatible",
                "provider_type": "anthropic",
                "base_url": f"http://127.0.0.1:{server.server_port}",
                "api_key": "anthropic-secret-9999",
            },
        ).json()
        updated = client.put(
            f"/api/settings/model-providers/{provider['id']}",
            json={
                "name": "Anthropic Compatible 2",
                "provider_type": "anthropic",
                "base_url": f"http://127.0.0.1:{server.server_port}/",
                "api_key": "",
                "enabled": True,
            },
        ).json()
        assert updated["api_key_preview"].endswith("9999")
        model = client.post(
            "/api/settings/model-models",
            json={"provider_id": provider["id"], "display_name": "Claude Test", "model_id": "claude-test"},
        ).json()
        response = client.post(f"/api/settings/model-models/{model['id']}/test")
        assert response.status_code == 200
        assert requests[-1]["path"] == "/v1/messages"
        headers = {key.lower(): value for key, value in requests[-1]["headers"].items()}
        assert headers["x-api-key"] == "anthropic-secret-9999"
    finally:
        server.shutdown()


def test_model_model_duplicate_disable_and_role_validation(client):
    provider = client.post(
        "/api/settings/model-providers",
        json={"name": "Local", "provider_type": "openai_compatible", "base_url": "http://127.0.0.1:9999", "api_key": "key"},
    ).json()
    model = client.post(
        "/api/settings/model-models",
        json={"provider_id": provider["id"], "display_name": "M1", "model_id": "model-1"},
    ).json()
    duplicate = client.post(
        "/api/settings/model-models",
        json={"provider_id": provider["id"], "display_name": "M1 copy", "model_id": "model-1"},
    )
    assert duplicate.status_code == 400

    invalid_role = client.put("/api/settings/model-roles", json={"judge_model_id": "missing", "data_model_id": None})
    assert invalid_role.status_code == 400

    disabled = client.delete(f"/api/settings/model-models/{model['id']}").json()
    assert disabled["status"] == "disabled"
    client.put("/api/settings/model-roles", json={"judge_model_id": model["id"], "data_model_id": model["id"]})
    roles = client.get("/api/settings/model-roles").json()
    assert roles["judge_model_id"] == model["id"]


def test_model_name_and_base_url_are_unique_across_connections(client):
    first = client.post(
        "/api/settings/model-providers",
        json={"name": "Connection A", "provider_type": "openai_compatible", "base_url": "https://api.example.test/v1", "api_key": "key-a"},
    ).json()
    second = client.post(
        "/api/settings/model-providers",
        json={"name": "Connection B", "provider_type": "openai_compatible", "base_url": "https://api.example.test/v1", "api_key": "key-b"},
    ).json()
    created = client.post(
        "/api/settings/model-models",
        json={"provider_id": first["id"], "display_name": "same-model", "model_id": "same-model"},
    )
    assert created.status_code == 200

    duplicate = client.post(
        "/api/settings/model-models",
        json={"provider_id": second["id"], "display_name": "same-model", "model_id": "same-model"},
    )

    assert duplicate.status_code == 400
    assert duplicate.json()["detail"] == "Model name and base_url already exist."


def test_disabled_runner_cannot_create_new_task(client):
    draft = importer.create_import_draft("sheet.zip", make_zip({"sheet/SKILL.md": "---\nname: sheet\n---"}))
    skill = importer.confirm_import_draft(draft["id"], "sheet", "1.0.0", "Data & Analytics")
    runner = client.get("/api/runners").json()[0]
    client.delete(f"/api/settings/runners/{runner['id']}")

    response = client.post(
        "/api/tasks",
        json={
            "skill_id": skill["id"],
            "skill_version_id": skill["latest_version"]["id"],
            "runner_environment_id": runner["id"],
        },
    )

    assert response.status_code == 400


def test_scoring_weights_validation_remains_legacy_compatible(client):
    invalid = client.put(
        "/api/settings/scoring-weights",
        json={"weights": [{"stage": "static_scan", "weight": 1.0}]},
    )
    assert invalid.status_code == 400

    invalid_sum = client.put(
        "/api/settings/scoring-weights",
        json={
            "weights": [
                {"stage": "static_scan", "weight": 0.25},
                {"stage": "trigger_eval", "weight": 0.25},
                {"stage": "effect_eval", "weight": 0.25},
                {"stage": "performance_eval", "weight": 0.30},
            ]
        },
    )
    assert invalid_sum.status_code == 400

    saved = client.put(
        "/api/settings/scoring-weights",
        json={
            "weights": [
                {"stage": "static_scan", "weight": 1.0},
                {"stage": "trigger_eval", "weight": 0.0},
                {"stage": "effect_eval", "weight": 0.0},
                {"stage": "performance_eval", "weight": 0.0},
            ]
        },
    )
    assert saved.status_code == 200

    draft = importer.create_import_draft(
        "score.zip",
        make_zip({"score/SKILL.md": "---\nname: score\ndescription: Score skill.\n---\nUse for score checks.\n"}),
    )
    skill = importer.confirm_import_draft(draft["id"], "score", "1.0.0", "Data & Analytics")
    runner = client.get("/api/runners").json()[0]
    eval_set = client.get(f"/api/skills/{skill['id']}/evaluation-set").json()
    client.post(
        f"/api/skills/{skill['id']}/evaluation-set/trigger-queries",
        json={"query": "please trigger score skill", "should_trigger": True},
    )
    task = client.post(
        "/api/tasks",
        json={
            "skill_id": skill["id"],
            "skill_version_id": skill["latest_version"]["id"],
            "runner_environment_id": runner["id"],
        },
    ).json()
    detail = client.post(f"/api/tasks/{task['id']}/run-now").json()

    assert eval_set["skill_id"] == skill["id"]
    assert detail["run"]["overall_score"] is None
    assert detail["run"]["result_summary"]["trigger_score"] == 100.0
