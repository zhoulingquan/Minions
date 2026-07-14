import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SagePage from "./index";

const mocks = vi.hoisted(() => ({
  getSageOverview: vi.fn(),
  listSageCandidates: vi.fn(),
  listSageReceipts: vi.fn(),
  listSageJobs: vi.fn(),
  listSageRuns: vi.fn(),
  listSageCases: vi.fn(),
  listSageInsights: vi.fn(),
  listSageKnowledge: vi.fn(),
  listSagePlaybooks: vi.fn(),
  listSageSignals: vi.fn(),
  reviewSageCase: vi.fn(),
  reviseSageInsight: vi.fn(),
  actOnSageInsight: vi.fn(),
  actOnSageKnowledge: vi.fn(),
  recordSageFeedback: vi.fn(),
  updateSagePolicy: vi.fn(),
  actOnSageCandidate: vi.fn(),
  scheduleSageMaintenance: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
}));

vi.mock("../../../api", () => ({
  default: {
    getSageOverview: mocks.getSageOverview,
    listSageCandidates: mocks.listSageCandidates,
    listSageReceipts: mocks.listSageReceipts,
    listSageJobs: mocks.listSageJobs,
    listSageRuns: mocks.listSageRuns,
    listSageCases: mocks.listSageCases,
    listSageInsights: mocks.listSageInsights,
    listSageKnowledge: mocks.listSageKnowledge,
    listSagePlaybooks: mocks.listSagePlaybooks,
    listSageSignals: mocks.listSageSignals,
    reviewSageCase: mocks.reviewSageCase,
    reviseSageInsight: mocks.reviseSageInsight,
    actOnSageInsight: mocks.actOnSageInsight,
    actOnSageKnowledge: mocks.actOnSageKnowledge,
    recordSageFeedback: mocks.recordSageFeedback,
    updateSagePolicy: mocks.updateSagePolicy,
    actOnSageCandidate: mocks.actOnSageCandidate,
    scheduleSageMaintenance: mocks.scheduleSageMaintenance,
  },
}));

vi.mock("../../../hooks/useAppMessage", () => ({
  useAppMessage: () => ({
    message: { success: mocks.success, error: mocks.error },
  }),
}));

vi.mock("../../../stores/agentStore", () => ({
  useAgentStore: (selector: (state: { selectedAgent: string }) => unknown) =>
    selector({ selectedAgent: "default" }),
}));

const overview = {
  snapshot: {
    tenant_id: "tenant-1",
    knowledge_total: 12,
    active_knowledge: 10,
    signal_count: 8,
    positive_signal_rate: 0.75,
    recall_count: 4,
    degradation_count: 0,
    degradation_rate: 0,
    pending_candidates: 1,
    applied_candidates: 2,
    rolled_back_candidates: 0,
    completed_runs: 3,
    failed_runs: 0,
    pending_jobs: 0,
    completed_jobs: 6,
    failed_jobs: 0,
    average_job_latency_ms: 120,
    generated_at: "2026-07-13T02:00:00Z",
  },
  policies: [
    {
      policy_id: "policy-1",
      tenant_id: "tenant-1",
      capability: "nightly_consolidation",
      mode: "shadow",
      scope: null,
      max_auto_risk: "low",
      settings: {},
      version: 1,
      updated_at: "2026-07-13T02:00:00Z",
    },
  ],
};

const candidate = {
  candidate_id: "candidate-1",
  run_id: "run-1",
  kind: "duplicate",
  action: "merge",
  source_ids: ["source-1", "source-2"],
  risk_level: "low",
  state: "proposed",
  rationale: "两条经验内容完全相同，可以保留一个权威版本。",
  proposed_change: {},
  before_snapshots: {
    "source-1": { title: "月结经验", content: "先核对总账" },
    "source-2": { title: "月结经验副本", content: "先核对总账" },
  },
  version: 1,
  created_at: "2026-07-13T02:00:00Z",
  updated_at: "2026-07-13T02:00:00Z",
};

describe("SagePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getSageOverview.mockResolvedValue(overview);
    mocks.listSageCandidates.mockResolvedValue({ items: [candidate] });
    mocks.listSageReceipts.mockResolvedValue({ items: [] });
    mocks.listSageJobs.mockResolvedValue({ items: [] });
    mocks.listSageRuns.mockResolvedValue({ items: [] });
    mocks.listSageCases.mockResolvedValue({ items: [] });
    mocks.listSageInsights.mockResolvedValue({ items: [] });
    mocks.listSageKnowledge.mockResolvedValue({ items: [] });
    mocks.listSagePlaybooks.mockResolvedValue({ items: [] });
    mocks.listSageSignals.mockResolvedValue({ items: [] });
    mocks.actOnSageCandidate.mockResolvedValue({
      ...candidate,
      state: "approved",
    });
  });

  it("shows knowledge health and pending decisions", async () => {
    render(<SagePage />);

    expect(
      await screen.findByText("让每一次完成的工作，成为下一次的起点。"),
    ).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("条有效经验")).toBeInTheDocument();
    expect(screen.getByText("发现重复经验")).toBeInTheDocument();
    expect(mocks.getSageOverview).toHaveBeenCalledWith("default");
  });

  it("supports reviewing and approving a candidate", async () => {
    const user = userEvent.setup();
    render(<SagePage />);
    await screen.findByText("让每一次完成的工作，成为下一次的起点。");

    await user.click(screen.getByRole("tab", { name: /整理建议/ }));
    await user.click(screen.getByRole("button", { name: "批准建议" }));

    await waitFor(() =>
      expect(mocks.actOnSageCandidate).toHaveBeenCalledWith(
        "default",
        "candidate-1",
        "approve",
      ),
    );
  });

  it("renders a permission-oriented error state", async () => {
    mocks.getSageOverview.mockRejectedValue(
      new Error("403 SAGE permission denied"),
    );
    render(<SagePage />);
    expect(
      await screen.findByText("你没有管理经验库的权限"),
    ).toBeInTheDocument();
  });

  it("exposes the complete governed memory workspace", async () => {
    render(<SagePage />);
    await screen.findByText("让每一次完成的工作，成为下一次的起点。");

    expect(screen.getByRole("tab", { name: "业务复盘" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "心得" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "知识库 (0)" })).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: "业务手册 (0)" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "使用反馈" })).toBeInTheDocument();
  });
});
