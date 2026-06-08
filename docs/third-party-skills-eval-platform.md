# 第三方独立 Skills 评测平台设计

版本：v0.1  
日期：2026-06-07  
状态：对齐讨论稿

## 1. 背景与目标

Agent Skills 的价值不只来自一份 `SKILL.md`，还来自它是否安全、是否会在正确场景被触发、是否真的提升任务结果，以及提升是否值得额外的时间、token 和工具调用成本。一个第三方独立 Skills 评测平台需要站在“选型、诊断、比较、持续跟踪”的角度，而不是只做某个 agent CLI 的本地测试命令。

本平台参考两类已存在实践：

- AWS `sample-agent-skill-eval`：提供较完整的工程化评测框架，核心包含 audit、functional、trigger、cost、regression、unified report，并有明确的 eval schema、CLI exit code、A-F 等级和 40/40/20 综合评分。
- Anthropic `skill-creator`：更强调技能创建与迭代闭环，包含 eval case schema、with-skill / without-skill 对照运行、grader 产物、benchmark 聚合、review viewer、description trigger 优化和 train/test holdout。

本平台将这些实践抽象成四层评测链路：

1. 静态扫描：不运行 agent，先判断 skill 包本身是否可信、完整、可评测。
2. 触发评测：验证 skill 在该用时会被调用，不该用时保持安静。
3. 效果评测：验证使用 skill 后任务结果是否更正确、更稳定、更可解释。
4. 性能评测：验证改进是否值得成本，包括时间、token、工具调用、错误率和回归风险。

## 2. 平台定位

### 2.1 产品定位

SkillsEval 是一个第三方独立 skills 评测与选型平台。它不替代具体 agent，也不假设技能只能服务 Claude、OpenAI、Cursor、Codex 或某个私有运行时。平台的核心价值是把不同来源的 skills 变成可比较、可复核、可追踪的评测资产。

目标用户包括：

- Skills 选型/使用用户：想知道某个 skill 是否值得安装、在哪些场景可靠、有哪些风险。
- 测试人员：想验证 skill 的触发描述、说明文档、脚本、eval case 和新旧版本质量。
- 平台运营人员：想建立第三方榜单、分类 benchmark、版本趋势、可信报告、风险审查和推荐治理。

### 2.2 与 CI 工具的区别

本平台可以导出 CLI 或 CI 结果，但本质不是 release gate。它更像一个持续评测与证据管理平台：

- 技能包上传后进入版本化管理，而不是一次性本地命令输出。
- 评测数据由平台生成、导入、编辑、复用，而不是强依赖 skill 包自带 `evals/`。
- 评测运行产物需要保存 transcript、outputs、grading、timing、metrics、review feedback，支持复核。
- 分类榜单和版本对比来自可追溯的 eval suite，而不是简单平均分。

## 3. 设计原则

1. 从浅到深：先静态，再触发，再效果，最后性能，避免在明显不安全或不可评测的 skill 上浪费运行成本。
2. 证据优先：每个结论必须能落到 finding、assertion、transcript、output、tool call 或 timing 等评测证据上。
3. 与 agent 解耦：通过评测执行器 runner 支持不同 agent CLI/API，平台保留统一的 run/result schema。
4. Skill 与评测集解耦但入口归属 Skill：skill 可以不自带 eval；平台应能在 Skill Detail 下生成、导入、维护版本化评测集。
5. 对照实验优先：效果评测默认比较 with-skill、without-skill，必要时比较 old-skill、new-skill。
6. 版本与分类是横切能力：同一 skill 的版本回归、同一 category 下的横向 benchmark 都应基于同一套证据。
7. 综合分服务选型，不掩盖风险：总分可用于排序，但关键安全问题、触发错误、重大回归必须单独暴露。

## 4. 核心对象模型

### 4.1 Skill

代表一个技能家族，例如 `pdf-form-filler` 或 `data-analysis`。

关键字段：

