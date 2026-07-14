import React from "react";
import { ThunderboltOutlined } from "@ant-design/icons";
import type { ToolCallContent } from "../shared/types";
import { ToolCardShell, DefaultBlock } from "../shared";
import { stringifyResult } from "../shared/utils";

export interface MaterializeSkillCardProps {
  content: ToolCallContent;
  isStreaming?: boolean;
}

const MaterializeSkillCard: React.FC<MaterializeSkillCardProps> = ({
  content,
  isStreaming,
}) => {
    const params = content.params || {};
  const skill = (params.name || "") as string;
  const title = skill
    ? `创建 ${skill}`
    : "创建 技能";

  const resultText = stringifyResult(content.result);

  return (
    <ToolCardShell
      content={content}
      isStreaming={isStreaming}
      icon={<ThunderboltOutlined />}
      title={title}
    >
      {resultText && <DefaultBlock title="Output" content={resultText} />}
    </ToolCardShell>
  );
};

export default MaterializeSkillCard;
