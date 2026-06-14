# Effect 评测详细设计

## 1. 设计目标

Effect 评测用于判断 Skill 是否真正提升任务结果。它不是模型自评，也不是简单检查 Skill 是否被触发。

当前 Effect 评测吸收两类方法：

- skill-creator 风格：with-skill 与 baseline 对照运行，沉淀可复核 artifact。
- AWS sample-agent-skill-eval 风格：assertion 是可执行判定规格，优先代码判定，必要时使用 Judge 模型。

核心原则：

- `expected_output` 是目标描述。
- `assertions` 是自动化判定单元。
- deterministic assertion 优先。
- LLM Judge 是 assertion 执行后端之一。
- Runner 模型是被测对象，不是裁判。

## 2. Runner 与 Judge 边界

Runner：

- 负责执行 prompt。
- 负责加载或不加载 Skill。
- 产生 raw output、tool calls、stdout/stderr、token 和耗时。

Judge：

- 负责判断语义类 assertion 是否满足。
- 使用系统设置中的全局裁判模型。
- 不使用 Runner 的 `model_name`。
- 不使用 legacy `runner_environments.judge_model`。

Judge 模型来源：

```text
model_role_settings.role = "judge"
```

调用模块：

```text
backend/app/model_client.py
```

## 3. Effect Case 数据结构

数据库表：`effect_cases`

字段：

| 字段 | 说明 |
| --- | --- |
| `case_key` | 测试用例稳定标识，用户可读 |
| `prompt` | 发给 Runner 的任务输入 |
| `expected_output` | 目标输出的自然语言描述 |
| `files` | 输入文件列表，路径相对 Skill artifact root |
| `assertions` | 自动化判定规格列表 |

示例：

```json
{
  "case_key": "summarize-csv",
  "prompt": "Summarize the revenue trend from sales.csv",
  "expected_output": "The answer should mention quarterly revenue growth and identify Q4 as the strongest quarter.",
  "files": ["examples/sales.csv"],
  "assertions": [
    "contains \"Q4\"",
    "contains \"revenue\"",
    "judge: explains the main trend correctly"
  ]
}
```

## 4. 执行流程

每个 Effect Case 执行两次：

```text
case
  -> with_skill
  -> without_skill
```

### 4.1 with_skill

流程：

1. 创建 workspace。
2. 复制 case.files 到 workspace。
3. 通过 `runner_adapter.run_prompt(..., load_skill=true)` 调用 Runner。
4. 当前 `opencode_cli` adapter 会把 Skill 放到 `.opencode/skills/<skill_name>/SKILL.md`。
5. 保存 stdout、stderr、response、metrics。
6. 执行 assertion grading。

### 4.2 without_skill

流程：

1. 创建独立 workspace。
2. 复制同样的 case.files。
3. 通过 `runner_adapter.run_prompt(..., load_skill=false)` 调用同一个 Runner。
4. 不加载 Skill。
5. 保存同样 artifact。
6. 执行同样 assertion grading。

### 4.3 为什么需要 baseline

只看 with-skill 输出无法判断提升是否来自 Skill。baseline 用于识别：

- Skill 是否带来增益。
- 不用 Skill 是否也能完成任务。
- Skill 是否反而造成退化。
- assertion 是否没有区分度。

## 5. Assertion 判定结果结构

每条 assertion 输出：

```json
{
  "text": "contains \"Q4\"",
  "passed": true,
  "evidence": "Substring found: 'Q4'",
  "method": "deterministic",
  "confidence": 1.0,
  "uncertain": false
}
```

字段说明：

- `text`：原始 assertion。
- `passed`：是否满足。
- `evidence`：判定证据。
- `method`：`deterministic` 或 `llm_judge`。
- `confidence`：置信度，确定性规则通常为 1.0。
- `uncertain`：Judge 或系统无法稳定判断时为 true。

## 6. Deterministic Assertion DSL

### 6.1 `contains "text"`

- 方法：deterministic
- 判定：输出文本忽略大小写后包含指定子串。
- 通过示例：输出包含 `Q4`，assertion 为 `contains "Q4"`。
- 失败证据：`Substring not found: 'Q4'`。

### 6.2 `does not contain "text"`

