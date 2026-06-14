# 领域模型与 API 详细设计

## 1. 文档目标

本文描述 SkillsEval 当前真实系统中的领域对象、SQLite 表、API 分组、文件产物和前端数据映射。

本文关注“数据怎么存、接口怎么用、对象之间怎么关联”。评测流程和规则请分别阅读：

- `evaluation-design.md`
- `static-scan-rules-design.md`
- `effect-eval-design.md`

## 2. 存储设计

当前系统使用本地 SQLite 和本地文件系统。

默认路径：

```text
data/skilleval.db
data/imports/
data/uploads/
data/runs/
data/workspaces/
```

目录职责：

| 路径 | 说明 |
| --- | --- |
| `data/skilleval.db` | 主数据库 |
| `data/imports/` | ZIP 上传后的临时 Import Draft 解压目录 |
| `data/uploads/` | 确认导入后的 Skill Version artifact |
| `data/runs/` | Evaluation Run 产物 |
| `data/workspaces/` | Runner 执行 workspace |

JSON 字段以 TEXT 存储，由 `db.encode_json` 和 `db.decode_json` 处理。

## 3. 核心对象关系

```text
Skill 1 --- N SkillVersion
Skill 1 --- 1 EvaluationSet
EvaluationSet 1 --- N TriggerQuery
EvaluationSet 1 --- N EffectCase
EvaluationSet 1 --- N EvaluationSetGenerationJob

EvaluationTask N --- 1 Skill
EvaluationTask N --- 1 SkillVersion
EvaluationTask N --- 1 EvaluationSet
EvaluationTask N --- 1 RunnerEnvironment

EvaluationTask 1 --- N EvaluationRun
EvaluationRun 1 --- N StageResult
EvaluationRun 1 --- N EvidenceItem
EvaluationRun 1 --- N Finding
```

当前 UX 中，一个 Skill 只有一个绑定的当前 Evaluation Set。未来如果支持多套评测集，可以在 `evaluation_sets` 上增加 scope/version/display_name 维度。

## 4. Settings 相关表

### 4.1 `categories`

用途：

- 管理 Skill 上传时可选分类。
- Overview 默认按 category 展示推荐榜单。

关键字段：

| 字段 | 说明 |
| --- | --- |
| `id` | 分类 ID |
| `name` | 分类名，唯一 |
| `description` | 分类说明 |
| `enabled` | 是否可用于新上传 |
| `created_at` | 创建时间 |

删除策略：

- 未被 Skill 引用：可硬删。
- 已被 Skill 引用：改为 `enabled = 0`。

### 4.2 `runner_environments`

用途：

- 管理被测运行环境。
- 创建评测任务时从 enabled Runner 中选择。

关键字段：

| 字段 | 说明 |
| --- | --- |
| `id` | Runner ID |
| `name` | 展示名称 |
| `runner_type` | Runner 类型，当前实现 `opencode_cli` |
| `model_name` | 被测模型名称，由 Runner 使用 |
| `judge_model` | legacy 字段，当前不再使用 |
| `command_path` | 本地命令路径 |
| `timeout_seconds` | 单次执行超时时间 |
| `enabled` | 是否可用于新任务 |
| `created_at` | 创建时间 |

边界：

- Runner model 是被测模型。
- Effect Judge 不读取 `model_name`。
- `judge_model` 字段仅保留历史兼容。

删除策略：

- 统一软删除，即 `enabled = 0`。

### 4.3 `model_api_providers`

用途：

- 存储模型 API 连接信息。
- 后端内部仍以 provider + model 两张表存储。

关键字段：

| 字段 | 说明 |
| --- | --- |
| `id` | Provider ID |
| `name` | Provider 名称，当前由前端按 `model @ base_url` 派生 |
| `provider_type` | `openai_compatible` 或 `anthropic` |
| `base_url` | 模型 API base URL |
| `api_key` | API Key，MVP 明文存 SQLite，不对前端回显 |
| `enabled` | 是否启用 |
| `created_at` / `updated_at` | 时间戳 |

前端展示：

- 不以 Provider 为核心。
- 用户只看到模型配置卡片。

### 4.4 `model_api_models`

用途：

- 存储具体模型配置。

关键字段：

