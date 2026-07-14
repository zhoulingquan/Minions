import { Card } from "@agentscope-ai/design";
import { formatCompact } from "../../../../utils/formatNumber";
import styles from "../index.module.less";

interface SummaryCardsProps {
  totalCalls: number;
  totalPromptTokens: number;
  totalCompletionTokens: number;
  totalTokens: number;
}

export function SummaryCards({
  totalCalls,
  totalPromptTokens,
  totalCompletionTokens,
  totalTokens,
}: SummaryCardsProps) {

  return (
    <div className={styles.summaryCards}>
      <Card className={styles.card}>
        <div className={styles.cardValue}>{formatCompact(totalCalls)}</div>
        <div className={styles.cardLabel}>{"总调用次数"}</div>
      </Card>
      <Card className={styles.card}>
        <div className={styles.cardValue}>
          {formatCompact(totalPromptTokens)}
        </div>
        <div className={styles.cardLabel}>{"输入 Token"}</div>
      </Card>
      <Card className={styles.card}>
        <div className={styles.cardValue}>
          {formatCompact(totalCompletionTokens)}
        </div>
        <div className={styles.cardLabel}>
          {"输出 Token"}
        </div>
      </Card>
      <Card className={styles.card}>
        <div className={styles.cardValue}>{formatCompact(totalTokens)}</div>
        <div className={styles.cardLabel}>{"总 Token"}</div>
      </Card>
    </div>
  );
}
