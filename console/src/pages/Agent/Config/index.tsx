import { useState, useMemo, useEffect } from "react";
import { Button, Form, Tabs } from "@agentscope-ai/design";
import { useSearchParams } from "react-router-dom";
import { useAgentConfig } from "./useAgentConfig.tsx";
import {
  ReactAgentCard,
  LlmRetryCard,
  LlmRateLimiterCard,
  ToolExecutionLevelCard,
  AgentLoopCard,
} from "./components";
import { PageHeader } from "@/components/PageHeader";
import {
  CONTEXT_MANAGER_BACKEND_MAPPINGS,
} from "@/constants/backendMappings";
import api from "@/api";
import styles from "./index.module.less";

function AgentConfigPage() {
    const [searchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(
    searchParams.get("tab") || "reactAgent",
  );
  const {
    form,
    loading,
    saving,
    error,
    language,
    savingLang,
    timezone,
    savingTimezone,
    approvalLevel,
    setApprovalLevel,
    fetchConfig,
    handleSave,
    handleLanguageChange,
    handleTimezoneChange,
  } = useAgentConfig();

  const llmRetryEnabled = Form.useWatch("llm_retry_enabled", form) ?? true;
  const contextBackend =
    Form.useWatch("context_manager_backend", form) || "light";

  const [maxInputLength, setMaxInputLength] = useState(131072);
  useEffect(() => {
    api
      .getActiveModels({ scope: "effective" })
      .then((info) => {
        if (info.active_llm) {
          return api.listProviders().then((providers) => {
            for (const p of providers) {
              const all = [...(p.models ?? []), ...(p.extra_models ?? [])];
              const m = all.find((m) => m.id === info.active_llm?.model);
              if (m?.max_input_length) {
                setMaxInputLength(m.max_input_length);
                return;
              }
            }
          });
        }
      })
      .catch(() => {});
  }, []);

  const dynamicTabs = useMemo(() => {
    const baseTabs = [
      {
        key: "reactAgent",
        label: (
          <span className={styles.tabLabel}>
            {"ReAct 智能体"}
          </span>
        ),
        children: (
          <div className={styles.tabContent}>
            <ReactAgentCard
              language={language}
              savingLang={savingLang}
              onLanguageChange={handleLanguageChange}
              timezone={timezone}
              savingTimezone={savingTimezone}
              onTimezoneChange={handleTimezoneChange}
            />
          </div>
        ),
      },
      {
        key: "agentLoop",
        label: (
          <span className={styles.tabLabel}>
            {"智能体 Loop 设置"}
          </span>
        ),
        children: (
          <div className={styles.tabContent}>
            <AgentLoopCard />
          </div>
        ),
      },
      {
        key: "llmRetry",
        label: (
          <span className={styles.tabLabel}>
            {"LLM 自动重试"}
          </span>
        ),
        children: (
          <div className={styles.tabContent}>
            <LlmRetryCard llmRetryEnabled={llmRetryEnabled} />
          </div>
        ),
      },
      {
        key: "llmRateLimiter",
        label: (
          <span className={styles.tabLabel}>
            {"LLM 并发限流"}
          </span>
        ),
        children: (
          <div className={styles.tabContent}>
            <LlmRateLimiterCard />
          </div>
        ),
      },
    ];

    const contextMapping = CONTEXT_MANAGER_BACKEND_MAPPINGS[contextBackend];
    if (contextMapping) {
      const ContextComponent = contextMapping.component;
      baseTabs.push({
        key: contextMapping.tabKey,
        label: (
          <span className={styles.tabLabel}>
            {"上下文管理"}
          </span>
        ),
        children: (
          <div className={styles.tabContent}>
            <ContextComponent maxInputLength={maxInputLength} />
          </div>
        ),
      });
    }

    // Add Tool Execution Level tab
    baseTabs.push({
      key: "toolExecutionLevel",
      label: (
        <span className={styles.tabLabel}>
          {"工具执行安全"}
        </span>
      ),
      children: (
        <div className={styles.tabContent}>
          <ToolExecutionLevelCard
            value={approvalLevel}
            onChange={setApprovalLevel}
            disabled={saving}
          />
        </div>
      ),
    });

    return baseTabs;
  }, [
    language,
    savingLang,
    timezone,
    savingTimezone,
    handleLanguageChange,
    handleTimezoneChange,
    llmRetryEnabled,
    maxInputLength,
    contextBackend,
    approvalLevel,
    setApprovalLevel,
    saving,
  ]);

  useEffect(() => {
    const tabKeys = dynamicTabs.map((t) => t.key);
    if (!tabKeys.includes(activeTab)) {
      setActiveTab(tabKeys[0] ?? "reactAgent");
    }
  }, [dynamicTabs, activeTab]);

  if (loading) {
    return (
      <div className={styles.configPage}>
        <div className={styles.centerState}>
          <span className={styles.stateText}>{"加载中..."}</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.configPage}>
        <div className={styles.centerState}>
          <span className={styles.stateTextError}>{error}</span>
          <Button size="small" onClick={fetchConfig} style={{ marginTop: 12 }}>
            {"重试"}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.configPage}>
      <PageHeader parent={"工作区"} current={"运行配置"} />

      <div className={styles.content}>
        <Form form={form} layout="vertical" className={styles.form}>
          <Tabs
            className={styles.mainTabs}
            activeKey={activeTab}
            onChange={setActiveTab}
            items={dynamicTabs}
            destroyInactiveTabPane={false}
          />
        </Form>
      </div>

      <div className={styles.footerActions}>
        <Button
          onClick={fetchConfig}
          disabled={saving}
          style={{ marginRight: 8 }}
        >
          {"重置"}
        </Button>
        <Button type="primary" onClick={handleSave} loading={saving}>
          {"保存"}
        </Button>
      </div>
    </div>
  );
}

export default AgentConfigPage;
