import json
from pathlib import Path

from app.effect_evaluator import deterministic_grade, run_effect_eval


def write_skill(root: Path) -> None:
    root.mkdir()
    (root / "SKILL.md").write_text(
        "---\nname: sample-skill\ndescription: Sample skill.\n---\nUse this skill for sample work.\n",
        encoding="utf-8",
    )


def make_fake_opencode(tmp_path: Path, mode: str = "normal") -> Path:
    command = tmp_path / f"fake-effect-opencode-{mode}.py"
    command.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "from pathlib import Path\n"
        f"mode = {mode!r}\n"
        "prompt = sys.argv[-1]\n"
        "has_skill = bool(list((Path.cwd() / '.opencode' / 'skills').glob('*/SKILL.md')))\n"
        "if 'evaluation judge' in prompt.lower():\n"
        "    if mode == 'bad_judge':\n"
        "        print('not json')\n"
        "    else:\n"
        "        print(json.dumps({'type':'assistant','message':{'content':[{'type':'text','text':json.dumps({'results':[{'text':'judge assertion','passed': True,'evidence':'judge evidence','confidence':0.8,'uncertain':False}]})}]}}))\n"
        "    sys.exit(0)\n"
        "text = 'valid result with skill' if has_skill else 'baseline result'\n"
        "if mode == 'regression':\n"
        "    text = 'baseline result' if has_skill else 'valid result with skill'\n"
        "print(json.dumps({'type':'assistant','message':{'content':[{'type':'text','text':text}]}}))\n"
        "if has_skill:\n"
        "    print(json.dumps({'type':'tool_use','part':{'tool':'skill','state':{'input':{'name':'sample-skill'}}}}))\n"
        "print(json.dumps({'type':'step_finish','part':{'tokens':{'input':10,'output':5,'total':15}}}))\n",
        encoding="utf-8",
    )
    command.chmod(0o755)
    return command


def test_deterministic_assertions_cover_core_dsl(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "out.txt").write_text("hello file", encoding="utf-8")
    output = '{"name":"demo"}\nsecond line'

    assert deterministic_grade('contains "demo"', output, workspace, [], "sample-skill", False)["passed"]
    assert deterministic_grade('does not contain "missing"', output, workspace, [], "sample-skill", False)["passed"]
    assert deterministic_grade("matches regex /demo/", output, workspace, [], "sample-skill", False)["passed"]
    assert deterministic_grade("is valid json", '{"ok": true}', workspace, [], "sample-skill", False)["passed"]
    assert deterministic_grade("has at least 2 lines", output, workspace, [], "sample-skill", False)["passed"]
    assert deterministic_grade("json path $.name equals demo", '{"name":"demo"}', workspace, [], "sample-skill", False)["passed"]
    assert deterministic_grade("file exists out.txt", output, workspace, [], "sample-skill", False)["passed"]
    assert deterministic_grade('file contains out.txt "hello"', output, workspace, [], "sample-skill", False)["passed"]
    assert deterministic_grade("tool called bash", output, workspace, [{"name": "bash"}], "sample-skill", False)["passed"]
    assert deterministic_grade("skill invoked sample-skill", output, workspace, [], "sample-skill", True)["passed"]


def test_effect_eval_scores_with_skill_lift_and_cost_metrics(tmp_path):
    artifact = tmp_path / "artifact"
    write_skill(artifact)
    runner = {
        "runner_type": "opencode_cli",
        "model_name": "openai/gpt-5.3-codex-spark",
        "judge_model": "openai/gpt-5.3-codex-spark",
        "command_path": str(make_fake_opencode(tmp_path)),
        "timeout_seconds": 5,
    }

    result = run_effect_eval(
        runner=runner,
        artifact_root=str(artifact),
        skill_name="sample-skill",
        effect_cases=[{"id": "case-1", "case_key": "case-1", "prompt": "do task", "expected_output": "", "files": [], "assertions": ['contains "valid result"']}],
        run_root=tmp_path / "run",
    )

    assert result["status"] == "completed"
    assert result["score"] == 100.0
    assert result["metrics"]["skill_lift"] == 1.0
    assert result["metrics"]["assertions_passed"] == 1
    assert result["metrics"]["tokens_per_passing_assertion"] == 15.0
    assert result["metrics"]["cost_efficiency_classification"] in {"PARETO_BETTER", "QUALITY_UP_COST_NEUTRAL", "QUALITY_UP_COST_UP"}


