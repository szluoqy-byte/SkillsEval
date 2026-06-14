# 评测体系详细设计

## 1. 设计目标

SkillsEval 的评测体系用于回答三个独立问题：

1. `Scan`：这个 Skill 包是否结构完整、安全、可维护？
2. `Trigger`：在被测 Runner 下，这个 Skill 是否会在正确场景被真实触发？
3. `Effect`：触发 Skill 后，任务结果是否比不使用 Skill 更好？

当前系统不再追求合并成一个 `overall_score`。原因是：

- 静态风险、触发能力、任务效果本质不同。
- 单一总分会掩盖关键风险，例如 Scan critical 但 Effect 很高。
- Skill 选型更需要可解释的多维证据。

因此，新任务的 `evaluation_runs.overall_score` 写入 `null`，页面展示三类指标和 recommendation 策略标签。

## 2. Stage 与指标映射

| 产品指标 | Stage Key | 实现模块 | 主要输出 |
| --- | --- | --- | --- |
| Scan | `static_scan` | `static_scanner.scan_skill_version` | scan_score、status、findings、rules |
| Trigger | `trigger_eval` | `runner_adapter.run_trigger_eval` | trigger_score、query results、stdout/stderr |
| Effect | `effect_eval` | `effect_evaluator.run_effect_eval` | effect_score、skill_lift、assertions、cost efficiency |

不再存在独立一级 `performance_eval`。耗时、token、工具调用、成本变化都作为 Effect 下的解释证据。

## 3. 任务执行链路

```text
POST /api/tasks
  -> create_task
  -> evaluation_tasks.status = queued
  -> BackgroundTasks.run_task

run_task
  -> 创建 evaluation_runs
  -> static_scan
  -> trigger_eval
  -> effect_eval
  -> 写 stage_results
  -> 写 evidence_items
  -> 写 result_summary
  -> 写 recommendation
  -> evaluation_tasks.status = completed
```

失败链路：

```text
任一未捕获异常
  -> evaluation_runs.status = failed
  -> evaluation_tasks.status = failed
  -> 不伪造后续阶段结果
```

## 4. 评测数据生成辅助

Evaluation Set 中的 Trigger Queries 和 Effect Cases 可以由 Data Model 辅助生成，但生成结果只是草稿，不直接参与评测。

生成链路：

```text
用户点击 AI 生成
  -> 创建 evaluation_set_generation_jobs
  -> 后台读取 Skill 元信息和 SKILL.md
  -> 调用全局 data model
  -> 解析 JSON 草稿
  -> 标记重复项
  -> 用户审核、编辑、勾选
  -> confirm 后写入正式 Trigger Queries 或 Effect Cases
```

设计原则：

- Data Model 负责提高测试数据准备效率。
- 用户负责最终筛选和确认，避免模型幻觉直接污染评测集。
- 重复项默认不选中。
- 生成失败保留错误信息，不写入正式数据。
- Full Evaluation 只读取正式入库的数据，不读取未确认草稿。

Trigger 生成要求：

- 输出 `query`、`should_trigger`、`rationale`。
- 可选择是否包含负样例。
- 正负样例都应围绕当前 Skill 的触发边界，而不是泛化问题。

Effect 生成要求：

- 输出 `case_key`、`prompt`、`expected_output`、`assertions`、`rationale`。
- assertions 优先使用 deterministic DSL。
- 只有语义质量难以代码判定时才建议 `judge:` assertion。

## 5. Scan 指标

Scan 关注 Skill 包本身，不运行模型。

输入：

- `skill_versions.artifact_root`
- `skill_versions.manifest`

输出：

- `scan_score`
- `scan_status`
- `critical_count`
- `major_count`
- `minor_count`
- `info_count`
- `total_findings`
- `rules_evaluated`
- `files_scanned`

评分：

```text
scan_score = clamp(
  100
  - critical_count * 25
  - major_count * 10
  - minor_count * 3
  - info_count * 1,
  0,
  100
)
```

状态：

- `critical`：存在 critical finding。
- `warning`：无 critical，但存在 major/minor finding。
- `passed`：无 active finding。

证据：

- `static/findings.json`
- `static/static_metrics.json`

前端展示：

- 默认展示 Findings。
- 支持查看 Passed Rules。
- 不把整个 Skill 表达为 pass/fail。

详细规则见 `static-scan-rules-design.md`。

## 6. Trigger 指标

Trigger 关注 Skill 是否被真实调用。

### 6.1 Trigger Query 数据结构

每条 Trigger Query 包含：

- `query`：发送给 Runner 的输入。
- `should_trigger`：预期是否触发该 Skill。

### 6.2 执行逻辑

对于每条 query：

1. 创建独立 workspace。
2. 将 Skill 加载到 Runner 需要的位置。
3. 调用 Runner。
4. 解析 Runner stdout。
5. 判断是否观察到 Skill 调用。
6. 与 `should_trigger` 对比得到判定结果。

当前 `opencode_cli` adapter 的触发证据来自 JSONL 事件：

- 原生 skill tool 调用。
- `skill({ name: "<skill_name>" })` 类事件。
- 读取 `.opencode/skills/<skill_name>/SKILL.md` 的事件。

### 6.3 判定规则

正样本：

```text
should_trigger = true
triggered = true
=> matched
```

负样本：

```text
should_trigger = false
triggered = false
=> matched
```

其他情况为 mismatch。

### 6.4 评分

```text
trigger_score = matched_queries / total_queries * 100
```

无 Trigger Queries：

- `total_queries = 0`
- `trigger_score = 0`
- recommendation = `not_recommended`

### 6.5 输出字段

每条 query 输出：

