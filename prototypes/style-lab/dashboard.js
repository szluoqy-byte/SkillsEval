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

const defaultManagedSkills = [
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
  ["Data analysis regression", "Bound to skill", "Ready", "24 cases"],
  ["Spreadsheet edge cases", "Bound to skill", "Draft", "8 cases"],
  ["Executive report rubric", "Bound to skill", "Ready", "12 cases"],
];

let managedSkills = loadManagedSkills();

const versionResults = [
  ["v1.2.0", "95.6", "98", "94", "96", "88", "+21%", "$1.42", "Recommended"],
  ["v1.1.0", "92.4", "96", "90", "93", "84", "+17%", "$1.31", "Recommended"],
  ["v1.0.0", "89.8", "93", "88", "89", "82", "+11%", "$1.18", "Usable"],
];

let evaluationTasks = [
  ["task_2481", "analytical-report", "Claude Code + MiniMax 2.7", "Completed", "95.6", "Today 09:20"],
  ["task_2482", "sheet-reconcile", "Codex Runner + GPT-5", "Running", "—", "Started 09:42"],
  ["task_2479", "pdf-form-auditor", "Claude Code + MiniMax 2.7", "Review Pending", "93.8", "Jun 07"],
  ["task_2471", "market-research-brief", "Local CLI + Qwen3 Coder", "Failed", "87.6", "Jun 07"],
];

const taskDetail = {
  id: "task_2481",
  skill: "analytical-report",
  version: "v1.2.0",
  status: "Completed",
  score: "95.6",
  runner: "Claude Code + MiniMax 2.7",
  suite: "analytical-report current suite",
  started: "Today 09:03",
  finished: "Today 09:20",
};

const methodCards = [
  ["Static scan", "System preset rules", "Structure, security, permissions, supply chain, prompt safety", "98"],
  ["Trigger eval", "Positive / negative queries", "Runs each query 3 times and checks activation rate", "94"],
  ["Effect eval", "With-skill / without-skill", "Grades deterministic assertions first, then LLM judge where needed", "96"],
  ["Performance", "Cost and latency", "Compares token, tool-call, latency, and quality lift tradeoff", "88"],
];

const runMetrics = [
  ["overall_score", "95.6", "Weighted product score"],
  ["skill_lift", "+21%", "with-skill vs without-skill"],
  ["trigger pass", "42 / 44", "positive, negative, hard negative"],
  ["cost", "$1.42", "estimated full run cost"],
];

const staticFindings = [
  ["STR-011", "Info", "Description is short but valid", "SKILL.md:4"],
  ["SEC-002", "Warning", "External read-only endpoint should be documented", "references/api.md:18"],
  ["PERM-002", "Info", "High-risk tool declared with scoped usage", "SKILL.md:8"],
];

const triggerResults = [
  ["Positive", "请根据这份 CSV 生成指标波动分析报告", "3 / 3", "100%", "Passed"],
  ["Positive", "把销售表格转成管理层摘要和异常解释", "3 / 3", "100%", "Passed"],
  ["Negative", "帮我润色一封客户邮件", "0 / 3", "0%", "Passed"],
  ["Hard negative", "解释这张图表的视觉风格", "1 / 3", "33%", "Needs Review"],
];

const effectResults = [
  ["case_014", "Quarterly revenue variance", "100%", "67%", "+33%", "deterministic + judge"],
  ["case_018", "Missing metric column", "75%", "50%", "+25%", "schema assertion"],
  ["case_021", "Cost center rollup", "100%", "83%", "+17%", "LLM judge"],
  ["case_024", "Ambiguous benchmark baseline", "58%", "67%", "-9%", "deterministic"],
];

const performanceResults = [
  ["mean latency", "48s", "+9s", "Acceptable"],
  ["mean tokens", "18.4k", "+2.1k", "Watch"],
  ["tool calls", "5.2", "+1.4", "Expected"],
  ["tokens / passed assertion", "612", "-18%", "Efficient"],
];

let triggerQueries = [
  { query: "帮我检查这个客服大模型评测集的质量", should_trigger: true },
  { query: "分析这批鲁棒性测试样本的通过率变化", should_trigger: true },
  { query: "把这段中文翻译成英文", should_trigger: false },
  { query: "帮我写一个周报标题", should_trigger: false },
];

let effectCases = [
  {
    id: "evalset-quality-check",
    prompt: "检查 files/customer_service_evalset.xlsx 中的评测集质量，输出重复问题、缺失标准答案、类别分布不均衡的问题。",
    expected_output: "应识别重复问题、缺失标准答案，以及部分意图类别样本过少的问题，并给出整改建议。",
    files: ["files/customer_service_evalset.xlsx"],
    assertions: [
      "contains '重复'",
      "contains '缺失'",
      "contains '类别'",
      "contains '整改'",
      "does not contain '无法读取'",
    ],
  },
  {
    id: "rubustness-noise-test",
    prompt: "基于 files/noise_cases.json 对模型鲁棒性进行分析，输出噪声扰动前后的通过率变化。",
    expected_output: "应输出原始样本通过率、噪声扰动样本通过率、下降比例，并指出主要失败类型。",
    files: ["files/noise_cases.json"],
    assertions: [
      "contains '通过率'",
      "contains '噪声'",
      "contains '下降'",
      "contains '失败类型'",
    ],
  },
];

const staticScanRules = [
  ["Structure", "18", "SKILL.md, frontmatter, references, required files"],
  ["Security", "27", "secrets, unsafe commands, sensitive paths"],
  ["Permissions", "14", "tool scope, shell access, external writes"],
  ["Supply chain", "11", "remote install, unpinned packages, script fetch"],
  ["Prompt safety", "9", "prompt injection and unsafe delegation patterns"],
];

