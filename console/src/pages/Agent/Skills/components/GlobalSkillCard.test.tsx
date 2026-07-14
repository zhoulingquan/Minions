// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import type {
  ButtonHTMLAttributes,
  HTMLAttributes,
  InputHTMLAttributes,
  PropsWithChildren,
  ReactNode,
} from "react";
import { describe, expect, it, vi } from "vitest";

import type { GlobalSkillSpec } from "../../../../api/types";
import { GlobalSkillCard } from "./GlobalSkillCard";

vi.mock("@agentscope-ai/design", () => ({
  Card: ({
    children,
    hoverable,
    ...props
  }: PropsWithChildren<
    HTMLAttributes<HTMLDivElement> & { hoverable?: boolean }
  >) => {
    void hoverable;
    return <div {...props}>{children}</div>;
  },
  Button: ({
    children,
    icon,
    type,
    ...props
  }: PropsWithChildren<
    ButtonHTMLAttributes<HTMLButtonElement> & {
      icon?: ReactNode;
      type?: string;
    }
  >) => {
    void type;
    return (
      <button {...props}>
        {icon}
        {children}
      </button>
    );
  },
  Checkbox: (props: InputHTMLAttributes<HTMLInputElement>) => (
    <input type="checkbox" {...props} />
  ),
  Tooltip: ({ children }: PropsWithChildren) => <>{children}</>,
}));

vi.mock("@/components/SkillVisual", () => ({
  SkillVisual: ({ name }: { name: string }) => <span>{name}</span>,
}));

const skill = (overrides: Partial<GlobalSkillSpec>): GlobalSkillSpec => ({
  name: "demo",
  content: "# demo",
  source: "customized",
  ...overrides,
  protected: overrides.protected ?? false,
});

describe("GlobalSkillCard auto-update action", () => {
  it("preserves explicitly selected targets when disabling auto-update", () => {
    const onToggleAutoUpdate = vi.fn();
    const onEdit = vi.fn();
    const selectedTargets = ["agent-a", "agent-b"];
    const currentSkill = skill({
      auto_update: true,
      auto_update_targets: selectedTargets,
    });

    render(
      <GlobalSkillCard
        skill={currentSkill}
        onEdit={onEdit}
        onToggleAutoUpdate={onToggleAutoUpdate}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "关闭自动同步" }));

    expect(onToggleAutoUpdate).toHaveBeenCalledWith(
      currentSkill,
      false,
      selectedTargets,
    );
    expect(onEdit).not.toHaveBeenCalled();
  });

  it("keeps null as the all-installed-agents target when enabling", () => {
    const onToggleAutoUpdate = vi.fn();
    const currentSkill = skill({
      auto_update: false,
      auto_update_targets: null,
    });

    render(
      <GlobalSkillCard
        skill={currentSkill}
        onToggleAutoUpdate={onToggleAutoUpdate}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "开启自动同步" }));

    expect(onToggleAutoUpdate).toHaveBeenCalledWith(currentSkill, true, null);
  });
});
