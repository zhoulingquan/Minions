import { describe, expect, it } from "vitest";
import { formatAgentList } from "./utils";

describe("formatAgentList", () => {
  it("renders agent rows from tool result text blocks", () => {
    const agents = [
      {
        name: "Coder",
        id: "agent-1",
        description: "Coding agent",
        status: "ready",
      },
    ];
    const rawToolResult = JSON.stringify([
      {
        type: "text",
        text: JSON.stringify(agents),
      },
    ]);

    const formattedResult = formatAgentList(rawToolResult);

    expect(formattedResult).toContain(
      "| Coder | `agent-1` | Coding agent | ready |",
    );
    expect(formattedResult).not.toContain("|  | `` |  |  |");
  });
});