- `id`
- `skill_name`
- `name`
- `description`
- `category`
- `source_type`: upload、registry、github、manual
- `owner`
- `latest_version_id`
- `created_at`

Trigger Query 最小结构：

- `query`
- `should_trigger`

Effect Case 最小结构：

- `id`
- `prompt`
- `expected_output`
- `files`
- `assertions`

`assertions` 是两级判定机制：

1. 先执行确定性规则匹配，例如 contains、does not contain、regex、JSON schema、结构/字段检查。
2. 确定性规则无法识别或语义判断不足时，再交给 LLM Judge，根据 rubric、expected_output 和实际输出做语义判定。

说明：

- Skill 的唯一身份按 `skill_name` 识别；`skill_name` 就是用户在管理页看到的 Skill 名称，同一个 `skill_name` 下可以有多个 Skill Version。
- `category` 在上传 skill 时由用户人工选择，平台后续可以提供推荐，但不自动覆盖人工选择。

### 4.2 Skill Version

代表一个可评测的完整 skill 包快照。

关键字段：

- `id`
- `skill_id`
- `version`
- `package_uri`
- `manifest`
- `import_status`
- `static_scan_status`
- `created_at`

说明：

- 所有评测运行都绑定到 `skill_version_id`，避免后续文件变化污染历史结论。
- MVP 使用同一 Skill 下 `version` 唯一校验；如果 `skill_name + version` 已存在，导入确认时提示该版本已存在。
- hash 与完整 file tree 可作为后续增强或调试信息，不作为 MVP 重复上传判断主链路。

### 4.3 Eval Suite

代表某个 skill 的一组评测任务定义。评测集只绑定 Skill，不再设置 Category 级评测集。

关键字段：

- `id`
- `scope`: skill
- `skill_id`
- `category`
- `name`
- `description`
- `owner`
- `status`: draft、ready、archived

### 4.4 Eval Suite Version

代表某次可复现的 eval 定义快照。

关键字段：

- `id`
- `eval_suite_id`
- `version`
- `cases`
- `trigger_queries`
- `files`
- `rubrics`
- `created_at`

### 4.5 Evaluation Run

代表一次具体运行。

关键字段：

- `id`
- `skill_version_id`
- `eval_suite_version_id`
- `runner_environment`: 平台预置运行环境，例如 `Claude Code + MiniMax 2.7`、`Codex Runner + GPT-5`。
- `task_scope`: 系统内置为 Full Evaluation，用户不选择。
- `run_config`
- `status`
- `started_at`
- `finished_at`
- `result_summary`
- `artifact_root`

### 4.6 Finding / Metric / Evidence

平台报告不只保存分数，还要保存证据：

- Finding：静态扫描问题，含 severity、code、file、line、fix。
- Metric：可聚合的指标值，含 metric key、value、unit。
- Evidence：评测证据/运行产物，含 transcript、outputs、grading.json、metrics.json、timing.json、benchmark.json、review feedback。工程字段仍可使用 `artifact_root`，但用户界面建议显示为“评测证据”。

## 5. 四类评测指标体系

### 5.1 静态扫描

目标：在不运行 agent 的前提下判断 skill 是否安全、完整、可评测、可维护。

参考来源：

- AWS audit / security_scan / permission_analyzer / structure_check。
- Anthropic quick validation 与 schema readiness。

建议指标：

