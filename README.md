# SkillsEval

第三方独立 Skills 评测与选型平台。当前仓库包含：

- `backend/`：FastAPI + SQLite + 本地文件存储的真实 API 服务。
- `frontend/`：Vite React TypeScript 前端。
- `prototypes/style-lab/`：前期高保真原型，仅作为视觉与交互参考。
- `docs/`：当前系统设计文档，历史产品讨论稿已归档到 `docs/archive/`。

## 本地启动

后端：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev
```

默认前端地址为 `http://localhost:5173`，后端地址为 `http://localhost:8000`。

## MVP 闭环

1. 在 `Skills 管理` 上传 Skill ZIP。
2. 后端解析 `SKILL.md` 并生成 Import Draft。
3. 用户确认 `skill_name`、`version`、`category`。
4. 系统创建 Skill、Skill Version 和 Skill 绑定的当前 Evaluation Set。
5. 在 Skill 的 Evaluation Set 页面维护 Trigger Queries 与 Effect Cases。
6. 在 `评测任务管理` 创建 Full Evaluation 任务。
7. Evaluator 执行真实 Scan、Trigger、Effect，并生成结构化证据与运行产物。
8. Overview 按 category 展示 Recommended Skills by Category。

## 当前评测模型

SkillsEval 当前按三类指标展示，不再把新任务合并为一个加权总分：

- `Scan`：静态规则扫描，输出风险、findings 和 scan score。
- `Trigger`：在配置的 Runner 下真实运行 trigger queries，判断 Skill 是否按预期触发。
- `Effect`：运行 with-skill 与 baseline，对 assertions 做确定性判定和 LLM Judge 判定，并展示质量提升与成本效率证据。

Runner 是被测运行环境；Effect Judge 使用 `系统设置` 中配置的全局裁判模型，不使用 Runner 里的模型作为裁判。

系统设计入口见 `docs/README.md`。
