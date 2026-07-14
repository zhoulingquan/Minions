import { useMemo, useState } from "react";
import { Button, Modal, Select } from "@agentscope-ai/design";
import type { CronTemplateCategory, CronTemplateDefinition } from "./templates";
import { CRON_TEMPLATES } from "./templates";
import styles from "../index.module.less";

const TEMPLATE_I18N: Record<string, { title: string; description: string; frequency: string }> = {
  "cronJobs.templates.dailyTechNewsBrief": { title: "工作日科技新闻早报", description: "工作日 9:30 自动整理当日热门科技资讯并推送简报。", frequency: "工作日 09:30（30 9 * * 1-5）" },
  "cronJobs.templates.weekendRelaxationReminder": { title: "周末电影推荐", description: "周末上午推送近期热门电影推荐。", frequency: "周末 10:00（0 10 * * 6,0）" },
  "cronJobs.templates.pomodoroBreakReminder": { title: "休息提醒", description: "工作时段每 25 分钟提醒起身喝水或远眺，减少疲劳。", frequency: "工作日 9:00-17:59 每 25 分钟（*/25 9-17 * * 1-5）" },
  "cronJobs.templates.petCareReminder": { title: "宠物驱虫/疫苗提醒", description: "每月 15 日晚提醒给宠物做体外驱虫。", frequency: "每月 15 日 20:00（0 20 15 * *）" },
  "cronJobs.templates.onceTextBirthdayReminder": { title: "生日提醒", description: "提醒xx于1月1日过生日。", frequency: "执行时间：2026年1月1日 09:00" },
  "cronJobs.templates.onceAgentBusinessTripPrep": { title: "出差前天气与行程准备", description: "查询目的地天气并给出行程准备建议。", frequency: "执行时间：2026年1月1日 20:00" },
  "cronJobs.templates.repeatCountTextMedicineReminder": { title: "吃药提醒（14次）", description: "提醒按时吃药，本疗程共14次。", frequency: "首次执行：2026年1月1日 09:00｜每1天一次｜限定14次" },
  "cronJobs.templates.repeatCountAgentDietPlan": { title: "14天饮食计划", description: "连续14天生成并发送当日饮食建议。", frequency: "首次执行：2026年1月1日 08:00｜每1天一次｜限定14次" },
  "cronJobs.templates.repeatUntilTextWeeklyMeeting": { title: "两个月周会提醒", description: "每周提醒参加周会，持续到设定截止时间。", frequency: "首次执行：2026年1月2日 08:45｜每7天一次｜截止到2026年3月1日" },
  "cronJobs.templates.repeatUntilAgentWeeklySummary": { title: "周会前工作总结", description: "每次周会前基于最近一周 memory 生成工作总结。", frequency: "首次执行：2026年1月2日 08:30｜每7天一次｜截止到2026年3月1日" },
};

function resolveI18nKey(key: string, field: "title" | "description" | "frequency"): string {
  const prefix = key.replace(/\.(title|description|frequency)$/, "");
  return TEMPLATE_I18N[prefix]?.[field] ?? key;
}

interface TemplatePickerModalProps {
  open: boolean;
  timezone: string;
  onCancel: () => void;
  onUseTemplate: (templateValues: Record<string, unknown>) => void;
}

export function TemplatePickerModal({
  open,
  timezone,
  onCancel,
  onUseTemplate,
}: TemplatePickerModalProps) {
    const [category, setCategory] = useState<CronTemplateCategory>("cron");

  const filteredTemplates = useMemo(
    () => CRON_TEMPLATES.filter((template) => template.category === category),
    [category],
  );

  const categoryOptions = [
    {
      label: "循环任务",
      value: "cron",
    },
    {
      label: "日程任务",
      value: "once",
    },
  ];

  const handleUseTemplate = (template: CronTemplateDefinition) => {
    const templateValues = template.toFormValues(timezone);
    onUseTemplate({
      ...templateValues,
      name: resolveI18nKey(template.titleKey, "title"),
      text:
        templateValues.task_type === "agent"
          ? ""
          : (templateValues.text as string) ||
            (resolveI18nKey(template.descriptionKey, "description") as string),
    });
  };

  return (
    <Modal
      visible={open}
      title={"选择定时任务模板"}
      footer={null}
      width={860}
      onCancel={onCancel}
    >
      <div className={styles.templateModalHeader}>
        <div className={styles.templateModalDesc}>
          {"先选内置模板，再在抽屉里微调关键参数后保存。"}
        </div>
        <Select<CronTemplateCategory>
          value={category}
          options={categoryOptions}
          style={{ width: 220 }}
          onChange={setCategory}
        />
      </div>
      <div className={styles.templateGrid}>
        {filteredTemplates.map((template) => (
          <div key={template.id} className={styles.templateCard}>
            <div className={styles.templateTitle}>{resolveI18nKey(template.titleKey, "title")}</div>
            <div className={styles.templateDesc}>
              {resolveI18nKey(template.descriptionKey, "description")}
            </div>
            <div className={styles.templateMeta}>
              {resolveI18nKey(template.frequencyKey, "frequency")}
            </div>
            <div className={styles.templateActions}>
              <Button
                type="primary"
                onClick={() => handleUseTemplate(template)}
              >
                {"使用模板"}
              </Button>
            </div>
          </div>
        ))}
      </div>
    </Modal>
  );
}
