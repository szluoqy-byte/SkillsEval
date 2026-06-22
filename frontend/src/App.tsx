import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowLeft,
  BarChart3,
  CheckCircle2,
  ChevronRight,
  Database,
  FileJson,
  ListChecks,
  Loader2,
  Play,
  Plus,
  Settings,
  ShieldCheck,
  Sparkles,
  Save,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, NavLink, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { api } from "./api";
import type { AssertionResult, Category, EffectCase, EffectCaseResult, EffectEvalEvidence, EvaluationSetGenerationJob, EvaluationTask, Finding, GenerationDraftItem, GenerationTarget, ImportDraft, ModelApiProvider, ModelProfile, ModelRoles, Runner, Skill, SkillFileContent, SkillFileEntry, SkillVersion, StageEvidenceDetail, StaticRuleEvidence, StaticScanEvidence, TaskEvidenceDetail, TriggerEvalEvidence, TriggerEvalResult, TriggerQuery } from "./types";

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">SE</div>
          <div>
            <strong>SkillsEval</strong>
            <span>Independent Skill Evaluation</span>
          </div>
        </div>
        <nav>
          <NavLink to="/" end><BarChart3 size={18} />概览</NavLink>
          <NavLink to="/skills"><Database size={18} />Skills 管理</NavLink>
          <NavLink to="/tasks"><ListChecks size={18} />评测任务管理</NavLink>
          <NavLink to="/settings"><Settings size={18} />系统设置</NavLink>
        </nav>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}

function PageHeader({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description: string; actions?: React.ReactNode }) {
  return (
    <header className="page-header">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="header-actions">{actions}</div>
    </header>
  );
}

