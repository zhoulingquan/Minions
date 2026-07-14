import { Dropdown, Button, type MenuProps } from "antd";
import { SparkMoonLine, SparkSunLine } from "@agentscope-ai/icons";
import { SunMoon } from "lucide-react";
import { useTheme, type ThemeMode } from "../../contexts/ThemeContext";
import type { ReactNode } from "react";
import styles from "./index.module.less";

const ICONS: Record<ThemeMode, ReactNode> = {
  light: <SparkSunLine />,
  dark: <SparkMoonLine />,
  system: <SunMoon size="1em" />,
};

export default function ThemeToggleButton() {
  const { themeMode, isDark, setThemeMode } = useTheme();

  const items: MenuProps["items"] = [
    {
      key: "light",
      label: "浅色",
      onClick: () => setThemeMode("light"),
    },
    {
      key: "dark",
      label: "深色",
      onClick: () => setThemeMode("dark"),
    },
    {
      key: "system",
      label: "跟随系统",
      onClick: () => setThemeMode("system"),
    },
  ];

  const icon =
    themeMode === "system" ? ICONS.system : ICONS[isDark ? "dark" : "light"];

  return (
    <Dropdown
      menu={{ items, selectedKeys: [themeMode] }}
      placement="bottomRight"
      overlayClassName={styles.themeDropdown}
    >
      <Button className={styles.toggleBtn} type="text" icon={icon} />
    </Dropdown>
  );
}
