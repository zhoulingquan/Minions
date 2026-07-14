import {
  useState,
  useEffect,
  useMemo,
  useCallback,
  useDeferredValue,
} from "react";
import {
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Slider,
  Switch,
  Tag,
  Tooltip,
} from "@agentscope-ai/design";
import { AutoComplete, Segmented } from "antd";
import {
  DeleteOutlined,
  PlusOutlined,
  ApiOutlined,
  EyeOutlined,
  SettingOutlined,
  DownOutlined,
  SearchOutlined,
  ExperimentOutlined,
  AppstoreOutlined,
  VideoCameraOutlined,
  FileTextOutlined,
  QuestionCircleOutlined,
  DatabaseOutlined,
  UserOutlined,
  GiftOutlined,
} from "@ant-design/icons";
import type {
  ProviderInfo,
  SeriesResponse,
  ModelInfo,
  ExtendedModelInfo,
} from "../../../../../api/types";

import api from "../../../../../api";
import { useTheme } from "../../../../../contexts/ThemeContext";
import { useAppMessage } from "../../../../../hooks/useAppMessage";
import { JsonConfigEditor } from "./JsonConfigEditor.tsx";
import {
  getLocalizedTestConnectionMessage,
  getTestConnectionFailureDetail,
} from "./testConnectionMessage";
import { OpenRouterFilterSection } from "./OpenRouterFilterSection";
import styles from "../../index.module.less";

