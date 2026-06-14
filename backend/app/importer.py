from __future__ import annotations

import re
import shutil
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from .config import IMPORT_DIR, UPLOAD_DIR
from .db import connect, encode_json, now_iso, row_to_dict


SKILL_MD = "SKILL.md"


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def normalize_skill_name(value: str) -> str:
    base = value.strip().lower()
    base = re.sub(r"[^a-z0-9._-]+", "-", base)
    base = re.sub(r"-{2,}", "-", base).strip("-._")
    return base or "untitled-skill"


def zip_base_name(filename: str) -> str:
    name = Path(filename).name
    return re.sub(r"\.zip$", "", name, flags=re.IGNORECASE)


def parse_frontmatter(markdown: str) -> dict[str, str]:
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    frontmatter: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        clean = value.strip().strip("\"'")
        frontmatter[key.strip()] = clean
    return frontmatter


def skill_md_candidates(names: list[str]) -> list[str]:
    candidates: list[str] = []
    for name in names:
        if name.endswith("/"):
            continue
        normalized = str(PurePosixPath(name))
        parts = PurePosixPath(normalized).parts
        if not parts or parts[-1] != SKILL_MD:
            continue
        allowed = False
        if len(parts) == 1:
            allowed = True
        elif len(parts) == 2:
            allowed = True
        elif len(parts) == 4 and parts[0] in {".codex", ".claude"} and parts[1] == "skills":
            allowed = True
        if allowed:
            candidates.append(normalized)
    return sorted(candidates)


def containing_dir(skill_md_path: str) -> str:
    parent = str(PurePosixPath(skill_md_path).parent)
    return "" if parent == "." else parent


def fallback_name_from_path(skill_md_path: str, filename: str) -> str:
    parent = containing_dir(skill_md_path)
    if parent:
        return PurePosixPath(parent).name
    return zip_base_name(filename)


def read_skill_root(zip_file: zipfile.ZipFile, skill_md_path: str, filename: str) -> dict[str, Any]:
    content = zip_file.read(skill_md_path).decode("utf-8", errors="replace")
    frontmatter = parse_frontmatter(content)
    root_path = containing_dir(skill_md_path)
    raw_name = frontmatter.get("name") or fallback_name_from_path(skill_md_path, filename)
    return {
        "root_path": root_path,
        "skill_md_path": skill_md_path,
        "frontmatter": frontmatter,
        "suggested_skill_name": normalize_skill_name(raw_name),
        "suggested_display_name": frontmatter.get("name") or raw_name,
        "suggested_version": frontmatter.get("version") or frontmatter.get("metadata.version"),
    }


def create_import_draft(source_name: str, payload: bytes) -> dict[str, Any]:
    draft_id = new_id("import")
    draft_dir = IMPORT_DIR / draft_id
    draft_dir.mkdir(parents=True, exist_ok=True)
    source_path = draft_dir / "source.zip"
    source_path.write_bytes(payload)

    status = "parsed"
    roots: list[dict[str, Any]] = []
    selected_root_path: str | None = None
    suggested_skill_name = ""
    suggested_display_name = ""
    suggested_version = None
    blocking_errors: list[dict[str, Any]] = []
    warnings: list[str] = []

    try:
        with zipfile.ZipFile(source_path) as zip_file:
            candidates = skill_md_candidates(zip_file.namelist())
            if not candidates:
                status = "failed"
                blocking_errors.append({"code": "SKILL_MD_NOT_FOUND", "message": "ZIP 包内未找到 SKILL.md。"})
            elif len(candidates) > 1:
                status = "failed"
                blocking_errors.append({"code": "MULTIPLE_SKILL_MD", "message": "ZIP 包内存在多个 SKILL.md，MVP 只接受单 Skill 包。", "paths": candidates})
            else:
                roots = [read_skill_root(zip_file, candidates[0], source_name)]
                selected_root_path = roots[0]["root_path"]
                suggested_skill_name = roots[0]["suggested_skill_name"]
                suggested_display_name = roots[0]["suggested_display_name"]
                suggested_version = roots[0]["suggested_version"]
                if not suggested_version:
                    warnings.append("未从 SKILL.md 中解析到 version，需要用户填写。")
    except zipfile.BadZipFile:
        status = "failed"
        blocking_errors.append({"code": "ZIP_PARSE_FAILED", "message": "文件不是有效 ZIP 包。"})

    created = now_iso()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO skill_import_drafts
              (id, source_type, source_name, source_path, status, detected_roots, selected_root_path,
               suggested_skill_name, suggested_display_name, suggested_version, warnings, blocking_errors, created_at)
            VALUES (?, 'zip', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                draft_id,
                source_name,
                str(source_path),
                status,
                encode_json(roots),
                selected_root_path,
                suggested_skill_name,
                suggested_display_name,
                suggested_version,
                encode_json(warnings),
                encode_json(blocking_errors),
                created,
            ),
        )
        row = conn.execute("SELECT * FROM skill_import_drafts WHERE id = ?", (draft_id,)).fetchone()
        return row_to_dict(row)


