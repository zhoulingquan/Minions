import React from "react";

import { SunMoon } from "lucide-react";
import {
  SparkSunLine,
  SparkMoonLine,
  SparkFullscreenLine,
  SparkExitFullscreenLine,
} from "@agentscope-ai/icons";
import { useTheme, type ThemeMode } from "../contexts/ThemeContext";
import { useSidebarModeStore } from "../stores/sidebarModeStore";
import styles from "./sidebarSettingsPanel.module.less";

interface SidebarSettingsPanelProps {
  onClose?: () => void;
}

export default function SidebarSettingsPanel({
  onClose,
}: SidebarSettingsPanelProps) {
    const { themeMode, setThemeMode } = useTheme();
  const { mode: sidebarMode, toggleMode: toggleSidebarMode } =
    useSidebarModeStore();

  const themeOptions: {
    key: ThemeMode;
    label: string;
    icon: React.ReactNode;
  }[] = [
    {
      key: "light",
      label: "浅色",
      icon: <SparkSunLine size={14} />,
    },
    {
      key: "dark",
      label: "深色",
      icon: <SparkMoonLine size={14} />,
    },
    {
      key: "system",
      label: "跟随系统",
      icon: <SunMoon size={14} />,
    },
  ];

  return (
    <div className={styles.panel}>
      {/* ── Theme ────────────────────────────────────────── */}
      <div className={styles.row}>
        <span className={styles.label}>
          {"主题"}
        </span>
        <div className={styles.options}>
          {themeOptions.map(({ key, label, icon }) => (
            <button
              key={key}
              title={label}
              className={`${styles.optBtn} ${
                themeMode === key ? styles.optBtnActive : ""
              }`}
              onClick={() => setThemeMode(key)}
            >
              {icon}
              <span className={styles.optLabel}>{label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* ── Mode ─────────────────────────────────────────── */}
      <div className={styles.row}>
        <span className={styles.label}>
          {"模式"}
        </span>
        <button
          className={`${styles.optBtn} ${styles.optBtnBlock}`}
          onClick={() => {
            toggleSidebarMode();
            onClose?.();
          }}
        >
          {sidebarMode === "simple" ? (
            <>
              <SparkFullscreenLine size={14} />
              <span className={styles.optLabel}>
                {"完整模式"}
              </span>
            </>
          ) : (
            <>
              <SparkExitFullscreenLine size={14} />
              <span className={styles.optLabel}>
                {"精简模式"}
              </span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