function ModelConfigEditor({
  providerId,
  model,
  onSaved,
  onProviderUpdated,
  onClose,
  isDark,
  thinkingParamStyle,
  reasoningEffortOptions,
  thinkingBudgetRange = [1, 81920],
}: {
  providerId: string;
  model: ModelInfo;
  onSaved: () => void | Promise<void>;
  onProviderUpdated?: (provider: ProviderInfo) => void;
  onClose: () => void;
  isDark: boolean;
  thinkingParamStyle?: "budget" | "effort" | null;
  reasoningEffortOptions?: string[];
  thinkingBudgetRange?: [number, number];
}) {
    const { message } = useAppMessage();
  const [saving, setSaving] = useState(false);

  const [maxTokens, setMaxTokens] = useState<number | null>(
    model.max_tokens ?? 8192,
  );
  const [maxInputLength, setMaxInputLength] = useState<number | null>(
    model.max_input_length ?? 131072,
  );
  const [preserveThinking, setPreserveThinking] = useState<boolean>(
    model.preserve_thinking ?? true,
  );
  const [thinkingEnabled, setThinkingEnabled] = useState<boolean | null>(
    model.thinking_enabled ?? null,
  );
  const [thinkingBudget, setThinkingBudget] = useState<number | null>(
    model.thinking_budget ?? null,
  );
  const [reasoningEffort, setReasoningEffort] = useState<string | null>(
    model.reasoning_effort ?? null,
  );

  const initialText = useMemo(
    () =>
      model.generate_kwargs && Object.keys(model.generate_kwargs).length > 0
        ? JSON.stringify(model.generate_kwargs, null, 2)
        : "",
    [model.generate_kwargs],
  );

  const [text, setText] = useState(initialText);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    setText(initialText);
    setMaxTokens(model.max_tokens ?? 8192);
    setMaxInputLength(model.max_input_length ?? 131072);
    setPreserveThinking(model.preserve_thinking ?? true);
    setThinkingEnabled(model.thinking_enabled ?? null);
    setThinkingBudget(model.thinking_budget ?? null);
    setReasoningEffort(model.reasoning_effort ?? null);
    setDirty(false);
  }, [
    initialText,
    model.max_tokens,
    model.max_input_length,
    model.preserve_thinking,
    model.thinking_enabled,
    model.thinking_budget,
    model.reasoning_effort,
  ]);

  const effectiveMaxTokens = maxTokens ?? 8192;
  const effectiveMaxInputLength = maxInputLength ?? 131072;

  const handleChange = useCallback((val: string) => {
    setText(val);
    setDirty(true);
  }, []);

  const handleMaxTokensChange = useCallback((val: number | null) => {
    setMaxTokens(val);
    setDirty(true);
  }, []);

  const handleMaxInputLengthChange = useCallback((val: number | null) => {
    setMaxInputLength(val);
    setDirty(true);
  }, []);

  const handleSave = async () => {
    const trimmed = text.trim();
    let parsed: Record<string, unknown> = {};
    if (trimmed) {
      try {
        const obj = JSON.parse(trimmed);
        if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
          message.error("生成参数配置必须是 JSON 对象");
          return;
        }
        parsed = obj;
      } catch {
        message.error("请输入有效的 JSON");
        return;
      }
    }

    setSaving(true);
    try {
      const updated = await api.configureModel(providerId, model.id, {
        max_tokens: effectiveMaxTokens,
        max_input_length: effectiveMaxInputLength,
        generate_kwargs: parsed,
        preserve_thinking: preserveThinking,
        thinking_enabled: thinkingEnabled,
        thinking_budget: thinkingBudget,
        reasoning_effort: reasoningEffort,
      });
      message.success(`模型 ${model.name} 的配置已保存`);
      setDirty(false);
      onProviderUpdated?.(updated);
      await onSaved();
      onClose();
    } catch (error) {
      const errMsg =
        error instanceof Error
          ? error.message
          : "保存模型配置失败";
      message.error(errMsg);
    } finally {
      setSaving(false);
    }
  };

  const labelStyle: React.CSSProperties = {
    fontSize: 13,
    color: isDark ? "rgba(255,255,255,0.85)" : "#333",
    marginBottom: 4,
  };

  return (
    <div style={{ padding: "8px 0 4px" }}>
      <div style={{ display: "flex", gap: 16, marginBottom: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={labelStyle}>
            {"最大输出 Tokens"}
          </div>
          <InputNumber
            style={{ width: "100%" }}
            min={1}
            step={1024}
            value={maxTokens}
            placeholder="8192"
            onChange={handleMaxTokensChange}
          />
          <div
            style={{
              fontSize: 11,
              color: isDark ? "rgba(255,255,255,0.35)" : "#999",
              marginTop: 2,
            }}
          >
            {"每次响应的最大输出 token 数"}
          </div>
        </div>
        <div style={{ flex: 1 }}>
          <div style={labelStyle}>
            {"最大上下文长度"}
          </div>
          <InputNumber
            style={{ width: "100%" }}
            min={1000}
            step={1024}
            value={maxInputLength}
            placeholder="131072"
            onChange={handleMaxInputLengthChange}
          />
          <div
            style={{
              fontSize: 11,
              color: isDark ? "rgba(255,255,255,0.35)" : "#999",
              marginTop: 2,
            }}
          >
            {"模型上下文窗口大小，控制上下文压缩阈值（≥1000）"}
          </div>
        </div>
      </div>
      {/* Enable Thinking (only for providers that support thinking config) */}
      {thinkingParamStyle && (
        <>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 8,
              padding: "6px 0",
            }}
          >
            <div>
              <span
                style={{
                  fontSize: 13,
                  color: isDark ? "rgba(255,255,255,0.85)" : "#333",
                }}
              >
                {"启用思考"}
              </span>
              <div
                style={{
                  fontSize: 11,
                  color: isDark ? "rgba(255,255,255,0.35)" : "#999",
                  marginTop: 2,
                }}
              >
                {"开启以启用模型思考/推理，关闭以禁用思考。"}
              </div>
            </div>
            <Switch
              checked={thinkingEnabled === true}
              onChange={(checked) => {
                setThinkingEnabled(checked);
                setDirty(true);
              }}
            />
          </div>

          {thinkingEnabled === true && (
            <div style={{ marginBottom: 12 }}>
              {thinkingParamStyle === "budget" ? (
                <div>
                  <div
                    style={{
                      ...labelStyle,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <span>{"思考预算"}</span>
                    <a
                      style={{ fontSize: 11, cursor: "pointer" }}
                      onClick={() => {
                        setThinkingBudget(
                          thinkingBudget === null
                            ? thinkingBudgetRange[0]
                            : null,
                        );
                        setDirty(true);
                      }}
                    >
                      {thinkingBudget === null
                        ? "手动设置"
                        : "自动"}
                    </a>
                  </div>
                  {thinkingBudget !== null ? (
                    <div
                      style={{ display: "flex", alignItems: "center", gap: 12 }}
                    >
                      <div style={{ flex: 1 }}>
                        <Slider
                          min={thinkingBudgetRange[0]}
                          max={thinkingBudgetRange[1]}
                          step={1024}
                          value={thinkingBudget}
                          onChange={(val: number) => {
                            setThinkingBudget(val);
                            setDirty(true);
                          }}
                        />
                      </div>
                      <InputNumber
                        style={{ width: 100 }}
                        min={thinkingBudgetRange[0]}
                        max={thinkingBudgetRange[1]}
                        step={1024}
                        value={thinkingBudget}
                        onChange={(val) => {
                          setThinkingBudget(val);
                          setDirty(true);
                        }}
                      />
                    </div>
                  ) : (
                    <div
                      style={{
                        fontSize: 11,
                        color: isDark ? "rgba(255,255,255,0.35)" : "#999",
                        marginTop: 2,
                      }}
                    >
                      {"使用模型默认思考预算"}
                    </div>
                  )}
                </div>
              ) : (
                <div>
                  <div style={labelStyle}>
                    {"推理深度"}
                  </div>
                  <Segmented
                    block
                    value={reasoningEffort ?? "__auto__"}
                    onChange={(val) => {
                      const v = val as string;
                      setReasoningEffort(v === "__auto__" ? null : v);
                      setDirty(true);
                    }}
                    options={[
                      { label: "自动", value: "__auto__" },
                      ...(
                        reasoningEffortOptions ?? [
                          "none",
                          "minimal",
                          "low",
                          "medium",
                          "high",
                          "xhigh",
                        ]
                      ).map((v) => ({
                        label: v.charAt(0).toUpperCase() + v.slice(1),
                        value: v,
                      })),
                    ]}
                  />
                </div>
              )}
            </div>
          )}
        </>
      )}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 8,
          padding: "6px 0",
        }}
      >
        <div>
          <span
            style={{
              fontSize: 13,
              color: isDark ? "rgba(255,255,255,0.85)" : "#333",
            }}
          >
            {"保留推理内容"}
          </span>
          <div
            style={{
              fontSize: 11,
              color: isDark ? "rgba(255,255,255,0.35)" : "#999",
              marginTop: 2,
            }}
          >
            {"将推理内容（thinking contents）回传至后续对话轮次"}
          </div>
        </div>
        <Switch
          checked={preserveThinking}
          onChange={(checked) => {
            setPreserveThinking(checked);
            setDirty(true);
          }}
        />
      </div>

      <div
        style={{
          fontSize: 12,
          color: isDark ? "rgba(255,255,255,0.45)" : "#888",
          marginBottom: 4,
        }}
      >
        {"使用 JSON 格式表示的该模型专属生成参数配置项，会被展开传入到生成请求中。优先级高于提供商级别的进阶配置。"}
      </div>
      <JsonConfigEditor
        value={text}
        onChange={handleChange}
        placeholder={`Example:\n{\n  "extra_body": {\n    "enable_thinking": false\n  }\n}`}
      />
      <div
        style={{
          display: "flex",
          justifyContent: "flex-end",
          marginTop: 8,
          gap: 8,
        }}
      >
        <Button
          type="primary"
          size="small"
          loading={saving}
          disabled={!dirty}
          onClick={handleSave}
        >
          {"保存"}
        </Button>
      </div>
    </div>
  );
}