def test_effect_eval_uses_external_workspace_when_provided(tmp_path):
    artifact = tmp_path / "artifact"
    write_skill(artifact)
    runner = {
        "runner_type": "opencode_cli",
        "model_name": "openai/gpt-5.3-codex-spark",
        "judge_model": "openai/gpt-5.3-codex-spark",
        "command_path": str(make_fake_opencode(tmp_path)),
        "timeout_seconds": 5,
    }
    run_root = tmp_path / "run"
    workspace_root = tmp_path / "isolated-workspaces"

    result = run_effect_eval(
        runner=runner,
        artifact_root=str(artifact),
        skill_name="sample-skill",
        effect_cases=[{"id": "case-1", "case_key": "case-1", "prompt": "do task", "expected_output": "", "files": [], "assertions": ['contains "valid result"']}],
        run_root=run_root,
        workspace_root=workspace_root,
    )

    assert result["status"] == "completed"
    assert (workspace_root / "case-1" / "with_skill" / "workspace" / ".opencode" / "skills" / "sample-skill" / "SKILL.md").exists()
    assert not (run_root / "effect" / "case-1" / "with_skill" / "workspace").exists()


def test_effect_eval_marks_non_discriminating_and_regressions(tmp_path):
    artifact = tmp_path / "artifact"
    write_skill(artifact)
    runner = {
        "runner_type": "opencode_cli",
        "model_name": "openai/gpt-5.3-codex-spark",
        "judge_model": "openai/gpt-5.3-codex-spark",
        "command_path": str(make_fake_opencode(tmp_path, "regression")),
        "timeout_seconds": 5,
    }

    result = run_effect_eval(
        runner=runner,
        artifact_root=str(artifact),
        skill_name="sample-skill",
        effect_cases=[
            {"id": "case-1", "case_key": "case-1", "prompt": "do task", "expected_output": "", "files": [], "assertions": ['contains "valid result"']},
            {"id": "case-2", "case_key": "case-2", "prompt": "do task", "expected_output": "", "files": [], "assertions": ['contains "result"']},
        ],
        run_root=tmp_path / "run",
    )

    assert result["metrics"]["regression_assertions"] == 1
    assert result["metrics"]["non_discriminating_assertions"] == 1


def test_effect_eval_handles_missing_judge_model_as_uncertain(tmp_path, monkeypatch):
    import app.effect_evaluator as effect_evaluator

    monkeypatch.setattr(effect_evaluator, "get_role_model", lambda role: None)
    artifact = tmp_path / "artifact"
    write_skill(artifact)
    runner = {
        "runner_type": "opencode_cli",
        "model_name": "openai/gpt-5.3-codex-spark",
        "judge_model": "openai/gpt-5.3-codex-spark",
        "command_path": str(make_fake_opencode(tmp_path)),
        "timeout_seconds": 5,
    }

    result = run_effect_eval(
        runner=runner,
        artifact_root=str(artifact),
        skill_name="sample-skill",
        effect_cases=[{"id": "case-1", "case_key": "case-1", "prompt": "do task", "expected_output": "good output", "files": [], "assertions": []}],
        run_root=tmp_path / "run",
    )

    assertion = result["case_results"][0]["with_skill"]["assertion_results"][0]
    assert assertion["method"] == "llm_judge"
    assert assertion["uncertain"] is True
    assert assertion["passed"] is False
    assert "not configured" in assertion["evidence"]


def test_effect_eval_no_cases_has_no_score(tmp_path):
    result = run_effect_eval(
        runner={"runner_type": "opencode_cli", "command_path": str(tmp_path / "missing"), "model_name": "model", "timeout_seconds": 1},
        artifact_root=str(tmp_path),
        skill_name="sample-skill",
        effect_cases=[],
        run_root=tmp_path / "run",
    )

    assert result["status"] == "no_cases"
    assert result["score"] is None
    assert json.loads((tmp_path / "run" / "effect" / "report.json").read_text(encoding="utf-8"))["status"] == "no_cases"
