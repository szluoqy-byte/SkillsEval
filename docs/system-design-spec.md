# SkillsEval 系统设计说明书

状态：v0.1 讨论稿  
目标：支撑后续 AI Coding 分模块开发  
范围：第三方独立 Agent Skills 评测与选型平台

## 1. 背景与目标

SkillsEval 是一个第三方独立 skills 评测平台。它的核心目标不是复制某个开源评测工具，而是把不同来源的 skill 包、评测集、运行任务、评分证据和版本结果沉淀成可比较、可复核、可追踪的产品系统。

平台围绕三类指标展开：

```text
Scan -> Trigger -> Effect
```

MVP 的目标：

- 管理 Skill 与 Skill Version。
- 为每个 Skill 维护一个绑定的 Evaluation Set。
- 支持 Trigger Queries 与 Effect Cases 在同一 Evaluation Set 页面下独立辅助生成、导入、增删改查。
- 支持创建评测任务，先运行真实 Scan 与 Trigger；Effect 后续逐步实现，performance 归入 Effect 的效率子指标。
- 保存评测结果、评分指标、findings 和运行证据。
- 在 Skill Detail、任务详情和 Overview 榜单中消费评测结论。

非目标：

- 不做完整多租户权限系统。
- 不做企业审批流。
- 不自动修复 skill 或自动创建新 skill version。
- 不做大规模分布式调度。
- MVP 暂不展示 confidence 和人工复核状态。

## 2. 产品边界

MVP 菜单：

```text
Overview
Skills 管理
  - Skill 卡片列表
  - Skill Detail / Summary
  - Skill Detail / Evaluation Sets
评测任务管理
  - 任务队列
  - 新建任务
  - 任务详情
系统设置
  - 暂不展开
```

页面职责：

- Overview：展示系统整体指标和 Recommended Skills by Category。
- Skills 管理：管理 skill、版本、最近评测结论和评测集入口。
- Skill Detail Summary：展示版本评测结果、最新 suggestion、Scan / Trigger / Effect 三类指标、关键风险和评测证据摘要。
- Skill Detail Evaluation Sets：维护当前 Skill 绑定的 Trigger Queries 与 Effect Cases 定义，两类数据在同一页面下独立操作。
- 评测任务管理：管理任务队列、运行状态和历史任务。
- 任务详情：承载 Scan / Trigger / Effect 评估方法、指标结果、findings 和评测证据。

重要边界：

- Evaluation Sets 是定义态，不放运行结果和 suggestion。
- Suggestion 属于评测运行结果，由 Skill Detail Summary 展示当前最新版本最近一次任务产出的建议。
- Skill Detail 的版本结果暂不下钻。
- 任务详情负责解释评估方法和证据。

## 3. 系统架构

建议采用前后端分离架构。MVP 可以先用单体服务实现，但模块边界按可拆分服务设计。

```text
Web App
  |
  | REST/JSON
  v
API Server
  |-- Skill Service
  |-- Evaluation Set Service
  |-- Task Service
  |-- Result Service
  |-- Scoring Service
  |-- Evidence Service
  |
  | internal job interface
  v
Evaluation Worker
  |-- Static Scanner
  |-- Trigger Evaluator
  |-- Effect Evaluator
  |-- Performance Aggregator
  |-- Assertion Engine
  |-- LLM Judge Adapter
  |-- Runner Adapter
  |
  +--> Database
  +--> Evidence Storage
```

MVP 技术选型：

- 前端：Vite + React + TypeScript。
- 后端：FastAPI。
- 数据库：SQLite 起步，后续可迁移 Postgres。
- 证据存储：本地文件目录起步，后续抽象到对象存储。
- 任务调度：进程内 worker 起步，后续替换为 Celery、Temporal 或云任务系统。

## 4. 核心领域模型

### 4.1 Skill

代表一个可评测、可展示、可比较的 skill 逻辑实体。用户看到的主键语义是 `skill_name`。

字段：

```json
{
  "id": "skill_001",
  "skill_name": "analytical-report",
  "display_name": "Analytical Report",
  "description": "Generates metric narratives from spreadsheet inputs.",
  "category": "Data & Analytics",
  "source_type": "upload | github | registry",
  "source_url": "https://...",
  "status": "imported | evaluating | report_ready | review_required | archived",
  "latest_version_id": "skillver_001",
  "created_at": "2026-06-08T00:00:00Z",
  "updated_at": "2026-06-08T00:00:00Z"
}
```

约束：

- `skill_name` 在平台内唯一。
- `skill_name` 可以从 `SKILL.md` frontmatter `name` 解析并生成默认值，但用户必须能确认或修正。
- `category` 上传解析后由用户人工选择，系统可以推荐但不自动覆盖。

### 4.1.1 Skill Import Draft

Skill 上传不是一次性直接创建最终版本，而是两步式流程：

```text
上传 skill 包 / 选择 local_path
  -> 平台解析 SKILL.md、候选 skill root、文件树
  -> 生成 Skill Import Draft
  -> 用户确认或编辑 skill_name、display_name、category、version 等必填项
  -> 用户提交确认
  -> 创建/更新 Skill，并冻结为 Skill Version
  -> 导入完成，等待用户创建评测任务
```

Import Draft 字段：

```json
{
  "id": "import_001",
  "source_type": "zip | local_path",
  "source_name": "analytical-report.zip",
  "status": "parsed | needs_user_input | failed | confirmed",
  "detected_skill_roots": [
    {
      "root_path": "analytical-report/",
      "skill_md_path": "analytical-report/SKILL.md",
      "frontmatter": {
        "name": "analytical-report",
        "description": "Generates metric narratives."
      }
    }
  ],
  "selected_root_path": "analytical-report/",
  "suggested_skill_name": "analytical-report",
  "suggested_display_name": "analytical-report",
  "suggested_version": null,
  "file_tree": [],
  "warnings": [],
  "required_user_fields": ["version", "category"],
  "created_at": "2026-06-08T00:00:00Z"
}
```

