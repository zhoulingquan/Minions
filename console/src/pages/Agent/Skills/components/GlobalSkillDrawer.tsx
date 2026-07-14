import {
  Button,
  Drawer,
  Form,
  Input,
  Modal,
  Select,
  Switch,
} from "@agentscope-ai/design";
import type {
  GlobalSkillSpec,
  WorkspaceSkillSummary,
} from "../../../../api/types";
import {
  deriveInstalledFromLabel,
  getGlobalBuiltinStatusLabel,
  getGlobalBuiltinStatusTone,
  isSkillBuiltin,
} from "@/utils/skill";
import { getAgentDisplayName } from "../../../../utils/agentDisplayName";
import { MarkdownCopy } from "../../../../components/MarkdownCopy/MarkdownCopy";
import type { GlobalSkillMode } from "./useGlobalSkills";
import styles from "../index.module.less";

type FormInstance = ReturnType<typeof Form.useForm>[0];

interface GlobalSkillDrawerProps {
  presentation?: "drawer" | "floating";
  mode: GlobalSkillMode | null;
  activeSkill: GlobalSkillSpec | null;
  form: FormInstance;
  drawerContent: string;
  showMarkdown: boolean;
  configText: string;
  workspaces?: WorkspaceSkillSummary[];
  autoUpdateEnabled?: boolean;
  autoUpdateTargets?: string[];
  onClose: () => void;
  onSave: () => void;
  onContentChange: (content: string) => void;
  onShowMarkdownChange: (value: boolean) => void;
  onConfigTextChange: (text: string) => void;
  onChangeBuiltinLanguage?: (skill: GlobalSkillSpec, language: string) => void;
  onAutoUpdateEnabledChange?: (enabled: boolean) => void;
  onAutoUpdateTargetsChange?: (targets: string[]) => void;
  validateFrontmatter: (_: unknown, value: string) => Promise<void>;
}

export function GlobalSkillDrawer({
  presentation = "drawer",
  mode,
  activeSkill,
  form,
  drawerContent,
  showMarkdown,
  configText,
  workspaces = [],
  autoUpdateEnabled = false,
  autoUpdateTargets = [],
  onClose,
  onSave,
  onContentChange,
  onShowMarkdownChange,
  onConfigTextChange,
  onChangeBuiltinLanguage,
  onAutoUpdateEnabledChange,
  onAutoUpdateTargetsChange,
  validateFrontmatter,
}: GlobalSkillDrawerProps) {
  const title =
    mode === "edit" ? `编辑 ${activeSkill?.name || ""}` : "创建全局技能项目";
  const open = mode === "create" || mode === "edit";
  const footer = (
    <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
      <Button onClick={onClose}>{"取消"}</Button>
      <Button type="primary" onClick={onSave}>
        {mode === "edit" ? "保存" : "创建"}
      </Button>
    </div>
  );

  const content = (
    <>
      {mode === "edit" && activeSkill && (
        <>
          <div className={styles.metaStack} style={{ marginBottom: 12 }}>
            <div className={styles.infoSection}>
              <div className={styles.infoLabel}>{"状态"}</div>
              <div
                className={`${styles.infoBlock} ${
                  styles[getGlobalBuiltinStatusTone(activeSkill.sync_status)]
                }`}
              >
                {getGlobalBuiltinStatusLabel(activeSkill.sync_status)}
              </div>
            </div>
            {isSkillBuiltin(activeSkill.source) &&
              (activeSkill.available_builtin_languages?.length ?? 0) > 1 &&
              onChangeBuiltinLanguage && (
                <div className={styles.infoSection}>
                  <div className={styles.infoLabel}>{"语言"}</div>
                  <div className={styles.languageToggle}>
                    {activeSkill.available_builtin_languages?.map((lang) => (
                      <Button
                        key={lang}
                        size="small"
                        type={
                          activeSkill.builtin_language === lang
                            ? "primary"
                            : "default"
                        }
                        onClick={() =>
                          void onChangeBuiltinLanguage(activeSkill, lang)
                        }
                      >
                        {lang === "zh" ? "中文" : "English"}
                      </Button>
                    ))}
                  </div>
                </div>
              )}
            <div className={styles.infoSection}>
              <div className={styles.infoLabel}>{"安装来源"}</div>
              <div className={styles.infoBlock}>
                {activeSkill.external && activeSkill.external_path
                  ? activeSkill.external_path
                  : deriveInstalledFromLabel(activeSkill.installed_from)}
              </div>
            </div>
          </div>
          <div style={{ marginBottom: 16 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 8,
                marginBottom: 8,
              }}
            >
              <span className={styles.infoLabel}>{"自动同步"}</span>
              <Switch
                checked={autoUpdateEnabled}
                onChange={(checked) => onAutoUpdateEnabledChange?.(checked)}
              />
            </div>
            {autoUpdateEnabled && (
              <div>
                <Select
                  mode="multiple"
                  style={{ width: "100%" }}
                  value={autoUpdateTargets.filter((id) =>
                    workspaces.some((ws) => ws.agent_id === id),
                  )}
                  onChange={(value) =>
                    onAutoUpdateTargetsChange?.(value as string[])
                  }
                  placeholder={"所有已安装该技能的智能体"}
                  options={workspaces.map((ws) => ({
                    label: getAgentDisplayName(
                      { id: ws.agent_id, name: ws.agent_name ?? "" },
                    ),
                    value: ws.agent_id,
                  }))}
                />
                <div
                  style={{
                    marginTop: 4,
                    fontSize: 12,
                    opacity: 0.6,
                  }}
                >
                  {"留空则同步到所有已安装该技能的智能体；选择智能体后仅同步到所选项（缺失时会自动安装）。"}
                </div>
              </div>
            )}
          </div>
        </>
      )}
      <Form form={form} layout="vertical">
        <Form.Item
          name="name"
          label={"技能名称"}
          rules={[{ required: true, message: "请输入技能名称" }]}
        >
          <Input placeholder={"技能名称"} />
        </Form.Item>

        <Form.Item
          name="content"
          rules={[{ required: true, validator: validateFrontmatter }]}
        >
          <MarkdownCopy
            content={drawerContent}
            showMarkdown={showMarkdown}
            onShowMarkdownChange={onShowMarkdownChange}
            editable={true}
            onContentChange={onContentChange}
            textareaProps={{
              placeholder: "SKILL.md 内容",
              rows: 12,
            }}
          />
        </Form.Item>

        <Form.Item label={"配置"}>
          <Input.TextArea
            rows={4}
            value={configText}
            onChange={(e) => {
              onConfigTextChange(e.target.value);
            }}
            placeholder={"{\"KEY\": \"value\"}"}
          />
        </Form.Item>
      </Form>
    </>
  );

  if (presentation === "floating") {
    return (
      <Modal
        open={open}
        onCancel={onClose}
        title={title}
        footer={footer}
        width={720}
        destroyOnHidden
      >
        <div style={{ maxHeight: "65vh", overflowY: "auto", paddingRight: 4 }}>
          {content}
        </div>
      </Modal>
    );
  }

  return (
    <Drawer
      width={520}
      placement="right"
      title={title}
      open={open}
      onClose={onClose}
      destroyOnHidden
      footer={footer}
    >
      {content}
    </Drawer>
  );
}
