import { Card } from "@agentscope-ai/design";
import { Line } from "@ant-design/plots";
import type { LineConfig } from "@ant-design/plots";
import styles from "../index.module.less";

interface ModelTrendChartProps {
  chartConfig: LineConfig | null;
}

export function ModelTrendChart({ chartConfig }: ModelTrendChartProps) {

  if (!chartConfig) return null;

  return (
    <Card
      className={styles.chartCard}
      title={
        <span className={styles.chartTitle}>{"模型用量趋势"}</span>
      }
    >
      <Line {...chartConfig} />
    </Card>
  );
}