function EmptyState({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) {
  return (
    <div className="empty-state">
      <ShieldCheck size={34} />
      <h2>{title}</h2>
      <p>{description}</p>
      {action}
    </div>
  );
}

function BackLink({ to, children }: { to: string; children: React.ReactNode }) {
  return <Link className="btn" to={to}><ArrowLeft size={17} />{children}</Link>;
}

function Score({ value }: { value?: number | null }) {
  if (value === null || value === undefined) return <span className="muted">Not evaluated</span>;
  return <strong className="score">{value.toFixed(1)}</strong>;
}

function statusClass(value?: string | null) {
  return `status-${(value ?? "unknown").replaceAll("_", "-")}`;
}

function staticScanLabel(value?: string | null) {
  const labels: Record<string, string> = {
    not_scanned: "Not scanned",
    passed: "No active findings",
    warning: "Findings",
    critical: "Critical risk",
  };
  return labels[value ?? ""] ?? value ?? "unknown";
}

function scanSeverityLabel(value?: string | null) {
  const labels: Record<string, string> = {
    critical: "Critical",
    major: "Major",
    minor: "Minor",
    info: "Info",
    no_risk: "No risk",
  };
  return labels[value ?? ""] ?? value ?? "unknown";
}

function recommendationLabel(value?: string | null) {
  const labels: Record<string, string> = {
    recommended: "Recommended",
    usable: "Usable",
    review_required: "Review required",
    not_recommended: "Not recommended",
    not_evaluated: "Not evaluated",
  };
  return labels[value ?? ""] ?? value ?? "unknown";
}

function evidenceSummaryLabel(summary?: string | null) {
  if (!summary) return "";
  return summary
    .replace("Static scan passed with no active findings.", "Static scan found no active findings.")
    .replace(/Trigger eval completed: (\d+)\/(\d+) queries passed\./, "Trigger 评测完成：$1/$2 条通过。")
    .replace(/Trigger eval completed: (\d+)\/(\d+) queries matched expectations\./, "Trigger 评测完成：$1/$2 条通过。");
}

function StatusPill({ value, label }: { value?: string | null; label?: string }) {
  return <span className={`pill ${statusClass(value)}`}>{label ?? value ?? "unknown"}</span>;
}

function numberFromSummary(summary: Record<string, unknown> | undefined, key: string) {
  const value = summary?.[key];
  return typeof value === "number" ? value : null;
}

function stringFromSummary(summary: Record<string, unknown> | undefined, key: string) {
  const value = summary?.[key];
  return typeof value === "string" ? value : null;
}

function summaryForTask(task?: EvaluationTask | null) {
  return task?.run?.result_summary ?? task?.result_summary ?? {};
}

function scanStatusFromSummary(summary: Record<string, unknown> | undefined, fallback?: string | null) {
  const explicitStatus = stringFromSummary(summary, "scan_status");
  if (explicitStatus) return explicitStatus;
  const score = scanScoreFromSummary(summary);
  if (score !== null) return score >= 100 ? "passed" : "warning";
  return fallback ?? "not_scanned";
}

function scanScoreFromSummary(summary: Record<string, unknown> | undefined) {
  return numberFromSummary(summary, "scan_score") ?? numberFromSummary(summary, "static_score");
}

function triggerScoreFromSummary(summary: Record<string, unknown> | undefined) {
  return numberFromSummary(summary, "trigger_score");
}

function canDeleteTask(task?: EvaluationTask | null) {
  return !!task && !["queued", "running"].includes(task.status);
}

function effectStatusFromSummary(summary: Record<string, unknown> | undefined) {
  return stringFromSummary(summary, "effect_status") ?? "pending";
}

function effectScoreFromSummary(summary: Record<string, unknown> | undefined) {
  return numberFromSummary(summary, "effect_score");
}

function triggerExpectationLabel(shouldTrigger: boolean | number) {
  return isEnabled(shouldTrigger) ? "Trigger" : "Not Trigger";
}

function triggerExpectationText(shouldTrigger: boolean | number) {
  return `预期 ${triggerExpectationLabel(shouldTrigger)}`;
}

function triggerObservedLabel(triggered: boolean) {
  return triggered ? "Trigger" : "Not Trigger";
}

function triggerVerdictLabel(pass: boolean) {
  return pass ? "Passed" : "Failed";
}

function effectStatusLabel(value?: string | null) {
  const labels: Record<string, string> = {
    completed: "Measured",
    no_cases: "Needs cases",
    needs_expectations: "Needs assertions",
    pending: "Pending",
    not_implemented: "Pending",
  };
  return labels[value ?? ""] ?? value ?? "unknown";
}

function CompactScore({ value }: { value?: number | null }) {
  if (value === null || value === undefined) return <strong className="empty-score">--</strong>;
  return <strong>{value.toFixed(1)}</strong>;
}

function AssessmentMetric({
  label,
  score,
  status,
  statusLabel,
}: {
  label: string;
  score?: number | null;
  status?: string | null;
  statusLabel?: string;
}) {
  return (
    <div>
      <span>{label}</span>
      <CompactScore value={score} />
      {status && <StatusPill value={status} label={statusLabel} />}
    </div>
  );
}

function AssessmentStrip({ summary, scanStatus }: { summary?: Record<string, unknown>; scanStatus?: string | null }) {
  const resolvedScanStatus = scanStatusFromSummary(summary, scanStatus);
  const scanScore = scanScoreFromSummary(summary);
  const triggerScore = triggerScoreFromSummary(summary);
  const effectStatus = effectStatusFromSummary(summary);
  const effectScore = effectScoreFromSummary(summary);
  return (
    <div className="assessment-strip">
      <AssessmentMetric label="Scan" score={scanScore} status={resolvedScanStatus} statusLabel={staticScanLabel(resolvedScanStatus)} />
      <AssessmentMetric label="Trigger" score={triggerScore} status={triggerScore === null ? "pending" : "measured"} statusLabel={triggerScore === null ? "Pending" : "Measured"} />
      <AssessmentMetric label="Effect" score={effectScore} status={effectStatus} statusLabel={effectStatusLabel(effectStatus)} />
    </div>
  );
}

function AssessmentRows({ task, onSelect }: { task: EvaluationTask; onSelect: (stage: string) => void }) {
  const summary = summaryForTask(task);
  const scanStatus = scanStatusFromSummary(summary);
  const scanScore = scanScoreFromSummary(summary);
  const triggerScore = triggerScoreFromSummary(summary);
  const triggerTotal = numberFromSummary(summary, "trigger_total_queries");
  const triggerMatched = numberFromSummary(summary, "trigger_matched_queries") ?? numberFromSummary(summary, "trigger_passed_queries");
  const effectStatus = effectStatusFromSummary(summary);
  const effectScore = effectScoreFromSummary(summary);
  const skillLift = numberFromSummary(summary, "skill_lift");
  return (
    <div className="stage-list">
      <button className="stage-row stage-row-action" type="button" onClick={() => onSelect("static_scan")}>
        <span>Scan</span>
        <StatusPill value={scanStatus} label={staticScanLabel(scanStatus)} />
        <div className="meter"><i style={{ width: `${scanScore ?? 0}%` }} /></div>
        <CompactScore value={scanScore} />
      </button>
      <button className="stage-row stage-row-action" type="button" onClick={() => onSelect("trigger_eval")}>
        <span>Trigger</span>
        <small>{triggerMatched ?? 0}/{triggerTotal ?? 0} 通过</small>
        <div className="meter"><i style={{ width: `${triggerScore ?? 0}%` }} /></div>
        <CompactScore value={triggerScore} />
      </button>
      <button className="stage-row stage-row-action" type="button" onClick={() => onSelect("effect_eval")}>
        <span>Effect</span>
        <StatusPill value={effectStatus} label={effectStatusLabel(effectStatus)} />
        <div className="meter"><i style={{ width: `${effectScore ?? 0}%` }} /></div>
        <div>
          <CompactScore value={effectScore} />
          {skillLift !== null && <small>{skillLift >= 0 ? "+" : ""}{Math.round(skillLift * 100)}% lift</small>}
        </div>
      </button>
    </div>
  );
}

function OverviewPage() {
  const [category, setCategory] = useState("Data & Analytics");
  const overview = useQuery({ queryKey: ["overview", category], queryFn: () => api.overview(category) });
  const metrics = overview.data?.metrics;
  return (
    <Shell>
      <PageHeader
        eyebrow="Overview"
        title="Skills 评测平台概览"
        description="只展示系统整体运营情况和按 Scan / Trigger / Effect 组织的分类推荐榜。"
      />
      <section className="metric-grid">
        <Metric label="Skills 总数" value={metrics?.skills_total ?? 0} />
        <Metric label="已评测 Skills" value={metrics?.evaluated_skills ?? 0} />
        <Metric label="评测任务数量" value={metrics?.evaluation_tasks ?? 0} />
        <Metric label="用户数量" value={metrics?.users ?? 0} />
      </section>
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Recommended Skills by Category</h2>
            <p>按推荐等级优先，其次 Trigger 表现和 Scan 风险排序；不再合并成单一总分。</p>
          </div>
        </div>
        <div className="tabs">
          {(overview.data?.categories ?? []).map((item) => (
            <button key={item.id} className={item.name === category ? "active" : ""} onClick={() => setCategory(item.name)}>{item.name}</button>
          ))}
        </div>
        {overview.isLoading ? <Loading /> : overview.data?.leaderboard.length ? (
          <div className="table">
            <div className="table-row leaderboard-row table-head"><span>#</span><span>Skill</span><span>Category</span><span>Assessment</span><span>Recommendation</span></div>
            {overview.data.leaderboard.map((skill, index) => (
              <Link className="table-row leaderboard-row" to={`/skills/${skill.id}`} key={`${skill.id}-${index}`}>
                <span>{index + 1}</span>
                <strong>{skill.skill_name}</strong>
                <span>{skill.category}</span>
                <AssessmentStrip summary={skill.result_summary} />
                <StatusPill value={skill.recommendation} label={recommendationLabel(skill.recommendation)} />
              </Link>
            ))}
          </div>
        ) : (
          <EmptyState title="暂无榜单数据" description="上传 Skill 并完成一次评测后，这里会按 category 展示推荐列表。" />
        )}
      </section>
    </Shell>
  );
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function SkillsPage() {
  const [uploadOpen, setUploadOpen] = useState(false);
  const skills = useQuery({ queryKey: ["skills"], queryFn: api.skills });
  return (
    <Shell>
      <PageHeader
        eyebrow="Skills Management"
        title="Skills 管理"
        description="Skill 只能通过上传 ZIP 创建；category 在导入确认时人工选择。"
        actions={<button className="btn primary" onClick={() => setUploadOpen(true)}><UploadCloud size={17} />上传 Skill</button>}
      />
      {skills.isLoading ? <Loading /> : skills.data?.length ? (
        <section className="skill-grid">
          {skills.data.map((skill) => <SkillCard key={skill.id} skill={skill} />)}
        </section>
      ) : (
        <EmptyState
          title="还没有 Skill"
          description="上传一个 ZIP 包，系统会解析 SKILL.md 并生成可确认的 Import Draft。"
          action={<button className="btn primary" onClick={() => setUploadOpen(true)}><UploadCloud size={17} />上传 Skill</button>}
        />
      )}
      {uploadOpen && <UploadSkillModal onClose={() => setUploadOpen(false)} />}
    </Shell>
  );
}

function SkillCard({ skill }: { skill: Skill }) {
  return (
    <Link to={`/skills/${skill.id}`} className="skill-card">
      <div className="card-top">
        <div>
          <h2>{skill.skill_name}</h2>
          <p>{skill.display_name}</p>
        </div>
        <ChevronRight size={18} />
      </div>
      <p className="description">{skill.description || "No description parsed from SKILL.md."}</p>
      <div className="card-meta">
        <span>{skill.category}</span>
        <span>v{skill.latest_version ?? "unknown"}</span>
        <StatusPill value={skill.status} />
      </div>
      <AssessmentStrip summary={skill.result_summary} />
    </Link>
  );
}

function UploadSkillModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const categories = useQuery({ queryKey: ["categories"], queryFn: api.categories });
  const [draft, setDraft] = useState<ImportDraft | null>(null);
  const [form, setForm] = useState({ skill_name: "", version: "", category: "", display_name: "" });
  const [error, setError] = useState("");
  const upload = useMutation({
    mutationFn: api.uploadSkillZip,
    onSuccess: (nextDraft) => {
      setDraft(nextDraft);
      setError("");
      setForm({
        skill_name: nextDraft.suggested_skill_name,
        version: nextDraft.suggested_version ?? "",
        category: "",
        display_name: nextDraft.suggested_display_name,
      });
    },
    onError: (err: Error) => setError(err.message),
  });
  const confirm = useMutation({
    mutationFn: () => {
      if (!draft) throw new Error("No import draft.");
      return api.confirmImport(draft.id, form);
    },
    onSuccess: (skill) => {
      queryClient.invalidateQueries({ queryKey: ["skills"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
      onClose();
      navigate(`/skills/${skill.id}`);
    },
    onError: (err: Error) => setError(err.message),
  });
  return (
    <div className="modal-backdrop">
      <div className="modal">
        <div className="modal-header">
          <div>
            <h2>上传 Skill ZIP</h2>
            <p>解析 SKILL.md 后确认 skill_name、version 和 category。</p>
          </div>
          <button className="icon-btn" onClick={onClose}><X size={18} /></button>
        </div>
        <input type="file" accept=".zip" onChange={(event) => event.target.files?.[0] && upload.mutate(event.target.files[0])} />
        {upload.isPending && <Loading label="解析 ZIP 中" />}
        {draft?.status === "failed" && <ErrorBox title="导入阻断" messages={draft.blocking_errors.map((item) => `${item.message}${item.paths ? `：${item.paths.join(", ")}` : ""}`)} />}
        {draft?.status === "parsed" && (
          <form className="form" onSubmit={(event) => { event.preventDefault(); confirm.mutate(); }}>
            <label>skill_name<input value={form.skill_name} onChange={(event) => setForm({ ...form, skill_name: event.target.value })} required /></label>
            <label>display_name<input value={form.display_name} onChange={(event) => setForm({ ...form, display_name: event.target.value })} /></label>
            <label>version<input value={form.version} onChange={(event) => setForm({ ...form, version: event.target.value })} required /></label>
            <label>category<select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} required>
              <option value="">选择 category</option>
              {(categories.data ?? []).map((item) => <option key={item.id} value={item.name}>{item.name}</option>)}
            </select></label>
            {draft.warnings.map((warning) => <p className="warning" key={warning}>{warning}</p>)}
            <button className="btn primary" type="submit" disabled={confirm.isPending}>{confirm.isPending ? "确认中" : "确认导入"}</button>
          </form>
        )}
        {error && <ErrorBox title="操作失败" messages={[error]} />}
      </div>
    </div>
  );
}

type SkillDetailTab = "cards" | "evaluation" | "files";

function SkillDetailPage({ initialTab = "cards" }: { initialTab?: SkillDetailTab }) {
  const { skillId = "" } = useParams();
  const skill = useQuery({ queryKey: ["skill", skillId], queryFn: () => api.skill(skillId), enabled: !!skillId });
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<SkillDetailTab>(initialTab);
  const [versionId, setVersionId] = useState("");
  const [selectedFilePath, setSelectedFilePath] = useState("");

  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab, skillId]);

  const versions = skill.data?.versions ?? [];
  const selectedVersionId = versionId || skill.data?.latest_version_id || versions[0]?.id || "";
  const files = useQuery({
    queryKey: ["skill-files", skillId, selectedVersionId],
    queryFn: () => api.skillFiles(skillId, selectedVersionId),
    enabled: activeTab === "files" && !!skillId && !!selectedVersionId,
  });
  const fileEntries = files.data?.files ?? [];
  const defaultFilePath = fileEntries.find((item) => item.type === "file" && item.is_text)?.path || fileEntries.find((item) => item.type === "file")?.path || "";
  const activeFilePath = selectedFilePath || defaultFilePath;
  const activeFile = fileEntries.find((item) => item.path === activeFilePath);
  const fileContent = useQuery({
    queryKey: ["skill-file-content", skillId, selectedVersionId, activeFilePath],
    queryFn: () => api.skillFileContent(skillId, activeFilePath, selectedVersionId),
    enabled: activeTab === "files" && !!skillId && !!selectedVersionId && !!activeFilePath && activeFile?.type === "file" && !!activeFile?.is_text,
  });
  const updateSkill = useMutation({
    mutationFn: (body: { display_name: string; description: string; category: string; card_content?: string }) => api.updateSkill(skillId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["skill", skillId] });
      queryClient.invalidateQueries({ queryKey: ["skills"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
    },
  });

  if (skill.isLoading) return <Shell><Loading /></Shell>;
  if (!skill.data) {
    return (
      <Shell>
        <PageHeader
          eyebrow="Skill Detail"
          title="Skill 不存在"
          description="请返回 Skills 管理重新选择。"
          actions={<BackLink to="/skills">返回 Skills 管理</BackLink>}
        />
        <EmptyState title="Skill 不存在" description="请返回 Skills 管理重新选择。" />
      </Shell>
    );
  }
  const task = skill.data.latest_task;
  const latestVersion = versions.find((version) => version.id === skill.data?.latest_version_id) ?? versions[0];
  return (
    <Shell>
      <PageHeader
        eyebrow="Skill Detail"
        title={skill.data.skill_name}
        description={skill.data.description || "No description parsed from SKILL.md."}
        actions={<><BackLink to="/skills">返回 Skills 管理</BackLink><Link className="btn primary" to="/tasks"><Play size={17} />发起评测</Link></>}
      />
      <section className="skill-detail-summary">
        <div className="compact-stat text-stat"><span>Category</span><strong>{skill.data.category}</strong></div>
        <div className="compact-stat text-stat"><span>Latest version</span><strong>{latestVersion ? `v${latestVersion.version}` : "unknown"}</strong></div>
        <div className="compact-stat text-stat"><span>Scan</span><StatusPill value={latestVersion?.static_scan_status ?? "not_scanned"} label={staticScanLabel(latestVersion?.static_scan_status ?? "not_scanned")} /></div>
        <div className="compact-stat text-stat"><span>Recommendation</span><strong>{recommendationLabel(task?.recommendation ?? "not_evaluated")}</strong></div>
      </section>
      <section className="panel skill-detail-workspace">
        <div className="tabs detail-tabs">
          <button className={activeTab === "cards" ? "active" : ""} type="button" onClick={() => setActiveTab("cards")}>Skill Cards</button>
          <button className={activeTab === "evaluation" ? "active" : ""} type="button" onClick={() => setActiveTab("evaluation")}>Evaluation Set</button>
          <button className={activeTab === "files" ? "active" : ""} type="button" onClick={() => setActiveTab("files")}>Files</button>
        </div>
        {activeTab === "cards" ? (
          <SkillCardsTab
            skill={skill.data}
            latestVersion={latestVersion}
            task={task}
            isSaving={updateSkill.isPending}
            error={updateSkill.error?.message}
            onSave={(cardContent) => updateSkill.mutateAsync({
              display_name: skill.data.display_name,
              description: skill.data.description,
              category: skill.data.category,
              card_content: cardContent,
            })}
          />
        ) : activeTab === "evaluation" ? (
          <EvaluationSetTab skillId={skillId} />
        ) : (
          <SkillFilesTab
            versions={versions}
            selectedVersionId={selectedVersionId}
            files={fileEntries}
            filesLoading={files.isLoading}
            filesError={files.error?.message}
            selectedFilePath={activeFilePath}
            selectedFile={activeFile}
            content={fileContent.data}
            contentLoading={fileContent.isLoading}
            contentError={fileContent.error?.message}
            onVersionChange={(nextVersionId) => {
              setVersionId(nextVersionId);
              setSelectedFilePath("");
            }}
            onFileSelect={setSelectedFilePath}
          />
        )}
      </section>
    </Shell>
  );
}

function SkillCardsTab({
  skill,
  latestVersion,
  task,
  isSaving,
  error,
  onSave,
}: {
  skill: Skill;
  latestVersion?: SkillVersion;
  task?: EvaluationTask | null;
  isSaving: boolean;
  error?: string;
  onSave: (cardContent: string) => Promise<unknown>;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState(defaultCardContent(skill));
  const editorRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isEditing) setDraft(defaultCardContent(skill));
  }, [isEditing, skill.id, skill.card_content, skill.description, skill.display_name]);

  const saveAndExit = async () => {
    const nextContent = editorRef.current?.innerHTML ?? draft;
    setDraft(nextContent);
    try {
      await onSave(nextContent);
      setIsEditing(false);
    } catch {
      // Keep the editor open; the mutation error is rendered below the card.
    }
  };

  return (
    <div className="skill-cards-layout">
      <div className="skill-card-main">
        <div className="card-section-header">
          <div>
            <h2>Skill Card</h2>
            <p>自由编辑平台侧展示内容，不修改上传包内 SKILL.md。</p>
          </div>
          {isEditing ? (
            <div className="card-edit-actions">
              <button className="btn" type="button" onClick={() => { setDraft(defaultCardContent(skill)); setIsEditing(false); }}>取消</button>
              <button className="btn primary" type="button" disabled={isSaving} onClick={saveAndExit}><Save size={16} />{isSaving ? "保存中" : "保存并退出"}</button>
            </div>
          ) : (
            <button className="btn primary" type="button" onClick={() => setIsEditing(true)}><Settings size={16} />编辑 Card</button>
          )}
        </div>
        {isEditing ? (
          <div className="rich-editor-shell">
            <div
              key={`${skill.id}-${skill.card_content ?? ""}-editing`}
              className="rich-editor"
              contentEditable
              ref={editorRef}
              suppressContentEditableWarning
              dangerouslySetInnerHTML={{ __html: draft }}
            />
          </div>
        ) : (
          <div className="rich-card-view" dangerouslySetInnerHTML={{ __html: defaultCardContent(skill) }} />
        )}
        {error && <ErrorBox title="保存失败" messages={[error]} />}
      </div>
      <div className="side-stack">
        <div className="mini-panel">
          <h3>Card Metadata</h3>
          <div className="metadata-list">
            <span>{skill.display_name || skill.skill_name}</span>
            <small>{skill.skill_name}</small>
            <StatusPill value={skill.status} />
            <strong>{skill.category}</strong>
          </div>
        </div>
        <div className="mini-panel">
          <h3>Latest Evaluation</h3>
          {task ? (
            <div className="run-summary compact-run-summary">
              <StatusPill value={task.status} />
              <AssessmentStrip summary={summaryForTask(task)} />
              <p>{recommendationLabel(task.recommendation ?? task.run?.recommendation ?? "not_evaluated")}</p>
            </div>
          ) : <p className="muted">还没有评测任务。</p>}
        </div>
        <div className="mini-panel">
          <h3>Versions</h3>
          <div className="version-list compact-version-list">
            {(skill.versions ?? []).map((version) => (
              <div className="version-row" key={version.id}>
                <strong>v{version.version}</strong>
                <StatusPill value={version.static_scan_status} label={staticScanLabel(version.static_scan_status)} />
                <small>{version.source_name}</small>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function defaultCardContent(skill: Skill) {
  if (skill.card_content?.trim()) return skill.card_content;
  const title = escapeHtml(skill.display_name || skill.skill_name);
  const description = escapeHtml(skill.description || "No description parsed from SKILL.md.");
  return `<h2>${title}</h2><p>${description}</p>`;
}

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function SkillFilesTab({
  versions,
  selectedVersionId,
  files,
  filesLoading,
  filesError,
  selectedFilePath,
  selectedFile,
  content,
  contentLoading,
  contentError,
  onVersionChange,
  onFileSelect,
}: {
  versions: SkillVersion[];
  selectedVersionId: string;
  files: SkillFileEntry[];
  filesLoading: boolean;
  filesError?: string;
  selectedFilePath: string;
  selectedFile?: SkillFileEntry;
  content?: SkillFileContent;
  contentLoading: boolean;
  contentError?: string;
  onVersionChange: (versionId: string) => void;
  onFileSelect: (path: string) => void;
}) {
  return (
    <div className="files-tab">
      <div className="files-toolbar">
        <div>
          <h2>Skill Files</h2>
          <p>只读浏览当前 Skill 版本的 artifact 文件，不会修改上传包。</p>
        </div>
        <label>Version<select value={selectedVersionId} onChange={(event) => onVersionChange(event.target.value)}>
          {versions.map((version) => <option key={version.id} value={version.id}>v{version.version}</option>)}
        </select></label>
      </div>
      <div className="files-browser">
        <div className="file-list-panel">
          {filesLoading ? <Loading label="读取文件列表" /> : filesError ? <ErrorBox title="文件列表加载失败" messages={[filesError]} /> : files.length ? (
            <div className="file-list">
              {files.map((file) => (
                <button
                  className={file.path === selectedFilePath ? "file-row active" : "file-row"}
                  type="button"
                  key={file.path}
                  onClick={() => file.type === "file" && onFileSelect(file.path)}
                  disabled={file.type === "directory"}
                >
                  <FileJson size={16} />
                  <span>{file.path}</span>
                  <small>{file.type === "directory" ? "dir" : formatBytes(file.size_bytes)}</small>
                </button>
              ))}
            </div>
          ) : <CompactEmpty title="暂无文件" description="当前版本 artifact 中没有可展示文件。" />}
        </div>
        <div className="file-preview-panel">
          {!selectedFile ? (
            <CompactEmpty title="选择文件预览" description="从左侧选择一个文本文件查看内容。" />
          ) : selectedFile.type !== "file" ? (
            <CompactEmpty title="目录不可预览" description="请选择具体文件。" />
          ) : !selectedFile.is_text ? (
            <FilePreviewEmpty title="二进制文件不可预览" file={selectedFile} />
          ) : contentLoading ? (
            <Loading label="读取文件内容" />
          ) : contentError ? (
            <ErrorBox title="文件内容加载失败" messages={[contentError]} />
          ) : content ? (
            <div className="file-preview">
              <div className="file-preview-header">
                <div>
                  <h3>{content.path}</h3>
                  <span>{formatBytes(content.size_bytes)}{content.truncated ? " · preview truncated" : ""}</span>
                </div>
              </div>
              <pre>{content.content}</pre>
            </div>
          ) : (
            <CompactEmpty title="选择文件预览" description="从左侧选择一个文本文件查看内容。" />
          )}
        </div>
      </div>
    </div>
  );
}

function FilePreviewEmpty({ title, file }: { title: string; file: SkillFileEntry }) {
  return (
    <div className="compact-empty file-empty">
      <strong>{title}</strong>
      <p>{file.path} · {formatBytes(file.size_bytes)}</p>
    </div>
  );
}

function formatBytes(value?: number) {
  const bytes = value ?? 0;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function EvaluationSetTab({ skillId }: { skillId: string }) {
  const queryClient = useQueryClient();
  const evaluationSet = useQuery({ queryKey: ["evaluation-set", skillId], queryFn: () => api.evaluationSet(skillId), enabled: !!skillId });
  const generationJobs = useQuery({
    queryKey: ["generation-jobs", skillId],
    queryFn: () => api.generationJobs(skillId),
    enabled: !!skillId,
    refetchInterval: (query) => {
      const jobs = query.state.data ?? [];
      return jobs.some((job) => ["queued", "running"].includes(job.status)) ? 2000 : false;
    },
  });
  const [modal, setModal] = useState<null | "trigger" | "effect">(null);
  const [generationTarget, setGenerationTarget] = useState<GenerationTarget | null>(null);
  const [reviewJobId, setReviewJobId] = useState<string | null>(null);
  const [detail, setDetail] = useState<null | { type: "trigger"; item: TriggerQuery } | { type: "effect"; item: EffectCase }>(null);
  const [allModal, setAllModal] = useState<null | "trigger" | "effect">(null);
  const [triggerFilter, setTriggerFilter] = useState<TriggerFilter>("all");
  const [effectFilter, setEffectFilter] = useState<EffectFilter>("all");
  const [triggerPage, setTriggerPage] = useState(1);
  const [effectPage, setEffectPage] = useState(1);
  const addTrigger = useMutation({
    mutationFn: (body: { query: string; should_trigger: boolean }) => api.addTriggerQuery(skillId, body),
    onSuccess: () => {
      setModal(null);
      setTriggerPage(1);
      queryClient.invalidateQueries({ queryKey: ["evaluation-set", skillId] });
    },
  });
  const deleteTrigger = useMutation({
    mutationFn: api.deleteTriggerQuery,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["evaluation-set", skillId] }),
  });
  const addEffect = useMutation({
    mutationFn: (body: { case_key: string; prompt: string; expected_output: string; assertions: string }) =>
      api.addEffectCase(skillId, { ...body, files: [], assertions: body.assertions.split("\n").map((item) => item.trim()).filter(Boolean) }),
    onSuccess: () => {
      setModal(null);
      setEffectPage(1);
      queryClient.invalidateQueries({ queryKey: ["evaluation-set", skillId] });
    },
  });
  const deleteEffect = useMutation({
    mutationFn: api.deleteEffectCase,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["evaluation-set", skillId] }),
  });
  const createGeneration = useMutation({
    mutationFn: (body: { target: GenerationTarget; count: number; instruction: string; include_negative?: boolean }) => api.createGenerationJob(skillId, body),
    onSuccess: (job) => {
      setGenerationTarget(null);
      queryClient.invalidateQueries({ queryKey: ["generation-jobs", skillId] });
      queryClient.invalidateQueries({ queryKey: ["evaluation-set", skillId] });
      if (job.status === "completed" || job.status === "failed") setReviewJobId(job.id);
    },
  });
  const deleteGeneration = useMutation({
    mutationFn: api.deleteGenerationJob,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["generation-jobs", skillId] });
      queryClient.invalidateQueries({ queryKey: ["evaluation-set", skillId] });
    },
  });

  const triggerQueries = evaluationSet.data?.trigger_queries ?? [];
  const effectCases = evaluationSet.data?.effect_cases ?? [];
  const jobs = generationJobs.data ?? evaluationSet.data?.generation_jobs ?? [];
  const positiveTriggers = triggerQueries.filter((item) => isEnabled(item.should_trigger)).length;
  const negativeTriggers = triggerQueries.length - positiveTriggers;
  const filteredTriggers = filterTriggers(triggerQueries, triggerFilter);
  const filteredEffects = filterEffects(effectCases, effectFilter);

  return (
    <div className="evaluation-set-tab">
      <div className="tab-section-header">
        <div>
          <h2>Evaluation Set</h2>
          <p>一个 Skill 只维护一个当前评测集；评测任务会自动使用这里的 Trigger Queries 和 Effect Cases。</p>
        </div>
      </div>
      {evaluationSet.isLoading ? <Loading /> : (
        <>
          <GenerationStatusBar
            jobs={jobs}
            onOpen={(job) => setReviewJobId(job.id)}
            onDelete={(job) => deleteGeneration.mutate(job.id)}
          />
          <section className="eval-compact-summary">
            <CompactStat label="Trigger Queries" value={triggerQueries.length} />
            <CompactStat label="预期 Trigger" value={positiveTriggers} />
            <CompactStat label="预期 Not Trigger" value={negativeTriggers} />
            <CompactStat label="Effect Cases" value={effectCases.length} />
          </section>
          <section className="eval-workbench">
            <TriggerCompactPanel
              items={filteredTriggers.slice(0, 5)}
              total={triggerQueries.length}
              filteredTotal={filteredTriggers.length}
              filter={triggerFilter}
              onFilterChange={(next) => {
                setTriggerFilter(next);
                setTriggerPage(1);
              }}
              onAdd={() => setModal("trigger")}
              onGenerate={() => setGenerationTarget("trigger_queries")}
              onViewAll={() => setAllModal("trigger")}
              onOpenDetail={(item) => setDetail({ type: "trigger", item })}
              onDelete={(id) => deleteTrigger.mutate(id)}
            />
            <EffectCompactPanel
              items={filteredEffects.slice(0, 5)}
              total={effectCases.length}
              filteredTotal={filteredEffects.length}
              filter={effectFilter}
              onFilterChange={(next) => {
                setEffectFilter(next);
                setEffectPage(1);
              }}
              onAdd={() => setModal("effect")}
              onGenerate={() => setGenerationTarget("effect_cases")}
              onViewAll={() => setAllModal("effect")}
              onOpenDetail={(item) => setDetail({ type: "effect", item })}
              onDelete={(id) => deleteEffect.mutate(id)}
            />
          </section>
        </>
      )}
      {detail && <EvaluationItemDrawer detail={detail} onClose={() => setDetail(null)} />}
      {allModal === "trigger" && (
        <TriggerAllModal
          items={filteredTriggers}
          filter={triggerFilter}
          page={triggerPage}
          total={triggerQueries.length}
          onFilterChange={(next) => {
            setTriggerFilter(next);
            setTriggerPage(1);
          }}
          onPageChange={setTriggerPage}
          onOpenDetail={(item) => {
            setAllModal(null);
            setDetail({ type: "trigger", item });
          }}
          onDelete={(id) => deleteTrigger.mutate(id)}
          onClose={() => setAllModal(null)}
        />
      )}
      {allModal === "effect" && (
        <EffectAllModal
          items={filteredEffects}
          filter={effectFilter}
          page={effectPage}
          total={effectCases.length}
          onFilterChange={(next) => {
            setEffectFilter(next);
            setEffectPage(1);
          }}
          onPageChange={setEffectPage}
          onOpenDetail={(item) => {
            setAllModal(null);
            setDetail({ type: "effect", item });
          }}
          onDelete={(id) => deleteEffect.mutate(id)}
          onClose={() => setAllModal(null)}
        />
      )}
      {modal === "trigger" && (
        <TriggerQueryModal
          isPending={addTrigger.isPending}
          error={addTrigger.error?.message}
          onClose={() => setModal(null)}
          onSubmit={(body) => addTrigger.mutate(body)}
        />
      )}
      {modal === "effect" && (
        <EffectCaseModal
          isPending={addEffect.isPending}
          error={addEffect.error?.message}
          onClose={() => setModal(null)}
          onSubmit={(body) => addEffect.mutate(body)}
        />
      )}
      {generationTarget && (
        <GenerationJobModal
          target={generationTarget}
          isPending={createGeneration.isPending}
          error={createGeneration.error?.message}
          onClose={() => setGenerationTarget(null)}
          onSubmit={(body) => createGeneration.mutate(body)}
        />
      )}
      {reviewJobId && (
        <GenerationReviewModal
          jobId={reviewJobId}
          onClose={() => setReviewJobId(null)}
          onConfirmed={() => {
            setReviewJobId(null);
            queryClient.invalidateQueries({ queryKey: ["evaluation-set", skillId] });
            queryClient.invalidateQueries({ queryKey: ["generation-jobs", skillId] });
          }}
        />
      )}
    </div>
  );
}