解析规则：

- 不假设 zip 根目录就是 skill root。
- 扫描包内 `SKILL.md`，支持根目录、一级目录、`.codex/skills/*/SKILL.md`、`.claude/skills/*/SKILL.md` 等常见形态。
- 如果发现多个 `SKILL.md`，MVP 直接阻断导入并提示存在多个 `SKILL.md`，不符合单 Skill 包规范；用户需要整理包结构后重新上传。
- `skill_name` 默认来自 `SKILL.md` frontmatter `name`，如果缺失则用包含 `SKILL.md` 的目录名，再不行用 zip 文件名。
- `display_name` 默认等于 frontmatter `name` 原值。
- `version` 不能可靠依赖官方结构，必须由用户最终确认；系统可从 frontmatter `version`、`metadata.version` 或文件名中预填。
- 用户确认前不创建最终 `Skill Version`。

### 4.2 Skill Version

代表某个 Skill 的可复现包快照。

字段：

```json
{
  "id": "skillver_001",
  "skill_id": "skill_001",
  "version": "1.2.0",
  "manifest": {
    "name": "analytical-report",
    "description": "...",
    "allowed_tools": ["Read", "Python"]
  },
  "artifact_root": "data/uploads/skill_001/1.2.0/",
  "static_scan_status": "not_scanned | passed | warning | critical",
  "created_at": "2026-06-08T00:00:00Z"
}
```

约束：

- 所有评测运行绑定 `skill_version_id`，避免历史结论被后续文件变化污染。
- `static_scan_status` 是兼容历史数据的内部枚举；面向用户展示为 `Not scanned | No active findings | Findings | Critical risk`，Skill 整体只做评分、风险提示和推荐等级，不使用 pass/fail 语义。
- MVP 使用 `(skill_id, version)` 做唯一约束；如果同一个 Skill 下版本号已存在，确认导入时直接提示“该版本已存在”。
- Skill Version 一旦创建不可覆盖；若用户修改 version 或元信息，应创建新的确认流程或取消本次 Import Draft。
- hash 与完整 file tree 可作为后续增强或调试元信息，不作为 MVP 去重主链路。

### 4.3 Evaluation Set

代表某个 Skill 绑定的一组评测定义。MVP 中一个 Skill 维护一个 Evaluation Set，不做 Category 级 Evaluation Sets。

Evaluation Set 页面下分成两个独立维护区：

- Trigger Queries：维护 query 与 should_trigger，支持辅助生成、导入、新增、编辑、删除。
- Effect Cases：维护 id、prompt、expected_output、files 与 assertions，支持辅助生成、导入、新增、编辑、删除。

两类数据共享同一个 Evaluation Set 归属，但操作入口、导入格式、校验逻辑和保存接口保持独立；不提供“一次导入同时修改 Trigger Queries 与 Effect Cases”的默认主流程。

字段：

```json
{
  "id": "evalset_001",
  "skill_id": "skill_001",
  "name": "analytical-report current suite",
  "description": "Current skill-bound evaluation set.",
  "status": "draft | ready | archived",
  "created_at": "2026-06-08T00:00:00Z",
  "updated_at": "2026-06-08T00:00:00Z"
}
```

### 4.4 Trigger Query

Trigger Queries 用于判断 skill 该触发时是否触发、不该触发时是否保持安静。

最小结构：

```json
{
  "query": "帮我检查这个客服大模型评测集的质量",
  "should_trigger": true
}
```

数据库字段：

```json
{
  "id": "trq_001",
  "eval_set_id": "evalset_001",
  "query": "帮我检查这个客服大模型评测集的质量",
  "should_trigger": true,
  "created_at": "2026-06-08T00:00:00Z",
  "updated_at": "2026-06-08T00:00:00Z"
}
```

约束：

- `should_trigger=true` 表示正样本。
- `should_trigger=false` 表示负样本或 hard negative。
- hard negative 可以后续通过标签扩展，MVP 不强制。

### 4.5 Effect Case

Effect Cases 用于判断 skill 被使用后是否真的改善任务结果。

最小结构：

```json
{
  "id": "evalset-quality-check",
  "prompt": "检查 files/customer_service_evalset.xlsx 中的评测集质量，输出重复问题、缺失标准答案、类别分布不均衡的问题。",
  "expected_output": "应识别重复问题、缺失标准答案，以及部分意图类别样本过少的问题，并给出整改建议。",
  "files": ["files/customer_service_evalset.xlsx"],
  "assertions": [
    "contains '重复'",
    "contains '缺失'",
    "contains '类别'",
    "contains '整改'",
    "does not contain '无法读取'"
  ]
}
```

数据库字段：

```json
{
  "id": "effect_001",
  "eval_set_id": "evalset_001",
  "case_key": "evalset-quality-check",
  "prompt": "...",
  "expected_output": "...",
  "files": ["files/customer_service_evalset.xlsx"],
  "assertions": ["contains '重复'"],
  "created_at": "2026-06-08T00:00:00Z",
  "updated_at": "2026-06-08T00:00:00Z"
}
```

约束：

- `case_key` 在同一个 Evaluation Set 内唯一。
- `files` 路径相对当前 Evaluation Set 的文件目录。
- `assertions` 是两级判定机制，详见第 8 节。

### 4.6 Evaluation Task

