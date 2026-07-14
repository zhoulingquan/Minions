import type { BuiltinUpdateNotice } from "../../../../api/types";

function getNoticeNames(items: Array<{ name: string }> | undefined): string[] {
  return (items || [])
    .map((item) => String(item.name || "").trim())
    .filter(Boolean);
}

export function getBuiltinNoticeLines(
  notice: BuiltinUpdateNotice | null,
): string[] {
  if (!notice?.has_updates) return [];

  const lines: string[] = [];
  const addedNames = getNoticeNames(notice.added);
  const missingNames = getNoticeNames(notice.missing);
  const updatedNames = getNoticeNames(notice.updated);
  const removedNames = getNoticeNames(notice.removed);

  if (addedNames.length > 0) {
    lines.push(
      `新增：${addedNames.join(", ")}`,
    );
  }
  if (missingNames.length > 0) {
    lines.push(
      `缺失：${missingNames.join(", ")}`,
    );
  }
  if (updatedNames.length > 0) {
    lines.push(
      `更新：${updatedNames.join(", ")}`,
    );
  }
  if (removedNames.length > 0) {
    lines.push(
      `移除：${removedNames.join(", ")}`,
    );
  }

  return lines;
}
