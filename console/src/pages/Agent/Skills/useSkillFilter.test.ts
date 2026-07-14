import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSkillFilter } from "./useSkillFilter";

interface TestSkill {
  name: string;
  description?: string;
}

const mockSkills: TestSkill[] = [
  {
    name: "CodeGen",
    description: "Generates code from prompts",
  },
  {
    name: "Translator",
    description: "Translates between languages",
  },
  {
    name: "Formatter",
    description: "Formats source files",
  },
  {
    name: "Linter",
    description: "Checks code quality",
  },
];

describe("useSkillFilter", () => {
  it("returns all skills when no filter is applied", () => {
    const { result } = renderHook(() => useSkillFilter(mockSkills));
    expect(result.current.filteredSkills).toEqual(mockSkills);
  });

  it("filters by name case-insensitively", () => {
    const { result } = renderHook(() => useSkillFilter(mockSkills));

    act(() => {
      result.current.setSearchQuery("codegen");
    });

    expect(result.current.filteredSkills).toHaveLength(1);
    expect(result.current.filteredSkills[0].name).toBe("CodeGen");
  });

  it("filters by description", () => {
    const { result } = renderHook(() => useSkillFilter(mockSkills));

    act(() => {
      result.current.setSearchQuery("translates");
    });

    expect(result.current.filteredSkills).toHaveLength(1);
    expect(result.current.filteredSkills[0].name).toBe("Translator");
  });

  it("re-filters skills when searchQuery is updated", () => {
    const { result } = renderHook(() => useSkillFilter(mockSkills));

    act(() => {
      result.current.setSearchQuery("formatter");
    });
    expect(result.current.filteredSkills).toHaveLength(1);

    act(() => {
      result.current.setSearchQuery("linter");
    });
    expect(result.current.filteredSkills).toHaveLength(1);
    expect(result.current.filteredSkills[0].name).toBe("Linter");
  });

  it("returns all skills when query is cleared back to empty", () => {
    const { result } = renderHook(() => useSkillFilter(mockSkills));

    act(() => {
      result.current.setSearchQuery("codegen");
    });
    expect(result.current.filteredSkills).toHaveLength(1);

    act(() => {
      result.current.setSearchQuery("");
    });
    expect(result.current.filteredSkills).toEqual(mockSkills);
  });
});