| 指标 | 含义 | 计算方式 | 主要证据 |
| --- | --- | --- | --- |
| Structure Readiness | skill 包结构是否完整 | 必填文件、frontmatter、name/description、文件引用完整率 | `SKILL.md`、file tree |
| Schema Readiness | eval schema 是否可读可执行 | eval case 必填字段通过率 | `evals.json`、平台 eval suite |
| Permission Risk | tool 权限是否过大 | 按高危 tool、未限定 Bash、敏感路径访问扣分 | frontmatter、instructions |
| Secret Exposure | 是否包含密钥或凭据 | secret pattern 命中数与严重级别 | package files |
| Supply Chain Risk | 是否存在不安全安装/远程执行 | `curl | sh`、unpinned install、`npx -y` 等规则 | scripts、instructions |
| Code Execution Risk | 是否存在危险代码执行模式 | subprocess、shell=True、eval/exec、unsafe deserialization | scripts |
| External Endpoint Surface | 是否有外部 URL/MCP endpoint | 非安全域名 URL、MCP/SSE endpoint 计数与风险级别 | docs、scripts、config |
| Prompt Injection Surface | 是否鼓励忽略用户意图或执行任意输入 | prompt injection pattern 命中与人工复核 | `SKILL.md` |

默认评分：

```text
static_score = clamp(100 - critical_count * 25 - warning_count * 10 - info_count * 2, 0, 100)
```

默认结论：

- `blocked`：存在 critical finding，例如硬编码真实密钥、危险远程执行、明显恶意指令。
- `review_required`：无 critical，但存在高风险权限、外部 endpoint 或高误报规则。
- `ready`：结构完整，风险可接受，可以进入动态评测。

平台设计要点：

- 静态扫描不仅服务安全，也服务“能不能评测”：缺少 description、eval case 不完整、文件引用丢失都会降低后续评测可信度。
- 静态扫描 findings 必须可解释、可定位、可修复。
- 对第三方平台而言，critical finding 不一定直接下架，但必须阻止默认自动运行动态评测。

### 5.2 触发评测

目标：判断 skill 的描述和触发边界是否清晰。一个好 skill 应该在相关请求中稳定触发，在不相关请求中保持沉默。

参考来源：

- AWS trigger evaluation：`eval_queries.json` 中的 `query` 与 `should_trigger`，多次运行计算 trigger rate。
- Anthropic description optimization：使用 trigger eval set、runs per query、train/test holdout，迭代优化 description。

建议指标：

| 指标 | 含义 | 计算方式 | 主要证据 |
| --- | --- | --- | --- |
| Trigger Recall | 应触发场景中是否触发 | true positive / should-trigger total | trigger runs |
| Trigger Precision | 触发场景是否准确 | true positive / all triggered | trigger runs |
| Negative Silence Rate | 不应触发时是否保持安静 | true negative / should-not-trigger total | trigger runs |
| Trigger Stability | 多次运行是否一致 | 每个 query 的 trigger rate 方差、flaky query 数 | repeated runs |
| Description Fit | description 是否能覆盖目标场景 | train/test trigger score、holdout gap | description eval |
| Boundary Clarity | 近邻场景是否误触发 | hard-negative pass rate | curated queries |

默认判定：

```text
positive query pass: trigger_rate >= 0.5
negative query pass: trigger_rate < 0.5
trigger_score = weighted_mean(recall, precision, silence_rate, stability)
```

建议默认权重：

- recall：35%
- precision：25%
- negative silence：25%
- stability：15%

平台设计要点：

- 触发评测要保留 query 级别结论，不能只展示总分。
- 正样本、负样本、hard negative 必须分开展示；否则高 recall 可能掩盖误触发。
- 对测试人员，平台应给出 description 改写建议，但不能自动覆盖原 skill；建议作为可采纳的 patch 或新版本候选。
- 对第三方榜单，触发评测要显示置信区间或样本规模，避免 5 条 query 决定排名。

### 5.3 效果评测

目标：判断 skill 被使用后是否真的改善任务结果。效果评测是平台最核心的价值层，因为它回答“这个 skill 是否有用”。

参考来源：

- AWS functional evaluation：with-skill / without-skill 对照运行，使用 deterministic assertions 和 LLM fallback grading。
- AWS functional 4-dimension：outcome、process、style、efficiency。
- Anthropic benchmark：with_skill / without_skill 多次运行，聚合 pass rate、time、tokens、tool calls、errors 和 notes。
- Anthropic grader：每个 expectation 要有 passed、evidence、claims、user notes、eval feedback。

