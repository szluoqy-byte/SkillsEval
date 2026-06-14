# SkillsEval 系统架构详细设计

## 1. 文档目标

本文描述 SkillsEval 的系统架构，而不是代码模块架构。

本文重点回答：

- 这个系统服务哪些角色？
- 系统由哪些业务能力和子系统组成？
- Skill 从上传到评测再到选型的端到端流程是什么？
- Runner、模型 API、裁判模型、评测数据、证据产物分别处在什么边界？
- 用户在页面上的主要交互路径是什么？
- 当前 MVP 的部署形态、安全边界和后续架构演进是什么？

代码文件、数据库表、API 细节请阅读：

- `domain-model-and-api.md`
- `evaluation-design.md`
- `static-scan-rules-design.md`
- `effect-eval-design.md`

## 2. 系统定位

SkillsEval 是第三方独立 Skill 评测与选型平台。

它的核心价值不是“运行某一个 Agent”，而是把不同来源的 Skill 变成统一管理、统一评测、统一展示和统一追溯的资产。

系统关注三件事：

1. Skill 是否安全、结构清晰、可维护。
2. Skill 是否能在被测运行环境里被正确触发。
3. Skill 是否真的提升任务结果。

当前评测模型是：

```text
Scan + Trigger + Effect
```

系统不再为新任务追求加权总分。推荐结果是策略标签，不是单一分数。

## 3. 用户角色

### 3.1 Skill 选型/使用用户

目标：

- 找到某类任务下可用的 Skill。
- 快速理解 Skill 的推荐等级、风险和效果证据。
- 比较同一 category 下的 Skill。

主要入口：

- 概览页
- Skills 管理
- Skill Detail

关注信息：

- category
- recommendation
- Scan 风险
- Trigger 分数
- Effect 分数和 lift
- 最近一次评测证据

### 3.2 测试人员

目标：

- 上传 Skill 版本。
- 维护 Trigger Queries 和 Effect Cases。
- 发起真实评测任务。
- 查看规则命中、触发细节、assertion 判定和运行产物。
- 根据证据改进 Skill 或评测集。

主要入口：

- Skills 管理
- Skill Detail > Evaluation Set
- 评测任务管理
- Task Detail

关注信息：

- 上传解析结果
- 评测集覆盖度
- 每条 query/case 的执行结果
- findings
- assertion evidence
- stdout/stderr/artifacts

### 3.3 平台运营人员

目标：

- 维护分类。
- 维护 Runner Environments。
- 配置第三方模型 API。
- 选择裁判模型和数据模型。
- 观察整体系统运营状态和榜单质量。

主要入口：

- 概览页
- 系统设置
- 评测任务管理

关注信息：

- Skills 总量
- 已评测 Skills 数
- 任务数量
- 分类覆盖
- Runner 可用性
- Judge 模型配置
- 推荐榜单质量

## 4. 系统上下文

```text
┌──────────────────────┐
│ Skill 选型/使用用户   │
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│ SkillsEval Web Portal│
└──────────┬───────────┘
           │
┌──────────▼──────────────────────────────────────┐
│ SkillsEval API & Evaluation Platform             │
│                                                  │
│ - Skill Inventory                                │
│ - Evaluation Set Management                      │
│ - Evaluation Task Orchestration                  │
│ - Evidence & Report                              │
│ - Settings Center                                │
└───────┬───────────────┬──────────────────┬──────┘
        │               │                  │
┌───────▼───────┐ ┌─────▼────────┐ ┌───────▼──────────┐
│ Local Storage │ │ Runner Layer │ │ Model API Layer   │
│ SQLite + FS   │ │ OpenCode etc │ │ Judge/Data Models │
└───────────────┘ └──────────────┘ └──────────────────┘
```

系统外部依赖：

- Skill ZIP 包。
- 本地或远端 Runner。
- 第三方模型 API。
- 本地文件系统。

系统内部资产：

- Skill。
- Skill Version。
- Evaluation Set。
- Evaluation Task。
- Evaluation Run。
- Evidence Artifact。
- System Settings。

## 5. 总体系统分层

### 5.1 用户交互层

职责：

- 提供 Skills、Evaluation、Settings 的 Web 管理界面。
- 展示推荐榜单、Skill 卡片、任务报告和证据详情。
- 提供上传、编辑、创建任务、查看产物等交互。

特征：

- 以蓝白 SaaS 风格呈现。
- 一级菜单保持简洁。
- 下钻页面提供业务返回按钮。
- Skill Detail 使用 tab 工作区承载紧密相关功能。

### 5.2 业务 API 层

职责：

