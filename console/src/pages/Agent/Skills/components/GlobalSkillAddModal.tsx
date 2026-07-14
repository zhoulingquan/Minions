import { Button, Modal } from "@agentscope-ai/design";
import {
  AppstoreOutlined,
  FileAddOutlined,
  LinkOutlined,
  UploadOutlined,
} from "@ant-design/icons";

interface GlobalSkillAddModalProps {
  open: boolean;
  onClose: () => void;
  onCreate: () => void;
  onUploadZip: () => void;
  onImportUrl: () => void;
  onBrowseMarket: () => void;
}

const optionStyle = {
  alignItems: "flex-start",
  display: "flex",
  gap: 12,
  height: "auto",
  justifyContent: "flex-start",
  padding: "16px",
  textAlign: "left" as const,
  whiteSpace: "normal" as const,
};

export function GlobalSkillAddModal({
  open,
  onClose,
  onCreate,
  onUploadZip,
  onImportUrl,
  onBrowseMarket,
}: GlobalSkillAddModalProps) {
  const choose = (action: () => void) => {
    onClose();
    action();
  };

  const options = [
    {
      description: "在弹窗中编写技能名称、内容与配置。",
      icon: <FileAddOutlined style={{ fontSize: 20, marginTop: 2 }} />,
      label: "手动创建技能",
      onClick: onCreate,
    },
    {
      description: "导入包含一个或多个技能的 ZIP 压缩包。",
      icon: <UploadOutlined style={{ fontSize: 20, marginTop: 2 }} />,
      label: "上传 ZIP 文件",
      onClick: onUploadZip,
    },
    {
      description: "从受支持的技能市场链接导入技能。",
      icon: <LinkOutlined style={{ fontSize: 20, marginTop: 2 }} />,
      label: "通过 URL 导入",
      onClick: onImportUrl,
    },
    {
      description: "浏览并安装技能市场中的可用技能。",
      icon: <AppstoreOutlined style={{ fontSize: 20, marginTop: 2 }} />,
      label: "浏览技能市场",
      onClick: onBrowseMarket,
    },
  ];

  return (
    <Modal
      open={open}
      onCancel={onClose}
      title="添加全局技能"
      footer={null}
      width={640}
    >
      <p style={{ color: "rgba(20, 20, 19, 0.6)", margin: "0 0 18px" }}>
        选择一种方式，将技能统一添加到全局技能。
      </p>
      <div
        style={{
          display: "grid",
          gap: 12,
          gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
        }}
      >
        {options.map((option) => (
          <Button
            key={option.label}
            type="default"
            style={optionStyle}
            onClick={() => choose(option.onClick)}
          >
            {option.icon}
            <span>
              <strong style={{ display: "block", marginBottom: 4 }}>
                {option.label}
              </strong>
              <span style={{ color: "rgba(20, 20, 19, 0.58)", fontSize: 13 }}>
                {option.description}
              </span>
            </span>
          </Button>
        ))}
      </div>
    </Modal>
  );
}
