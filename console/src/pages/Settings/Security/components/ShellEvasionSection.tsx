import { Switch } from "@agentscope-ai/design";
import styles from "../index.module.less";

const SHELL_EVASION_LABELS: Record<string, { name: string; description: string }> = {
  command_substitution: { name: "命令替换", description: "检测 $()、反引号、进程替换等命令替换模式" },
  obfuscated_flags: { name: "混淆标志", description: "检测 ANSI-C 引号、本地化引号和空引号标志混淆" },
  backslash_escaped_whitespace: { name: "反斜杠转义空白", description: "检测可能改变命令解析的反斜杠转义空格/制表符" },
  backslash_escaped_operators: { name: "反斜杠转义操作符", description: "检测 Shell 操作符 (;|&<>) 前的反斜杠，可隐藏命令结构" },
  newlines: { name: "隐藏换行符", description: "检测可能分隔隐藏命令的换行符和回车符" },
  comment_quote_desync: { name: "注释引号失同步", description: "检测 # 注释中的引号字符，可导致引号追踪失同步" },
  quoted_newline: { name: "引号内换行", description: "检测引号字符串中的换行符后跟 # 行，可隐藏参数" },
};

/**
 * The 7 shell evasion check types defined in
 * `shell_evasion_guardian.py` → `_CHECKS`.
 */
const SHELL_EVASION_CHECK_KEYS = [
  "command_substitution",
  "obfuscated_flags",
  "backslash_escaped_whitespace",
  "backslash_escaped_operators",
  "newlines",
  "comment_quote_desync",
  "quoted_newline",
] as const;

interface ShellEvasionSectionProps {
  checks: Record<string, boolean>;
  onToggle: (checkName: string, checked: boolean) => void;
  disabled?: boolean;
}

export function ShellEvasionSection({
  checks,
  onToggle,
  disabled = false,
}: ShellEvasionSectionProps) {

  return (
    <div className={styles.shellEvasionSection}>
      <div className={styles.shellEvasionGrid}>
        {SHELL_EVASION_CHECK_KEYS.map((checkKey) => {
          const isEnabled = checks[checkKey] === true;
          const labels = SHELL_EVASION_LABELS[checkKey];
          const displayName =
            labels?.name ||
            checkKey
              .replace(/_/g, " ")
              .replace(/\b\w/g, (c) => c.toUpperCase());
          const displayDesc = labels?.description ?? "";

          return (
            <div key={checkKey} className={styles.shellEvasionItem}>
              <div className={styles.shellEvasionItemInfo}>
                <span className={styles.shellEvasionItemName}>
                  {displayName}
                </span>
                {displayDesc && (
                  <span className={styles.shellEvasionItemDesc}>
                    {displayDesc}
                  </span>
                )}
              </div>
              <Switch
                size="small"
                checked={isEnabled}
                onChange={(val) => onToggle(checkKey, val)}
                disabled={disabled}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
