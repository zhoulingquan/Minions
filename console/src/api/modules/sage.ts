import { request } from "../request";
import type {
  SageActivationMode,
  SageCandidate,
  SageCase,
  SageInsight,
  SageJob,
  SageKnowledgeItem,
  SageOverview,
  SagePage,
  SagePolicy,
  SageReceipt,
  SageRiskLevel,
  SageRun,
  SagePlaybook,
  SageSignal,
} from "../types/sage";

const agentHeaders = (agentId: string): HeadersInit => ({
  "X-Agent-Id": agentId,
});

export const sageApi = {
  getSageOverview: (agentId: string) =>
    request<SageOverview>("/sage/overview", {
      headers: agentHeaders(agentId),
    }),

  listSageCandidates: (agentId: string) =>
    request<SagePage<SageCandidate>>("/sage/candidates?limit=200", {
      headers: agentHeaders(agentId),
    }),

  listSageReceipts: (agentId: string) =>
    request<SagePage<SageReceipt>>("/sage/receipts?limit=100", {
      headers: agentHeaders(agentId),
    }),

  listSageJobs: (agentId: string) =>
    request<SagePage<SageJob>>("/sage/jobs?limit=100", {
      headers: agentHeaders(agentId),
    }),

  listSageRuns: (agentId: string) =>
    request<SagePage<SageRun>>("/sage/runs?limit=100", {
      headers: agentHeaders(agentId),
    }),

  listSageCases: (agentId: string) =>
    request<SagePage<SageCase>>("/sage/cases?limit=200", {
      headers: agentHeaders(agentId),
    }),

  reviewSageCase: (
    agentId: string,
    caseId: string,
    outcome: "success" | "partial" | "failure" | "cancelled",
    decisionSummary: string,
  ) =>
    request<{ case: SageCase; insight: SageInsight | null }>(
      `/sage/cases/${caseId}/review`,
      {
        method: "POST",
        headers: agentHeaders(agentId),
        body: JSON.stringify({
          outcome,
          decision_summary: decisionSummary,
          outcome_metrics: {},
        }),
      },
    ),

  listSageInsights: (agentId: string) =>
    request<SagePage<SageInsight>>("/sage/insights?limit=200", {
      headers: agentHeaders(agentId),
    }),

  reviseSageInsight: (
    agentId: string,
    insightId: string,
    title: string,
    content: string,
    applicability: Record<string, unknown>,
  ) =>
    request<SageInsight>(`/sage/insights/${insightId}`, {
      method: "PUT",
      headers: agentHeaders(agentId),
      body: JSON.stringify({ title, content, applicability }),
    }),

  listSageKnowledge: (agentId: string) =>
    request<SagePage<SageKnowledgeItem>>("/sage/items?limit=200", {
      headers: agentHeaders(agentId),
    }),

  actOnSageKnowledge: (
    agentId: string,
    itemId: string,
    action: "archive" | "dispute",
  ) =>
    request<SageKnowledgeItem>(`/sage/items/${itemId}/${action}`, {
      method: "POST",
      headers: agentHeaders(agentId),
    }),

  listSagePlaybooks: (agentId: string) =>
    request<SagePage<SagePlaybook>>("/sage/playbooks?limit=200", {
      headers: agentHeaders(agentId),
    }),

  listSageSignals: (agentId: string) =>
    request<SagePage<SageSignal>>("/sage/signals?limit=200", {
      headers: agentHeaders(agentId),
    }),

  recordSageFeedback: (
    agentId: string,
    receiptId: string,
    verdict: "useful" | "irrelevant" | "wrong" | "outdated",
    sourceId?: string,
  ) =>
    request("/sage/feedback", {
      method: "POST",
      headers: agentHeaders(agentId),
      body: JSON.stringify({
        receipt_id: receiptId,
        verdict,
        source_id: sourceId,
        comment: "",
      }),
    }),

  actOnSageInsight: (
    agentId: string,
    insightId: string,
    action: "validate" | "approve" | "reject" | "activate" | "rollback",
  ) =>
    request<SageInsight>(`/sage/insights/${insightId}/${action}`, {
      method: "POST",
      headers: agentHeaders(agentId),
    }),

  updateSagePolicy: (
    agentId: string,
    capability: SagePolicy["capability"],
    mode: SageActivationMode,
    maxAutoRisk: SageRiskLevel,
  ) =>
    request<SagePolicy>(`/sage/policies/${capability}`, {
      method: "PUT",
      headers: agentHeaders(agentId),
      body: JSON.stringify({ mode, max_auto_risk: maxAutoRisk }),
    }),

  actOnSageCandidate: (
    agentId: string,
    candidateId: string,
    action: "approve" | "reject" | "apply" | "rollback",
  ) =>
    request<SageCandidate>(`/sage/candidates/${candidateId}/${action}`, {
      method: "POST",
      headers: agentHeaders(agentId),
    }),

  scheduleSageMaintenance: (agentId: string) =>
    request<{ items: SageJob[] }>("/sage/maintenance", {
      method: "POST",
      headers: agentHeaders(agentId),
      body: JSON.stringify({}),
    }),
};