建议指标：

| 指标 | 含义 | 计算方式 | 主要证据 |
| --- | --- | --- | --- |
| Outcome Pass Rate | 输出是否满足预期 | passed assertions / total assertions | grading.json |
| Skill Lift | skill 带来的净提升 | with_skill pass_rate - without_skill pass_rate | benchmark |
| Baseline Advantage | 相比无 skill 是否显著更好 | 多轮运行均值差、置信区间、显著性标签 | benchmark |
| Process Quality | 工具使用路径是否合理 | tool call rubric、必要文件读取、无无效步骤 | transcript、metrics |
| Output Correctness | 输出/文件是否正确可用 | 文件存在、格式合法、内容校验、截图/渲染验证 | outputs |
| Style / Contract Fit | 输出格式是否符合要求 | JSON schema、markdown/table/style assertions | outputs |
| Evidence Quality | 评分证据是否充分 | expectation evidence 覆盖率、claims verified rate | grading.json |
| Eval Quality | eval 本身是否可靠 | assertion 区分度、过宽/过窄提示、flaky case 比例 | eval feedback |

默认判定：

```text
effect_score = 0.45 * outcome
             + 0.25 * normalized_skill_lift
             + 0.15 * process_quality
             + 0.10 * output_correctness
             + 0.05 * evidence_quality
```

其中：

- `outcome` 是 with-skill 的 assertion pass rate。
- `skill_lift` 是 with-skill 与 without-skill 的差值；小于 0 时视为强风险。
- `normalized_skill_lift` 可将 `[-0.2, +0.5]` 映射到 `[0, 1]`，避免少数极端 case 主导总分。

平台设计要点：

- 效果评测默认必须跑 baseline，否则只能称为 “task score”，不能称为 “skill lift”。
- assertions 采用两级判定：先走确定性规则匹配；确定性规则识别不了的，再交给 LLM Judge。LLM Judge 结果必须保存 reasoning/evidence。
- 对生成文件类任务，必须保存产物并支持人工/自动查看。
- 平台要区分 skill 问题和 eval 问题：低分可能来自 skill 差，也可能来自 eval case 不可判定。

### 5.4 性能评测

目标：判断 skill 带来的收益是否值得成本，并监控版本变化是否退化。

参考来源：

- AWS cost estimation 与 cost-efficiency classification。
- AWS regression snapshot / baseline comparison。
- Anthropic benchmark 中的 time、tokens、tool calls、errors、stddev、delta。

建议指标：

| 指标 | 含义 | 计算方式 | 主要证据 |
| --- | --- | --- | --- |
| Latency | 任务完成耗时 | mean / p50 / p95 duration | timing.json |
| Token Cost | token 消耗 | input/output/total tokens、估算价格 | timing、runner usage |
| Tool Call Cost | 工具调用复杂度 | total tool calls、high-risk tool calls、redundant calls | metrics.json |
| Error Rate | 运行错误率 | errors / runs | metrics、transcript |
| Flakiness | 结果稳定性 | pass rate stddev、same case 多轮波动 | benchmark |
| Cost Efficiency | 质量提升与成本变化关系 | quality_delta 与 cost_delta 的 Pareto 分类 | benchmark |
| Regression Score | 相比历史版本是否退化 | current vs baseline metric delta | baseline snapshots |
| Throughput Readiness | 平台规模化运行可行性 | 并发耗时、失败重试率、平均成本 | run scheduler |

建议 Pareto 分类：

- `PARETO_BETTER`：质量提升且成本下降。
- `TRADEOFF`：质量提升但成本上升。
- `CHEAPER_BUT_WEAKER`：成本下降但质量下降。
- `PARETO_WORSE`：质量不升且成本上升。
- `REJECT`：质量显著下降，即使成本下降也不推荐。

默认评分：

