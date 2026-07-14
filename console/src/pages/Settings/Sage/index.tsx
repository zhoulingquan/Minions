import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type CSSProperties,
} from "react";
import {
  Alert,
  Button,
  Empty,
  Input,
  Modal,
  Segmented,
  Skeleton,
  Tabs,
  Tag,
  Tooltip,
} from "antd";
import {
  BookOpen,
  BookMarked,
  Archive,
  CheckCircle2,
  ChevronRight,
  Clock3,
  History,
  Library,
  MessageSquareText,
  Pencil,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Sprout,
  XCircle,
} from "lucide-react";
import api from "../../../api";
import type {
  SageActivationMode,
  SageCandidate,
  SageCase,
  SageInsight,
  SageJob,
  SageKnowledgeItem,
  SageOverview,
  SagePolicy,
  SageReceipt,
  SageRun,
  SagePlaybook,
  SageSignal,
} from "../../../api/types/sage";
import { PageHeader } from "@/components/PageHeader";
import { useAppMessage } from "../../../hooks/useAppMessage";
import { useAgentStore } from "../../../stores/agentStore";
import styles from "./index.module.less";

const MODE_OPTIONS: Array<{ label: string; value: SageActivationMode }> = [
  { label: "关闭", value: "off" },
  { label: "只观察", value: "shadow" },
  { label: "审核后采用", value: "approval" },
  { label: "自动采用", value: "auto" },
];

const CAPABILITY_COPY: Record<
  SagePolicy["capability"],
  { name: string; description: string }
> = {
  hybrid_recall: {
    name: "业务经验召回",
    description: "结合业务对象、时间和历史效果，为当前任务寻找最相关经验。",
  },
  feedback_learning: {
    name: "反馈学习",
    description: "根据有用、错误、过期等反馈，谨慎调整经验可信度。",
  },
  nightly_consolidation: {
    name: "夜间知识整理",
    description: "定期发现重复、冲突、过期内容和可复用的工作方法。",
  },
  knowledge_merge: {
    name: "知识合并",
    description: "把重复经验归并，并保留原始版本和完整回滚记录。",
  },
  playbook_promotion: {
    name: "方法沉淀",
    description: "将多次验证有效的心得整理为可复用的业务手册。",
  },
  cross_scope_transfer: {
    name: "跨范围复用",
    description: "控制个人、项目、团队之间是否允许迁移已有经验。",
  },
};

const KIND_COPY: Record<SageCandidate["kind"], string> = {
  duplicate: "发现重复经验",
  conflict: "发现相互冲突的说法",
  stale: "发现过期内容",
  low_utility: "发现长期低效经验",
  playbook_promotion: "可沉淀为业务手册",
};

const JOB_COPY: Record<string, string> = {
  reflect_case: "复盘已完成业务",
  consolidate_tenant: "整理知识库",
  recalculate_utility: "校准经验效果",
  evaluate_recall: "评估经验召回",
};

function formatTime(value?: string): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function stateTag(state: SageCandidate["state"]) {
  const map = {
    proposed: ["待审核", "gold"],
    approved: ["已批准", "blue"],
    applied: ["已采用", "green"],
    rejected: ["已拒绝", "default"],
    stale: ["需重新检查", "orange"],
    rolled_back: ["已回滚", "purple"],
  } as const;
  return <Tag color={map[state][1]}>{map[state][0]}</Tag>;
}

