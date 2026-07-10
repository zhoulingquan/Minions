import { request } from "../request";
import { getApiUrl } from "../config";
import { buildAuthHeaders } from "../authHeaders";
import { downloadFileFromUrl } from "../../utils/downloadFileFromUrl";
import type { MdFileInfo, MdFileContent, DailyMemoryFile } from "../types";

function getSelectedAgentId(): string {
  try {
    // Read from sessionStorage first (per-tab agent), fall back to localStorage
    const agentStorage =
      sessionStorage.getItem("minions-agent-storage") ||
      localStorage.getItem("minions-agent-storage");
    if (agentStorage) {
      const parsed = JSON.parse(agentStorage);
      const selectedAgent = parsed?.state?.selectedAgent;
      if (selectedAgent) {
        return selectedAgent;
      }
    }
  } catch (error) {
    console.warn("Failed to get selected agent from storage:", error);
  }
  return "default";
}

function generateFallbackFilename(): string {
  const agentId = getSelectedAgentId();
  const now = new Date();
  const timestamp = now
    .toISOString()
    .replace(/[-:]/g, "")
    .replace(/\..+/, "")
    .replace("T", "_")
    .slice(0, 15); // YYYYMMDD_HHMMSS
  return `minions_workspace_${agentId}_${timestamp}.zip`;
}

function encodePath(path: string): string {
  return path.split("/").map(encodeURIComponent).join("/");
}

export const workspaceApi = {
  listFiles: () =>
    request<MdFileInfo[]>("/workspace/files").then((files) =>
      files.map((file) => ({
        ...file,
        updated_at: new Date(file.modified_time).getTime(),
      })),
    ),

  loadFile: (fileName: string) =>
    request<MdFileContent>(`/workspace/files/${encodeURIComponent(fileName)}`),

  saveFile: (fileName: string, content: string) =>
    request<Record<string, unknown>>(
      `/workspace/files/${encodeURIComponent(fileName)}`,
      {
        method: "PUT",
        body: JSON.stringify({ content }),
      },
    ),

  // Workspace package download
  downloadWorkspace: () =>
    downloadFileFromUrl(
      getApiUrl("/workspace/download"),
      generateFallbackFilename(),
      {
        headers: buildAuthHeaders(),
        errorMessage: "Workspace download failed",
        preferResponseFilename: true,
      },
    ),

  // File upload functionality
  uploadFile: async (
    file: File,
  ): Promise<{ success: boolean; message: string }> => {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(getApiUrl("/workspace/upload"), {
      method: "POST",
      headers: buildAuthHeaders(),
      body: formData,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(
        `Upload failed: ${response.status} ${response.statusText} - ${errorText}`,
      );
    }

    return await response.json();
  },

  listDailyMemory: () =>
    request<MdFileInfo[]>("/workspace/memory").then((files) =>
      files.map((file) => {
        const basename = file.filename.split("/").pop() || file.filename;
        const date = basename.replace(".md", "");
        return {
          ...file,
          date,
          updated_at: new Date(file.modified_time).getTime(),
        } as DailyMemoryFile;
      }),
    ),

  loadDailyMemory: (memoryPath: string) =>
    request<MdFileContent>(`/workspace/memory/${encodePath(memoryPath)}`),

  saveDailyMemory: (memoryPath: string, content: string) =>
    request<Record<string, unknown>>(
      `/workspace/memory/${encodePath(memoryPath)}`,
      {
        method: "PUT",
        body: JSON.stringify({ content }),
      },
    ),

  // System prompt files management
  getSystemPromptFiles: () =>
    request<string[]>("/workspace/system-prompt-files"),

  setSystemPromptFiles: (files: string[]) =>
    request<string[]>("/workspace/system-prompt-files", {
      method: "PUT",
      body: JSON.stringify(files),
    }),
};
