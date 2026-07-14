import { useState, useEffect } from "react";
import { useAppMessage } from "../../../../hooks/useAppMessage";
import type { MarkdownFile } from "../../../../api/types";
import { workspaceApi } from "../../../../api/modules/workspace";
import { useAgentStore } from "../../../../stores/agentStore";

const getParentDir = (filePath: string): string => {
  const match = filePath.match(/^(.*)[/\\]/);
  return match ? match[1] : filePath;
};

export const useAgentsData = () => {
  const { selectedAgent } = useAgentStore();
  const [files, setFiles] = useState<MarkdownFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<MarkdownFile | null>(null);
  const [fileContent, setFileContent] = useState("");
  const [originalContent, setOriginalContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [workspacePath, setWorkspacePath] = useState<string | null>(null);
  const [enabledFiles, setEnabledFiles] = useState<string[]>([]);
  const { message } = useAppMessage();

  const sortFilesByEnabled = (
    fileList: MarkdownFile[],
    currentEnabledFiles: string[],
  ) => {
    const safeEnabled = Array.isArray(currentEnabledFiles)
      ? currentEnabledFiles
      : [];
    return [...fileList].sort((a, b) => {
      const aIndex = safeEnabled.indexOf(a.filename);
      const bIndex = safeEnabled.indexOf(b.filename);
      if (aIndex !== -1 && bIndex !== -1) return aIndex - bIndex;
      if (aIndex !== -1) return -1;
      if (bIndex !== -1) return 1;
      return a.filename.localeCompare(b.filename);
    });
  };

  const fetchEnabledFiles = async () => {
    try {
      const result = await workspaceApi.getSystemPromptFiles();
      const enabled = Array.isArray(result) ? result : [];
      setEnabledFiles(enabled);
      return enabled;
    } catch (error) {
      console.error("Failed to fetch enabled files", error);
      return [];
    }
  };

  const refreshFiles = async (latestEnabledFiles?: string[]) => {
    const enabled = Array.isArray(latestEnabledFiles)
      ? latestEnabledFiles
      : await fetchEnabledFiles();
    const fileList = await workspaceApi.listFiles();
    const markdownFiles = fileList as unknown as MarkdownFile[];
    setFiles(sortFilesByEnabled(markdownFiles, enabled));
    setWorkspacePath(
      fileList.length > 0 ? getParentDir(fileList[0].path) : "",
    );
    return markdownFiles;
  };

  useEffect(() => {
    const initializeData = async () => {
      const previousFilename = selectedFile?.filename;
      setFileContent("");
      setOriginalContent("");
      try {
        const fileList = await refreshFiles();
        const previous = fileList.find(
          (file) => file.filename === previousFilename,
        );
        if (previous) await handleFileClick(previous);
        else setSelectedFile(null);
      } catch (error) {
        console.error("Failed to initialize workspace files", error);
        message.error("Failed to load file list");
      }
    };
    void initializeData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAgent]);

  useEffect(() => {
    if (files.length === 0) return;
    const sorted = sortFilesByEnabled(files, enabledFiles);
    if (sorted.some((file, index) => file.filename !== files[index]?.filename)) {
      setFiles(sorted);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabledFiles]);

  const fetchFiles = async (latestEnabledFiles?: string[]) => {
    try {
      await refreshFiles(latestEnabledFiles);
    } catch (error) {
      console.error("Failed to fetch files", error);
      message.error("Failed to load file list");
    }
  };

  const handleFileClick = async (file: MarkdownFile) => {
    setSelectedFile(file);
    setLoading(true);
    try {
      const data = await workspaceApi.loadFile(file.filename);
      setFileContent(data.content);
      setOriginalContent(data.content);
    } catch (error) {
      console.error("Failed to load file", error);
      message.error("Failed to load file");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!selectedFile) return;
    setLoading(true);
    try {
      await workspaceApi.saveFile(selectedFile.filename, fileContent);
      setOriginalContent(fileContent);
      message.success("Saved successfully");
      await fetchFiles();
    } catch (error) {
      console.error("Failed to save file", error);
      message.error("Failed to save");
    } finally {
      setLoading(false);
    }
  };

  const handleToggleFileEnabled = async (filename: string) => {
    const next = enabledFiles.includes(filename)
      ? enabledFiles.filter((file) => file !== filename)
      : [...enabledFiles, filename];
    try {
      await workspaceApi.setSystemPromptFiles(next);
      setEnabledFiles(next);
      message.success("系统提示词配置已更新");
    } catch (error) {
      console.error("Failed to update system prompt files", error);
      message.error("更新系统提示词配置失败");
    }
  };

  const handleReorderFiles = async (newOrder: string[]) => {
    try {
      await workspaceApi.setSystemPromptFiles(newOrder);
      setEnabledFiles(newOrder);
    } catch (error) {
      console.error("Failed to reorder files", error);
      message.error("Failed to update file order");
    }
  };

  return {
    files,
    selectedFile,
    fileContent,
    loading,
    workspacePath,
    hasChanges: fileContent !== originalContent,
    enabledFiles,
    setFileContent,
    fetchFiles,
    handleFileClick,
    handleSave,
    handleReset: () => setFileContent(originalContent),
    handleToggleFileEnabled,
    handleReorderFiles,
  };
};
