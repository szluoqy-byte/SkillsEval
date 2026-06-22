from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from .model_client import call_configured_model, get_role_model
from .runner_adapter import run_prompt
from .opencode_runner import prepare_skill_cache


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def assertion_result(text: str, passed: bool, evidence: str, method: str = "deterministic", confidence: float = 1.0, uncertain: bool = False) -> dict[str, Any]:
    return {
        "text": text,
        "passed": passed,
        "evidence": evidence,
        "method": method,
        "confidence": confidence,
        "uncertain": uncertain,
    }


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def json_path_lookup(payload: Any, path: str) -> tuple[bool, Any]:
    if not path.startswith("$."):
        return False, None
    current = payload
    for part in path[2:].split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return False, None
    return True, current


DETERMINISTIC_ASSERTION_PREFIXES = (
    "contains ",
    "does not contain ",
    "starts with ",
    "ends with ",
    "matches regex ",
    "matches pattern ",
    "has at least ",
    "is valid json",
    "output is valid json",
    "json path ",
    "file exists ",
    "file contains ",
    "tool called ",
    "skill invoked ",
)


def looks_deterministic_assertion(text: str) -> bool:
    clean = text.strip().lower()
    return any(clean.startswith(prefix) for prefix in DETERMINISTIC_ASSERTION_PREFIXES)


def deterministic_grade(assertion: str, output: str, workspace: Path, tool_calls: list[dict[str, Any]], skill_name: str, skill_invoked: bool) -> dict[str, Any] | None:
    raw = assertion.strip()
    lower = raw.lower()

    or_parts = re.split(r"\s+or\s+", raw, flags=re.IGNORECASE)
    if len(or_parts) >= 2 and all(looks_deterministic_assertion(part) for part in or_parts):
        branch_results: list[dict[str, Any]] = []
        for part in or_parts:
            result = deterministic_grade(part.strip(), output, workspace, tool_calls, skill_name, skill_invoked)
            if result is None:
                continue
            branch_results.append(result)
            if result["passed"]:
                return assertion_result(raw, True, f"OR satisfied by: {part.strip()} - {result['evidence']}")
        if branch_results:
            evidence = "; ".join(f"{part.strip()}: {result['evidence']}" for part, result in zip(or_parts, branch_results))
            return assertion_result(raw, False, f"No OR branch satisfied - {evidence}")

    contains = re.match(r"^contains\s+(.+)$", raw, re.IGNORECASE)
    if contains:
        needle = strip_quotes(contains.group(1))
        found = needle.lower() in output.lower()
        return assertion_result(raw, found, f"Substring {'found' if found else 'not found'}: {needle!r}")

    not_contains = re.match(r"^does not contain\s+(.+)$", raw, re.IGNORECASE)
    if not_contains:
        needle = strip_quotes(not_contains.group(1))
        found = needle.lower() in output.lower()
        return assertion_result(raw, not found, f"Substring {'found (FAIL)' if found else 'not found (OK)'}: {needle!r}")

    starts = re.match(r"^starts with\s+(.+)$", raw, re.IGNORECASE)
    if starts:
        prefix = strip_quotes(starts.group(1))
        passed = output.lstrip().lower().startswith(prefix.lower())
        return assertion_result(raw, passed, f"Output {'starts' if passed else 'does not start'} with {prefix!r}.")

    ends = re.match(r"^ends with\s+(.+)$", raw, re.IGNORECASE)
    if ends:
        suffix = strip_quotes(ends.group(1))
        passed = output.rstrip().lower().endswith(suffix.lower())
        return assertion_result(raw, passed, f"Output {'ends' if passed else 'does not end'} with {suffix!r}.")

    regex = re.match(r"^matches\s+(?:regex|pattern)\s+/(.+)/$", raw, re.IGNORECASE)
    if regex:
        pattern = regex.group(1)
        try:
            matched = re.search(pattern, output) is not None
        except re.error as error:
            return assertion_result(raw, False, f"Invalid regex: {error}")
        return assertion_result(raw, matched, f"Regex /{pattern}/ {'matched' if matched else 'did not match'}.")

    if lower in {"is valid json", "output is valid json"}:
        try:
            json.loads(output)
        except json.JSONDecodeError as error:
            return assertion_result(raw, False, f"JSON parse error: {error}")
        return assertion_result(raw, True, "Output parsed as valid JSON.")

    lines = re.match(r"^has at least\s+(\d+)\s+lines?$", raw, re.IGNORECASE)
    if lines:
        threshold = int(lines.group(1))
        count = len(output.splitlines())
        return assertion_result(raw, count >= threshold, f"Line count: {count} (threshold: {threshold}).")

    json_path = re.match(r"^json path\s+(\$\.[^\s]+)\s+equals\s+(.+)$", raw, re.IGNORECASE)
    if json_path:
        try:
            payload = json.loads(output)
        except json.JSONDecodeError as error:
            return assertion_result(raw, False, f"Output is not valid JSON: {error}")
        found, actual = json_path_lookup(payload, json_path.group(1))
        expected = strip_quotes(json_path.group(2))
        passed = found and str(actual) == expected
        return assertion_result(raw, passed, f"JSON path {'found' if found else 'missing'}; actual={actual!r}, expected={expected!r}.")

    file_exists = re.match(r"^file exists\s+(.+)$", raw, re.IGNORECASE)
    if file_exists:
        rel = Path(strip_quotes(file_exists.group(1)))
        target = (workspace / rel).resolve()
        try:
            target.relative_to(workspace.resolve())
        except ValueError:
            return assertion_result(raw, False, "File path escapes workspace.")
        return assertion_result(raw, target.is_file(), f"File {'exists' if target.is_file() else 'does not exist'}: {rel.as_posix()}.")

    file_contains = re.match(r"^file contains\s+([^\s]+)\s+(.+)$", raw, re.IGNORECASE)
    if file_contains:
        rel = Path(strip_quotes(file_contains.group(1)))
        needle = strip_quotes(file_contains.group(2))
        target = (workspace / rel).resolve()
        try:
            target.relative_to(workspace.resolve())
        except ValueError:
            return assertion_result(raw, False, "File path escapes workspace.")
        if not target.is_file():
            return assertion_result(raw, False, f"File does not exist: {rel.as_posix()}.")
        content = target.read_text(encoding="utf-8", errors="replace")
        found = needle.lower() in content.lower()
        return assertion_result(raw, found, f"Substring {'found' if found else 'not found'} in {rel.as_posix()}: {needle!r}.")

    tool_called = re.match(r"^tool called\s+(.+)$", raw, re.IGNORECASE)
    if tool_called:
        expected = strip_quotes(tool_called.group(1)).lower()
        names = [str(item.get("name", "")).lower() for item in tool_calls]
        return assertion_result(raw, expected in names, f"Observed tools: {', '.join(names) or 'none'}.")

    skill = re.match(r"^skill invoked\s+(.+)$", raw, re.IGNORECASE)
    if skill:
        expected = strip_quotes(skill.group(1))
        passed = skill_invoked and expected == skill_name
        return assertion_result(raw, passed, f"Skill invocation for {skill_name!r} was {'observed' if skill_invoked else 'not observed'}.")

    if raw.startswith("judge:"):
        return None
    return None


