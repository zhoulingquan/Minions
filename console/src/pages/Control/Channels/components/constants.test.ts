import { describe, it, expect } from "vitest";
import { CHANNEL_LABELS, getChannelLabel } from "./constants";

describe("CHANNEL_LABELS", () => {
  it("contains known channels: dingtalk, feishu, console", () => {
    expect(CHANNEL_LABELS["dingtalk"]).toBe("DingTalk");
    expect(CHANNEL_LABELS["feishu"]).toBe("Feishu");
    expect(CHANNEL_LABELS["console"]).toBe("Console");
  });
});

describe("getChannelLabel", () => {
  it("returns the English label for a known channel", () => {
    expect(getChannelLabel("dingtalk")).toBe("DingTalk");
  });

  it("formats snake_case custom channel key to Title Case", () => {
    expect(getChannelLabel("custom_channel")).toBe("Custom Channel");
  });

  it("formats kebab-case custom channel key to Title Case", () => {
    expect(getChannelLabel("my-bot")).toBe("My Bot");
  });
});
