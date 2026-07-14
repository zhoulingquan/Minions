import { useState, useCallback } from "react";
import { Button, Empty, Modal, Input, Select } from "@agentscope-ai/design";
import { Tabs } from "antd";
import { Plus } from "lucide-react";
import type { MCPClientInfo } from "../../../api/types";
import { MCPClientCard } from "./components";
import { useMCP } from "./useMCP";
import { PageHeader } from "@/components/PageHeader";
import styles from "./index.module.less";

type MCPTransport = "stdio" | "streamable_http" | "sse";

function normalizeTransport(raw?: unknown): MCPTransport | undefined {
  if (typeof raw !== "string") return undefined;
  const value = raw.trim().toLowerCase();
  switch (value) {
    case "stdio":
      return "stdio";
    case "sse":
      return "sse";
    case "streamablehttp":
    case "streamable_http":
    case "streamable-http":
    case "http":
      return "streamable_http";
    default:
      return undefined;
  }
}

function normalizeClientData(key: string, rawData: Record<string, unknown>) {
  const transport =
    normalizeTransport(
      (rawData.transport as string) ?? (rawData.type as string),
    ) ??
    (rawData.url || rawData.baseUrl || !rawData.command
      ? "streamable_http"
      : "stdio");

  const command =
    transport === "stdio" ? ((rawData.command ?? "") as string) : "";

  return {
    name: (rawData.name as string) || key,
    description: (rawData.description as string) || "",
    enabled:
      (rawData.enabled as boolean) ?? (rawData.isActive as boolean) ?? true,
    transport,
    url: (rawData.url || rawData.baseUrl || "") as string,
    headers: (rawData.headers as Record<string, string>) || {},
    command,
    args: Array.isArray(rawData.args) ? (rawData.args as string[]) : [],
    env: (rawData.env as Record<string, string>) || {},
    cwd: (rawData.cwd || "") as string,
  };
}

// ---------------------------------------------------------------------------
// Form-mode state defaults
// ---------------------------------------------------------------------------

const defaultForm = {
  key: "",
  name: "",
  description: "",
  transport: "streamable_http" as MCPTransport,
  url: "",
  command: "",
  args: "",
  env: "",
  cwd: "",
};