代表一次用户创建的评测任务。

字段：

```json
{
  "id": "task_2481",
  "skill_id": "skill_001",
  "skill_version_id": "skillver_001",
  "eval_set_id": "evalset_001",
  "runner_environment_id": "runnerenv_claude_minimax",
  "task_scope": "full",
  "status": "queued | running | completed | failed | canceled",
  "created_by": "user_001",
  "created_at": "2026-06-08T00:00:00Z",
  "started_at": null,
  "finished_at": null
}
```

产品边界：

- 用户创建任务时不选择评测范围；MVP 固定为 Full Evaluation。
- 用户不选择 model 或 Judge Model；系统通过 Runner Environment 预置被测模型、裁判模型和评分逻辑。
- 任务运行中用户只需要看到任务状态，不展示阶段进度条；完成后展示各类结果和证据。

### 4.7 Evaluation Run

代表任务的一次实际执行。MVP 中一个 task 可以只有一个 run；后续 retry 会产生多个 run。

字段：

```json
{
  "id": "run_001",
  "task_id": "task_2481",
  "status": "queued | running | completed | failed | canceled",
  "current_stage": "static_scan | trigger_eval | effect_eval | done",
  "overall_score": null,
  "recommendation": "recommended | usable | review_required | not_recommended",
  "result_summary": {
    "scan_score": 98,
    "scan_status": "passed | warning | critical",
    "trigger_score": 94,
    "trigger_matched_queries": 18,
    "trigger_total_queries": 20,
    "effect_status": "pending"
  },
  "artifact_root": "data/runs/run_001/",
  "created_at": "2026-06-08T00:00:00Z",
  "started_at": "2026-06-08T00:03:00Z",
  "finished_at": "2026-06-08T00:20:00Z"
}
```

说明：

- `current_stage` 是 worker 内部调度字段，不在用户界面展示阶段进度。
- 用户界面只展示 task/run 的总体 `status`；完成后展示各类结果和证据。

### 4.8 Stage Result

代表单个评测阶段的结果。

```json
{
  "id": "stage_001",
  "run_id": "run_001",
  "stage": "static_scan",
  "status": "completed",
  "score": 98,
  "summary": "No critical risks.",
  "metrics": {
    "critical_count": 0,
    "warning_count": 1,
    "info_count": 2
  },
  "artifact_path": "static/findings.json"
}
```

### 4.9 Evaluation Summary

Summary 回答“这次评测发生了什么”，只解释结果，不提出具体修改动作。

```json
{
  "run_id": "run_001",
  "text": "该版本整体表现较好，主要问题集中在 hard negative 误触发和缺失文件场景下的输出稳定性。with-skill 相比 baseline 有明显提升，但在高噪声输入下 token 成本偏高。",
  "weak_metrics": ["scan", "trigger", "effect"],
  "risk_level": "low | medium | high",
  "created_at": "2026-06-08T00:20:00Z"
}
```

边界：

- Summary 可以进入任务详情顶部。
- Skill Detail Summary 读取当前版本最近一次完成任务的 summary 摘要。
- Summary 不等同于 Suggestion，不能替代可执行改法。

### 4.10 Finding

静态扫描或动态评测风险项。

```json
{
  "id": "finding_001",
  "run_id": "run_001",
  "stage": "static_scan",
  "code": "SEC-002",
  "severity": "critical | warning | info",
  "title": "External endpoint should be documented",
  "detail": "...",
  "file_path": "references/api.md",
  "line_number": 18,
  "fix": "Document why this endpoint is read-only and required."
}
```

### 4.11 Suggestion

Suggestion 回答“下一步应该怎么改”，必须是可执行建议。没有 `suggested_change` 和 `evidence_refs` 的内容只能叫 Summary 或 Finding，不能叫 Suggestion。

```json
{
  "id": "suggestion_001",
  "run_id": "run_001",
  "target": "skill_description | skill_instruction | evaluation_set | performance",
  "action": "narrow_trigger | add_case | update_assertion | constrain_output | reduce_tool_calls",
  "title": "收窄触发描述",
  "suggested_change": "在 SKILL.md description 中增加“仅当用户要求分析结构化数据文件或生成经营指标解读时触发”。",
  "why": "2 条 should_trigger=false 的查询误触发，说明当前触发描述覆盖过宽。",
  "evidence_refs": ["trigger.query_003", "trigger.query_004"],
  "created_at": "2026-06-08T00:20:00Z"
}
```

边界：

- Suggestion 只展示建议，不自动修改 Skill。
- Suggestion 不自动创建新的 Skill Version。
- Suggestion 不自动修改 Evaluation Set。
- Suggestion 由任务详情展示完整列表；Skill Detail Summary 只展示最近完成任务的 Top Suggestions。
- Evaluation Sets 和任务列表不展示 Suggestion。

### 4.12 Evidence

评测证据/运行产物。用户界面不用 Artifact 作为主词，但工程字段可以使用 `artifact_path`。

```json
{
  "id": "evidence_001",
  "run_id": "run_001",
  "type": "transcript | output | grading | metrics | timing | benchmark | report",
  "name": "grading.json",
  "path": "data/runs/run_001/effect/grading.json",
  "mime_type": "application/json",
  "size_bytes": 12345,
  "created_at": "2026-06-08T00:20:00Z"
}
```

## 5. 任务状态机

### 5.1 Task 状态

```text
queued -> running -> completed
                  -> failed
                  -> canceled
```

状态说明：

- `queued`：任务已创建，等待 worker 执行。
- `running`：worker 已领取任务。
- `completed`：所有目标阶段执行完成。
- `failed`：任务失败。MVP 暂不细化自动恢复。
- `canceled`：用户取消或系统取消。

