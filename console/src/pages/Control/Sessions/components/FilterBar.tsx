import { Input, Select } from "@agentscope-ai/design";
import styles from "../index.module.less";

interface FilterBarProps {
  isMobile?: boolean;
  filterUserId: string;
  filterChannel: string;
  filterTitle: string;
  uniqueChannels: string[];
  onUserIdChange: (value: string) => void;
  onChannelChange: (value: string) => void;
  onTitleChange: (value: string) => void;
}

export function FilterBar({
  isMobile,
  filterUserId,
  filterChannel,
  filterTitle,
  uniqueChannels,
  onUserIdChange,
  onChannelChange,
  onTitleChange,
}: FilterBarProps) {

  return (
    <div className={styles.filterBar}>
      <Input
        placeholder={"按标题筛选"}
        value={filterTitle}
        onChange={(e) => onTitleChange(e.target.value)}
        allowClear
        className="sessions-filter-input"
        style={isMobile ? { width: "100%" } : { width: 200, marginRight: 8 }}
      />
      <Input
        placeholder={"按用户ID筛选"}
        value={filterUserId}
        onChange={(e) => onUserIdChange(e.target.value)}
        allowClear
        className="sessions-filter-input"
        style={isMobile ? { width: "100%" } : { width: 200, marginRight: 8 }}
      />
      <Select
        placeholder={"按频道筛选"}
        value={filterChannel || undefined}
        onChange={(value) => onChannelChange(value || "")}
        allowClear
        className="sessions-filter-select"
        style={isMobile ? { width: "100%" } : { width: 180 }}
      >
        {uniqueChannels.map((channel) => (
          <Select.Option key={channel} value={channel}>
            {channel}
          </Select.Option>
        ))}
      </Select>
    </div>
  );
}