type TriggerFilter = "all" | "should" | "negative";
type EffectFilter = "all" | "with_assertions" | "missing_assertions";

const PAGE_SIZE = 10;

function filterTriggers(items: TriggerQuery[], filter: TriggerFilter) {
  if (filter === "should") return items.filter((item) => isEnabled(item.should_trigger));
  if (filter === "negative") return items.filter((item) => !isEnabled(item.should_trigger));
  return items;
}

function filterEffects(items: EffectCase[], filter: EffectFilter) {
  if (filter === "with_assertions") return items.filter((item) => item.assertions.length > 0);
  if (filter === "missing_assertions") return items.filter((item) => item.assertions.length === 0);
  return items;
}

function pageSlice<T>(items: T[], page: number) {
  return items.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
}

function pageTotal(items: unknown[]) {
  return Math.max(1, Math.ceil(items.length / PAGE_SIZE));
}

function CompactStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="compact-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function TriggerFilterTabs({ value, onChange }: { value: TriggerFilter; onChange: (value: TriggerFilter) => void }) {
  return (
    <div className="segmented-control" aria-label="Trigger filter">
      <button type="button" className={value === "all" ? "active" : ""} onClick={() => onChange("all")}>全部</button>
      <button type="button" className={value === "should" ? "active" : ""} onClick={() => onChange("should")}>预期 Trigger</button>
      <button type="button" className={value === "negative" ? "active" : ""} onClick={() => onChange("negative")}>预期 Not Trigger</button>
    </div>
  );
}

function EffectFilterTabs({ value, onChange }: { value: EffectFilter; onChange: (value: EffectFilter) => void }) {
  return (
    <div className="segmented-control" aria-label="Effect case filter">
      <button type="button" className={value === "all" ? "active" : ""} onClick={() => onChange("all")}>全部</button>
      <button type="button" className={value === "with_assertions" ? "active" : ""} onClick={() => onChange("with_assertions")}>有断言</button>
      <button type="button" className={value === "missing_assertions" ? "active" : ""} onClick={() => onChange("missing_assertions")}>待补断言</button>
    </div>
  );
}

function TriggerCompactPanel({
  items,
  total,
  filteredTotal,
  filter,
  onFilterChange,
  onAdd,
  onGenerate,
  onViewAll,
  onOpenDetail,
  onDelete,
}: {
  items: TriggerQuery[];
  total: number;
  filteredTotal: number;
  filter: TriggerFilter;
  onFilterChange: (value: TriggerFilter) => void;
  onAdd: () => void;
  onGenerate: () => void;
  onViewAll: () => void;
  onOpenDetail: (item: TriggerQuery) => void;
  onDelete: (id: string) => void;
}) {
  if (!items.length) {
    return (
      <div className="panel eval-compact-panel">
        <EvalPanelHeader title="Trigger Queries" meta={`${filteredTotal}/${total} 条`} onAdd={onAdd} onGenerate={onGenerate} onViewAll={onViewAll} addLabel="新增 Trigger" canViewAll={total > 0} />
        <TriggerFilterTabs value={filter} onChange={onFilterChange} />
        <CompactEmpty title="暂无 Trigger Query" description="新增正向或负向触发样例后，触发评测会使用这些数据。" />
      </div>
    );
  }
  return (
    <div className="panel eval-compact-panel">
      <EvalPanelHeader title="Trigger Queries" meta={`${filteredTotal}/${total} 条`} onAdd={onAdd} onGenerate={onGenerate} onViewAll={onViewAll} addLabel="新增 Trigger" canViewAll={total > 0} />
      <TriggerFilterTabs value={filter} onChange={onFilterChange} />
      <div className="compact-eval-list">
        {items.map((item) => (
          <div className="compact-eval-row" key={item.id}>
            <div className="compact-eval-content">
              <strong>{item.query}</strong>
              <span>{triggerExpectationText(item.should_trigger)}</span>
            </div>
            <div className="compact-row-actions">
              <button className="btn small" type="button" onClick={() => onOpenDetail(item)}>详情</button>
              <button className="icon-btn danger" type="button" aria-label={`删除 ${item.query}`} onClick={() => window.confirm("删除这条 Trigger Query？") && onDelete(item.id)}><Trash2 size={16} /></button>
            </div>
          </div>
        ))}
      </div>
      {filteredTotal > items.length && <button className="inline-link" type="button" onClick={onViewAll}>查看全部 {filteredTotal} 条 <ChevronRight size={15} /></button>}
    </div>
  );
}

function EffectCompactPanel({
  items,
  total,
  filteredTotal,
  filter,
  onFilterChange,
  onAdd,
  onGenerate,
  onViewAll,
  onOpenDetail,
  onDelete,
}: {
  items: EffectCase[];
  total: number;
  filteredTotal: number;
  filter: EffectFilter;
  onFilterChange: (value: EffectFilter) => void;
  onAdd: () => void;
  onGenerate: () => void;
  onViewAll: () => void;
  onOpenDetail: (item: EffectCase) => void;
  onDelete: (id: string) => void;
}) {
  if (!items.length) {
    return (
      <div className="panel eval-compact-panel">
        <EvalPanelHeader title="Effect Cases" meta={`${filteredTotal}/${total} 条`} onAdd={onAdd} onGenerate={onGenerate} onViewAll={onViewAll} addLabel="新增 Case" canViewAll={total > 0} />
        <EffectFilterTabs value={filter} onChange={onFilterChange} />
        <CompactEmpty title="暂无 Effect Case" description="新增 case 后，效果评测会用 prompt、expected output 和 assertions 做质量检查。" />
      </div>
    );
  }
  return (
    <div className="panel eval-compact-panel">
      <EvalPanelHeader title="Effect Cases" meta={`${filteredTotal}/${total} 条`} onAdd={onAdd} onGenerate={onGenerate} onViewAll={onViewAll} addLabel="新增 Case" canViewAll={total > 0} />
      <EffectFilterTabs value={filter} onChange={onFilterChange} />
      <div className="compact-eval-list">
        {items.map((item) => (
          <div className="compact-eval-row" key={item.id}>
            <div className="compact-eval-content">
              <strong>{item.case_key}</strong>
              <span>{item.prompt}</span>
            </div>
            <span className="assertion-count">{item.assertions.length} assertions</span>
            <div className="compact-row-actions">
              <button className="btn small" type="button" onClick={() => onOpenDetail(item)}>详情</button>
              <button className="icon-btn danger" type="button" aria-label={`删除 ${item.case_key}`} onClick={() => window.confirm("删除这个 Effect Case？") && onDelete(item.id)}><Trash2 size={16} /></button>
            </div>
          </div>
        ))}
      </div>
      {filteredTotal > items.length && <button className="inline-link" type="button" onClick={onViewAll}>查看全部 {filteredTotal} 条 <ChevronRight size={15} /></button>}
    </div>
  );
}

function EvalPanelHeader({ title, meta, addLabel, canViewAll, onAdd, onGenerate, onViewAll }: { title: string; meta: string; addLabel: string; canViewAll: boolean; onAdd: () => void; onGenerate: () => void; onViewAll: () => void }) {
  return (
    <div className="compact-panel-header">
      <div>
        <h2>{title}</h2>
        <span>{meta}</span>
      </div>
      <div className="compact-header-actions">
        {canViewAll && <button className="btn" type="button" onClick={onViewAll}>查看全部</button>}
        <button className="btn" type="button" onClick={onGenerate}><Sparkles size={16} />AI 生成</button>
        <button className="btn primary" type="button" onClick={onAdd}><Plus size={16} />{addLabel}</button>
      </div>
    </div>
  );
}