const latestSuggestions = [
  ["Trigger description", "Use this skill when the user asks for spreadsheet-backed metric narratives, variance analysis, or executive-ready analytical report sections.", "+8 hard-negative clarity"],
  ["Effect case", "Add one missing-column case where optional metrics are absent but totals can still be computed.", "+4 outcome coverage"],
  ["Static scan", "Document the read-only external endpoint in the skill instructions before the next evaluation.", "risk note"],
];

const policyDecisions = [
  ["Dynamic evaluation", "Allowed even with risk", "High-risk findings remain visible but do not block the run."],
  ["Trigger optimization", "Suggestion only", "Platform proposes wording changes without creating a new version."],
  ["LLM judge ranking", "Included", "Judge-backed scores can enter the leaderboard in MVP."],
];

function loadManagedSkills() {
  try {
    const stored = window.localStorage.getItem("skillsEval.managedSkills");
    return stored ? JSON.parse(stored) : defaultManagedSkills.map((skill) => ({ ...skill, stage: [...skill.stage] }));
  } catch {
    return defaultManagedSkills.map((skill) => ({ ...skill, stage: [...skill.stage] }));
  }
}

function saveManagedSkills() {
  try {
    window.localStorage.setItem("skillsEval.managedSkills", JSON.stringify(managedSkills));
  } catch {
    // Some embedded browser sandboxes disable localStorage; CRUD still works in memory.
  }
}

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
      <a class="nav-item ${active === "tasks" ? "active" : ""}" href="./product-cloud-tasks.html">${icon("clipboard-check")}评测任务管理</a>
      <a class="nav-item" href="#">${icon("settings")}系统设置</a>
    </nav>
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

