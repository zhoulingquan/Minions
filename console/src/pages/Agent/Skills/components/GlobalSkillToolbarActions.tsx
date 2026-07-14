import { Button, Dropdown } from "@agentscope-ai/design";
import { Badge } from "antd";
import {
  CheckSquareOutlined,
  MoreOutlined,
  PlusOutlined,
  SettingOutlined,
  SyncOutlined,
} from "@ant-design/icons";

import styles from "../index.module.less";

interface GlobalSkillToolbarActionsProps {
  hasUpdates: boolean;
  updateCount: number;
  hasUnseenUpdate: boolean;
  onAddSkill: () => void;
  onStartBatch: () => void;
  onManageBuiltins: () => void | Promise<void>;
}

export function GlobalSkillToolbarActions({
  hasUpdates,
  updateCount,
  hasUnseenUpdate,
  onAddSkill,
  onStartBatch,
  onManageBuiltins,
}: GlobalSkillToolbarActionsProps) {
  const updateLabel =
    updateCount > 0 ? `更新内置技能（${updateCount}）` : "更新内置技能";
  const menuItems = [
    {
      key: "add-skill",
      label: "添加新技能",
      icon: <PlusOutlined />,
      onClick: onAddSkill,
    },
    {
      key: "batch-operations",
      label: "批量操作",
      icon: <CheckSquareOutlined />,
      onClick: onStartBatch,
    },
    {
      key: "manage-builtin-skills",
      label: "管理内置技能",
      icon: <SettingOutlined />,
      onClick: () => void onManageBuiltins(),
    },
  ];

  return (
    <>
      {hasUpdates && (
        <Badge
          dot={hasUnseenUpdate}
          color="rgba(255, 157, 77, 1)"
          offset={[-4, 4]}
        >
          <Button
            className={styles.builtinUpdateButton}
            icon={<SyncOutlined />}
            onClick={() => void onManageBuiltins()}
          >
            {updateLabel}
          </Button>
        </Badge>
      )}
      <Dropdown menu={{ items: menuItems }} placement="bottomRight">
        <Button icon={<MoreOutlined />}>更多操作</Button>
      </Dropdown>
    </>
  );
}
