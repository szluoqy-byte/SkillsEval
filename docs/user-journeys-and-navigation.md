# SkillsEval 用户角色、场景旅程与菜单目录推荐

版本：v0.1  
日期：2026-06-07  
状态：对齐讨论稿

## 1. 设计目标

本文补充 `third-party-skills-eval-platform.md` 的产品体验层，回答三个问题：

1. 谁会使用第三方 Skills 评测平台？
2. 他们在什么场景下进入平台，完成什么旅程？
3. 菜单目录应该如何组织，才能支撑“选型、诊断、比较、持续跟踪”的核心叙事？

平台主线仍保持：

```text
静态扫描 -> 触发评测 -> 效果评测 -> 性能评测
```

其中比较、榜单、版本趋势是评测后的分析视角，不作为单次评测任务里的第五个执行阶段。

## 2. 角色模型

### 2.1 Skills 选型/使用用户

典型身份：

- AI 应用开发者
- Agent 产品经理
- 企业内部工具使用者
- 想安装或引用第三方 skill 的个人用户
- 需要比较不同 skills 并决定试用/安装的人

核心问题：

- 这个 skill 值不值得用？
- 它适合我的任务场景吗？
- 有没有安全、权限、误触发或性能风险？
- 同类 skill 里哪个更好？
- 当前版本是否值得升级或替换？

关键页面：

- Overview
- Overview / Top 10 Skills by Category
- Skill Detail
- Evaluation Report
- Comparison

成功标准：

- 能在 3-5 分钟内判断某个 skill 是否值得进一步试用。
- 能看到推荐理由，而不只是一个总分。
- 能快速区分“安全风险”“触发不准”“效果一般”“太贵/太慢”。
- 能基于报告决定收藏、试用、导出或替换。

### 2.2 测试人员

典型身份：

- AI 评测工程师
- QA / 测试工程师
- Agent eval 平台建设者
- skill 维护团队中的测试负责人
- 数据集与 benchmark 维护者

核心问题：

- 我的 skill 哪里扣分？
- description 是否导致误触发或漏触发？
- eval case 是否足够覆盖真实场景？
- 新版本是否比旧版本更好？
- assertion/rubric 是否可复核？
- 哪些 case flaky、过宽、过窄或区分度不足？
- 运行产物是否足够支持复盘？

关键页面：

- Skills
- Skill Version Detail
- Skill Detail / Evaluation Sets
- Evaluation Runs
- Eval Case Editor
- Artifacts
- Run Detail / Review
- Runner Config

成功标准：

- 能上传一个版本并看到静态扫描结果。
- 能创建或生成 eval suite。
- 能看到逐 case 失败原因和可操作改进建议。
- 能比较新旧版本，避免只看单次分数。
- 能版本化管理 eval suite。
- 能追踪 prompt、files、expected output、assertions、rubrics。
- 能把人工反馈沉淀为下一版 eval suite 或 skill 改进建议。

### 2.3 平台运营人员

典型身份：

- 第三方评测平台运营
- 榜单维护者
- benchmark curator
- 社区/生态运营
- 企业内部 marketplace / 白名单维护者
- 安全与治理协作方

核心问题：

- 当前平台覆盖哪些 skill category？
- 哪些 category 缺少可靠 benchmark？
- 哪些榜单可以公开展示？
- 哪些评测结果过期、置信度不足或需要复评？
- 哪些 skill 有 critical risk，不适合推荐？
- 安全合格但效果差的 skill 是否应进入推荐？

关键页面：

- Overview
- Overview / Top 10 Skills by Category
- Overview / Benchmark Coverage
- 评测任务管理 / Risk Review
- 评测任务管理 / Runs Queue
- Overview / Data Quality
- Overview / Reports
- 系统设置 / Policies

成功标准：

- 能维护“可信榜单”而不是静态排行。
- 能看到 freshness、coverage、confidence。
- 能发现缺 eval、缺 runner telemetry、缺复核的类别。
- 能用 risk status 而不是只靠总分做治理判断。
- 能导出证据包支持审批、上架或下架决策。

## 3. 关键场景

### 3.1 找一个可用的 skill

触发条件：

- 用户需要完成某类 agent 任务，例如文档处理、数据分析、代码审查、表格生成。

用户目标：

- 在同类 skill 中找到安全、准确、触发稳定、成本可接受的候选。

