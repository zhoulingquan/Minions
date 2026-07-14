import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../api/modules/tenancy", () => ({
  tenancyApi: { getTenantOverview: vi.fn() },
}));

import { tenancyApi } from "../api/modules/tenancy";
import type { TenantOverview } from "../api/types/tenancy";
import { useTenantStore } from "./tenantStore";

const overview = {
  tenant: { tenant_id: "tenant-1", slug: "acme", name: "Acme" },
  membership: { role: "owner" },
} as TenantOverview;

describe("tenantStore", () => {
  beforeEach(() => {
    useTenantStore.setState({ overview: null, loading: false, error: null });
  });
  afterEach(() => vi.clearAllMocks());

  it("loads the attested current enterprise space", async () => {
    vi.mocked(tenancyApi.getTenantOverview).mockResolvedValue(overview);
    await useTenantStore.getState().refresh();
    expect(useTenantStore.getState().overview).toEqual(overview);
    expect(useTenantStore.getState().error).toBeNull();
  });

  it("clears enterprise identity on logout", () => {
    useTenantStore.setState({ overview });
    useTenantStore.getState().clear();
    expect(useTenantStore.getState().overview).toBeNull();
  });
});
