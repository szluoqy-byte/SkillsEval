from pathlib import Path

from app.opencode_runner import parse_triggered, run_trigger_eval


def make_fake_opencode(tmp_path: Path, mode: str) -> Path:
    command = tmp_path / f"fake-opencode-{mode}.py"
    command.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys, time\n"
        "from pathlib import Path\n"
        f"mode = {mode!r}\n"
        "if mode == 'sleep':\n"
        "    time.sleep(5)\n"
        "if mode == 'fail':\n"
        "    print('boom', file=sys.stderr)\n"
        "    sys.exit(2)\n"
        "skills = list((Path.cwd() / '.opencode' / 'skills').glob('*/SKILL.md'))\n"
        "skill = skills[0].parent.name if skills else 'unknown'\n"
        "if mode == 'trigger':\n"
        "    print(json.dumps({'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'name': 'skill', 'input': {'name': skill}}]}}))\n"
        "else:\n"
        "    print(json.dumps({'type': 'assistant', 'message': {'content': []}}))\n",
        encoding="utf-8",
    )
    command.chmod(0o755)
    return command


def write_skill(root: Path) -> None:
    root.mkdir()
    (root / "SKILL.md").write_text(
        "---\nname: sample-skill\ndescription: Sample trigger skill.\n---\nUse this skill for sample work.\n",
        encoding="utf-8",
    )


def test_parse_triggered_detects_opencode_skill_tool_event():
    stdout = '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"skill","input":{"name":"sample-skill"}}]}}\n'

    assert parse_triggered(stdout, "sample-skill") is True
    assert parse_triggered(stdout, "other-skill") is False


def test_parse_triggered_detects_native_opencode_tool_use_event():
    stdout = (
        '{"type":"tool_use","part":{"type":"tool","tool":"skill",'
        '"state":{"status":"completed","input":{"name":"sample-skill"}}}}\n'
    )

    assert parse_triggered(stdout, "sample-skill") is True


def test_parse_triggered_detects_opencode_skill_file_read_event():
    stdout = (
        '{"type":"tool_use","part":{"type":"tool","tool":"read",'
        '"state":{"status":"completed","input":{"filePath":"/tmp/work/.opencode/skills/sample-skill/SKILL.md"},'
        '"output":"<path>/tmp/work/.opencode/skills/sample-skill/SKILL.md</path>"}}}\n'
    )

    assert parse_triggered(stdout, "sample-skill") is True
    assert parse_triggered(stdout, "other-skill") is False


def test_parse_triggered_does_not_count_glob_listing_as_invocation():
    stdout = (
        '{"type":"tool_use","part":{"type":"tool","tool":"glob",'
        '"state":{"status":"completed","input":{"pattern":"**/*","path":"/tmp/work"},'
        '"output":"/tmp/work/.opencode/skills/sample-skill/SKILL.md"}}}\n'
    )

    assert parse_triggered(stdout, "sample-skill") is False


def test_trigger_eval_scores_positive_and_negative_queries(tmp_path):
    skill_root = tmp_path / "artifact"
    write_skill(skill_root)
    runner = {
        "runner_type": "opencode_cli",
        "model_name": "openai/gpt-5.3-codex-spark",
        "command_path": str(make_fake_opencode(tmp_path, "trigger")),
        "timeout_seconds": 5,
    }

    result = run_trigger_eval(
        runner=runner,
        artifact_root=str(skill_root),
        skill_name="sample-skill",
        trigger_queries=[
            {"id": "positive", "query": "please trigger", "should_trigger": 1},
            {"id": "negative", "query": "near miss", "should_trigger": 0},
        ],
        run_root=tmp_path / "run",
    )

    assert result["score"] == 50.0
    assert result["summary"] == "Trigger eval completed: 1/2 queries matched expectations."
    assert result["metrics"]["matched_queries"] == 1
    assert result["metrics"]["mismatched_queries"] == 1
    assert result["metrics"]["passed_queries"] == 1
    assert result["results"][0]["pass"] is True
    assert result["results"][1]["pass"] is False


def test_trigger_eval_records_command_failures_without_simulation(tmp_path):
    skill_root = tmp_path / "artifact"
    write_skill(skill_root)
    runner = {
        "runner_type": "opencode_cli",
        "model_name": "openai/gpt-5.3-codex-spark",
        "command_path": str(make_fake_opencode(tmp_path, "fail")),
        "timeout_seconds": 5,
    }

    result = run_trigger_eval(
        runner=runner,
        artifact_root=str(skill_root),
        skill_name="sample-skill",
        trigger_queries=[{"id": "positive", "query": "please trigger", "should_trigger": 1}],
        run_root=tmp_path / "run",
    )

    assert result["score"] == 0.0
    assert result["metrics"]["simulated"] is False
    assert "exited with code 2" in result["results"][0]["error"]


def test_trigger_eval_records_timeout_without_simulation(tmp_path):
    skill_root = tmp_path / "artifact"
    write_skill(skill_root)
    runner = {
        "runner_type": "opencode_cli",
        "model_name": "openai/gpt-5.3-codex-spark",
        "command_path": str(make_fake_opencode(tmp_path, "sleep")),
        "timeout_seconds": 1,
    }

    result = run_trigger_eval(
        runner=runner,
        artifact_root=str(skill_root),
        skill_name="sample-skill",
        trigger_queries=[{"id": "positive", "query": "please trigger", "should_trigger": 1}],
        run_root=tmp_path / "run",
    )

    assert result["score"] == 0.0
    assert result["metrics"]["simulated"] is False
    assert "timed out" in result["results"][0]["error"]
