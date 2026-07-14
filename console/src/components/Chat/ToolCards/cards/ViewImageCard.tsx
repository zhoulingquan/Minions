import React from "react";
import { PictureOutlined } from "@ant-design/icons";
import type { ToolCallContent } from "../shared/types";
import { ToolCardShell, MediaPreview } from "../shared";
import { shortFileName, getMediaInfo } from "../shared/utils";

export interface ViewImageCardProps {
  content: ToolCallContent;
  isStreaming?: boolean;
}

const ViewImageCard: React.FC<ViewImageCardProps> = ({
  content,
  isStreaming,
}) => {
    const params = content.params || {};
  const imgPath = (params.image_path || "") as string;
  const file = shortFileName(imgPath);
  const title = file
    ? `查看图片 ${file}`
    : "查看图片";

  const media = getMediaInfo(content);

  return (
    <ToolCardShell
      content={content}
      isStreaming={isStreaming}
      icon={<PictureOutlined />}
      title={title}
    >
      {media && <MediaPreview media={media} />}
    </ToolCardShell>
  );
};

export default ViewImageCard;
