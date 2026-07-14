// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import type { ButtonHTMLAttributes, PropsWithChildren, ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { GlobalSkillToolbarActions } from "./GlobalSkillToolbarActions";

vi.mock("@agentscope-ai/design", () => ({
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
  Dropdown: ({
    children,
    menu,
  }: PropsWithChildren<{
    menu: {
      items: Array<{
        key: string;
        label: string;
        onClick?: () => void;
      }>;
    };
  }>) => (
    <div>
      {children}
      {menu.items.map((item) => (
        <button key={item.key} onClick={item.onClick}>
          {item.label}
        </button>
      ))}
    </div>
  ),
}));

vi.mock("antd", () => ({
  Badge: ({ children, dot }: PropsWithChildren<{ dot?: boolean }>) => (
    <div data-unseen={dot ? "true" : "false"}>{children}</div>
  ),
}));

describe("GlobalSkillToolbarActions", () => {
  it("puts add, batch, and built-in management in more actions", () => {
    const onAddSkill = vi.fn();
    const onStartBatch = vi.fn();
    const onManageBuiltins = vi.fn();

    render(
      <GlobalSkillToolbarActions
        hasUpdates={false}
        updateCount={0}
        hasUnseenUpdate={false}
        onAddSkill={onAddSkill}
        onStartBatch={onStartBatch}
        onManageBuiltins={onManageBuiltins}
      />,
    );

    expect(screen.queryByText("更新内置技能")).not.toBeInTheDocument();
    expect(screen.getByText("更多操作")).toBeVisible();

    fireEvent.click(screen.getByText("添加新技能"));
    fireEvent.click(screen.getByText("批量操作"));
    fireEvent.click(screen.getByText("管理内置技能"));

    expect(onAddSkill).toHaveBeenCalledTimes(1);
    expect(onStartBatch).toHaveBeenCalledTimes(1);
    expect(onManageBuiltins).toHaveBeenCalledTimes(1);
  });

  it("shows an update action with the detected change count", () => {
    const onManageBuiltins = vi.fn();

    render(
      <GlobalSkillToolbarActions
        hasUpdates
        updateCount={3}
        hasUnseenUpdate
        onAddSkill={vi.fn()}
        onStartBatch={vi.fn()}
        onManageBuiltins={onManageBuiltins}
      />,
    );

    const updateAction = screen.getByText("更新内置技能（3）");
    expect(updateAction).toBeVisible();
    expect(updateAction.closest("[data-unseen='true']")).not.toBeNull();

    fireEvent.click(updateAction);
    expect(onManageBuiltins).toHaveBeenCalledTimes(1);
  });
});