function CompactEmpty({ title, description }: { title: string; description: string }) {
  return (
    <div className="compact-empty">
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  );
}

function EvaluationItemDrawer({
  detail,
  onClose,
}: {
  detail: { type: "trigger"; item: TriggerQuery } | { type: "effect"; item: EffectCase };
  onClose: () => void;
}) {
  return (
    <div className="modal-backdrop drawer-backdrop">
      <aside className="detail-drawer" aria-label="Evaluation item detail">
        <ModalHeader
          title={detail.type === "trigger" ? "Trigger Query 详情" : "Effect Case 详情"}
          description={detail.type === "trigger" ? "查看触发样例的完整文本和期望行为。" : "查看效果样例的完整 prompt、期望输出和断言。"}
          onClose={onClose}
        />
        {detail.type === "trigger" ? (
          <div className="drawer-content">
            <DetailBlock title="Query" body={detail.item.query} />
            <DetailBlock title="预期行为" body={triggerExpectationText(detail.item.should_trigger)} />
          </div>
        ) : (
          <div className="drawer-content">
            <DetailBlock title="Case key" body={detail.item.case_key} />
            <DetailBlock title="Prompt" body={detail.item.prompt} />
            <DetailBlock title="Expected output" body={detail.item.expected_output} />
            <DetailBlock title="Assertions" body={detail.item.assertions.length ? detail.item.assertions.join("\n") : "暂无断言。"} />
          </div>
        )}
      </aside>
    </div>
  );
}

function DetailBlock({ title, body }: { title: string; body: string }) {
  return (
    <div className="detail-block">
      <span>{title}</span>
      <p>{body}</p>
    </div>
  );
}

function TriggerAllModal({
  items,
  filter,
  page,
  total,
  onFilterChange,
  onPageChange,
  onOpenDetail,
  onDelete,
  onClose,
}: {
  items: TriggerQuery[];
  filter: TriggerFilter;
  page: number;
  total: number;
  onFilterChange: (value: TriggerFilter) => void;
  onPageChange: (page: number) => void;
  onOpenDetail: (item: TriggerQuery) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
}) {
  const pages = pageTotal(items);
  const safePage = Math.min(page, pages);
  const visible = pageSlice(items, safePage);
  return (
    <div className="modal-backdrop">
      <section className="modal all-items-modal">
        <ModalHeader title="全部 Trigger Queries" description={`共 ${total} 条，当前筛选 ${items.length} 条。`} onClose={onClose} />
        <TriggerFilterTabs value={filter} onChange={onFilterChange} />
        <div className="modal-list">
          {visible.length ? visible.map((item) => (
            <div className="compact-eval-row all-row" key={item.id}>
              <div className="compact-eval-content">
                <strong>{item.query}</strong>
                <span>{triggerExpectationText(item.should_trigger)}</span>
              </div>
              <div className="compact-row-actions">
                <button className="btn small" type="button" onClick={() => onOpenDetail(item)}>详情</button>
                <button className="icon-btn danger" type="button" aria-label={`删除 ${item.query}`} onClick={() => window.confirm("删除这条 Trigger Query？") && onDelete(item.id)}><Trash2 size={16} /></button>
              </div>
            </div>
          )) : <CompactEmpty title="没有匹配的数据" description="调整筛选条件后再查看。" />}
        </div>
        <Pagination page={safePage} pages={pages} onPageChange={onPageChange} />
      </section>
    </div>
  );
}

function EffectAllModal({
  items,
  filter,
  page,
  total,
  onFilterChange,
  onPageChange,
  onOpenDetail,
  onDelete,
  onClose,
}: {
  items: EffectCase[];
  filter: EffectFilter;
  page: number;
  total: number;
  onFilterChange: (value: EffectFilter) => void;
  onPageChange: (page: number) => void;
  onOpenDetail: (item: EffectCase) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
}) {
  const pages = pageTotal(items);
  const safePage = Math.min(page, pages);
  const visible = pageSlice(items, safePage);
  return (
    <div className="modal-backdrop">
      <section className="modal all-items-modal">
        <ModalHeader title="全部 Effect Cases" description={`共 ${total} 条，当前筛选 ${items.length} 条。`} onClose={onClose} />
        <EffectFilterTabs value={filter} onChange={onFilterChange} />
        <div className="modal-list">
          {visible.length ? visible.map((item) => (
            <div className="compact-eval-row all-row" key={item.id}>
              <div className="compact-eval-content">
                <strong>{item.case_key}</strong>
                <span>{item.prompt}</span>
              </div>
              <span className="assertion-count">{item.assertions.length} assertions</span>
              <div className="compact-row-actions">
                <button className="btn small" type="button" onClick={() => onOpenDetail(item)}>详情</button>
                <button className="icon-btn danger" type="button" aria-label={`删除 ${item.case_key}`} onClick={() => window.confirm("删除这个 Effect Case？") && onDelete(item.id)}><Trash2 size={16} /></button>
              </div>
            </div>
          )) : <CompactEmpty title="没有匹配的数据" description="调整筛选条件后再查看。" />}
        </div>
        <Pagination page={safePage} pages={pages} onPageChange={onPageChange} />
      </section>
    </div>
  );
}

function Pagination({ page, pages, onPageChange }: { page: number; pages: number; onPageChange: (page: number) => void }) {
  return (
    <div className="pagination-bar">
      <button className="btn" type="button" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>上一页</button>
      <span>{page} / {pages}</span>
      <button className="btn" type="button" disabled={page >= pages} onClick={() => onPageChange(page + 1)}>下一页</button>
    </div>
  );
}

function GenerationStatusBar({
  jobs,
  onOpen,
  onDelete,
}: {
  jobs: EvaluationSetGenerationJob[];
  onOpen: (job: EvaluationSetGenerationJob) => void;
  onDelete: (job: EvaluationSetGenerationJob) => void;
}) {
  const visibleJobs = jobs.filter((job) => ["queued", "running", "completed", "failed"].includes(job.status));
  if (!visibleJobs.length) return null;
  return (
    <div className="generation-status-list">
      {visibleJobs.map((job) => (
        <div className={`generation-status-card status-${job.status}`} key={job.id}>
          <div>
            <strong>{job.target === "trigger_queries" ? "Trigger Queries" : "Effect Cases"} AI 生成</strong>
            <p>{job.error || job.progress_message || generationStatusText(job.status)}</p>
          </div>
          <StatusPill value={job.status} />
          <div className="row-actions">
            {["queued", "running"].includes(job.status) && <button className="btn small" type="button" onClick={() => onOpen(job)}>查看进度</button>}
            {job.status === "completed" && <button className="btn small primary" type="button" onClick={() => onOpen(job)}>查看生成草稿</button>}
            {job.status === "failed" && <button className="btn small" type="button" onClick={() => onOpen(job)}>查看错误</button>}
            <button className="icon-btn" type="button" aria-label="移除生成任务" onClick={() => onDelete(job)}><X size={15} /></button>
          </div>
        </div>
      ))}
    </div>
  );
}

function generationStatusText(status: string) {
  if (status === "queued") return "等待后台生成。";
  if (status === "running") return "正在生成候选草稿。";
  if (status === "completed") return "生成完成，请审核后入库。";
  if (status === "failed") return "生成失败。";
  return status;
}

function GenerationJobModal({
  target,
  isPending,
  error,
  onClose,
  onSubmit,
}: {
  target: GenerationTarget;
  isPending: boolean;
  error?: string;
  onClose: () => void;
  onSubmit: (body: { target: GenerationTarget; count: number; instruction: string; include_negative?: boolean }) => void;
}) {
  const [form, setForm] = useState({ count: 5, instruction: "", include_negative: true });
  const isTrigger = target === "trigger_queries";
  return (
    <div className="modal-backdrop">
      <form className="modal settings-modal generation-modal" onSubmit={(event) => { event.preventDefault(); onSubmit({ target, ...form }); }}>
        <ModalHeader
          title={isTrigger ? "AI 生成 Trigger Queries" : "AI 生成 Effect Cases"}
          description="生成会在后台执行，结果只作为草稿保存；确认后才会写入 Evaluation Set。"
          onClose={onClose}
        />
        <label>生成数量<input type="number" min="1" max="20" value={form.count} onChange={(event) => setForm({ ...form, count: Number(event.target.value) })} required /></label>
        <label>生成要求<textarea value={form.instruction} onChange={(event) => setForm({ ...form, instruction: event.target.value })} placeholder={isTrigger ? "默认使用中文；例如：覆盖正向、负向和边界触发场景" : "默认使用中文；例如：优先生成带 deterministic assertions 的 case"} /></label>
        {isTrigger && <label className="switch-row"><input type="checkbox" checked={form.include_negative} onChange={(event) => setForm({ ...form, include_negative: event.target.checked })} />包含负样例</label>}
        {error && <ErrorBox title="创建生成任务失败" messages={[error]} />}
        <div className="modal-actions">
          <button className="btn" type="button" onClick={onClose}>取消</button>
          <button className="btn primary" type="submit" disabled={isPending}><Sparkles size={16} />{isPending ? "创建中" : "开始生成"}</button>
        </div>
      </form>
    </div>
  );
}

