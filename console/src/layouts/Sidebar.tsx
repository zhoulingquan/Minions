import {
  Layout,
  Menu,
  Button,
  Modal,
  Input,
  Form,
  Tooltip,
  Badge,
  Popover,
} from "antd";
import { useState, useEffect, useMemo, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAppMessage } from "../hooks/useAppMessage";
import AgentSelector from "../components/AgentSelector";
import {
  SparkChatTabFill,
  SparkExitFullscreenLine,
  SparkSearchUserLine,
  SparkMenuExpandLine,
  SparkMenuFoldLine,
  SparkEmailLine,
  SparkSettingLine,
} from "@agentscope-ai/icons";
import SidebarSessionList from "./SidebarSessionList";
import SidebarSettingsPanel from "./SidebarSettingsPanel";
import { clearAuthToken, setAuthToken } from "../api/config";
import { authApi } from "../api/modules/auth";
import api from "../api";
import {
  syncSessionsGlobal,
  type ExtendedSession,
} from "../stores/sessionListStore";
import { useSidebarModeStore } from "../stores/sidebarModeStore";
import { buildSessionPath, getSessionIdFromPath } from "../utils/sessionRoute";
import sessionApi from "../pages/Chat/sessionApi";
import styles from "./index.module.less";
import { useTheme } from "../contexts/ThemeContext";
import { Building2 } from "lucide-react";
import { useTenantStore } from "../stores/tenantStore";
import type { TenantRole } from "../api/types/tenancy";
import { useMenuItems, useRoutes } from "../plugins/registry/hooks";
import { Slot } from "../plugins/registry/Slot";
import {
  deriveOpenKeys,
  findMenuItem,
  flattenMenu,
  renderIcon,
  routeIdToPath,
  toAntdItems,
} from "./registry/adapter";
import type { FlatMenuEntry } from "./registry/adapter";
import type { MenuItem } from "../plugins/registry/types";
import type { ReactNode } from "react";

// ── Layout ────────────────────────────────────────────────────────────────

const { Sider } = Layout;
const MOBILE_SIDEBAR_QUERY = "(max-width: 768px)";

function isMobileSidebarViewport() {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia(MOBILE_SIDEBAR_QUERY).matches
  );
}
const MSG_BADGE_POLLING_MS = 6000;
const TENANT_ROLE_LABELS: Record<TenantRole, string> = {
  owner: "所有者",
  admin: "管理员",
  operator: "业务运营",
  member: "成员",
  viewer: "只读成员",
};

// ── Simple mode whitelist ─────────────────────────────────────────────────

/** Menu item IDs that remain visible in simple sidebar mode (no groups). */
const SIMPLE_MODE_WHITELIST = new Set([
  "core.msg",
  "core.cron-jobs",
  "core.agent-config",
  "core.models",
]);

/**
 * Flatten a MenuItem tree into a leaf-only list for simple sidebar mode.
 * Groups are eliminated entirely — only whitelisted children survive
 * as top-level items.
 */
function flattenMenuForSimpleMode(items: MenuItem[]): MenuItem[] {
  const result: MenuItem[] = [];
  for (const rawItem of items) {
    const item = rawItem as MenuItem & { __children?: MenuItem[] };
    if (item.__children && item.__children.length > 0) {
      for (const child of item.__children) {
        if (SIMPLE_MODE_WHITELIST.has(child.id)) {
          result.push(child);
        }
      }
    } else if (SIMPLE_MODE_WHITELIST.has(item.id)) {
      result.push(item);
    }
  }
  return result;
}

// ── Types ─────────────────────────────────────────────────────────────────

interface SidebarProps {
  /** Route id of the currently active page (e.g. "core.workspace"). */
  selectedKey: string;
}

// ── Sidebar ───────────────────────────────────────────────────────────────

