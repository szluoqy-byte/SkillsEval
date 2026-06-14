export type Category = {
  id: string;
  name: string;
  description: string;
  enabled?: number | boolean;
};

export type Runner = {
  id: string;
  name: string;
  runner_type: string;
  model_name: string;
  judge_model?: string;
  command_path: string;
  timeout_seconds: number;
  enabled?: number | boolean;
};

export type ModelApiProvider = {
  id: string;
  name: string;
  provider_type: "openai_compatible" | "anthropic" | string;
  base_url: string;
  enabled?: number | boolean;
  api_key_configured: boolean;
  api_key_preview: string;
};

export type ModelProfile = {
  id: string;
  provider_id: string;
  display_name: string;
  model_id: string;
  enabled?: number | boolean;
  provider_name?: string;
  provider_type?: string;
  provider_base_url?: string;
  provider_enabled?: number | boolean;
};

export type ModelRoles = {
  judge_model_id: string | null;
  data_model_id: string | null;
};

export type ModelTestResult = {
  status: string;
  content_preview: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
};

export type Skill = {
  id: string;
  skill_name: string;
  display_name: string;
  description: string;
  card_content?: string;
  category: string;
  status: string;
  latest_version_id: string | null;
  latest_version?: string;
  overall_score?: number | null;
  recommendation?: string | null;
  result_summary?: Record<string, unknown>;
  last_evaluated_at?: string | null;
  versions?: SkillVersion[];
  latest_task?: EvaluationTask | null;
};

export type SkillVersion = {
  id: string;
  skill_id: string;
  version: string;
  manifest: Record<string, unknown>;
  artifact_root: string;
  static_scan_status: string;
  source_name: string;
  created_at: string;
};

export type SkillFileEntry = {
  path: string;
  name: string;
  type: "file" | "directory";
  size_bytes: number;
  extension: string;
  is_text: boolean;
};

export type SkillFileList = {
  version_id: string;
  version: string;
  files: SkillFileEntry[];
};

export type SkillFileContent = {
  path: string;
  content: string;
  size_bytes: number;
  is_text: boolean;
  truncated: boolean;
};

export type ImportDraft = {
  id: string;
  source_name: string;
  status: "parsed" | "failed" | "confirmed";
  detected_roots: Array<{
    root_path: string;
    skill_md_path: string;
    frontmatter: Record<string, string>;
  }>;
  selected_root_path: string | null;
  suggested_skill_name: string;
  suggested_display_name: string;
  suggested_version: string | null;
  warnings: string[];
  blocking_errors: Array<{ code: string; message: string; paths?: string[] }>;
};

export type TriggerQuery = {
  id: string;
  query: string;
  should_trigger: number | boolean;
};

export type EffectCase = {
  id: string;
  case_key: string;
  prompt: string;
  expected_output: string;
  files: string[];
  assertions: string[];
};

export type GenerationTarget = "trigger_queries" | "effect_cases";

export type GenerationDraftItem = {
  id?: string;
  selected?: boolean;
  duplicate?: boolean;
  rationale?: string;
  query?: string;
  should_trigger?: boolean;
  case_key?: string;
  prompt?: string;
  expected_output?: string;
  files?: string[];
  assertions?: string[];
};

export type EvaluationSetGenerationJob = {
  id: string;
  skill_id: string;
  eval_set_id: string;
  target: GenerationTarget;
  status: "queued" | "running" | "completed" | "failed" | "confirmed" | string;
  progress_message: string;
  request_payload: Record<string, unknown>;
  draft_items: GenerationDraftItem[];
  error: string;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
};

export type EvaluationSet = {
  id: string;
  skill_id: string;
  name: string;
  description: string;
  status: string;
  trigger_queries: TriggerQuery[];
  effect_cases: EffectCase[];
  generation_jobs?: EvaluationSetGenerationJob[];
};