| 字段 | 说明 |
| --- | --- |
| `id` | Model Profile ID |
| `provider_id` | 所属 Provider |
| `display_name` | 展示名，当前与 model_id 保持一致 |
| `model_id` | API 调用中的模型名 |
| `enabled` | 是否启用 |
| `created_at` / `updated_at` | 时间戳 |

唯一性：

- 当前按 `model_id + provider.base_url` 判断是否重复。

### 4.5 `model_role_settings`

用途：

- 管理全局模型角色。

角色：

| role | 用途 |
| --- | --- |
| `judge` | Effect LLM Judge |
| `data` | 后续 AI 辅助生成评测数据 |

当前使用：

- `judge` 已接入 Effect。
- `data` 已接入 Evaluation Set 的 Trigger Queries / Effect Cases AI 辅助生成。

### 4.6 `scoring_weights`

用途：

- legacy 兼容。

当前状态：

- 表和接口仍保留。
- 新任务不读取权重。
- Settings 页面展示 Assessment Policy，不再提供权重编辑主入口。

## 5. Skill 相关表

### 5.1 `skills`

用途：

- 表示一个逻辑 Skill。
- 唯一身份按 `skill_name`。

关键字段：

| 字段 | 说明 |
| --- | --- |
| `id` | Skill ID |
| `skill_name` | 包名/唯一名 |
| `display_name` | 平台展示名 |
| `description` | 平台描述 |
| `card_content` | Skill Cards 富文本内容 |
| `category` | 分类文本 |
| `status` | 当前状态 |
| `latest_version_id` | 最新版本 |
| `latest_task_id` | 最近任务 |
| `recommendation` | 最新推荐标签 |
| `created_at` / `updated_at` | 时间戳 |

说明：

- `display_name`、`description`、`category`、`card_content` 是平台元信息。
- 修改这些字段不会修改上传 artifact 中的 `SKILL.md`。

### 5.2 `skill_versions`

用途：

- 表示 Skill 的一个版本 artifact。

关键字段：

| 字段 | 说明 |
| --- | --- |
| `id` | Skill Version ID |
| `skill_id` | 所属 Skill |
| `version` | 用户填写版本号 |
| `manifest` | 导入阶段元数据 |
| `artifact_root` | 本地 artifact 目录 |
| `static_scan_status` | 最近静态扫描状态 |
| `source_name` | 上传文件名或来源 |
| `created_at` | 创建时间 |

唯一性：

- 同一 Skill 下 `version` 不允许重复。
- 用户侧表现为 `skill_name + version` 不允许重复导入。

### 5.3 `skill_import_drafts`

用途：

- 保存上传 ZIP 后、确认导入前的临时草稿。

关键字段：

| 字段 | 说明 |
| --- | --- |
| `id` | Draft ID |
| `source_name` | ZIP 文件名 |
| `extract_root` | 解压目录 |
| `skill_md_path` | 命中的 SKILL.md 路径 |
| `derived_skill_name` | 解析或推导出的 skill_name |
| `manifest` | 解析元数据 |
| `created_at` | 创建时间 |

生命周期：

```text
ZIP 上传 -> Import Draft -> 用户确认 -> Skill/SkillVersion
```

## 6. Evaluation Set 相关表

### 6.1 `evaluation_sets`

用途：

- Skill 绑定的评测集容器。

关键字段：

| 字段 | 说明 |
| --- | --- |
| `id` | Evaluation Set ID |
| `skill_id` | 所属 Skill |
| `name` | 名称 |
| `created_at` / `updated_at` | 时间戳 |

当前策略：

- 每个 Skill 默认创建一个 Evaluation Set。
- 前端不提供单独一级菜单。
- 在 Skill Detail 的 Evaluation Set tab 维护。

### 6.2 `trigger_queries`

用途：

- 触发评测数据。

字段：

| 字段 | 说明 |
| --- | --- |
| `id` | Query ID |
| `eval_set_id` | 所属 Evaluation Set |
| `query` | 输入文本 |
| `should_trigger` | 是否应该触发 |
| `created_at` | 创建时间 |

### 6.3 `effect_cases`

用途：

- 效果评测数据。

字段：

