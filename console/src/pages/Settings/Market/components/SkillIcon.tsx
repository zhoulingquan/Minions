import { useState } from "react";
import styles from "./SkillIcon.module.less";

export const SOURCE_LABELS: Record<string, string> = {
  minions: "Minions",
  clawhub: "ClawHub",
  modelscope: "ModelScope",
  aliyun: "Aliyun",
};

export function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source;
}

const PROVIDER_FALLBACK: Record<string, { letter: string }> = {
  minions: { letter: "Q" },
  clawhub: { letter: "C" },
  modelscope: { letter: "M" },
  aliyun: { letter: "A" },
};

interface SkillIconProps {
  url: string | null | undefined;
  alt: string;
  source: string;
}

export function SkillIcon({ url, alt, source }: SkillIconProps) {
  const [imgFailed, setImgFailed] = useState(false);

  if (url && !imgFailed) {
    return (
      <img
        className={styles.skillIcon}
        src={url}
        alt={alt}
        loading="lazy"
        referrerPolicy="no-referrer"
        onError={() => setImgFailed(true)}
      />
    );
  }

  const fallback = PROVIDER_FALLBACK[source];
  if (fallback) {
    return (
      <div
        className={styles.skillIcon}
        aria-hidden
        style={{ fontWeight: 600 }}
      >
        {fallback.letter}
      </div>
    );
  }

  return (
    <div className={styles.skillIcon} aria-hidden>
      🧩
    </div>
  );
}
