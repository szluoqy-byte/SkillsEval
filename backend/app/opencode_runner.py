from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


def text_payload(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def copy_skill_to_workspace(artifact_root: Path, workspace: Path, skill_name: str) -> Path:
    skill_dir = workspace / ".opencode" / "skills" / skill_name
    skill_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(artifact_root, skill_dir, dirs_exist_ok=True)
    return skill_dir


def event_tool_name(event: dict[str, Any]) -> str:
    part = event.get("part") if isinstance(event.get("part"), dict) else {}
    return str(event.get("name") or event.get("tool_name") or event.get("tool") or part.get("tool") or "")


def parse_jsonl_events(stdout: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def extract_text_from_event(event: dict[str, Any]) -> str:
    candidates: list[Any] = [event]
    for key in ("message", "event", "content_block", "delta", "part"):
        value = event.get(key)
        if isinstance(value, dict):
            candidates.append(value)
        elif isinstance(value, list):
            candidates.extend(item for item in value if isinstance(item, dict))
    content = event.get("message", {}).get("content") if isinstance(event.get("message"), dict) else None
    if isinstance(content, list):
        candidates.extend(item for item in content if isinstance(item, dict))
    texts: list[str] = []
    for item in candidates:
        text = item.get("text") or item.get("content") or item.get("output")
        if isinstance(text, str):
            texts.append(text)
    return "\n".join(texts)


def extract_token_counts(value: Any) -> dict[str, int]:
    counts = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    if not isinstance(value, dict):
        return counts
    for key in ("input_tokens", "input", "prompt_tokens"):
        if isinstance(value.get(key), int):
            counts["input_tokens"] += int(value[key])
    for key in ("output_tokens", "output", "completion_tokens"):
        if isinstance(value.get(key), int):
            counts["output_tokens"] += int(value[key])
    for key in ("total_tokens", "total"):
        if isinstance(value.get(key), int):
            counts["total_tokens"] += int(value[key])
    if counts["total_tokens"] == 0:
        counts["total_tokens"] = counts["input_tokens"] + counts["output_tokens"]
    return counts


def parse_run_output(stdout: str, skill_name: str = "") -> dict[str, Any]:
    events = parse_jsonl_events(stdout)
    response_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    cost = 0.0
    skill_invoked = False
    errors = 0

    for event in events:
        text = extract_text_from_event(event)
        if text:
            response_parts.append(text)
        tool_name = event_tool_name(event)
        if tool_name:
            tool_calls.append({"name": tool_name, "event_type": event.get("type", "")})
        if skill_name and event_invokes_skill(event, skill_name):
            skill_invoked = True
        event_type = str(event.get("type", "")).lower()
        if "error" in event_type or event.get("error"):
            errors += 1
        for key in ("tokens", "token_counts", "usage"):
            token_counts = extract_token_counts(event.get(key))
            tokens["input_tokens"] += token_counts["input_tokens"]
            tokens["output_tokens"] += token_counts["output_tokens"]
            tokens["total_tokens"] += token_counts["total_tokens"]
        part = event.get("part") if isinstance(event.get("part"), dict) else {}
        token_counts = extract_token_counts(part.get("tokens"))
        tokens["input_tokens"] += token_counts["input_tokens"]
        tokens["output_tokens"] += token_counts["output_tokens"]
        tokens["total_tokens"] += token_counts["total_tokens"]
        for key in ("cost", "cost_usd", "total_cost"):
            if isinstance(event.get(key), (int, float)):
                cost += float(event[key])

    return {
        "response": "\n".join(dict.fromkeys(part.strip() for part in response_parts if part.strip())),
        "tool_calls": tool_calls,
        "tool_call_count": len(tool_calls),
        "skill_invoked": skill_invoked,
        "errors_encountered": errors,
        "estimated_cost": round(cost, 6),
        **tokens,
    }


def event_invokes_skill(event: dict[str, Any], skill_name: str) -> bool:
    skill_path_markers = (
        f"/.opencode/skills/{skill_name}/SKILL.md",
        f"\\.opencode/skills/{skill_name}/SKILL.md",
    )
    candidates: list[Any] = [event]
    for key in ("message", "event", "content_block", "delta", "part"):
        value = event.get(key)
        if isinstance(value, dict):
            candidates.append(value)
            state = value.get("state")
            if isinstance(state, dict):
                candidates.append(state)
    content = event.get("message", {}).get("content") if isinstance(event.get("message"), dict) else None
    if isinstance(content, list):
        candidates.extend(item for item in content if isinstance(item, dict))

    for item in candidates:
        name = item.get("name") or item.get("tool_name")
        name = name or item.get("tool")
        input_payload = item.get("input") or item.get("tool_input") or item.get("arguments") or {}
        if not input_payload and isinstance(item.get("state"), dict):
            input_payload = item["state"].get("input") or {}
        if isinstance(input_payload, str):
            try:
                input_payload = json.loads(input_payload)
            except json.JSONDecodeError:
                input_payload = {"raw": input_payload}
        if name == "skill" and isinstance(input_payload, dict) and input_payload.get("name") == skill_name:
            return True
        if name in {"Skill", "skill"} and isinstance(input_payload, dict):
            if input_payload.get("skill") == skill_name or input_payload.get("name") == skill_name:
                return True
        if isinstance(input_payload, dict):
            for key in ("filePath", "path"):
                value = input_payload.get(key)
                if isinstance(value, str) and any(marker in value for marker in skill_path_markers):
                    return True
        if isinstance(item.get("skill"), str) and item["skill"] == skill_name:
            return True
    return False


def parse_triggered(stdout: str, skill_name: str) -> bool:
    for event in parse_jsonl_events(stdout):
        if event_invokes_skill(event, skill_name):
            return True
    return False


def run_opencode_prompt(
    *,
    command_path: str,
    model_name: str,
    timeout_seconds: int,
    prompt: str,
    workspace: Path,
    stdout_path: Path,
    stderr_path: Path,
    artifact_root: str | None = None,
    skill_name: str = "",
    load_skill: bool = False,
) -> dict[str, Any]:
    started = time.monotonic()
    command = Path(command_path)
    result: dict[str, Any] = {
        "prompt": prompt,
        "response": "",
        "duration_ms": 0,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "returncode": None,
        "error": "",
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "tool_calls": [],
        "tool_call_count": 0,
        "skill_invoked": False,
        "errors_encountered": 0,
        "estimated_cost": 0.0,
    }
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)

    if not command.exists():
        result["error"] = f"OpenCode command not found: {command_path}"
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text(result["error"], encoding="utf-8")
        return result

    try:
        if load_skill and artifact_root and skill_name:
            copy_skill_to_workspace(Path(artifact_root), workspace, skill_name)
        completed = subprocess.run(
            [
                str(command),
                "run",
                "--format",
                "json",
                "-m",
                model_name,
                "--dir",
                str(workspace),
                prompt,
            ],
            cwd=workspace,
            text=True,
            capture_output=True,
            timeout=max(1, int(timeout_seconds)),
            check=False,
        )
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        parsed = parse_run_output(completed.stdout, skill_name)
        result.update(parsed)
        result["returncode"] = completed.returncode
        if completed.returncode != 0:
            result["error"] = f"OpenCode exited with code {completed.returncode}."
    except subprocess.TimeoutExpired as error:
        stdout_text = text_payload(error.stdout)
        stderr_text = text_payload(error.stderr) or f"OpenCode timed out after {timeout_seconds}s."
        stdout_path.write_text(stdout_text, encoding="utf-8")
        stderr_path.write_text(stderr_text, encoding="utf-8")
        result.update(parse_run_output(stdout_text, skill_name))
        result["error"] = f"OpenCode timed out after {timeout_seconds}s."
    finally:
        result["duration_ms"] = int((time.monotonic() - started) * 1000)
    return result


def run_trigger_query(
    *,
    command_path: str,
    model_name: str,
    timeout_seconds: int,
    artifact_root: str,
    skill_name: str,
    query: str,
    should_trigger: bool,
    workspace: Path,
    stdout_path: Path,
    stderr_path: Path,
) -> dict[str, Any]:
    started = time.monotonic()
    command = Path(command_path)
    result: dict[str, Any] = {
        "query": query,
        "should_trigger": should_trigger,
        "triggered": False,
        "pass": False,
        "duration_ms": 0,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "error": "",
    }
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)

    if not command.exists():
        result["error"] = f"OpenCode command not found: {command_path}"
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text(result["error"], encoding="utf-8")
        return result

    try:
        copy_skill_to_workspace(Path(artifact_root), workspace, skill_name)
        completed = subprocess.run(
            [
                str(command),
                "run",
                "--format",
                "json",
                "-m",
                model_name,
                "--dir",
                str(workspace),
                query,
            ],
            cwd=workspace,
            text=True,
            capture_output=True,
            timeout=max(1, int(timeout_seconds)),
            check=False,
        )
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        triggered = parse_triggered(completed.stdout, skill_name)
        result["triggered"] = triggered
        result["pass"] = triggered if should_trigger else not triggered
        if completed.returncode != 0:
            result["pass"] = False
            result["error"] = f"OpenCode exited with code {completed.returncode}."
    except subprocess.TimeoutExpired as error:
        stdout_path.write_text(text_payload(error.stdout), encoding="utf-8")
        stderr_path.write_text(text_payload(error.stderr) or f"OpenCode timed out after {timeout_seconds}s.", encoding="utf-8")
        result["error"] = f"OpenCode timed out after {timeout_seconds}s."
    finally:
        result["duration_ms"] = int((time.monotonic() - started) * 1000)
    return result