| 字段 | 说明 |
| --- | --- |
| `id` | Case ID |
| `eval_set_id` | 所属 Evaluation Set |
| `case_key` | 稳定可读 key |
| `prompt` | Runner 输入 |
| `expected_output` | 目标描述 |
| `files` | JSON list，输入文件 |
| `assertions` | JSON list，判定规则 |
| `created_at` | 创建时间 |

### 6.4 `evaluation_set_generation_jobs`

用途：

- 保存 AI 辅助生成 Trigger Queries / Effect Cases 的后台任务与草稿。
- 支持用户关闭页面后恢复查看生成进度或已完成草稿。
- 草稿不会自动进入正式 Evaluation Set，必须由用户确认入库。

字段：

| 字段 | 说明 |
| --- | --- |
| `id` | Generation Job ID |
| `skill_id` | 所属 Skill |
| `eval_set_id` | 所属 Evaluation Set |
| `target` | `trigger_queries` 或 `effect_cases` |
| `status` | queued/running/completed/failed/confirmed |
| `progress_message` | 当前进度提示 |
| `request_payload` | JSON，请求参数，包括 count、instruction、include_negative |
| `draft_items` | JSON，生成草稿列表 |
| `error` | 失败原因 |
| `created_at` / `updated_at` / `completed_at` | 时间戳 |

生命周期：

```text
用户点击 AI 生成
  -> 创建 generation job
  -> 后台调用 data model
  -> 生成 draft_items
  -> 用户审核、编辑、勾选
  -> confirm 写入 trigger_queries 或 effect_cases
  -> job.status = confirmed
```

草稿语义：

- `selected = true`：默认会被确认入库。
- `duplicate = true`：与已有数据或本批草稿重复，默认不选中。
- Trigger 草稿包含 `query`、`should_trigger`、`rationale`。
- Effect 草稿包含 `case_key`、`prompt`、`expected_output`、`assertions`、`rationale`。

## 7. Evaluation Run 相关表

### 7.1 `evaluation_tasks`

用途：

- 用户创建的评测任务。

字段：

| 字段 | 说明 |
| --- | --- |
| `id` | Task ID |
| `skill_id` | 被测 Skill |
| `skill_version_id` | 被测版本 |
| `eval_set_id` | 绑定评测集 |
| `runner_environment_id` | 被测 Runner |
| `task_scope` | 当前固定 `full` |
| `status` | queued/running/completed/failed |
| `created_at` / `started_at` / `finished_at` | 时间戳 |

### 7.2 `evaluation_runs`

用途：

- 一次具体执行。

字段：

| 字段 | 说明 |
| --- | --- |
| `id` | Run ID |
| `task_id` | 所属 Task |
| `status` | running/completed/failed |
| `current_stage` | 当前阶段 |
| `overall_score` | legacy，新任务为 null |
| `recommendation` | 推荐标签 |
| `result_summary` | 三类指标摘要 JSON |
| `artifact_root` | run artifact 目录 |
| `created_at` / `started_at` / `finished_at` | 时间戳 |

### 7.3 `stage_results`

用途：

- 保存每个 stage 的结果摘要。

字段：

| 字段 | 说明 |
| --- | --- |
| `id` | Stage Result ID |
| `run_id` | 所属 Run |
| `stage` | `static_scan` / `trigger_eval` / `effect_eval` |
| `status` | completed/no_cases/failed 等 |
| `score` | 阶段分 |
| `summary` | 摘要 |
| `metrics` | JSON |
| `artifact_path` | artifact 文件路径 |

### 7.4 `findings`

用途：

- 保存 Static Scan 命中规则。

字段：

| 字段 | 说明 |
| --- | --- |
| `id` | Finding ID |
| `run_id` | 所属 Run |
| `stage` | 当前为 static_scan |
| `code` | 规则 ID |
| `severity` | scanner 原始等级，critical/major/minor/info |
| `review_severity` | 人工确认等级，critical/major/minor/info/no_risk，可为空 |
| `review_note` | 人工确认备注 |
| `reviewed_at` | 人工确认时间 |
| `reviewed_by` | MVP 固定为 manual |
| `title` | 标题 |
| `detail` | 详情 |
| `file_path` | 相对文件路径 |
| `line_number` | 行号 |
| `fix` | 修复建议 |

### 7.5 `evidence_items`

用途：

- 登记 run 生成的证据文件。

字段：

