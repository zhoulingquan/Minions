import { Card } from "@agentscope-ai/design";
import { Line } from "@ant-design/plots";
import type { LineConfig } from "@ant-design/plots";
import styles from "../index.module.less";

interface TokenTypeChartProps {
  chartConfig: LineConfig | null;
}

export function TokenTypeChart({ chartConfig }: TokenTypeChartProps) {

  if (!chartConfig) return null;

  return (
    <Card
      className={styles.chartCard}
      title={
        <span className={styles.chartTitle}>
          {"Token 类型趋势"}
        </span>
      }
    >
      <Line {...chartConfig} />
    </Card>
  );
}