平台支持：

- 展示 `Top 10 Skills by Category`。
- 每个 category 只展示当前排名前 10 的 skills。
- Top 10 默认按 `overall_score` 排名。
- Skill card 显示综合分、四阶段分、confidence、最近评测时间、关键风险。

推荐第一批 category：

| Category | 中文名 | 典型 skills |
| --- | --- | --- |
| Data & Analytics | 数据分析 | CSV/Excel 分析、指标归因、数据摘要、报表生成 |
| Documents & Knowledge | 文档与知识 | PDF/Word 处理、知识库问答、合同/报告解析 |
| Developer Tools | 开发工具 | 代码审查、测试生成、PR 分析、依赖检查 |
| Research & Web | 研究与检索 | 市场研究、网页调研、资料汇总、竞品分析 |
| Productivity & Office | 办公生产力 | PPT 生成、会议纪要、邮件草稿、任务整理 |
| Design & Media | 设计与多媒体 | 图片标注、设计检查、素材整理、alt text |
| Customer Support & CRM | 客服与客户管理 | 工单分类、客户摘要、回复建议、满意度分析 |
| DevOps & Cloud | 运维与云服务 | 日志分析、部署检查、云资源巡检、告警归因 |
| Security & Compliance | 安全与合规 | 权限审查、敏感信息扫描、策略检查、审计辅助 |
| Finance & Business | 财务与商业 | 财务表格、商业分析、预算说明、经营摘要 |
| Education & Training | 教育与培训 | 课件生成、学习材料整理、练习题生成 |
| Communication & Collaboration | 沟通协作 | Slack/飞书摘要、跨团队同步、项目周报 |

### 3.2 上传一个 skill 版本

触发条件：

- 测试人员需要导入新 skill 或新版本。
- 平台运营人员需要导入外部 skill，纳入分类评测或榜单候选。

用户目标：

- 完成 skill package / GitHub source 导入，形成可追踪的 Skill Version。
- 看到导入状态、版本信息和下一步建议。

平台支持：

- 上传 package / GitHub URL。
- 解析 `SKILL.md` 与文件树。
- 创建 Skill Version。
- 记录 source、version、hash、file tree、manifest。
- 提示是否进入该 skill 的评测集准备或完整评测。

### 3.3 在 Skill 下设计或生成评测集

触发条件：

- skill 没有自带 eval，或现有 eval 覆盖不足。

用户目标：

- 在当前 skill 下快速得到可运行、可复核的 trigger 和 effect eval cases。

平台支持：

- 在 Skill Detail 的 `评测集` tab 中管理。
- 从 skill description、README、scripts、examples 生成草稿。
- 区分 positive trigger、negative trigger、hard negative。
- 区分 deterministic assertions 与 LLM judge rubric。
- 保存为该 skill 绑定的评测集版本。

### 3.4 运行完整评测

触发条件：

- skill version 和 eval suite 都 ready，用户希望生成四阶段评测报告。

用户目标：

- 得到静态扫描、触发评测、效果评测、性能评测的完整报告、证据、风险结论和推荐级别。

平台支持：

- 按顺序执行静态扫描、触发评测、效果评测、性能评测。
- 动态评测默认 with-skill / without-skill 对照。
- 保存 transcript、outputs、grading、metrics、timing、benchmark。
- 对 critical risk 或明显触发失败给出停止/继续选择。

### 3.5 比较两个版本

触发条件：

- 测试人员完成新版本评测，或选型/使用用户在多个版本间选择。

用户目标：

- 判断新版本是否值得升级。

平台支持：

- 对比 static、trigger、effect、performance 的 delta。
- 展示新增/消失 findings。
- 展示 pass rate、trigger precision、token/time、flaky case 的变化。
- 标记 regression、improvement、tradeoff。

### 3.6 维护公开榜单

触发条件：

- 平台要对外展示某个 category 下的推荐 skill。

用户目标：

- 让榜单可信、可解释、不过期。

平台支持：

- 排名同时显示 overall、四阶段分、confidence、sample size、last evaluated。
- 排除 blocked 或 confidence 太低的结果。
- 显示榜单使用的 benchmark suite version。

## 4. 用户旅程

### 4.1 Skills 选型/使用用户旅程：从发现到试用

