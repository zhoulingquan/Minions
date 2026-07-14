import { useState, useCallback } from "react";
import { Modal } from "antd";
import { useRequest } from "ahooks";
import { useAppMessage } from "@/hooks/useAppMessage";
import { fetchPlugins, uninstallPlugin } from "@/api/modules/plugin";
import type { PluginInfo } from "@/api/modules/plugin";

export function usePluginManager() {
    const { message } = useAppMessage();
  const [uninstallingId, setUninstallingId] = useState<string | null>(null);

  const {
    data: plugins,
    loading,
    refresh,
  } = useRequest(fetchPlugins, {
    onError: () => message.error("加载插件列表失败"),
  });

  const handleUninstall = useCallback(
    (plugin: PluginInfo) => {
      Modal.confirm({
        title: "确认卸载",
        content: `确定要卸载插件 "${plugin.name}"？操作无法撤销。部分插件可能需要重启应用才能完全移除。`,
        okType: "danger",
        okText: "卸载",
        cancelText: "取消",
        onOk: async () => {
          setUninstallingId(plugin.id);
          try {
            await uninstallPlugin(plugin.id);
            message.success("插件卸载成功");
            refresh();
            setTimeout(() => window.location.reload(), 800);
          } catch (err) {
            const msg =
              err instanceof Error
                ? err.message
                : "插件卸载失败";
            message.error(msg);
          } finally {
            setUninstallingId(null);
          }
        },
      });
    },
    [message, refresh],
  );

  return {
    plugins,
    loading,
    refresh,
    uninstallingId,
    handleUninstall,
  };
}
