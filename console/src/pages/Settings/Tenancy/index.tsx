import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Empty,
  Form,
  Input,
  Modal,
  Progress,
  Select,
  Skeleton,
  Table,
  Tabs,
  Tag,
  Tooltip,
} from "antd";
import {
  Activity,
  Bot,
  Building2,
  CheckCircle2,
  Copy,
  HardDrive,
  History,
  Plus,
  RefreshCw,
  ShieldCheck,
  UserPlus,
  Users,
} from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { tenancyApi } from "../../../api/modules/tenancy";
import type {
  MembershipStatus,
  TenantAgentGrant,
  TenantAuditEvent,
  TenantInvite,
  TenantMember,
  TenantOverview,
  TenantRole,
  TenantSpace,
} from "../../../api/types/tenancy";
import { setAuthToken } from "../../../api/config";
import { useAppMessage } from "../../../hooks/useAppMessage";
import styles from "./index.module.less";

const ROLE_LABELS: Record<TenantRole, string> = {
  owner: "所有者",
  admin: "管理员",
  operator: "业务运营",
  member: "成员",
  viewer: "只读成员",
};

const ACTION_LABELS: Record<string, string> = {
  "tenant.bootstrap": "创建企业空间",
  "tenant.provision": "新建企业空间",
  "tenant.switch": "切换企业空间",
  "member.invite": "邀请成员",
  "member.invite.revoke": "撤销成员邀请",
  "member.accept_invite": "成员加入",
  "member.update": "调整成员权限",
  "agent.create": "创建智能体",
  "agent.archive": "归档智能体",
  "migration.agents.import": "接入原有智能体",
  "session.revoke": "退出会话",
  "session.revoke_all": "结束全部会话",
  "user.profile.update": "更新账户资料",
};

function formatTime(value?: string): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function usagePercent(value: number, total: number): number {
  return total ? Math.min(100, Math.round((value / total) * 100)) : 0;
}

