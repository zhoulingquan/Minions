import { request } from "../request";
import type {
  MembershipStatus,
  TenantAgentGrant,
  TenantAuditEvent,
  TenantInvite,
  TenantMember,
  TenantOverview,
  TenantRole,
  TenantSessionResponse,
  TenantSpace,
} from "../types/tenancy";

export const tenancyApi = {
  getTenantOverview: () => request<TenantOverview>("/tenancy/overview"),
  listTenantSpaces: () =>
    request<{ items: TenantSpace[] }>("/tenancy/spaces"),
  createTenantSpace: (name: string, slug: string) =>
    request<TenantSessionResponse>("/tenancy/spaces", {
      method: "POST",
      body: JSON.stringify({ name, slug }),
    }),
  switchTenantSpace: (slug: string) =>
    request<TenantSessionResponse>(
      `/tenancy/spaces/${encodeURIComponent(slug)}/switch`,
      { method: "POST" },
    ),
  listTenantMembers: () =>
    request<{ items: TenantMember[] }>("/tenancy/members"),
  updateTenantMember: (
    userId: string,
    update: { role?: TenantRole; status?: MembershipStatus },
  ) =>
    request<TenantMember>(`/tenancy/members/${userId}`, {
      method: "PATCH",
      body: JSON.stringify(update),
    }),
  inviteTenantMember: (username: string, role: TenantRole) =>
    request<TenantInvite>("/tenancy/invites", {
      method: "POST",
      body: JSON.stringify({ username, role }),
    }),
  listTenantInvites: () =>
    request<{ items: TenantInvite[] }>("/tenancy/invites"),
  revokeTenantInvite: (inviteId: string) =>
    request<{ success: boolean }>(
      `/tenancy/invites/${encodeURIComponent(inviteId)}`,
      { method: "DELETE" },
    ),
  acceptTenantInvite: (
    inviteToken: string,
    username: string,
    password: string,
    displayName?: string,
  ) =>
    request<TenantSessionResponse>("/tenancy/invites/accept", {
      method: "POST",
      body: JSON.stringify({
        invite_token: inviteToken,
        username,
        password,
        display_name: displayName || null,
      }),
    }),
  listTenantAgents: () =>
    request<{ items: TenantAgentGrant[] }>("/tenancy/agents"),
  listTenantAudit: (limit = 100) =>
    request<{ items: TenantAuditEvent[] }>(`/tenancy/audit?limit=${limit}`),
};