function tabs(active, skill) {
  const suffix = skill ? `?skill=${encodeURIComponent(skill.packageName)}` : "";
  const items = [
    ["summary", "Summary", `./product-cloud-skills.html${suffix}`],
    ["evalsets", "Evaluation Sets", `./product-cloud-eval-sets.html${suffix}`],
  ];
  return `
    <nav class="tabbar">
      ${items.map(([key, label, href]) => `<a class="tab ${active === key ? "active" : ""}" href="${href}">${label}</a>`).join("")}
    </nav>
  `;
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

function compactPolicyRows() {
  return policyDecisions.map(([name, value, desc]) => `
    <div class="policy-row">
      <div>${icon("check-circle-2")}<span><strong>${name}</strong><small>${desc}</small></span></div>
      <span class="pill">${value}</span>
    </div>
  `).join("");
}

function versionResultRows() {
  return versionResults.map(([version, overall, staticScore, trigger, effect, performance, lift, cost, status]) => `
    <div class="version-result-row">
      <strong>${version}</strong>
      <span class="score">${overall}</span>
      <span>${staticScore}</span>
      <span>${trigger}</span>
      <span>${effect}</span>
      <span>${performance}</span>
      <span>${lift}</span>
      <span>${cost}</span>
      ${statusPill(status)}
    </div>
  `).join("");
}

function latestSuggestionRows() {
  return latestSuggestions.map(([type, suggestion, impact]) => `
    <div class="suggestion-row">
      <span>${type}</span>
      <strong>${suggestion}</strong>
      <em>${impact}</em>
    </div>
  `).join("");
}

function triggerQueryRows() {
  return triggerQueries.map(({ query, should_trigger }, index) => `
    <div class="case-row">
      <span class="case-kind">${should_trigger ? "true" : "false"}</span>
      <strong>${query}</strong>
      <span>${should_trigger ? "should_trigger" : "should_not_trigger"}</span>
      <div class="row-actions">
        <button class="icon-btn" type="button" data-eval-action="edit-trigger" data-index="${index}" aria-label="编辑 trigger query">${icon("square-pen")}</button>
        <button class="icon-btn danger" type="button" data-eval-action="delete-trigger" data-index="${index}" aria-label="删除 trigger query">${icon("trash-2")}</button>
      </div>
    </div>
  `).join("");
}

function effectCaseRows() {
  return effectCases.map(({ id, prompt, expected_output, files, assertions }, index) => `
    <div class="case-row effect-definition-row">
      <span class="case-id">${id}</span>
      <div>
        <strong>${prompt}</strong>
        <small>expected_output: ${expected_output}</small>
      </div>
      <span>${files.length} files</span>
      <span>${assertions.length} assertions</span>
      <div class="row-actions">
        <button class="icon-btn" type="button" data-eval-action="edit-effect" data-index="${index}" aria-label="编辑 effect case">${icon("square-pen")}</button>
        <button class="icon-btn danger" type="button" data-eval-action="delete-effect" data-index="${index}" aria-label="删除 effect case">${icon("trash-2")}</button>
      </div>
    </div>
  `).join("");
}

function selectedSkillFromUrl() {
  const packageName = new URLSearchParams(window.location.search).get("skill");
  return packageName ? managedSkills.find((skill) => skill.packageName === packageName) : null;
}

function skillCards() {
  return managedSkills.map((skill) => `
    <article class="skill-card">
      <a class="skill-card-main" href="./product-cloud-skills.html?skill=${encodeURIComponent(skill.packageName)}" aria-label="查看 ${skill.packageName} 详情">
        <div class="skill-card-top">
          <div class="package-mark">${icon("package")}</div>
          <div>
            <span class="eyebrow">skill_name</span>
            <h2>${skill.packageName}</h2>
          </div>
        </div>
        <p>${skill.summary}</p>
        <div class="tag-row">
          <span class="pill">${skill.category}</span>
          <span class="pill">v${skill.version}</span>
          ${statusPill(skill.status)}
        </div>
      </a>
      <div class="skill-card-footer">
        <div>
          <span>overall</span>
          <strong>${skill.score}</strong>
        </div>
        <div>
          <span>updated</span>
          <strong>${skill.updated}</strong>
        </div>
        <div class="card-actions">
          <button class="icon-btn" type="button" data-skill-action="edit" data-skill="${skill.packageName}" title="编辑 ${skill.packageName}" aria-label="编辑 ${skill.packageName}">${icon("square-pen")}</button>
          <button class="icon-btn" type="button" data-skill-action="duplicate" data-skill="${skill.packageName}" title="复制 ${skill.packageName}" aria-label="复制 ${skill.packageName}">${icon("copy")}</button>
          <button class="icon-btn danger" type="button" data-skill-action="delete" data-skill="${skill.packageName}" title="删除 ${skill.packageName}" aria-label="删除 ${skill.packageName}">${icon("trash-2")}</button>
        </div>
      </div>
    </article>
  `).join("");
}

function renderSkillCards(v) {
  return `
    <div class="app-shell">
      <aside class="sidebar">${renderNav("skills")}</aside>
      <main class="main">
        <header class="topbar">
          <div class="title">
            <h1>Skills 管理</h1>
            <p>按 skill_name 管理 skill、版本、评测集和最近评测结论。</p>
          </div>
          <div class="actions">
            <span class="pill">${icon("tag")}category 手动选择</span>
            <button class="btn">${icon("sliders-horizontal")}筛选</button>
            <button class="btn">${icon("search")}搜索</button>
            <button class="btn primary" data-skill-action="create">${icon("plus")}新建 Skill</button>
          </div>
        </header>

        <section class="skill-workspace">
          <div class="management-summary">
            <div class="stat"><span>skills</span><strong>186</strong><small>按 skill_name 管理</small></div>
            <div class="stat"><span>ready</span><strong>128</strong><small>已有完整评测报告</small></div>
            <div class="stat"><span>needs review</span><strong>4</strong><small>风险可见但不阻断评测</small></div>
            <div class="stat"><span>draft suites</span><strong>11</strong><small>等待补齐 case</small></div>
          </div>

          <div class="filter-strip card-filter">
            <span class="chip active">Data & Analytics</span>
            <span class="chip">Documents</span>
            <span class="chip">Developer Tools</span>
            <span class="chip">Research & Web</span>
            <span class="chip">Review Required</span>
          </div>

          <section class="skill-card-grid" aria-label="Skills cards">
            ${skillCards()}
          </section>
        </section>
      </main>
    </div>
  `;
}

function renderSkillDetail(v, selected) {
  return `
    <div class="app-shell">
      <aside class="sidebar">${renderNav("skills")}</aside>
      <main class="main">
        <header class="topbar">
          <div class="title">
            <a class="back-link" href="./product-cloud-skills.html">${icon("arrow-left")}Skills 管理</a>
            <h1>${selected.packageName}</h1>
            <p>Skill detail · 版本评测结果、评测集、风险和评测证据。</p>
          </div>
          <div class="actions">
            <button class="btn" data-skill-action="edit" data-skill="${selected.packageName}">${icon("square-pen")}编辑</button>
            <button class="btn" data-skill-action="delete" data-skill="${selected.packageName}">${icon("trash-2")}删除</button>
            <button class="btn primary">${icon("play")}Run Evaluation</button>
          </div>
        </header>

        <section class="skill-detail-layout">
          <section class="skill-workspace">
            ${tabs("summary", selected)}
            <div class="skill-hero panel">
              <div class="skill-hero-main">
                <div class="package-mark">${icon("package-check")}</div>
                <div>
                  <span class="eyebrow">skill_name</span>
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

            <div class="panel">
              <div class="panel-header">
                <div>
                  <h2>版本评测结果</h2>
                  <p>每个版本展示总分、四阶段关键指标、skill lift 和成本。</p>
                </div>
                <span class="pill">${icon("badge-check")}latest v${selected.version}</span>
              </div>
              <div class="version-result-table">
                <div class="version-result-row header">
                  <span>Version</span>
                  <span>Overall</span>
                  <span>Static</span>
                  <span>Trigger</span>
                  <span>Effect</span>
                  <span>Perf</span>
                  <span>Lift</span>
                  <span>Cost</span>
                  <span>Status</span>
                </div>
                ${versionResultRows()}
              </div>
            </div>

            <div class="panel">
              <div class="panel-header">
                <div>
                  <h2>最新评测建议</h2>
                  <p>来自当前最新版本最近一次评测任务的 suggestion 结果。</p>
                </div>
                <span class="pill">${icon("sparkles")}v${selected.version} · latest run</span>
              </div>
              <div class="suggestion-list">${latestSuggestionRows()}</div>
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

          </section>

          <aside class="detail-side">
            <div class="panel">
              <div class="panel-header compact">
                <div>
                  <h2>Versions</h2>
                  <p>同一 skill_name 下追踪版本。</p>
                </div>
              </div>
              <div class="timeline">
                ${versionResults.map(([version, overall, staticScore, trigger, effect, performance]) => `
                  <div class="time-row ${version === `v${selected.version}` ? "current" : ""}">
                    <strong>${version}</strong>
                    <span>overall ${overall} · S ${staticScore} / T ${trigger} / E ${effect} / P ${performance}</span>
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

function renderSkillsManagement(v) {
  const selected = selectedSkillFromUrl();
  return selected ? renderSkillDetail(v, selected) : renderSkillCards(v);
}

function renderEvaluationSets(v) {
  const selected = selectedSkillFromUrl() || managedSkills[0];
  return `
    <div class="app-shell">
      <aside class="sidebar">${renderNav("skills")}</aside>
      <main class="main">
        <header class="topbar">
          <div class="title">
            <h1>Evaluation Sets</h1>
            <p>${selected.packageName} · 维护当前 Skill 绑定的 trigger queries 和 effect cases 定义。</p>
          </div>
          <div class="actions">
            <span class="pill">${icon("link")}skill-bound suite</span>
            <a class="btn primary" href="./product-cloud-tasks.html" data-link>${icon("play")}新建评测任务</a>
          </div>
        </header>

        <section class="skill-workspace">
          ${tabs("evalsets", selected)}

          <div class="panel">
            <div class="panel-header">
              <div>
                <h2>AWS 静态扫描规则</h2>
                <p>系统预置规则，只读不可修改；当前评测集读取规则数量用于静态扫描。</p>
              </div>
              <span class="pill">${icon("lock")}system preset</span>
            </div>
            <div class="rules-grid">
              ${staticScanRules.map(([group, count, desc]) => `
                <div class="rule-card">
                  <span>${group}</span>
                  <strong>${count}</strong>
                  <small>${desc}</small>
                </div>
              `).join("")}
            </div>
          </div>

          <div class="eval-case-layout">
            <div class="panel">
              <div class="panel-header">
                <div>
                <h2>Trigger Queries</h2>
                <p>定义 query 与 should_trigger，运行后的 trigger rate 在任务详情中查看。</p>
              </div>
                <div class="panel-actions">
                  <button class="btn" data-eval-action="generate-trigger">${icon("sparkles")}辅助生成</button>
                  <button class="btn" data-eval-action="import-trigger">${icon("file-input")}导入</button>
                  <button class="btn" data-eval-action="add-trigger">${icon("plus")}新增</button>
                </div>
              </div>
              <div class="case-table">
                ${triggerQueryRows()}
              </div>
            </div>

            <div class="panel">
              <div class="panel-header">
                <div>
                  <h2>Effect Cases</h2>
                  <p>每个 case 绑定 id、prompt、expected_output、files 和 assertions；assertions 先走确定性规则，识别不了再交给 LLM Judge。</p>
                </div>
                <div class="panel-actions">
                  <button class="btn" data-eval-action="generate-effect">${icon("sparkles")}辅助生成</button>
                  <button class="btn" data-eval-action="import-effect">${icon("file-input")}导入</button>
                  <button class="btn" data-eval-action="add-effect">${icon("plus")}新增</button>
                </div>
              </div>
              <div class="case-table wide">
                ${effectCaseRows()}
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  `;
}

function taskRows() {
  return evaluationTasks.map(([id, skill, runner, status, score, time]) => `
    <a class="task-row" href="./product-cloud-task-detail.html?task=${encodeURIComponent(id)}">
      <div><strong>${id}</strong><small>${skill}</small></div>
      <span>${runner}</span>
      ${statusPill(status)}
      <strong>${score}</strong>
      <span>${time}</span>
    </a>
  `).join("");
}

function methodCardRows() {
  return methodCards.map(([stage, method, detail, score]) => `
    <div class="method-card">
      <span>${stage}</span>
      <strong>${method}</strong>
      <small>${detail}</small>
      <b>${score}</b>
    </div>
  `).join("");
}

function runMetricRows() {
  return runMetrics.map(([name, value, desc]) => `
    <div class="stat"><span>${name}</span><strong>${value}</strong><small>${desc}</small></div>
  `).join("");
}

function staticFindingRows() {
  return staticFindings.map(([code, severity, title, location]) => `
    <div class="finding-row">
      <strong>${code}</strong>
      <span>${severity}</span>
      <div>${title}<small>${location}</small></div>
    </div>
  `).join("");
}

function triggerResultRows() {
  return triggerResults.map(([kind, query, count, rate, status]) => `
    <div class="trigger-result-row">
      <span>${kind}</span>
      <strong>${query}</strong>
      <b>${count}</b>
      <b>${rate}</b>
      ${statusPill(status)}
    </div>
  `).join("");
}

function effectResultRows() {
  return effectResults.map(([id, name, withSkill, withoutSkill, lift, method]) => `
    <div class="effect-result-row">
      <strong>${id}</strong>
      <span>${name}</span>
      <b>${withSkill}</b>
      <b>${withoutSkill}</b>
      <b>${lift}</b>
      <span>${method}</span>
    </div>
  `).join("");
}

function performanceResultRows() {
  return performanceResults.map(([metric, value, delta, status]) => `
    <div class="performance-row">
      <strong>${metric}</strong>
      <span>${value}</span>
      <b>${delta}</b>
      <span class="pill">${status}</span>
    </div>
  `).join("");
}

function renderEvaluationTasks(v) {
  return `
    <div class="app-shell">
      <aside class="sidebar">${renderNav("tasks")}</aside>
      <main class="main">
        <header class="topbar">
          <div class="title">
            <h1>评测任务管理</h1>
            <p>集中管理评测队列、运行状态和历史任务，不归属于 Skill 详情页。</p>
          </div>
          <div class="actions">
            <button class="btn">${icon("sliders-horizontal")}筛选</button>
            <button class="btn">${icon("download")}导出任务</button>
            <button class="btn primary" data-task-action="create">${icon("play")}新建评测任务</button>
          </div>
        </header>

        <section class="skill-workspace">
          <div class="management-summary">
            <div class="stat"><span>queued</span><strong>12</strong><small>等待执行</small></div>
            <div class="stat"><span>running</span><strong>3</strong><small>正在评测</small></div>
            <div class="stat"><span>completed</span><strong>342</strong><small>历史任务</small></div>
            <div class="stat"><span>review</span><strong>7</strong><small>需要查看结果</small></div>
          </div>

          <div class="panel task-management-panel">
            <div class="panel-header">
              <div>
                <h2>任务队列</h2>
                <p>按任务维度查看运行状态、目标 skill、运行环境、分数和更新时间。</p>
              </div>
              <span class="pill">${icon("clock-3")}updated 09:42</span>
            </div>
            <div class="task-table">
              <div class="task-row header">
                <span>Task</span>
                <span>Runner</span>
                <span>Status</span>
                <span>Score</span>
                <span>Time</span>
              </div>
              ${taskRows()}
            </div>
          </div>
        </section>
      </main>
    </div>
  `;
}

function renderTaskDetail(v) {
  return `
    <div class="app-shell">
      <aside class="sidebar">${renderNav("tasks")}</aside>
      <main class="main">
        <header class="topbar">
          <div class="title">
            <a class="back-link" href="./product-cloud-tasks.html">${icon("arrow-left")}评测任务管理</a>
            <h1>${taskDetail.id}</h1>
            <p>${taskDetail.skill} · ${taskDetail.version} · ${taskDetail.status}</p>
          </div>
          <div class="actions">
            <span class="pill">${taskDetail.runner}</span>
            <button class="btn">${icon("download")}导出结果</button>
          </div>
        </header>

        <section class="skill-workspace">
          <div class="skill-hero panel">
            <div class="skill-hero-main">
              <div class="package-mark">${icon("clipboard-check")}</div>
              <div>
                <span class="eyebrow">evaluation run</span>
                <h2>${taskDetail.skill}</h2>
                <p>任务详情承载评估方法、阶段结果和运行证据；Skill Detail 只消费最新结论和版本汇总。</p>
                <div class="tag-row">
                  ${statusPill(taskDetail.status)}
                  <span class="pill">${taskDetail.suite}</span>
                  <span class="pill">${taskDetail.started} - ${taskDetail.finished}</span>
                </div>
              </div>
            </div>
            <div class="hero-score">
              <span>overall_score</span>
              <strong>${taskDetail.score}</strong>
              <small>latest completed run</small>
            </div>
          </div>

          <section class="run-summary-grid">
            ${runMetricRows()}
          </section>

          <div class="panel">
            <div class="panel-header">
              <div>
                <h2>评估结果</h2>
                <p>任务只展示整体状态；完成后再呈现静态扫描、触发、效果对照和性能成本结果。</p>
              </div>
            </div>
            <div class="method-grid">${methodCardRows()}</div>
          </div>

          <section class="task-detail-grid">
            <div class="panel">
              <div class="panel-header">
                <div>
                  <h2>静态扫描 Findings</h2>
                  <p>系统预置规则输出 code、severity、位置和修复方向。</p>
                </div>
              </div>
              <div class="finding-list">${staticFindingRows()}</div>
            </div>

            <div class="panel">
              <div class="panel-header">
                <div>
                  <h2>Performance</h2>
                  <p>成本和耗时只解释推荐级别，不单独压过效果结果。</p>
                </div>
              </div>
              <div class="performance-list">${performanceResultRows()}</div>
            </div>
          </section>

          <div class="panel">
            <div class="panel-header">
              <div>
                <h2>Trigger Results</h2>
                <p>每条 query 记录期望触发、实际触发次数、触发率和状态。</p>
              </div>
            </div>
            <div class="trigger-result-table">
              <div class="trigger-result-row header">
                <span>Type</span>
                <span>Query</span>
                <span>Runs</span>
                <span>Rate</span>
                <span>Status</span>
              </div>
              ${triggerResultRows()}
            </div>
          </div>

          <div class="panel">
            <div class="panel-header">
              <div>
                <h2>Effect Results</h2>
                <p>效果评测默认保留 with-skill / without-skill 对照，lift 才能进入榜单和建议。</p>
              </div>
            </div>
            <div class="effect-result-table">
              <div class="effect-result-row header">
                <span>Case</span>
                <span>Name</span>
                <span>With</span>
                <span>Without</span>
                <span>Lift</span>
                <span>Method</span>
              </div>
              ${effectResultRows()}
            </div>
          </div>

          <div class="panel">
            <div class="panel-header">
              <div>
                <h2>评测证据 / 运行产物</h2>
                <p>任务详情保存真实证据，Summary 只展示可消费结论。</p>
              </div>
            </div>
            <div class="evidence-list">${evidenceRows()}</div>
          </div>
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
  const pages = {
    overview: () => renderOverview(v),
    skills: () => renderSkillsManagement(v),
    evalsets: () => renderEvaluationSets(v),
    tasks: () => renderEvaluationTasks(v),
    taskDetail: () => renderTaskDetail(v),
  };
  const titles = {
    overview: `SkillsEval Prototype - ${v.name}`,
    skills: "SkillsEval Prototype - Product Cloud Skills",
    evalsets: "SkillsEval Prototype - Evaluation Sets",
    tasks: "SkillsEval Prototype - Evaluation Tasks",
    taskDetail: "SkillsEval Prototype - Evaluation Task Detail",
  };
  document.title = titles[page] || titles.overview;
  document.body.innerHTML = (pages[page] || pages.overview)();
  if (window.lucide) window.lucide.createIcons();
}

document.addEventListener("DOMContentLoaded", renderApp);

function findSkill(packageName) {
  return managedSkills.find((skill) => skill.packageName === packageName);
}

function showSkillEditor(skill) {
  const isEdit = Boolean(skill);
  const draft = skill || {
    packageName: "new-skill-pack",
    category: "Data & Analytics",
    version: "0.1.0",
    score: "0.0",
    stage: ["0", "0", "0", "0"],
    status: "Imported",
    risk: "Not scanned",
    updated: "Just now",
    summary: "Describe what this skill evaluates or improves.",
  };
  document.body.insertAdjacentHTML("beforeend", `
    <div class="modal-backdrop" data-modal>
      <form class="skill-modal" data-skill-form data-mode="${isEdit ? "edit" : "create"}" data-original="${skill?.packageName || ""}">
        <div class="modal-header">
          <div>
            <h2>${isEdit ? "编辑 Skill" : "新建 Skill"}</h2>
            <p>${isEdit ? draft.packageName : "创建后会出现在卡片管理页中。"}</p>
          </div>
          <button class="icon-btn" type="button" data-modal-close aria-label="关闭">${icon("x")}</button>
        </div>
        <label>skill_name<input name="packageName" value="${draft.packageName}" required></label>
        <label>Category<input name="category" value="${draft.category}" required></label>
        <div class="form-grid">
          <label>Version<input name="version" value="${draft.version}" required></label>
          <label>Score<input name="score" value="${draft.score}" required></label>
        </div>
        <label>Status<input name="status" value="${draft.status}" required></label>
        <label>Summary<textarea name="summary" rows="4" required>${draft.summary}</textarea></label>
        <div class="modal-actions">
          <button class="btn" type="button" data-modal-close>取消</button>
          <button class="btn primary" type="submit">${isEdit ? "保存修改" : "创建 Skill"}</button>
        </div>
      </form>
    </div>
  `);
  if (window.lucide) window.lucide.createIcons();
}

function showDeleteConfirm(skill) {
  document.body.insertAdjacentHTML("beforeend", `
    <div class="modal-backdrop" data-modal>
      <div class="skill-modal compact">
        <div class="modal-header">
          <div>
            <h2>删除 Skill</h2>
            <p>${skill.packageName} 会从当前原型卡片列表中移除。</p>
          </div>
          <button class="icon-btn" type="button" data-modal-close aria-label="关闭">${icon("x")}</button>
        </div>
        <div class="modal-actions">
          <button class="btn" type="button" data-modal-close>取消</button>
          <button class="btn primary" type="button" data-confirm-delete="${skill.packageName}">确认删除</button>
        </div>
      </div>
    </div>
  `);
  if (window.lucide) window.lucide.createIcons();
}

function showTaskCreator() {
  const skillOptions = managedSkills.map((skill) => `<option value="${skill.packageName}">${skill.packageName}</option>`).join("");
  document.body.insertAdjacentHTML("beforeend", `
    <div class="modal-backdrop" data-modal>
      <form class="skill-modal" data-task-form>
        <div class="modal-header">
          <div>
            <h2>新建评测任务</h2>
            <p>选择 Skill、版本和运行环境；系统默认执行完整评测。</p>
          </div>
          <button class="icon-btn" type="button" data-modal-close aria-label="关闭">${icon("x")}</button>
        </div>
        <label>Skill<select name="skill" required>${skillOptions}</select></label>
        <div class="form-grid">
          <label>Version<input name="version" value="latest" required></label>
          <label>Evaluation Sets<input name="suite" value="Current skill-bound suite" readonly></label>
        </div>
        <label>Runner
          <select name="runner" required>
            <option value="Claude Code + MiniMax 2.7">Claude Code + MiniMax 2.7</option>
            <option value="Codex Runner + GPT-5">Codex Runner + GPT-5</option>
            <option value="Local CLI + Qwen3 Coder">Local CLI + Qwen3 Coder</option>
          </select>
        </label>
        <div class="modal-actions">
          <button class="btn" type="button" data-modal-close>取消</button>
          <button class="btn primary" type="submit">创建任务</button>
        </div>
      </form>
    </div>
  `);
  if (window.lucide) window.lucide.createIcons();
}

function showTriggerEditor(index) {
  const existing = Number.isInteger(index) ? triggerQueries[index] : {
    query: "帮我检查这个客服大模型评测集的质量",
    should_trigger: true,
  };
  document.body.insertAdjacentHTML("beforeend", `
    <div class="modal-backdrop" data-modal>
      <form class="skill-modal" data-trigger-form data-index="${Number.isInteger(index) ? index : ""}">
        <div class="modal-header">
          <div>
            <h2>${Number.isInteger(index) ? "编辑 Trigger Query" : "新增 Trigger Query"}</h2>
            <p>维护当前 Skill 的触发样本。</p>
          </div>
          <button class="icon-btn" type="button" data-modal-close aria-label="关闭">${icon("x")}</button>
        </div>
        <label>query<textarea name="query" rows="3" required>${existing.query}</textarea></label>
        <label>should_trigger
          <select name="should_trigger" required>
            <option value="true" ${existing.should_trigger ? "selected" : ""}>true</option>
            <option value="false" ${!existing.should_trigger ? "selected" : ""}>false</option>
          </select>
        </label>
        <div class="modal-actions">
          <button class="btn" type="button" data-modal-close>取消</button>
          <button class="btn primary" type="submit">保存</button>
        </div>
      </form>
    </div>
  `);
  if (window.lucide) window.lucide.createIcons();
}

function showEffectEditor(index) {
  const existing = Number.isInteger(index) ? effectCases[index] : {
    id: `case_${String(effectCases.length + 1).padStart(3, "0")}`,
    prompt: "基于 files/noise_cases.json 对模型鲁棒性进行分析，输出噪声扰动前后的通过率变化。",
    expected_output: "应输出原始样本通过率、噪声扰动样本通过率、下降比例，并指出主要失败类型。",
    files: ["files/noise_cases.json"],
    assertions: ["contains '通过率'", "contains '噪声'", "contains '下降'"],
  };
  document.body.insertAdjacentHTML("beforeend", `
    <div class="modal-backdrop" data-modal>
      <form class="skill-modal" data-effect-form data-index="${Number.isInteger(index) ? index : ""}">
        <div class="modal-header">
          <div>
            <h2>${Number.isInteger(index) ? "编辑 Effect Case" : "新增 Effect Case"}</h2>
            <p>维护当前 Skill 的效果评测 case。</p>
          </div>
          <button class="icon-btn" type="button" data-modal-close aria-label="关闭">${icon("x")}</button>
        </div>
        <label>id<input name="id" value="${existing.id}" required></label>
        <label>prompt<textarea name="prompt" rows="3" required>${existing.prompt}</textarea></label>
        <label>expected_output<textarea name="expected_output" rows="3" required>${existing.expected_output}</textarea></label>
        <label>files<textarea name="files" rows="2" required>${existing.files.join("\n")}</textarea></label>
        <label>assertions<textarea name="assertions" rows="5" required>${existing.assertions.join("\n")}</textarea></label>
        <p class="form-note">判定顺序：先执行 contains / regex / JSON schema 等确定性规则；确定性规则无法覆盖时，再交给 LLM Judge 做语义判定。</p>
        <div class="modal-actions">
          <button class="btn" type="button" data-modal-close>取消</button>
          <button class="btn primary" type="submit">保存</button>
        </div>
      </form>
    </div>
  `);
  if (window.lucide) window.lucide.createIcons();
}

function showImportEvals(kind) {
  const isTrigger = kind === "trigger";
  document.body.insertAdjacentHTML("beforeend", `
    <div class="modal-backdrop" data-modal>
      <div class="skill-modal compact">
        <div class="modal-header">
          <div>
            <h2>导入 ${isTrigger ? "Trigger Queries" : "Effect Cases"}</h2>
            <p>${isTrigger ? "只导入 query 与 should_trigger 样例，不改动 Effect Cases。" : "只导入 effect case 样例，不改动 Trigger Queries。"}</p>
          </div>
          <button class="icon-btn" type="button" data-modal-close aria-label="关闭">${icon("x")}</button>
        </div>
        <div class="modal-actions">
          <button class="btn" type="button" data-modal-close>取消</button>
          <button class="btn primary" type="button" data-confirm-import-evals="${kind}">确认导入</button>
        </div>
      </div>
    </div>
  `);
  if (window.lucide) window.lucide.createIcons();
}

function showGenerateEvals(kind) {
  const isTrigger = kind === "trigger";
  document.body.insertAdjacentHTML("beforeend", `
    <div class="modal-backdrop" data-modal>
      <div class="skill-modal compact">
        <div class="modal-header">
          <div>
            <h2>辅助生成 ${isTrigger ? "Trigger Queries" : "Effect Cases"}</h2>
            <p>${isTrigger ? "基于当前 Skill 描述生成触发/不触发 query 候选，不改动 Effect Cases。" : "基于当前 Skill 能力生成 effect case 候选，不改动 Trigger Queries。"}</p>
          </div>
          <button class="icon-btn" type="button" data-modal-close aria-label="关闭">${icon("x")}</button>
        </div>
        <div class="modal-actions">
          <button class="btn" type="button" data-modal-close>取消</button>
          <button class="btn primary" type="button" data-confirm-generate-evals="${kind}">生成样例</button>
        </div>
      </div>
    </div>
  `);
  if (window.lucide) window.lucide.createIcons();
}

function closeModal() {
  document.querySelector("[data-modal]")?.remove();
}

document.addEventListener("click", (event) => {
  const closeTarget = event.target.closest("[data-modal-close]");
  if (closeTarget) {
    closeModal();
    return;
  }

  const confirmDelete = event.target.closest("[data-confirm-delete]");
  if (confirmDelete) {
    const packageName = confirmDelete.dataset.confirmDelete;
    const index = managedSkills.findIndex((skill) => skill.packageName === packageName);
    if (index >= 0) managedSkills.splice(index, 1);
    saveManagedSkills();
    closeModal();
    if (new URLSearchParams(window.location.search).get("skill") === packageName) {
      window.history.pushState({}, "", "./product-cloud-skills.html");
    }
    renderApp();
    return;
  }

  const confirmImport = event.target.closest("[data-confirm-import-evals]");
  if (confirmImport) {
    if (confirmImport.dataset.confirmImportEvals === "trigger") {
      triggerQueries.push({ query: "分析这批鲁棒性测试样本的通过率变化", should_trigger: true });
      triggerQueries.push({ query: "帮我写一个周报标题", should_trigger: false });
    }
    if (confirmImport.dataset.confirmImportEvals === "effect") {
      effectCases.push({
        id: `case_${String(effectCases.length + 1).padStart(3, "0")}`,
        prompt: "检查 files/customer_service_evalset.xlsx 中的评测集质量，输出重复问题、缺失标准答案、类别分布不均衡的问题。",
        expected_output: "应识别重复问题、缺失标准答案，以及部分意图类别样本过少的问题，并给出整改建议。",
        files: ["files/customer_service_evalset.xlsx"],
        assertions: ["contains '重复'", "contains '缺失'", "contains '类别'", "contains '整改'"],
      });
    }
    closeModal();
    renderApp();
    return;
  }

  const confirmGenerate = event.target.closest("[data-confirm-generate-evals]");
  if (confirmGenerate) {
    if (confirmGenerate.dataset.confirmGenerateEvals === "trigger") {
      triggerQueries.unshift({ query: "帮我根据季度销售数据生成异常波动分析", should_trigger: true });
      triggerQueries.unshift({ query: "给我推荐三本产品管理书", should_trigger: false });
    }
    if (confirmGenerate.dataset.confirmGenerateEvals === "effect") {
      effectCases.unshift({
        id: `generated_case_${String(effectCases.length + 1).padStart(3, "0")}`,
        prompt: "基于 files/quarterly_sales.csv 生成一段经营分析，指出收入波动、主要原因和下一步行动。",
        expected_output: "应包含收入波动、原因解释、行动建议，并避免在数据缺失时编造结论。",
        files: ["files/quarterly_sales.csv"],
        assertions: ["contains '收入'", "contains '原因'", "contains '建议'", "does not contain '无法读取'"],
      });
    }
    closeModal();
    renderApp();
    return;
  }

  const taskAction = event.target.closest("[data-task-action]");
  if (taskAction) {
    event.preventDefault();
    if (taskAction.dataset.taskAction === "create") showTaskCreator();
    return;
  }

  const evalAction = event.target.closest("[data-eval-action]");
  if (evalAction) {
    event.preventDefault();
    const index = evalAction.dataset.index === undefined ? null : Number(evalAction.dataset.index);
    if (evalAction.dataset.evalAction === "add-trigger") showTriggerEditor();
    if (evalAction.dataset.evalAction === "edit-trigger") showTriggerEditor(index);
    if (evalAction.dataset.evalAction === "delete-trigger") {
      triggerQueries.splice(index, 1);
      renderApp();
    }
    if (evalAction.dataset.evalAction === "add-effect") showEffectEditor();
    if (evalAction.dataset.evalAction === "edit-effect") showEffectEditor(index);
    if (evalAction.dataset.evalAction === "delete-effect") {
      effectCases.splice(index, 1);
      renderApp();
    }
    if (evalAction.dataset.evalAction === "import-trigger") showImportEvals("trigger");
    if (evalAction.dataset.evalAction === "import-effect") showImportEvals("effect");
    if (evalAction.dataset.evalAction === "generate-trigger") showGenerateEvals("trigger");
    if (evalAction.dataset.evalAction === "generate-effect") showGenerateEvals("effect");
    return;
  }

  const action = event.target.closest("[data-skill-action]");
  if (!action) return;
  event.preventDefault();
  const skill = findSkill(action.dataset.skill);
  if (action.dataset.skillAction === "create") {
    showSkillEditor();
  }
  if (action.dataset.skillAction === "edit" && skill) {
    showSkillEditor(skill);
  }
  if (action.dataset.skillAction === "duplicate" && skill) {
    const copy = {
      ...skill,
      packageName: `${skill.packageName}-copy`,
      version: "0.1.0",
      score: "0.0",
      status: "Imported",
      updated: "Just now",
    };
    managedSkills.unshift(copy);
    saveManagedSkills();
    renderApp();
  }
  if (action.dataset.skillAction === "delete" && skill) {
    showDeleteConfirm(skill);
  }
});

document.addEventListener("submit", (event) => {
  const taskForm = event.target.closest("[data-task-form]");
  if (taskForm) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(taskForm).entries());
    const id = `task_${Math.floor(3000 + Math.random() * 6000)}`;
    evaluationTasks.unshift([id, data.skill, data.runner, "Queued", "—", "Just now"]);
    closeModal();
    renderApp();
    return;
  }

  const triggerForm = event.target.closest("[data-trigger-form]");
  if (triggerForm) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(triggerForm).entries());
    const next = {
      query: data.query.trim(),
      should_trigger: data.should_trigger === "true",
    };
    const index = triggerForm.dataset.index === "" ? -1 : Number(triggerForm.dataset.index);
    if (index >= 0) triggerQueries[index] = next;
    else triggerQueries.unshift(next);
    closeModal();
    renderApp();
    return;
  }

  const effectForm = event.target.closest("[data-effect-form]");
  if (effectForm) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(effectForm).entries());
    const toLines = (value) => value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    const next = {
      id: data.id.trim(),
      prompt: data.prompt.trim(),
      expected_output: data.expected_output.trim(),
      files: toLines(data.files),
      assertions: toLines(data.assertions),
    };
    const index = effectForm.dataset.index === "" ? -1 : Number(effectForm.dataset.index);
    if (index >= 0) effectCases[index] = next;
    else effectCases.unshift(next);
    closeModal();
    renderApp();
    return;
  }

  const form = event.target.closest("[data-skill-form]");
  if (!form) return;
  event.preventDefault();
  const data = Object.fromEntries(new FormData(form).entries());
  const skill = {
    packageName: data.packageName.trim(),
    title: data.packageName.trim(),
    category: data.category.trim(),
    version: data.version.trim(),
    score: data.score.trim(),
    stage: ["0", "0", "0", "0"],
    status: data.status.trim(),
    risk: "Not scanned",
    updated: "Just now",
    summary: data.summary.trim(),
  };
  const original = form.dataset.original;
  const index = managedSkills.findIndex((item) => item.packageName === original);
  if (form.dataset.mode === "edit" && index >= 0) {
    managedSkills[index] = { ...managedSkills[index], ...skill };
  } else {
    managedSkills.unshift(skill);
  }
  saveManagedSkills();
  closeModal();
  window.history.pushState({}, "", `./product-cloud-skills.html?skill=${encodeURIComponent(skill.packageName)}`);
  renderApp();
});