const tagColors = (isDark: boolean) => ({
  multimodal: {
    backgroundColor: isDark ? "rgba(24,144,255,0.15)" : "#e6f7ff",
    color: "#1890ff",
    borderColor: isDark ? "rgba(24,144,255,0.3)" : "#91d5ff",
  },
  vision: {
    backgroundColor: isDark ? "rgba(19,194,194,0.15)" : "#e6fffb",
    color: "#13c2c2",
    borderColor: isDark ? "rgba(19,194,194,0.3)" : "#87e8de",
  },
  video: {
    backgroundColor: isDark ? "rgba(114,46,211,0.15)" : "#f9f0ff",
    color: "#722ed1",
    borderColor: isDark ? "rgba(114,46,211,0.3)" : "#d3adf7",
  },
  text: {
    backgroundColor: isDark ? "rgba(255,255,255,0.1)" : "#f5f5f5",
    color: isDark ? "rgba(255,255,255,0.65)" : "#595959",
    borderColor: isDark ? "rgba(255,255,255,0.15)" : "#d9d9d9",
  },
  notProbed: {
    backgroundColor: isDark ? "rgba(255,255,255,0.1)" : "#f5f5f5",
    color: isDark ? "rgba(255,255,255,0.65)" : "#8c8c8c",
    borderColor: isDark ? "rgba(255,255,255,0.15)" : "#d9d9d9",
  },
  builtin: {
    backgroundColor: isDark ? "rgba(82,196,26,0.15)" : "#f6ffed",
    color: "#52c41a",
    borderColor: isDark ? "rgba(82,196,26,0.3)" : "#b7eb8f",
  },
  free: {
    backgroundColor: isDark ? "rgba(82,196,26,0.15)" : "#f6ffed",
    color: "#52c41a",
    borderColor: isDark ? "rgba(82,196,26,0.3)" : "#b7eb8f",
  },
  userAdded: {
    backgroundColor: isDark ? "rgba(24,144,255,0.15)" : "#e6f7ff",
    color: "#1890ff",
    borderColor: isDark ? "rgba(24,144,255,0.3)" : "#91d5ff",
  },
});

