export type SageActivationMode = "off" | "shadow" | "approval" | "auto";
export type SageRiskLevel = "low" | "medium" | "high" | "critical";
export type SageCapability =
  | "hybrid_recall"
  | "feedback_learning"
  | "nightly_consolidation"
  | "knowledge_merge"
  | "playbook_promotion"
  | "cross_scope_transfer";

export interface SagePolicy {
  policy_id: string;
  tenant_id: string;
  capability: SageCapability;
  mode: SageActivationMode;
  scope: { scope_type: string; scope_id: string } | null;
  max_auto_risk: SageRiskLevel;
  settings: Record<string, unknown>;
  version: number;
  updated_at: string;
}

export interface SageEvaluationSnapshot {
  tenant_id: string;
  knowledge_total: number;
  active_knowledge: number;
  signal_count: number;
  positive_signal_rate: number;
  recall_count: number;
  degradation_count: number;
  degradation_rate: number;
  pending_candidates: number;
  applied_candidates: number;
  rolled_back_candidates: number;
  completed_runs: number;
  failed_runs: number;
  pending_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  average_job_latency_ms: number;
  generated_at: string;
}

export interface SageOverview {
  snapshot: SageEvaluationSnapshot;
  policies: SagePolicy[];
}

export interface SageCandidate {
  candidate_id: string;
  run_id: string;
  kind:
    | "duplicate"
    | "conflict"
    | "stale"
    | "low_utility"
    | "playbook_promotion";
  action: "merge" | "dispute" | "archive" | "promote_playbook";
  source_ids: string[];
  risk_level: SageRiskLevel;
  state:
    | "proposed"
    | "approved"
    | "applied"
    | "rejected"
    | "stale"
    | "rolled_back";
  rationale: string;
  proposed_change: Record<string, unknown>;
  before_snapshots: Record<
    string,
    {
      title?: string;
      content?: string;
      classification?: string;
      state?: string;
      [key: string]: unknown;
    }
  >;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface SageReceipt {
  receipt_id: string;
  query: string;
  ranking_mode: string;
  selections: Array<{
    source_id: string;
    title?: string;
    score_components?: Record<string, number>;
  }>;
  degradations: string[];
  generated_at: string;
}

export interface SageJob {
  job_id: string;
  job_type: string;
  state: "pending" | "leased" | "completed" | "failed";
  attempts: number;
  last_error: string;
  created_at: string;
  updated_at: string;
}

export interface SageRun {
  run_id: string;
  local_date: string;
  state: "pending" | "running" | "completed" | "failed";
  stats: Record<string, number>;
  error: string;
  updated_at: string;
}

export interface SageCase {
  case_id: string;
  domain: string;
  process: string;
  task_type: string;
  goal: string;
  decision_summary: string;
  outcome: "success" | "partial" | "failure" | "cancelled" | "unknown";
  state: "open" | "pending_review" | "completed" | "archived";
  started_at: string;
  completed_at?: string;
}

export interface SageInsight {
  insight_id: string;
  title: string;
  content: string;
  applicability: Record<string, unknown>;
  evidence_case_ids: string[];
  confidence: number;
  risk_level: SageRiskLevel;
  state:
    | "observed"
    | "draft"
    | "validating"
    | "approved"
    | "active"
    | "rejected"
    | "superseded"
    | "rolled_back"
    | "archived";
  created_at: string;
  updated_at: string;
}

export interface SageKnowledgeItem {
  item_id: string;
  kind:
    | "anchor"
    | "fact"
    | "rule"
    | "preference"
    | "insight"
    | "warning"
    | "exception";
  title: string;
  content: string;
  structured_data: Record<string, unknown>;
  confidence: number;
  importance: number;
  utility: number;
  state:
    | "draft"
    | "validating"
    | "active"
    | "disputed"
    | "superseded"
    | "archived"
    | "erased";
  version: number;
  updated_at: string;
}

export interface SagePlaybook {
  playbook_id: string;
  name: string;
  steps: Array<Record<string, unknown>>;
  pitfalls: string[];
  acceptance_criteria: string[];
  state: "draft" | "testing" | "active" | "deprecated" | "rolled_back";
  version: number;
  evidence_count: number;
  success_rate: number;
  updated_at: string;
}

export interface SageSignal {
  signal_id: string;
  source_id: string;
  kind: "feedback" | "outcome";
  value: number;
  verdict?: "useful" | "irrelevant" | "wrong" | "outdated";
  receipt_id?: string;
  occurred_at: string;
}

export interface SagePage<T> {
  items: T[];
  offset: number;
  limit: number;
  has_more: boolean;
}
