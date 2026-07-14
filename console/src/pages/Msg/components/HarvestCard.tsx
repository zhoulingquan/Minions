import { Card, Button, Badge, Progress } from "antd";
import { Zap, BookOpen, Settings, Clock, Trophy } from "lucide-react";
import type { HarvestInstance } from "../types";
import { useHarvestCountdown } from "../hooks/useHarvestCountdown";
import styles from "./HarvestCard.module.less";

interface HarvestCardProps {
  harvest: HarvestInstance;
  onTrigger: (id: string) => void;
  onViewAll: (id: string) => void;
  onSettings: (id: string) => void;
}

export function HarvestCard({
  harvest,
  onTrigger,
  onViewAll,
  onSettings,
}: HarvestCardProps) {
    const countdown = useHarvestCountdown(harvest.schedule.nextRun);
  const timeText = countdown.isOverdue
    ? "已就绪"
    : `${String(countdown.hours).padStart(2, "0")}:${String(
        countdown.minutes,
      ).padStart(2, "0")}:${String(countdown.seconds).padStart(2, "0")}`;

  return (
    <Card
      className={`${styles.harvestCard} ${
        countdown.isOverdue ? styles.harvestCardReady : ""
      }`}
      hoverable
      bodyStyle={{ padding: 14 }}
    >
      <div className={styles.cardHeader}>
        <div className={styles.titleRow}>
          <span className={styles.emoji}>{harvest.emoji}</span>
          <h3 className={styles.title}>{harvest.name}</h3>
        </div>
        <Badge
          status={harvest.status === "active" ? "processing" : "default"}
          text={harvest.status}
        />
      </div>
      <div className={styles.cardBody}>
        <div className={styles.countdownSection}>
          <Progress
            type="circle"
            size={90}
            percent={Math.round(countdown.percentage)}
            format={() => timeText}
            strokeColor={countdown.isOverdue ? "#FFD700" : "#FF7F16"}
          />
          <div className={styles.countdownInfo}>
            <div className={styles.statusText}>
              <Clock size={14} />{" "}
              {countdown.isOverdue
                ? "可立即收获"
                : "生成中"}
            </div>
          </div>
        </div>
        <div className={styles.statsSection}>
          <div className={styles.statItem}>
            <Zap size={14} />
            <span>
              {`已生成 ${harvest.stats.totalGenerated} 次`}
            </span>
          </div>
          <div className={styles.statItem}>
            <Trophy size={14} />
            <span>
              {`成功率 ${harvest.stats.successRate}%`}
            </span>
          </div>
        </div>
      </div>
      <div className={styles.cardActions}>
        <Button
          type="primary"
          icon={<Zap size={15} />}
          onClick={() => onTrigger(harvest.id)}
        >
          {"立即收获"}
        </Button>
        <Button
          icon={<BookOpen size={15} />}
          onClick={() => onViewAll(harvest.id)}
        >
          {"查看全部"}
        </Button>
        <Button
          icon={<Settings size={15} />}
          onClick={() => onSettings(harvest.id)}
        />
      </div>
    </Card>
  );
}