interface RemoteModelManageModalProps {
  provider: ProviderInfo;
  open: boolean;
  onClose: () => void;
  onSaved: () => void | Promise<void>;
  onProviderUpdated?: (provider: ProviderInfo) => void;
}

function CapabilityTags({
  model,
  isDark,
}: {
  model: ModelInfo;
  isDark: boolean;
}) {
    const c = tagColors(isDark);
  if (model.supports_image && model.supports_video) {
    return (
      <Tag style={{ fontSize: 11, marginRight: 4, ...c.multimodal }}>
        <AppstoreOutlined style={{ fontSize: 10, marginRight: 3 }} />
        {"多模态"}
      </Tag>
    );
  }
  if (model.supports_image) {
    return (
      <Tag style={{ fontSize: 11, marginRight: 4, ...c.vision }}>
        <EyeOutlined style={{ fontSize: 10, marginRight: 3 }} />
        {"视觉"}
      </Tag>
    );
  }
  if (model.supports_video) {
    return (
      <Tag style={{ fontSize: 11, marginRight: 4, ...c.video }}>
        <VideoCameraOutlined style={{ fontSize: 10, marginRight: 3 }} />
        {"视频"}
      </Tag>
    );
  }
  if (model.supports_multimodal === false) {
    return (
      <Tag style={{ fontSize: 11, marginRight: 4, ...c.text }}>
        <FileTextOutlined style={{ fontSize: 10, marginRight: 3 }} />
        {"文本"}
      </Tag>
    );
  }
  return (
    <Tag style={{ fontSize: 11, marginRight: 4, ...c.notProbed }}>
      <QuestionCircleOutlined style={{ fontSize: 10, marginRight: 3 }} />
      {"未检测"}
    </Tag>
  );
}