export default function Sidebar({ selectedKey }: SidebarProps) {
  const navigate = useNavigate();
  const location = useLocation();
    const { message } = useAppMessage();
  const { isDark } = useTheme();
  const currentSessionId = getSessionIdFromPath(location.pathname);
  const chatPath = buildSessionPath("chat", currentSessionId);
  const [authEnabled, setAuthEnabled] = useState(false);
  const [accountModalOpen, setAccountModalOpen] = useState(false);
  const [accountLoading, setAccountLoading] = useState(false);
  const [accountForm] = Form.useForm();
  // Start collapsed on mobile so the first paint does not overlay/obscure
  // the main content on narrow viewports.
  const [collapsed, setCollapsed] = useState(isMobileSidebarViewport);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(isMobileSidebarViewport);
  const [hasMsgUnread, setHasMsgUnread] = useState(false);
  const tenantOverview = useTenantStore((state) => state.overview);
  const refreshTenant = useTenantStore((state) => state.refresh);
  const clearTenant = useTenantStore((state) => state.clear);

  // Sidebar mode: "simple" (only core items) or "full" (everything)
  const { mode: sidebarMode } = useSidebarModeStore();

  // Menu + route snapshots from registry (builtin + plugin registrations merged).
  const rawAgentMenu = useMenuItems("primary.agentScoped");
  const rawSettingsMenu = useMenuItems("primary.settings");
  const routes = useRoutes();

  // Apply simple-mode filtering when enabled
  const agentMenu = useMemo(
    () =>
      sidebarMode === "simple"
        ? flattenMenuForSimpleMode(rawAgentMenu)
        : rawAgentMenu,
    [rawAgentMenu, sidebarMode],
  );
  const settingsMenu = useMemo(
    () =>
      sidebarMode === "simple"
        ? flattenMenuForSimpleMode(rawSettingsMenu)
        : rawSettingsMenu,
    [rawSettingsMenu, sidebarMode],
  );

  // Flat nav entries for simple mode (icon + label + path)
  const simpleFlatNav = useMemo(() => {
    if (sidebarMode !== "simple") return [];
    return [
      ...flattenMenu(agentMenu, routes, 16),
      ...flattenMenu(settingsMenu, routes, 16),
    ];
  }, [agentMenu, settingsMenu, routes, sidebarMode]);

  // ── Effects ──────────────────────────────────────────────────────────────

  useEffect(() => {
    authApi
      .getStatus()
      .then((res) => {
        setAuthEnabled(res.enabled);
        if (res.enabled && res.multitenant) {
          void refreshTenant();
        } else {
          clearTenant();
        }
      })
      .catch(() => {});
  }, [clearTenant, refreshTenant]);

  useEffect(() => {
    if (
      typeof window === "undefined" ||
      typeof window.matchMedia !== "function"
    ) {
      return;
    }

    const mediaQuery = window.matchMedia(MOBILE_SIDEBAR_QUERY);
    const syncMobileSidebar = () => {
      setIsMobile(mediaQuery.matches);
      // Collapse on mobile to avoid covering the main content; expand again
      // when the viewport returns to desktop width.
      setCollapsed(mediaQuery.matches);
    };

    syncMobileSidebar();
    mediaQuery.addEventListener("change", syncMobileSidebar);

    return () => {
      mediaQuery.removeEventListener("change", syncMobileSidebar);
    };
  }, []);
  useEffect(() => {
    const loadUnreadState = async () => {
      try {
        const [msgRes, pushRes] = await Promise.all([
          api.getMsgEvents({
            unread_only: true,
            limit: 1,
          }),
          api.getPushMessages(),
        ]);
        const hasUnreadEvents = (msgRes?.events?.length || 0) > 0;
        const hasPendingApprovals =
          (pushRes?.pending_approvals?.length || 0) > 0;
        setHasMsgUnread(hasUnreadEvents || hasPendingApprovals);
      } catch {
        // Keep previous state when polling fails.
      }
    };
    void loadUnreadState();
    const timer = window.setInterval(() => {
      void loadUnreadState();
    }, MSG_BADGE_POLLING_MS);
    return () => window.clearInterval(timer);
  }, []);

  // ── Pre-fetch sessions on mount ───────────────────────────────────────────
  // On mobile the sidebar starts collapsed so SidebarSessionList is unmounted
  // and never fetches.  When the user expands the sidebar the list mounts fresh
  // but the Zustand store may still be empty (ChatSessionInitializer may not
  // have synced yet).  Proactively fetch sessions into the store so the data
  // is ready the moment the user expands.  Fire on mount regardless of
  // sidebar mode (the default "full" mode also benefits from this).
  // Uses sessionApi.getSessionList() instead of raw api.listChats() to ensure
  // the same data processing pipeline (dedup, realId, generating state) as
  // the desktop ChatSessionDrawer.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const list = await sessionApi.getSessionList();
        if (!cancelled && list.length > 0) {
          syncSessionsGlobal(list as ExtendedSession[]);
        }
      } catch {
        // Best-effort: let SidebarSessionList retry on its own.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // ── Adapter: convert MenuItem trees to antd, with msg badge decoration.

  /** Wrap the msg label with the unread-Badge while keeping all other labels intact. */
  const decorateLabel = (item: MenuItem, label: ReactNode): ReactNode => {
    if (item.id !== "core.msg" || label == null) return label;
    return (
      <Badge dot={hasMsgUnread} color="rgba(255, 157, 77, 1)" offset={[5, 7]}>
        <span>{label}</span>
      </Badge>
    );
  };

  const agentMenuItems = useMemo(
    () => toAntdItems(agentMenu, { collapsed, decorateLabel }),
    // hasMsgUnread closure inside decorateLabel - listed as dep explicitly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [agentMenu, collapsed, hasMsgUnread],
  );

  const settingsMenuItems = useMemo(
    () => toAntdItems(settingsMenu, { collapsed }),
    [settingsMenu, collapsed],
  );

  const openKeys = useMemo(
    () => [...deriveOpenKeys(agentMenu), ...deriveOpenKeys(settingsMenu)],
    [agentMenu, settingsMenu],
  );

  const collapsedNavItems = useMemo(() => {
    // Sticky chat is its own carve-out (lives outside menu data — see builtinMenu.ts).
    const stickyChat: FlatMenuEntry = {
      key: "core.chat",
      icon: <SparkChatTabFill size={18} />,
      path: chatPath,
      label: "聊天",
    };
    // Msg in collapsed mode shows a dot overlay on its icon (kept Sidebar-local
    // for the same reason as decorateLabel: live state isn't menu data).
    const decorateMsgIcon = (icon: ReactNode): ReactNode => (
      <span style={{ position: "relative", display: "inline-flex" }}>
        {icon ?? <SparkEmailLine size={18} />}
        {hasMsgUnread && (
          <span
            style={{
              position: "absolute",
              top: -1,
              right: -3,
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: "rgba(255, 157, 77, 1)",
            }}
          />
        )}
      </span>
    );
    const flat = [
      stickyChat,
      ...flattenMenu(agentMenu, routes, 18),
      ...flattenMenu(settingsMenu, routes, 18),
    ];
    return flat.map((entry) =>
      entry.key === "core.msg"
        ? { ...entry, icon: decorateMsgIcon(entry.icon) }
        : entry,
    );
  }, [agentMenu, settingsMenu, routes, chatPath, hasMsgUnread]);

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleMenuClick = (key: string, allItems: MenuItem[]) => {
    const item = findMenuItem(allItems, key);
    if (item?.href) {
      window.open(item.href, "_blank", "noopener,noreferrer");
      return;
    }
    const path = routeIdToPath(item?.route, routes);
    if (path) navigate(path);
  };

  /**
   * New chat: if we're already on the chat page, dispatch the event so
   * ChatSessionInitializer (which is mounted) creates the session.
   * If we're on another page, navigate to /chat without a session id —
   * the chat page will auto-create a new session on mount.
   */
  const handleNewChat = useCallback(() => {
    const onChatPage = location.pathname.startsWith("/chat");
    if (onChatPage) {
      window.dispatchEvent(new CustomEvent("minions:sidebar-new-chat"));
    } else {
      sessionStorage.setItem("minions_pending_new_chat", "1");
      navigate("/chat");
    }
  }, [location.pathname, navigate]);

  /**
   * Session click: navigate directly without relying on ChatSessionInitializer.
   * Resolve realId (backend UUID) to avoid exposing local timestamp in URL.
   */
  const handleSidebarSessionClick = useCallback(
    (sessionId: string) => {
      const effectiveId = sessionApi.getEffectiveSessionId(sessionId);
      const targetPath = buildSessionPath("chat", effectiveId);
      navigate(targetPath);
    },
    [navigate],
  );

  const handleUpdateProfile = async (values: {
    currentPassword: string;
    newUsername?: string;
    newPassword?: string;
  }) => {
    const trimmedUsername = values.newUsername?.trim() || undefined;
    const trimmedPassword = values.newPassword?.trim() || undefined;

    if (values.newPassword && !trimmedPassword) {
      message.error("密码不能为空白");
      return;
    }

    if (values.newUsername && !trimmedUsername) {
      message.error("用户名不能为空白");
      return;
    }

    if (!trimmedUsername && !trimmedPassword) {
      message.warning("请输入新用户名或新密码");
      return;
    }

    setAccountLoading(true);
    try {
      const session = await authApi.updateProfile(
        values.currentPassword,
        trimmedUsername,
        trimmedPassword,
      );
      setAuthToken(session.token);
      message.success("账户更新成功");
      setAccountModalOpen(false);
      accountForm.resetFields();
      await refreshTenant();
    } catch (err: unknown) {
      const raw = err instanceof Error ? err.message : "";
      let msg = "账户更新失败";
      if (raw.includes("password is incorrect")) {
        msg = "当前密码不正确";
      } else if (raw.includes("Nothing to update")) {
        msg = "请输入新用户名或新密码";
      } else if (raw.includes("cannot be empty")) {
        msg = "请输入新用户名或新密码";
      } else if (raw) {
        msg = raw;
      }
      message.error(msg);
    } finally {
      setAccountLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch {
      // Local logout must still complete if the server is unavailable.
    } finally {
      clearTenant();
      clearAuthToken();
      window.location.href = "/login";
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────

  const siderWidth = collapsed ? (isMobile ? 56 : 72) : 240;
  const isChatActive = selectedKey === "core.chat";
  // `renderIcon` retained for tree-shaking awareness.
  void renderIcon;

  // On mobile, the expanded sidebar shows sessions (like simple mode) instead
  // of the full menu — matching the desktop history panel UX.
  const isSimpleExpanded = (sidebarMode === "simple" || isMobile) && !collapsed;

  return (
    <Sider
      width={siderWidth}
      className={`${styles.sider}${
        collapsed ? ` ${styles.siderCollapsed}` : ""
      }${isDark ? ` ${styles.siderDark}` : ""}${
        isSimpleExpanded ? ` ${styles.siderSimple}` : ""
      }`}
    >
      {collapsed ? (
        <nav className={styles.collapsedNav}>
          {collapsedNavItems.map((item) => {
            const isActive =
              item.key === "core.chat"
                ? isChatActive
                : selectedKey === item.key;
            return (
              <Tooltip
                key={item.key}
                title={item.label}
                placement="right"
                overlayInnerStyle={{
                  background: "rgba(0,0,0,0.75)",
                  color: "#fff",
                }}
              >
                <button
                  className={`${styles.collapsedNavItem} ${
                    isActive ? styles.collapsedNavItemActive : ""
                  }`}
                  onClick={() =>
                    item.href
                      ? window.open(item.href, "_blank", "noopener,noreferrer")
                      : navigate(item.path)
                  }
                >
                  {item.icon}
                </button>
              </Tooltip>
            );
          })}
        </nav>
      ) : isSimpleExpanded ? (
        <>
          {/* Simple mode: flat nav items + session list */}
          <div className={styles.agentScopedSection}>
            <div className={styles.agentSelectorContainer}>
              <AgentSelector collapsed={collapsed} />
            </div>
            {/* Flat nav items (no groups) */}
            <div className={styles.simpleNavItems}>
              {simpleFlatNav.map((entry) => {
                const isMsg = entry.key === "core.msg";
                const isActive = selectedKey === entry.key;
                return (
                  <button
                    key={entry.key}
                    className={`${styles.simpleNavItem} ${
                      isActive ? styles.simpleNavItemActive : ""
                    }`}
                    onClick={() =>
                      entry.href
                        ? window.open(
                            entry.href,
                            "_blank",
                            "noopener,noreferrer",
                          )
                        : navigate(entry.path)
                    }
                  >
                    {isMsg ? (
                      <span
                        style={{
                          position: "relative",
                          display: "inline-flex",
                        }}
                      >
                        {entry.icon ?? <SparkEmailLine size={16} />}
                        {hasMsgUnread && (
                          <span
                            style={{
                              position: "absolute",
                              top: -1,
                              right: -3,
                              width: 6,
                              height: 6,
                              borderRadius: "50%",
                              background: "rgba(255, 157, 77, 1)",
                            }}
                          />
                        )}
                      </span>
                    ) : (
                      entry.icon
                    )}
                    <span>{entry.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Session list — fills remaining space */}
          <SidebarSessionList
            onNewChat={handleNewChat}
            onSessionClick={handleSidebarSessionClick}
          />
        </>
      ) : (
        <>
          {/* Agent-scoped section: selector + Chat + Control + Workspace */}
          <div className={styles.agentScopedSection}>
            <div className={styles.agentSelectorContainer}>
              <AgentSelector collapsed={collapsed} />
              {/* Chat entry — sticky together with agent selector */}
              <button
                className={`${styles.stickyChatButton}${
                  isChatActive ? ` ${styles.stickyChatButtonActive}` : ""
                }`}
                onClick={() => navigate(chatPath)}
              >
                <SparkChatTabFill size={16} />
                <span>{"聊天"}</span>
              </button>
            </div>
            <Slot name="sider.top" kind="fill" />
            <Menu
              mode="inline"
              selectedKeys={[selectedKey]}
              openKeys={openKeys}
              onClick={({ key }) => handleMenuClick(String(key), agentMenu)}
              items={agentMenuItems}
              theme={isDark ? "dark" : "light"}
              className={styles.sideMenu}
            />
          </div>

          {/* Global settings section */}
          <Menu
            mode="inline"
            selectedKeys={[selectedKey]}
            openKeys={openKeys}
            onClick={({ key }) => handleMenuClick(String(key), settingsMenu)}
            items={settingsMenuItems}
            theme={isDark ? "dark" : "light"}
            className={styles.sideMenu}
          />
          <Slot name="sider.bottom" kind="fill" />
        </>
      )}

      {authEnabled && !collapsed && (
        <div className={styles.authActions}>
          {tenantOverview && (
            <button
              type="button"
              className={styles.tenantSummary}
              onClick={() => navigate("/settings/tenancy")}
            >
              <span className={styles.tenantSummaryIcon}>
                <Building2 size={16} />
              </span>
              <span>
                <strong>{tenantOverview.tenant.name}</strong>
                <small>
                  {TENANT_ROLE_LABELS[tenantOverview.membership.role]}
                </small>
              </span>
            </button>
          )}
          <Button
            type="text"
            icon={<SparkSearchUserLine size={16} />}
            onClick={() => {
              accountForm.resetFields();
              setAccountModalOpen(true);
            }}
            block
            className={`${styles.authBtn} ${
              collapsed ? styles.authBtnCollapsed : ""
            }`}
          >
            {!collapsed && "账户管理"}
          </Button>
          <Button
            type="text"
            icon={<SparkExitFullscreenLine size={16} />}
            onClick={() => void handleLogout()}
            block
            className={`${styles.authBtn} ${
              collapsed ? styles.authBtnCollapsed : ""
            }`}
          >
            {!collapsed && "退出登录"}
          </Button>
        </div>
      )}

      <div className={styles.collapseToggleContainer}>
        {!collapsed && (
          <Popover
            open={settingsOpen}
            onOpenChange={setSettingsOpen}
            placement="topRight"
            trigger="click"
            content={
              <SidebarSettingsPanel onClose={() => setSettingsOpen(false)} />
            }
          >
            <Button
              type="text"
              icon={<SparkSettingLine size={18} />}
              className={styles.collapseToggle}
            />
          </Popover>
        )}
        <Button
          type="text"
          icon={
            collapsed ? (
              <SparkMenuExpandLine size={20} />
            ) : (
              <SparkMenuFoldLine size={20} />
            )
          }
          onClick={() => setCollapsed(!collapsed)}
          className={styles.collapseToggle}
        />
      </div>

      <Modal
        open={accountModalOpen}
        onCancel={() => setAccountModalOpen(false)}
        title={"账户管理"}
        footer={null}
        destroyOnHidden
        centered
      >
        <Form
          form={accountForm}
          layout="vertical"
          onFinish={handleUpdateProfile}
        >
          <Form.Item
            name="currentPassword"
            label={"当前密码"}
            rules={[
              { required: true, message: "请输入当前密码" },
            ]}
          >
            <Input.Password />
          </Form.Item>
          <Form.Item name="newUsername" label={"新用户名"}>
            <Input placeholder={"留空则保持不变"} />
          </Form.Item>
          <Form.Item name="newPassword" label={"新密码"}>
            <Input.Password placeholder={"留空则保持不变"} />
          </Form.Item>
          <Form.Item
            name="confirmPassword"
            label={"确认新密码"}
            dependencies={["newPassword"]}
            rules={[
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value && !getFieldValue("newPassword")) {
                    return Promise.resolve();
                  }
                  if (value === getFieldValue("newPassword")) {
                    return Promise.resolve();
                  }
                  return Promise.reject(
                    new Error("两次输入的密码不一致"),
                  );
                },
              }),
            ]}
          >
            <Input.Password
              placeholder={"再次输入新密码"}
            />
          </Form.Item>
          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={accountLoading}
              block
            >
              {"保存更改"}
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </Sider>
  );
}
