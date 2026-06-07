const variants = {
  a: {
    name: "Civic Ledger",
    subtitle: "公共评测报告感，清晰、稳重、可信，适合对外展示榜单和证据。",
    accent: "Evidence-first overview",
    bodyClass: "style-a",
  },
  b: {
    name: "Command Graph",
    subtitle: "深色技术控制台，密度高，适合测试人员盯任务、队列和 runner 证据。",
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

function icon(name) {
  return `<span class="icon"><i data-lucide="${name}"></i></span>`;
}

function renderNav() {
  return `
    <div class="brand">
      <div class="brand-mark">${icon("radar")}</div>
      <div>SkillsEval</div>
    </div>
    <nav class="nav">
      <a class="nav-item active" href="#">${icon("layout-dashboard")}概览</a>
      <a class="nav-item" href="#">${icon("boxes")}Skills 管理</a>
      <a class="nav-item" href="#">${icon("clipboard-check")}评测任务管理</a>
      <a class="nav-item" href="#">${icon("settings")}设置</a>
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

function renderApp() {
  const key = document.body.dataset.variant || "a";
  const v = variants[key];
  document.body.className = v.bodyClass;
  document.title = `SkillsEval Prototype - ${v.name}`;
  document.body.innerHTML = `
    <div class="app-shell">
      <aside class="sidebar">${renderNav()}</aside>
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
          <div class="stat"><span>Evaluated Skills</span><strong>128</strong><small>24 categories covered</small></div>
          <div class="stat"><span>Complete Reports</span><strong>87</strong><small>four-stage reports ready</small></div>
          <div class="stat"><span>Category Coverage</span><strong>76%</strong><small>18 of 24 have ready benchmark</small></div>
          <div class="stat"><span>Avg Confidence</span><strong>91%</strong><small>sample size and freshness weighted</small></div>
        </section>

        <section class="overview-board">
          <div class="panel">
            <div class="panel-header">
              <div>
                <h2>Top 10 Skills by Category</h2>
                <p>Data & Analytics category · public overview ranking · updated 09:20</p>
              </div>
              <span class="pill">${icon("badge-check")}sample size 42 · confidence 91%</span>
            </div>
            <div class="category-list">${topSkillsRows()}</div>
          </div>
        </section>
      </main>
    </div>
  `;
  if (window.lucide) window.lucide.createIcons();
}

document.addEventListener("DOMContentLoaded", renderApp);
