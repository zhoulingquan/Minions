import defaultStyles from "../index.module.less";

interface SkillCategoryProps {
  categories?: string[];
  styles?: Record<string, string>;
}

export function SkillCategoryBadges({
  categories,
  styles = defaultStyles,
}: Pick<SkillCategoryProps, "categories" | "styles">) {
  if (!categories?.length) return null;
  return (
    <>
      {categories.map((cat) => (
        <span key={cat} className={styles.categoryChip}>
          {cat}
        </span>
      ))}
    </>
  );
}
