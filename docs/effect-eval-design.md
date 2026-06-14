# Effect Eval Design

## Goal

Effect measures whether a Skill improves task outcomes in the current SkillsEval architecture. It does not reintroduce a single overall score. Performance and cost are treated as Effect evidence, not a fourth top-level metric.

The design absorbs two practices:

- skill-creator: run with-skill and baseline, grade expectations, aggregate benchmark evidence.
- sample-agent-skill-eval: treat assertions as executable grading units, with deterministic checks first and an LLM judge fallback.

## Terms

- `prompt`: the task sent to the runner.
- `expected_output`: human-readable success description for reviewers and the judge.
- `assertions`: executable grading specs used for scoring.
- `deterministic assertion`: a rule checked by code.
- `llm_judge assertion`: a rule checked by the configured judge model.
- `judge model`: the global system role selected from Model API Providers / Model Profiles, separate from the Runner's tested model.

## Flow

For each Effect Case:

1. Create two isolated workspaces.
2. Run `with_skill` with the Skill loaded into `.opencode/skills/<skill_name>/`.
3. Run `without_skill` with the same prompt/files/model/timeout and no Skill.
4. Grade both outputs against assertions.
5. Aggregate quality lift and cost-efficiency metrics.

No Effect Cases means `effect_status = no_cases`; the system does not fabricate a score.

## Assertion DSL

MVP deterministic assertions:

- `contains "text"`
- `does not contain "text"`
- `starts with "text"`
- `ends with "text"`
- `matches regex /pattern/`
- `is valid json`
- `has at least N lines`
- `json path $.a.b equals value`
- `file exists path`
- `file contains path "text"`
- `tool called name`
- `skill invoked <skill_name>`

Unrecognized assertions and assertions prefixed with `judge:` are sent to the LLM judge. The judge uses the global `裁判模型` configured in System Settings. MVP supports OpenAI-compatible endpoints such as DeepSeek and native Anthropic Messages API providers. If no judge model is configured, the provider/model is disabled, the API call fails, or the judge response is not valid JSON, the assertion is marked `uncertain=true` and `passed=false`.

MVP does not execute user-provided Python or shell assertions.

Each assertion result uses:

```json
{
  "text": "contains \"valid\"",
  "passed": true,
  "evidence": "Substring found: 'valid'",
  "method": "deterministic",
  "confidence": 1.0,
  "uncertain": false
}
```

## Metrics

Quality:

- `effect_score = with_skill_pass_rate * 100`
- `with_skill_pass_rate`
- `without_skill_pass_rate`
- `skill_lift`
- `assertions_passed`
- `assertions_total`
- `non_discriminating_assertions`
- `regression_assertions`

Cost efficiency:

- `duration_ms`
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `tool_calls`
- `tokens_per_passing_assertion`
- `quality_delta`
- `cost_delta_pct`
- `cost_efficiency_classification`

Classifications:

- `PARETO_BETTER`
- `QUALITY_UP_COST_UP`
- `QUALITY_UP_COST_NEUTRAL`
- `PARETO_WORSE`
- `NO_MEANINGFUL_DELTA`

## Recommendation Policy

- `recommended`: Scan has no critical finding, Trigger >= 80, Effect >= 80, `skill_lift > 0`, and cost efficiency is not `PARETO_WORSE`.
- `usable`: Scan has no critical finding, Trigger >= 80, Effect >= 60.
- `review_required`: Scan warning/critical, Trigger 50-79, Effect 50-79, too many uncertain judge results, or no Effect Cases.
- `not_recommended`: no Trigger Queries, Trigger < 50, Effect < 50, run failure, or with-skill is clearly worse than baseline.

## Artifacts

Main artifact:

```text
data/runs/<run_id>/effect/report.json
```

Per case/configuration artifacts:

```text
effect/<case_key>/with_skill/stdout.jsonl
effect/<case_key>/with_skill/stderr.log
effect/<case_key>/with_skill/response.txt
effect/<case_key>/with_skill/metrics.json
effect/<case_key>/with_skill/grading.json
effect/<case_key>/without_skill/...
```

The task evidence API reads `effect/report.json` and returns summary, case results, assertion evidence, analyzer notes, and cost-efficiency evidence.
