import React from "react";
import { Button, Card } from "@agentscope-ai/design";
import { ReloadOutlined } from "@ant-design/icons";
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
  arrayMove,
} from "@dnd-kit/sortable";
import type { MarkdownFile } from "../../../../api/types";
import { FileItem } from "./FileItem";
import styles from "../index.module.less";

interface FileListPanelProps {
  files: MarkdownFile[];
  selectedFile: MarkdownFile | null;
  enabledFiles: string[];
  onRefresh: () => void;
  onFileClick: (file: MarkdownFile) => void;
  onToggleEnabled: (filename: string) => void;
  onReorder: (newOrder: string[]) => void;
}

export const FileListPanel: React.FC<FileListPanelProps> = ({
  files,
  selectedFile,
  enabledFiles,
  onRefresh,
  onFileClick,
  onToggleEnabled,
  onReorder,
}) => {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = enabledFiles.indexOf(active.id as string);
    const newIndex = enabledFiles.indexOf(over.id as string);
    if (oldIndex === -1 || newIndex === -1) return;
    onReorder(arrayMove(enabledFiles, oldIndex, newIndex));
  };

  return (
    <div className={styles.fileListPanel}>
      <Card
        bodyStyle={{
          padding: 16,
          display: "flex",
          flexDirection: "column",
          height: "100%",
          overflow: "auto",
        }}
        style={{ flex: 1, minHeight: 0 }}
      >
        <div className={styles.headerRow}>
          <h3 className={styles.sectionTitle}>{"核心文件"}</h3>
          <Button size="small" onClick={onRefresh} icon={<ReloadOutlined />} />
        </div>
        <p className={styles.infoText}>{"引导角色、身份和工具指南。"}</p>
        <div className={styles.divider} />
        <div className={styles.scrollContainer}>
          {files.length > 0 ? (
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext
                items={enabledFiles}
                strategy={verticalListSortingStrategy}
              >
                {files.map((file) => (
                  <FileItem
                    key={file.filename}
                    file={file}
                    selectedFile={selectedFile}
                    enabled={enabledFiles.includes(file.filename)}
                    onFileClick={onFileClick}
                    onToggleEnabled={onToggleEnabled}
                  />
                ))}
              </SortableContext>
            </DndContext>
          ) : (
            <div className={styles.emptyState}>{"没有文件"}</div>
          )}
        </div>
      </Card>
    </div>
  );
};