def get_import_draft(draft_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM skill_import_drafts WHERE id = ?", (draft_id,)).fetchone()
        return row_to_dict(row)


def safe_extract_root(zip_path: Path, selected_root: str | None, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    root_prefix = f"{selected_root.rstrip('/')}/" if selected_root else ""
    with zipfile.ZipFile(zip_path) as zip_file:
        for info in zip_file.infolist():
            if info.is_dir():
                continue
            name = str(PurePosixPath(info.filename))
            if root_prefix and not name.startswith(root_prefix):
                continue
            relative = name[len(root_prefix):] if root_prefix else name
            if not relative or relative.startswith("../") or "/../" in relative:
                continue
            destination = target_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with zip_file.open(info) as source, destination.open("wb") as output:
                shutil.copyfileobj(source, output)


def confirm_import_draft(draft_id: str, skill_name: str, version: str, category: str, display_name: str | None = None) -> dict[str, Any]:
    draft = get_import_draft(draft_id)
    if not draft:
        raise ValueError("Import draft not found.")
    if draft["status"] == "failed":
        raise ValueError("Import draft has blocking errors and cannot be confirmed.")
    normalized_name = normalize_skill_name(skill_name)
    clean_version = version.strip()
    clean_category = category.strip()
    if not clean_version:
        raise ValueError("version is required.")
    if not clean_category:
        raise ValueError("category is required.")

    created = now_iso()
    skill_id = new_id("skill")
    version_id = new_id("skillver")
    eval_set_id = new_id("evalset")
    artifact_root = UPLOAD_DIR / normalized_name / clean_version
    source_path = Path(draft["source_path"])
    detected_roots = draft.get("detected_roots") or []
    frontmatter = detected_roots[0].get("frontmatter", {}) if detected_roots else {}
    description = frontmatter.get("description", "")
    manifest = {
        "name": normalized_name,
        "display_name": display_name or draft.get("suggested_display_name") or normalized_name,
        "description": description,
        "frontmatter": frontmatter,
        "skill_md_path": f"{normalized_name}/SKILL.md",
        "source_skill_md_path": detected_roots[0].get("skill_md_path") if detected_roots else None,
    }

    with connect() as conn:
        existing_skill = conn.execute("SELECT * FROM skills WHERE skill_name = ?", (normalized_name,)).fetchone()
        if existing_skill:
            skill_id = existing_skill["id"]
            duplicate = conn.execute(
                "SELECT id FROM skill_versions WHERE skill_id = ? AND version = ?",
                (skill_id, clean_version),
            ).fetchone()
            if duplicate:
                raise ValueError("该 skill_name + version 已存在。")
        else:
            conn.execute(
                """
                INSERT INTO skills
                  (id, skill_name, display_name, description, category, status, latest_version_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'imported', ?, ?, ?)
                """,
                (skill_id, normalized_name, display_name or manifest["display_name"], description, clean_category, version_id, created, created),
            )
            conn.execute(
                """
                INSERT INTO evaluation_sets (id, skill_id, name, description, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'draft', ?, ?)
                """,
                (eval_set_id, skill_id, f"{normalized_name} current set", "Current skill-bound evaluation set.", created, created),
            )

        safe_extract_root(source_path, draft.get("selected_root_path"), artifact_root)
        conn.execute(
            """
            INSERT INTO skill_versions
              (id, skill_id, version, manifest, artifact_root, static_scan_status, source_name, created_at)
            VALUES (?, ?, ?, ?, ?, 'not_scanned', ?, ?)
            """,
            (version_id, skill_id, clean_version, encode_json(manifest), str(artifact_root), draft["source_name"], created),
        )
        conn.execute(
            """
            UPDATE skills
            SET display_name = ?, description = COALESCE(NULLIF(?, ''), description), category = ?, latest_version_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (display_name or manifest["display_name"], description, clean_category, version_id, created, skill_id),
        )
        conn.execute("UPDATE skill_import_drafts SET status = 'confirmed' WHERE id = ?", (draft_id,))
        row = conn.execute("SELECT * FROM skills WHERE id = ?", (skill_id,)).fetchone()
        skill = row_to_dict(row)
        version_row = conn.execute("SELECT * FROM skill_versions WHERE id = ?", (version_id,)).fetchone()
        skill["latest_version"] = row_to_dict(version_row)
        return skill