function SagePage() {
  const { message } = useAppMessage();
  const selectedAgent = useAgentStore((state) => state.selectedAgent);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [overview, setOverview] = useState<SageOverview | null>(null);
  const [candidates, setCandidates] = useState<SageCandidate[]>([]);
  const [receipts, setReceipts] = useState<SageReceipt[]>([]);
  const [jobs, setJobs] = useState<SageJob[]>([]);
  const [runs, setRuns] = useState<SageRun[]>([]);
  const [cases, setCases] = useState<SageCase[]>([]);
  const [insights, setInsights] = useState<SageInsight[]>([]);
  const [knowledge, setKnowledge] = useState<SageKnowledgeItem[]>([]);
  const [playbooks, setPlaybooks] = useState<SagePlaybook[]>([]);
  const [signals, setSignals] = useState<SageSignal[]>([]);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [selectedCandidate, setSelectedCandidate] =
    useState<SageCandidate | null>(null);
  const [selectedCase, setSelectedCase] = useState<SageCase | null>(null);
  const [reviewSummary, setReviewSummary] = useState("");
  const [selectedInsight, setSelectedInsight] = useState<SageInsight | null>(
    null,
  );
  const [insightTitle, setInsightTitle] = useState("");
  const [insightContent, setInsightContent] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [
        nextOverview,
        candidatePage,
        receiptPage,
        jobPage,
        runPage,
        casePage,
        insightPage,
        knowledgePage,
        playbookPage,
        signalPage,
      ] = await Promise.all([
        api.getSageOverview(selectedAgent),
        api.listSageCandidates(selectedAgent),
        api.listSageReceipts(selectedAgent),
        api.listSageJobs(selectedAgent),
        api.listSageRuns(selectedAgent),
        api.listSageCases(selectedAgent),
        api.listSageInsights(selectedAgent),
        api.listSageKnowledge(selectedAgent),
        api.listSagePlaybooks(selectedAgent),
        api.listSageSignals(selectedAgent),
      ]);
      setOverview(nextOverview);
      setCandidates(candidatePage.items);
      setReceipts(receiptPage.items);
      setJobs(jobPage.items);
      setRuns(runPage.items);
      setCases(casePage.items);
      setInsights(insightPage.items);
      setKnowledge(knowledgePage.items);
      setPlaybooks(playbookPage.items);
      setSignals(signalPage.items);
    } catch (reason) {
      const detail = reason instanceof Error ? reason.message : "未知错误";
      setError(detail);
    } finally {
      setLoading(false);
    }
  }, [selectedAgent]);

  useEffect(() => {
    void load();
  }, [load]);

  const healthScore = useMemo(() => {
    if (!overview) return 0;
    const { snapshot } = overview;
    const activeRate = snapshot.knowledge_total
      ? snapshot.active_knowledge / snapshot.knowledge_total
      : 1;
    return Math.round(
      Math.max(
        0,
        Math.min(
          100,
          activeRate * 50 +
            snapshot.positive_signal_rate * 30 +
            (1 - snapshot.degradation_rate) * 20,
        ),
      ),
    );
  }, [overview]);

  const pending = candidates.filter(
    (item) => item.state === "proposed" || item.state === "approved",
  );
  const pendingCases = cases.filter((item) => item.state === "pending_review");

  const updatePolicy = async (policy: SagePolicy, mode: SageActivationMode) => {
    setBusyKey(policy.capability);
    try {
      await api.updateSagePolicy(
        selectedAgent,
        policy.capability,
        mode,
        policy.max_auto_risk,
      );
      message.success("成长规则已更新");
      await load();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "更新失败");
    } finally {
      setBusyKey(null);
    }
  };

  const actOnCandidate = async (
    candidate: SageCandidate,
    action: "approve" | "reject" | "apply" | "rollback",
  ) => {
    setBusyKey(`${candidate.candidate_id}:${action}`);
    try {
      await api.actOnSageCandidate(
        selectedAgent,
        candidate.candidate_id,
        action,
      );
      message.success(
        action === "rollback" ? "已恢复到采用前版本" : "处理完成",
      );
      setSelectedCandidate(null);
      await load();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "处理失败");
    } finally {
      setBusyKey(null);
    }
  };

  const scheduleMaintenance = async () => {
    setBusyKey("maintenance");
    try {
      await api.scheduleSageMaintenance(selectedAgent);
      message.success("本次知识整理已进入队列");
      await load();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "安排失败");
    } finally {
      setBusyKey(null);
    }
  };

  const reviewCase = async (
    outcome: "success" | "partial" | "failure" | "cancelled",
  ) => {
    if (!selectedCase) return;
    setBusyKey(`case:${selectedCase.case_id}`);
    try {
      await api.reviewSageCase(
        selectedAgent,
        selectedCase.case_id,
        outcome,
        reviewSummary,
      );
      message.success(
        outcome === "success" || outcome === "partial"
          ? "复盘完成，已形成心得候选"
          : "业务结果已记录",
      );
      setSelectedCase(null);
      setReviewSummary("");
      await load();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "复盘失败");
    } finally {
      setBusyKey(null);
    }
  };

  const actOnInsight = async (
    insight: SageInsight,
    action: "validate" | "approve" | "reject" | "activate" | "rollback",
  ) => {
    setBusyKey(`insight:${insight.insight_id}:${action}`);
    try {
      await api.actOnSageInsight(selectedAgent, insight.insight_id, action);
      message.success(action === "rollback" ? "心得已回滚" : "心得状态已更新");
      await load();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "操作失败");
    } finally {
      setBusyKey(null);
    }
  };

  const openInsightEditor = (insight: SageInsight) => {
    setSelectedInsight(insight);
    setInsightTitle(insight.title);
    setInsightContent(insight.content);
  };

  const saveInsightRevision = async () => {
    if (!selectedInsight || !insightTitle.trim() || !insightContent.trim())
      return;
    setBusyKey(`insight:${selectedInsight.insight_id}:revise`);
    try {
      await api.reviseSageInsight(
        selectedAgent,
        selectedInsight.insight_id,
        insightTitle.trim(),
        insightContent.trim(),
        selectedInsight.applicability,
      );
      message.success("心得已修订，将重新经过验证");
      setSelectedInsight(null);
      await load();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "修订失败");
    } finally {
      setBusyKey(null);
    }
  };

  const actOnKnowledge = async (
    item: SageKnowledgeItem,
    action: "archive" | "dispute",
  ) => {
    setBusyKey(`knowledge:${item.item_id}:${action}`);
    try {
      await api.actOnSageKnowledge(selectedAgent, item.item_id, action);
      message.success(
        action === "archive" ? "知识已归档" : "知识已标记为有争议",
      );
      await load();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "操作失败");
    } finally {
      setBusyKey(null);
    }
  };

  const recordFeedback = async (
    receipt: SageReceipt,
    sourceId: string,
    verdict: "useful" | "irrelevant" | "wrong" | "outdated",
  ) => {
    setBusyKey(`feedback:${receipt.receipt_id}:${sourceId}`);
    try {
      await api.recordSageFeedback(
        selectedAgent,
        receipt.receipt_id,
        verdict,
        sourceId,
      );
      message.success("反馈已记录，系统会谨慎调整经验效果");
      await load();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "反馈失败");
    } finally {
      setBusyKey(null);
    }
  };

  const candidateActions = (candidate: SageCandidate) => {
    if (candidate.state === "proposed") {
      return (
        <>
          <Button
            onClick={() => void actOnCandidate(candidate, "reject")}
            loading={busyKey === `${candidate.candidate_id}:reject`}
          >
            暂不采用
          </Button>
          <Button
            type="primary"
            onClick={() => void actOnCandidate(candidate, "approve")}
            loading={busyKey === `${candidate.candidate_id}:approve`}
          >
            批准建议
          </Button>
        </>
      );
    }
    if (candidate.state === "approved") {
      return (
        <Button
          type="primary"
          onClick={() => void actOnCandidate(candidate, "apply")}
          loading={busyKey === `${candidate.candidate_id}:apply`}
        >
          应用到知识库
        </Button>
      );
    }
    if (candidate.state === "applied") {
      return (
        <Button
          icon={<RotateCcw size={15} />}
          onClick={() => void actOnCandidate(candidate, "rollback")}
          loading={busyKey === `${candidate.candidate_id}:rollback`}
        >
          回滚
        </Button>
      );
    }
    return null;
  };

  if (loading && !overview) {
    return (
      <div className={styles.page}>
        <PageHeader parent="工作区" current="经验成长" />
        <div className={styles.loading} aria-label="正在加载经验成长数据">
          <Skeleton active paragraph={{ rows: 8 }} />
        </div>
      </div>
    );
  }

  if (error && !overview) {
    const permissionDenied = /permission|403|denied/i.test(error);
    return (
      <div className={styles.page}>
        <PageHeader parent="工作区" current="经验成长" />
        <div className={styles.errorState}>
          <ShieldCheck size={38} />
          <h2>
            {permissionDenied
              ? "你没有管理经验库的权限"
              : "经验中心暂时无法读取"}
          </h2>
          <p>{permissionDenied ? "请联系管理员授予 SAGE 管理权限。" : error}</p>
          <Button onClick={() => void load()}>重新加载</Button>
        </div>
      </div>
    );
  }

  if (!overview) return null;

  const { snapshot } = overview;
  const overviewTab = (
    <div className={styles.tabContent}>
      <section className={styles.hero}>
        <div>
          <div className={styles.eyebrow}>
            <Sprout size={15} /> 持续成长中的业务经验
          </div>
          <h1>让每一次完成的工作，成为下一次的起点。</h1>
          <p>
            系统正在沉淀有效做法、识别过期信息，并把有风险的改变留给你决定。
          </p>
          <div className={styles.heroActions}>
            <Button
              type="primary"
              icon={<Sparkles size={16} />}
              onClick={() => void scheduleMaintenance()}
              loading={busyKey === "maintenance"}
            >
              立即整理一次
            </Button>
            <span>最近评估于 {formatTime(snapshot.generated_at)}</span>
          </div>
        </div>
        <div
          className={styles.healthDial}
          style={{ "--health": `${healthScore * 3.6}deg` } as CSSProperties}
          aria-label={`知识健康度 ${healthScore} 分`}
        >
          <div>
            <strong>{healthScore}</strong>
            <span>知识健康度</span>
          </div>
        </div>
      </section>

      <section className={styles.metricGrid}>
        <article className={styles.metricCard}>
          <BookOpen size={20} />
          <div>
            <strong>{snapshot.active_knowledge}</strong>
            <span>条有效经验</span>
          </div>
          <small>共沉淀 {snapshot.knowledge_total} 条知识</small>
        </article>
        <article className={styles.metricCard}>
          <CheckCircle2 size={20} />
          <div>
            <strong>{Math.round(snapshot.positive_signal_rate * 100)}%</strong>
            <span>正向反馈</span>
          </div>
          <small>来自 {snapshot.signal_count} 次真实使用</small>
        </article>
        <article className={styles.metricCard}>
          <Clock3 size={20} />
          <div>
            <strong>{snapshot.pending_candidates}</strong>
            <span>项等待决定</span>
          </div>
          <small>高风险改变不会自动生效</small>
        </article>
        <article className={styles.metricCard}>
          <History size={20} />
          <div>
            <strong>{snapshot.completed_runs}</strong>
            <span>次完整整理</span>
          </div>
          <small>
            {snapshot.failed_runs
              ? `${snapshot.failed_runs} 次需要关注`
              : "运行稳定"}
          </small>
        </article>
      </section>

      <section className={styles.splitGrid}>
        <div className={styles.panel}>
          <div className={styles.panelHeader}>
            <div>
              <span className={styles.panelKicker}>需要你的判断</span>
              <h2>待处理建议</h2>
            </div>
            <Tag color={pending.length ? "gold" : "green"}>
              {pending.length} 项
            </Tag>
          </div>
          {pending.length ? (
            pending.slice(0, 4).map((candidate) => (
              <button
                className={styles.candidateRow}
                key={candidate.candidate_id}
                onClick={() => setSelectedCandidate(candidate)}
              >
                <span className={styles.kindMark} data-kind={candidate.kind} />
                <span>
                  <strong>{KIND_COPY[candidate.kind]}</strong>
                  <small>{candidate.rationale}</small>
                </span>
                <ChevronRight size={17} />
              </button>
            ))
          ) : (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="暂时没有需要处理的建议"
            />
          )}
        </div>

        <div className={styles.panel}>
          <div className={styles.panelHeader}>
            <div>
              <span className={styles.panelKicker}>最近发生</span>
              <h2>成长轨迹</h2>
            </div>
          </div>
          <div className={styles.timeline}>
            {jobs.slice(0, 5).map((job) => (
              <div className={styles.timelineItem} key={job.job_id}>
                <span data-state={job.state} />
                <div>
                  <strong>{JOB_COPY[job.job_type] ?? job.job_type}</strong>
                  <small>
                    {formatTime(job.updated_at)} ·{" "}
                    {job.state === "completed"
                      ? "已完成"
                      : job.state === "failed"
                      ? "需要检查"
                      : "处理中"}
                  </small>
                </div>
              </div>
            ))}
            {!jobs.length && (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="完成业务后，这里会出现成长记录"
              />
            )}
          </div>
        </div>
      </section>
    </div>
  );

  const policiesTab = (
    <div className={styles.policyGrid}>
      {overview.policies.map((policy) => {
        const copy = CAPABILITY_COPY[policy.capability];
        return (
          <article className={styles.policyCard} key={policy.policy_id}>
            <div className={styles.policyTop}>
              <div>
                <h3>{copy.name}</h3>
                <p>{copy.description}</p>
              </div>
              <Tooltip title={`当前规则版本 ${policy.version}`}>
                <ShieldCheck size={19} />
              </Tooltip>
            </div>
            <Segmented
              block
              options={MODE_OPTIONS}
              value={policy.mode}
              disabled={busyKey === policy.capability}
              onChange={(value) =>
                void updatePolicy(policy, value as SageActivationMode)
              }
            />
            <div className={styles.policyFoot}>
              <span>
                {policy.mode === "auto"
                  ? "仅低风险改变可自动生效"
                  : policy.mode === "approval"
                  ? "生成建议，等待人工确认"
                  : policy.mode === "shadow"
                  ? "计算效果，但不改变现有知识"
                  : "此能力不运行"}
              </span>
              <Tag>{policy.scope ? "范围规则" : "租户默认"}</Tag>
            </div>
          </article>
        );
      })}
    </div>
  );

  const decisionsTab = (
    <div className={styles.decisionList}>
      {candidates.length ? (
        candidates.map((candidate) => (
          <article className={styles.decisionCard} key={candidate.candidate_id}>
            <div className={styles.decisionMain}>
              <span className={styles.kindMark} data-kind={candidate.kind} />
              <div>
                <div className={styles.decisionTitle}>
                  <h3>{KIND_COPY[candidate.kind]}</h3>
                  {stateTag(candidate.state)}
                  <Tag>
                    {candidate.risk_level === "low"
                      ? "低风险"
                      : candidate.risk_level === "medium"
                      ? "中风险"
                      : "高风险"}
                  </Tag>
                </div>
                <p>{candidate.rationale}</p>
                <small>
                  {candidate.source_ids.length} 条来源 ·{" "}
                  {formatTime(candidate.updated_at)}
                </small>
              </div>
            </div>
            <div className={styles.decisionActions}>
              <Button onClick={() => setSelectedCandidate(candidate)}>
                查看对比
              </Button>
              {candidateActions(candidate)}
            </div>
          </article>
        ))
      ) : (
        <div className={styles.emptyPanel}>
          <Empty description="还没有整理建议" />
        </div>
      )}
    </div>
  );

  const historyTab = (
    <div className={styles.historyGrid}>
      <section className={styles.panel}>
        <div className={styles.panelHeader}>
          <div>
            <span className={styles.panelKicker}>为什么想起这条经验</span>
            <h2>召回说明</h2>
          </div>
        </div>
        {receipts.map((receipt) => (
          <article className={styles.receipt} key={receipt.receipt_id}>
            <div>
              <strong>{receipt.query || "业务上下文召回"}</strong>
              <Tag>
                {receipt.ranking_mode === "shadow" ? "对照观察" : "已应用"}
              </Tag>
            </div>
            <p>
              选取 {receipt.selections.length} 条经验
              {receipt.degradations.length
                ? `，${receipt.degradations.length} 项能力降级`
                : "，所有检索能力正常"}
            </p>
            <small>{formatTime(receipt.generated_at)}</small>
          </article>
        ))}
        {!receipts.length && (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="使用经验后会生成可解释的召回记录"
          />
        )}
      </section>
      <section className={styles.panel}>
        <div className={styles.panelHeader}>
          <div>
            <span className={styles.panelKicker}>可恢复、可追溯</span>
            <h2>整理批次</h2>
          </div>
        </div>
        {runs.map((run) => (
          <article className={styles.runRow} key={run.run_id}>
            <span className={styles.runIcon} data-state={run.state}>
              {run.state === "completed" ? (
                <CheckCircle2 size={17} />
              ) : run.state === "failed" ? (
                <XCircle size={17} />
              ) : (
                <RefreshCw size={17} />
              )}
            </span>
            <div>
              <strong>{run.local_date} 知识整理</strong>
              <small>
                扫描 {run.stats.scanned ?? 0} 条 ·{" "}
                {run.state === "completed"
                  ? "已完成"
                  : run.state === "failed"
                  ? "失败"
                  : "处理中"}
              </small>
            </div>
          </article>
        ))}
        {!runs.length && (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="尚未运行夜间整理"
          />
        )}
      </section>
    </div>
  );

  const casesTab = (
    <div className={styles.decisionList}>
      {cases.length ? (
        cases.map((item) => (
          <article className={styles.decisionCard} key={item.case_id}>
            <div className={styles.decisionMain}>
              <span
                className={styles.kindMark}
                data-kind={
                  item.state === "pending_review" ? "stale" : "duplicate"
                }
              />
              <div>
                <div className={styles.decisionTitle}>
                  <h3>
                    {item.goal || item.process || item.task_type || "业务任务"}
                  </h3>
                  <Tag
                    color={item.state === "pending_review" ? "gold" : "green"}
                  >
                    {item.state === "pending_review" ? "等待复盘" : "已完成"}
                  </Tag>
                </div>
                <p>
                  {item.decision_summary ||
                    "系统已保留执行过程，确认结果后会自动提炼可复用做法。"}
                </p>
                <small>
                  {item.process || item.domain || "通用业务"} ·{" "}
                  {formatTime(item.started_at)}
                </small>
              </div>
            </div>
            {item.state === "pending_review" && (
              <Button
                type="primary"
                onClick={() => {
                  setSelectedCase(item);
                  setReviewSummary("");
                }}
              >
                完成复盘
              </Button>
            )}
          </article>
        ))
      ) : (
        <div className={styles.emptyPanel}>
          <Empty description="完成一次业务后，这里会出现待复盘记录" />
        </div>
      )}
    </div>
  );

  const insightsTab = (
    <div className={styles.decisionList}>
      {insights.length ? (
        insights.map((insight) => (
          <article className={styles.decisionCard} key={insight.insight_id}>
            <div className={styles.decisionMain}>
              <span
                className={styles.kindMark}
                data-kind="playbook_promotion"
              />
              <div>
                <div className={styles.decisionTitle}>
                  <h3>{insight.title}</h3>
                  <Tag
                    color={
                      insight.state === "active"
                        ? "green"
                        : insight.state === "validating"
                        ? "gold"
                        : "blue"
                    }
                  >
                    {insight.state === "observed"
                      ? "等待结果确认"
                      : insight.state === "draft"
                      ? "积累证据"
                      : insight.state === "validating"
                      ? "等待审核"
                      : insight.state === "approved"
                      ? "已批准"
                      : insight.state === "active"
                      ? "使用中"
                      : insight.state === "rolled_back"
                      ? "已回滚"
                      : insight.state === "superseded"
                      ? "已合并"
                      : insight.state === "archived"
                      ? "已归档"
                      : "已拒绝"}
                  </Tag>
                </div>
                <p>{insight.content}</p>
                <small>
                  {insight.evidence_case_ids.length} 个业务案例 · 可信度{" "}
                  {Math.round(insight.confidence * 100)}%
                </small>
              </div>
            </div>
            <div className={styles.decisionActions}>
              {(insight.state === "observed" ||
                insight.state === "draft" ||
                insight.state === "validating") && (
                <Button
                  icon={<Pencil size={14} />}
                  onClick={() => openInsightEditor(insight)}
                >
                  修订
                </Button>
              )}
              {insight.state === "draft" && (
                <Button onClick={() => void actOnInsight(insight, "validate")}>
                  提交验证
                </Button>
              )}
              {insight.state === "validating" && (
                <>
                  <Button onClick={() => void actOnInsight(insight, "reject")}>
                    拒绝
                  </Button>
                  <Button
                    type="primary"
                    onClick={() => void actOnInsight(insight, "approve")}
                  >
                    批准
                  </Button>
                </>
              )}
              {insight.state === "approved" && (
                <Button
                  type="primary"
                  onClick={() => void actOnInsight(insight, "activate")}
                >
                  投入使用
                </Button>
              )}
              {insight.state === "active" && (
                <Button onClick={() => void actOnInsight(insight, "rollback")}>
                  回滚
                </Button>
              )}
            </div>
          </article>
        ))
      ) : (
        <div className={styles.emptyPanel}>
          <Empty description="复盘后的有效做法会在这里逐步成长" />
        </div>
      )}
    </div>
  );

  const knowledgeTab = (
    <div className={styles.decisionList}>
      {knowledge.length ? (
        knowledge.map((item) => (
          <article className={styles.decisionCard} key={item.item_id}>
            <div className={styles.decisionMain}>
              <span className={styles.memoryIcon}>
                <Library size={17} />
              </span>
              <div>
                <div className={styles.decisionTitle}>
                  <h3>{item.title}</h3>
                  <Tag
                    color={
                      item.state === "active"
                        ? "green"
                        : item.state === "disputed"
                        ? "orange"
                        : "default"
                    }
                  >
                    {item.state === "active"
                      ? "正在使用"
                      : item.state === "disputed"
                      ? "存在争议"
                      : item.state === "archived"
                      ? "已归档"
                      : item.state === "superseded"
                      ? "已有新版本"
                      : item.state}
                  </Tag>
                  <Tag>
                    {item.kind === "insight"
                      ? "心得"
                      : item.kind === "warning"
                      ? "提醒"
                      : item.kind === "rule"
                      ? "规则"
                      : "知识"}
                  </Tag>
                </div>
                <p>{item.content}</p>
                <small>
                  版本 {item.version} · 可信度{" "}
                  {Math.round(item.confidence * 100)}% · 使用效用{" "}
                  {Math.round(item.utility * 100)}%
                </small>
              </div>
            </div>
            {item.state === "active" && (
              <div className={styles.decisionActions}>
                <Button onClick={() => void actOnKnowledge(item, "dispute")}>
                  标记争议
                </Button>
                <Button
                  icon={<Archive size={14} />}
                  onClick={() => void actOnKnowledge(item, "archive")}
                >
                  归档
                </Button>
              </div>
            )}
          </article>
        ))
      ) : (
        <div className={styles.emptyPanel}>
          <Empty description="通过验证的心得会发布到这里" />
        </div>
      )}
    </div>
  );

  const playbooksTab = (
    <div className={styles.playbookGrid}>
      {playbooks.length ? (
        playbooks.map((playbook) => (
          <article className={styles.playbookCard} key={playbook.playbook_id}>
            <div className={styles.playbookTop}>
              <span>
                <BookMarked size={20} />
              </span>
              <div>
                <h3>{playbook.name}</h3>
                <Tag color={playbook.state === "active" ? "green" : "default"}>
                  {playbook.state === "active" ? "正在使用" : playbook.state}
                </Tag>
              </div>
            </div>
            <ol>
              {playbook.steps.slice(0, 8).map((step, index) => (
                <li key={`${playbook.playbook_id}:${index}`}>
                  {String(step.action ?? "业务步骤")}
                </li>
              ))}
            </ol>
            <small>
              {playbook.evidence_count} 个证据 · 成功率{" "}
              {Math.round(playbook.success_rate * 100)}% · 版本{" "}
              {playbook.version}
            </small>
          </article>
        ))
      ) : (
        <div className={styles.emptyPanel}>
          <Empty description="多次验证有效的心得会沉淀为业务手册" />
        </div>
      )}
    </div>
  );

  const feedbackTab = (
    <div className={styles.historyGrid}>
      <section className={styles.panel}>
        <div className={styles.panelHeader}>
          <div>
            <span className={styles.panelKicker}>帮助系统判断经验是否有效</span>
            <h2>评价召回结果</h2>
          </div>
          <MessageSquareText size={20} />
        </div>
        {receipts.map((receipt) => (
          <article className={styles.feedbackCard} key={receipt.receipt_id}>
            <strong>{receipt.query || "业务经验召回"}</strong>
            {receipt.selections.slice(0, 4).map((selection) => (
              <div className={styles.feedbackSource} key={selection.source_id}>
                <span>
                  {selection.title || `经验 ${selection.source_id.slice(0, 8)}`}
                </span>
                <div>
                  <Button
                    size="small"
                    onClick={() =>
                      void recordFeedback(
                        receipt,
                        selection.source_id,
                        "useful",
                      )
                    }
                  >
                    有帮助
                  </Button>
                  <Button
                    size="small"
                    onClick={() =>
                      void recordFeedback(
                        receipt,
                        selection.source_id,
                        "irrelevant",
                      )
                    }
                  >
                    不相关
                  </Button>
                  <Button
                    size="small"
                    danger
                    onClick={() =>
                      void recordFeedback(receipt, selection.source_id, "wrong")
                    }
                  >
                    错误
                  </Button>
                  <Button
                    size="small"
                    onClick={() =>
                      void recordFeedback(
                        receipt,
                        selection.source_id,
                        "outdated",
                      )
                    }
                  >
                    已过期
                  </Button>
                </div>
              </div>
            ))}
          </article>
        ))}
        {!receipts.length && (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="经验被使用后，可以在这里评价"
          />
        )}
      </section>
      <section className={styles.panel}>
        <div className={styles.panelHeader}>
          <div>
            <span className={styles.panelKicker}>缓慢调整，不直接覆盖正文</span>
            <h2>最近反馈</h2>
          </div>
        </div>
        {signals.slice(0, 30).map((signal) => (
          <div className={styles.signalRow} key={signal.signal_id}>
            <span data-positive={signal.value > 0}>
              {signal.value > 0 ? "+" : "−"}
            </span>
            <div>
              <strong>
                {signal.verdict === "useful"
                  ? "有帮助"
                  : signal.verdict === "irrelevant"
                  ? "不相关"
                  : signal.verdict === "wrong"
                  ? "错误"
                  : signal.verdict === "outdated"
                  ? "已过期"
                  : "业务结果反馈"}
              </strong>
              <small>
                {signal.source_id.slice(0, 12)} ·{" "}
                {formatTime(signal.occurred_at)}
              </small>
            </div>
          </div>
        ))}
        {!signals.length && (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="还没有使用反馈"
          />
        )}
      </section>
    </div>
  );

  return (
    <div className={styles.page}>
      <PageHeader
        parent="工作区"
        current="经验成长"
        extra={
          <Button
            icon={<RefreshCw size={15} />}
            onClick={() => void load()}
            loading={loading}
          >
            刷新
          </Button>
        }
      />
      {error && (
        <Alert
          banner
          type="warning"
          message="部分数据刷新失败，当前显示最近一次成功结果。"
        />
      )}
      <div className={styles.content}>
        <Tabs
          defaultActiveKey="overview"
          items={[
            { key: "overview", label: "总览", children: overviewTab },
            {
              key: "cases",
              label: `业务复盘 ${
                pendingCases.length ? `(${pendingCases.length})` : ""
              }`,
              children: casesTab,
            },
            {
              key: "insights",
              label: `心得 ${insights.length ? `(${insights.length})` : ""}`,
              children: insightsTab,
            },
            {
              key: "knowledge",
              label: `知识库 (${knowledge.length})`,
              children: knowledgeTab,
            },
            {
              key: "playbooks",
              label: `业务手册 (${playbooks.length})`,
              children: playbooksTab,
            },
            { key: "feedback", label: "使用反馈", children: feedbackTab },
            { key: "policies", label: "成长规则", children: policiesTab },
            {
              key: "decisions",
              label: `整理建议 ${pending.length ? `(${pending.length})` : ""}`,
              children: decisionsTab,
            },
            { key: "history", label: "运行记录", children: historyTab },
          ]}
        />
      </div>

      <Modal
        title={
          selectedCandidate ? KIND_COPY[selectedCandidate.kind] : "建议详情"
        }
        open={Boolean(selectedCandidate)}
        onCancel={() => setSelectedCandidate(null)}
        width={760}
        footer={selectedCandidate ? candidateActions(selectedCandidate) : null}
      >
        {selectedCandidate && (
          <div className={styles.comparison}>
            <p className={styles.rationale}>{selectedCandidate.rationale}</p>
            <div className={styles.comparisonGrid}>
              {Object.entries(selectedCandidate.before_snapshots).map(
                ([id, source], index) => (
                  <article key={id}>
                    <span>来源 {index + 1}</span>
                    <h4>{source.title || "未命名经验"}</h4>
                    <p>{source.content || "内容不可见"}</p>
                  </article>
                ),
              )}
            </div>
            <Alert
              showIcon
              type="info"
              message="所有改变都会记录原始版本，可在采用后回滚。"
            />
          </div>
        )}
      </Modal>

      <Modal
        title="确认业务结果并形成心得"
        open={Boolean(selectedCase)}
        onCancel={() => {
          setSelectedCase(null);
          setReviewSummary("");
        }}
        width={680}
        footer={null}
      >
        {selectedCase && (
          <div className={styles.comparison}>
            <Alert
              showIcon
              type="info"
              message={selectedCase.goal || "本次业务任务"}
              description="结果必须由有权限的成员确认，智能体不能自行宣称业务成功。"
            />
            <div>
              <h4>这次工作中，哪种做法值得下次复用？</h4>
              <Input.TextArea
                value={reviewSummary}
                onChange={(event) => setReviewSummary(event.target.value)}
                rows={5}
                maxLength={4000}
                showCount
                placeholder="可留空，系统会根据已记录的目标和执行结果生成保守摘要。"
              />
            </div>
            <div className={styles.decisionActions}>
              <Button
                onClick={() => void reviewCase("failure")}
                loading={busyKey === `case:${selectedCase.case_id}`}
              >
                未达成
              </Button>
              <Button
                onClick={() => void reviewCase("partial")}
                loading={busyKey === `case:${selectedCase.case_id}`}
              >
                部分达成
              </Button>
              <Button
                type="primary"
                onClick={() => void reviewCase("success")}
                loading={busyKey === `case:${selectedCase.case_id}`}
              >
                已成功完成
              </Button>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        title="修订心得候选"
        open={Boolean(selectedInsight)}
        onCancel={() => {
          setSelectedInsight(null);
          setInsightTitle("");
          setInsightContent("");
        }}
        okText="保存修订"
        cancelText="取消"
        confirmLoading={
          selectedInsight
            ? busyKey === `insight:${selectedInsight.insight_id}:revise`
            : false
        }
        okButtonProps={{
          disabled: !insightTitle.trim() || !insightContent.trim(),
        }}
        onOk={() => void saveInsightRevision()}
        width={720}
      >
        <div className={styles.insightEditor}>
          <Alert
            showIcon
            type="info"
            message="修订后会重新进入验证，不会直接覆盖正在使用的知识。"
          />
          <label>
            <span>心得标题</span>
            <Input
              value={insightTitle}
              onChange={(event) => setInsightTitle(event.target.value)}
              maxLength={240}
              showCount
            />
          </label>
          <label>
            <span>可复用做法与适用条件</span>
            <Input.TextArea
              value={insightContent}
              onChange={(event) => setInsightContent(event.target.value)}
              rows={8}
              maxLength={12000}
              showCount
            />
          </label>
        </div>
      </Modal>
    </div>
  );
}

export default SagePage;
