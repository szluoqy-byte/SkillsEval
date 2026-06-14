# SkillsEval 设计文档目录

本目录存放 SkillsEval 当前真实系统的中文详细设计说明。早期产品探索、用户旅程草稿和旧评分模型不再保留在主仓库文档中。

## 推荐阅读顺序

1. `system-architecture.md`
   - 系统架构详细设计。
   - 包含产品边界、前后端模块、主流程、页面交互、Runner/模型/Judge 边界、安全隔离与后续演进。

2. `domain-model-and-api.md`
   - 领域模型与 API 设计。
   - 包含 SQLite 表、关键对象、API 分组、artifact 目录和前端数据映射。

3. `evaluation-design.md`
   - 评测体系详细设计。
   - 包含 Scan / Trigger / Effect 三类指标、任务执行链路、推荐策略、result_summary、证据展示方式。

4. `static-scan-rules-design.md`
   - 静态扫描规则详细设计。
   - 逐条说明当前 53 条规则的触发条件、严重级别、风险说明和修复建议。

5. `effect-eval-design.md`
   - Effect 评测详细设计。
   - 包含 with-skill/baseline、assertion DSL、LLM Judge、成本效率指标和 artifact 结构。

## 当前系统快照

当前 SkillsEval 已从高保真原型演进为本地真实前后端系统：

- 前端：`frontend/`，React + Vite + TypeScript。
- 后端：`backend/app/`，FastAPI + SQLite + 本地文件存储。
- 数据库：`data/skilleval.db`。
- 文件产物：`data/imports/`、`data/uploads/`、`data/runs/`、`data/workspaces/`。
- 评测模型：`Scan`、`Trigger`、`Effect` 三类指标独立展示。
- Runner 边界：Runner 是被测运行环境，当前已实现 `opencode_cli` adapter。
- Judge 边界：Effect LLM Judge 使用系统设置中的全局裁判模型，不使用 Runner 模型。

## 文档维护原则

- 主目录文档只描述当前系统设计。
- 文档内容只维护当前口径，避免混入已废弃的旧模型。
- 规则类文档需要逐条说明规则，不只写规则组。
- 架构类文档需要覆盖主流程和用户交互，而不只是模块列表。
- 变更实现后，应同步更新相关设计文档。
