# SkillsEval

第三方独立 Skills 评测与选型平台。当前仓库包含：

- `backend/`：FastAPI + SQLite + 本地文件存储的真实 API 服务。
- `frontend/`：Vite React TypeScript 前端。
- `prototypes/style-lab/`：前期高保真原型，仅作为视觉与交互参考。
- `docs/`：产品与系统设计文档。

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
7. 模拟 worker 生成四阶段结果、overall_score、suggestions 和评测证据。
8. Overview 按 category 展示 Top 10 Skills by Category。