function GenerationReviewModal({
  jobId,
  onClose,
  onConfirmed,
}: {
  jobId: string;
  onClose: () => void;
  onConfirmed: () => void;
}) {
  const queryClient = useQueryClient();
  const jobQuery = useQuery({
    queryKey: ["generation-job", jobId],
    queryFn: () => api.generationJob(jobId),
    refetchInterval: (query) => ["queued", "running"].includes(query.state.data?.status ?? "") ? 2000 : false,
  });
  const [items, setItems] = useState<GenerationDraftItem[]>([]);
  useEffect(() => {
    if (jobQuery.data?.draft_items) setItems(jobQuery.data.draft_items);
  }, [jobQuery.data?.id, jobQuery.data?.draft_items]);
  const confirm = useMutation({
    mutationFn: () => api.confirmGenerationJob(jobId, items),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["generation-job", jobId] });
      onConfirmed();
    },
  });
  const job = jobQuery.data;
  const selectedCount = items.filter((item) => item.selected).length;
  return (
    <div className="modal-backdrop">
      <section className="modal generation-review-modal">
        <ModalHeader
          title={job?.target === "effect_cases" ? "审核 Effect Case 草稿" : "审核 Trigger Query 草稿"}
          description="勾选并编辑需要入库的数据；重复项默认不勾选。"
          onClose={onClose}
        />
        {jobQuery.isLoading && <Loading label="读取生成任务" />}
        {job && ["queued", "running"].includes(job.status) && (
          <div className="generation-waiting">
            <Loader2 size={18} className="spin" />
            <strong>{job.progress_message || "正在生成候选草稿"}</strong>
          </div>
        )}
        {job?.status === "failed" && <ErrorBox title="生成失败" messages={[job.error || "生成任务失败。"]} />}
        {job?.status === "completed" && (
          <>
            <div className="draft-toolbar">
              <span>{selectedCount}/{items.length} 条将被保存</span>
              <div className="row-actions">
                <button className="btn small" type="button" onClick={() => setItems(items.map((item) => ({ ...item, selected: true })))}>全选</button>
                <button className="btn small" type="button" onClick={() => setItems(items.map((item) => ({ ...item, selected: !item.duplicate })))}>选择非重复项</button>
                <button className="btn small" type="button" onClick={() => setItems(items.map((item) => ({ ...item, selected: false })))}>清空选择</button>
              </div>
            </div>
            <div className="draft-list">
              {items.map((item, index) => job.target === "effect_cases" ? (
                <EffectDraftEditor key={item.id ?? index} item={item} onChange={(next) => setItems(items.map((current, currentIndex) => currentIndex === index ? next : current))} onDelete={() => setItems(items.filter((_, currentIndex) => currentIndex !== index))} />
              ) : (
                <TriggerDraftEditor key={item.id ?? index} item={item} onChange={(next) => setItems(items.map((current, currentIndex) => currentIndex === index ? next : current))} onDelete={() => setItems(items.filter((_, currentIndex) => currentIndex !== index))} />
              ))}
            </div>
            {confirm.error && <ErrorBox title="保存草稿失败" messages={[confirm.error.message]} />}
            <div className="modal-actions">
              <button className="btn" type="button" onClick={onClose}>稍后处理</button>
              <button className="btn primary" type="button" disabled={selectedCount === 0 || confirm.isPending} onClick={() => confirm.mutate()}><Save size={16} />{confirm.isPending ? "保存中" : `确认入库 ${selectedCount} 条`}</button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}

function TriggerDraftEditor({ item, onChange, onDelete }: { item: GenerationDraftItem; onChange: (item: GenerationDraftItem) => void; onDelete: () => void }) {
  return (
    <div className={`draft-card ${item.duplicate ? "duplicate" : ""}`}>
      <div className="draft-card-header">
        <div className="draft-card-title">
          <label className="switch-row"><input type="checkbox" checked={!!item.selected} onChange={(event) => onChange({ ...item, selected: event.target.checked })} />选中此草稿</label>
          {item.duplicate && <StatusPill value="duplicate" label="重复" />}
        </div>
        <button className="icon-btn danger" type="button" aria-label="删除草稿" onClick={onDelete}><Trash2 size={16} /></button>
      </div>
      <div className="draft-card-grid trigger-draft-grid">
        <label className="draft-field draft-field-main">Query<textarea value={item.query ?? ""} onChange={(event) => onChange({ ...item, query: event.target.value })} /></label>
        <label className="draft-field draft-side-field">预期行为<select value={String(!!item.should_trigger)} onChange={(event) => onChange({ ...item, should_trigger: event.target.value === "true" })}>
          <option value="true">预期 Trigger</option>
          <option value="false">预期 Not Trigger</option>
        </select></label>
      </div>
      {item.rationale && <p className="draft-rationale">{item.rationale}</p>}
    </div>
  );
}

function EffectDraftEditor({ item, onChange, onDelete }: { item: GenerationDraftItem; onChange: (item: GenerationDraftItem) => void; onDelete: () => void }) {
  return (
    <div className={`draft-card effect-draft-card ${item.duplicate ? "duplicate" : ""}`}>
      <div className="draft-card-header">
        <div className="draft-card-title">
          <label className="switch-row"><input type="checkbox" checked={!!item.selected} onChange={(event) => onChange({ ...item, selected: event.target.checked })} />选中此草稿</label>
          {item.duplicate && <StatusPill value="duplicate" label="重复" />}
        </div>
        <button className="icon-btn danger" type="button" aria-label="删除草稿" onClick={onDelete}><Trash2 size={16} /></button>
      </div>
      <div className="draft-card-grid effect-draft-grid">
        <label className="draft-field draft-side-field">Case key<input value={item.case_key ?? ""} onChange={(event) => onChange({ ...item, case_key: event.target.value })} /></label>
        <label className="draft-field draft-field-main">Prompt<textarea value={item.prompt ?? ""} onChange={(event) => onChange({ ...item, prompt: event.target.value })} /></label>
        <label className="draft-field">Expected output<textarea value={item.expected_output ?? ""} onChange={(event) => onChange({ ...item, expected_output: event.target.value })} /></label>
        <label className="draft-field">Assertions<textarea value={(item.assertions ?? []).join("\n")} onChange={(event) => onChange({ ...item, assertions: event.target.value.split("\n").map((line) => line.trim()).filter(Boolean) })} /></label>
      </div>
      {item.rationale && <p className="draft-rationale">{item.rationale}</p>}
    </div>
  );
}

function TriggerQueryModal({
  error,
  isPending,
  onClose,
  onSubmit,
}: {
  error?: string;
  isPending: boolean;
  onClose: () => void;
  onSubmit: (body: { query: string; should_trigger: boolean }) => void;
}) {
  const [form, setForm] = useState({ query: "", should_trigger: true });
  return (
    <div className="modal-backdrop">
      <form className="modal settings-modal" onSubmit={(event) => { event.preventDefault(); onSubmit(form); }}>
        <ModalHeader title="新增 Trigger Query" description="添加一个用户 query，并标注预期是 Trigger 还是 Not Trigger。" onClose={onClose} />
        <label>Query<input value={form.query} onChange={(event) => setForm({ ...form, query: event.target.value })} placeholder="例如：summarize this benchmark report" required /></label>
        <label>预期行为<select value={String(form.should_trigger)} onChange={(event) => setForm({ ...form, should_trigger: event.target.value === "true" })}>
          <option value="true">预期 Trigger</option>
          <option value="false">预期 Not Trigger</option>
        </select></label>
        {error && <ErrorBox title="保存失败" messages={[error]} />}
        <div className="modal-actions">
          <button className="btn" type="button" onClick={onClose}>取消</button>
          <button className="btn primary" type="submit" disabled={isPending}><Plus size={16} />{isPending ? "保存中" : "保存"}</button>
        </div>
      </form>
    </div>
  );
}

function EffectCaseModal({
  error,
  isPending,
  onClose,
  onSubmit,
}: {
  error?: string;
  isPending: boolean;
  onClose: () => void;
  onSubmit: (body: { case_key: string; prompt: string; expected_output: string; assertions: string }) => void;
}) {
  const [form, setForm] = useState({ case_key: "", prompt: "", expected_output: "", assertions: "" });
  return (
    <div className="modal-backdrop">
      <form className="modal settings-modal eval-modal" onSubmit={(event) => { event.preventDefault(); onSubmit(form); }}>
        <ModalHeader title="新增 Effect Case" description="添加一个输出效果样例；assertions 每行一条，留空也可以后续补充。" onClose={onClose} />
        <label>Case key<input value={form.case_key} onChange={(event) => setForm({ ...form, case_key: event.target.value })} placeholder="例如：basic_summary" required /></label>
        <label>Prompt<textarea value={form.prompt} onChange={(event) => setForm({ ...form, prompt: event.target.value })} placeholder="用户会发送给 Skill 的输入" required /></label>
        <label>Expected output<textarea value={form.expected_output} onChange={(event) => setForm({ ...form, expected_output: event.target.value })} placeholder="期望输出或关键质量要求" required /></label>
        <label>Assertions<textarea value={form.assertions} onChange={(event) => setForm({ ...form, assertions: event.target.value })} placeholder="每行一条，例如：includes source citations" /></label>
        {error && <ErrorBox title="保存失败" messages={[error]} />}
        <div className="modal-actions">
          <button className="btn" type="button" onClick={onClose}>取消</button>
          <button className="btn primary" type="submit" disabled={isPending}><Plus size={16} />{isPending ? "保存中" : "保存"}</button>
        </div>
      </form>
    </div>
  );
}

function TasksPage() {
  const [open, setOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<EvaluationTask | null>(null);
  const queryClient = useQueryClient();
  const tasks = useQuery({ queryKey: ["tasks"], queryFn: api.tasks, refetchInterval: 5000 });
  const deleteTask = useMutation({
    mutationFn: (id: string) => api.deleteTask(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
      queryClient.invalidateQueries({ queryKey: ["skills"] });
      setDeleteTarget(null);
    },
  });
  return (
    <Shell>
      <PageHeader
        eyebrow="Evaluation Task Management"
        title="评测任务管理"
        description="创建 Full Evaluation 任务；系统自动使用 Skill 当前绑定的 Evaluation Set。"
        actions={<button className="btn primary" onClick={() => setOpen(true)}><Play size={17} />新建评测任务</button>}
      />
      <section className="panel">
        {tasks.isLoading ? <Loading /> : tasks.data?.length ? (
          <div className="table">
            <div className="table-row table-head task-table-head"><span>Task</span><span>Skill</span><span>Runner</span><span>Status</span><span>Trigger</span><span></span></div>
            {tasks.data.map((task, index) => (
              <div className="table-row task-table-row" key={`${task.id}-${index}`}>
                <Link className="task-row-link" to={`/tasks/${task.id}`}>
                  <strong>{task.id}</strong>
                  <span>{task.skill_name}</span>
                  <span>{task.runner_name}</span>
                  <StatusPill value={task.status} />
                  <CompactScore value={triggerScoreFromSummary(task.result_summary)} />
                </Link>
                {canDeleteTask(task) ? (
                  <button className="icon-btn danger" type="button" aria-label={`删除 ${task.id}`} onClick={() => setDeleteTarget(task)}><Trash2 size={16} /></button>
                ) : (
                  <button className="icon-btn" type="button" aria-label="运行中的任务不可删除" disabled><Trash2 size={16} /></button>
                )}
              </div>
            ))}
          </div>
        ) : <EmptyState title="暂无评测任务" description="上传 Skill 后可以创建完整评测任务。" />}
      </section>
      {open && <CreateTaskModal onClose={() => setOpen(false)} />}
      {deleteTarget && (
        <DeleteTaskConfirmModal
          task={deleteTarget}
          error={deleteTask.error?.message}
          isPending={deleteTask.isPending}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => deleteTask.mutate(deleteTarget.id)}
        />
      )}
    </Shell>
  );
}

function CreateTaskModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const skills = useQuery({ queryKey: ["skills"], queryFn: api.skills });
  const runners = useQuery({ queryKey: ["runners"], queryFn: api.runners });
  const [skillId, setSkillId] = useState("");
  const [runnerId, setRunnerId] = useState("");
  const selected = useMemo(() => (skills.data ?? []).find((skill) => skill.id === skillId), [skills.data, skillId]);
  const create = useMutation({
    mutationFn: () => {
      if (!selected?.latest_version_id || !runnerId) throw new Error("请选择 Skill 和 Runner。");
      return api.createTask({ skill_id: selected.id, skill_version_id: selected.latest_version_id, runner_environment_id: runnerId });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
      onClose();
    },
  });
  return (
    <div className="modal-backdrop">
      <form className="modal" onSubmit={(event) => { event.preventDefault(); create.mutate(); }}>
        <div className="modal-header">
          <div>
            <h2>新建评测任务</h2>
            <p>系统自动使用 Skill 当前绑定的评测集；任务固定为完整评测。</p>
          </div>
          <button className="icon-btn" type="button" onClick={onClose}><X size={18} /></button>
        </div>
        <label>Skill<select value={skillId} onChange={(event) => setSkillId(event.target.value)} required>
          <option value="">选择 Skill</option>
          {(skills.data ?? []).map((skill) => <option key={skill.id} value={skill.id}>{skill.skill_name} · v{skill.latest_version}</option>)}
        </select></label>
        <label>Evaluation Mode<input value="Full evaluation" readOnly /></label>
        <label>Runner<select value={runnerId} onChange={(event) => setRunnerId(event.target.value)} required>
          <option value="">选择 Runner</option>
          {(runners.data ?? []).map((runner) => <option key={runner.id} value={runner.id}>{runner.name}</option>)}
        </select></label>
        {create.error && <ErrorBox title="创建失败" messages={[create.error.message]} />}
        <button className="btn primary" type="submit">创建任务</button>
      </form>
    </div>
  );
}

function DeleteTaskConfirmModal({
  task,
  error,
  isPending,
  onCancel,
  onConfirm,
}: {
  task: EvaluationTask;
  error?: string;
  isPending: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="modal-backdrop">
      <section className="modal settings-modal">
        <div className="modal-header">
          <div>
            <h2>删除评测任务</h2>
            <p>此操作会删除任务、评测报告、证据记录、运行产物和临时工作区。</p>
          </div>
          <button className="icon-btn" type="button" onClick={onCancel}><X size={18} /></button>
        </div>
        <div className="delete-summary">
          <span>Task</span><strong>{task.id}</strong>
          <span>Skill</span><strong>{task.skill_name ?? task.skill_id}</strong>
          <span>Runner</span><strong>{task.runner_name ?? task.runner_environment_id}</strong>
        </div>
        {error && <ErrorBox title="删除失败" messages={[error]} />}
        <div className="modal-actions">
          <button className="btn" type="button" onClick={onCancel} disabled={isPending}>取消</button>
          <button className="btn danger" type="button" onClick={onConfirm} disabled={isPending}><Trash2 size={16} />{isPending ? "删除中" : "确认删除"}</button>
        </div>
      </section>
    </div>
  );
}

function TaskDetailPage() {
  const { taskId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [deleteTarget, setDeleteTarget] = useState<EvaluationTask | null>(null);
  const task = useQuery({ queryKey: ["task", taskId], queryFn: () => api.task(taskId), enabled: !!taskId, refetchInterval: 3000 });
  const runNow = useMutation({
    mutationFn: () => api.runTaskNow(taskId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["task", taskId] }),
  });
  const deleteTask = useMutation({
    mutationFn: (id: string) => api.deleteTask(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
      queryClient.invalidateQueries({ queryKey: ["skills"] });
      navigate("/tasks");
    },
  });
  return (
    <Shell>
      {deleteTarget && (
        <DeleteTaskConfirmModal
          task={deleteTarget}
          error={deleteTask.error?.message}
          isPending={deleteTask.isPending}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => deleteTask.mutate(deleteTarget.id)}
        />
      )}
      <PageHeader
        eyebrow="Evaluation Report"
        title={task.data?.id ?? "评测任务详情"}
        description={`${task.data?.skill_name ?? ""} ${task.data?.version ? `· v${task.data.version}` : ""}`}
        actions={<><BackLink to="/tasks">返回评测任务管理</BackLink>{task.data?.status !== "completed" && <button className="btn primary" onClick={() => runNow.mutate()}><Activity size={17} />Run now</button>}{canDeleteTask(task.data) && <button className="btn danger" type="button" onClick={() => setDeleteTarget(task.data ?? null)}><Trash2 size={16} />删除</button>}</>}
      />
      {task.isLoading ? <Loading /> : task.data ? <TaskReport task={task.data} /> : <EmptyState title="任务不存在" description="请返回任务列表重新选择。" />}
    </Shell>
  );
}

function TaskReport({ task }: { task: EvaluationTask }) {
  const [activeEvidenceTab, setActiveEvidenceTab] = useState("static_scan");
  const evidence = useQuery({
    queryKey: ["task-evidence-detail", task.id],
    queryFn: () => api.taskEvidenceDetail(task.id),
    enabled: !!task.run,
  });
  return (
    <section className="detail-grid">
      <div className="panel wide report-summary">
        <div>
          <h2>评测结论</h2>
          <p>{recommendationLabel(task.run?.recommendation ?? task.recommendation ?? "not_evaluated")}</p>
          {task.runner_name && <small>{task.runner_name}</small>}
        </div>
        <StatusPill value={task.run?.recommendation ?? task.recommendation ?? "not_evaluated"} label={recommendationLabel(task.run?.recommendation ?? task.recommendation ?? "not_evaluated")} />
        <AssessmentStrip summary={summaryForTask(task)} />
      </div>
      <div className="panel">
        <h2>三类指标</h2>
        <AssessmentRows task={task} onSelect={setActiveEvidenceTab} />
      </div>
      <div className="panel">
        <h2>建议</h2>
        <div className="stack-list">
          {(task.suggestions ?? []).map((item) => (
            <div className="stack-item" key={item.id}>
              <strong>{item.title}</strong>
              <p>{item.suggested_change}</p>
            </div>
          ))}
        </div>
      </div>
      <div className="panel wide">
        <EvidenceWorkspace
          taskId={task.id}
          activeTab={activeEvidenceTab}
          detail={evidence.data}
          isLoading={evidence.isLoading}
          error={evidence.error?.message}
          onTabChange={setActiveEvidenceTab}
        />
      </div>
    </section>
  );
}

const evidenceTabs = [
  { id: "static_scan", label: "Scan" },
  { id: "trigger_eval", label: "Trigger" },
  { id: "effect_eval", label: "Effect" },
  { id: "raw_artifacts", label: "Raw Artifacts" },
];

function EvidenceWorkspace({
  taskId,
  activeTab,
  detail,
  isLoading,
  error,
  onTabChange,
}: {
  taskId: string;
  activeTab: string;
  detail?: TaskEvidenceDetail;
  isLoading: boolean;
  error?: string;
  onTabChange: (tab: string) => void;
}) {
  return (
    <div className="evidence-workspace">
      <div className="panel-header evidence-header">
        <div>
          <h2>评测证据 / 运行产物</h2>
          <p>按阶段查看可读证据，原始 artifact 保留在 Raw Artifacts 中用于排查。</p>
        </div>
      </div>
      <div className="tabs evidence-tabs">
        {evidenceTabs.map((tab) => (
          <button key={tab.id} className={activeTab === tab.id ? "active" : ""} type="button" onClick={() => onTabChange(tab.id)}>
            {tab.label}
          </button>
        ))}
      </div>
      {isLoading ? <Loading /> : error ? <ErrorBox title="证据加载失败" messages={[error]} /> : detail ? (
        <div className="evidence-body">
          {activeTab === "static_scan" && <StaticScanEvidencePanel taskId={taskId} evidence={detail.static_scan} />}
          {activeTab === "trigger_eval" && <TriggerEvalEvidencePanel evidence={detail.trigger_eval} />}
          {activeTab === "effect_eval" && <EffectEvalEvidencePanel evidence={detail.effect_eval} />}
          {activeTab === "raw_artifacts" && <RawArtifactsPanel artifacts={detail.artifacts} />}
        </div>
      ) : <EmptyState title="暂无证据" description="任务完成后会在这里展示分阶段证据。" />}
    </div>
  );
}