export type EvaluationTask = {
  id: string;
  skill_id: string;
  skill_version_id: string;
  eval_set_id: string;
  runner_environment_id: string;
  task_scope: string;
  status: string;
  skill_name?: string;
  skill_display_name?: string;
  version?: string;
  runner_name?: string;
  overall_score?: number | null;
  recommendation?: string | null;
  result_summary?: Record<string, unknown>;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  run?: EvaluationRun | null;
  stage_results?: StageResult[];
  findings?: Finding[];
  suggestions?: Suggestion[];
  evidence_items?: EvidenceItem[];
};

export type EvaluationRun = {
  id: string;
  status: string;
  current_stage: string;
  overall_score: number | null;
  recommendation: string;
  result_summary: Record<string, unknown>;
  artifact_root: string;
};

export type StageResult = {
  id: string;
  stage: string;
  status: string;
  score: number;
  summary: string;
  metrics: Record<string, unknown>;
  artifact_path: string;
};

export type StaticRuleEvidence = {
  rule_id: string;
  category: string;
  item: string;
  severity: string;
  title: string;
  fix: string;
  status: "passed" | "failed" | "reviewed_no_risk";
  finding?: Finding | null;
  findings: Finding[];
  active_findings_count: number;
  no_risk_findings_count: number;
};

export type StageEvidenceDetail = {
  status: string;
  score: number;
  summary: string;
  metrics: Record<string, unknown>;
  error: string;
};

export type StaticScanEvidence = StageEvidenceDetail & {
  rules: StaticRuleEvidence[];
};

export type TriggerEvalResult = {
  query_id: string;
  query: string;
  should_trigger: boolean;
  triggered: boolean;
  pass: boolean;
  duration_ms: number;
  stdout_path: string;
  stderr_path: string;
  error: string;
};

export type TriggerEvalEvidence = StageEvidenceDetail & {
  results: TriggerEvalResult[];
};

export type AssertionResult = {
  text: string;
  passed: boolean;
  evidence: string;
  method: string;
  confidence: number;
  uncertain: boolean;
};

export type EffectRunResult = {
  configuration: string;
  raw_output: string;
  error: string;
  stdout_path: string;
  stderr_path: string;
  response_path: string;
  pass_rate: number;
  assertion_results: AssertionResult[];
  summary: { passed: number; failed: number; total: number; pass_rate: number };
  metrics: Record<string, unknown>;
  needs_expectations: boolean;
  deterministic_assertions: number;
  judge_assertions: number;
  uncertain_assertions: number;
};

export type EffectCaseResult = {
  case_id: string;
  case_key: string;
  prompt: string;
  expected_output: string;
  assertions: string[];
  with_skill: EffectRunResult;
  without_skill: EffectRunResult;
  delta_pass_rate: number;
  non_discriminating_assertions: string[];
  regression_assertions: string[];
  needs_expectations: boolean;
};

export type EffectEvalEvidence = StageEvidenceDetail & {
  case_results: EffectCaseResult[];
  analyzer_notes: string[];
  cost_efficiency: Record<string, unknown>;
};

export type TaskEvidenceDetail = {
  task_id: string;
  run_id: string;
  static_scan: StaticScanEvidence;
  trigger_eval: TriggerEvalEvidence;
  effect_eval: EffectEvalEvidence;
  performance_eval: StageEvidenceDetail;
  artifacts: EvidenceItem[];
};

export type Finding = {
  id: string;
  severity: string;
  original_severity?: string | null;
  effective_severity?: string | null;
  review_severity?: string | null;
  review_note?: string | null;
  reviewed_at?: string | null;
  reviewed_by?: string | null;
  code: string;
  title: string;
  detail: string;
  file_path?: string | null;
  line_number?: number | null;
  fix?: string;
};

export type Suggestion = {
  id: string;
  target: string;
  action: string;
  title: string;
  suggested_change: string;
  why: string;
};

export type EvidenceItem = {
  id: string;
  type: string;
  name: string;
  path: string;
  size_bytes: number;
};

export type Overview = {
  metrics: {
    skills_total: number;
    evaluated_skills: number;
    evaluation_tasks: number;
    users: number;
  };
  default_category: string;
  categories: Category[];
  leaderboard: Skill[];
};

export type ScoringWeight = {
  stage: string;
  weight: number;
};
