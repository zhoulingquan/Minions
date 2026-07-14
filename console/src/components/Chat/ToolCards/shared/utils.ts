/**
 * Shared utility functions for tool cards.
 * Extracted from ToolCallBlock.tsx for reuse across individual card plugins.
 */

import type { ToolCallContent } from "./types";
import { chatApi } from "@/api/modules/chat";

// ---------------------------------------------------------------------------
// URL helpers
// ---------------------------------------------------------------------------

/** Convert a backend file/image URL to a displayable URL */
export function toDisplayUrl(url: string): string {
  if (!url) return "";
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  if (url.startsWith("data:")) return url;
  if (url.startsWith("file://")) url = url.replace("file://", "");
  return chatApi.filePreviewUrl(url.startsWith("/") ? url : `/${url}`);
}

// ---------------------------------------------------------------------------
// File helpers
// ---------------------------------------------------------------------------

/** Extract short file name from a path */
export function shortFileName(filePath: string): string {
  const parts = filePath.replace(/\\/g, "/").split("/");
  return parts[parts.length - 1] || filePath;
}

/** Count lines in a string */
export function countLines(text: unknown): number {
  if (typeof text !== "string" || !text) return 0;
  return text.split("\n").length;
}

/** Get language identifier from file extension for syntax highlighting */
export function getFileLanguage(tc: ToolCallContent): string {
  const params = tc.params || {};
  const filePath = (
    (params.file_path || params.path || "") as string
  ).toLowerCase();
  const ext = filePath.match(/\.([^.]+)$/)?.[1] || "";

  const langMap: Record<string, string> = {
    ts: "typescript",
    tsx: "tsx",
    js: "javascript",
    jsx: "jsx",
    py: "python",
    rb: "ruby",
    go: "go",
    rs: "rust",
    java: "java",
    kt: "kotlin",
    swift: "swift",
    cs: "csharp",
    cpp: "cpp",
    c: "c",
    h: "c",
    hpp: "cpp",
    html: "html",
    css: "css",
    less: "less",
    scss: "scss",
    json: "json",
    yaml: "yaml",
    yml: "yaml",
    toml: "toml",
    xml: "xml",
    sql: "sql",
    sh: "bash",
    bash: "bash",
    zsh: "bash",
    md: "markdown",
    txt: "text",
    conf: "ini",
    ini: "ini",
    dockerfile: "dockerfile",
    makefile: "makefile",
    vue: "vue",
    svelte: "svelte",
    dart: "dart",
    php: "php",
    lua: "lua",
    r: "r",
    scala: "scala",
    ex: "elixir",
    exs: "elixir",
  };

  return langMap[ext] || "";
}

// ---------------------------------------------------------------------------
// Media detection
// ---------------------------------------------------------------------------

const IMG_EXTS = ["png", "jpg", "jpeg", "gif", "bmp", "webp", "svg"];
const VIDEO_EXTS = ["mp4", "avi", "mov", "wmv", "flv", "mkv", "webm"];
const AUDIO_EXTS = ["mp3", "wav", "flac", "ape", "aac", "ogg", "wma"];

export type MediaType = "image" | "video" | "audio" | "file";

export interface MediaInfo {
  url: string;
  name: string;
  type: MediaType;
  size?: number;
}