### 5.2 Stage 状态

```text
pending -> running -> completed
                   -> failed
                   -> skipped
```

阶段顺序：

```text
static_scan
trigger_eval
effect_eval
```

MVP 决策：

- 即使 skill 存在安全风险，默认仍允许动态评测。
- 静态扫描风险不阻断 Trigger，但会影响 recommendation 和风险展示。
- Effect 未实现时展示 `pending`，不合并为单一总分。

### 5.3 Retry 设计

待讨论：

- MVP 是否支持 retry。
- retry 是整个 task 重跑，还是单个 stage 重跑。
- retry 产生新 run，还是覆盖原 run。

建议：

- MVP 支持整个 task 重跑，产生新 `EvaluationRun`。
- 不支持单阶段 retry。

## 6. Evaluation Set Schema

### 6.1 导入格式

建议支持一个 JSON 文件同时包含 trigger queries 与 effect cases：

```json
{
  "trigger_queries": [
    {
      "query": "帮我检查这个客服大模型评测集的质量",
      "should_trigger": true
    }
  ],
  "effect_cases": [
    {
      "id": "evalset-quality-check",
      "prompt": "检查 files/customer_service_evalset.xlsx 中的评测集质量...",
      "expected_output": "应识别重复问题、缺失标准答案...",
      "files": ["files/customer_service_evalset.xlsx"],
      "assertions": ["contains '重复'"]
    }
  ]
}
```

也可以兼容单独数组导入：

- Trigger Queries 数组。
- Effect Cases 数组。

### 6.2 校验规则

Trigger Query：

- `query` 必填，非空字符串。
- `should_trigger` 必填，boolean。

Effect Case：

- `id` 必填，Evaluation Set 内唯一。
- `prompt` 必填，非空字符串。
- `expected_output` 必填，非空字符串。
- `files` 必填，字符串数组，可为空数组。
- `assertions` 必填，字符串数组，至少一条。

文件校验：

- `files` 路径必须是相对路径。
- 不允许 `..` 跳出 Evaluation Set 文件目录。
- 导入时检查文件是否存在；缺失文件给出 warning 或 error 待讨论。

## 7. Runner 抽象

Runner 负责把同一套评测输入交给不同 agent 或模型运行，并返回统一结果。

产品层用户感知的是“运行环境 Runner”，而不是分开的 runner 和 model。一个 Runner Environment 是平台预置组合，包含：

- 执行器类型，例如 OpenCode CLI、Claude Code、Codex Runner、本地 CLI、API Runner。
- 被测模型，例如 `openai/gpt-5.3-codex-spark`、MiniMax 2.7、GPT-5、Qwen3 Coder。
- 运行参数，例如 timeout、workspace、tool permissions。

因此创建任务时只展示 Runner Environment，例如 `OpenCode + GPT-5.3 Codex Spark`。Runner 只负责被测 agent/model 的真实执行，不再承载 Effect Judge 的模型选择。

### 7.0 Model API 与模型角色

系统设置维护独立的第三方模型 API 配置：

- `Model API Provider`：保存 provider name、接口格式、base_url、api_key、enabled。接口格式支持 `openai_compatible` 与 `anthropic`。
- `Model Profile`：保存 provider 下的具体模型，例如 `deepseek-chat`、`deepseek-reasoner`。
- `Model Roles`：保存全局裁判模型与数据模型选择。

Effect 的 LLM Judge 使用全局裁判模型。后续 AI 辅助生成 Trigger Queries / Effect Cases 时使用全局数据模型。API Key 本地 MVP 保存到 SQLite，但后端 API 不回显明文，只返回是否已配置与掩码。

### 7.1 Runner 输入

```json
{
  "run_id": "run_001",
  "mode": "with_skill | without_skill | trigger",
  "skill_version": {
    "id": "skillver_001",
    "artifact_root": "data/uploads/skill_001/1.2.0/"
  },
  "prompt": "检查 files/customer_service_evalset.xlsx 中的评测集质量...",
  "files": ["data/eval_sets/evalset_001/files/customer_service_evalset.xlsx"],
  "workspace_dir": "data/runs/run_001/workspaces/case_001/with_skill/",
  "runner_environment": "OpenCode + GPT-5.3 Codex Spark",
  "timeout_seconds": 120
}
```

### 7.2 Runner 输出

```json
{
  "status": "completed | failed | timeout",
  "text": "实际输出文本",
  "raw_output_path": "effect/outputs/case_001_with.txt",
  "transcript_path": "effect/transcripts/case_001_with.md",
  "tool_calls": [
    {
      "name": "Read",
      "input": {"file": "customer_service_evalset.xlsx"}
    }
  ],
  "usage": {
    "input_tokens": 12000,
    "output_tokens": 2400,
    "total_tokens": 14400
  },
  "timing": {
    "started_at": "2026-06-08T00:03:00Z",
    "finished_at": "2026-06-08T00:04:00Z",
    "elapsed_ms": 60000
  },
  "error": null
}
```

### 7.3 Runner Environment 类型

MVP 已选：

- `opencode_cli + openai/gpt-5.3-codex-spark`：调用本机 OpenCode CLI 执行真实 trigger 评测。

后续可扩展：

- `local_cli + configured_model`：调用本地命令。
- `claude_code + configured_model`：Claude Code 组合。
- `api_runner + configured_model`：通用模型 API 组合。

## 8. Assertion Engine 与 LLM Judge

### 8.1 Assertions 两级判定机制

`assertions` 是两级判定机制：

