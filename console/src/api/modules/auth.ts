import { getApiUrl } from "../config";

export interface LoginResponse {
  token: string;
  username: string;
  tenant_id?: string;
  tenant_slug?: string;
  role?: string;
  permissions?: string[];
  message?: string;
}

export interface AuthStatusResponse {
  enabled: boolean;
  has_users: boolean;
  multitenant?: boolean;
}

export interface TenantOption {
  tenant_id: string;
  slug: string;
  name: string;
}

export const authApi = {
  login: async (
    username: string,
    password: string,
    tenantSlug?: string,
  ): Promise<LoginResponse> => {
    const res = await fetch(getApiUrl("/auth/login"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username,
        password,
        ...(tenantSlug ? { tenant_slug: tenantSlug } : {}),
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Login failed");
    }
    return res.json();
  },

  register: async (
    username: string,
    password: string,
    options?: {
      tenantName?: string;
      tenantSlug?: string;
      displayName?: string;
    },
  ): Promise<LoginResponse> => {
    const res = await fetch(getApiUrl("/auth/register"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username,
        password,
        tenant_name: options?.tenantName || "默认企业空间",
        tenant_slug: options?.tenantSlug || "default",
        display_name: options?.displayName || null,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Registration failed");
    }
    return res.json();
  },

  getStatus: async (): Promise<AuthStatusResponse> => {
    const res = await fetch(getApiUrl("/auth/status"));
    if (!res.ok) throw new Error("Failed to check auth status");
    return res.json();
  },

  getTenantOptions: async (
    username: string,
    password: string,
  ): Promise<TenantOption[]> => {
    const res = await fetch(getApiUrl("/auth/tenant-options"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "企业空间读取失败");
    }
    const body = await res.json();
    return body.items || [];
  },

  updateProfile: async (
    currentPassword: string,
    newUsername?: string,
    newPassword?: string,
  ): Promise<LoginResponse> => {
    const token = localStorage.getItem("minions_auth_token") || "";
    const res = await fetch(getApiUrl("/auth/update-profile"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        current_password: currentPassword,
        new_username: newUsername || null,
        new_password: newPassword || null,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Update failed");
    }
    return res.json();
  },

  logout: async (): Promise<void> => {
    const token = localStorage.getItem("minions_auth_token") || "";
    if (!token) return;
    const res = await fetch(getApiUrl("/auth/revoke-token"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({}),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Logout failed");
    }
  },
};
