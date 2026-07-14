import { useCallback, useEffect, useState } from "react";
import { useAppMessage } from "@/hooks/useAppMessage";
import {
  fetchPluginCatalog,
  installPlugin,
  type OfficialPluginCatalogEntry,
} from "@/api/modules/plugin";

interface UseOfficialPluginsOptions {
  onInstalled: () => void;
}

export function useOfficialPlugins({ onInstalled }: UseOfficialPluginsOptions) {
    const { message } = useAppMessage();
  const [loading, setLoading] = useState(true);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [plugins, setPlugins] = useState<OfficialPluginCatalogEntry[]>([]);
  const [installingId, setInstallingId] = useState<string | null>(null);

  const loadCatalog = useCallback(async () => {
    setLoading(true);
    setCatalogError(null);
    try {
      const data = await fetchPluginCatalog();
      if (data.error) {
        setCatalogError(data.error);
        setPlugins([]);
      } else {
        setPlugins(data.plugins ?? []);
      }
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : "加载官方插件列表失败";
      setCatalogError(msg);
      setPlugins([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCatalog();
  }, [loadCatalog]);

  const handleInstall = useCallback(
    async (entry: OfficialPluginCatalogEntry) => {
      setInstallingId(entry.id);
      try {
        const result = await installPlugin(entry.install_url, {
          force: entry.installed || entry.upgrade_available,
        });
        message.success(`${"插件安装成功"}: ${result.name}`);
        onInstalled();
        setTimeout(() => window.location.reload(), 800);
      } catch (err) {
        const msg =
          err instanceof Error ? err.message : "插件安装失败";
        message.error(msg);
      } finally {
        setInstallingId(null);
      }
    },
    [message, onInstalled],
  );

  return {
    loading,
    catalogError,
    plugins,
    installingId,
    loadCatalog,
    handleInstall,
  };
}