1. 先走确定性规则匹配。
2. 确定性规则识别不了或语义判断不足时，再交给 LLM Judge。

确定性规则示例：

```text
contains '重复'
does not contain '无法读取'
matches regex '通过率[:：]\\s*\\d+%'
is valid JSON
json path '$.status' equals 'passed'
has at least 3 lines
```

确定性规则输出：

```json
{
  "assertion": "contains '重复'",
  "type": "contains",
  "decision_source": "deterministic",
  "passed": true,
  "score": 1,
  "evidence": "输出中包含“重复”。"
}
```

### 8.2 LLM Judge 触发条件

以下情况交给 LLM Judge：

- assertion 无法被确定性 parser 识别。
- assertion 是语义描述，例如“应给出整改建议”。
- 确定性规则结果为 inconclusive。
- 需要结合 `expected_output` 与实际输出做语义判断。

LLM Judge 输入：

```json
{
  "case_id": "evalset-quality-check",
  "prompt": "...",
  "expected_output": "...",
  "actual_output": "...",
  "assertion": "应给出整改建议",
  "rubric": "判断 actual_output 是否针对发现的问题提出可执行整改建议。"
}
```

LLM Judge 输出：

```json
{
  "assertion": "应给出整改建议",
  "decision_source": "llm_judge",
  "passed": true,
  "score": 0.9,
  "reasoning": "输出中列出了去重、补齐标准答案、补齐类别样本三类整改动作。",
  "evidence": ["去重", "补齐标准答案", "增加少样本意图类别"]
}
```

### 8.3 Grading Result

每个 case 的 grading 结果：

```json
{
  "case_id": "evalset-quality-check",
  "mode": "with_skill",
  "assertion_results": [
    {
      "assertion": "contains '重复'",
      "decision_source": "deterministic",
      "passed": true,
      "score": 1
    }
  ],
  "pass_rate": 0.8,
  "score": 80,
  "raw_output_path": "effect/outputs/evalset-quality-check_with.txt"
}
```

## 9. 三类指标设计

### 9.1 静态扫描

目标：

- 判断 skill 包是否安全、完整、可维护、可评测。

输入：

- Skill Version 文件树。
- `SKILL.md` frontmatter。
- scripts、references、assets、agents 等目录。

输出：

- `findings.json`
- `static_metrics.json`
- `scan_score`

规则分组：

- Structure
- Security
- Permissions
- Supply chain
- Prompt safety

MVP 评分：

```text
static_score = clamp(
  100
  - critical_count * 25
  - major_count * 10
  - minor_count * 3
  - info_count * 1,
  0,
  100
)
```

MVP 决策：

- 真实规则引擎只在评测任务的 `static_scan` 阶段运行，上传导入阶段不阻断。
- 命中 critical finding 不阻断后续动态评测，但 recommendation 最高降为 `review_required`。
- 规则明细、severity 归一、artifact 格式和评分口径见 [static-scan-rules-design.md](static-scan-rules-design.md)。
- MVP 不提供 ignore / allowlist / 规则开关。

### 9.2 触发评测

目标：

- 判断 skill 是否在该触发时触发、不该触发时不触发。

输入：

- Trigger Queries。
- Skill Version。
- Runner。

执行：

- 每条 query 运行 N 次。
- 根据 runner transcript、tool calls、skill activation signal 判断是否触发。

输出：

```json
{
  "total_queries": 4,
  "passed": 4,
  "failed": 0,
  "trigger_precision": 1.0,
  "no_trigger_precision": 1.0,
  "query_results": [
    {
      "query": "...",
      "should_trigger": true,
      "trigger_count": 3,
      "run_count": 3,
      "trigger_rate": 1.0,
      "passed": true
    }
  ]
}
```

MVP 规则：

- `should_trigger=true`：`trigger_rate >= 0.5` 视为通过。
- `should_trigger=false`：`trigger_rate < 0.5` 视为通过。

待讨论：

- trigger signal 如何识别。
- positive / negative / hard negative 是否用标签扩展。

### 9.3 效果评测

目标：

- 判断使用 skill 后任务结果是否更好，并解释这份提升是否值得成本。
- `expected_output` 是目标说明；`assertions` 是自动化判定单元。

执行：

每个 Effect Case 默认运行两组：

```text
with_skill
without_skill
```

流程：

1. 准备隔离 workspace。
2. 拷贝 case files。
3. 用 skill 运行 prompt。
4. 不用 skill 运行同一 prompt。
5. 对两组输出分别执行 assertions 分层判定。
6. 聚合 pass_rate、score、lift、成本效率分类。

Assertion 判定：

- `deterministic`：内置 DSL 可直接判定，例如 `contains`、`does not contain`、`matches regex`、`is valid json`、`file exists`、`file contains`、`tool called`、`skill invoked`。
- `llm_judge`：确定性规则无法判定，或 assertion 明确使用 `judge:` 前缀时，交给系统设置里的全局裁判模型。
- `hybrid`：同一 case 中可混合 deterministic 与 LLM Judge。
- MVP 不执行用户上传的任意 Python/script assertion。

输出：

```json
{
  "case_id": "evalset-quality-check",
  "with_skill": {
    "pass_rate": 1.0,
    "assertion_results": [
      {
        "text": "contains \"valid\"",
        "passed": true,
        "method": "deterministic",
        "evidence": "Substring found: 'valid'",
        "confidence": 1.0,
        "uncertain": false
      }
    ]
  },
  "without_skill": {
    "pass_rate": 0.67
  },
  "delta_pass_rate": 0.33,
  "non_discriminating_assertions": [],
  "regression_assertions": []
}
```

核心指标：

