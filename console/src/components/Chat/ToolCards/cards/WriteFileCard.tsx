import React from "react";
import { FileAddOutlined } from "@ant-design/icons";
import type { ToolCallContent } from "../shared/types";
import { ToolCardShell, DefaultBlock } from "../shared";
import { shortFileName, countLines } from "../shared/utils";
import styles from "../shared/toolCards.module.less";

export interface WriteFileCardProps {
  content: ToolCallContent;
  isStreaming?: boolean;
}

const WriteFileCard: React.FC<WriteFileCardProps> = ({
  content,
  isStreaming,
}) => {
    const params = content.params || {};
  const file = shortFileName((params.file_path || params.path || "") as string);
  const title = file
    ? `创建 ${file}`
    : "创建 文件";

  const writtenContent = (params.content as string) || "";
  const lineCount = countLines(writtenContent);

  const badge =
    !content.status?.startsWith("call") && lineCount > 0 ? (
      <span className={styles.diffAddBadge}>
        {`${lineCount}行`}
      </span>
    ) : null;

  return (
    <ToolCardShell
      content={content}
      isStreaming={isStreaming}
      icon={<FileAddOutlined />}
      title={title}
      badges={badge}
    >
      {writtenContent && (
        <DefaultBlock title="Content" content={writtenContent} />
      )}
    </ToolCardShell>
  );
};

export default WriteFileCard;