```text
进入 Overview
  -> 选择 Category
  -> 查看 Top Skills by Category
  -> 打开 Skill Detail
  -> 阅读四阶段摘要与关键风险
  -> 查看 Evaluation Report
  -> 对比同类 skill 或版本
  -> 收藏 / 导出 / 标记试用
```

关键体验：

- 第一屏先回答“这个 skill 排名靠前的原因是什么”。
- Skill Detail 先显示结论，再显示证据。
- 对非测试人员，报告要有自然语言摘要和风险标签。

### 4.2 测试人员旅程：从上传到评测改进

```text
进入 Skills
  -> Upload Skill
  -> 创建 Skill Version
  -> 查看 Static Scan
  -> 在 Skill Detail 下导入或生成评测集
  -> Run Evaluation
  -> 查看失败 case
  -> 接收 improvement suggestions
  -> 上传下一版本
  -> Version Comparison
```

关键体验：

- 上传后不要强迫立即生成 eval，但要明确下一步。
- 失败 case 要能定位到 description、文件、assertion 或运行产物。
- 改进建议必须是 proposal，不自动覆盖原 skill。

补充旅程：从 case 设计到 benchmark 维护

```text
进入 Skill Detail
  -> 打开评测集 tab
  -> 选择 Skill-owned Suite 或 Category Benchmark Suite
  -> 编辑 Trigger Queries / Effect Cases / Rubrics
  -> Dry Run / Validate Schema
  -> Run Benchmark
  -> Review Artifacts
  -> 标记 flaky / weak assertions
  -> 发布评测集版本
```

关键体验：

- Eval Suite Version 要像代码版本一样可追踪。
- Review feedback 要能回流到下一版 eval。
- category benchmark 的 case 数量不宜过大，优先保证可比性和复核质量。

### 4.3 平台运营人员旅程：从覆盖监控到榜单发布

```text
进入 Overview
  -> 查看 category coverage / freshness / confidence
  -> 进入 Benchmark Coverage
  -> 识别缺评测或过期 category
  -> 安排复评 runs
  -> 检查榜单候选
  -> 发布或更新榜单
```

关键体验：

- Overview 是评测生态状态，不是运行控制台。
- 榜单要显示依据，而不是只给排名。
- 运营指标要服务 selection/refinement，不堆无关系统指标。

补充旅程：从风险审查到推荐治理

```text
进入评测任务管理 / Risk Review
  -> 查看 blocked / review_required skills
  -> 打开 Audit Findings
  -> 检查权限、secret、外部 endpoint、供应链风险
  -> 查看效果与性能是否支持推荐
  -> 导出 Evidence Pack
  -> 设置推荐状态或治理标签
```

关键体验：

- 风险审查要与选型推荐分离。
- 高总分不能掩盖 critical finding。
- 审批视角要能导出 findings、报告和 artifact links。

## 5. 菜单目录推荐

### 5.1 MVP 菜单

建议第一版采用 4 个一级菜单：

```text
Overview
Skills Management
Evaluation Task Management
System Settings
```

对应中文：

```text
概览
Skills 管理
评测任务管理
系统设置
```

设计理由：

- `Overview` 是所有角色都能看的公共首页，只承接系统整体运营指标和 Top 10 Skills by Category。
- `Skills 管理` 是上传、版本、详情、报告、评测集管理的主入口。
- `评测任务管理` 承载任务队列、历史运行、失败状态、运行配置和任务详情里的复核能力。
- `系统设置` 只放 runner、model、category、scoring weights 等配置，不要压到主流程里。

### 5.2 推荐信息架构

```text
Overview
  - Health Summary
  - Category Coverage
  - Report Freshness
  - Risk Highlights
  - Top 10 Skills by Category

Skills Management
  - All Skills
  - Upload Skill
  - Skill Detail
  - Version Timeline
  - Evaluation Sets
  - Case Editor
  - Evaluation Set Versions
  - Evaluation Report
  - Improvement Suggestions

Evaluation Task Management
  - Run Queue
  - Run History
  - Run Detail
  - Artifacts
  - Review
  - Runner Logs

System Settings
  - Runner Adapters
  - Models
  - Categories
  - Scoring Weights
  - Export
```

### 5.3 Skill Detail 内部结构

Skill Detail 是最重要的页面，建议分成以下 tabs：

```text
Summary
Versions
Evaluation
Findings
Artifacts
Comparisons
Evaluation Sets
```

每个 tab 的职责：

