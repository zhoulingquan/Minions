import { request } from "../request";

/** Metadata for a custom tool file on disk (from `GET /custom-tools`). */
export interface CustomToolFile {
  /** Tool file stem (without .py). */
  name: string;
  /** File name including .py. */
  filename: string;
  /** File size in bytes. */
  size: number;
  /** Last modified epoch (seconds). */
  modified_time: number;
}

/** Full content of a custom tool file (from create/get/update). */
export interface CustomToolContent {
  name: string;
  content: string;
  size: number;
  modified_time: number;
}

/** Response from the hot-reload endpoint. */
export interface CustomToolReloadResult {
  reloaded: boolean;
  name: string;
  time: number;
}

export const customToolsApi = {
  /**
   * List all custom tool files on disk.
   */
  list: () => request<CustomToolFile[]>("/custom-tools"),

  /**
   * Create a new custom tool file.
   */
  create: (name: string, content: string) =>
    request<CustomToolContent>("/custom-tools", {
      method: "POST",
      body: JSON.stringify({ name, content }),
    }),

  /**
   * Read the source code of a custom tool file.
   */
  get: (name: string) =>
    request<CustomToolContent>(`/custom-tools/${encodeURIComponent(name)}`),

  /**
   * Update the source code of a custom tool file.
   */
  update: (name: string, content: string) =>
    request<CustomToolContent>(`/custom-tools/${encodeURIComponent(name)}`, {
      method: "PUT",
      body: JSON.stringify({ content }),
    }),

  /**
   * Delete a custom tool file.
   */
  delete: (name: string) =>
    request<{ deleted: boolean; name: string }>(
      `/custom-tools/${encodeURIComponent(name)}`,
      { method: "DELETE" },
    ),

  /**
   * Hot-reload a custom tool file into the running process.
   */
  reload: (name: string) =>
    request<CustomToolReloadResult>(
      `/custom-tools/${encodeURIComponent(name)}/reload`,
      { method: "POST" },
    ),
};
