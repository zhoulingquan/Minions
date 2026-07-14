import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../request", () => ({ request: vi.fn() }));

import { request } from "../request";
import { tenancyApi } from "./tenancy";

describe("tenancyApi", () => {
  beforeEach(() => vi.mocked(request).mockResolvedValue(undefined));
  afterEach(() => vi.clearAllMocks());

  it("loads the current enterprise space", async () => {
    await tenancyApi.getTenantOverview();
    expect(request).toHaveBeenCalledWith("/tenancy/overview");
  });

  it("creates and switches enterprise spaces without client tenant claims", async () => {
    await tenancyApi.createTenantSpace("第二企业", "second-company");
    expect(request).toHaveBeenCalledWith("/tenancy/spaces", {
      method: "POST",
      body: JSON.stringify({ name: "第二企业", slug: "second-company" }),
    });

    await tenancyApi.switchTenantSpace("second-company");
    expect(request).toHaveBeenCalledWith(
      "/tenancy/spaces/second-company/switch",
      { method: "POST" },
    );
  });

  it("accepts an invite through the public one-time token flow", async () => {
    await tenancyApi.acceptTenantInvite(
      "one-time-token",
      "staff",
      "correct-horse",
      "Staff",
    );
    expect(request).toHaveBeenCalledWith("/tenancy/invites/accept", {
      method: "POST",
      body: JSON.stringify({
        invite_token: "one-time-token",
        username: "staff",
        password: "correct-horse",
        display_name: "Staff",
      }),
    });
  });

  it("invites a member without putting tenant identity in the body", async () => {
    await tenancyApi.inviteTenantMember("staff", "member");
    expect(request).toHaveBeenCalledWith("/tenancy/invites", {
      method: "POST",
      body: JSON.stringify({ username: "staff", role: "member" }),
    });
  });

  it("updates only role and membership status", async () => {
    await tenancyApi.updateTenantMember("user-1", {
      role: "operator",
      status: "active",
    });
    expect(request).toHaveBeenCalledWith("/tenancy/members/user-1", {
      method: "PATCH",
      body: JSON.stringify({ role: "operator", status: "active" }),
    });
  });

  it("revokes a pending invitation by server-side id", async () => {
    await tenancyApi.revokeTenantInvite("invite-1");
    expect(request).toHaveBeenCalledWith("/tenancy/invites/invite-1", {
      method: "DELETE",
    });
  });
});
