import React from "react";
import { FileTextOutlined } from "@ant-design/icons";
import type { ToolCallContent } from "../shared/types";
import { ToolCardShell, DefaultBlock } from "../shared";
import { shortFileName, countLines, stringifyResult } from "../shared/utils";
import styles from "../shared/toolCards.module.less";

export interface ReadFileCardProps {
  content: ToolCallContent;
  isStreaming?: boolean;
}

const ReadFileCard: React.FC<ReadFileCardProps> = ({
  content,
  isStreaming,
}) => {
    const params = content.params || {};
  const file = shortFileName((params.file_path || params.path || "") as string);
  const title = file ? `阅读 ${file}` : "阅读 文件";

  const resultText = stringifyResult(content.result);
  const lineCount = countLines(resultText);

  const badge =
    content.status === "done" && lineCount > 0 ? (
      <span className={styles.lineReadBadge}>
        {`${lineCount}行`}
      </span>
    ) : null;

  return (
    <ToolCardShell
      content={content}
      isStreaming={isStreaming}
      icon={<FileTextOutlined />}
      title={title}
      badges={badge}
    >
      {resultText && <DefaultBlock title="Output" content={resultText} />}
    </ToolCardShell>
  );
};

export default ReadFileCard;