```text
performance_score = 0.30 * latency_score
                  + 0.25 * token_cost_score
                  + 0.20 * stability_score
                  + 0.15 * error_score
                  + 0.10 * regression_score
```

平台设计要点：

- 性能评测不能脱离效果评测单独排名；低成本但无效果提升的 skill 不应被推荐。
- 对用户选型，最有用的不是绝对 token 数，而是“每提升 1% pass rate 需要付出多少成本”。
- 版本回归建议作为横切维度展示在 skill detail 中，不单独变成第五类主指标。

## 6. 综合评分与报告口径

### 6.1 阶段分数

平台保留四个阶段分数：

- `static_score`: 0-100
- `trigger_score`: 0-100
- `effect_score`: 0-100
- `performance_score`: 0-100

### 6.2 默认综合分

建议默认权重：

```text
overall_score = static_score * 0.20
              + trigger_score * 0.25
              + effect_score * 0.40
              + performance_score * 0.15
```

原因：

- 静态扫描是信任底座，但不能替代真实效果，因此不应压过动态评测。
- 触发评测决定 skill 能否被正确使用。
- 效果评测最能体现 skill 价值，因此权重最高。
- 性能评测影响推荐级别和生产可用性，但不应压过安全与效果。

如果某阶段缺失，平台不应简单重分配权重。MVP 暂不展示 `confidence`，只展示已完成阶段、缺失阶段和最近评测时间。

示例：

- 只有静态扫描：可以给出风险报告，但不能进入榜单。
- 静态 + 触发：可以给出触发质量诊断，但不能宣称效果最好。
- 四阶段完整：可以进入分类榜单和版本对比。

### 6.3 等级

建议等级：

- A：90-100，推荐优先试用。
- B：80-89，可用，有明确改进项。
- C：70-79，谨慎使用，适合继续迭代。
- D：60-69，不建议默认安装。
- F：0-59，不推荐。

强制降级规则：

- 任一 critical security finding：最高不超过 C，并显示关键风险标签；MVP 不直接阻断进入榜单。
- trigger precision 或 recall 低于 60：最高不超过 C。
- effect skill lift 小于 0：最高不超过 D。
- performance Pareto worse 且无明显质量提升：最高不超过 C。

## 7. 评测流水线

### 7.1 上传与导入

1. 用户上传 skill package 或填写本地/服务器导入路径。
2. 平台解析 `SKILL.md`、frontmatter、候选 skill root、文件树、脚本和引用文件，生成 Import Draft。
3. 用户确认或编辑 `skill_name`、`display_name`、`category`、`version` 等必填项；其中 `version` 必须由用户最终确认。
4. 平台创建 Skill 与 Skill Version，并冻结文件树。
5. 给出 import readiness，不自动触发静态扫描或动态 eval；静态扫描属于后续评测任务的一部分。

导入规则：

- 上传解析后先展示解析结果和候选值，不直接冻结为最终版本。
- `skill_name` 可从 `SKILL.md` frontmatter `name` 预填，但用户可以修正。
- `version` 不可靠依赖官方结构，必须由用户填写或确认。
- `category` 由用户人工选择，系统可以推荐但不自动覆盖。
- 如果包内存在多个 `SKILL.md`，直接阻断导入并提示不符合单 Skill 包规范，由用户整理包结构后重新上传。

### 7.2 Eval Suite 生成与维护

平台提供三种方式：

- 从 skill 自带 `evals/` 导入。
- 用户手动创建/编辑。
- 平台基于 skill description、README、examples、scripts 生成初稿。

生成后必须进入 review 状态：

- trigger queries 要有正样本、负样本、hard negatives。
- functional/effect cases 要有 `id`、`prompt`、`expected_output`、`files`、`assertions`。
- rubrics 要区分 deterministic check 与 LLM judge。

### 7.3 动态运行

推荐顺序：