- 方法：deterministic
- 判定：输出文本忽略大小写后不包含指定子串。
- 使用场景：禁止泄露敏感词、禁止出现错误格式。
- 失败证据：`Substring found (FAIL): '...'`。

### 6.3 `starts with "text"`

- 方法：deterministic
- 判定：输出去除左侧空白后，以指定文本开头，忽略大小写。
- 使用场景：要求输出固定前缀或格式。

### 6.4 `ends with "text"`

- 方法：deterministic
- 判定：输出去除右侧空白后，以指定文本结尾，忽略大小写。
- 使用场景：要求输出固定后缀。

### 6.5 `matches regex /pattern/`

- 方法：deterministic
- 判定：Python `re.search(pattern, output)` 有匹配。
- 失败情况：
  - 正则不匹配。
  - 正则语法非法。
- 使用场景：检查格式、日期、编号、JSON 片段等。

### 6.6 `is valid json`

- 方法：deterministic
- 判定：`json.loads(output)` 成功。
- 使用场景：要求 Runner 输出可机器解析 JSON。

### 6.7 `has at least N lines`

- 方法：deterministic
- 判定：`len(output.splitlines()) >= N`。
- 使用场景：要求输出至少包含若干条结构化内容。

### 6.8 `json path $.a.b equals value`

- 方法：deterministic
- 判定：
  1. 输出必须是合法 JSON。
  2. 按简单点路径读取字段。
  3. 将实际值转字符串后与 expected 比较。
- 当前限制：只支持简单对象路径，不支持数组索引、过滤器、复杂 JSONPath。

### 6.9 `file exists path`

- 方法：deterministic
- 判定：workspace 内存在指定文件。
- 安全限制：路径 resolve 后必须仍在 workspace 内。
- 使用场景：验证 Runner 是否生成了预期文件。

### 6.10 `file contains path "text"`

- 方法：deterministic
- 判定：
  1. workspace 内存在指定文件。
  2. 文件文本内容忽略大小写后包含指定子串。
- 安全限制：路径不得逃逸 workspace。

### 6.11 `tool called name`

- 方法：deterministic
- 判定：Runner 输出解析出的 tool calls 中包含指定工具名。
- 使用场景：验证是否使用了某个工具或能力。

### 6.12 `skill invoked <skill_name>`

- 方法：deterministic
- 判定：
  - Runner 输出中观察到 Skill 调用。
  - assertion 中的 skill name 与当前被测 skill name 一致。
- 使用场景：在 Effect 中确保 with-skill 运行确实触发了目标 Skill。

## 7. LLM Judge

### 7.1 触发条件

以下情况交给 LLM Judge：

- assertion 以 `judge:` 开头。
- assertion 不属于 deterministic DSL。
- assertions 为空但 `expected_output` 非空，系统生成：

```text
judge: output satisfies expected output: <expected_output>
```

### 7.2 Judge 输入

Judge prompt 包含：

- 任务 prompt。
- expected_output。
- assertion 列表。
- actual output。
- stdout 摘要。
- stderr 摘要。

### 7.3 Judge 输出格式

Judge 必须返回 JSON：

```json
{
  "results": [
    {
      "text": "assertion text",
      "passed": true,
      "evidence": "specific evidence",
      "confidence": 0.9,
      "uncertain": false
    }
  ]
}
```

### 7.4 异常处理

以下情况 assertion 标记为：

```json
{
  "passed": false,
  "method": "llm_judge",
  "confidence": 0.0,
  "uncertain": true
}
```

触发条件：

- 未配置裁判模型。
- 模型被停用。
- Provider 被停用。
- API Key 缺失。
- 模型 API 调用失败。
- API 返回非 JSON。
- Judge 返回内容不是规定 JSON。
- Judge results 数量不足。

## 8. 模型 API 调用

Judge 调用使用系统设置中的模型配置。

支持：

- `openai_compatible`
- `anthropic`

OpenAI-compatible：

```text
POST {base_url}/chat/completions
```

Anthropic：

```text
POST {base_url}/v1/messages
```

系统不内置 OpenAI endpoint。DeepSeek、OpenAI-compatible 网关、私有兼容服务都由用户自行配置 `base_url`。