| 字段 | 说明 |
| --- | --- |
| `id` | Evidence ID |
| `run_id` | 所属 Run |
| `evidence_type` | static/trigger/effect 等 |
| `name` | 展示名 |
| `path` | 文件路径 |
| `mime_type` | MIME |
| `size_bytes` | 文件大小 |
| `created_at` | 创建时间 |

## 8. API 详细设计

### 8.1 公共配置 API

#### `GET /api/categories`

返回 enabled categories。

用途：

- 上传确认时选择 category。
- Overview category selector。

#### `GET /api/runners`

返回 enabled runner environments。

用途：

- 创建评测任务时选择 Runner。

### 8.2 系统设置 API

#### Categories

```text
GET    /api/settings/categories
POST   /api/settings/categories
PUT    /api/settings/categories/{category_id}
DELETE /api/settings/categories/{category_id}
```

校验：

- name 必填。
- name 唯一。

删除：

- 未引用硬删。
- 已引用禁用。

#### Runners

```text
GET    /api/settings/runners
POST   /api/settings/runners
PUT    /api/settings/runners/{runner_id}
DELETE /api/settings/runners/{runner_id}
```

必填：

- name
- runner_type
- model_name
- command_path

删除：

- 统一软删除。

#### Model API Models

内部 API 仍分 provider/model：

```text
GET    /api/settings/model-providers
POST   /api/settings/model-providers
PUT    /api/settings/model-providers/{provider_id}
DELETE /api/settings/model-providers/{provider_id}

GET    /api/settings/model-models
POST   /api/settings/model-models
PUT    /api/settings/model-models/{model_id}
DELETE /api/settings/model-models/{model_id}
POST   /api/settings/model-models/{model_id}/test
```

前端交互上只呈现“模型配置”：

- provider_type
- base_url
- model name
- api_key

安全：

- 不返回 api_key 明文。
- 返回 `api_key_configured` 和 `api_key_preview`。

唯一性：

- `model_id + base_url` 不允许重复。

#### Model Roles

```text
GET /api/settings/model-roles
PUT /api/settings/model-roles
```

字段：

- `judge_model_id`
- `data_model_id`

校验：

- 选择的模型必须存在。

### 8.3 Skill 导入 API

#### `POST /api/imports/skill-zip`

请求：

- multipart form，字段 `file`。

成功返回：

- draft id
- source name
- derived skill name
- skill md path
- manifest

失败：

- 非 ZIP。
- 无 `SKILL.md`。
- 多个 `SKILL.md`。

#### `POST /api/imports/{draft_id}/confirm`

请求：

```json
{
  "skill_name": "csv-analyzer",
  "version": "1.0.0",
  "category": "Data & Analytics",
  "display_name": "CSV Analyzer"
}
```

校验：

- draft 必须存在。
- category 必须 enabled。
- `skill_name + version` 不重复。

结果：

- 创建或更新 Skill。
- 创建 Skill Version。
- 创建默认 Evaluation Set。

### 8.4 Skill API

```text
GET /api/skills
GET /api/skills/{skill_id}
PUT /api/skills/{skill_id}
```

`PUT /api/skills/{skill_id}` 只更新平台元信息：

- display_name
- description
- category
- card_content

不会修改 artifact 中的 `SKILL.md`。

### 8.5 Skill Files API

```text
GET /api/skills/{skill_id}/files?version_id=...
GET /api/skills/{skill_id}/files/content?version_id=...&path=...
```

安全：

- path 必须解析到 artifact root 内。
- 只返回相对路径。
- 二进制或超大文件不返回正文。

### 8.6 Evaluation Set API

```text
GET    /api/skills/{skill_id}/evaluation-set
POST   /api/skills/{skill_id}/evaluation-set/trigger-queries
DELETE /api/trigger-queries/{query_id}
POST   /api/skills/{skill_id}/evaluation-set/effect-cases
DELETE /api/effect-cases/{case_id}
GET    /api/skills/{skill_id}/evaluation-set/generation-jobs
POST   /api/skills/{skill_id}/evaluation-set/generation-jobs
GET    /api/evaluation-set-generation-jobs/{job_id}
POST   /api/evaluation-set-generation-jobs/{job_id}/confirm
DELETE /api/evaluation-set-generation-jobs/{job_id}
```

