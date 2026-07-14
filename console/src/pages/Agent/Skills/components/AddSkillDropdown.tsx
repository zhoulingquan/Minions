import { Button, Dropdown } from "@agentscope-ai/design";
import type { MenuProps } from "antd";
import {
  AppstoreOutlined,
  DownloadOutlined,
  ImportOutlined,
  PlusOutlined,
  UploadOutlined,
} from "@ant-design/icons";

interface AddSkillDropdownProps {
  onCreate: () => void;
  /** Skills page only — omitted on the global skills page (it IS the pool). */
  onFromGlobal?: () => void;
  onUploadZip: () => void;
  onFromUrl: () => void;
  onBrowseMarket: () => void;
  uploading?: boolean;
}

/**
 * Single entry point for every way of adding a skill: create, pull from the
 * global skills, upload a zip, import from a hub URL, or browse the market.
 */
export function AddSkillDropdown({
  onCreate,
  onFromGlobal,
  onUploadZip,
  onFromUrl,
  onBrowseMarket,
  uploading,
}: AddSkillDropdownProps) {

  const items: MenuProps["items"] = [
    {
      key: "create",
      label: "创建技能",
      icon: <PlusOutlined />,
      onClick: onCreate,
    },
    ...(onFromGlobal
      ? [
          {
            key: "from-global",
            label: "从全局技能载入",
            icon: <DownloadOutlined />,
            onClick: onFromGlobal,
          },
        ]
      : []),
    {
      key: "upload-zip",
      label: "通过Zip上传",
      icon: <UploadOutlined />,
      disabled: uploading,
      onClick: onUploadZip,
    },
    {
      key: "from-url",
      label: "通过URL上传",
      icon: <ImportOutlined />,
      onClick: onFromUrl,
    },
    { type: "divider" },
    {
      key: "market",
      label: "浏览市场",
      icon: <AppstoreOutlined />,
      onClick: onBrowseMarket,
    },
  ];

  return (
    <Dropdown menu={{ items }} placement="bottomRight">
      <Button type="primary" icon={<PlusOutlined />} loading={uploading}>
        {"添加技能"}
      </Button>
    </Dropdown>
  );
}