function MCPPage() {
    const {
    clients,
    loading,
    toggleEnabled,
    deleteClient,
    createClient,
    updateClient,
    updatePolicy,
    refreshClients,
  } = useMCP();
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<"json" | "form">("json");

  // JSON-import state
  const [newClientJson, setNewClientJson] = useState(`{
  "mcpServers": {
    "example-client": {
      "command": "npx",
      "args": ["-y", "@example/mcp-server"],
      "env": {
        "API_KEY": "<YOUR_API_KEY>"
      }
    }
  }
}`);

  // Form state
  const [form, setForm] = useState({ ...defaultForm });

  const setField = useCallback(
    <K extends keyof typeof defaultForm>(k: K, v: (typeof defaultForm)[K]) => {
      setForm((prev) => ({ ...prev, [k]: v }));
    },
    [],
  );

  const resetModal = useCallback(() => {
    setNewClientJson(`{
  "mcpServers": {
    "example-client": {
      "command": "npx",
      "args": ["-y", "@example/mcp-server"],
      "env": {
        "API_KEY": "<YOUR_API_KEY>"
      }
    }
  }
}`);
    setForm({ ...defaultForm });
    setActiveTab("json");
  }, []);

  const handleToggleEnabled = async (
    client: MCPClientInfo,
    e?: React.MouseEvent,
  ) => {
    e?.stopPropagation();
    await toggleEnabled(client);
  };

  const handleDelete = async (client: MCPClientInfo, e?: React.MouseEvent) => {
    e?.stopPropagation();
    await deleteClient(client);
  };

  // ---------- JSON import ----------
  const handleCreateFromJson = async () => {
    try {
      const parsed = JSON.parse(newClientJson) as Record<string, unknown>;
      const clientsToCreate: Array<{
        key: string;
        data: ReturnType<typeof normalizeClientData>;
      }> = [];

      if (parsed.mcpServers) {
        Object.entries(parsed.mcpServers as Record<string, unknown>).forEach(
          ([key, data]) => {
            clientsToCreate.push({
              key,
              data: normalizeClientData(key, data as Record<string, unknown>),
            });
          },
        );
      } else if (
        parsed.key &&
        (parsed.command || parsed.url || parsed.baseUrl)
      ) {
        const { key, ...clientData } = parsed as Record<string, unknown>;
        clientsToCreate.push({
          key: key as string,
          data: normalizeClientData(key as string, clientData),
        });
      } else {
        Object.entries(parsed).forEach(([key, data]) => {
          if (
            typeof data === "object" &&
            data !== null &&
            ((data as Record<string, unknown>).command ||
              (data as Record<string, unknown>).url ||
              (data as Record<string, unknown>).baseUrl)
          ) {
            clientsToCreate.push({
              key,
              data: normalizeClientData(key, data as Record<string, unknown>),
            });
          }
        });
      }

      let allSuccess = true;
      for (const { key, data } of clientsToCreate) {
        const success = await createClient(key, data);
        if (!success) allSuccess = false;
      }

      if (allSuccess) {
        setCreateModalOpen(false);
        resetModal();
      }
    } catch {
      alert("Invalid JSON format");
    }
  };

  // ---------- Form create ----------
  const handleCreateFromForm = async () => {
    const key = form.key.trim();
    const name = form.name.trim();
    if (!key) {
      alert("请填写客户端标识符");
      return;
    }
    if (!name) {
      alert("请填写显示名称");
      return;
    }

    const isHttp =
      form.transport === "streamable_http" || form.transport === "sse";

    if (isHttp && !form.url.trim()) {
      alert("远程 MCP 服务器需要填写 URL");
      return;
    }
    if (form.transport === "stdio" && !form.command.trim()) {
      alert("Stdio 模式需要填写启动命令");
      return;
    }

    // Parse args: split on newlines, commas, or spaces
    const args = form.args
      .split(/[\n, ]+/)
      .map((s) => s.trim())
      .filter(Boolean);

    // Parse env (KEY=VALUE lines)
    const env: Record<string, string> = {};
    form.env
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean)
      .forEach((line) => {
        const idx = line.indexOf("=");
        if (idx > 0) {
          env[line.slice(0, idx).trim()] = line.slice(idx + 1).trim();
        }
      });

    const clientData = {
      name,
      description: form.description,
      transport: form.transport,
      url: isHttp ? form.url.trim() : "",
      command: form.transport === "stdio" ? form.command.trim() : "",
      args,
      env,
      cwd: form.cwd.trim(),
    };

    const success = await createClient(key, clientData);
    if (success) {
      setCreateModalOpen(false);
      resetModal();
    }
  };

  const isHttpTransport =
    form.transport === "streamable_http" || form.transport === "sse";

  return (
    <div className={styles.mcpPage}>
      <PageHeader
        items={[{ title: "工作区" }, { title: "MCP 客户端" }]}
        extra={
          <Button
            type="primary"
            icon={<Plus size={14} />}
            onClick={() => setCreateModalOpen(true)}
          >
            {"创建客户端"}
          </Button>
        }
      />

      {loading ? (
        <div className={styles.loading}>
          <p>{"加载中..."}</p>
        </div>
      ) : clients.length === 0 ? (
        <div className={styles.emptyState}>
          <Empty description={"暂无配置的 MCP 客户端"} />
        </div>
      ) : (
        <div className={styles.mcpGrid}>
          {clients.map((client) => (
            <MCPClientCard
              key={client.key}
              client={client}
              onToggle={handleToggleEnabled}
              onDelete={handleDelete}
              onUpdate={updateClient}
              onUpdatePolicy={updatePolicy}
              onRefresh={refreshClients}
            />
          ))}
        </div>
      )}

      <Modal
        title={"创建客户端"}
        open={createModalOpen}
        onCancel={() => {
          setCreateModalOpen(false);
          resetModal();
        }}
        footer={
          <div className={styles.modalFooter}>
            <Button
              onClick={() => {
                setCreateModalOpen(false);
                resetModal();
              }}
              style={{ marginRight: 8 }}
            >
              {"取消"}
            </Button>
            <Button
              type="primary"
              onClick={
                activeTab === "json"
                  ? handleCreateFromJson
                  : handleCreateFromForm
              }
            >
              {"创建"}
            </Button>
          </div>
        }
        width={800}
      >
        <Tabs
          activeKey={activeTab}
          onChange={(k) => setActiveTab(k as "json" | "form")}
          items={[
            {
              key: "json",
              label: "JSON 导入",
              children: (
                <div>
                  <div className={styles.importHint}>
                    <p className={styles.importHintTitle}>
                      {"支持的格式"}:
                    </p>
                    <ul className={styles.importHintList}>
                      <li>
                        {"标准（mcpServers 包裹）"}:{" "}
                        <code>{`{ "mcpServers": { "key": {...} } }`}</code>
                      </li>
                      <li>
                        {"直连（键 → 配置对象）"}:{" "}
                        <code>{`{ "key": {...} }`}</code>
                      </li>
                      <li>
                        {"单客户端（平铺字段）"}:{" "}
                        <code>{`{ "key": "...", "name": "...", "command": "..." }`}</code>
                      </li>
                    </ul>
                  </div>
                  <Input.TextArea
                    value={newClientJson}
                    onChange={(e) => setNewClientJson(e.target.value)}
                    autoSize={{ minRows: 15, maxRows: 25 }}
                    className={styles.jsonTextArea}
                  />
                </div>
              ),
            },
            {
              key: "form",
              label: "表单模式",
              children: (
                <div
                  style={{ display: "flex", flexDirection: "column", gap: 10 }}
                >
                  {/* Key + Name */}
                  <div style={rowStyle}>
                    <div style={fieldStyle}>
                      <label style={labelStyle}>
                        {"客户端标识符"}
                        <span style={{ color: "#c0392b" }}> *</span>
                      </label>
                      <Input
                        placeholder={"my-mcp-server"}
                        value={form.key}
                        onChange={(e) => setField("key", e.target.value)}
                      />
                    </div>
                    <div style={fieldStyle}>
                      <label style={labelStyle}>
                        {"显示名称"}
                        <span style={{ color: "#c0392b" }}> *</span>
                      </label>
                      <Input
                        placeholder={"My MCP Server"}
                        value={form.name}
                        onChange={(e) => setField("name", e.target.value)}
                      />
                    </div>
                  </div>

                  {/* Transport */}
                  <div>
                    <label style={labelStyle}>{"传输方式"}</label>
                    <Select
                      value={form.transport}
                      onChange={(v) => setField("transport", v as MCPTransport)}
                      style={{ width: "100%" }}
                      options={[
                        {
                          label: "Streamable HTTP",
                          value: "streamable_http",
                        },
                        { label: "SSE", value: "sse" },
                        { label: "Stdio", value: "stdio" },
                      ]}
                    />
                  </div>

                  {/* URL (HTTP/SSE) or Command (stdio) */}
                  {isHttpTransport ? (
                    <div>
                      <label style={labelStyle}>
                        {"服务器 URL"}
                        <span style={{ color: "#c0392b" }}> *</span>
                      </label>
                      <Input
                        placeholder="https://mcp.example.com/mcp"
                        value={form.url}
                        onChange={(e) => setField("url", e.target.value)}
                      />
                    </div>
                  ) : (
                    <>
                      <div>
                        <label style={labelStyle}>
                          {"启动命令"}
                          <span style={{ color: "#c0392b" }}> *</span>
                        </label>
                        <Input
                          placeholder="npx"
                          value={form.command}
                          onChange={(e) => setField("command", e.target.value)}
                        />
                      </div>
                      <div>
                        <label style={labelStyle}>{"命令参数（空格或换行分隔）"}</label>
                        <Input
                          placeholder="-y @example/mcp-server"
                          value={form.args}
                          onChange={(e) => setField("args", e.target.value)}
                        />
                      </div>
                    </>
                  )}

                  {/* Description */}
                  <div>
                    <label style={labelStyle}>
                      {"描述"}
                    </label>
                    <Input
                      placeholder={"可选描述"}
                      value={form.description}
                      onChange={(e) => setField("description", e.target.value)}
                    />
                  </div>

                  {/* Env (only for stdio) */}
                  {form.transport === "stdio" && (
                    <div>
                      <label style={labelStyle}>{"环境变量"}</label>
                      <Input.TextArea
                        placeholder={"KEY=VALUE（每行一个）"}
                        value={form.env}
                        onChange={(e) => setField("env", e.target.value)}
                        autoSize={{ minRows: 2, maxRows: 5 }}
                      />
                    </div>
                  )}
                </div>
              ),
            },
          ]}
        />
      </Modal>
    </div>
  );
}

const rowStyle: React.CSSProperties = {
  display: "flex",
  gap: 12,
};

const fieldStyle: React.CSSProperties = {
  flex: 1,
  display: "flex",
  flexDirection: "column",
  gap: 4,
};

const labelStyle: React.CSSProperties = {
  fontSize: 12,
  color: "#555",
  fontWeight: 500,
};

export default MCPPage;
