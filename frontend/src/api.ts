import type {
  Category,
  EffectCase,
  EvaluationSet,
  EvaluationTask,
  ImportDraft,
  ModelApiProvider,
  ModelProfile,
  ModelRoles,
  ModelTestResult,
  Overview,
  Runner,
  ScoringWeight,
  Skill,
  SkillFileContent,
  SkillFileList,
  TaskEvidenceDetail,
  TriggerQuery,
  EvaluationSetGenerationJob,
  GenerationDraftItem,
  GenerationTarget,
} from "./types";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(options.headers ?? {}),
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(payload.detail ?? "Request failed");
  }
  return response.json() as Promise<T>;
}

export const api = {
  overview: (category = "Data & Analytics") => request<Overview>(`/api/overview?category=${encodeURIComponent(category)}`),
  categories: () => request<Category[]>("/api/categories"),
  runners: () => request<Runner[]>("/api/runners"),
  settingsCategories: () => request<Category[]>("/api/settings/categories"),
  createCategory: (body: { name: string; description: string; enabled?: boolean }) =>
    request<Category>("/api/settings/categories", { method: "POST", body: JSON.stringify(body) }),
  updateCategory: (id: string, body: { name: string; description: string; enabled: boolean }) =>
    request<Category>(`/api/settings/categories/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteCategory: (id: string) => request<{ status: string; id: string }>(`/api/settings/categories/${id}`, { method: "DELETE" }),
  settingsRunners: () => request<Runner[]>("/api/settings/runners"),
  createRunner: (body: { name: string; runner_type: string; model_name: string; command_path: string; timeout_seconds: number; enabled?: boolean }) =>
    request<Runner>("/api/settings/runners", { method: "POST", body: JSON.stringify(body) }),
  updateRunner: (id: string, body: { name: string; runner_type: string; model_name: string; command_path: string; timeout_seconds: number; enabled: boolean }) =>
    request<Runner>(`/api/settings/runners/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteRunner: (id: string) => request<{ status: string; id: string }>(`/api/settings/runners/${id}`, { method: "DELETE" }),
  modelProviders: () => request<ModelApiProvider[]>("/api/settings/model-providers"),
  createModelProvider: (body: { name: string; provider_type: string; base_url: string; api_key?: string; enabled?: boolean }) =>
    request<ModelApiProvider>("/api/settings/model-providers", { method: "POST", body: JSON.stringify(body) }),
  updateModelProvider: (id: string, body: { name: string; provider_type: string; base_url: string; api_key?: string; enabled: boolean }) =>
    request<ModelApiProvider>(`/api/settings/model-providers/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteModelProvider: (id: string) => request<{ status: string; id: string }>(`/api/settings/model-providers/${id}`, { method: "DELETE" }),
  modelProfiles: () => request<ModelProfile[]>("/api/settings/model-models"),
  createModelProfile: (body: { provider_id: string; display_name: string; model_id: string; enabled?: boolean }) =>
    request<ModelProfile>("/api/settings/model-models", { method: "POST", body: JSON.stringify(body) }),
  updateModelProfile: (id: string, body: { provider_id: string; display_name: string; model_id: string; enabled: boolean }) =>
    request<ModelProfile>(`/api/settings/model-models/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteModelProfile: (id: string) => request<{ status: string; id: string }>(`/api/settings/model-models/${id}`, { method: "DELETE" }),
  modelRoles: () => request<ModelRoles>("/api/settings/model-roles"),
  updateModelRoles: (body: ModelRoles) =>
    request<ModelRoles>("/api/settings/model-roles", { method: "PUT", body: JSON.stringify(body) }),
  testModelProfile: (id: string) => request<ModelTestResult>(`/api/settings/model-models/${id}/test`, { method: "POST" }),
  skills: () => request<Skill[]>("/api/skills"),
  skill: (id: string) => request<Skill>(`/api/skills/${id}`),
  updateSkill: (id: string, body: { display_name: string; description: string; category: string; card_content?: string }) =>
    request<Skill>(`/api/skills/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  skillFiles: (skillId: string, versionId?: string) => {
    const params = versionId ? `?version_id=${encodeURIComponent(versionId)}` : "";
    return request<SkillFileList>(`/api/skills/${skillId}/files${params}`);
  },
  skillFileContent: (skillId: string, path: string, versionId?: string) => {
    const params = new URLSearchParams({ path });
    if (versionId) params.set("version_id", versionId);
    return request<SkillFileContent>(`/api/skills/${skillId}/files/content?${params.toString()}`);
  },
  evaluationSet: (skillId: string) => request<EvaluationSet>(`/api/skills/${skillId}/evaluation-set`),
  generationJobs: (skillId: string) => request<EvaluationSetGenerationJob[]>(`/api/skills/${skillId}/evaluation-set/generation-jobs`),
  createGenerationJob: (skillId: string, body: { target: GenerationTarget; count: number; instruction: string; include_negative?: boolean }) =>
    request<EvaluationSetGenerationJob>(`/api/skills/${skillId}/evaluation-set/generation-jobs`, { method: "POST", body: JSON.stringify(body) }),
  generationJob: (id: string) => request<EvaluationSetGenerationJob>(`/api/evaluation-set-generation-jobs/${id}`),
  confirmGenerationJob: (id: string, items: GenerationDraftItem[]) =>
    request<{ status: string; inserted_count: number; items: unknown[] }>(`/api/evaluation-set-generation-jobs/${id}/confirm`, { method: "POST", body: JSON.stringify({ items }) }),
  deleteGenerationJob: (id: string) => request<{ status: string }>(`/api/evaluation-set-generation-jobs/${id}`, { method: "DELETE" }),
  uploadSkillZip: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ImportDraft>("/api/imports/skill-zip", { method: "POST", body: form });
  },
  confirmImport: (draftId: string, body: { skill_name: string; version: string; category: string; display_name?: string }) =>
    request<Skill>(`/api/imports/${draftId}/confirm`, { method: "POST", body: JSON.stringify(body) }),
  addTriggerQuery: (skillId: string, body: { query: string; should_trigger: boolean }) =>
    request<TriggerQuery>(`/api/skills/${skillId}/evaluation-set/trigger-queries`, { method: "POST", body: JSON.stringify(body) }),
  deleteTriggerQuery: (id: string) => request<{ status: string }>(`/api/trigger-queries/${id}`, { method: "DELETE" }),
  addEffectCase: (skillId: string, body: { case_key: string; prompt: string; expected_output: string; files: string[]; assertions: string[] }) =>
    request<EffectCase>(`/api/skills/${skillId}/evaluation-set/effect-cases`, { method: "POST", body: JSON.stringify(body) }),
  deleteEffectCase: (id: string) => request<{ status: string }>(`/api/effect-cases/${id}`, { method: "DELETE" }),
  tasks: () => request<EvaluationTask[]>("/api/tasks"),
  createTask: (body: { skill_id: string; skill_version_id: string; runner_environment_id: string }) =>
    request<EvaluationTask>("/api/tasks", { method: "POST", body: JSON.stringify(body) }),
  runTaskNow: (id: string) => request<EvaluationTask>(`/api/tasks/${id}/run-now`, { method: "POST" }),
  deleteTask: (id: string) => request<{ status: string; id: string; deleted_runs: number; cleanup_errors: string[] }>(`/api/tasks/${id}`, { method: "DELETE" }),
  task: (id: string) => request<EvaluationTask>(`/api/tasks/${id}`),
  taskEvidenceDetail: (id: string) => request<TaskEvidenceDetail>(`/api/tasks/${id}/evidence-detail`),
  reviewScanFinding: (taskId: string, findingId: string, body: { review_severity: string; review_note?: string }) =>
    request<TaskEvidenceDetail>(`/api/tasks/${taskId}/scan-findings/${findingId}/review`, { method: "PUT", body: JSON.stringify(body) }),
  clearScanFindingReview: (taskId: string, findingId: string) =>
    request<TaskEvidenceDetail>(`/api/tasks/${taskId}/scan-findings/${findingId}/review`, { method: "DELETE" }),
  scoringWeights: () => request<ScoringWeight[]>("/api/settings/scoring-weights"),
  updateScoringWeights: (weights: ScoringWeight[]) =>
    request<ScoringWeight[]>("/api/settings/scoring-weights", { method: "PUT", body: JSON.stringify({ weights }) }),
};