- 接收前端请求。
- 执行业务校验。
- 聚合领域对象。
- 返回页面所需视图数据。
- 管理上传、设置、任务、证据读取等业务动作。

边界：

- API 层不直接代表某个 Runner。
- API 层不直接调用裁判模型，裁判调用由 Effect 评测流程触发。
- API 层负责保证文件读取不越界。

### 5.3 评测编排层

职责：

- 将一次 Full Evaluation 拆成 Scan、Trigger、Effect。
- 管理任务状态、run 状态和 stage 结果。
- 聚合 result_summary 和 recommendation。
- 生成 evidence artifacts。

设计原则：

- Scan、Trigger、Effect 独立输出。
- Trigger 和 Effect 都通过 Runner 边界执行。
- Effect Judge 使用模型角色配置，不复用 Runner 模型。
- 失败不伪造结果。

### 5.4 Runner 执行层

职责：

- 表示被测运行环境。
- 接收 prompt、workspace、Skill 加载开关。
- 返回模型输出、工具调用、Skill 调用证据、耗时和错误。

当前实现：

- `opencode_cli`

未来可扩展：

- Claude Code Runner。
- Codex Runner。
- 自定义 local CLI Runner。
- Remote API Runner。
- Containerized Runner。

### 5.5 模型 API 层

职责：

- 管理可供 Judge/Data 使用的模型配置。
- 统一调用 openai-compatible 和 anthropic 风格接口。
- 屏蔽 API Key 明文。

当前角色：

- `judge`：Effect LLM Judge。
- `data`：Evaluation Set 中 Trigger Queries / Effect Cases 的 AI 辅助生成。

关键边界：

- 模型 API 层不是 Runner。
- Judge 模型不等于被测 Runner 模型。
- 系统不内置默认 OpenAI endpoint，base_url 由用户配置。

### 5.6 数据与证据层

职责：

- 保存结构化业务数据。
- 保存上传 Skill artifact。
- 保存 run 产物。
- 提供证据可追溯性。

数据类型：

- SQLite 业务数据。
- Skill artifact 文件。
- Run artifact JSON。
- stdout/stderr 日志。
- response/metrics/grading 文件。

## 6. 业务能力模块

### 6.1 概览与榜单模块

目标：

- 给所有角色提供系统整体状态和推荐 Skill 入口。

功能：

- 展示 Skills 总数。
- 展示已评测 Skills 数。
- 展示评测任务数量。
- 展示用户数量或运营指标。
- 按 category 展示 Recommended Skills。

榜单排序：

1. recommendation tier。
2. Trigger score。
3. Scan 风险低优先。

不承担：

- 不展示任务管理细节。
- 不展示系统设计说明。
- 不提供复杂筛选。

### 6.2 Skill Inventory 模块

目标：

- 管理 Skill 资产与版本。

功能：

- 上传 Skill ZIP。
- 解析 `SKILL.md`。
- 创建 Import Draft。
- 确认 Skill name、version、category。
- 创建 Skill 与 Skill Version。
- 展示 Skill 卡片。
- 展示最新评测摘要。

约束：

- 不提供“空白新建 Skill”。
- Skill 创建来源是上传导入。
- Skill 唯一身份是 package name，即 `skill_name`。

### 6.3 Skill Detail 工作区

目标：

- 将与单个 Skill 强关联的功能聚合在一个工作区。

包含：

- Skill Cards。
- Evaluation Set。
- Files。

设计理由：

- Evaluation Set 是 Skill 的评测数据，不应作为独立一级菜单。
- Files 是 Skill Version artifact 的检查能力，也应放在 Skill 内。
- 测试人员围绕一个 Skill 工作时不需要频繁跳转。

### 6.4 Evaluation Set 模块

目标：

- 维护 Trigger 与 Effect 所需评测数据。
- 用 Data Model 辅助生成候选评测数据，并由用户审核确认。

数据：

- Trigger Queries。
- Effect Cases。
- AI Generation Jobs。

交互原则：

- 使用紧凑工作台。
- 列表有分页或“查看全部”。
- 明细用抽屉或弹窗。
- 避免页面随数据增加而无限变长。
- AI 生成不阻塞页面，完成后先进入草稿审核，不直接入库。

AI 生成边界：

- Trigger 生成支持指定数量、生成要求和是否包含负样例。
- Effect 生成支持指定数量和生成要求，优先生成 deterministic assertions。
- 生成任务状态包括 queued、running、completed、failed。
- 刷新页面后可恢复查看 running、completed、failed job。
- 草稿项支持勾选、编辑、删除和重复项标记。

### 6.5 Evaluation Task 模块

目标：

- 发起和管理完整评测。

创建任务需要选择：