- `query_id`
- `query`
- `should_trigger`
- `triggered`
- `pass`
- `duration_ms`
- `stdout_path`
- `stderr_path`
- `error`

整体 metrics：

- `total_queries`
- `matched_queries`
- `mismatched_queries`
- `passed_queries`
- `failed_queries`
- `runner_type`
- `model_name`
- `command_path`
- `timeout_seconds`
- `simulated = false`

## 7. Effect 指标

Effect 关注 Skill 对任务结果的实际提升。

### 7.1 Effect Case 数据结构

每条 Effect Case 包含：

- `case_key`
- `prompt`
- `expected_output`
- `files`
- `assertions`

其中：

- `expected_output` 是目标描述，供用户理解和 Judge 使用。
- `assertions` 是真正参与自动化判定的规格。

### 7.2 with-skill vs baseline

每个 case 跑两组：

- `with_skill`：加载 Skill。
- `without_skill`：不加载 Skill。

两组使用相同：

- prompt
- files
- Runner
- model_name
- timeout_seconds

这样可以计算 Skill 带来的实际提升，而不是只看单次输出是否“看起来不错”。

### 7.3 assertion 判定

判定优先级：

1. deterministic assertion：代码规则可判定。
2. LLM Judge：语义或质量类 assertion。

每条 assertion 统一输出：

- `text`
- `passed`
- `evidence`
- `method`
- `confidence`
- `uncertain`

### 7.4 Effect 评分

```text
with_skill_pass_rate = with_skill_passed_assertions / assertions_total
without_skill_pass_rate = without_skill_passed_assertions / assertions_total
effect_score = with_skill_pass_rate * 100
skill_lift = with_skill_pass_rate - without_skill_pass_rate
```

无 Effect Cases：

- `effect_status = no_cases`
- recommendation 通常为 `review_required`
- 不伪造 Effect 分数。

详细设计见 `effect-eval-design.md`。

## 8. 成本效率证据

成本效率不是一级指标，但作为 Effect 的解释证据。

采集字段：

- `duration_ms`
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `tool_calls`
- `tokens_per_passing_assertion`
- `estimated_cost`

派生字段：

- `quality_delta`
- `cost_delta_pct`
- `cost_efficiency_classification`

分类：

- `PARETO_BETTER`
- `QUALITY_UP_COST_NEUTRAL`
- `QUALITY_UP_COST_UP`
- `PARETO_WORSE`
- `NO_MEANINGFUL_DELTA`

解释：

- `PARETO_BETTER`：质量提升且成本不增加。
- `QUALITY_UP_COST_NEUTRAL`：质量提升，成本增幅可接受。
- `QUALITY_UP_COST_UP`：质量提升但成本明显增加。
- `PARETO_WORSE`：质量无提升或下降，成本还增加。
- `NO_MEANINGFUL_DELTA`：质量和成本差异不明显。

## 9. Recommendation 策略

Recommendation 是策略标签，不是总分映射。

### recommended

条件：

- Scan 无 critical。
- Trigger >= 80。
- Effect >= 80。
- `skill_lift > 0`。
- 成本效率不是 `PARETO_WORSE`。

含义：

- 可以优先推荐给 Skill 选型用户。
- 仍可查看证据，但无需默认复核。

### usable

条件：

- Scan 无 critical。
- Trigger >= 80。
- Effect >= 60。

含义：

- 可用，但效果或证据强度未达到推荐级。

### review_required

触发条件：

- Scan warning 或 critical。
- Trigger 50-79。
- Effect 50-79。
- 无 Effect Cases。
- Judge uncertainty 过多。

含义：

- 需要测试人员或运营人员复核。
- 不代表不可用。

### not_recommended

触发条件：

- 无 Trigger Queries。
- Trigger < 50。
- Effect < 50。
- 运行失败。
- with-skill 明显劣于 baseline。

含义：

- 不建议选型使用。
- 应优先补评测集或修复 Skill。

## 10. result_summary 设计

`evaluation_runs.result_summary` 是列表和卡片使用的轻量摘要。

字段建议：

```json
{
  "scan_score": 92.0,
  "scan_status": "warning",
  "trigger_score": 80.0,
  "trigger_matched_queries": 4,
  "trigger_total_queries": 5,
  "effect_score": 75.0,
  "effect_status": "completed",
  "effect_valid_cases": 3,
  "skill_lift": 0.25,
  "cost_efficiency_classification": "QUALITY_UP_COST_NEUTRAL"
}
```

使用场景：

- Overview 榜单。
- Skills 卡片。
- Skill Detail summary。
- Task list。

## 11. Evidence 展示设计

Task Detail evidence workspace 分为：

- Scan
- Trigger
- Effect
- Raw Artifacts

### Scan

默认展示 findings：

- rule id
- severity
- title
- detail
- file_path
- line_number
- fix

可切换 passed rules。

### Trigger

展示每条 query：

- 输入 query。
- 预期触发。
- 实际触发。
- 判定结果。
- 耗时。
- error。
- stdout/stderr 路径。

### Effect

展示：

- Effect Summary。
- 每个 case 的 with-skill 和 baseline。
- assertion 判定。
- Judge 证据。
- non-discriminating assertions。
- regression assertions。
- cost efficiency。

### Raw Artifacts

用于工程排查，不作为普通用户主阅读入口。

## 12. 旧模型兼容

历史四阶段模型：

- static_scan
- trigger_eval
- effect_eval
- performance_eval

以及 legacy weighted `overall_score`，只保留在：

- archive 文档。
- legacy DB 字段。
- legacy API 类型兼容。

当前新任务不使用四阶段加权模型。