type ScanRuleView = "active" | "no_risk" | "clean" | "all";

type ScanFindingRow = {
  rule: StaticRuleEvidence;
  finding: Finding;
};

const reviewSeverityOptions = ["critical", "major", "minor", "info", "no_risk"];

function StaticScanEvidencePanel({ taskId, evidence }: { taskId: string; evidence: StaticScanEvidence }) {
  const queryClient = useQueryClient();
  const [scanRuleView, setScanRuleView] = useState<ScanRuleView>("active");
  const findingRows = evidence.rules.flatMap((rule) => (rule.findings ?? []).map((finding) => ({ rule, finding })));
  const activeFindingRows = findingRows.filter(({ finding }) => (finding.effective_severity ?? finding.severity) !== "no_risk");
  const noRiskFindingRows = findingRows.filter(({ finding }) => (finding.effective_severity ?? finding.severity) === "no_risk");
  const cleanRules = evidence.rules.filter((rule) => rule.status === "passed");
  const visibleRules = scanRuleView === "clean" ? cleanRules : evidence.rules;
  const reviewSuccess = () => {
    queryClient.invalidateQueries({ queryKey: ["task", taskId] });
    queryClient.invalidateQueries({ queryKey: ["task-evidence-detail", taskId] });
    queryClient.invalidateQueries({ queryKey: ["tasks"] });
    queryClient.invalidateQueries({ queryKey: ["skills"] });
    queryClient.invalidateQueries({ queryKey: ["overview"] });
  };
  const updateReview = useMutation({
    mutationFn: ({ findingId, review_severity }: { findingId: string; review_severity: string }) => api.reviewScanFinding(taskId, findingId, { review_severity }),
    onSuccess: reviewSuccess,
  });
  const clearReview = useMutation({
    mutationFn: ({ findingId }: { findingId: string }) => api.clearScanFindingReview(taskId, findingId),
    onSuccess: reviewSuccess,
  });
  const handleReviewChange = (finding: Finding, value: string) => {
    if (value === "__scanner__") {
      clearReview.mutate({ findingId: finding.id });
      return;
    }
    updateReview.mutate({ findingId: finding.id, review_severity: value });
  };
  const pendingFindingId = updateReview.isPending ? updateReview.variables?.findingId : clearReview.isPending ? clearReview.variables?.findingId : "";
  const activeError = updateReview.error?.message ?? clearReview.error?.message;
  const visibleFindingRows = scanRuleView === "no_risk" ? noRiskFindingRows : activeFindingRows;
  const viewTitle = scanRuleView === "active" ? "Active Findings" : scanRuleView === "no_risk" ? "No Risk" : scanRuleView === "clean" ? "Clean Rules" : "All Rules";
  return (
    <div className="evidence-panel">
      <StageEvidenceSummary title="Scan" evidence={evidence} extra={`${activeFindingRows.length} active / ${noRiskFindingRows.length} no risk`} />
      {evidence.error && <ErrorBox title="Static artifact 读取失败" messages={[evidence.error]} />}
      {activeError && <ErrorBox title="风险确认失败" messages={[activeError]} />}
      <div className="scan-rule-toolbar">
        <div>
          <strong>{viewTitle}</strong>
          <span>
            {scanRuleView === "active"
              ? "默认只展示仍参与扣分的活跃风险，可在行内调整人工确认等级。"
              : scanRuleView === "no_risk"
                ? "查看已人工确认为无风险的 findings；它们不参与 Scan 扣分。"
              : scanRuleView === "clean"
                ? "查看未命中 finding 的规则，用于审计覆盖。"
                : "查看完整规则执行情况。"}
          </span>
        </div>
        <div className="segmented-control scan-rule-filter" aria-label="Scan rule filter">
          <button className={scanRuleView === "active" ? "active" : ""} type="button" onClick={() => setScanRuleView("active")}>
            Active · {activeFindingRows.length}
          </button>
          <button className={scanRuleView === "no_risk" ? "active" : ""} type="button" onClick={() => setScanRuleView("no_risk")}>
            No Risk · {noRiskFindingRows.length}
          </button>
          <button className={scanRuleView === "clean" ? "active" : ""} type="button" onClick={() => setScanRuleView("clean")}>
            Clean · {cleanRules.length}
          </button>
          <button className={scanRuleView === "all" ? "active" : ""} type="button" onClick={() => setScanRuleView("all")}>
            All · {evidence.rules.length}
          </button>
        </div>
      </div>
      <div className="rule-table">
        {scanRuleView === "active" || scanRuleView === "no_risk" ? (
          <>
            <div className="rule-row rule-head scan-finding-row">
              <span>Rule</span>
              <span>Category</span>
              <span>Risk</span>
              <span>Review</span>
              <span>Detail</span>
            </div>
            {visibleFindingRows.length ? visibleFindingRows.map(({ rule, finding }) => (
              <ScanFindingReviewRow
                key={finding.id}
                rule={rule}
                finding={finding}
                isPending={pendingFindingId === finding.id}
                onChange={(value) => handleReviewChange(finding, value)}
              />
            )) : (
              <div className="scan-rule-empty">
                <strong>当前视图没有 finding</strong>
                <p>{scanRuleView === "active" ? "当前没有仍参与扣分的活跃风险。" : "还没有人工确认为无风险的 finding。"}</p>
              </div>
            )}
          </>
        ) : (
          <>
            <div className="rule-row rule-head">
              <span>Rule</span>
              <span>Category</span>
              <span>Severity</span>
              <span>Status</span>
              <span>Detail</span>
            </div>
            {visibleRules.length ? visibleRules.map((rule) => (
              <div className="rule-row" key={rule.rule_id}>
                <strong>{rule.rule_id}</strong>
                <span>{rule.category}</span>
                <StatusPill value={rule.severity} />
                <StatusPill
                  value={rule.status === "reviewed_no_risk" ? "no_risk" : rule.status}
                  label={rule.status === "failed" ? "Finding" : rule.status === "reviewed_no_risk" ? "No risk" : "No finding"}
                />
                <div>
                  <strong>{rule.title}</strong>
                  <p>{rule.finding?.detail ?? rule.item}</p>
                  {rule.finding?.file_path && <small>{rule.finding.file_path}{rule.finding.line_number ? `:${rule.finding.line_number}` : ""}</small>}
                  {rule.finding?.fix && <small>Fix: {rule.finding.fix}</small>}
                </div>
              </div>
            )) : (
              <div className="scan-rule-empty">
                <strong>当前视图没有规则项</strong>
                <p>切换到其他视图查看规则执行情况。</p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function ScanFindingReviewRow({
  rule,
  finding,
  isPending,
  onChange,
}: {
  rule: StaticRuleEvidence;
  finding: Finding;
  isPending: boolean;
  onChange: (value: string) => void;
}) {
  const effectiveSeverity = finding.effective_severity ?? finding.severity;
  const originalSeverity = finding.original_severity ?? finding.severity;
  return (
    <div className="rule-row scan-finding-row">
      <strong>{rule.rule_id}</strong>
      <span>{rule.category}</span>
      <StatusPill value={effectiveSeverity} label={scanSeverityLabel(effectiveSeverity)} />
      <label className="risk-review-control">
        <span>人工确认</span>
        <select value={finding.review_severity ?? "__scanner__"} onChange={(event) => onChange(event.target.value)} disabled={isPending}>
          <option value="__scanner__">原始: {scanSeverityLabel(originalSeverity)}</option>
          {reviewSeverityOptions.map((severity) => (
            <option key={severity} value={severity}>{scanSeverityLabel(severity)}</option>
          ))}
        </select>
      </label>
      <div>
        <strong>{finding.title}</strong>
        <p>{finding.detail}</p>
        <small>Scanner severity: {scanSeverityLabel(originalSeverity)}</small>
        {finding.reviewed_at && <small>Reviewed by {finding.reviewed_by ?? "manual"} at {finding.reviewed_at}</small>}
        {finding.file_path && <small>{finding.file_path}{finding.line_number ? `:${finding.line_number}` : ""}</small>}
        {finding.fix && <small>Fix: {finding.fix}</small>}
      </div>
    </div>
  );
}

function TriggerEvalEvidencePanel({ evidence }: { evidence: TriggerEvalEvidence }) {
  return (
    <div className="evidence-panel">
      <StageEvidenceSummary
        title="Trigger"
        evidence={evidence}
        extra={`${String(evidence.metrics.matched_queries ?? evidence.metrics.passed_queries ?? 0)}/${String(evidence.metrics.total_queries ?? evidence.results.length)} 通过`}
      />
      {evidence.error && <ErrorBox title="Trigger artifact 读取失败" messages={[evidence.error]} />}
      {evidence.results.length ? (
        <div className="trigger-table-wrap">
          <table className="trigger-result-table">
            <thead>
              <tr>
                <th>Query</th>
                <th>预期</th>
                <th>实际</th>
                <th>判定</th>
                <th>耗时</th>
                <th>产物</th>
              </tr>
            </thead>
            <tbody>
              {evidence.results.map((item) => <TriggerResultItem key={item.query_id} item={item} />)}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="trigger-result-list">
          <p className="muted">暂无 Trigger Query 执行结果。</p>
        </div>
      )}
    </div>
  );
}

function TriggerResultItem({ item }: { item: TriggerEvalResult }) {
  const expected = triggerExpectationLabel(item.should_trigger);
  const actual = triggerObservedLabel(item.triggered);
  const verdict = triggerVerdictLabel(item.pass);
  return (
    <tr className="trigger-result-row">
      <td>
        <div className="trigger-query-cell">
          <strong>{item.query}</strong>
          <small>{item.query_id}</small>
          {item.error && <span className="warning">error: {item.error}</span>}
        </div>
      </td>
      <td><span className="trigger-token">{expected}</span></td>
      <td><span className="trigger-token">{actual}</span></td>
      <td><StatusPill value={item.pass ? "passed" : "failed"} label={verdict} /></td>
      <td><strong className="trigger-duration">{item.duration_ms} ms</strong></td>
      <td>
        <details className="trigger-artifacts">
          <summary>查看路径</summary>
          <small>stdout: {item.stdout_path}</small>
          <small>stderr: {item.stderr_path}</small>
        </details>
      </td>
    </tr>
  );
}

function metricValue(metrics: Record<string, unknown>, key: string) {
  const value = metrics[key];
  if (typeof value === "number") return value;
  if (typeof value === "string") return value;
  return "—";
}

function percentValue(value: unknown) {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "—";
}

function EffectEvalEvidencePanel({ evidence }: { evidence: EffectEvalEvidence }) {
  const classification = String(evidence.cost_efficiency?.classification ?? evidence.metrics.cost_efficiency_classification ?? "unknown");
  const analyzerNotes = evidence.analyzer_notes ?? [];
  const caseResults = evidence.case_results ?? [];
  return (
    <div className="evidence-panel">
      <StageEvidenceSummary
        title="Effect"
        evidence={evidence}
        showScore={typeof evidence.score === "number" && evidence.status !== "no_cases" && evidence.status !== "needs_expectations"}
        extra={`${String(evidence.metrics.valid_cases ?? 0)}/${String(evidence.metrics.total_cases ?? caseResults.length)} valid cases`}
      />
      {evidence.error && <ErrorBox title="Effect artifact 读取失败" messages={[evidence.error]} />}
      <div className="effect-summary-grid">
        <Metric label="With skill" value={percentValue(evidence.metrics.with_skill_pass_rate)} />
        <Metric label="Baseline" value={percentValue(evidence.metrics.without_skill_pass_rate)} />
        <Metric label="Skill lift" value={percentValue(evidence.metrics.skill_lift)} />
        <Metric label="Cost efficiency" value={classification} />
      </div>
      <div className="effect-metrics-line">
        <span>Tokens/pass assertion: {String(metricValue(evidence.metrics, "tokens_per_passing_assertion"))}</span>
        <span>Token delta: {String(metricValue(evidence.metrics, "token_delta_pct"))}%</span>
        <span>Duration delta: {String(metricValue(evidence.metrics, "duration_delta_pct"))}%</span>
        <span>Tool delta: {String(metricValue(evidence.metrics, "tool_call_delta"))}</span>
      </div>
      {analyzerNotes.length > 0 && (
        <div className="analysis-notes">
          <h3>Analyzer Notes</h3>
          {analyzerNotes.map((note) => <p key={note}>{note}</p>)}
        </div>
      )}
      {caseResults.length ? (
        <div className="effect-case-list">
          {caseResults.map((item) => <EffectCaseResultItem key={item.case_id} item={item} />)}
        </div>
      ) : (
        <EmptyState title="暂无 Effect Case 结果" description="补充 Effect Cases 后，新评测任务会执行 with-skill 与 baseline 对照。" />
      )}
    </div>
  );
}

function EffectCaseResultItem({ item }: { item: EffectCaseResult }) {
  return (
    <div className="effect-case-result">
      <div className="effect-case-head">
        <div>
          <strong>{item.case_key}</strong>
          <p>{item.prompt}</p>
          {item.expected_output && <small>Expected: {item.expected_output}</small>}
        </div>
        <div className="trigger-pills">
          <StatusPill value={item.delta_pass_rate > 0 ? "positive_lift" : item.delta_pass_rate < 0 ? "regression" : "no_delta"} label={`${item.delta_pass_rate >= 0 ? "+" : ""}${Math.round(item.delta_pass_rate * 100)}% lift`} />
          {item.needs_expectations && <StatusPill value="needs_expectations" label="Needs assertions" />}
        </div>
      </div>
      {(item.non_discriminating_assertions.length > 0 || item.regression_assertions.length > 0) && (
        <div className="assertion-alerts">
          {item.non_discriminating_assertions.length > 0 && <small>{item.non_discriminating_assertions.length} non-discriminating assertions</small>}
          {item.regression_assertions.length > 0 && <small className="warning">{item.regression_assertions.length} regression assertions</small>}
        </div>
      )}
      <div className="effect-run-compare">
        <EffectRunCard title="With Skill" run={item.with_skill} />
        <EffectRunCard title="Baseline" run={item.without_skill} />
      </div>
    </div>
  );
}

function EffectRunCard({ title, run }: { title: string; run: EffectCaseResult["with_skill"] }) {
  return (
    <div className="effect-run-card">
      <div className="effect-run-head">
        <strong>{title}</strong>
        <CompactScore value={run.pass_rate * 100} />
      </div>
      <div className="effect-metrics-line compact">
        <span>{String(metricValue(run.metrics, "duration_ms"))} ms</span>
        <span>{String(metricValue(run.metrics, "total_tokens"))} tokens</span>
        <span>{String(metricValue(run.metrics, "tool_calls"))} tools</span>
      </div>
      {run.error && <small className="warning">{run.error}</small>}
      <AssertionTable items={run.assertion_results} />
      <details className="raw-output-preview">
        <summary>Response preview</summary>
        <pre>{run.raw_output || "(empty output)"}</pre>
      </details>
    </div>
  );
}

function AssertionTable({ items }: { items: AssertionResult[] }) {
  if (!items.length) return <p className="muted">暂无 assertion 判定结果。</p>;
  return (
    <div className="assertion-table">
      {items.map((item) => (
        <div className="assertion-row" key={`${item.text}-${item.method}`}>
          <StatusPill value={item.passed ? "passed" : item.uncertain ? "uncertain" : "failed"} label={item.passed ? "Passed" : item.uncertain ? "Uncertain" : "Failed"} />
          <span>{item.method}</span>
          <div>
            <strong>{item.text}</strong>
            <p>{item.evidence}</p>
            {item.method === "llm_judge" && <small>confidence: {Math.round((item.confidence ?? 0) * 100)}%</small>}
          </div>
        </div>
      ))}
    </div>
  );
}

function StageEvidencePanel({ title, evidence }: { title: string; evidence: StageEvidenceDetail }) {
  return (
    <div className="evidence-panel">
      <StageEvidenceSummary title={title} evidence={evidence} showScore={evidence.status !== "pending" && evidence.status !== "not_implemented"} />
      {evidence.error && <ErrorBox title={`${title} artifact 读取失败`} messages={[evidence.error]} />}
      <div className="not-implemented-box">
        <StatusPill value={evidence.status} />
        <p>{evidence.summary}</p>
      </div>
    </div>
  );
}

function StageEvidenceSummary({ title, evidence, extra, showScore = true }: { title: string; evidence: StageEvidenceDetail; extra?: string; showScore?: boolean }) {
  return (
    <div className="evidence-summary">
      <div>
        <h3>{title}</h3>
        <p>{evidenceSummaryLabel(evidence.summary)}</p>
      </div>
      <StatusPill value={evidence.status} />
      {showScore ? <Score value={evidence.score} /> : <span className="muted">Pending</span>}
      {extra && <span className="muted">{extra}</span>}
    </div>
  );
}

function RawArtifactsPanel({ artifacts }: { artifacts: TaskEvidenceDetail["artifacts"] }) {
  return (
    <div className="table compact-table raw-artifact-table">
      {artifacts.map((item) => (
        <div className="table-row" key={item.id}>
          <FileJson size={16} />
          <strong>{item.name}</strong>
          <span>{item.type}</span>
          <small>{item.path}</small>
        </div>
      ))}
    </div>
  );
}

function SettingsPage() {
  const categories = useQuery({ queryKey: ["settings-categories"], queryFn: api.settingsCategories });
  const runners = useQuery({ queryKey: ["settings-runners"], queryFn: api.settingsRunners });
  const providers = useQuery({ queryKey: ["model-providers"], queryFn: api.modelProviders });
  const models = useQuery({ queryKey: ["model-profiles"], queryFn: api.modelProfiles });
  const roles = useQuery({ queryKey: ["model-roles"], queryFn: api.modelRoles });
  const activeRunners = (runners.data ?? []).filter((item) => isEnabled(item.enabled)).length;
  const activeCategories = (categories.data ?? []).filter((item) => isEnabled(item.enabled)).length;
  const activeModels = (models.data ?? []).filter((item) => isEnabled(item.enabled) && isEnabled(item.provider_enabled)).length;
  return (
    <Shell>
      <PageHeader eyebrow="System Settings" title="系统设置" description="集中维护运行环境、第三方模型 API、裁判/数据模型、Skill 分类和三类评估策略。" />
      <section className="settings-summary">
        <Metric label="Active runners" value={activeRunners} />
        <Metric label="Active models" value={activeModels} />
        <Metric label="Active categories" value={activeCategories} />
        <Metric label="Assessment groups" value={3} />
      </section>
      <section className="settings-layout">
        <RunnerSettingsPanel runners={runners.data ?? []} />
        <ModelApiSettingsPanel providers={providers.data ?? []} models={models.data ?? []} />
        <ModelRolesPanel roles={roles.data ?? { judge_model_id: null, data_model_id: null }} models={models.data ?? []} />
        <CategorySettingsPanel categories={categories.data ?? []} />
        <AssessmentPolicyPanel />
      </section>
    </Shell>
  );
}

function isEnabled(value?: number | boolean) {
  return value === undefined ? true : value === true || value === 1;
}

type RunnerFormBody = {
  name: string;
  runner_type: string;
  model_name: string;
  command_path: string;
  timeout_seconds: number;
  enabled: boolean;
};

type ProviderFormBody = {
  name: string;
  provider_type: string;
  base_url: string;
  api_key?: string;
  enabled: boolean;
  initial_model_display_name?: string;
  initial_model_id?: string;
};

type ModelFormBody = {
  provider_id: string;
  display_name: string;
  model_id: string;
  enabled: boolean;
};

type ModelConfigFormBody = {
  model_id: string;
  provider_type: string;
  base_url: string;
  api_key?: string;
  enabled: boolean;
};

function CategorySettingsPanel({ categories }: { categories: Category[] }) {
  const queryClient = useQueryClient();
  const [modal, setModal] = useState<null | { mode: "create" | "edit"; item?: Category }>(null);
  const create = useMutation({
    mutationFn: (body: { name: string; description: string; enabled: boolean }) => api.createCategory(body),
    onSuccess: () => {
      setModal(null);
      invalidateSettings(queryClient);
    },
  });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: { name: string; description: string; enabled: boolean } }) => api.updateCategory(id, body),
    onSuccess: () => {
      setModal(null);
      invalidateSettings(queryClient);
    },
  });
  const active = categories.filter((item) => isEnabled(item.enabled));
  const inactive = categories.filter((item) => !isEnabled(item.enabled));
  const saveCategory = (body: { name: string; description: string; enabled: boolean }) => {
    if (modal?.mode === "edit" && modal.item) {
      update.mutate({ id: modal.item.id, body });
    } else {
      create.mutate(body);
    }
  };
  const setCategoryEnabled = (item: Category, enabled: boolean) => {
    update.mutate({ id: item.id, body: { name: item.name, description: item.description, enabled } });
  };
  return (
    <div className="panel settings-panel">
      <div className="panel-header">
        <div>
          <h2>Categories</h2>
          <p>控制上传 Skill 时可选的分类；停用不会改写历史 Skill。</p>
        </div>
        <button className="btn primary" type="button" onClick={() => setModal({ mode: "create" })}><Plus size={16} />新增分类</button>
      </div>
      <SettingsList
        activeLabel="启用中"
        inactiveLabel="已停用"
        activeItems={active}
        inactiveItems={inactive}
        renderItem={(item) => (
          <SettingsListItem
            key={item.id}
            title={item.name}
            subtitle={item.description || "No description"}
            enabled={isEnabled(item.enabled)}
            onEdit={() => setModal({ mode: "edit", item })}
            onToggle={() => setCategoryEnabled(item, !isEnabled(item.enabled))}
            toggleLabel={isEnabled(item.enabled) ? "停用" : "启用"}
          />
        )}
      />
      {(create.error || update.error) && <ErrorBox title="保存失败" messages={[create.error?.message, update.error?.message].filter(Boolean) as string[]} />}
      {modal && (
        <CategoryEditorModal
          item={modal.item}
          isSaving={create.isPending || update.isPending}
          onClose={() => setModal(null)}
          onSubmit={saveCategory}
        />
      )}
    </div>
  );
}

function RunnerSettingsPanel({ runners }: { runners: Runner[] }) {
  const queryClient = useQueryClient();
  const [modal, setModal] = useState<null | { mode: "create" | "edit"; item?: Runner }>(null);
  const create = useMutation({
    mutationFn: (body: RunnerFormBody) => api.createRunner(body),
    onSuccess: () => {
      setModal(null);
      invalidateSettings(queryClient);
    },
  });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: RunnerFormBody }) => api.updateRunner(id, body),
    onSuccess: () => {
      setModal(null);
      invalidateSettings(queryClient);
    },
  });
  const remove = useMutation({
    mutationFn: api.deleteRunner,
    onSuccess: () => invalidateSettings(queryClient),
  });
  const active = runners.filter((item) => isEnabled(item.enabled));
  const inactive = runners.filter((item) => !isEnabled(item.enabled));
  const saveRunner = (body: RunnerFormBody) => {
    if (modal?.mode === "edit" && modal.item) {
      update.mutate({ id: modal.item.id, body });
    } else {
      create.mutate(body);
    }
  };
  const setRunnerEnabled = (item: Runner, enabled: boolean) => {
    if (!enabled) {
      remove.mutate(item.id);
      return;
    }
    update.mutate({
      id: item.id,
      body: {
        name: item.name,
        runner_type: item.runner_type,
        model_name: item.model_name,
        command_path: item.command_path,
        timeout_seconds: item.timeout_seconds,
        enabled: true,
      },
    });
  };
  return (
    <div className="panel settings-panel">
      <div className="panel-header">
        <div>
          <h2>Runner Environments</h2>
          <p>控制新建评测任务时可选的执行环境；停用后历史任务仍保留引用。</p>
        </div>
        <button className="btn primary" type="button" onClick={() => setModal({ mode: "create" })}><Plus size={16} />新增 Runner</button>
      </div>
      <SettingsList
        activeLabel="启用中"
        inactiveLabel="已停用"
        activeItems={active}
        inactiveItems={inactive}
        renderItem={(item) => (
          <SettingsListItem
            key={item.id}
            title={item.name}
            subtitle={`${item.runner_type} · ${item.model_name} · ${item.command_path || "no command"} · ${item.timeout_seconds}s`}
            enabled={isEnabled(item.enabled)}
            onEdit={() => setModal({ mode: "edit", item })}
            onToggle={() => setRunnerEnabled(item, !isEnabled(item.enabled))}
            toggleLabel={isEnabled(item.enabled) ? "停用" : "启用"}
          />
        )}
      />
      {(create.error || update.error || remove.error) && <ErrorBox title="保存失败" messages={[create.error?.message, update.error?.message, remove.error?.message].filter(Boolean) as string[]} />}
      {modal && (
        <RunnerEditorModal
          item={modal.item}
          isSaving={create.isPending || update.isPending}
          onClose={() => setModal(null)}
          onSubmit={saveRunner}
        />
      )}
    </div>
  );
}

