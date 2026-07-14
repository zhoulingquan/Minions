import React from "react";
import { ChromeOutlined } from "@ant-design/icons";
import type { ToolCallContent } from "../shared/types";
import { ToolCardShell, DefaultBlock } from "../shared";
import { stringifyResult } from "../shared/utils";

/**
 * Try to extract meaningful fields from a browser tool result object.
 * Returns extracted text or null if the object doesn't have known fields.
 */
/** Unescape literal \n \t sequences that survived double-serialization. */
function unescapeLiterals(text: string): string {
  return text.replace(/\\n/g, "\n").replace(/\\t/g, "\t");
}

function extractBrowserFields(obj: Record<string, unknown>): string | null {
  const parts: string[] = [];
  if (obj.snapshot && typeof obj.snapshot === "string") {
    parts.push(unescapeLiterals(obj.snapshot));
  }
  if (obj.message && typeof obj.message === "string") {
    parts.push(obj.message);
  }
  if (obj.url && typeof obj.url === "string" && !obj.snapshot) {
    parts.push(`URL: ${obj.url}`);
  }
  return parts.length > 0 ? parts.join("\n\n") : null;
}

/**
 * Extract human-readable text from browser tool results.
 * Handles: string JSON, parsed object, MCP content blocks wrapping JSON.
 */
function formatBrowserResult(result: unknown): string {
  if (result == null) return "";

  // Case 1: result is already an object with snapshot/message/url
  if (typeof result === "object" && !Array.isArray(result)) {
    const extracted = extractBrowserFields(result as Record<string, unknown>);
    if (extracted) return extracted;
  }

  // Case 2: result is a string — try parsing as JSON
  if (typeof result === "string") {
    const trimmed = result.trim();
    if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
      try {
        const parsed = JSON.parse(trimmed);
        // Could be a direct object
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
          const extracted = extractBrowserFields(
            parsed as Record<string, unknown>,
          );
          if (extracted) return extracted;
        }
        // Could be MCP content blocks wrapping a JSON string
        if (Array.isArray(parsed)) {
          for (const item of parsed) {
            if (item?.type === "text" && typeof item.text === "string") {
              try {
                const inner = JSON.parse(item.text);
                if (
                  inner &&
                  typeof inner === "object" &&
                  !Array.isArray(inner)
                ) {
                  const extracted = extractBrowserFields(
                    inner as Record<string, unknown>,
                  );
                  if (extracted) return extracted;
                }
              } catch {
                // text is not JSON, use it directly
              }
            }
          }
        }
      } catch {
        // not valid JSON
      }
    }
  }

  // Fallback: use stringifyResult
  return stringifyResult(result);
}

/** All tool names this card handles */
export const BROWSER_TOOL_NAMES = new Set([
  "browser_use",
  "browser_navigate",
  "navigate",
  "browser_click",
  "click",
  "browser_type",
  "type",
  "browser_snapshot",
  "snapshot",
  "browser_scroll",
  "scroll",
]);

function getBrowserTitle(
  name: string,
  params: Record<string, unknown>,
): string {
  if (name === "browser_use") {
    const action = (params.action || "") as string;
    const url = (params.url || "") as string;
    const selector = (params.selector || params.element || "") as string;
    const text = (params.text || "") as string;
    const width = params.width as number | undefined;
    const height = params.height as number | undefined;
    const key = (params.key || "") as string;
    const path = (params.path || "") as string;
    const code = (params.code || "") as string;
    const filename = (params.filename || "") as string;
    const tabAction = (params.tab_action || "") as string;

    const detail = (() => {
      switch (action) {
        case "start":
          return params.headed
            ? "启动浏览器(有界面)"
            : "启动浏览器";
        case "stop":
          return "关闭浏览器";
        case "open":
          return url
            ? `打开 ${url}`
            : "打开页面";
        case "navigate":
          return url
            ? `导航 ${url}`
            : "导航页面";
        case "navigate_back":
          return "返回上一页";
        case "click":
          return selector
            ? `点击 ${selector}`
            : "点击元素";
        case "type":
          return text
            ? `输入 ${text.length > 20 ? text.slice(0, 20) + "…" : text}`
            : "输入文本";
        case "snapshot":
          return "获取快照";
        case "screenshot":
          return path
            ? `截图 ${path}`
            : "截图";
        case "eval":
        case "evaluate":
          return code
            ? `执行 ${code.length > 30 ? code.slice(0, 30) + "…" : code}`
            : "执行代码";
        case "run_code":
          return code
            ? `运行 ${code.length > 30 ? code.slice(0, 30) + "…" : code}`
            : "运行代码";
        case "close":
          return "关闭页面";
        case "tabs":
          return tabAction
            ? `标签页 ${tabAction}`
            : "管理标签页";
        case "fill_form":
          return "填写表单";
        case "file_upload":
          return filename
            ? `上传 ${filename}`
            : "上传文件";
        case "file_download":
          return filename
            ? `下载 ${filename}`
            : url
            ? `下载 ${url}`
            : "下载文件";
        case "press_key":
          return key
            ? `按键 ${key}`
            : "按键";
        case "hover":
          return selector
            ? `悬停 ${selector}`
            : "悬停元素";
        case "drag":
          return "拖拽";
        case "select_option":
          return "选择选项";
        case "wait_for":
          return text
            ? `等待 ${text}`
            : selector
            ? `等待 ${selector}`
            : "等待元素";
        case "resize":
          return width && height
            ? `调整大小 ${width}x${height}`
            : "调整窗口大小";
        case "pdf":
          return path
            ? `导出PDF ${path}`
            : "导出PDF";
        case "install":
          return "安装";
        case "batch":
          return "批量操作";
        default:
          return action;
      }
    })();
    return `浏览 ${detail}`;
  }

  switch (name) {
    case "browser_navigate":
    case "navigate": {
      const url = (params.url || "") as string;
      return url
        ? `浏览 打开 ${url}`
        : "浏览 打开页面";
    }
    case "browser_click":
    case "click":
      return "浏览 点击";
    case "browser_type":
    case "type":
      return "浏览 输入";
    case "browser_snapshot":
    case "snapshot":
      return "浏览 快照";
    case "browser_scroll":
    case "scroll":
      return "浏览 滚动";
    default:
      return name;
  }
}

export interface BrowserUseCardProps {
  content: ToolCallContent;
  isStreaming?: boolean;
}

const BrowserUseCard: React.FC<BrowserUseCardProps> = ({
  content,
  isStreaming,
}) => {
    const title = getBrowserTitle(content.name, content.params || {});
  const resultText = formatBrowserResult(content.result);

  return (
    <ToolCardShell
      content={content}
      isStreaming={isStreaming}
      icon={<ChromeOutlined />}
      title={title}
    >
      {resultText && <DefaultBlock title="Output" content={resultText} />}
    </ToolCardShell>
  );
};

export default BrowserUseCard;