- `with_skill_pass_rate`
- `without_skill_pass_rate`
- `skill_lift`
- `assertions_passed`
- `assertions_total`
- `deterministic_assertions`
- `judge_assertions`
- `uncertain_assertions`
- `non_discriminating_assertions`
- `regression_assertions`

### 9.4 Effect 成本效率子指标

目标：

- 判断效果提升是否值得成本。该能力归入 Effect，不再作为独立一级指标。

指标：

- latency
- input_tokens
- output_tokens
- total_tokens
- tool_calls
- estimated_cost
- tokens_per_passed_assertion
- quality_delta
- cost_delta_pct
- cost_efficiency_classification

输出：

```json
{
  "mean_latency_ms": 48000,
  "mean_total_tokens": 18400,
  "mean_tool_calls": 5.2,
  "estimated_cost_usd": 1.42,
  "tokens_per_passed_assertion": 612,
  "cost_efficiency_classification": "PARETO_BETTER | QUALITY_UP_COST_UP | QUALITY_UP_COST_NEUTRAL | PARETO_WORSE | NO_MEANINGFUL_DELTA"
}
```

## 10. 推荐策略

MVP 不再追求单一 `overall_score`。新任务保留 `overall_score = null` 作为 legacy 兼容字段，前端和榜单使用 Scan / Trigger / Effect 三类指标。

三类指标：

- Scan：结构、安全、权限和可维护性风险。
- Trigger：真实 OpenCode 触发评测的 matched expectations。
- Effect：真实 with-skill / baseline 效果评测，包含 assertion 判定、Judge 裁决和成本效率证据。

推荐等级：

```text
Recommended: Scan 无 critical，Trigger >= 80，Effect >= 80，skill_lift > 0，且不是 PARETO_WORSE
Usable: Scan 无 critical，Trigger >= 80，Effect >= 60
Review Required: Scan warning/critical，Trigger 50-79，Effect 50-79，Judge uncertain 过多，或无 Effect Cases
Not Recommended: 无 Trigger Queries，Trigger < 50，Effect < 50，运行失败，或 with-skill 明显劣于 baseline
```

MVP 决策：

- 任一 critical finding 会把最高 recommendation 限制为 `review_required`，但不阻断 Trigger。
- 新任务仍写 `overall_score = null`，不把 Scan / Trigger / Effect 合并为单一分。

## 11. 证据存储

建议目录：

```text
data/
  uploads/
    {skill_id}/
      {version}/
        skill/
        manifest.json
        file_tree.json
  eval_sets/
    {eval_set_id}/
      files/
      eval_set.json
  runs/
    {run_id}/
      report.json
      report.md
      static/
        findings.json
        static_metrics.json
      trigger/
        trigger_report.json
        transcripts/
        outputs/
      effect/
        benchmark.json
        grading.json
        outputs/
        transcripts/
        workspaces/
      performance/
        metrics.json
        timing.json
      evidence_manifest.json
```

`evidence_manifest.json`：

```json
{
  "run_id": "run_001",
  "items": [
    {
      "type": "grading",
      "name": "grading.json",
      "path": "effect/grading.json",
      "mime_type": "application/json"
    }
  ]
}
```

## 12. API 合约 v0.1

### 12.1 Skills

```text
GET    /api/skills
POST   /api/skills
GET    /api/skills/{skill_id}
PATCH  /api/skills/{skill_id}
DELETE /api/skills/{skill_id}
```

创建 Skill：

```json
{
  "skill_name": "analytical-report",
  "display_name": "Analytical Report",
  "category": "Data & Analytics",
  "description": "..."
}
```

### 12.2 Skill Versions

```text
GET  /api/skills/{skill_id}/versions
POST /api/skills/{skill_id}/versions
GET  /api/skill-versions/{version_id}
```

MVP 更推荐把上传解析与版本确认拆成两个 API：

```text
POST /api/skill-imports
GET  /api/skill-imports/{import_id}
POST /api/skill-imports/{import_id}/confirm
```

`POST /api/skill-imports` 用于上传 zip 或提交 local_path，并只做解析：

```json
{
  "source_type": "zip | local_path",
  "local_path": "D:/skills/analytical-report"
}
```

响应：

```json
{
  "import_id": "import_001",
  "status": "needs_user_input",
  "detected_skill_roots": [
    {
      "root_path": "analytical-report/",
      "skill_md_path": "analytical-report/SKILL.md",
      "frontmatter": {
        "name": "analytical-report",
        "description": "Generates metric narratives."
      }
    }
  ],
  "suggested_skill_name": "analytical-report",
  "suggested_display_name": "analytical-report",
  "suggested_version": null,
  "required_user_fields": ["version", "category"],
  "warnings": []
}
```

如果包内发现多个 `SKILL.md`，解析直接失败：

```json
{
  "import_id": "import_001",
  "status": "failed",
  "blocking_errors": [
    {
      "code": "MULTIPLE_SKILL_MD",
      "message": "包内存在多个 SKILL.md，不符合单 Skill 包规范，请整理后重新上传。",
      "paths": [
        "skill-a/SKILL.md",
        "skill-b/SKILL.md"
      ]
    }
  ]
}
```

`POST /api/skill-imports/{import_id}/confirm` 用于用户确认必填项后创建 Skill / Skill Version：

```json
{
  "selected_root_path": "analytical-report/",
  "skill_name": "analytical-report",
  "display_name": "Analytical Report",
  "category": "Data & Analytics",
  "version": "1.2.0"
}
```

确认成功响应：

```json
{
  "skill_id": "skill_001",
  "skill_version_id": "skillver_001",
  "status": "imported",
  "next_actions": [
    "prepare_evaluation_set",
    "create_evaluation_task"
  ]
}
```

