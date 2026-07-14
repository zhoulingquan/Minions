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

import type { SkillSpec } from "../../../../api/types";
import { SkillCard } from "./SkillCard";

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
    loading,
    danger,
    type,
    size,
    ...props
  }: PropsWithChildren<
    ButtonHTMLAttributes<HTMLButtonElement> & {
      icon?: ReactNode;
      loading?: boolean;
      danger?: boolean;
      type?: string;
      size?: string;
    }
  >) => {
    void loading;
    void danger;
    void type;
    void size;
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
  Switch: ({
    checked,
    onChange,
    ...props
  }: Omit<InputHTMLAttributes<HTMLInputElement>, "onChange"> & {
    onChange?: (checked: boolean) => void;
  }) => (
    <input
      type="checkbox"
      role="switch"
      checked={checked}
      onChange={(event) => onChange?.(event.target.checked)}
      {...props}
    />
  ),
  Tooltip: ({ children }: PropsWithChildren) => <>{children}</>,
}));

const linkedSkill: SkillSpec = {
  name: "demo",
  content: "# demo",
  source: "customized",
  enabled: true,
  channels: ["all"],
  sync_status: "not_synced",
  in_global: true,
  global_hash: "same-hash",
  agent_hash: "same-hash",
};

describe("SkillCard sync action", () => {
  it("shows the sync button before hover and keeps the card click isolated", () => {
    const onSync = vi.fn();
    const onClick = vi.fn();

    const { container } = render(
      <SkillCard
        skill={linkedSkill}
        onClick={onClick}
        onToggleEnabled={vi.fn()}
        onSync={onSync}
      />,
    );

    const syncButton = screen.getByRole("button", {
      name: "link 建立同步",
    });
    expect(syncButton).toBeVisible();

    fireEvent.mouseEnter(container.firstElementChild as Element);
    expect(syncButton).toBeVisible();

    fireEvent.click(syncButton);
    expect(onSync).toHaveBeenCalledTimes(1);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("uses a switch instead of enabled text and the old toggle button", () => {
    const onToggleEnabled = vi.fn();
    const onClick = vi.fn();

    render(
      <SkillCard
        skill={linkedSkill}
        onClick={onClick}
        onToggleEnabled={onToggleEnabled}
      />,
    );

    expect(screen.queryByText("已启用")).not.toBeInTheDocument();
    expect(screen.queryByText("禁用")).not.toBeInTheDocument();

    const enabledSwitch = screen.getByRole("switch", {
      name: "启用技能 demo",
    });
    expect(enabledSwitch).toBeChecked();

    fireEvent.click(enabledSwitch);
    expect(onToggleEnabled).toHaveBeenCalledTimes(1);
    expect(onClick).not.toHaveBeenCalled();
  });
});
