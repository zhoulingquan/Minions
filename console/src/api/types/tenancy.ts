export type TenantRole = "owner" | "admin" | "operator" | "member" | "viewer";
export type MembershipStatus = "active" | "disabled";

export interface TenantSpace {
  tenant_id: string;
  slug: string;
  name: string;
  role: TenantRole;
  current: boolean;
}

export interface TenantSessionResponse {
  token: string;
  username: string;
  tenant_id: string;
  role: TenantRole;
  permissions: string[];
}

export interface TenantOverview {
  tenant: {
    tenant_id: string;
    slug: string;
    name: string;
    status: "active" | "suspended" | "archived";
    created_at: string;
    updated_at: string;
  };
  membership: {
    tenant_id: string;
    user_id: string;
    role: TenantRole;
    status: MembershipStatus;
  };
  quota: {
    max_members: number;
    max_agents: number;
    max_concurrent_tasks: number;
    max_storage_mb: number;
  };
  usage: {
    members: number;
    agents: number;
    concurrent_tasks: number;
    storage_mb: number;
  };
  permissions: string[];
}

export interface TenantMember {
  tenant_id: string;
  user_id: string;
  username: string;
  display_name: string;
  role: TenantRole;
  status: MembershipStatus;
  user_status: "active" | "disabled";
  created_at: string;
  updated_at: string;
}

export interface TenantInvite {
  invite_id: string;
  tenant_id: string;
  username: string;
  role: TenantRole;
  status: "pending" | "accepted" | "revoked" | "expired";
  expires_at: string;
  created_at: string;
  invite_token?: string;
}

export interface TenantAgentGrant {
  agent_id: string;
  tenant_id: string;
  owner_user_id: string;
  access: "private" | "tenant";
  status: "active" | "disabled" | "archived";
  created_at: string;
  updated_at: string;
}

export interface TenantAuditEvent {
  event_id: string;
  actor_user_id?: string;
  action: string;
  resource_type: string;
  resource_id: string;
  outcome: string;
  metadata: Record<string, unknown>;
  created_at: string;
}