- Skill。
- Skill Version。
- Runner Environment。

不需要选择：

- Eval Set。当前由 Skill 绑定。
- 评测阶段。当前是 Full Evaluation。

状态：

- queued
- running
- completed
- failed

### 6.6 Evidence & Report 模块

目标：

- 让用户看懂评测结果，而不是只下载日志。

证据视图：

- Scan：findings 与 passed rules。
- Trigger：每条 query 的预期、实际和判定。
- Effect：with-skill/baseline、assertion、Judge、成本效率。
- Raw Artifacts：工程排查入口。

设计原则：

- 先展示结构化证据。
- 原始文件作为辅助。
- 不用“Skill pass/fail”简化复杂结果。

### 6.7 Settings Center 模块

目标：

- 维护平台运行配置。

包含：

- Runner Environments。
- Model API Models。
- Model Roles。
- Categories。
- Assessment Policy。

关键设计：

- Runner 是被测环境。
- Model API 是 Judge/Data 能力。
- Model Roles 从已配置模型中选择。
- Categories 影响后续上传选择，不重写历史 Skill。

## 7. 主流程架构

### 7.1 Skill 上传导入流程

```text
测试人员
  -> Skills 管理
  -> 上传 ZIP
  -> 系统解析 SKILL.md
  -> 生成 Import Draft
  -> 用户确认 skill_name/version/category
  -> 系统创建 Skill + Skill Version + Evaluation Set
  -> Skill 出现在列表
```

系统行为：

- 检查 ZIP。
- 找 `SKILL.md`。
- 解析 frontmatter name。
- 判断重复版本。
- 保存 artifact。
- 不自动运行评测。

异常：

- 无 `SKILL.md`：阻断。
- 多个 `SKILL.md`：阻断。
- 重复版本：阻断。
- category 不可用：阻断。

### 7.2 评测数据维护流程

```text
测试人员
  -> Skill Detail
  -> Evaluation Set tab
  -> 新增 Trigger Query
  -> 新增 Effect Case
  -> 保存后立即进入该 Skill 的评测数据资产
```

设计重点：

- Trigger Queries 用于判断“是否该触发”。
- Effect Cases 用于判断“触发后是否有效果提升”。
- 评测数据与 Skill 强绑定。

AI 辅助生成流程：

```text
测试人员
  -> Skill Detail
  -> Evaluation Set tab
  -> 点击 Trigger Queries 或 Effect Cases 的 AI 生成
  -> 填写生成数量和补充要求
  -> 系统创建 generation job
  -> 后台调用 Data Model
  -> 页面状态条显示 queued/running/completed/failed
  -> 用户查看生成草稿
  -> 勾选、编辑、删除草稿项
  -> 确认入库
```

设计重点：

- Data Model 只生成候选草稿，不拥有最终写入权。
- 重复草稿默认不选中，避免误写入。
- 失败 job 保留错误信息，便于用户调整模型配置或生成要求后重试。
- 关闭弹窗不取消后台任务，避免长时间生成时阻塞工作。

### 7.3 Full Evaluation 流程

```text
测试人员
  -> 评测任务管理
  -> 创建任务
  -> 选择 Skill / Version / Runner
  -> 系统创建 task
  -> 评测编排层执行 Scan / Trigger / Effect
  -> 生成 report 和 artifacts
```

系统执行：

1. Scan：检查 Skill artifact。
2. Trigger：在 Runner 下跑 trigger queries。
3. Effect：在 Runner 下跑 with-skill 和 baseline。
4. Judge：对语义 assertion 调用全局裁判模型。
5. Recommendation：根据策略生成标签。

### 7.4 证据查看流程

```text
用户
  -> Task Detail
  -> 查看三类指标摘要
  -> 切换 Scan / Trigger / Effect tab
  -> 查看结构化证据
  -> 必要时打开 Raw Artifacts
```

用户体验目标：

- 选型用户能快速理解推荐原因。
- 测试人员能定位失败 query/case。
- 运营人员能评估榜单可信度。

### 7.5 系统配置流程

```text
运营人员
  -> 系统设置
  -> 配置 Runner
  -> 配置模型 API
  -> 选择裁判模型
  -> 维护分类
```

配置生效范围：

- Runner：影响之后创建的新任务。
- Judge 模型：影响之后运行的 Effect Judge。
- Category：影响之后上传 Skill 的可选分类。

## 8. 用户交互架构

### 8.1 一级导航

```text
概览
Skills 管理
评测任务管理
系统设置
```

原则：

- 一级导航只保留高频主入口。
- Skill Detail、Task Detail 是下钻页。
- 下钻页提供业务返回按钮。

