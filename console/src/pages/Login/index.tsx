import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Alert, Button, Form, Input, Select } from "antd";
import { useAppMessage } from "../../hooks/useAppMessage";
import { LockOutlined, UserOutlined } from "@ant-design/icons";
import { authApi, type TenantOption } from "../../api/modules/auth";
import { tenancyApi } from "../../api/modules/tenancy";
import { setAuthToken } from "../../api/config";
import { useTheme } from "../../contexts/ThemeContext";

export default function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { isDark } = useTheme();
  const [loading, setLoading] = useState(false);
  const [isRegister, setIsRegister] = useState(false);
  const [isInvite, setIsInvite] = useState(false);
  const [hasUsers, setHasUsers] = useState(true);
  const [multitenant, setMultitenant] = useState(false);
  const [tenantOptions, setTenantOptions] = useState<TenantOption[]>([]);
  const { message } = useAppMessage();
  const [form] = Form.useForm();

  useEffect(() => {
    authApi
      .getStatus()
      .then((res) => {
        if (!res.enabled) {
          navigate("/chat", { replace: true });
          return;
        }
        setHasUsers(res.has_users);
        setMultitenant(Boolean(res.multitenant));
        if (!res.has_users) {
          setIsRegister(true);
        }
      })
      .catch(() => {});
  }, [navigate]);

  const onFinish = async (values: {
    username: string;
    password: string;
    tenantName?: string;
    tenantSlug?: string;
    displayName?: string;
    inviteToken?: string;
  }) => {
    setLoading(true);
    try {
      const raw = searchParams.get("redirect") || "/chat";
      const redirect =
        raw.startsWith("/") && !raw.startsWith("//") ? raw : "/chat";

      if (isInvite) {
        const res = await tenancyApi.acceptTenantInvite(
          values.inviteToken || "",
          values.username,
          values.password,
          values.displayName,
        );
        setAuthToken(res.token);
        message.success("已加入企业空间");
        navigate(redirect, { replace: true });
      } else if (isRegister) {
        const res = await authApi.register(values.username, values.password, {
          tenantName: values.tenantName,
          tenantSlug: values.tenantSlug,
          displayName: values.displayName,
        });
        if (res.token) {
          setAuthToken(res.token);
          message.success("注册成功");
          navigate(redirect, { replace: true });
        }
      } else {
        const res = await authApi.login(
          values.username,
          values.password,
          values.tenantSlug,
        );
        if (res.token) {
          setAuthToken(res.token);
          navigate(redirect, { replace: true });
        } else {
          message.info("认证未启用");
          navigate(redirect, { replace: true });
        }
      }
    } catch (err) {
      let errorMsg = "登录失败，请检查您的凭据";

      // Check if it's an Error object and use the backend message directly
      if (
        !isRegister &&
        !isInvite &&
        multitenant &&
        err instanceof Error &&
        err.message.includes("企业空间")
      ) {
        try {
          const options = await authApi.getTenantOptions(
            values.username,
            values.password,
          );
          setTenantOptions(options);
          errorMsg = "这个账户属于多个企业空间，请选择后继续";
        } catch {
          errorMsg = err.message;
        }
      } else if (isInvite) {
        errorMsg =
          err instanceof Error
            ? err.message
            : "加入失败，请核对邀请码和账户信息";
      } else if (err instanceof Error) {
        // Use the backend message directly without complex parsing
        errorMsg = err.message;
      } else if (isRegister) {
        errorMsg = "注册失败";
      }

      message.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        height: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: isDark
          ? "linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%)"
          : "linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)",
      }}
    >
      <div
        style={{
          width: 420,
          maxHeight: "calc(100vh - 40px)",
          overflowY: "auto",
          padding: 32,
          borderRadius: 12,
          background: isDark ? "#1f1f1f" : "#fff",
          boxShadow: isDark
            ? "0 4px 24px rgba(0,0,0,0.4)"
            : "0 4px 24px rgba(0,0,0,0.1)",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <img
            src={isDark ? "/logo-dark.svg" : "/logo-light.svg"}
            alt="Minions"
            style={{ height: 48, marginBottom: 12 }}
          />
          <h2 style={{ margin: 0, fontWeight: 600, fontSize: 20 }}>
            {isRegister
              ? "创建账户"
              : isInvite
                ? "加入企业空间"
                : "登录 Minions"}
          </h2>
          {!hasUsers && (
            <p
              style={{
                margin: "8px 0 0",
                color: isDark ? "rgba(255,255,255,0.45)" : "#666",
                fontSize: 13,
              }}
            >
              {"创建管理员账户以开始使用"}
            </p>
          )}
        </div>

        <Form
          form={form}
          layout="vertical"
          onFinish={onFinish}
          autoComplete="off"
          size="large"
        >
          {isInvite && (
            <Form.Item
              name="inviteToken"
              label="一次性邀请码"
              rules={[{ required: true, message: "请粘贴邀请码" }]}
            >
              <Input.TextArea
                autoSize={{ minRows: 2, maxRows: 4 }}
                placeholder="粘贴企业管理员发给你的邀请码"
                autoFocus
              />
            </Form.Item>
          )}

          <Form.Item
            name="username"
            rules={[{ required: true, message: "请输入用户名" }]}
          >
            <Input
              prefix={
                <UserOutlined
                  style={{
                    color: isDark ? "rgba(255,255,255,0.45)" : undefined,
                  }}
                />
              }
              placeholder={"用户名"}
              autoFocus={!isInvite}
            />
          </Form.Item>

          {isInvite && (
            <Form.Item name="displayName" label="你的姓名（首次加入时使用）">
              <Input placeholder="例如：张三" />
            </Form.Item>
          )}

          {isRegister && multitenant && (
            <>
              <Form.Item
                name="displayName"
                rules={[{ required: true, message: "请输入你的姓名" }]}
              >
                <Input placeholder="你的姓名" />
              </Form.Item>
              <Form.Item
                name="tenantName"
                rules={[{ required: true, message: "请输入企业空间名称" }]}
              >
                <Input placeholder="企业或团队名称" />
              </Form.Item>
              <Form.Item
                name="tenantSlug"
                extra="用于登录和系统识别，例如 acme；创建后仍可显示中文名称。"
                rules={[
                  { required: true, message: "请输入空间代号" },
                  {
                    pattern: /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/,
                    message: "请使用小写字母、数字和短横线",
                  },
                ]}
              >
                <Input placeholder="企业空间代号，例如 acme" />
              </Form.Item>
            </>
          )}

          <Form.Item
            name="password"
            rules={[
              { required: true, message: "请输入密码" },
              ...(isInvite
                ? [{ min: 8, message: "密码至少需要 8 位" }]
                : []),
            ]}
          >
            <Input.Password
              prefix={
                <LockOutlined
                  style={{
                    color: isDark ? "rgba(255,255,255,0.45)" : undefined,
                  }}
                />
              }
              placeholder={"密码"}
            />
          </Form.Item>

          {!isRegister && !isInvite && tenantOptions.length > 1 && (
            <Form.Item
              name="tenantSlug"
              rules={[{ required: true, message: "请选择企业空间" }]}
            >
              <Select
                placeholder="选择企业空间"
                options={tenantOptions.map((item) => ({
                  value: item.slug,
                  label: item.name,
                }))}
              />
            </Form.Item>
          )}

          {multitenant && (
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
              message={
                isRegister
                  ? "首个账户将成为企业空间所有者"
                  : isInvite
                    ? "已有账户请输入原密码；新账户请设置至少 8 位密码"
                    : "登录后只会进入你选择的企业空间"
              }
            />
          )}

          <Form.Item style={{ marginBottom: 0, marginTop: 8 }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              style={{ height: 44, borderRadius: 8, fontWeight: 500 }}
            >
              {isRegister ? "注册" : isInvite ? "确认加入" : "登录"}
            </Button>
          </Form.Item>

          {multitenant && hasUsers && !isRegister && (
            <div style={{ textAlign: "center", marginTop: 14 }}>
              <Button
                type="link"
                onClick={() => {
                  setIsInvite((value) => !value);
                  setTenantOptions([]);
                  form.resetFields();
                }}
              >
                {isInvite ? "返回账户登录" : "我收到了企业邀请码"}
              </Button>
            </div>
          )}
        </Form>
      </div>
    </div>
  );
}