待讨论：

- 上传用 multipart 还是先用本地路径模拟。
- GitHub URL 导入后置，MVP 不进入主链路。

### 12.3 Evaluation Sets

```text
GET   /api/skills/{skill_id}/evaluation-set
PATCH /api/evaluation-sets/{eval_set_id}
```

### 12.4 Trigger Queries

```text
GET    /api/evaluation-sets/{eval_set_id}/trigger-queries
POST   /api/evaluation-sets/{eval_set_id}/trigger-queries
POST   /api/evaluation-sets/{eval_set_id}/trigger-queries/import
POST   /api/evaluation-sets/{eval_set_id}/trigger-queries/generate
PATCH  /api/trigger-queries/{trigger_query_id}
DELETE /api/trigger-queries/{trigger_query_id}
```

### 12.5 Effect Cases

```text
GET    /api/evaluation-sets/{eval_set_id}/effect-cases
POST   /api/evaluation-sets/{eval_set_id}/effect-cases
POST   /api/evaluation-sets/{eval_set_id}/effect-cases/import
POST   /api/evaluation-sets/{eval_set_id}/effect-cases/generate
PATCH  /api/effect-cases/{effect_case_id}
DELETE /api/effect-cases/{effect_case_id}
```

### 12.6 Tasks and Runs

```text
GET  /api/evaluation-tasks
POST /api/evaluation-tasks
GET  /api/evaluation-tasks/{task_id}
GET  /api/evaluation-runs/{run_id}
POST /api/evaluation-tasks/{task_id}/cancel
POST /api/evaluation-tasks/{task_id}/retry
```

创建任务：

```json
{
  "skill_id": "skill_001",
  "skill_version_id": "skillver_001",
  "runner_environment_id": "runnerenv_claude_minimax"
}
```

后端根据 `skill_id` 自动绑定当前 Skill 的 current Evaluation Set；用户不在创建任务时选择或传入其他评测集。

### 12.7 Evidence

```text
GET /api/evaluation-runs/{run_id}/evidence
GET /api/evidence/{evidence_id}
GET /api/evaluation-runs/{run_id}/download
```

## 13. 数据库表草案

```text
skills
skill_versions
evaluation_sets
trigger_queries
effect_cases
evaluation_tasks
evaluation_runs
stage_results
evaluation_summaries
findings
suggestions
metrics
evidence_items
```

待讨论：

- `metrics` 是否独立表，还是直接存在 stage result JSON。
- `files` 与 `assertions` 是否使用 JSON 字段。
- SQLite 时 JSON 查询能力是否足够。

## 14. 安全与隔离

MVP 需要考虑：

- 上传文件路径隔离。
- Evaluation Set files 禁止路径穿越。
- Runner workspace 每次运行独立目录。
- without-skill workspace 不允许看到 skill 文件。
- 日志和 transcript 中的 secrets 脱敏。
- 静态扫描不阻断动态评测，但风险必须显著展示。

待讨论：

- 是否需要沙箱运行 skill scripts。
- 本地 CLI runner 是否允许执行任意命令。
- 企业环境下如何配置 allowlist。

## 15. 可观测性

每个 run 至少记录：

- task_id
- run_id
- stage
- status
- started_at
- finished_at
- elapsed_ms
- error_code
- error_message

日志建议：

```text
data/runs/{run_id}/logs/worker.log
data/runs/{run_id}/logs/runner.log
data/runs/{run_id}/logs/judge.log
```

MVP 暂不设计复杂系统失败处理，但需要保留错误字段，便于后续补齐。

## 16. 前端页面与数据映射

### 16.1 Overview

依赖：

- `/api/overview`
- `/api/leaderboard?category=Data%20%26%20Analytics`

展示：

- Skills 总数
- 已评测 Skills 数
- 评测任务数量
- 用户数量
- Recommended Skills by Category

### 16.2 Skills 管理

依赖：

- `/api/skills`
- `/api/skills/{skill_id}`

展示：

- Skill 卡片
- Scan / Trigger / Effect 三类指标
- latest version
- category
- status
- updated time

### 16.3 Skill Detail Summary

依赖：

- `/api/skills/{skill_id}`
- `/api/skills/{skill_id}/versions`
- `/api/skills/{skill_id}/latest-result`

展示：

- 版本评测结果
- 最新 suggestion
- Scan / Trigger / Effect 三类指标
- 风险摘要
- 评测证据摘要

### 16.4 Evaluation Sets

依赖：

- `/api/skills/{skill_id}/evaluation-set`
- `/api/evaluation-sets/{eval_set_id}/trigger-queries`
- `/api/evaluation-sets/{eval_set_id}/effect-cases`

展示：

- AWS 静态扫描规则数量，只读。
- Trigger Queries：`query`、`should_trigger`，独立支持辅助生成、导入、新增、编辑、删除。
- Effect Cases：`id`、`prompt`、`expected_output`、`files`、`assertions`，独立支持辅助生成、导入、新增、编辑、删除。

### 16.5 评测任务管理

依赖：

- `/api/evaluation-tasks`
- `/api/evaluation-tasks` POST

展示：

- 任务队列
- 任务状态
- 运行环境 Runner
- 新建任务

新建任务表单：

- `Skill`
- `Skill Version`
- `Evaluation Set`：只读展示当前 Skill 绑定的 suite。
- `Runner`：选择平台预置 Runner Environment。

不展示：

- 评测范围；系统固定 Full Evaluation。
- Model；已包含在 Runner Environment 中。
- Judge Model；系统预置。
- 阶段进度；任务只展示状态。

