from __future__ import annotations

from pathlib import Path
from typing import Any

from . import opencode_runner


SUPPORTED_RUNNER_TYPES = {"opencode_cli"}


def require_opencode_runner(runner: dict[str, Any]) -> tuple[str, str, int]:
    runner_type = str(runner.get("runner_type") or "").strip()
    if runner_type not in SUPPORTED_RUNNER_TYPES:
        raise ValueError(f"Unsupported runner_type: {runner_type or 'missing'}.")
    command_path = str(runner.get("command_path") or "").strip()
    model_name = str(runner.get("model_name") or "").strip()
    if not command_path:
        raise ValueError("Runner command_path is required.")
    if not model_name:
        raise ValueError("Runner model_name is required.")
    timeout_seconds = int(runner.get("timeout_seconds") or 60)
    return command_path, model_name, timeout_seconds


def run_trigger_eval(
    *,
    runner: dict[str, Any],
    artifact_root: str,
    skill_name: str,
    trigger_queries: list[dict[str, Any]],
    run_root: Path,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    require_opencode_runner(runner)
    return opencode_runner.run_trigger_eval(
        runner=runner,
        artifact_root=artifact_root,
        skill_name=skill_name,
        trigger_queries=trigger_queries,
        run_root=run_root,
        workspace_root=workspace_root,
    )


def run_prompt(
    *,
    runner: dict[str, Any],
    prompt: str,
    workspace: Path,
    stdout_path: Path,
    stderr_path: Path,
    artifact_root: str | None = None,
    skill_name: str = "",
    load_skill: bool = False,
    skill_source_root: Path | None = None,
) -> dict[str, Any]:
    command_path, model_name, timeout_seconds = require_opencode_runner(runner)
    return opencode_runner.run_opencode_prompt(
        command_path=command_path,
        model_name=model_name,
        timeout_seconds=timeout_seconds,
        prompt=prompt,
        workspace=workspace,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        artifact_root=artifact_root,
        skill_name=skill_name,
        load_skill=load_skill,
        skill_source_root=skill_source_root,
    )
