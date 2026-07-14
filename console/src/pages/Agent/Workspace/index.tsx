import { useAgentsData, FileListPanel, FileEditor } from "./components";
import styles from "./index.module.less";
import { UploadOutlined, DownloadOutlined } from "@ant-design/icons";
import { Button, Tooltip } from "@agentscope-ai/design";
import { workspaceApi } from "../../../api/modules/workspace";
import { useEffect, useRef, useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { useAppMessage } from "../../../hooks/useAppMessage";
import { useUploadLimitStore } from "../../../stores/uploadLimitStore";
import { DownloadCancelledError } from "../../../utils/downloadFileFromUrl";
import type { MarkdownFile } from "../../../api/types";

export default function WorkspacePage() {
    const { message } = useAppMessage();
  const {
    files,
    selectedFile,
    fileContent,
    workspacePath,
    hasChanges,
    enabledFiles,
    setFileContent,
    fetchFiles,
    handleFileClick,
    handleSave,
    handleReset,
    handleToggleFileEnabled,
    handleReorderFiles,
  } = useAgentsData();

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [downloading, setDownloading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [mobileShowEditor, setMobileShowEditor] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 768px)");
    const update = () => setIsMobile(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    if (!isMobile) {
      setMobileShowEditor(false);
    }
  }, [isMobile]);

  const handleFileClickMobile = (file: MarkdownFile) => {
    void handleFileClick(file);
    if (isMobile) {
      setMobileShowEditor(true);
    }
  };

  const handleBackToFileList = () => {
    setMobileShowEditor(false);
  };

  const handleSaveWithState = async () => {
    setSaving(true);
    try {
      await handleSave();
    } finally {
      setSaving(false);
    }
  };

  const handleDownload = async () => {
    if (downloading) return;
    setDownloading(true);
    message.loading({
      content: "正在准备工作区下载...",
      key: "workspace-download",
      duration: 0,
    });
    try {
      await workspaceApi.downloadWorkspace();
      message.success({
        content: "工作区下载成功",
        key: "workspace-download",
      });
    } catch (error) {
      if (error instanceof DownloadCancelledError) {
        message.destroy("workspace-download");
        return;
      }
      console.error("Download failed:", error);
      message.error({
        content:
          "工作区下载失败" + ": " + (error as Error).message,
        key: "workspace-download",
      });
    } finally {
      setDownloading(false);
    }
  };

  const handleFileUpload = async (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Check if file is zip format
    if (!file.name.toLowerCase().endsWith(".zip")) {
      message.error("仅支持上传 .zip 文件");
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      return;
    }

    const uploadLimit = useUploadLimitStore.getState().uploadMaxSizeMb;
    if (uploadLimit !== null && file.size > uploadLimit * 1024 * 1024) {
      message.error(
        `文件大小超过 ${uploadLimit}MB 限制。当前文件：${(file.size / (1024 * 1024)).toFixed(2)}MB`,
      );
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      return;
    }

    try {
      const result = await workspaceApi.uploadFile(file);
      if (result.success) {
        message.success("文件上传成功");
      } else {
        message.error("文件上传失败" + ": " + result.message);
      }
    } catch (error) {
      console.error("Upload failed:", error);
      message.error(
        "文件上传失败" + ": " + (error as Error).message,
      );
    } finally {
      // Clear input value to allow re-uploading the same file
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className={styles.workspacePage}>
      <PageHeader
        className={styles.pageHeader}
        items={[{ title: "工作区" }, { title: "文件" }]}
        afterBreadcrumb={
          <p className={styles.workspacePath}>
            {"工作区路径："}{" "}
            {workspacePath === null
              ? "加载中..."
              : workspacePath || "没有文件"}
          </p>
        }
        extra={
          <div className={styles.workspaceInfo}>
            <div className={styles.actionButtons}>
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileUpload}
                style={{ display: "none" }}
                accept=".zip"
                title=""
              />
              <Tooltip
                title={`${"引导角色、身份和工具指南。"} (${
                  useUploadLimitStore.getState().uploadMaxSizeMb !== null
                    ? `仅支持 ZIP 文件，最大 ${useUploadLimitStore.getState().uploadMaxSizeMb}MB`
                    : "仅支持 ZIP 文件"
                })`}
                placement="top"
                mouseEnterDelay={0.5}
              >
                <Button
                  size="small"
                  onClick={handleUploadClick}
                  icon={<UploadOutlined />}
                >
                  {"上传"}
                </Button>
              </Tooltip>
              <Button
                size="small"
                onClick={handleDownload}
                loading={downloading}
                disabled={downloading}
                icon={<DownloadOutlined />}
              >
                {"下载"}
              </Button>
            </div>
          </div>
        }
      />

      <div
        className={
          mobileShowEditor
            ? `${styles.content} ${styles.mobileShowEditor}`
            : styles.content
        }
      >
        <FileListPanel
          files={files}
          selectedFile={selectedFile}
          enabledFiles={enabledFiles}
          onRefresh={fetchFiles}
          onFileClick={handleFileClickMobile}
          onToggleEnabled={handleToggleFileEnabled}
          onReorder={handleReorderFiles}
        />

        <FileEditor
          selectedFile={selectedFile}
          fileContent={fileContent}
          hasChanges={hasChanges}
          onContentChange={setFileContent}
          onSave={handleSaveWithState}
          onReset={handleReset}
          onBack={isMobile ? handleBackToFileList : undefined}
          compact={isMobile}
          saving={saving}
        />
      </div>
    </div>
  );
}