1. 检查静态扫描是否允许动态运行。
2. 运行 trigger eval，发现明显触发问题时可停止效果评测。
3. 运行 functional/effect eval，默认 with-skill 与 without-skill 对照。
4. 聚合 benchmark，生成 effect 与 performance 指标。
5. 如存在历史版本，运行 regression comparison。

### 7.4 人工复核

动态评测产物必须有 review 页面：

- 按 eval case 查看 prompt、outputs、transcript、grading。
- 支持标记误判、补充反馈、调整 assertion。
- 支持将反馈生成新 eval suite version 或 skill 改进建议。

## 8. 平台页面与体验

MVP 页面建议：

1. Overview：Skills 总数、已评测 Skills 数、评测任务数量、用户数量、Top 10 Skills by Category。
2. Skills 管理：skill 列表、上传入口、版本、导入状态、分类、最近分数。
3. Skill Detail：版本评测结果、四阶段指标、findings、评测集、评测证据。
4. 评测任务管理：独立一级菜单，集中管理任务队列、运行状态和历史任务；任务详情页承载四阶段评估方法、阶段指标、with-skill / without-skill 对照、findings 和评测证据。
5. 系统设置：运行环境 Runner、category、scoring weights。

重要体验原则：

- 首页不要做运维控制台，重点是“哪些 skill 值得看、为什么、风险是什么”。
- Skill detail 要先展示版本与结论，再进入底层证据。
- Overview 是所有角色都能看的公共页，只保留系统整体运营情况和榜单；榜单默认展示 `Data & Analytics` category，默认按 `overall_score` 排名，并显示四阶段分、关键风险和最近评测时间。

## 9. 数据与产物目录建议

平台内部可以采用如下概念目录：

```text
data/
  uploads/
    {skill_id}/{version}/
  eval_suites/
    {suite_id}/{version}/
  runs/
    {run_id}/
      static/
      trigger/
      effect/
      performance/
      artifacts/
        transcript.md
        outputs/
        grading.json
        metrics.json
        timing.json
        benchmark.json
        feedback.json
```

对外导出格式：

- `report.json`: 机器可读总报告。
- `report.md`: 人类可读摘要。
- `findings.json`: 静态扫描 findings。
- `benchmark.json`: 多轮运行聚合。
- `artifacts.zip`: 完整评测证据包。

## 10. MVP 范围

第一版建议聚焦：

- Skill upload/import。
- Skill/Skill Version 管理。
- 静态扫描。
- Skill Detail 下的评测集 CRUD/import/generate draft。
- Trigger eval。
- Effect eval with/without skill。
- Benchmark aggregation。
- 四阶段报告。
- Skill detail 与 Overview 中的 Top 10 Skills by Category。

暂不做：

- 自动发布 marketplace。
- 企业审批流。
- 多租户权限系统。
- 大规模分布式调度。
- 自动修复并提交 PR。

## 11. 已确认决策与待对齐问题

已确认：

