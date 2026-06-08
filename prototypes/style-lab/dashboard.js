const variants = {
  a: {
    name: "Civic Ledger",
    subtitle: "公共评测报告感，清晰、稳重、可信，适合对外展示榜单和证据。",
    accent: "Evidence-first overview",
    bodyClass: "style-a",
  },
  b: {
    name: "Command Graph",
    subtitle: "深色技术控制台，密度高，适合测试人员盯任务、队列和执行日志。",
    accent: "Telemetry-heavy command view",
    bodyClass: "style-b",
  },
  c: {
    name: "Product Cloud",
    subtitle: "现代 SaaS 风格，轻量、明亮、产品化，适合第一版 Web app。",
    accent: "Friendly marketplace surface",
    bodyClass: "style-c",
  },
  d: {
    name: "Operator Atlas",
    subtitle: "更有品牌感的评测地图，左侧深色导航，右侧高对比信息卡。",
    accent: "Curated ranking atlas",
    bodyClass: "style-d",
  },
};

const topSkills = [
  ["1", "analytical-report", "Data & Analytics · v1.2.0", "95.6", "98", "92", "评测集 2/3 ready"],
  ["2", "pdf-form-auditor", "Documents · v0.9.4", "93.8", "94", "91", "1 critical fixed"],
  ["3", "sheet-reconcile", "Spreadsheets · v2.1.0", "91.4", "90", "88", "low cost delta"],
  ["4", "code-review-pack", "Developer Tools · v1.0.7", "90.5", "86", "93", "trigger stable"],
  ["5", "workflow-summarizer", "Ops · v1.4.2", "89.7", "91", "84", "needs perf run"],
  ["6", "contract-clause-check", "Legal · v0.8.8", "88.9", "83", "90", "review required"],
  ["7", "market-research-brief", "Research · v1.3.1", "87.6", "89", "82", "fresh 2h ago"],
  ["8", "ppt-structure-polish", "Presentations · v1.1.0", "86.8", "85", "81", "suite draft"],
  ["9", "ticket-triage-agent", "Support · v0.7.6", "85.9", "82", "87", "10 hard negatives"],
  ["10", "image-alt-text", "Accessibility · v1.0.0", "84.7", "88", "79", "cost efficient"],
];

const managedSkills = [
  {
    packageName: "analytical-report",
    title: "Analytical Report",
    category: "Data & Analytics",
    version: "1.2.0",
    score: "95.6",
    stage: ["98", "94", "96", "88"],
    status: "Report Ready",
    risk: "No critical risk",
    updated: "Today 09:20",
    summary: "Generates metric narratives, variance explanations, and table-backed report sections from spreadsheet inputs.",
  },
  {
    packageName: "sheet-reconcile",
    title: "Sheet Reconcile",
    category: "Data & Analytics",
    version: "2.1.0",
    score: "91.4",
    stage: ["93", "90", "92", "84"],
    status: "Evaluating",
    risk: "External file access reviewed",
    updated: "Today 08:10",
    summary: "Compares two spreadsheet snapshots and explains row-level deltas for finance and operations workflows.",
  },
  {
    packageName: "market-research-brief",
    title: "Market Research Brief",
    category: "Research & Web",
    version: "1.3.1",
    score: "87.6",
    stage: ["89", "86", "88", "79"],
    status: "Report Ready",
    risk: "Needs source citation review",
    updated: "Yesterday",
    summary: "Collects source-backed competitive research and assembles a concise market brief.",
  },
  {
    packageName: "pdf-form-auditor",
    title: "PDF Form Auditor",
    category: "Documents & Knowledge",
    version: "0.9.4",
    score: "93.8",
    stage: ["94", "91", "95", "83"],
    status: "Review Required",
    risk: "1 critical fixed in v0.9.4",
    updated: "Jun 07",
    summary: "Reads PDF forms, checks required fields, and produces completion-risk summaries.",
  },
  {
    packageName: "code-review-pack",
    title: "Code Review Pack",
    category: "Developer Tools",
    version: "1.0.7",
    score: "90.5",
    stage: ["86", "93", "91", "82"],
    status: "Report Ready",
    risk: "Bash scope limited",
    updated: "Jun 06",
    summary: "Reviews pull requests for test gaps, dependency risks, and maintainability findings.",
  },
];

const evalSets = [
  ["Data analysis regression", "Skill-owned", "Ready", "24 cases"],
  ["Data & Analytics benchmark", "Category", "Ready", "42 cases"],
  ["Spreadsheet edge cases", "Skill-owned", "Draft", "8 cases"],
];

const runHistory = [
  ["run_2481", "Full evaluation", "Completed", "95.6", "Today 09:20"],
  ["run_2418", "Trigger + effect", "Completed", "93.2", "Jun 07"],
  ["run_2304", "Static scan", "Completed", "98.0", "Jun 05"],
];

function icon(name) {
  return `<span class="icon"><i data-lucide="${name}"></i></span>`;
}

