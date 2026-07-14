import React from "react";

import { IconButton } from "@agentscope-ai/design";
import { SparkHistoryLine, SparkNewChatFill } from "@agentscope-ai/icons";
import {
  ExpandAltOutlined,
  CompressOutlined,
  MoreOutlined,
} from "@ant-design/icons";
import { Dropdown, Flex, Tooltip } from "antd";
import type { MenuProps } from "antd";
import { useCreateNewSession } from "../../hooks/useCreateNewSession";
import { useIsMobile } from "../../../../hooks/useIsMobile";

interface ChatActionGroupProps {
  /** Callback to toggle the right-side history panel */
  onToggleHistory?: () => void;
  /** Whether the history panel is currently visible */
  historyOpen?: boolean;
  isWideMode?: boolean;
  onToggleWideMode?: () => void;
}

const ChatActionGroup: React.FC<ChatActionGroupProps> = ({
  onToggleHistory,
  historyOpen = false,
  isWideMode = false,
  onToggleWideMode,
}) => {

  const createNewSession = useCreateNewSession();

  // Compact mode follows the viewport: collapse secondary actions only on
  // mobile. This saves space on phones while keeping actions visible on desktop.
  const isCompact = useIsMobile();

  // Build "more" dropdown items for compact mode: History, WideMode.
  const moreItems: MenuProps["items"] = [];
  if (onToggleHistory) {
    moreItems.push({
      key: "history",
      icon: <SparkHistoryLine />,
      label: (
        <div style={{ textAlign: "center" }}>
          {"聊天历史"}
        </div>
      ),
      onClick: () => onToggleHistory(),
    });
  }
  if (onToggleWideMode) {
    moreItems.push({
      key: "wideMode",
      icon: isWideMode ? <CompressOutlined /> : <ExpandAltOutlined />,
      label: (
        <div style={{ textAlign: "center" }}>
          {isWideMode ? "正常模式" : "宽屏模式"}
        </div>
      ),
      onClick: () => onToggleWideMode(),
    });
  }

  return (
    <Flex gap={8} align="center">
      {/* Essential actions always visible */}
      <Tooltip title={"新建聊天"} mouseEnterDelay={0.5}>
        <IconButton
          bordered={false}
          icon={<SparkNewChatFill />}
          onClick={createNewSession}
        />
      </Tooltip>

      {/* History + WideMode: inline when NOT compact */}
      {!isCompact && onToggleHistory && (
        <Tooltip title={"聊天历史"} mouseEnterDelay={0.5}>
          <IconButton
            bordered={false}
            icon={<SparkHistoryLine />}
            style={
              historyOpen
                ? { color: "var(--color-primary, #ff9d4d)" }
                : undefined
            }
            onClick={onToggleHistory}
          />
        </Tooltip>
      )}
      {!isCompact && onToggleWideMode && (
        <Tooltip
          title={
            isWideMode ? "正常模式" : "宽屏模式"
          }
          mouseEnterDelay={0.5}
        >
          <IconButton
            bordered={false}
            icon={isWideMode ? <CompressOutlined /> : <ExpandAltOutlined />}
            onClick={onToggleWideMode}
          />
        </Tooltip>
      )}

      {/* Compact mode: collapse History/WideMode into more dropdown */}
      {isCompact && moreItems.length > 0 && (
        <Dropdown
          menu={{ items: moreItems }}
          trigger={["click"]}
          placement="bottomRight"
        >
          <IconButton bordered={false} icon={<MoreOutlined />} />
        </Dropdown>
      )}
    </Flex>
  );
};

export default ChatActionGroup;