export function getFileExtFromPath(path: string): string {
  const match = path.match(/\.([^.?#]+)(?:[?#]|$)/);
  return match ? match[1].toLowerCase() : "";
}

function classifyMediaType(ext: string): MediaType {
  if (IMG_EXTS.includes(ext)) return "image";
  if (VIDEO_EXTS.includes(ext)) return "video";
  if (AUDIO_EXTS.includes(ext)) return "audio";
  return "file";
}

/**
 * Extract a URL and filename from a result that uses the MCP content-block
 * array format, e.g.:
 * `[{"type":"file","source":{"type":"url","url":"file:///..."},"filename":"a.txt"},
 *   {"type":"text","text":"File sent successfully."}]`
 *
 * Also handles `{"type":"image","source":{...}}` etc.
 */
function extractUrlFromResultBlocks(
  result: unknown,
): { url: string; filename?: string } | null {
  let arr: unknown[] | null = null;

  if (typeof result === "string") {
    try {
      const parsed = JSON.parse(result);
      if (Array.isArray(parsed)) arr = parsed;
    } catch {
      return null;
    }
  } else if (Array.isArray(result)) {
    arr = result;
  }

  if (!arr) return null;

  for (const block of arr) {
    if (!block || typeof block !== "object") continue;
    const b = block as Record<string, unknown>;

    // Content blocks with source.url (file / image / video / audio types)
    if (b.source && typeof b.source === "object") {
      const src = b.source as Record<string, unknown>;
      if (typeof src.url === "string" && src.url) {
        return {
          url: src.url,
          filename: typeof b.filename === "string" ? b.filename : undefined,
        };
      }
    }

    // Flat blocks: { url: "..." } or { path: "..." }
    if (typeof b.url === "string" && b.url) {
      return {
        url: b.url,
        filename: typeof b.filename === "string" ? b.filename : undefined,
      };
    }
    if (typeof b.path === "string" && b.path) {
      return {
        url: b.path,
        filename: typeof b.filename === "string" ? b.filename : undefined,
      };
    }
  }

  return null;
}

/** Read the first usable path from params (multiple key variants). */
function getPathFromParams(params: Record<string, unknown>): string {
  return (params.file_path ||
    params.image_path ||
    params.video_path ||
    params.audio_path ||
    params.path ||
    "") as string;
}

/** Extract media info from tool params/result (unified for all tool names) */
export function getMediaInfo(tc: ToolCallContent): MediaInfo | null {
  const params = tc.params || {};
  const paramPath = getPathFromParams(params);

  // 1) Try to get a reliable URL from result content blocks
  const fromResult = extractUrlFromResultBlocks(tc.result);

  // 2) Try text-based regex extraction (e.g. "saved to /path/to/file")
  let textUrl = "";
  if (!fromResult && tc.result && typeof tc.result === "string") {
    textUrl = extractUrlFromText(tc.result) || "";
  }

  const rawUrl = fromResult?.url || paramPath || textUrl || "";
  if (!rawUrl) return null;

  const name =
    fromResult?.filename ||
    rawUrl.split("/").pop() ||
    paramPath.split("/").pop() ||
    "file";
  const ext = getFileExtFromPath(name);
  const mediaType = classifyMediaType(ext);

  return { url: toDisplayUrl(rawUrl), name, type: mediaType };
}

/** Try to extract a file URL from a text result via regex patterns */
export function extractUrlFromText(resultStr: string): string | null {
  // 1. "Saved to" pattern
  const pathMatch = resultStr.match(
    /(?:saved to|Saved to|保存到|输出到)[:\s]+([^\s\n]+)/i,
  );
  if (pathMatch) return pathMatch[1].trim();

  // 2. Absolute file path with known media extension
  const filePathMatch = resultStr.match(
    /\/[\w.\-/]+\.(?:png|jpg|jpeg|gif|bmp|webp|svg|mp4|avi|mov|wmv|flv|mkv|webm|mp3|wav|flac|aac|ogg)/i,
  );
  if (filePathMatch) return filePathMatch[0];

  return null;
}

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

/** Generic JSON parse that returns null on failure instead of throwing */
function tryParseJson(text: string): unknown | null {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

interface AgentListItem {
  name?: string;
  display_name?: string;
  id?: string;
  agent_id?: string;
  description?: string;
  status?: string;
}

function isAgentListItem(item: unknown): item is AgentListItem {
  if (!item || typeof item !== "object") return false;

  const candidate = item as Record<string, unknown>;
  // Require at least two identifying fields to reduce false positives
  const identifyingFields = ["name", "display_name", "id", "agent_id"].filter(
    (field) => field in candidate,
  );
  return identifyingFields.length >= 1 && "description" in candidate;
}

function extractAgentListItems(
  value: unknown,
  depth = 0,
): AgentListItem[] | null {
  if (depth > 5) return null;

  if (Array.isArray(value)) {
    if (value.every(isAgentListItem)) {
      return value;
    }

    for (const item of value) {
      const extracted = extractAgentListItems(item, depth + 1);
      if (extracted) return extracted;
    }
    return null;
  }

  if (!value || typeof value !== "object") return null;

  const record = value as Record<string, unknown>;
  if (Array.isArray(record.agents)) {
    return extractAgentListItems(record.agents, depth + 1);
  }

  if (typeof record.text === "string") {
    const parsedText = tryParseJson(record.text);
    if (parsedText !== null) {
      return extractAgentListItems(parsedText, depth + 1);
    }
  }

  if ("output" in record) {
    return extractAgentListItems(record.output, depth + 1);
  }

  if (isAgentListItem(record)) {
    return [record];
  }

  return null;
}

/** Format list_agents result as markdown table */
export function formatAgentList(raw: string): string {
  const parsed = tryParseJson(raw);
  if (parsed === null) return raw;

  const agents = extractAgentListItems(parsed);
  if (!agents || agents.length === 0) return raw;

  const rows = agents.map((agent) => {
    const name = agent.name || agent.display_name || agent.id || "";
    const id = agent.id || agent.agent_id || "";
    const desc = agent.description || "";
    const status = agent.status || "";
    return `| ${name} | \`${id}\` | ${desc} | ${status} |`;
  });

  return `| 名称 | ID | 描述 | 状态 |\n| --- | --- | --- | --- |\n${rows.join("\n")}`;
}

/** Detect if content looks like markdown */
export function looksLikeMarkdown(text: string): boolean {
  if (/\|.+\|/.test(text) && /\|[\s-:]+\|/.test(text)) return true;
  const mdPatterns = /^(#{1,6}\s|[-*]\s|\d+\.\s|\*\*.+\*\*)/m;
  return mdPatterns.test(text);
}

/** Stringify tool result safely */
/**
 * Extract text from MCP content blocks: `[{ type: "text", text: "..." }, ...]`.
 * Returns joined text or null if the input is not MCP format.
 */
function extractMcpText(arr: unknown[]): string | null {
  const textParts = arr
    .filter(
      (item): item is { type: string; text: string } =>
        item != null &&
        typeof item === "object" &&
        (item as Record<string, unknown>).type === "text" &&
        typeof (item as Record<string, unknown>).text === "string",
    )
    .map((item) => item.text);
  return textParts.length > 0 ? textParts.join("\n") : null;
}

/**
 * Convert a tool result to a display string.
 *
 * Handles three cases:
 * 1. String that is a JSON-serialized MCP content block array → extract text
 * 2. Array of MCP content blocks → extract text
 * 3. Anything else → JSON.stringify or return as-is
 */
export function stringifyResult(result: unknown): string {
  if (typeof result === "string") {
    const trimmed = result.trim();
    if (trimmed.startsWith("[")) {
      try {
        const parsed = JSON.parse(trimmed);
        if (Array.isArray(parsed)) {
          const extracted = extractMcpText(parsed);
          if (extracted) return extracted;
        }
      } catch {
        // not valid JSON, return as-is
      }
    }
    return result;
  }
  if (Array.isArray(result)) {
    const extracted = extractMcpText(result);
    if (extracted) return extracted;
  }
  if (result != null) return JSON.stringify(result, null, 2);
  return "";
}