### 8.2 Skill Detail Tab 架构

```text
Skill Detail
  -> Skill Cards
  -> Evaluation Set
  -> Files
```

原因：

- Skill 卡片、评测集、文件都属于单个 Skill 的工作上下文。
- 合并为 tab 后减少菜单跳转。

### 8.3 Task Detail Evidence Tab 架构

```text
Task Detail
  -> Scan
  -> Trigger
  -> Effect
  -> Raw Artifacts
```

原因：

- 用户先按评测维度理解结果。
- 原始产物不作为默认阅读方式。

### 8.4 Settings 分区架构

```text
系统设置
  -> Runner Environments
  -> Model API Models
  -> Model Roles
  -> Categories
  -> Assessment Policy
```

原因：

- Runner 与模型 API 是两个不同概念。
- 裁判模型通过 Model Roles 选择。
- 权重配置已不再是当前主模型。

## 9. 集成架构

### 9.1 Runner 集成

Runner 集成采用 adapter 思路：

```text
评测编排层
  -> Runner Adapter
  -> 具体 Runner
```

当前实现：

- `opencode_cli`

未来扩展时，业务流程不应感知具体 Runner 细节。

### 9.2 模型 API 集成

模型 API 集成采用模型配置中心：

```text
Model API Model
  -> provider_type
  -> base_url
  -> model name
  -> api_key
```

支持：

- OpenAI-compatible Chat Completions。
- Anthropic Messages API。

使用场景：

- Effect LLM Judge。
- Data Model 生成 Trigger Queries / Effect Cases 草稿。

### 9.3 文件与 Artifact 集成

文件系统承担两类职责：

- Skill Version artifact。
- Evaluation Run artifact。

所有前端可见路径都应是相对路径或受控展示路径，避免暴露服务器任意文件读取能力。

## 10. 安全边界

### 10.1 上传安全

- ZIP 解压到受控目录。
- 只接受一个 `SKILL.md`。
- 不在上传阶段执行 Skill 代码。

### 10.2 文件读取安全

- Files API 限制在 artifact root 内。
- Evidence API 限制在 run artifact root 内。
- 二进制和超大文本不直接预览。

### 10.3 Runner 执行安全

当前是本地 workspace 隔离，不是容器隔离。

风险：

- Runner 进程仍可能访问本机环境。
- Skill 中的脚本如果被 Runner 执行，存在系统风险。

后续建议：

- 引入容器化 runner。
- 限制网络和文件权限。
- 为 Runner 单独配置沙箱策略。

### 10.4 API Key 安全

当前 MVP：

- API Key 明文保存在本地 SQLite。
- API 不返回明文。
- 前端只显示 mask。

后续建议：

- 本地加密。
- KMS。
- 权限审计。

## 11. 可观测性架构

系统当前可观测性主要依赖结构化 artifact。

每次 run 生成：

- stage_results。
- findings。
- evidence_items。
- static/report artifacts。
- trigger/report artifacts。
- effect/report artifacts。
- stdout/stderr。

前端通过 Evidence Workspace 消费这些结构化证据。

后续可扩展：

- 任务事件流。
- Worker 日志。
- Runner 调用 trace。
- Judge 调用 trace。
- 成本统计看板。

## 12. 当前 MVP 架构边界

当前没有：

- 多用户权限。
- 多租户隔离。
- 远程对象存储。
- 独立 worker 队列。
- 容器化 Runner 沙箱。
- 多 Runner 类型。
- 规则配置中心。

当前已经具备：

- 真实前后端。
- Skill ZIP 导入。
- Skill 版本管理。
- Evaluation Set 管理。
- 真实 Static Scan。
- 真实 Trigger Eval。
- Effect with-skill/baseline。
- LLM Judge。
- 模型 API 配置。
- 数据模型自动生成评测数据草稿。
- 证据工作区。

## 13. 后续架构演进

建议演进顺序：

1. 独立 Worker 服务  
   将评测任务从 API 进程中拆出，支持队列、重试、并发控制。

2. Runner Registry  
   将 Runner Adapter 扩展为 registry，支持多 runner_type 和运行时能力描述。

3. Runner 沙箱  
   引入容器、网络限制、文件系统隔离和资源限制。

4. Evidence Store  
   将本地 artifact 抽象为对象存储接口，支持远端部署。

5. Rule Management  
   为 Static Scan 增加规则版本、启停、ignore、allowlist。

6. Data Generation 增强  
   增加基于历史评测结果的覆盖度建议、生成任务重试、批量质量检查和多轮草稿改写。

7. Team & Permission  
   引入用户、角色、审计日志和 API Key 权限管理。