export default function TenancyPage() {
  const { message } = useAppMessage();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [overview, setOverview] = useState<TenantOverview | null>(null);
  const [members, setMembers] = useState<TenantMember[]>([]);
  const [invites, setInvites] = useState<TenantInvite[]>([]);
  const [agents, setAgents] = useState<TenantAgentGrant[]>([]);
  const [audit, setAudit] = useState<TenantAuditEvent[]>([]);
  const [spaces, setSpaces] = useState<TenantSpace[]>([]);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [issuedInviteToken, setIssuedInviteToken] = useState<string | null>(null);
  const [editMember, setEditMember] = useState<TenantMember | null>(null);
  const [busy, setBusy] = useState(false);
  const [inviteForm] = Form.useForm();
  const [createForm] = Form.useForm();
  const [memberForm] = Form.useForm();

  const canReadMembers = overview?.permissions.includes("member.read") ?? false;
  const canInvite = overview?.permissions.includes("member.invite") ?? false;
  const canManage = overview?.permissions.includes("member.manage") ?? false;
  const canCreateSpace = overview?.permissions.includes("tenant.manage") ?? false;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const nextOverview = await tenancyApi.getTenantOverview();
      const [spacePage, memberPage, invitePage, agentPage, auditPage] = await Promise.all([
        tenancyApi.listTenantSpaces(),
        nextOverview.permissions.includes("member.read")
          ? tenancyApi.listTenantMembers()
          : Promise.resolve({ items: [] }),
        nextOverview.permissions.includes("member.read")
          ? tenancyApi.listTenantInvites()
          : Promise.resolve({ items: [] }),
        tenancyApi.listTenantAgents(),
        nextOverview.permissions.includes("audit.read")
          ? tenancyApi.listTenantAudit()
          : Promise.resolve({ items: [] }),
      ]);
      setOverview(nextOverview);
      setSpaces(spacePage.items);
      setMembers(memberPage.items);
      setInvites(invitePage.items);
      setAgents(agentPage.items);
      setAudit(auditPage.items);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "企业空间读取失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const activeInvites = useMemo(
    () => invites.filter((item) => item.status === "pending"),
    [invites],
  );

  const submitInvite = async (values: {
    username: string;
    role: TenantRole;
  }) => {
    setBusy(true);
    try {
      const invite = await tenancyApi.inviteTenantMember(
        values.username,
        values.role,
      );
      setInviteOpen(false);
      inviteForm.resetFields();
      if (invite.invite_token) {
        setIssuedInviteToken(invite.invite_token);
        try {
          await navigator.clipboard.writeText(invite.invite_token);
          message.success("邀请已创建，邀请码已复制");
        } catch {
          message.success("邀请已创建，请复制下方的一次性邀请码");
        }
      } else {
        message.success("邀请已创建");
      }
      await load();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "邀请失败");
    } finally {
      setBusy(false);
    }
  };

  const copyInviteToken = async () => {
    if (!issuedInviteToken) return;
    try {
      await navigator.clipboard.writeText(issuedInviteToken);
      message.success("邀请码已复制");
    } catch {
      message.info("请长按或选中邀请码后复制");
    }
  };

  const submitCreateSpace = async (values: { name: string; slug: string }) => {
    setBusy(true);
    try {
      const session = await tenancyApi.createTenantSpace(values.name, values.slug);
      setAuthToken(session.token);
      message.success("新企业空间已创建，正在进入");
      window.location.reload();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "创建失败");
      setBusy(false);
    }
  };

  const switchSpace = async (slug: string) => {
    if (slug === overview?.tenant.slug) return;
    setBusy(true);
    try {
      const session = await tenancyApi.switchTenantSpace(slug);
      setAuthToken(session.token);
      window.location.reload();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "切换失败");
      setBusy(false);
    }
  };

  const submitMember = async (values: {
    role: TenantRole;
    status: MembershipStatus;
  }) => {
    if (!editMember) return;
    setBusy(true);
    try {
      await tenancyApi.updateTenantMember(editMember.user_id, values);
      setEditMember(null);
      message.success("成员权限已更新");
      await load();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "更新失败");
    } finally {
      setBusy(false);
    }
  };

  const revokeInvite = async (inviteId: string) => {
    setBusy(true);
    try {
      await tenancyApi.revokeTenantInvite(inviteId);
      message.success("邀请已撤销");
      await load();
    } catch (reason) {
      message.error(reason instanceof Error ? reason.message : "撤销失败");
    } finally {
      setBusy(false);
    }
  };

  if (loading && !overview) {
    return (
      <div className={styles.page}>
        <PageHeader parent="设置" current="企业空间" />
        <div className={styles.loading}><Skeleton active paragraph={{ rows: 10 }} /></div>
      </div>
    );
  }

  if (!overview) {
    return (
      <div className={styles.page}>
        <PageHeader parent="设置" current="企业空间" />
        <div className={styles.emptyState}>
          <ShieldCheck size={42} />
          <h2>企业空间暂时无法读取</h2>
          <p>{error || "请稍后重试"}</p>
          <Button onClick={() => void load()}>重新加载</Button>
        </div>
      </div>
    );
  }

  const { tenant, membership, quota, usage } = overview;
  const overviewPanel = (
    <div className={styles.panel}>
      <section className={styles.hero}>
        <div className={styles.heroCopy}>
          <span className={styles.eyebrow}><ShieldCheck size={15} /> 独立、安全、持续成长</span>
          <h1>{tenant.name}</h1>
          <p>这里汇总成员、智能体和经验治理情况。每一项业务数据都只属于当前企业空间。</p>
          <div className={styles.heroMeta}>
            <Tag color="green" icon={<CheckCircle2 size={12} />}>运行正常</Tag>
            <span>你的身份：{ROLE_LABELS[membership.role]}</span>
            <span>空间代号：{tenant.slug}</span>
          </div>
        </div>
        <div className={styles.monogram} aria-hidden>{tenant.name.slice(0, 1)}</div>
      </section>

      <section className={styles.metricGrid}>
        <article className={styles.metricCard}>
          <div className={styles.metricIcon}><Users size={20} /></div>
          <strong>{usage.members}<small> / {quota.max_members}</small></strong>
          <span>团队成员</span>
          <Progress percent={usagePercent(usage.members, quota.max_members)} showInfo={false} />
        </article>
        <article className={styles.metricCard}>
          <div className={styles.metricIcon}><Bot size={20} /></div>
          <strong>{usage.agents}<small> / {quota.max_agents}</small></strong>
          <span>企业智能体</span>
          <Progress percent={usagePercent(usage.agents, quota.max_agents)} showInfo={false} />
        </article>
        <article className={styles.metricCard}>
          <div className={styles.metricIcon}><Activity size={20} /></div>
          <strong>{usage.concurrent_tasks}<small> / {quota.max_concurrent_tasks}</small></strong>
          <span>同时运行任务</span>
          <Progress percent={usagePercent(usage.concurrent_tasks, quota.max_concurrent_tasks)} showInfo={false} />
        </article>
        <article className={styles.metricCard}>
          <div className={styles.metricIcon}><HardDrive size={20} /></div>
          <strong>{usage.storage_mb}<small> / {quota.max_storage_mb} MB</small></strong>
          <span>工作区存储</span>
          <Progress percent={usagePercent(usage.storage_mb, quota.max_storage_mb)} showInfo={false} />
        </article>
      </section>

      <section className={styles.boundaryNote}>
        <Building2 size={22} />
        <div><strong>租户边界已经生效</strong><p>成员、智能体、工作区、定时任务和经验库都按当前空间隔离。</p></div>
      </section>
    </div>
  );

  const memberPanel = (
    <div className={styles.panel}>
      <div className={styles.sectionHeading}>
        <div><h2>成员与角色</h2><p>只授予完成工作所需的权限；停用成员会立即结束其登录会话。</p></div>
        {canInvite && <Button type="primary" icon={<UserPlus size={16} />} onClick={() => setInviteOpen(true)}>邀请成员</Button>}
      </div>
      {!canReadMembers ? <Empty description="你没有查看成员的权限" /> : (
        <Table
          rowKey="user_id"
          dataSource={members}
          pagination={false}
          columns={[
            { title: "成员", key: "member", render: (_, row) => <div className={styles.person}><span>{row.display_name.slice(0, 1)}</span><div><strong>{row.display_name}</strong><small>{row.username}</small></div></div> },
            { title: "角色", dataIndex: "role", render: (value: TenantRole) => <Tag>{ROLE_LABELS[value]}</Tag> },
            { title: "状态", dataIndex: "status", render: (value: MembershipStatus) => <Tag color={value === "active" ? "green" : "default"}>{value === "active" ? "正常" : "已停用"}</Tag> },
            { title: "加入时间", dataIndex: "created_at", render: formatTime },
            { title: "", key: "action", width: 90, render: (_, row) => canManage && row.user_id !== membership.user_id ? <Button type="link" onClick={() => { setEditMember(row); memberForm.setFieldsValue({ role: row.role, status: row.status }); }}>管理</Button> : null },
          ]}
        />
      )}
      {activeInvites.length > 0 && (
        <div className={styles.invites}>
          <h3>等待加入</h3>
          {activeInvites.map((invite) => <div key={invite.invite_id}><UserPlus size={16} /><span><strong>{invite.username}</strong> · {ROLE_LABELS[invite.role]}</span><span><small>{formatTime(invite.expires_at)} 前有效</small>{canInvite && <Button type="link" danger size="small" loading={busy} onClick={() => void revokeInvite(invite.invite_id)}>撤销</Button>}</span></div>)}
        </div>
      )}
    </div>
  );

  const agentPanel = (
    <div className={styles.panel}>
      <div className={styles.sectionHeading}><div><h2>智能体归属</h2><p>只有当前空间内的成员可以看到和运行这些智能体。</p></div></div>
      <div className={styles.agentGrid}>
        {agents.map((agent) => (
          <article key={agent.agent_id} className={styles.agentCard}>
            <div><Bot size={20} /><Tag color={agent.status === "active" ? "green" : "default"}>{agent.status === "active" ? "可用" : "已停用"}</Tag></div>
            <h3>{agent.agent_id}</h3>
            <p>{agent.access === "tenant" ? "企业空间内共享" : "仅拥有者可用"}</p>
            <small>接入于 {formatTime(agent.created_at)}</small>
          </article>
        ))}
        {!agents.length && <Empty description="还没有接入智能体" />}
      </div>
    </div>
  );

  const auditPanel = (
    <div className={styles.panel}>
      <div className={styles.sectionHeading}><div><h2>安全记录</h2><p>关键变更只追加、不覆盖，便于企业追溯责任和恢复现场。</p></div></div>
      <div className={styles.timeline}>
        {audit.map((item) => (
          <article key={item.event_id}>
            <span><History size={15} /></span>
            <div><strong>{ACTION_LABELS[item.action] || item.action}</strong><p>{item.resource_type} · {item.resource_id}</p></div>
            <time>{formatTime(item.created_at)}</time>
          </article>
        ))}
        {!audit.length && <Empty description="暂无安全记录" />}
      </div>
    </div>
  );

  return (
    <div className={styles.page}>
      <PageHeader parent="设置" current="企业空间" />
      {error && <Alert type="warning" showIcon message="部分信息刷新失败" description={error} closable />}
      <div className={styles.toolbar}>
        <div>
          <Building2 size={18} />
          <Select
            aria-label="切换企业空间"
            value={tenant.slug}
            loading={busy}
            style={{ minWidth: 180 }}
            onChange={(value) => void switchSpace(value)}
            options={spaces.map((space) => ({
              value: space.slug,
              label: `${space.name} · ${ROLE_LABELS[space.role]}`,
            }))}
          />
        </div>
        <div>
          {canCreateSpace && (
            <Button icon={<Plus size={16} />} onClick={() => setCreateOpen(true)}>
              新建企业空间
            </Button>
          )}
          <Tooltip title="刷新"><Button icon={<RefreshCw size={16} />} loading={loading} onClick={() => void load()} /></Tooltip>
        </div>
      </div>
      <Tabs
        className={styles.tabs}
        items={[
          { key: "overview", label: "空间概览", children: overviewPanel },
          { key: "members", label: `成员 ${usage.members}`, children: memberPanel },
          { key: "agents", label: `智能体 ${usage.agents}`, children: agentPanel },
          { key: "audit", label: "安全记录", children: auditPanel },
        ]}
      />

      <Modal title="邀请新成员" open={inviteOpen} onCancel={() => setInviteOpen(false)} footer={null} destroyOnClose>
        <Form form={inviteForm} layout="vertical" onFinish={(values) => void submitInvite(values)} initialValues={{ role: "member" }}>
          <Form.Item name="username" label="登录名" rules={[{ required: true, message: "请输入成员登录名" }]}><Input placeholder="例如：zhangsan" /></Form.Item>
          <Form.Item name="role" label="进入空间后的角色" rules={[{ required: true }]}><Select options={(["admin", "operator", "member", "viewer"] as TenantRole[]).map((value) => ({ value, label: ROLE_LABELS[value] }))} /></Form.Item>
          <Alert className={styles.modalNote} type="info" showIcon message="创建后会显示一次性邀请码，并自动复制。请通过可信渠道发给成员。" />
          <Button block type="primary" htmlType="submit" loading={busy}>创建邀请</Button>
        </Form>
      </Modal>

      <Modal
        title="一次性邀请码"
        open={!!issuedInviteToken}
        onCancel={() => setIssuedInviteToken(null)}
        footer={<Button type="primary" onClick={() => void copyInviteToken()} icon={<Copy size={16} />}>复制邀请码</Button>}
        destroyOnClose
      >
        <Alert className={styles.modalNote} type="warning" showIcon message="关闭后将不再显示这个邀请码，请先通过可信渠道发送给成员。" />
        <Input.TextArea value={issuedInviteToken || ""} readOnly autoSize={{ minRows: 3, maxRows: 6 }} />
      </Modal>

      <Modal title="新建企业空间" open={createOpen} onCancel={() => setCreateOpen(false)} footer={null} destroyOnClose>
        <Form form={createForm} layout="vertical" onFinish={(values) => void submitCreateSpace(values)}>
          <Form.Item name="name" label="企业或团队名称" rules={[{ required: true, message: "请输入企业空间名称" }]}><Input placeholder="例如：上海分公司" /></Form.Item>
          <Form.Item
            name="slug"
            label="空间代号"
            extra="用于登录时区分企业，创建后请保持稳定。"
            rules={[
              { required: true, message: "请输入空间代号" },
              { pattern: /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/, message: "请使用小写字母、数字和短横线" },
            ]}
          ><Input placeholder="例如：shanghai-office" /></Form.Item>
          <Alert className={styles.modalNote} type="info" showIcon message="新空间的数据、成员、智能体和经验库都与当前空间隔离；你将成为所有者。" />
          <Button block type="primary" htmlType="submit" loading={busy}>创建并进入</Button>
        </Form>
      </Modal>

      <Modal title={`管理 ${editMember?.display_name || "成员"}`} open={!!editMember} onCancel={() => setEditMember(null)} footer={null} destroyOnClose>
        <Form form={memberForm} layout="vertical" onFinish={(values) => void submitMember(values)}>
          <Form.Item name="role" label="角色" rules={[{ required: true }]}><Select options={(["admin", "operator", "member", "viewer"] as TenantRole[]).map((value) => ({ value, label: ROLE_LABELS[value] }))} /></Form.Item>
          <Form.Item name="status" label="成员状态" rules={[{ required: true }]}><Select options={[{ value: "active", label: "正常" }, { value: "disabled", label: "停用并结束会话" }]} /></Form.Item>
          <Button block type="primary" htmlType="submit" loading={busy}>保存变更</Button>
        </Form>
      </Modal>
    </div>
  );
}