function renderNav(active = "overview") {
  return `
    <div class="brand">
      <div class="brand-mark">${icon("radar")}</div>
      <div>SkillsEval</div>
    </div>
    <nav class="nav">
      <a class="nav-item ${active === "overview" ? "active" : ""}" href="./product-cloud.html">${icon("layout-dashboard")}概览</a>
      <a class="nav-item ${active === "skills" ? "active" : ""}" href="./product-cloud-skills.html">${icon("boxes")}Skills 管理</a>
      <a class="nav-item" href="#">${icon("clipboard-check")}评测任务管理</a>
      <a class="nav-item" href="#">${icon("settings")}系统设置</a>
    </nav>
    <div class="side-block">
      <h3>Freshness</h3>
      <strong>92%</strong>
      <small>完整报告在 7 天内完成复评</small>
    </div>
    <div class="side-block">
      <h3>Policy</h3>
      <strong>4</strong>
      <small>skills 标记为 review required</small>
    </div>
  `;
}

function topSkillsRows() {
  return topSkills.map(([rank, name, meta, score, trigger, effect, note]) => `
    <div class="category-row">
      <div class="rank">${rank}</div>
      <div>
        <div class="skill-name">${name}</div>
        <div class="skill-meta">${meta}</div>
      </div>
      <div>
        <div class="score">${score}</div>
        <div class="skill-meta">overall</div>
      </div>
      <div class="hide-sm">
        <div class="score">${trigger}</div>
        <div class="skill-meta">trigger</div>
      </div>
      <div class="hide-sm">
        <div class="score">${effect}</div>
        <div class="skill-meta">effect</div>
      </div>
      <div class="hide-sm">
        <span class="pill">${note}</span>
      </div>
    </div>
  `).join("");
}

function stageBlock([staticScore, triggerScore, effectScore, performanceScore]) {
  return [
    ["Static scan", staticScore],
    ["Trigger eval", triggerScore],
    ["Effect eval", effectScore],
    ["Performance", performanceScore],
  ].map(([label, value]) => `
    <div class="stage">
      <b>${label}</b>
      <div class="meter"><i style="--w:${value}%"></i></div>
      <strong>${value}</strong>
    </div>
  `).join("");
}

function statusPill(status) {
  const key = status.toLowerCase().replaceAll(" ", "-");
  return `<span class="status-pill status-${key}">${status}</span>`;
}

function skillListRows() {
  return managedSkills.map((skill, index) => `
    <button class="skill-list-row ${index === 0 ? "selected" : ""}" type="button">
      <span class="skill-row-main">
        <strong>${skill.packageName}</strong>
        <small>${skill.category} · v${skill.version}</small>
      </span>
      <span class="skill-row-score">${skill.score}</span>
    </button>
  `).join("");
}

function evidenceRows() {
  return [
    ["report.md", "Human-readable summary", "ready"],
    ["grading.json", "Case-level grading", "ready"],
    ["timing.json", "Latency and token usage", "ready"],
    ["benchmark.json", "With-skill benchmark", "ready"],
  ].map(([name, desc, state]) => `
    <div class="evidence-row">
      <div>${icon("file-check-2")}<span><strong>${name}</strong><small>${desc}</small></span></div>
      <span class="pill">${state}</span>
    </div>
  `).join("");
}

