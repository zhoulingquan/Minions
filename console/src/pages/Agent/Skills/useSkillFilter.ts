import { useMemo, useState } from "react";

interface Filterable {
  name: string;
  description?: string;
}

export function useSkillFilter<T extends Filterable>(skills: T[]) {
  const [searchQuery, setSearchQuery] = useState("");

  const filteredSkills = useMemo(() => {
    const q = searchQuery.toLowerCase();
    return skills.filter((skill) => {
      return (
        !q ||
        skill.name.toLowerCase().includes(q) ||
        (skill.description || "").toLowerCase().includes(q)
      );
    });
  }, [skills, searchQuery]);

  return {
    searchQuery,
    setSearchQuery,
    filteredSkills,
  };
}
