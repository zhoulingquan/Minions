import React from "react";
import { SendOutlined } from "@ant-design/icons";
import type { ToolCallContent } from "../shared/types";
import { ToolCardShell, MediaPreview } from "../shared";
import { shortFileName, getMediaInfo } from "../shared/utils";

export interface SendFileCardProps {
  content: ToolCallContent;
  isStreaming?: boolean;
}

const SendFileCard: React.FC<SendFileCardProps> = ({
  content,
  isStreaming,
}) => {
    const params = content.params || {};
  const filePath = (params.file_path ||
    params.image_path ||
    params.video_path ||
    params.audio_path ||
    params.path ||
    "") as string;
  const file = shortFileName(filePath);
  const title = file ? `发送 ${file}` : "发送 文件";

  const media = getMediaInfo(content);

  return (
    <ToolCardShell
      content={content}
      isStreaming={isStreaming}
      icon={<SendOutlined />}
      title={title}
    >
      {media && <MediaPreview media={media} />}
    </ToolCardShell>
  );
};

export default SendFileCard;