def run_trigger_eval(
    *,
    runner: dict[str, Any],
    artifact_root: str,
    skill_name: str,
    trigger_queries: list[dict[str, Any]],
    run_root: Path,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    trigger_root = run_root / "trigger"
    workspace_base = workspace_root or trigger_root / "workspaces"
    results: list[dict[str, Any]] = []
    command_path = str(runner.get("command_path") or "").strip()
    model_name = str(runner.get("model_name") or "").strip()
    if not command_path:
        raise ValueError("Runner command_path is required.")
    if not model_name:
        raise ValueError("Runner model_name is required.")
    timeout_seconds = int(runner.get("timeout_seconds") or 60)

    for index, item in enumerate(trigger_queries, start=1):
        query_id = item.get("id") or f"query-{index}"
        result = run_trigger_query(
            command_path=command_path,
            model_name=model_name,
            timeout_seconds=timeout_seconds,
            artifact_root=artifact_root,
            skill_name=skill_name,
            query=item["query"],
            should_trigger=bool(item["should_trigger"]),
            workspace=workspace_base / str(query_id),
            stdout_path=trigger_root / "logs" / f"{query_id}.stdout.jsonl",
            stderr_path=trigger_root / "logs" / f"{query_id}.stderr.log",
        )
        result["query_id"] = query_id
        results.append(result)

    total = len(results)
    matched = sum(1 for item in results if item["pass"])
    score = round((matched / total) * 100, 1) if total else 0.0
    return {
        "score": score,
        "summary": f"Trigger eval completed: {matched}/{total} queries matched expectations." if total else "Trigger eval has no queries; score is 0.",
        "metrics": {
            "score": score,
            "total_queries": total,
            "matched_queries": matched,
            "mismatched_queries": total - matched,
            "passed_queries": matched,
            "failed_queries": total - matched,
            "runner_type": runner.get("runner_type"),
            "model_name": model_name,
            "command_path": command_path,
            "timeout_seconds": timeout_seconds,
            "simulated": False,
        },
        "results": results,
    }
