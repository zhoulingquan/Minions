/** Pet plugin UI locale — Chinese only. */

export type PetLocale = "zh";

export type MessageKey = keyof typeof messages;

const messages = {
  routeLabel: "宠物",
  title: "Minions 桌面宠物",
  intro:
    "已安装的宠物位于 Minions 工作目录下。启动桌面桥接后，可在不重启 Minions 的情况下切换悬浮宠物。",
  startDesktop: "启动桌面宠物",
  importPet: "导入宠物",
  refresh: "刷新",
  petsDirectory: "宠物目录：",
  desktopHealth: "桌面服务状态：",
  desktopUnknown: "未知（请刷新）",
  colPreview: "预览",
  colName: "名称",
  colFolder: "文件夹",
  colManifestId: "pet.json id",
  colAction: "操作",
  switch: "切换",
  tableEmpty: "未找到宠物。请运行：minions-pet install-pet …",
  desktopAlreadyRunning: "桌面宠物已在运行。",
  desktopStartFailed: "无法启动桌面宠物。",
  desktopReady: "桌面宠物已就绪。",
  desktopStarting: "桌面可能仍在启动中；如有问题请查看 pet-desktop.log。",
  dropFolderOrZip: "请拖入文件夹或 .zip 文件。",
  importChooseFirst: "请先拖入文件夹或选择 .zip 文件。",
  importSuccess: "已导入「{name}」→ {path}",
  switchSuccess: "已切换至「{name}」（{petId}）",
  switchFailed: "切换失败",
  modalImportTitle: "导入宠物",
  modalImportOk: "导入",
  dropzoneTitle: "将文件夹或 .zip 拖放到此处",
  dropzoneHint: "或点击选择 .zip 文件",
  importFormatHint:
    "文件夹或解压后的目录需包含 pet.json 与 spritesheet.webp（1536×1872）。",
  selectedOne: "已选择：{path}",
  selectedMany: "已选择：{count} 个文件（根目录：{root}）",
  importReplace: "若已存在相同 id 的宠物则覆盖",
};

export function resolvePetLocale(): PetLocale {
  return "zh";
}

export function t(
  key: MessageKey,
  params?: Record<string, string | number>,
): string {
  let text: string = messages[key];
  if (params) {
    for (const [name, value] of Object.entries(params)) {
      text = text.split(`{${name}}`).join(String(value));
    }
  }
  return text;
}