## 9. Case 级指标

每个 case 计算：

- `with_skill.pass_rate`
- `without_skill.pass_rate`
- `skill_lift`
- `assertions_total`
- `assertions_passed`
- `deterministic_assertions`
- `judge_assertions`
- `uncertain_assertions`
- `non_discriminating_assertions`
- `regression_assertions`

定义：

- non-discriminating：with-skill 和 baseline 都通过的 assertion。
- regression：baseline 通过但 with-skill 失败的 assertion。

## 10. Run 级 Effect 指标

聚合字段：

- `effect_score`
- `with_skill_pass_rate`
- `without_skill_pass_rate`
- `skill_lift`
- `valid_cases`
- `case_count`
- `uncertain_assertions`
- `non_discriminating_assertions`
- `regression_assertions`

评分：

```text
effect_score = mean(case.with_skill_pass_rate) * 100
skill_lift = mean(case.with_skill_pass_rate - case.without_skill_pass_rate)
```

无有效 case：

- `status = no_cases`
- `score = null`
- summary 提示需要补充 Effect Cases。

## 11. 成本效率指标

每次 Runner 调用记录：

- `duration_ms`
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `tool_calls`
- `errors_encountered`
- `estimated_cost`

派生指标：

- `tokens_per_passing_assertion`
- `quality_delta`
- `cost_delta_pct`
- `cost_efficiency_classification`

分类逻辑：

| 分类 | 条件 | 含义 |
| --- | --- | --- |
| `PARETO_BETTER` | 质量提升且成本不增加 | 更好且不更贵 |
| `QUALITY_UP_COST_NEUTRAL` | 质量提升且成本增幅 <= 25% | 更好，成本可接受 |
| `QUALITY_UP_COST_UP` | 质量提升但成本明显增加 | 效果提升但需关注成本 |
| `PARETO_WORSE` | 质量下降，或质量无明显提升且成本增加 > 25% | 不值得推荐 |
| `NO_MEANINGFUL_DELTA` | 质量和成本变化都不明显 | 无明显差异 |

## 12. Artifact 结构

主报告：

```text
data/runs/<run_id>/effect/report.json
```

每个 case/configuration：

```text
effect/<case_key>/with_skill/stdout.jsonl
effect/<case_key>/with_skill/stderr.log
effect/<case_key>/with_skill/response.txt
effect/<case_key>/with_skill/metrics.json
effect/<case_key>/with_skill/grading.json

effect/<case_key>/without_skill/stdout.jsonl
effect/<case_key>/without_skill/stderr.log
effect/<case_key>/without_skill/response.txt
effect/<case_key>/without_skill/metrics.json
effect/<case_key>/without_skill/grading.json
```

Judge artifact：

```text
effect/<case_key>/<configuration>/judge/judge.stdout.jsonl
effect/<case_key>/<configuration>/judge/judge.stderr.log
effect/<case_key>/<configuration>/judge/usage.json
```

## 13. 前端展示

Effect Evidence Tab 展示：

- Effect Summary。
- Case 列表。
- with-skill pass rate。
- baseline pass rate。
- skill lift。
- assertion 表格。
- Judge uncertainty。
- regression assertions。
- non-discriminating assertions。
- cost efficiency。

交互建议：

- 默认展示 case summary。
- 点击 case 查看 assertion 明细。
- 对 regression 和 non-discriminating 给出明显提示。
- Raw logs 只显示路径，不在 MVP 中渲染完整日志。

## 14. Recommendation 影响

- Effect >= 80 且 `skill_lift > 0` 是 `recommended` 的必要条件。
- Effect >= 60 是 `usable` 的必要条件。
- Effect 50-79 通常为 `review_required`。
- Effect < 50 为 `not_recommended`。
- with-skill 明显低于 baseline 为 `not_recommended`。
- `PARETO_WORSE` 阻止进入 `recommended`。

## 15. 当前边界

- 每个 case/configuration 只运行一次。
- 不计算方差和置信区间。
- 不执行用户自定义代码 assertion。
- 不支持数据模型自动生成 case。
- 不支持在线编辑 artifact 文件。
- 当前 Runner Adapter 只实现 `opencode_cli`。