### 16.6 任务详情

依赖：

- `/api/evaluation-tasks/{task_id}`
- `/api/evaluation-runs/{run_id}`
- `/api/evaluation-runs/{run_id}/evidence`

展示：

- 任务状态
- 完成后的评估方法与结果
- static findings
- trigger results
- effect with/without results
- performance metrics
- evidence items

## 17. AI Coding 开发切分建议

### Phase 0：工程骨架

- FastAPI 后端。
- React / Vite 前端。
- SQLite。
- 本地文件存储目录。
- 基础配置文件。
- health check 与 DB migration 跑通。
- 目录结构按后续服务器部署和容器化预留。

### Phase 1：Skill 管理闭环

- Skill 列表和卡片管理。
- 上传/导入 draft。
- 解析单个 `SKILL.md`。
- 用户确认 `skill_name`、`version`、`category`。
- `(skill_id, version)` 唯一校验。
- 多个 `SKILL.md` 阻断。
- 不做扫描。

### Phase 2：Evaluation Set 管理

- 一个 Skill 自动维护一个 current Evaluation Set。
- Trigger Queries CRUD。
- Trigger Queries JSON 导入。
- Effect Cases CRUD。
- Effect Cases JSON 导入。
- AWS 静态扫描规则数量只读展示。
- 辅助生成接口先 mock 返回草稿。
- 不跑评测。

### Phase 3：评测任务管理与 Mock Worker

- 新建任务：只选 Skill、Version、Runner Environment。
- 自动绑定 current Evaluation Set。
- 固定 Full Evaluation。
- 任务队列。
- 任务详情报告页。
- Summary / Finding / Suggestion / Evidence 结构落库。
- Mock Worker 生成完整任务结果。

### Phase 4：真实评测 Worker

- Static Scanner。
- Trigger Evaluator。
- Effect Evaluator with/without。
- Performance Aggregator。
- Evidence Manifest。
- 状态从 queued -> running -> completed / failed。

### Phase 5：LLM Judge

- Judge adapter。
- judge prompt。
- judge result schema。
- deterministic -> LLM fallback。
- judge evidence 保存。
- Summary / Suggestion 基于结构化 facts 生成。
- Suggestion 必须有 `suggested_change` 和 `evidence_refs`。

### Phase 6：榜单与推荐

- overall score 聚合。
- recommendation。
- latest result 写回 Skill Summary。
- Overview leaderboard。

## 18. 剩余待细化清单

以下不是产品方向问题，而是 AICoding 开发前后需要继续细化的实现细节：

1. Skill 导入确认页的错误展示：字段级错误、包级错误、重复版本提示如何呈现。
2. Skill Version 已存在时是否提供跳转到已有版本详情。
3. Effect Case files 缺失时是 warning 还是 error。
4. assertions 确定性语法第一版支持哪些：contains、does not contain、regex、JSON schema、结构字段检查的优先级。
5. LLM Judge 的默认 rubric 与 prompt 模板。
6. LLM Judge 结果是否缓存，重跑时是否复用。
7. effect_eval 的第一版断言执行和 LLM Judge 如何落地。
8. Effect 效率子指标的 token、耗时、成本如何从 runner telemetry 采集。
9. static scanner 第一版系统预置规则范围。
10. retry 是否进入 MVP；如果进入，retry 与原 task/run 的关系。
11. API 错误码规范。
12. Docker 化部署是否进入第一版交付，还是只提供服务器手工部署说明。

## 19. 当前已确认决策

- 视觉与交互方向收敛为 Product Cloud。
- Evaluation Sets 归属 Skill Detail，不做一级菜单。
- 每个 Skill 维护一个 Evaluation Set。
- Evaluation Sets 下的 Trigger Queries 与 Effect Cases 分开独立维护，分别支持辅助生成、导入、新增、编辑、删除。
- Evaluation Sets 不提供默认的混合导入入口，避免一次操作同时改动 Trigger Queries 与 Effect Cases。
- Evaluation Sets 不做启用/禁用和版本发布。
- Evaluation Sets 不展示 suggestion。
- Suggestion 属于评测运行结果，由 Skill Detail Summary 展示。
- Skill Detail Summary 不重复展示 Evaluation Sets。
- Skill Detail 的版本评测结果暂不下钻。
- 评测任务管理是独立一级菜单。
- 评测任务管理需要新建任务流程。
- 新建评测任务不让用户选择评测范围，系统固定 Full Evaluation。
- Runner 与 model 在产品层合并为运行环境 Runner，例如 `Claude Code + MiniMax 2.7`。
- Judge Model 与评分逻辑由系统预置，不暴露给用户选择。
- 任务运行中只展示状态，不展示阶段进度。
- 任务列表不展示报告摘要。
- 任务详情承载核心评估方法和证据。
- 即使存在安全风险，平台默认仍允许动态评测。
- LLM Judge 结果可以进入榜单。
- MVP 暂不展示人工复核状态。
- MVP 暂不展示 confidence。
- `assertions` 采用两级判定：先确定性规则匹配，识别不了再交给 LLM Judge。
- Skill 导入采用两步式流程：上传后先解析生成 Import Draft，用户确认或编辑 `skill_name`、`display_name`、`category`、`version` 后再创建 Skill Version。
- `skill_name` 可从 `SKILL.md` frontmatter `name` 预填，但用户可以修正。
- `version` 必须由用户填写或确认，不能假设官方结构一定提供。
- MVP 使用 `(skill_id, version)` 作为 Skill Version 唯一约束；重复时提示版本已存在，不创建新版本。
- hash 与完整 file tree 后置为增强能力，不作为 MVP 去重主链路。