function providerTypeLabel(value: string) {
  const labels: Record<string, string> = {
    openai_compatible: "OpenAI-compatible",
    anthropic: "Anthropic",
  };
  return labels[value] ?? value;
}

function ModelApiSettingsPanel({ providers, models }: { providers: ModelApiProvider[]; models: ModelProfile[] }) {
  const queryClient = useQueryClient();
  const [modal, setModal] = useState<null | { mode: "create" | "edit"; item?: ModelProfile }>(null);
  const [testResult, setTestResult] = useState<Record<string, string>>({});
  const providerFor = (model: ModelProfile) => providers.find((provider) => provider.id === model.provider_id);
  const connectionNameFor = (body: ModelConfigFormBody) => `${body.model_id} @ ${body.base_url}`;
  const assertUniqueModelConfig = (body: ModelConfigFormBody, currentModelId?: string) => {
    const duplicate = models.some((model) => {
      const provider = providerFor(model);
      return model.id !== currentModelId && model.model_id === body.model_id && provider?.base_url === body.base_url;
    });
    if (duplicate) throw new Error("model name + base_url 已存在。");
  };
  const createConfig = useMutation({
    mutationFn: async (body: ModelConfigFormBody) => {
      assertUniqueModelConfig(body);
      const provider = await api.createModelProvider({
        name: connectionNameFor(body),
        provider_type: body.provider_type,
        base_url: body.base_url,
        api_key: body.api_key,
        enabled: body.enabled,
      });
      return api.createModelProfile({
        provider_id: provider.id,
        display_name: body.model_id,
        model_id: body.model_id,
        enabled: body.enabled,
      });
    },
    onSuccess: () => {
      setModal(null);
      invalidateSettings(queryClient);
    },
  });
  const updateConfig = useMutation({
    mutationFn: async ({ model, body }: { model: ModelProfile; body: ModelConfigFormBody }) => {
      assertUniqueModelConfig(body, model.id);
      const provider = providerFor(model);
      if (!provider) throw new Error("Model provider not found.");
      await api.updateModelProvider(provider.id, {
        name: connectionNameFor(body),
        provider_type: body.provider_type,
        base_url: body.base_url,
        api_key: body.api_key ?? "",
        enabled: body.enabled,
      });
      return api.updateModelProfile(model.id, {
        provider_id: provider.id,
        display_name: body.model_id,
        model_id: body.model_id,
        enabled: body.enabled,
      });
    },
    onSuccess: () => {
      setModal(null);
      invalidateSettings(queryClient);
    },
  });
  const deleteModel = useMutation({
    mutationFn: api.deleteModelProfile,
    onSuccess: () => invalidateSettings(queryClient),
  });
  const updateModel = useMutation({
    mutationFn: ({ id, body }: { id: string; body: ModelFormBody }) => api.updateModelProfile(id, body),
    onSuccess: () => invalidateSettings(queryClient),
  });
  const updateProvider = useMutation({
    mutationFn: ({ id, body }: { id: string; body: ProviderFormBody }) => api.updateModelProvider(id, body),
    onSuccess: () => invalidateSettings(queryClient),
  });
  const testModel = useMutation({
    mutationFn: api.testModelProfile,
    onMutate: (id) => setTestResult((current) => ({ ...current, [id]: "Testing..." })),
    onSuccess: (result, id) => setTestResult((current) => ({ ...current, [id]: `OK · ${result.total_tokens} tokens` })),
    onError: (error, id) => setTestResult((current) => ({ ...current, [id]: error.message })),
  });
  const saveConfig = (body: ModelConfigFormBody) => {
    if (modal?.mode === "edit" && modal.item) {
      updateConfig.mutate({ model: modal.item, body });
    } else {
      createConfig.mutate(body);
    }
  };
  const toggleModel = (item: ModelProfile) => {
    const provider = providerFor(item);
    const enabled = !isEnabled(item.enabled);
    if (!enabled) {
      deleteModel.mutate(item.id);
      return;
    }
    if (provider && !isEnabled(provider.enabled)) {
      updateProvider.mutate({
        id: provider.id,
        body: { name: provider.name, provider_type: provider.provider_type, base_url: provider.base_url, api_key: "", enabled: true },
      });
    }
    updateModel.mutate({
      id: item.id,
      body: { provider_id: item.provider_id, display_name: item.display_name, model_id: item.model_id, enabled: true },
    });
  };
  const messages = [createConfig.error, updateConfig.error, deleteModel.error, updateModel.error, updateProvider.error].map((item) => item?.message).filter(Boolean) as string[];
  return (
    <div className="panel settings-panel">
      <div className="panel-header">
        <div>
          <h2>Model API Models</h2>
          <p>直接维护可用于 Judge/Data 的模型；每个模型包含接口格式、base_url 和 API Key。</p>
        </div>
        <button className="btn primary" type="button" onClick={() => setModal({ mode: "create" })}><Plus size={16} />新增模型配置</button>
      </div>
      <div className="model-config-list">
        {models.length ? models.map((model) => {
          const provider = providerFor(model);
          const enabled = isEnabled(model.enabled) && isEnabled(provider?.enabled);
          return (
            <div className="model-config-card" key={model.id}>
              <div>
                <strong>{model.model_id}</strong>
                <p>{provider?.base_url ?? model.provider_base_url ?? "Missing base_url"}</p>
                <small>{provider ? providerTypeLabel(provider.provider_type) : "Provider not found"}</small>
                {provider && <small>{provider.api_key_configured ? `API Key ${provider.api_key_preview}` : "API Key not configured"}</small>}
                {testResult[model.id] && <small>{testResult[model.id]}</small>}
              </div>
              <StatusPill value={enabled ? "enabled" : "disabled"} />
              <div className="row-actions">
                <button className="btn" type="button" onClick={() => testModel.mutate(model.id)}>测试连接</button>
                <button className="btn" type="button" onClick={() => setModal({ mode: "edit", item: model })}><Settings size={16} />编辑</button>
                <button className={`btn ${enabled ? "danger" : ""}`} type="button" onClick={() => toggleModel(model)}>
                  {enabled ? <Trash2 size={16} /> : <CheckCircle2 size={16} />}{enabled ? "停用" : "启用"}
                </button>
              </div>
            </div>
          );
        }) : <p className="settings-empty">暂无模型配置。新增模型后可设为裁判模型或数据模型。</p>}
      </div>
      {messages.length > 0 && <ErrorBox title="保存失败" messages={messages} />}
      {modal && (
        <ModelConfigEditorModal
          item={modal.item}
          provider={modal.item ? providerFor(modal.item) : undefined}
          isSaving={createConfig.isPending || updateConfig.isPending}
          onClose={() => setModal(null)}
          onSubmit={saveConfig}
        />
      )}
    </div>
  );
}