def extract_json_object(text: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def judge_assertions(
    *,
    runner: dict[str, Any],
    assertions: list[str],
    prompt: str,
    expected_output: str,
    output: str,
    stdout_summary: str,
    stderr_summary: str,
    workspace: Path,
    stdout_path: Path,
    stderr_path: Path,
) -> list[dict[str, Any]]:
    if not assertions:
        return []
    assertion_lines = "\n".join(f"{index + 1}. {item.removeprefix('judge:').strip()}" for index, item in enumerate(assertions))
    judge_prompt = f"""You are an evaluation judge. Determine whether each assertion is satisfied by the actual output.

Return only valid JSON in this shape:
{{"results":[{{"text":"assertion text","passed":true,"evidence":"specific evidence","confidence":0.0,"uncertain":false}}]}}

Task prompt:
{prompt}

Expected output description:
{expected_output or "(none)"}

Assertions:
{assertion_lines}

Actual output:
{output[:12000]}

Stdout summary:
{stdout_summary[:3000]}

Stderr summary:
{stderr_summary[:3000]}
"""
    model = get_role_model("judge")
    if not model:
        message = "LLM judge model is not configured in system settings."
        write_text(stderr_path, message)
        return [
            assertion_result(item, False, message, method="llm_judge", confidence=0.0, uncertain=True)
            for item in assertions
        ]
    result = call_configured_model(model, judge_prompt, timeout_seconds=int(runner.get("timeout_seconds") or 60))
    write_text(stdout_path, result.content or "")
    write_json(
        stdout_path.with_name("usage.json"),
        {
            "model_api_model_id": model.get("id"),
            "provider_id": model.get("provider_id"),
            "provider_type": model.get("provider_type"),
            "model_id": model.get("model_id"),
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "total_tokens": result.total_tokens,
            "raw_usage": result.raw_usage or {},
        },
    )
    if result.error:
        write_text(stderr_path, result.error)
        return [
            assertion_result(item, False, f"LLM judge unavailable: {result.error}", method="llm_judge", confidence=0.0, uncertain=True)
            for item in assertions
        ]
    write_text(stderr_path, "")
    payload = extract_json_object(result.content)
    if not payload or not isinstance(payload.get("results"), list):
        return [
            assertion_result(item, False, "LLM judge did not return valid JSON.", method="llm_judge", confidence=0.0, uncertain=True)
            for item in assertions
        ]
    by_text: list[dict[str, Any]] = []
    for index, item in enumerate(assertions):
        judged = payload["results"][index] if index < len(payload["results"]) and isinstance(payload["results"][index], dict) else {}
        by_text.append(
            assertion_result(
                item,
                bool(judged.get("passed")),
                str(judged.get("evidence") or "No evidence returned."),
                method="llm_judge",
                confidence=float(judged.get("confidence") or 0.0),
                uncertain=bool(judged.get("uncertain")),
            )
        )
    return by_text


def grade_run(
    *,
    runner: dict[str, Any],
    assertions: list[str],
    prompt: str,
    expected_output: str,
    output: str,
    workspace: Path,
    tool_calls: list[dict[str, Any]],
    skill_name: str,
    skill_invoked: bool,
    stdout_path: Path,
    stderr_path: Path,
    judge_root: Path,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    deferred: list[str] = []
    effective_assertions = assertions[:]
    if not effective_assertions and expected_output.strip():
        effective_assertions = [f"judge: output satisfies expected output: {expected_output.strip()}"]

    for item in effective_assertions:
        result = deterministic_grade(item, output, workspace, tool_calls, skill_name, skill_invoked)
        if result is None:
            deferred.append(item)
        else:
            results.append(result)
    if deferred:
        results.extend(
            judge_assertions(
                runner=runner,
                assertions=deferred,
                prompt=prompt,
                expected_output=expected_output,
                output=output,
                stdout_summary=stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.exists() else "",
                stderr_summary=stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.exists() else "",
                workspace=judge_root / "workspace",
                stdout_path=judge_root / "judge.stdout.jsonl",
                stderr_path=judge_root / "judge.stderr.log",
            )
        )

    total = len(results)
    passed = sum(1 for item in results if item["passed"])
    pass_rate = round(passed / total, 4) if total else 0.0
    return {
        "assertion_results": results,
        "pass_rate": pass_rate,
        "summary": {
            "passed": passed,
            "failed": total - passed,
            "total": total,
            "pass_rate": pass_rate,
        },
        "needs_expectations": not effective_assertions,
        "deterministic_assertions": sum(1 for item in results if item["method"] == "deterministic"),
        "judge_assertions": sum(1 for item in results if item["method"] == "llm_judge"),
        "uncertain_assertions": sum(1 for item in results if item["uncertain"]),
    }


def copy_case_files(files: list[str], artifact_root: Path, workspace: Path) -> list[dict[str, str]]:
    copied: list[dict[str, str]] = []
    root = artifact_root.resolve()
    for item in files:
        rel = Path(item)
        src = (root / rel).resolve()
        try:
            src.relative_to(root)
        except ValueError:
            copied.append({"path": item, "status": "blocked", "message": "Path escapes artifact root."})
            continue
        if not src.is_file():
            copied.append({"path": item, "status": "missing", "message": "File does not exist."})
            continue
        dst = workspace / rel.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append({"path": item, "status": "copied", "message": str(dst)})
    return copied


def run_effect_case_configuration(
    *,
    runner: dict[str, Any],
    case: dict[str, Any],
    configuration: str,
    artifact_root: str,
    skill_name: str,
    case_root: Path,
    workspace_root: Path,
    skill_source_root: Path | None = None,
) -> dict[str, Any]:
    run_root = case_root / configuration
    workspace = workspace_root / configuration / "workspace"
    files = copy_case_files(case.get("files") or [], Path(artifact_root), workspace)
    run = run_prompt(
        runner=runner,
        prompt=case["prompt"],
        workspace=workspace,
        stdout_path=run_root / "stdout.jsonl",
        stderr_path=run_root / "stderr.log",
        artifact_root=artifact_root,
        skill_name=skill_name,
        load_skill=configuration == "with_skill",
        skill_source_root=skill_source_root if configuration == "with_skill" else None,
    )
    write_text(run_root / "response.txt", run.get("response") or "")
    metrics = {
        "duration_ms": run["duration_ms"],
        "input_tokens": run.get("input_tokens", 0),
        "output_tokens": run.get("output_tokens", 0),
        "total_tokens": run.get("total_tokens", 0),
        "tool_calls": run.get("tool_call_count", 0),
        "errors_encountered": run.get("errors_encountered", 0) + (1 if run.get("error") else 0),
        "estimated_cost": run.get("estimated_cost", 0.0),
        "files": files,
    }
    grading = grade_run(
        runner=runner,
        assertions=case.get("assertions") or [],
        prompt=case["prompt"],
        expected_output=case.get("expected_output") or "",
        output=run.get("response") or "",
        workspace=workspace,
        tool_calls=run.get("tool_calls") or [],
        skill_name=skill_name,
        skill_invoked=bool(run.get("skill_invoked")),
        stdout_path=run_root / "stdout.jsonl",
        stderr_path=run_root / "stderr.log",
        judge_root=run_root / "judge",
    )
    payload = {
        "configuration": configuration,
        "raw_output": run.get("response") or "",
        "error": run.get("error") or "",
        "stdout_path": str(run_root / "stdout.jsonl"),
        "stderr_path": str(run_root / "stderr.log"),
        "response_path": str(run_root / "response.txt"),
        "metrics": metrics,
        **grading,
    }
    write_json(run_root / "metrics.json", metrics)
    write_json(run_root / "grading.json", payload)
    return payload


def classify_cost_efficiency(quality_delta: float, cost_delta_pct: float) -> str:
    if quality_delta > 0.05 and cost_delta_pct <= 0:
        return "PARETO_BETTER"
    if quality_delta > 0.05 and cost_delta_pct <= 25:
        return "QUALITY_UP_COST_NEUTRAL"
    if quality_delta > 0.05:
        return "QUALITY_UP_COST_UP"
    if quality_delta < -0.05 or (quality_delta <= 0.05 and cost_delta_pct > 25):
        return "PARETO_WORSE"
    return "NO_MEANINGFUL_DELTA"


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def run_effect_eval(
    *,
    runner: dict[str, Any],
    artifact_root: str,
    skill_name: str,
    effect_cases: list[dict[str, Any]],
    run_root: Path,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    effect_root = run_root / "effect"
    workspace_base = workspace_root or effect_root / "workspaces"
    results: list[dict[str, Any]] = []
    if not effect_cases:
        report = {
            "status": "no_cases",
            "score": None,
            "summary": "Effect eval has no cases; add Effect Cases to measure result quality.",
            "metrics": {"total_cases": 0, "valid_cases": 0, "simulated": False},
            "case_results": [],
            "analyzer_notes": ["No Effect Cases were configured, so quality lift cannot be measured."],
        }
        write_json(effect_root / "report.json", report)
        return report

    skill_source_root = prepare_skill_cache(Path(artifact_root), workspace_base, skill_name)

    for index, case in enumerate(effect_cases, start=1):
        key = case.get("case_key") or case.get("id") or f"case-{index}"
        case_root = effect_root / str(key)
        metadata = {
            "case_id": case.get("id") or key,
            "case_key": key,
            "prompt": case["prompt"],
            "expected_output": case.get("expected_output") or "",
            "assertions": case.get("assertions") or [],
            "files": case.get("files") or [],
        }
        write_json(case_root / "eval_metadata.json", metadata)
        with_skill = run_effect_case_configuration(
            runner=runner,
            case=case,
            configuration="with_skill",
            artifact_root=artifact_root,
            skill_name=skill_name,
            case_root=case_root,
            workspace_root=workspace_base / str(key),
            skill_source_root=skill_source_root,
        )
        without_skill = run_effect_case_configuration(
            runner=runner,
            case=case,
            configuration="without_skill",
            artifact_root=artifact_root,
            skill_name=skill_name,
            case_root=case_root,
            workspace_root=workspace_base / str(key),
        )
        delta = round(with_skill["pass_rate"] - without_skill["pass_rate"], 4)
        with_assertions = {item["text"]: item for item in with_skill["assertion_results"]}
        without_assertions = {item["text"]: item for item in without_skill["assertion_results"]}
        non_discriminating = [
            text for text, item in with_assertions.items()
            if item["passed"] and without_assertions.get(text, {}).get("passed")
        ]
        regressions = [
            text for text, item in without_assertions.items()
            if item["passed"] and not with_assertions.get(text, {}).get("passed")
        ]
        results.append(
            {
                "case_id": case.get("id") or key,
                "case_key": key,
                "prompt": case["prompt"],
                "expected_output": case.get("expected_output") or "",
                "assertions": case.get("assertions") or [],
                "with_skill": with_skill,
                "without_skill": without_skill,
                "delta_pass_rate": delta,
                "non_discriminating_assertions": non_discriminating,
                "regression_assertions": regressions,
                "needs_expectations": with_skill["needs_expectations"],
            }
        )

    valid_results = [item for item in results if not item["needs_expectations"]]
    valid_count = len(valid_results)
    with_rates = [item["with_skill"]["pass_rate"] for item in valid_results]
    without_rates = [item["without_skill"]["pass_rate"] for item in valid_results]
    with_pass_rate = round(mean(with_rates), 4) if valid_count else 0.0
    without_pass_rate = round(mean(without_rates), 4) if valid_count else 0.0
    skill_lift = round(with_pass_rate - without_pass_rate, 4)
    score = round(with_pass_rate * 100, 1) if valid_count else None
    with_tokens = mean([item["with_skill"]["metrics"]["total_tokens"] for item in valid_results])
    without_tokens = mean([item["without_skill"]["metrics"]["total_tokens"] for item in valid_results])
    with_duration = mean([item["with_skill"]["metrics"]["duration_ms"] for item in valid_results])
    without_duration = mean([item["without_skill"]["metrics"]["duration_ms"] for item in valid_results])
    with_tools = mean([item["with_skill"]["metrics"]["tool_calls"] for item in valid_results])
    without_tools = mean([item["without_skill"]["metrics"]["tool_calls"] for item in valid_results])
    assertions_passed = sum(item["with_skill"]["summary"]["passed"] for item in valid_results)
    assertions_total = sum(item["with_skill"]["summary"]["total"] for item in valid_results)
    tokens_per_passing = round(with_tokens / assertions_passed, 1) if assertions_passed else None
    cost_delta_pct = round(((with_tokens - without_tokens) / without_tokens) * 100, 1) if without_tokens else 0.0
    duration_delta_pct = round(((with_duration - without_duration) / without_duration) * 100, 1) if without_duration else 0.0
    classification = classify_cost_efficiency(skill_lift, cost_delta_pct)
    notes: list[str] = []
    non_discriminating_count = sum(len(item["non_discriminating_assertions"]) for item in valid_results)
    regression_count = sum(len(item["regression_assertions"]) for item in valid_results)
    if non_discriminating_count:
        notes.append(f"{non_discriminating_count} assertions passed in both with_skill and baseline; consider tightening them.")
    if regression_count:
        notes.append(f"{regression_count} assertions passed in baseline but failed with the skill; inspect regressions.")
    if classification == "PARETO_WORSE":
        notes.append("The skill did not improve quality enough to justify its token cost.")
    if not notes:
        notes.append("No obvious assertion discrimination or cost-efficiency issues were detected.")

    metrics = {
        "score": score,
        "total_cases": len(results),
        "valid_cases": valid_count,
        "with_skill_pass_rate": with_pass_rate,
        "without_skill_pass_rate": without_pass_rate,
        "skill_lift": skill_lift,
        "assertions_passed": assertions_passed,
        "assertions_total": assertions_total,
        "deterministic_assertions": sum(item["with_skill"]["deterministic_assertions"] for item in valid_results),
        "judge_assertions": sum(item["with_skill"]["judge_assertions"] for item in valid_results),
        "uncertain_assertions": sum(item["with_skill"]["uncertain_assertions"] for item in valid_results),
        "non_discriminating_assertions": non_discriminating_count,
        "regression_assertions": regression_count,
        "mean_duration_ms": round(with_duration, 1),
        "mean_total_tokens": round(with_tokens, 1),
        "mean_tool_calls": round(with_tools, 1),
        "duration_delta_pct": duration_delta_pct,
        "token_delta_pct": cost_delta_pct,
        "tool_call_delta": round(with_tools - without_tools, 1),
        "tokens_per_passing_assertion": tokens_per_passing,
        "quality_delta": skill_lift,
        "cost_delta_pct": cost_delta_pct,
        "cost_efficiency_classification": classification,
        "simulated": False,
    }
    status = "completed" if valid_count else "needs_expectations"
    report = {
        "status": status,
        "score": score,
        "summary": f"Effect eval completed: with-skill pass rate {with_pass_rate:.0%}, baseline {without_pass_rate:.0%}, lift {skill_lift:+.0%}." if valid_count else "Effect eval has no valid assertions or expected outputs.",
        "metrics": metrics,
        "case_results": results,
        "analyzer_notes": notes,
        "cost_efficiency": {
            "quality_delta": skill_lift,
            "cost_delta_pct": cost_delta_pct,
            "classification": classification,
        },
    }
    write_json(effect_root / "report.json", report)
    return report
