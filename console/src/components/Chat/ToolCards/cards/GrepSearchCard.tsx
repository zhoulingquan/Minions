import React from "react";
import { SearchOutlined } from "@ant-design/icons";
import type { ToolCallContent } from "../shared/types";
import { ToolCardShell, DefaultBlock } from "../shared";
import { countLines, stringifyResult } from "../shared/utils";
import styles from "../shared/toolCards.module.less";

export interface GrepSearchCardProps {
  content: ToolCallContent;
  isStreaming?: boolean;
}

const GrepSearchCard: React.FC<GrepSearchCardProps> = ({
  content,
  isStreaming,
}) => {
    const params = content.params || {};
  const pattern = (params.pattern || "") as string;
  const title = pattern
    ? `文本匹配 ${pattern}`
    : "文本匹配";

  const resultText = stringifyResult(content.result);
  const lineCount = countLines(resultText);

  const badge =
    content.status === "done" && lineCount > 0 ? (
      <span className={styles.lineSearchBadge}>
        {`${lineCount}匹配`}
      </span>
    ) : null;

  return (
    <ToolCardShell
      content={content}
      isStreaming={isStreaming}
      icon={<SearchOutlined />}
      title={title}
      badges={badge}
    >
      {resultText && <DefaultBlock title="Output" content={resultText} />}
    </ToolCardShell>
  );
};

export default GrepSearchCard;