function renderSkillsManagement(v) {
  const selected = managedSkills[0];
  return `
    <div class="app-shell">
      <aside class="sidebar">${renderNav("skills")}</aside>
      <main class="main">
        <header class="topbar">
          <div class="title">
            <h1>Skills 管理</h1>
            <p>按 package_name 管理 skill、版本、评测集和最近评测结论。</p>
          </div>
          <div class="actions">
            <span class="pill">${icon("tag")}category 手动选择</span>
            <button class="btn">${icon("sliders-horizontal")}筛选</button>
            <button class="btn primary">${icon("upload-cloud")}上传 Skill</button>
          </div>
        </header>

        <section class="skills-layout">
          <aside class="skills-rail panel">
            <div class="panel-header compact">
              <div>
                <h2>All Skills</h2>
                <p>186 packages · 12 categories</p>
              </div>
            </div>
            <div class="filter-strip">
              <span class="chip active">Data & Analytics</span>
              <span class="chip">Documents</span>
              <span class="chip">Developer</span>
            </div>
            <div class="skill-list">${skillListRows()}</div>
          </aside>

          <section class="skill-workspace">
            <div class="skill-hero panel">
              <div class="skill-hero-main">
                <div class="package-mark">${icon("package-check")}</div>
                <div>
                  <span class="eyebrow">package_name</span>
                  <h2>${selected.packageName}</h2>
                  <p>${selected.summary}</p>
                  <div class="tag-row">
                    <span class="pill">${selected.category}</span>
                    <span class="pill">v${selected.version}</span>
                    ${statusPill(selected.status)}
                  </div>
                </div>
              </div>
              <div class="hero-score">
                <span>overall_score</span>
                <strong>${selected.score}</strong>
                <small>${selected.updated}</small>
              </div>
            </div>

            <div class="detail-grid">
              <div class="panel">
                <div class="panel-header">
                  <div>
                    <h2>四阶段评测</h2>
                    <p>榜单展示 overall 与阶段分，不展示 confidence。</p>
                  </div>
                </div>
                <div class="stage-stack">${stageBlock(selected.stage)}</div>
              </div>

              <div class="panel">
                <div class="panel-header">
                  <div>
                    <h2>关键风险</h2>
                    <p>critical 不阻断榜单，但必须显著展示。</p>
                  </div>
                </div>
                <div class="risk-list">
                  <div class="risk-row low">${icon("shield-check")}<span><strong>No critical risk</strong><small>Static scan passed required policy checks.</small></span></div>
                  <div class="risk-row warn">${icon("triangle-alert")}<span><strong>External endpoint noted</strong><small>Endpoint is documented and limited to read-only data fetch.</small></span></div>
                </div>
              </div>
            </div>

            <div class="panel">
              <div class="panel-header">
                <div>
                  <h2>Evaluation Sets</h2>
                  <p>评测集在当前 skill 下管理，不做一级菜单。</p>
                </div>
                <button class="btn">${icon("plus")}生成草稿</button>
              </div>
              <div class="data-table">
                ${evalSets.map(([name, scope, status, cases]) => `
                  <div class="data-row">
                    <strong>${name}</strong>
                    <span>${scope}</span>
                    <span>${cases}</span>
                    ${statusPill(status)}
                  </div>
                `).join("")}
              </div>
            </div>
          </section>

          <aside class="detail-side">
            <div class="panel">
              <div class="panel-header compact">
                <div>
                  <h2>Versions</h2>
                  <p>同一 package_name 下追踪版本。</p>
                </div>
              </div>
              <div class="timeline">
                <div class="time-row current"><strong>v1.2.0</strong><span>Current · score 95.6</span></div>
                <div class="time-row"><strong>v1.1.0</strong><span>score 92.4</span></div>
                <div class="time-row"><strong>v1.0.0</strong><span>score 89.8</span></div>
              </div>
            </div>

            <div class="panel">
              <div class="panel-header compact">
                <div>
                  <h2>Recent Runs</h2>
                  <p>进入报告和复核。</p>
                </div>
              </div>
              <div class="run-list">
                ${runHistory.map(([id, type, status, score, date]) => `
                  <div class="run-row">
                    <div><strong>${id}</strong><small>${type} · ${date}</small></div>
                    <div><span>${score}</span>${statusPill(status)}</div>
                  </div>
                `).join("")}
              </div>
            </div>

            <div class="panel">
              <div class="panel-header compact">
                <div>
                  <h2>评测证据</h2>
                  <p>面向用户展示 evidence。</p>
                </div>
              </div>
              <div class="evidence-list">${evidenceRows()}</div>
            </div>
          </aside>
        </section>
      </main>
    </div>
  `;
}

function renderOverview(v) {
  return `
    <div class="app-shell">
      <aside class="sidebar">${renderNav("overview")}</aside>
      <main class="main">
        <header class="topbar">
          <div class="title">
            <h1>${v.name}</h1>
            <p>${v.subtitle}</p>
          </div>
          <div class="actions">
            <span class="pill">${v.accent}</span>
            <button class="btn">${icon("download")}导出榜单</button>
            <button class="btn primary">${icon("book-open-check")}查看评测标准</button>
          </div>
        </header>

        <section class="stat-grid">
          <div class="stat"><span>Skills 总数</span><strong>186</strong><small>覆盖 12 个推荐分类</small></div>
          <div class="stat"><span>已评测 Skills 数</span><strong>128</strong><small>完成四阶段报告</small></div>
          <div class="stat"><span>评测任务数量</span><strong>342</strong><small>含历史任务和复评任务</small></div>
          <div class="stat"><span>用户数量</span><strong>48</strong><small>选型用户、测试人员、运营人员</small></div>
        </section>

        <section class="overview-board">
          <div class="panel">
            <div class="panel-header">
              <div>
                <h2>Top 10 Skills by Category</h2>
                <p>Data & Analytics category · ranked by overall_score · updated 09:20</p>
              </div>
              <span class="pill">${icon("badge-check")}sample size 42 · last evaluated today</span>
            </div>
            <div class="category-list">${topSkillsRows()}</div>
          </div>
        </section>
      </main>
    </div>
  `;
}

function renderApp() {
  const key = document.body.dataset.variant || "a";
  const page = document.body.dataset.page || "overview";
  const v = variants[key];
  document.body.className = v.bodyClass;
  document.title = page === "skills" ? "SkillsEval Prototype - Product Cloud Skills" : `SkillsEval Prototype - ${v.name}`;
  document.body.innerHTML = page === "skills" ? renderSkillsManagement(v) : renderOverview(v);
  if (window.lucide) window.lucide.createIcons();
}

document.addEventListener("DOMContentLoaded", renderApp);
