import io
import zipfile
from typing import Union

import pytest
from fastapi.testclient import TestClient

from app import db
from app import importer
from app.db import init_db, seed_db
from app.main import app


def make_zip(files: dict[str, Union[str, bytes]]) -> bytes:
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
    import app.evaluator as evaluator

    monkeypatch.setattr(evaluator, "RUN_DIR", tmp_path / "runs")
    init_db(db.DB_PATH)
    seed_db(db.DB_PATH)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def import_sample_skill() -> dict:
    draft = importer.create_import_draft(
        "detail.zip",
        make_zip(
            {
                "detail/SKILL.md": "---\nname: detail\ndescription: Original description.\n---\nBody",
                "detail/scripts/run.py": "print('hello')\n",
                "detail/assets/logo.bin": b"\x00\x01\x02\x03",
            }
        ),
    )
    return importer.confirm_import_draft(draft["id"], "detail", "1.0.0", "Data & Analytics", "Detail Skill")


def test_update_skill_platform_card_fields(client):
    skill = import_sample_skill()

    response = client.put(
        f"/api/skills/{skill['id']}",
        json={
            "display_name": "Updated Detail Skill",
            "description": "Edited platform description.",
            "category": "Security & Compliance",
            "card_content": "<h2>Updated card</h2><p>Rich content.</p>",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["display_name"] == "Updated Detail Skill"
    assert payload["description"] == "Edited platform description."
    assert payload["card_content"] == "<h2>Updated card</h2><p>Rich content.</p>"
    assert payload["category"] == "Security & Compliance"


def test_update_skill_rejects_empty_display_name_and_unknown_category(client):
    skill = import_sample_skill()

    empty_name = client.put(
        f"/api/skills/{skill['id']}",
        json={"display_name": " ", "description": "", "category": "Data & Analytics"},
    )
    assert empty_name.status_code == 400

    unknown_category = client.put(
        f"/api/skills/{skill['id']}",
        json={"display_name": "Detail Skill", "description": "", "category": "Missing"},
    )
    assert unknown_category.status_code == 400


def test_skill_files_list_and_text_content(client):
    skill = import_sample_skill()

    listing = client.get(f"/api/skills/{skill['id']}/files")

    assert listing.status_code == 200
    paths = [item["path"] for item in listing.json()["files"]]
    assert "SKILL.md" in paths
    assert "scripts/run.py" in paths
    assert "assets/logo.bin" in paths

    content = client.get(f"/api/skills/{skill['id']}/files/content", params={"path": "scripts/run.py"})

    assert content.status_code == 200
    payload = content.json()
    assert payload["is_text"] is True
    assert payload["content"] == "print('hello')\n"
    assert payload["truncated"] is False


def test_skill_files_binary_and_path_escape_are_safe(client):
    skill = import_sample_skill()

    binary = client.get(f"/api/skills/{skill['id']}/files/content", params={"path": "assets/logo.bin"})

    assert binary.status_code == 200
    assert binary.json()["is_text"] is False
    assert binary.json()["content"] == ""

    escaped = client.get(f"/api/skills/{skill['id']}/files/content", params={"path": "../skilleval.db"})
    assert escaped.status_code == 400