1. 用户角色分为 Skills 选型/使用用户、测试人员、平台运营人员。
2. Overview 只展示 Skills 总数、已评测 Skills 数、评测任务数量、用户数量，以及 Top 10 Skills by Category。
3. Top 10 默认展示 `Data & Analytics` category，默认按 `overall_score` 排名。
4. Skills 管理是第一优先级页面，但不是首页。
5. Evaluation Sets 归属 Skill Detail，不做一级菜单。
6. Skill Detail 不承载运行详情；评测任务管理作为独立一级菜单，Skill Detail 首页直接展示版本评测结果。
7. Skill 唯一身份按 `skill_name` 识别，`skill_name` 即用户看到的 Skill 名称。
8. 上传 skill 时由用户人工选择 `category`。
9. critical finding 不直接阻断进入榜单，但必须显示关键风险。
10. MVP 暂不展示 `confidence`。
11. 用户界面使用“评测证据/运行产物”，不直接使用 Artifact 作为主展示词。
12. runner 在产品层指运行环境 Runner，是执行器和被测模型的预置组合；系统设置 MVP 只保留运行环境 Runner、category、scoring weights。
13. MVP 暂不设计系统失败处理，后续再补充。
14. 即使 skill 存在安全风险，平台默认仍允许动态评测；风险在榜单、详情和运行报告中显著展示，不作为运行阻断条件。
15. 触发优化建议由平台生成 suggestion / proposal，不自动创建或覆盖新的 skill version。
16. LLM judge 结果可以进入榜单；MVP 阶段用户只看结果和相关 judge 口径，暂不引入人工复核状态。
17. 视觉与交互方向收敛为 `Product Cloud`，其他探索方向保留为历史参考，不再继续演进。
18. Skill Detail Summary 不重复展示 Evaluation Sets；每个 Skill 维护一个 Evaluation Sets，在独立 tab 中维护。
19. AWS 静态扫描规则由系统预置，只读不可修改；Evaluation Sets 中只展示规则分组和规则数量。
20. Suggestion 属于评测运行结果，不属于 Evaluation Sets 定义；Skill Detail Summary 展示当前最新版本最近一次任务产出的 suggestion。
21. Skill Detail 的版本评测结果暂不下钻。
22. 评测任务管理需要新建任务流程，但只让用户选择 Skill、版本、当前 Evaluation Sets 和运行环境 Runner；评测范围固定 Full Evaluation，不展示 Task Type、Model 或 Judge Model。
23. 任务运行中只展示任务状态，不展示阶段进度。
24. 任务列表不放报告摘要，任务详情页展示核心评估方法与结果证据。
25. Evaluation Sets 下 Trigger Queries 与 Effect Cases 分开独立维护，分别支持辅助生成、导入、新增、编辑、删除，不做启用/禁用和版本发布。
26. Evaluation Sets 不提供默认的混合导入入口，避免一次操作同时改动 Trigger Queries 与 Effect Cases。
27. 系统设置与 Overview 暂不继续细化。

仍需对齐：

status: not provided

## 12. 参考实现来源

本稿参考并抽象了以下实现口径：

- AWS sample-agent-skill-eval：https://github.com/aws-samples/sample-agent-skill-eval
  - `docs/concepts.md`：三支柱、评分规则、eval schema、CI exit code。
  - `skill_eval/audit/*`：结构、安全、权限静态扫描。
  - `skill_eval/functional.py`：with-skill / without-skill 对照运行与 grading。
  - `skill_eval/trigger.py`：正负触发 query、多次运行、trigger rate。
  - `skill_eval/cost.py`：token cost 与 cost estimation。
  - `skill_eval/regression.py`：snapshot、baseline、regression comparison。
  - `skill_eval/unified_report.py`：audit 40%、functional 40%、trigger 20% 的统一报告。
- Anthropic skill-creator：https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator/skills/skill-creator
  - `references/schemas.md`：`evals.json`、`grading.json`、`metrics.json`、`timing.json`、`benchmark.json` 等产物 schema。
  - `scripts/run_eval.py`、`scripts/run_loop.py`：触发评测、description optimization、train/test holdout。
  - `scripts/aggregate_benchmark.py`：多轮运行聚合、均值/方差/delta。
  - `eval-viewer/generate_review.py`：review viewer 与反馈保存。
  - `agents/grader.md`、`agents/analyzer.md`、`agents/comparator.md`：评分、分析、比较的 agent 分工。

## 13. 第一版对齐结论

建议把 SkillsEval 的核心叙事定为：

> 一个第三方独立 skills 评测平台，通过“静态扫描 -> 触发评测 -> 效果评测 -> 性能评测”的渐进链路，把 skill 包、eval suite、运行证据和版本比较沉淀成可复核的选型报告与分类榜单。

这个叙事保留了 AWS 工程框架的可落地性，也吸收了 Anthropic skill-creator 的迭代和 benchmark 思路，同时避免把产品做成单纯的 CI gate 或本地调试工具。