设计：

- Evaluation Set 由 Skill 绑定。
- 创建任务时不需要用户另选 Eval Set。
- AI 生成采用后台 job + draft_items + 用户确认入库，不直接写正式数据。

`POST /api/skills/{skill_id}/evaluation-set/generation-jobs` 请求：

```json
{
  "target": "trigger_queries",
  "count": 5,
  "instruction": "覆盖数据分析场景，包含边界 query",
  "include_negative": true
}
```

或：

```json
{
  "target": "effect_cases",
  "count": 3,
  "instruction": "生成带 deterministic assertions 的效果评测 case"
}
```

`POST /api/evaluation-set-generation-jobs/{job_id}/confirm` 请求：

```json
{
  "items": [
    {
      "selected": true,
      "duplicate": false,
      "query": "analyze this csv",
      "should_trigger": true
    }
  ]
}
```

确认规则：

- 只保存 `selected = true` 的草稿项。
- 后端会再次校验必填字段。
- Trigger 写入 `trigger_queries`。
- Effect 写入 `effect_cases`。
- 保存成功后 job 标记为 `confirmed`。

### 8.7 Task API

```text
GET  /api/tasks
POST /api/tasks
POST /api/tasks/{task_id}/run-now
GET  /api/tasks/{task_id}
GET  /api/tasks/{task_id}/evidence-detail
PUT  /api/tasks/{task_id}/scan-findings/{finding_id}/review
DELETE /api/tasks/{task_id}/scan-findings/{finding_id}/review
```

Scan finding review：

- `PUT` 请求体为 `{"review_severity":"no_risk","review_note":""}`。
- `review_severity` 支持 `critical`、`major`、`minor`、`info`、`no_risk`。
- `DELETE` 清除人工确认，恢复 scanner 原始等级。
- 保存或清除后，系统重新计算当前 Run 的 `scan_score`、`scan_status` 和 recommendation。
- Raw `static/findings.json` 不改写，API 和页面使用 DB 中的 effective severity。

`POST /api/tasks` 请求：

```json
{
  "skill_id": "skill_xxx",
  "skill_version_id": "version_xxx",
  "runner_environment_id": "runner_xxx"
}
```

校验：

- Skill Version 属于 Skill。
- Skill 有 Evaluation Set。
- Runner enabled。

`evidence-detail` 返回：

- static_scan normalized evidence。
- trigger_eval normalized evidence。
- effect_eval normalized evidence。
- raw artifacts。

### 8.8 Overview API

```text
GET /api/overview?category=Data%20%26%20Analytics
```

返回：

- Skills 总数。
- 已评测 Skills 数。
- 评测任务数量。
- 用户数量或运营占位指标。
- category 下推荐榜单。

排序：

1. recommendation tier。
2. Trigger score。
3. Scan 风险低优先。

## 9. Artifact 目录

```text
data/runs/<run_id>/
  static/
    findings.json
    static_metrics.json
  trigger/
    report.json
    logs/
      <query_id>.stdout.jsonl
      <query_id>.stderr.log
    workspaces/
  effect/
    report.json
    <case_key>/
      with_skill/
        stdout.jsonl
        stderr.log
        response.txt
        metrics.json
        grading.json
        judge/
          judge.stdout.jsonl
          judge.stderr.log
          usage.json
      without_skill/
        ...
```

## 10. 前端数据映射

| 页面 | 路径 | 主要 API |
| --- | --- | --- |
| 概览 | `/` | `/api/overview`、`/api/categories` |
| Skills 管理 | `/skills` | `/api/skills`、import APIs |
| Skill Detail | `/skills/:skillId` | `/api/skills/{id}`、files、evaluation-set |
| 评测任务管理 | `/tasks` | `/api/tasks`、`/api/runners` |
| Task Detail | `/tasks/:taskId` | `/api/tasks/{id}`、`/api/tasks/{id}/evidence-detail` |
| 系统设置 | `/settings` | `/api/settings/*` |

## 11. 兼容边界

保留但不作为当前主逻辑：

- `overall_score`
- `scoring_weights`
- `runner_environments.judge_model`

当前主逻辑：

- Scan / Trigger / Effect 独立展示。
- Runner 只代表被测环境。
- Judge 来自全局模型角色配置。