export function RemoteModelManageModal({
  provider,
  open,
  onClose,
  onSaved,
  onProviderUpdated,
}: RemoteModelManageModalProps) {
    const { isDark } = useTheme();
  const darkBtnStyle = isDark ? { color: "rgba(255,255,255,0.65)" } : undefined;
  const { message } = useAppMessage();
  const supportsAutoDiscover = provider.support_model_discovery;
  const isOpenRouter = provider.id === "openrouter";
  const [adding, setAdding] = useState(false);
  const [saving, setSaving] = useState(false);
  const [discoveringModels, setDiscoveringModels] = useState(false);
  const [testingModelId, setTestingModelId] = useState<string | null>(null);
  const [probingModelId, setProbingModelId] = useState<string | null>(null);
  const [configOpenModelId, setConfigOpenModelId] = useState<string | null>(
    null,
  );
  const [modelSearchQuery, setModelSearchQuery] = useState("");
  const [form] = Form.useForm();
  const [showFilters, setShowFilters] = useState(false);
  const [availableSeries, setAvailableSeries] = useState<string[]>([]);
  const [discoveredModels, setDiscoveredModels] = useState<ExtendedModelInfo[]>(
    [],
  );
  const [selectedSeries, setSelectedSeries] = useState<string[]>([]);
  const [selectedInputModalities, setSelectedInputModalities] = useState<
    string[]
  >([]);
  const [showFreeOnly, setShowFreeOnly] = useState(false);
  const [loadingFilters, setLoadingFilters] = useState(false);

  const [loadingDiscoveredModels, setLoadingDiscoveredModels] = useState(false);
  const PAGE_SIZE = 30;
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  // For custom providers ALL models are deletable.
  // For built-in providers only extra_models are deletable.
  const extraModelIds = new Set((provider.extra_models || []).map((m) => m.id));

  const doAddModel = async (id: string, name: string) => {
    await api.addModel(provider.id, { id, name });
    message.success(`模型 "${name}" 已添加`);
    form.resetFields();
    setAdding(false);
    onSaved();
  };

  const handleAddModel = async () => {
    try {
      const values = await form.validateFields();
      const id = values.id.trim();
      const name = values.name?.trim() || id;
      const modelAlreadyExists = [
        ...(provider.models ?? []),
        ...(provider.extra_models ?? []),
      ].some((model) => model.id.trim() === id);

      if (modelAlreadyExists) {
        message.warning(`模型 ID "${id}" 已存在`);
        return;
      }

      // Step 1: Test the model connection first
      setSaving(true);
      const testResult = await api.testModelConnection(provider.id, {
        model_id: id,
      });

      if (!testResult.success) {
        // Test failed – ask user whether to proceed anyway
        setSaving(false);
        const failureDetail =
          getTestConnectionFailureDetail(testResult.message) ||
          "模型验证失败，请检查模型ID是否正确";
        Modal.confirm({
          title: "连接测试失败",
          content: `模型连接测试失败：${failureDetail}。是否仍要添加此模型？`,
          okText: "添加模型",
          cancelText: "取消",
          onOk: async () => {
            setSaving(true);
            try {
              await doAddModel(id, name);
            } catch (error) {
              const errMsg =
                error instanceof Error
                  ? error.message
                  : "添加模型失败";
              message.error(errMsg);
            } finally {
              setSaving(false);
            }
          },
        });
        return;
      }

      // Step 2: If test passed, add the model
      await doAddModel(id, name);
    } catch (error) {
      if (error && typeof error === "object" && "errorFields" in error) return;
      const errMsg =
        error instanceof Error ? error.message : "添加模型失败";
      message.error(errMsg);
    } finally {
      setSaving(false);
    }
  };

  const handleTestModel = async (modelId: string) => {
    setTestingModelId(modelId);
    try {
      const result = await api.testModelConnection(provider.id, {
        model_id: modelId,
      });
      if (result.success) {
        message.success(getLocalizedTestConnectionMessage(result));
      } else {
        message.warning(getLocalizedTestConnectionMessage(result));
      }
    } catch (error) {
      const errMsg =
        error instanceof Error
          ? error.message
          : "测试连接时发生错误";
      message.error(errMsg);
    } finally {
      setTestingModelId(null);
    }
  };

  const handleProbeMultimodal = async (modelId: string) => {
    setProbingModelId(modelId);
    try {
      const result = await api.probeMultimodal(provider.id, modelId);
      const parts: string[] = [];
      if (result.supports_image) parts.push("图片");

      if (result.supports_video) parts.push("视频");

      if (parts.length > 0) {
        message.success(
          `支持: ${parts.join(", ")}`,
        );
      } else {
        message.info("该模型不支持多模态输入");
      }
      await onSaved();
    } catch (error) {
      const errMsg =
        error instanceof Error ? error.message : "探测失败";

      message.error(errMsg);
    } finally {
      setProbingModelId(null);
    }
  };

  const handleRemoveModel = (modelId: string, modelName: string) => {
    Modal.confirm({
      title: "移除",
      content: `确定从 ${provider.name} 中移除模型 "${modelName}"？`,
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        try {
          await api.removeModel(provider.id, modelId);
          message.success(`模型 "${modelName}" 已移除`);
          await onSaved();
        } catch (error) {
          const errMsg =
            error instanceof Error
              ? error.message
              : "移除模型失败";
          message.error(errMsg);
        }
      },
    });
  };

  const handleClose = () => {
    setAdding(false);
    setConfigOpenModelId(null);
    setModelSearchQuery("");
    setVisibleCount(PAGE_SIZE);
    form.resetFields();
    onClose();
  };

  // Load available series for OpenRouter
  useEffect(() => {
    if (isOpenRouter) {
      api
        .getOpenRouterSeries()
        .then((res: SeriesResponse) => {
          const series = res.series || [];
          setAvailableSeries(series);
          setSelectedSeries((prev) =>
            prev.length === 0
              ? series
              : prev.filter((item) => series.includes(item)),
          );
        })
        .catch(() => {
          setAvailableSeries([]);
          setSelectedSeries([]);
        });
    }
  }, [isOpenRouter]);

  // Fetch models with current filters
  const handleFetchModels = async () => {
    if (!isOpenRouter) return;

    setLoadingFilters(true);
    try {
      const filterBody: Record<string, unknown> = {};
      const hasPartialProviderSelection =
        selectedSeries.length > 0 &&
        selectedSeries.length < availableSeries.length;
      if (hasPartialProviderSelection) {
        filterBody.providers = selectedSeries;
      }
      if (selectedInputModalities.length > 0) {
        filterBody.input_modalities = selectedInputModalities;
      }
      if (showFreeOnly) {
        filterBody.is_free = true;
      }

      const result = await api.filterOpenRouterModels(filterBody);
      if (result.success) {
        setDiscoveredModels(result.models || []);
        message.success(
          `已加载过滤模型：${result.total_count}`,
        );
      } else {
        message.error("过滤模型失败");
      }
    } catch {
      message.error("过滤模型失败");
    } finally {
      setLoadingFilters(false);
    }
  };

  const handleAddFilteredModel = async (model: ExtendedModelInfo) => {
    setSaving(true);
    try {
      await api.addModel(provider.id, {
        id: model.id,
        name: model.name,
        is_free: model.is_free,
        supports_multimodal: model.supports_multimodal,
        supports_image: model.supports_image,
        supports_video: model.supports_video,
        probe_source: model.probe_source,
      });
      message.success(`模型 "${model.name}" 已添加`);
      await onSaved();
      setDiscoveredModels((prev) => prev.filter((m) => m.id !== model.id));
    } catch {
      message.error("添加模型失败");
    } finally {
      setSaving(false);
    }
  };

  const handleAutoDiscoverModels = async () => {
    setDiscoveringModels(true);
    try {
      const result = await api.discoverModels(provider.id, undefined, true);

      if (!result.success) {
        message.error(result.message || "自动发现模型失败");
        return;
      }

      await onSaved();

      if (result.added_count > 0) {
        message.success(
          `自动发现完成，新增 ${result.added_count} 个模型`,
        );
        return;
      }

      message.info(
        result.message ||
          "自动发现完成，未新增模型",
      );
    } catch (error) {
      const errMsg =
        error instanceof Error
          ? error.message
          : "自动发现模型失败";
      message.error(errMsg);
    } finally {
      setDiscoveringModels(false);
    }
  };

  useEffect(() => {
    if (!adding) {
      setDiscoveredModels([]);
      return;
    }
    setLoadingDiscoveredModels(true);
    api
      .discoverModels(provider.id, undefined, false)
      .then((result) => {
        const sorted = result.models
          .slice()
          .sort((a, b) => a.id.localeCompare(b.id));
        setDiscoveredModels(sorted as unknown as ExtendedModelInfo[]);
      })
      .catch(() => setDiscoveredModels([]))
      .finally(() => setLoadingDiscoveredModels(false));
  }, [adding, provider.id]);

  useEffect(() => {
    if (!isOpenRouter || !adding) return;
    setAdding(false);
    form.resetFields();
  }, [adding, form, isOpenRouter]);

  const deferredSearchQuery = useDeferredValue(modelSearchQuery);

  useEffect(() => {
    setVisibleCount(PAGE_SIZE);
  }, [deferredSearchQuery]);

  const filteredModels = useMemo(() => {
    const all_models = [
      ...(provider.extra_models ?? []),
      ...(provider.models ?? []),
    ];
    const q = deferredSearchQuery.trim().toLowerCase();
    if (!q) return all_models;
    return all_models.filter(
      (m) => m.name.toLowerCase().includes(q) || m.id.toLowerCase().includes(q),
    );
  }, [provider.models, provider.extra_models, deferredSearchQuery]);

  const colors = tagColors(isDark);

  return (
    <Modal
      title={`${provider.name} — 模型管理`}
      open={open}
      onCancel={handleClose}
      footer={null}
      width={800}
      className={styles.modelManageModal}
      destroyOnHidden
    >
      <Input
        placeholder={"搜索模型..."}
        value={modelSearchQuery}
        onChange={(e) => setModelSearchQuery(e.target.value)}
        prefix={<SearchOutlined />}
        allowClear
      />

      {/* Model list */}
      <div className={styles.modelList}>
        {filteredModels.length === 0 ? (
          <div className={styles.modelListEmpty}>{"暂无模型"}</div>
        ) : (
          <>
            {filteredModels.slice(0, visibleCount).map((m) => {
              const isDeletable = provider.is_custom || extraModelIds.has(m.id);
              const isConfigOpen = configOpenModelId === m.id;
              return (
                <div key={m.id}>
                  <div className={styles.modelListItem}>
                    <div className={styles.modelListItemInfo}>
                      <span className={styles.modelListItemName}>{m.name}</span>
                      <span className={styles.modelListItemId}>{m.id}</span>
                    </div>
                    <div className={styles.modelListItemActions}>
                      <CapabilityTags model={m} isDark={isDark} />
                      {m.is_free && (
                        <Tag
                          style={{
                            fontSize: 11,
                            marginRight: 4,
                            ...colors.free,
                          }}
                        >
                          <GiftOutlined
                            style={{ fontSize: 10, marginRight: 3 }}
                          />
                          {"免费"}
                        </Tag>
                      )}
                      <Tag
                        style={{
                          fontSize: 11,
                          marginRight: 4,
                          ...(isDeletable ? colors.userAdded : colors.builtin),
                        }}
                      >
                        {isDeletable ? (
                          <UserOutlined
                            style={{ fontSize: 10, marginRight: 3 }}
                          />
                        ) : (
                          <DatabaseOutlined
                            style={{ fontSize: 10, marginRight: 3 }}
                          />
                        )}
                        {isDeletable ? "用户添加" : "内置"}
                      </Tag>
                      <span
                        style={{
                          display: "inline-block",
                          width: 1,
                          height: 16,
                          background: isDark
                            ? "rgba(255,255,255,0.15)"
                            : "#e5e7eb",
                          margin: "0 8px",
                          flexShrink: 0,
                        }}
                      />
                      {m.probe_source !== "documentation" && (
                        <Tooltip
                          title={"测试多模态"}
                        >
                          <Button
                            type="text"
                            size="small"
                            icon={<ExperimentOutlined />}
                            onClick={() => handleProbeMultimodal(m.id)}
                            loading={probingModelId === m.id}
                            style={darkBtnStyle}
                          />
                        </Tooltip>
                      )}
                      <Tooltip title={"测试连接"}>
                        <Button
                          type="text"
                          size="small"
                          icon={<ApiOutlined />}
                          onClick={() => handleTestModel(m.id)}
                          loading={testingModelId === m.id}
                          style={darkBtnStyle}
                        />
                      </Tooltip>
                      <Tooltip title={"模型配置"}>
                        <Button
                          type="text"
                          size="small"
                          icon={
                            isConfigOpen ? (
                              <DownOutlined />
                            ) : (
                              <SettingOutlined />
                            )
                          }
                          onClick={() =>
                            setConfigOpenModelId(isConfigOpen ? null : m.id)
                          }
                          style={darkBtnStyle}
                        />
                      </Tooltip>
                      {isDeletable && (
                        <Button
                          type="text"
                          size="small"
                          danger
                          icon={<DeleteOutlined />}
                          onClick={() => handleRemoveModel(m.id, m.name)}
                        />
                      )}
                    </div>
                  </div>
                  {isConfigOpen && (
                    <div
                      style={{
                        padding: "0 16px 12px",
                        borderBottom: isDark
                          ? "1px solid rgba(255,255,255,0.06)"
                          : "1px solid #f5f5f5",
                      }}
                    >
                      <ModelConfigEditor
                        providerId={provider.id}
                        model={m}
                        onSaved={onSaved}
                        onProviderUpdated={onProviderUpdated}
                        onClose={() => setConfigOpenModelId(null)}
                        isDark={isDark}
                        thinkingParamStyle={
                          extraModelIds.has(m.id)
                            ? undefined
                            : m.thinking_param_style ??
                              provider.thinking_param_style
                        }
                        reasoningEffortOptions={
                          m.reasoning_effort_options ??
                          provider.reasoning_effort_options
                        }
                        thinkingBudgetRange={
                          (m.thinking_budget_range ??
                            provider.thinking_budget_range) as
                            | [number, number]
                            | undefined
                        }
                      />
                    </div>
                  )}
                </div>
              );
            })}
            {filteredModels.length > visibleCount && (
              <div className={styles.modelListLoadMore}>
                <Button
                  type="link"
                  size="small"
                  onClick={() => setVisibleCount((c) => c + PAGE_SIZE)}
                >
                  {`加载更多 (${Math.min(
                    PAGE_SIZE,
                    filteredModels.length - visibleCount,
                  )})`}
                </Button>
                <span className={styles.modelListCount}>
                  {visibleCount} / {filteredModels.length}
                </span>
              </div>
            )}
          </>
        )}
      </div>

      {isOpenRouter && (
        <OpenRouterFilterSection
          showFilters={showFilters}
          availableSeries={availableSeries}
          selectedSeries={selectedSeries}
          selectedInputModalities={selectedInputModalities}
          showFreeOnly={showFreeOnly}
          loadingFilters={loadingFilters}
          discoveredModels={discoveredModels}
          saving={saving}
          isDark={isDark}
          freeTagStyle={colors.free}
          onToggleFilters={() => setShowFilters(!showFilters)}
          onSelectedSeriesChange={setSelectedSeries}
          onSelectedInputModalitiesChange={setSelectedInputModalities}
          onShowFreeOnlyChange={setShowFreeOnly}
          onFetchModels={handleFetchModels}
          onAddModel={handleAddFilteredModel}
        />
      )}

      {/* Add model section */}
      {!isOpenRouter &&
        (adding ? (
          <div className={styles.modelAddForm}>
            <Form form={form} layout="vertical" style={{ marginBottom: 0 }}>
              <Form.Item
                name="id"
                label={"模型 ID"}
                rules={[{ required: true, message: "模型 ID" }]}
                style={{ marginBottom: 12 }}
              >
                <AutoComplete
                  placeholder={"例如 gpt-4o, gemini-2.0-flash"}
                  options={discoveredModels.map((model) => ({
                    value: model.id,
                    label: model.id,
                  }))}
                  filterOption={(
                    inputValue: string,
                    option?: { value?: string },
                  ) =>
                    option?.value
                      ?.toLowerCase()
                      .includes(inputValue.toLowerCase()) ?? false
                  }
                  notFoundContent={
                    loadingDiscoveredModels
                      ? "加载中..."
                      : "未发现可用模型。该供应商可能不支持模型列表查询，请手动输入模型 ID。"
                  }
                >
                  <Input />
                </AutoComplete>
              </Form.Item>
              <Form.Item
                name="name"
                label={"模型名称"}
                style={{ marginBottom: 12 }}
              >
                <Input placeholder={"例如 GPT-4o, Gemini 2.0 Flash"} />
              </Form.Item>
              <div
                style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}
              >
                <Button
                  size="small"
                  onClick={() => {
                    setAdding(false);
                    form.resetFields();
                  }}
                >
                  {"取消"}
                </Button>
                <Button
                  type="primary"
                  size="small"
                  loading={saving}
                  onClick={handleAddModel}
                >
                  {"添加模型"}
                </Button>
              </div>
            </Form>
          </div>
        ) : (
          <div className={styles.modalActionRow}>
            {supportsAutoDiscover && (
              <Button
                icon={<SearchOutlined />}
                loading={discoveringModels}
                onClick={handleAutoDiscoverModels}
                style={{ flex: 1 }}
              >
                {"自动发现模型"}
              </Button>
            )}
            <Button
              type="dashed"
              icon={<PlusOutlined />}
              onClick={() => setAdding(true)}
              style={{ flex: 1 }}
            >
              {"添加模型"}
            </Button>
          </div>
        ))}
    </Modal>
  );
}