- `Summary`：结论、四阶段分、confidence、推荐状态、最近运行。
- `Versions`：版本列表、当前版本、版本趋势、上传来源。
- `Evaluation`：单次 run 的四阶段报告。
- `Findings`：静态扫描和动态运行风险。
- `Artifacts`：transcript、outputs、grading、metrics、timing、benchmark。
- `Comparisons`：版本对比、同类对比、baseline 对比。
- `Evaluation Sets`：当前 skill 下绑定的 skill-owned suite 和 category benchmark suite。

### 5.4 Skill Detail > 评测集 Tab 内部结构

```text
Overview
Trigger Queries
Effect Cases
Rubrics
Files
Versions
Run History
Quality
```

设计重点：

- `Trigger Queries` 要清晰区分 positive、negative、hard negative。
- `Effect Cases` 要绑定 prompt、files、expected output、assertions。
- `Quality` 展示 flaky、weak assertion、coverage gap、review feedback。

### 5.5 Evaluation Run Detail 内部结构

```text
Run Summary
Stage Results
Case Results
Artifacts
Cost & Timing
Errors
Review
```

设计重点：

- `Stage Results` 按四阶段显示，不按 AWS/Anthropic/OpenAI provider 显示。
- `Case Results` 支持筛选 failed、flaky、needs review。
- `Artifacts` 必须能打开具体证据，而不是只显示 JSON 路径。

## 6. 首页推荐布局

首页不建议做操作密集型 dashboard，也不放评测任务管理内容。建议做“系统整体运营情况 + Top 10 Skills by Category”：

1. 顶部结论区：
   - Skills 总数
   - 已评测 Skills 数
   - 评测任务数量
   - 用户数量
2. Top 10 Skills by Category：
   - 默认展示 `Data & Analytics` category
   - 每个 category 展示排名前 10 的 skills
   - 默认按 `overall_score` 排名
   - 显示 overall、四阶段分、confidence、最近评测时间、关键风险

首页应避免：

- 大量运行按钮。
- 类似 CI pipeline 的状态堆叠。
- 抽象 capability counter。
- 与上传 skill 无关的生态指标。

## 7. 推荐命名

### 7.1 一级导航中文命名

推荐：

- 概览
- Skills 管理
- 评测任务管理
- 系统设置

不推荐：

- 运营看板：容易把平台带回内部运营系统。
- 质量门禁：容易变成 release gate。
- 方法论：不适合作为用户主导航。
- 数据管理：过泛，无法表达 eval suite 的产品价值。

### 7.2 状态命名

Skill 评测状态：

- `Imported`
- `Static Ready`
- `Eval Suite Ready`
- `Evaluating`
- `Report Ready`
- `Review Required`
- `Recommended`
- `Blocked`

Eval Suite 状态：

- `Draft`
- `Ready`
- `Running`
- `Needs Review`
- `Published`
- `Archived`

Run 状态：

- `Queued`
- `Running`
- `Completed`
- `Failed`
- `Stopped`
- `Review Pending`

## 8. MVP 优先级

第一阶段必须有：

1. Overview
2. Skills 管理 / Skill Detail
3. Skill Detail / Evaluation Sets / Case Editor
4. 评测任务管理 / Run Detail

第一阶段可以简化：

- Review 作为 Run Detail 里的 tab，不作为一级菜单。
- 榜单能力合入 Overview，先只做 `Top 10 Skills by Category`。
- 系统设置只保留 runner、model、category、scoring weights。

不建议第一阶段做：

- 企业审批流。
- 复杂 RBAC。
- public marketplace 发布。
- 大量自定义 dashboard。

## 9. 已确认决策

当前已确认：

- 用户角色分为 Skills 选型/使用用户、测试人员、平台运营人员。
- `Overview` 是所有角色都能看的公共首页，只保留系统整体运营指标和 `Top 10 Skills by Category`。
- 首页顶部指标保留 Skills 总数、已评测 Skills 数、评测任务数量、用户数量。
- `Top 10 Skills by Category` 默认展示 `Data & Analytics`，默认按 `overall_score` 排名。
- `Skills 管理` 是第一优先级页面，但不是首页。
- `Evaluation Sets` 归属 Skill Detail，不做一级菜单。
- Review 保持在 Run Detail 内，不做一级菜单。
- `系统设置` MVP 只保留 runner、model、category、scoring weights。