function ModelRolesPanel({ roles, models }: { roles: ModelRoles; models: ModelProfile[] }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<ModelRoles>(roles);
  useEffect(() => setForm(roles), [roles.judge_model_id, roles.data_model_id]);
  const save = useMutation({
    mutationFn: api.updateModelRoles,
    onSuccess: () => invalidateSettings(queryClient),
  });
  const enabledModels = models.filter((model) => isEnabled(model.enabled) && isEnabled(model.provider_enabled));
  const selectedModelIds = new Set([form.judge_model_id, form.data_model_id].filter(Boolean));
  const selectableModels = [
    ...enabledModels,
    ...models.filter((model) => selectedModelIds.has(model.id) && !enabledModels.some((enabled) => enabled.id === model.id)),
  ];
  const optionLabel = (model: ModelProfile) => `${model.model_id} · ${model.provider_base_url ?? model.provider_name ?? "base_url missing"}`;
  const optionStatus = (model: ModelProfile) => isEnabled(model.enabled) && isEnabled(model.provider_enabled) ? "" : " · disabled";
  return (
    <div className="panel settings-panel">
      <div className="panel-header">
        <div>
          <h2>Model Roles</h2>
          <p>裁判模型用于 Effect 评分；数据模型预留给后续 AI 辅助生成评测数据。</p>
        </div>
        <button className="btn primary" type="button" onClick={() => save.mutate(form)} disabled={save.isPending}><Save size={16} />保存角色</button>
      </div>
      <div className="role-grid">
        <label>裁判模型
          <select value={form.judge_model_id ?? ""} onChange={(event) => setForm({ ...form, judge_model_id: event.target.value || null })}>
            <option value="">未配置</option>
            {selectableModels.map((model) => <option value={model.id} key={model.id}>{optionLabel(model)}{optionStatus(model)}</option>)}
          </select>
        </label>
        <label>数据模型
          <select value={form.data_model_id ?? ""} onChange={(event) => setForm({ ...form, data_model_id: event.target.value || null })}>
            <option value="">未配置</option>
            {selectableModels.map((model) => <option value={model.id} key={model.id}>{optionLabel(model)}{optionStatus(model)}</option>)}
          </select>
        </label>
      </div>
      {save.error && <ErrorBox title="保存失败" messages={[save.error.message]} />}
    </div>
  );
}

function AssessmentPolicyPanel() {
  return (
    <div className="panel settings-panel">
      <div className="panel-header">
        <div>
          <h2>Assessment Policy</h2>
          <p>当前按 Scan、Trigger、Effect 三类指标展示，不合并为单一总分。</p>
        </div>
        <StatusPill value="legacy" label="No weighted score" />
      </div>
      <div className="policy-list">
        <div><strong>Scan</strong><p>结构、安全与维护风险，独立展示 findings 和风险等级。</p></div>
        <div><strong>Trigger</strong><p>真实 Runner 触发评测，按每条 query 的预期 / 实际 / 判定计算通过率。</p></div>
        <div><strong>Effect</strong><p>执行 with-skill 与 baseline 对照，通过 assertions 和 Judge 判断质量提升，并展示成本效率证据。</p></div>
      </div>
    </div>
  );
}

function SettingsList<T>({
  activeLabel,
  inactiveLabel,
  activeItems,
  inactiveItems,
  renderItem,
}: {
  activeLabel: string;
  inactiveLabel: string;
  activeItems: T[];
  inactiveItems: T[];
  renderItem: (item: T) => React.ReactNode;
}) {
  return (
    <div className="settings-list">
      <div className="settings-group-heading">
        <span>{activeLabel}</span>
        <strong>{activeItems.length}</strong>
      </div>
      {activeItems.length ? activeItems.map(renderItem) : <p className="settings-empty">暂无启用项。</p>}
      {inactiveItems.length > 0 && (
        <details className="settings-archive">
          <summary>{inactiveLabel} · {inactiveItems.length}</summary>
          <div className="settings-list archived-list">
            {inactiveItems.map(renderItem)}
          </div>
        </details>
      )}
    </div>
  );
}

function SettingsListItem({
  title,
  subtitle,
  enabled,
  onEdit,
  onToggle,
  toggleLabel,
}: {
  title: string;
  subtitle: string;
  enabled: boolean;
  onEdit: () => void;
  onToggle: () => void;
  toggleLabel: string;
}) {
  return (
    <div className="settings-list-item">
      <div>
        <strong>{title}</strong>
        <p>{subtitle}</p>
      </div>
      <StatusPill value={enabled ? "enabled" : "disabled"} />
      <div className="row-actions">
        <button className="btn" type="button" onClick={onEdit}><Settings size={16} />编辑</button>
        <button className={`btn ${enabled ? "danger" : ""}`} type="button" onClick={onToggle}>
          {enabled ? <Trash2 size={16} /> : <CheckCircle2 size={16} />}{toggleLabel}
        </button>
      </div>
    </div>
  );
}

function CategoryEditorModal({
  item,
  isSaving,
  onClose,
  onSubmit,
}: {
  item?: Category;
  isSaving: boolean;
  onClose: () => void;
  onSubmit: (body: { name: string; description: string; enabled: boolean }) => void;
}) {
  const [form, setForm] = useState({
    name: item?.name ?? "",
    description: item?.description ?? "",
    enabled: isEnabled(item?.enabled),
  });
  return (
    <div className="modal-backdrop">
      <form className="modal settings-modal" onSubmit={(event) => { event.preventDefault(); onSubmit(form); }}>
        <ModalHeader title={item ? "编辑 Category" : "新增 Category"} description="停用后不会再出现在上传 Skill 的分类选择中。" onClose={onClose} />
        <label>Category name<input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required /></label>
        <label>Description<textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
        <label className="switch-row"><input type="checkbox" checked={form.enabled} onChange={(event) => setForm({ ...form, enabled: event.target.checked })} />Enabled</label>
        <div className="modal-actions">
          <button className="btn" type="button" onClick={onClose}>取消</button>
          <button className="btn primary" type="submit" disabled={isSaving}><Save size={16} />保存</button>
        </div>
      </form>
    </div>
  );
}

function RunnerEditorModal({
  item,
  isSaving,
  onClose,
  onSubmit,
}: {
  item?: Runner;
  isSaving: boolean;
  onClose: () => void;
  onSubmit: (body: RunnerFormBody) => void;
}) {
  const [form, setForm] = useState({
    name: item?.name ?? "",
    runner_type: item?.runner_type ?? "",
    model_name: item?.model_name ?? "",
    command_path: item?.command_path ?? "",
    timeout_seconds: item?.timeout_seconds ?? 60,
    enabled: isEnabled(item?.enabled),
  });
  return (
    <div className="modal-backdrop">
      <form className="modal settings-modal" onSubmit={(event) => { event.preventDefault(); onSubmit(form); }}>
        <ModalHeader title={item ? "编辑 Runner" : "新增 Runner"} description="停用后不会再出现在新建评测任务的 Runner 选择中。" onClose={onClose} />
        <label>Runner name<input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required /></label>
        <div className="form-grid">
          <label>runner_type<input value={form.runner_type} onChange={(event) => setForm({ ...form, runner_type: event.target.value })} required /></label>
          <label>model_name<input value={form.model_name} onChange={(event) => setForm({ ...form, model_name: event.target.value })} required /></label>
        </div>
        <label>command_path<input value={form.command_path} onChange={(event) => setForm({ ...form, command_path: event.target.value })} required /></label>
        <label>timeout_seconds<input type="number" min="1" step="1" value={form.timeout_seconds} onChange={(event) => setForm({ ...form, timeout_seconds: Number(event.target.value) })} required /></label>
        <label className="switch-row"><input type="checkbox" checked={form.enabled} onChange={(event) => setForm({ ...form, enabled: event.target.checked })} />Enabled</label>
        <div className="modal-actions">
          <button className="btn" type="button" onClick={onClose}>取消</button>
          <button className="btn primary" type="submit" disabled={isSaving}><Save size={16} />保存</button>
        </div>
      </form>
    </div>
  );
}

function ModelConfigEditorModal({
  item,
  provider,
  isSaving,
  onClose,
  onSubmit,
}: {
  item?: ModelProfile;
  provider?: ModelApiProvider;
  isSaving: boolean;
  onClose: () => void;
  onSubmit: (body: ModelConfigFormBody) => void;
}) {
  const [form, setForm] = useState<ModelConfigFormBody>({
    model_id: item?.model_id ?? "",
    provider_type: provider?.provider_type ?? "openai_compatible",
    base_url: provider?.base_url ?? "",
    api_key: "",
    enabled: isEnabled(item?.enabled) && isEnabled(provider?.enabled),
  });
  return (
    <div className="modal-backdrop">
      <form className="modal settings-modal" onSubmit={(event) => { event.preventDefault(); onSubmit(form); }}>
        <ModalHeader
          title={item ? "编辑模型配置" : "新增模型配置"}
          description={item ? "API Key 留空会保留原 Key；系统不会回显明文。" : "只需要配置接口格式、base_url、model name 与 API Key。OpenAI-compatible 会追加 /chat/completions；Anthropic 会追加 /v1/messages。"}
          onClose={onClose}
        />
        <div className="form-grid">
          <label>model_id / model name<input value={form.model_id} onChange={(event) => setForm({ ...form, model_id: event.target.value })} placeholder="model-name-from-provider" required /></label>
          <label>provider_type
            <select value={form.provider_type} onChange={(event) => setForm({ ...form, provider_type: event.target.value })}>
              <option value="openai_compatible">OpenAI-compatible</option>
              <option value="anthropic">Anthropic</option>
            </select>
          </label>
        </div>
        <label>base_url<input value={form.base_url} onChange={(event) => setForm({ ...form, base_url: event.target.value })} placeholder="https://api.example.com/v1" required /></label>
        <label>api_key<input type="password" value={form.api_key ?? ""} placeholder={provider?.api_key_configured ? "留空保留现有 API Key" : "输入 API Key"} onChange={(event) => setForm({ ...form, api_key: event.target.value })} required={!provider?.api_key_configured} /></label>
        <div className="modal-actions">
          <button className="btn" type="button" onClick={onClose}>取消</button>
          <button className="btn primary" type="submit" disabled={isSaving}><Save size={16} />保存</button>
        </div>
      </form>
    </div>
  );
}

function ModalHeader({ title, description, onClose }: { title: string; description: string; onClose: () => void }) {
  return (
    <div className="modal-header">
      <div>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      <button className="icon-btn" type="button" onClick={onClose} aria-label="关闭"><X size={18} /></button>
    </div>
  );
}

function invalidateSettings(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ["settings-categories"] });
  queryClient.invalidateQueries({ queryKey: ["settings-runners"] });
  queryClient.invalidateQueries({ queryKey: ["model-providers"] });
  queryClient.invalidateQueries({ queryKey: ["model-profiles"] });
  queryClient.invalidateQueries({ queryKey: ["model-roles"] });
  queryClient.invalidateQueries({ queryKey: ["categories"] });
  queryClient.invalidateQueries({ queryKey: ["runners"] });
  queryClient.invalidateQueries({ queryKey: ["weights"] });
  queryClient.invalidateQueries({ queryKey: ["overview"] });
}

function Loading({ label = "加载中" }: { label?: string }) {
  return <div className="loading"><Loader2 size={18} className="spin" />{label}</div>;
}

function ErrorBox({ title, messages }: { title: string; messages: string[] }) {
  return (
    <div className="error-box">
      <strong>{title}</strong>
      {messages.map((message) => <p key={message}>{message}</p>)}
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<OverviewPage />} />
      <Route path="/skills" element={<SkillsPage />} />
      <Route path="/skills/:skillId" element={<SkillDetailPage />} />
      <Route path="/skills/:skillId/evaluation-set" element={<SkillDetailPage initialTab="evaluation" />} />
      <Route path="/tasks" element={<TasksPage />} />
      <Route path="/tasks/:taskId" element={<TaskDetailPage />} />
      <Route path="/settings" element={<SettingsPage />} />
    </Routes>
  );
}
