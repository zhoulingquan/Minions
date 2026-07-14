import {
  Drawer,
  Form,
  Input,
  InputNumber,
  Switch,
  Button,
  Select,
} from "@agentscope-ai/design";
import { useAppMessage } from "../../../../hooks/useAppMessage";
import { Alert, ConfigProvider } from "antd";
import { LinkOutlined } from "@ant-design/icons";
import { useEffect } from "react";
import type { FormInstance } from "antd";
import { getChannelLabel, type ChannelKey } from "./constants";
import { QrcodeAuthBlock } from "./QrcodeAuthBlock";
import type { ChannelSchema } from "../../../../api/modules/channel";
import styles from "../index.module.less";
import { useAgentStore } from "../../../../stores/agentStore";
import { openExternalLink } from "../../../../utils/openExternalLink";

const CHANNELS_WITH_ACCESS_CONTROL: ChannelKey[] = [
  "telegram",
  "dingtalk",
  "discord",
  "feishu",
  "wecom",
  "mattermost",
  "matrix",
  "wechat",
  "imessage",
  "onebot",
  "qq",
  "mqtt",
  "xiaoyi",
  "yuanbao",
  "slack",
];

// Doc EN URLs per channel (anchors on https://minions.agentscope.io/docs/channels)
const CHANNEL_DOC_EN_URLS: Partial<Record<ChannelKey, string>> = {
  dingtalk:
    "https://minions.agentscope.io/docs/channels/?lang=en#DingTalk-recommended",
  feishu: "https://minions.agentscope.io/docs/channels/?lang=en#Feishu-Lark",
  imessage:
    "https://minions.agentscope.io/docs/channels/?lang=en#iMessage-macOS-only",
  discord: "https://minions.agentscope.io/docs/channels/?lang=en#Discord",
  qq: "https://minions.agentscope.io/docs/channels/?lang=en#QQ",
  telegram: "https://minions.agentscope.io/docs/channels/?lang=en#Telegram",
  mqtt: "https://minions.agentscope.io/docs/channels/?lang=en#MQTT",
  mattermost: "https://minions.agentscope.io/docs/channels/?lang=en#Mattermost",
  matrix: "https://minions.agentscope.io/docs/channels/?lang=en#Matrix",
  sip: "https://minions.agentscope.io/docs/channels/?lang=en#SIP",
  wecom:
    "https://minions.agentscope.io/docs/channels/?lang=en#WeCom-WeChat-Work",
  wechat:
    "https://minions.agentscope.io/docs/channels/?lang=en#WeChat-Personal-iLink",
  xiaoyi:
    "https://developer.huawei.com/consumer/cn/doc/service/openclaw-0000002518410344",
  yuanbao: "https://minions.agentscope.io/docs/channels/?lang=en#Yuanbao",
  onebot:
    "https://minions.agentscope.io/docs/channels/?lang=en#OneBot-v11-NapCat--QQ-full-protocol",
  slack: "https://minions.agentscope.io/docs/channels/?lang=en#Slack",
};

// Doc ZH URLs per channel (anchors on https://minions.agentscope.io/docs/channels)
const CHANNEL_DOC_ZH_URLS: Partial<Record<ChannelKey, string>> = {
  dingtalk: "https://minions.agentscope.io/docs/channels/?lang=zh#钉钉推荐",
  feishu: "https://minions.agentscope.io/docs/channels/?lang=zh#飞书",
  imessage:
    "https://minions.agentscope.io/docs/channels/?lang=zh#iMessage仅-macOS",
  discord: "https://minions.agentscope.io/docs/channels/?lang=zh#Discord",
  qq: "https://minions.agentscope.io/docs/channels/?lang=zh#QQ",
  telegram: "https://minions.agentscope.io/docs/channels/?lang=zh#Telegram",
  mqtt: "https://minions.agentscope.io/docs/channels/?lang=zh#MQTT",
  mattermost: "https://minions.agentscope.io/docs/channels/?lang=zh#Mattermost",
  matrix: "https://minions.agentscope.io/docs/channels/?lang=zh#Matrix",
  sip: "https://minions.agentscope.io/docs/channels/?lang=zh#SIP",
  wecom: "https://minions.agentscope.io/docs/channels/?lang=zh#企业微信",
  wechat: "https://minions.agentscope.io/docs/channels/?lang=zh#微信个人iLink",
  xiaoyi:
    "https://developer.huawei.com/consumer/cn/doc/service/openclaw-0000002518410344",
  yuanbao:
    "https://minions.agentscope.io/docs/channels/?lang=zh#腾讯元宝Yuanbao",
  onebot:
    "https://minions.agentscope.io/docs/channels/?lang=zh#OneBot-v11NapCat--QQ-完整协议",
  slack: "https://minions.agentscope.io/docs/channels/?lang=zh#Slack",
};

const TWILIO_CONSOLE_URL = "https://console.twilio.com";

const BASE_FIELDS = [
  "enabled",
  "bot_prefix",
  "filter_tool_messages",
  "filter_thinking",
  "isBuiltin",
];

interface ChannelDrawerProps {
  open: boolean;
  activeKey: ChannelKey | null;
  activeLabel: string;
  form: FormInstance<Record<string, unknown>>;
  saving: boolean;
  initialValues: Record<string, unknown> | undefined;
  isBuiltin: boolean;
  channelSchema?: ChannelSchema;
  onClose: () => void;
  onSubmit: (values: Record<string, unknown>) => void;
}

export function ChannelDrawer({
  open,
  activeKey,
  activeLabel,
  form,
  saving,
  initialValues,
  isBuiltin,
  channelSchema,
  onClose,
  onSubmit,
}: ChannelDrawerProps) {
    const { selectedAgent, agents } = useAgentStore();
  const currentAgent = agents.find((a) => a.id === selectedAgent);
  const defaultMediaDir = currentAgent?.workspace_dir
    ? `${currentAgent.workspace_dir}/media`
    : "~/.minions/media";
  const currentLang = "zh";
  const label = activeKey ? getChannelLabel(activeKey) : activeLabel;
  const { message } = useAppMessage();
  const matrixAuthMethod = Form.useWatch("auth_method", form);
  const isMatrixPasswordAuth = matrixAuthMethod === "password";
  const feishuDomain = (Form.useWatch("domain", form) as string) || "feishu";

  // Parent calls form.setFieldsValue() before the Form mounts, which wins over
  // initialValues. Re-apply auth_method after open so the dropdown is correct.
  useEffect(() => {
    if (!open || activeKey !== "matrix") return;
    const pw = initialValues?.password;
    if (typeof pw === "string" && pw.trim().length > 0) {
      form.setFieldsValue({ auth_method: "password" });
    }
  }, [open, activeKey, initialValues, form]);

  // ── Access control fields (shared across multiple channels) ──────────────

  const renderAccessControlFields = () => (
    <>
      <Form.Item
        name="access_control_dm"
        label={"私聊访问控制"}
        valuePropName="checked"
        tooltip={"开启后，只有白名单用户可以通过私聊与机器人互动"}
      >
        <Switch />
      </Form.Item>
      <Form.Item
        name="access_control_group"
        label={"群聊访问控制"}
        valuePropName="checked"
        tooltip={"开启后，只有白名单用户可以在群聊中与机器人互动"}
      >
        <Switch />
      </Form.Item>
      <Form.Item
        name="require_mention"
        label={"需要 @提及"}
        valuePropName="checked"
        tooltip={"开启后，群聊中仅在被 @提及 时才会回复"}
      >
        <Switch />
      </Form.Item>
    </>
  );

  // ── Builtin channel-specific fields ─────────────────────────────────────

  const renderBuiltinExtraFields = (key: ChannelKey) => {
    switch (key) {
      case "matrix":
        return (
          <>
            <Form.Item
              name="homeserver"
              label="Homeserver URL"
              rules={[{ required: true }]}
            >
              <Input placeholder="https://matrix.org" />
            </Form.Item>
            <Form.Item
              name="user_id"
              label="User ID"
              tooltip="Accepts a full MXID (e.g. @bot:matrix.org) or just the localpart (e.g. bot)."
              rules={[{ required: true, message: "Please enter User ID" }]}
            >
              <Input placeholder="@bot:matrix.org" />
            </Form.Item>
            <Form.Item
              name="auth_method"
              label="Auth Method"
              initialValue="token"
            >
              <Select
                options={[
                  { value: "token", label: "Token" },
                  { value: "password", label: "Password" },
                ]}
              />
            </Form.Item>
            <Form.Item
              name="access_token"
              label="Access Token"
              rules={[
                {
                  required: !isMatrixPasswordAuth,
                  message: "Please enter access token",
                },
              ]}
              hidden={isMatrixPasswordAuth}
            >
              <Input.Password placeholder="syt_..." />
            </Form.Item>
            <Form.Item
              name="password"
              label="Password"
              rules={[
                {
                  required: isMatrixPasswordAuth,
                  message: "Please enter password",
                },
              ]}
              hidden={!isMatrixPasswordAuth}
            >
              <Input.Password placeholder="Account password for login" />
            </Form.Item>
            <Form.Item
              name="encryption"
              label="Enable End-to-End Encryption"
              tooltip="After enabling, you must verify the device in a Matrix client (e.g. Element). E2EE requires manually installing matrix-nio[e2e] (pip install matrix-nio[e2e])."
              valuePropName="checked"
              hidden={!isMatrixPasswordAuth}
            >
              <Switch />
            </Form.Item>
            <Form.Item
              name="device_name"
              label="Device Name"
              tooltip="A stable device identity for the Matrix client. Defaults to 'minions-worker' if left empty."
            >
              <Input placeholder="minions-worker" />
            </Form.Item>
            <Form.Item
              name="dm_disabled"
              label={"禁用私聊"}
              valuePropName="checked"
              tooltip={"开启后，机器人将完全忽略所有私聊消息"}
            >
              <Switch />
            </Form.Item>
            <Form.Item
              name="group_disabled"
              label={"禁用群聊"}
              valuePropName="checked"
              tooltip={"开启后，机器人将完全忽略所有群聊消息"}
            >
              <Switch />
            </Form.Item>
          </>
        );

      case "imessage":
        return (
          <>
            <Form.Item
              name="db_path"
              label="DB Path"
              rules={[{ required: true, message: "Please input DB path" }]}
            >
              <Input placeholder="~/Library/Messages/chat.db" />
            </Form.Item>
            <Form.Item
              name="poll_sec"
              label="Poll Interval (sec)"
              rules={[
                { required: true, message: "Please input poll interval" },
              ]}
            >
              <InputNumber min={0.1} step={0.1} style={{ width: "100%" }} />
            </Form.Item>
          </>
        );

      case "discord":
        return (
          <>
            <Form.Item
              name="bot_token"
              label="Bot Token"
              rules={[{ required: true }]}
            >
              <Input.Password placeholder="Discord bot token" />
            </Form.Item>
            <Form.Item name="http_proxy" label="HTTP Proxy">
              <Input placeholder="http://127.0.0.1:18118" />
            </Form.Item>
            <Form.Item name="http_proxy_auth" label="HTTP Proxy Auth">
              <Input placeholder="user:password" />
            </Form.Item>
            <Form.Item
              name="accept_bot_messages"
              label={"接收机器人消息"}
              valuePropName="checked"
              tooltip={"开启后，将接收来自其他机器人的消息"}
            >
              <Switch />
            </Form.Item>
            <Form.Item name="media_dir" label={"媒体文件目录"}>
              <Input placeholder={defaultMediaDir} />
            </Form.Item>
          </>
        );

      case "dingtalk":
        return (
          <>
            <ConfigProvider prefixCls="ant">
              <Alert
                type="info"
                showIcon
                message={"使用钉钉扫码一键创建机器人。扫码后将自动创建钉钉应用并获取 Client ID 和 Client Secret。"}
                style={{ marginBottom: 16 }}
              />
            </ConfigProvider>
            <QrcodeAuthBlock
              label={"扫码创建机器人"}
              buttonText={"获取钉钉二维码"}
              imageAlt="DingTalk QR Code"
              hintText={"请使用钉钉扫描上方二维码，完成授权后 Client ID 与 Client Secret 将自动填入。"}
              channel="dingtalk"
              successStatus="success"
              successCredentialKey="client_id"
              pollInterval={5000}
              onSuccess={(credentials) => {
                form.setFieldsValue({
                  client_id: credentials.client_id,
                  client_secret: credentials.client_secret,
                });
                message.success("钉钉机器人创建成功，Client ID 与 Client Secret 已自动填入");
              }}
              onError={(type) => {
                if (type === "expired") {
                  message.warning("二维码已过期，请重新获取");
                } else {
                  message.error("获取钉钉二维码失败，请稍后重试");
                }
              }}
            />
            <Form.Item
              name="client_id"
              label="Client ID"
              rules={[{ required: true }]}
            >
              <Input placeholder="dingxxxxx" />
            </Form.Item>
            <Form.Item
              name="client_secret"
              label="Client Secret"
              rules={[{ required: true }]}
            >
              <Input.Password />
            </Form.Item>
            <Form.Item
              name="message_type"
              label="Message Type"
              tooltip="markdown: regular messages; card: AI interactive card"
            >
              <Select
                options={[
                  { label: "markdown", value: "markdown" },
                  { label: "card", value: "card" },
                ]}
              />
            </Form.Item>
            <Form.Item
              name="cron_message_type"
              label="Cron Message Type"
              tooltip="Message type for cron/scheduled task sends. Independent from the chat message type above."
            >
              <Select
                options={[
                  { label: "markdown", value: "markdown" },
                  { label: "card", value: "card" },
                ]}
              />
            </Form.Item>
            <Form.Item
              noStyle
              shouldUpdate={(prev, cur) =>
                prev.message_type !== cur.message_type ||
                prev.cron_message_type !== cur.cron_message_type
              }
            >
              {({ getFieldValue }) => {
                const needsCard =
                  getFieldValue("message_type") === "card" ||
                  getFieldValue("cron_message_type") === "card";
                if (!needsCard) return null;
                return (
                  <>
                    <Form.Item
                      name="card_template_id"
                      label="Card Template ID"
                      rules={[
                        {
                          required: true,
                          message:
                            "Please input card template id when message_type=card",
                        },
                      ]}
                    >
                      <Input placeholder="dt_card_template_xxx" />
                    </Form.Item>
                    <Form.Item
                      name="card_template_key"
                      label="Card Template Key"
                      tooltip="Must exactly match the template variable name"
                    >
                      <Input placeholder="content" />
                    </Form.Item>
                    <Form.Item
                      name="robot_code"
                      label="Robot Code"
                      tooltip="Recommended to configure explicitly for group chats"
                    >
                      <Input placeholder="robot code (default client_id)" />
                    </Form.Item>
                  </>
                );
              }}
            </Form.Item>
            <Form.Item
              name="endpoint"
              label={"API 地址"}
              tooltip={"用于钉钉私有化部署的自定义 API 地址。留空则使用官方默认地址。"}
            >
              <Input placeholder="https://api.dingtalk.com" />
            </Form.Item>
            <Form.Item
              name="at_sender_on_reply"
              label={"回复时@发送者"}
              tooltip={"开启后，机器人在群聊中回复时会在第一条消息中@发送者。注意：卡片模式下，@功能仅对企业内部成员生效。"}
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
          </>
        );

      case "feishu":
        return (
          <>
            <Form.Item
              name="domain"
              label={"地区"}
              initialValue="feishu"
              tooltip={"国内用户选择飞书，海外用户选择 Lark"}
            >
              <Select>
                <Select.Option value="feishu">
                  {"飞书（国内）"}
                </Select.Option>
                <Select.Option value="lark">
                  {"Lark（海外）"}
                </Select.Option>
              </Select>
            </Form.Item>
            <ConfigProvider prefixCls="ant">
              <Alert
                type="info"
                showIcon
                message={"使用飞书扫码一键创建机器人。扫码后将自动创建飞书应用并获取 App ID 和 App Secret。"}
                style={{ marginBottom: 16 }}
              />
            </ConfigProvider>
            <QrcodeAuthBlock
              label={"扫码创建机器人"}
              buttonText={"获取飞书二维码"}
              imageAlt="Feishu QR Code"
              hintText={"请使用飞书扫描上方二维码，完成授权后 App ID 与 App Secret 将自动填入。"}
              channel="feishu"
              successStatus="success"
              successCredentialKey="app_id"
              pollInterval={2000}
              params={{ domain: feishuDomain }}
              onSuccess={(credentials) => {
                form.setFieldsValue({
                  app_id: credentials.app_id,
                  app_secret: credentials.app_secret,
                });
                message.success("飞书机器人创建成功，App ID 与 App Secret 已自动填入");
              }}
              onError={(type) => {
                if (type === "expired") {
                  message.warning("二维码已过期，请重新获取");
                } else {
                  message.error("获取飞书二维码失败，请稍后重试");
                }
              }}
            />
            <Form.Item
              name="app_id"
              label="App ID"
              rules={[{ required: true }]}
            >
              <Input placeholder="cli_xxx" />
            </Form.Item>
            <Form.Item
              name="app_secret"
              label="App Secret"
              rules={[{ required: true }]}
            >
              <Input.Password placeholder="App Secret" />
            </Form.Item>
            <Form.Item name="encrypt_key" label="Encrypt Key">
              <Input placeholder="Optional, for event encryption" />
            </Form.Item>
            <Form.Item name="verification_token" label="Verification Token">
              <Input placeholder="Optional" />
            </Form.Item>
            <Form.Item name="media_dir" label={"媒体文件目录"}>
              <Input placeholder={defaultMediaDir} />
            </Form.Item>
            <Form.Item
              name="share_session_in_group"
              label={"群聊共享上下文"}
              valuePropName="checked"
              tooltip={"启用时，群内所有成员共享同一会话上下文；禁用时，每位成员维护各自独立的会话。"}
            >
              <Switch />
            </Form.Item>
          </>
        );

      case "qq":
        return (
          <>
            <ConfigProvider prefixCls="ant">
              <Alert
                type="info"
                showIcon
                message={"使用 QQ 扫码授权机器人，扫码后将自动获取 APP ID 和 Client Secret 并填入。"}
                style={{ marginBottom: 16 }}
              />
            </ConfigProvider>
            <QrcodeAuthBlock
              label={"扫码授权机器人"}
              buttonText={"获取 QQ 二维码"}
              imageAlt="QQ QR Code"
              hintText={"请使用 QQ 扫描上方二维码，完成授权后 APP ID 和 Client Secret 将自动填入。"}
              channel="qq"
              successStatus="success"
              successCredentialKey="app_id"
              pollInterval={2000}
              pollTimeout={300000}
              maxPollCount={180}
              onSuccess={(credentials) => {
                form.setFieldsValue({
                  app_id: credentials.app_id,
                  client_secret: credentials.client_secret,
                  user_openid: credentials.user_openid,
                });
                message.success("QQ 机器人授权成功，APP ID 和 Client Secret 已自动填入");
              }}
              onError={(type) => {
                if (type === "expired") {
                  message.warning("二维码已过期，请重新获取");
                } else {
                  message.error("获取 QQ 二维码失败，请稍后重试");
                }
              }}
            />
            <Form.Item
              name="app_id"
              label="App ID"
              rules={[{ required: true }]}
            >
              <Input />
            </Form.Item>
            <Form.Item
              name="client_secret"
              label="Client Secret"
              rules={[{ required: true }]}
            >
              <Input.Password />
            </Form.Item>
            <Form.Item name="user_openid" hidden>
              <Input />
            </Form.Item>
            <Form.Item
              name="ack_message"
              label={"即时确认消息"}
              tooltip={"收到消息后立即发送一条确认回复，在 Agent 处理之前。留空则禁用。"}
            >
              <Input placeholder={"⏳ 正在处理中..."} />
            </Form.Item>
          </>
        );

      case "telegram":
        return (
          <>
            <Form.Item
              name="bot_token"
              label="Bot Token"
              rules={[{ required: true }]}
            >
              <Input.Password placeholder="Telegram bot token from BotFather" />
            </Form.Item>
            <Form.Item name="base_url" label="API Base URL">
              <Input placeholder="https://tg-api.yourdomain.com" />
            </Form.Item>
            <Form.Item name="http_proxy" label="HTTP Proxy">
              <Input placeholder="http://127.0.0.1:18118" />
            </Form.Item>
            <Form.Item name="http_proxy_auth" label="HTTP Proxy Auth">
              <Input placeholder="user:password" />
            </Form.Item>
            <Form.Item
              name="show_typing"
              label="Show Typing"
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
          </>
        );

      case "slack":
        return (
          <>
            <Form.Item
              name="bot_token"
              label="Bot Token"
              rules={[{ required: true }]}
              tooltip={"Slack Bot User OAuth Token，以 xoxb- 开头"}
            >
              <Input.Password placeholder="xoxb-..." />
            </Form.Item>
            <Form.Item
              name="app_token"
              label="App Token"
              rules={[{ required: true }]}
              tooltip={"Slack App-Level Token（Socket Mode），以 xapp- 开头"}
            >
              <Input.Password placeholder="xapp-..." />
            </Form.Item>
            <Form.Item
              name="proxy"
              label="HTTP Proxy"
              tooltip={"HTTP 代理地址，用于连接 Slack API"}
            >
              <Input placeholder="http://127.0.0.1:18118" />
            </Form.Item>
          </>
        );

      case "mqtt":
        return (
          <>
            <Form.Item
              name="host"
              label="MQTT Host"
              rules={[{ required: true }]}
            >
              <Input placeholder="127.0.0.1" />
            </Form.Item>
            <Form.Item
              name="port"
              label="MQTT Port"
              rules={[
                { required: true },
                {
                  type: "number",
                  min: 1,
                  max: 65535,
                  message: "Port must be between 1 and 65535",
                },
              ]}
            >
              <InputNumber
                min={1}
                max={65535}
                style={{ width: "100%" }}
                placeholder="1883"
              />
            </Form.Item>
            <Form.Item
              name="transport"
              label="Transport"
              initialValue="tcp"
              rules={[{ required: true }]}
            >
              <Select>
                <Select.Option value="tcp">MQTT (tcp)</Select.Option>
                <Select.Option value="websockets">
                  WS (websockets)
                </Select.Option>
              </Select>
            </Form.Item>
            <Form.Item
              name="clean_session"
              label="Clean Session"
              valuePropName="checked"
            >
              <Switch defaultChecked />
            </Form.Item>
            <Form.Item
              name="qos"
              label="QoS"
              initialValue="2"
              rules={[{ required: true }]}
            >
              <Select>
                <Select.Option value="0">At Most Once (0)</Select.Option>
                <Select.Option value="1">At Least Once (1)</Select.Option>
                <Select.Option value="2">Exactly Once (2)</Select.Option>
              </Select>
            </Form.Item>
            <Form.Item name="username" label="MQTT Username">
              <Input placeholder="Leave blank to disable / not use" />
            </Form.Item>
            <Form.Item name="password" label="MQTT Password">
              <Input.Password placeholder="Leave blank to disable / not use" />
            </Form.Item>
            <Form.Item
              name="subscribe_topic"
              label="Subscribe Topic"
              rules={[{ required: true }]}
            >
              <Input placeholder="server/+/up" />
            </Form.Item>
            <Form.Item
              name="publish_topic"
              label="Publish Topic"
              rules={[{ required: true }]}
            >
              <Input placeholder="client/{client_id}/down" />
            </Form.Item>
            <Form.Item
              name="tls_enabled"
              label="TLS Enabled"
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
            <Form.Item name="tls_ca_certs" label="TLS CA Certs">
              <Input placeholder="Path to CA certificates file" />
            </Form.Item>
            <Form.Item name="tls_certfile" label="TLS Certfile">
              <Input placeholder="Path to client certificate file" />
            </Form.Item>
            <Form.Item name="tls_keyfile" label="TLS Keyfile">
              <Input placeholder="Path to client private key file" />
            </Form.Item>
          </>
        );

      case "mattermost":
        return (
          <>
            <Form.Item
              name="url"
              label="Mattermost URL"
              rules={[{ required: true }]}
            >
              <Input placeholder="https://mattermost.example.com" />
            </Form.Item>
            <Form.Item
              name="bot_token"
              label="Bot Token"
              rules={[{ required: true }]}
            >
              <Input.Password placeholder="Mattermost bot token" />
            </Form.Item>
            <Form.Item name="media_dir" label={"媒体文件目录"}>
              <Input placeholder={defaultMediaDir} />
            </Form.Item>
            <Form.Item
              name="show_typing"
              label="Show Typing"
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
            <Form.Item
              name="thread_follow_without_mention"
              label="Thread Follow Without Mention"
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
          </>
        );

      case "voice":
        return (
          <>
            <ConfigProvider prefixCls="ant">
              <Alert
                type="info"
                showIcon
                message={"请先注册 Twilio 账户并购买电话号码，然后在下方填写凭据。Account SID 和 Auth Token 可在 Twilio 控制台首页找到。Phone Number SID 在 Phone Numbers → Active Numbers 中查看。"}
                style={{ marginBottom: 16 }}
              />
            </ConfigProvider>
            <Form.Item
              name="twilio_account_sid"
              label={"Twilio 账户 SID"}
              rules={[{ required: true }]}
            >
              <Input placeholder="ACxxxxxxxx" />
            </Form.Item>
            <Form.Item
              name="twilio_auth_token"
              label={"Twilio 认证令牌"}
              rules={[{ required: true }]}
            >
              <Input.Password />
            </Form.Item>
            <Form.Item name="phone_number" label={"电话号码"}>
              <Input placeholder="+15551234567" />
            </Form.Item>
            <Form.Item
              name="phone_number_sid"
              label={"电话号码 SID"}
              tooltip={"可在 Twilio 控制台的 Phone Numbers → Active Numbers 中找到。"}
            >
              <Input placeholder="PNxxxxxxxx" />
            </Form.Item>
            <Form.Item name="tts_provider" label={"TTS 提供商"}>
              <Input placeholder="google" />
            </Form.Item>
            <Form.Item name="tts_voice" label={"TTS 语音"}>
              <Input placeholder="en-US-Journey-D" />
            </Form.Item>
            <Form.Item name="stt_provider" label={"STT 提供商"}>
              <Input placeholder="deepgram" />
            </Form.Item>
            <Form.Item name="language" label={"语言"}>
              <Input placeholder="en-US" />
            </Form.Item>
            <Form.Item
              name="welcome_greeting"
              label={"欢迎语"}
            >
              <Input.TextArea rows={2} />
            </Form.Item>
          </>
        );

      case "sip":
        return (
          <>
            <ConfigProvider prefixCls="ant">
              <Alert
                type="info"
                showIcon
                message={"配置 SIP 注册服务器（如 Asterisk、FreeSWITCH），然后在下方填写 SIP 凭据。Dev 模式使用 pyVoIP 在本地处理 SIP/RTP；Production 模式使用 LiveKit SIP Server。"}
                style={{ marginBottom: 16 }}
              />
            </ConfigProvider>
            <Form.Item
              name="sip_mode"
              label={"SIP 模式"}
              tooltip={"Dev：纯 Python pyVoIP，适合本地开发测试。Production：LiveKit SIP Server，适合高并发生产环境。"}
              initialValue="dev"
            >
              <Select
                options={[
                  { value: "dev", label: "Dev (pyVoIP)" },
                  { value: "livekit", label: "Production (LiveKit)" },
                ]}
              />
            </Form.Item>
            <Form.Item
              shouldUpdate={(
                prev: Record<string, unknown>,
                cur: Record<string, unknown>,
              ) => prev.sip_mode !== cur.sip_mode}
              noStyle
            >
              {({
                getFieldValue,
              }: {
                getFieldValue: (name: string) => unknown;
              }) => (
                <Form.Item name="sip_server" label={"SIP 服务器"}>
                  <Input
                    placeholder={
                      getFieldValue("sip_mode") === "livekit"
                        ? "LiveKit 模式无需填写"
                        : "留空使用内置注册服务器"
                    }
                  />
                </Form.Item>
              )}
            </Form.Item>
            <Form.Item name="sip_username" label={"SIP 用户名"}>
              <Input placeholder="1001" />
            </Form.Item>
            <Form.Item name="sip_password" label={"SIP 密码"}>
              <Input.Password />
            </Form.Item>
            <Form.Item
              name="sip_port"
              label={"SIP 端口"}
              rules={[
                {
                  type: "number",
                  min: 1,
                  max: 65535,
                },
              ]}
            >
              <InputNumber
                min={1}
                max={65535}
                style={{ width: "100%" }}
                placeholder="5061"
              />
            </Form.Item>
            <Form.Item
              name="sip_transport"
              label={"传输协议"}
              initialValue="UDP"
            >
              <Select
                options={[
                  { value: "UDP", label: "UDP" },
                  { value: "TCP", label: "TCP" },
                  { value: "TLS", label: "TLS" },
                ]}
              />
            </Form.Item>
            <Form.Item
              name="dashscope_api_key"
              label={"DashScope API Key"}
              tooltip={"阿里云 DashScope STT/TTS 的 API Key。留空则回退到 DASHSCOPE_API_KEY 环境变量。"}
            >
              <Input.Password placeholder="sk-..." />
            </Form.Item>
            <Form.Item name="tts_provider" label={"TTS 提供商"}>
              <Input placeholder="aliyun" />
            </Form.Item>
            <Form.Item name="tts_voice" label={"TTS 语音"}>
              <Input placeholder="longxiaochun" />
            </Form.Item>
            <Form.Item name="stt_provider" label={"STT 提供商"}>
              <Input placeholder="aliyun" />
            </Form.Item>
            <Form.Item name="language" label={"语言"}>
              <Input placeholder="zh-CN" />
            </Form.Item>
            <Form.Item
              name="welcome_greeting"
              label={"欢迎语"}
            >
              <Input.TextArea rows={2} />
            </Form.Item>
            <Form.Item
              noStyle
              shouldUpdate={(prev, cur) => prev.sip_mode !== cur.sip_mode}
            >
              {({ getFieldValue }) => {
                if (getFieldValue("sip_mode") !== "livekit") return null;
                return (
                  <>
                    <Form.Item
                      name="livekit_url"
                      label={"LiveKit URL"}
                      rules={[{ required: true }]}
                    >
                      <Input placeholder="ws://localhost:7880" />
                    </Form.Item>
                    <Form.Item
                      name="livekit_api_key"
                      label={"LiveKit API Key"}
                      rules={[{ required: true }]}
                    >
                      <Input />
                    </Form.Item>
                    <Form.Item
                      name="livekit_api_secret"
                      label={"LiveKit API Secret"}
                      rules={[{ required: true }]}
                    >
                      <Input.Password />
                    </Form.Item>
                    <Form.Item
                      name="livekit_sip_trunk_id"
                      label={"LiveKit SIP Trunk ID"}
                    >
                      <Input placeholder="ST_xxxx" />
                    </Form.Item>
                    <Form.Item
                      name="livekit_room_name"
                      label={"LiveKit 房间名称"}
                      tooltip={"Agent 连入并等待 SIP 来电的 LiveKit 房间名称，需与 SIP Dispatch Rule 中配置的房间名一致。"}
                    >
                      <Input placeholder="sip-inbound" />
                    </Form.Item>
                  </>
                );
              }}
            </Form.Item>
          </>
        );

      case "wecom":
        return (
          <>
            <ConfigProvider prefixCls="ant">
              <Alert
                type="warning"
                showIcon
                message={"使用二维码创建机器人时，授权机器人可使用的能力时请选择「暂不授权」。如果选择了「确认授权」，除了机器人创建者，其他用户可能无法与机器人交互。"}
                style={{ marginBottom: 16 }}
              />
            </ConfigProvider>
            <QrcodeAuthBlock
              label={"扫码授权"}
              buttonText={"获取企业微信二维码"}
              imageAlt="WeCom QR Code"
              hintText={"请使用企业微信扫描上方二维码完成授权，授权成功后 Bot ID 与 Secret 将自动填入。"}
              channel="wecom"
              successStatus="success"
              successCredentialKey="bot_id"
              pollInterval={3000}
              onSuccess={(credentials) => {
                form.setFieldsValue({
                  bot_id: credentials.bot_id,
                  secret: credentials.secret,
                });
                message.success("企业微信机器人授权成功，Bot ID 与 Secret 已自动填入");
              }}
              onError={() => {
                message.error("获取企业微信二维码失败，请重试");
              }}
            />
            <Form.Item
              name="bot_id"
              label="Bot ID"
              rules={[{ required: true, message: "Please input Bot ID" }]}
            >
              <Input placeholder="Bot ID from WeCom backend" />
            </Form.Item>
            <Form.Item
              name="secret"
              label="Secret"
              rules={[{ required: true, message: "Please input Secret" }]}
            >
              <Input.Password placeholder="Secret from WeCom backend" />
            </Form.Item>
            <Form.Item name="media_dir" label={"媒体文件目录"}>
              <Input placeholder={defaultMediaDir} />
            </Form.Item>
            <Form.Item
              name="welcome_text"
              label={"欢迎消息"}
              tooltip={"用户当天首次进入机器人单聊会话时机器人自动发送的消息"}
            >
              <Input placeholder={"例如：你好！我是 Minions，有什么可以帮你的？"} />
            </Form.Item>
            <Form.Item
              name="share_session_in_group"
              label={"群聊共享上下文"}
              valuePropName="checked"
              tooltip={"启用时，群内所有成员共享同一会话上下文；禁用时，每位成员维护各自独立的会话。"}
            >
              <Switch />
            </Form.Item>
          </>
        );

      case "xiaoyi":
        return (
          <>
            <ConfigProvider prefixCls="ant">
              <Alert
                type="info"
                showIcon
                message={"请在华为开发者平台创建智能体并获取 AK/SK 和 Agent ID。AK/SK 可在凭证管理页面找到。"}
                style={{ marginBottom: 16 }}
              />
            </ConfigProvider>
            <Form.Item
              name="ak"
              label="Access Key (AK)"
              rules={[{ required: true, message: "Please input Access Key" }]}
            >
              <Input placeholder="Access Key from Huawei Developer Platform" />
            </Form.Item>
            <Form.Item
              name="sk"
              label="Secret Key (SK)"
              rules={[{ required: true, message: "Please input Secret Key" }]}
            >
              <Input.Password placeholder="Secret Key from Huawei Developer Platform" />
            </Form.Item>
            <Form.Item
              name="agent_id"
              label="Agent ID"
              rules={[{ required: true, message: "Please input Agent ID" }]}
            >
              <Input placeholder="Agent ID from XiaoYi platform" />
            </Form.Item>
          </>
        );

      case "wechat":
        return (
          <>
            <ConfigProvider prefixCls="ant">
              <Alert
                type="info"
                showIcon
                message={"微信个人账号 Bot（iLink 协议）。首次启动时若未配置 Bot Token，系统将打印二维码链接，请扫码登录；Token 将自动保存到本地文件供后续使用。"}
                style={{ marginBottom: 16 }}
              />
              <Alert
                type="warning"
                showIcon
                message={"微信 iLink 平台限制：每条用户消息对应的 context_token 最多只能回复 10 条消息，这是平台侧的硬性限制。建议关闭思考及工具输出，或者使用消息合并功能以避免超出限制导致消息发送失败。"}
                style={{ marginBottom: 16 }}
              />
            </ConfigProvider>
            <QrcodeAuthBlock
              label={"扫码登录"}
              buttonText={"获取登录二维码"}
              imageAlt="WeChat QR Code"
              hintText={"请用微信扫描二维码，扫码成功后点击保存"}
              channel="wechat"
              successStatus="confirmed"
              successCredentialKey="bot_token"
              pollInterval={2000}
              onSuccess={(credentials) => {
                form.setFieldsValue({ bot_token: credentials.bot_token });
                message.success("微信扫码登录成功，Token 已填入");
              }}
              onError={(type) => {
                if (type === "expired") {
                  message.warning("二维码已过期，请重新获取");
                } else {
                  message.error("获取二维码失败，请稍后重试");
                }
              }}
            />
            <Form.Item
              name="bot_token"
              label={"Bot Token"}
              tooltip={"扫码登录后获取的 Bearer Token。留空时将在启动时引导扫码登录。"}
            >
              <Input.Password
                placeholder={"扫码登录后自动填入，也可手动粘贴"}
              />
            </Form.Item>
            <Form.Item
              name="bot_token_file"
              label={"Token 文件路径"}
              tooltip={"Token 持久化存储路径，默认为 ~/.minions/wechat_bot_token"}
            >
              <Input placeholder="~/.minions/wechat_bot_token" />
            </Form.Item>
            <Form.Item name="media_dir" label={"媒体文件目录"}>
              <Input placeholder={defaultMediaDir} />
            </Form.Item>
            <Form.Item
              name="message_merge_enabled"
              label={"消息合并"}
              valuePropName="checked"
              tooltip={"将多条回复消息合并为更少的消息发送，避免触发微信 context_token 10 条消息的限制。开启并设置延时为 0 时，所有文本回复将在请求结束后合并为一条消息发送。设置正数延时（毫秒）则合并该时间窗口内的相邻消息。"}
            >
              <Switch />
            </Form.Item>
            <Form.Item
              noStyle
              shouldUpdate={(prev, cur) =>
                prev.message_merge_enabled !== cur.message_merge_enabled
              }
            >
              {({ getFieldValue }) =>
                getFieldValue("message_merge_enabled") ? (
                  <Form.Item
                    name="message_merge_delay_ms"
                    label={"合并延时（毫秒）"}
                    tooltip={"相邻消息合并的时间窗口。设为 0 表示将所有消息合并为一条最终回复。设为正数（如 1000）则缓冲该时间段内的消息后发送。"}
                    initialValue={0}
                    rules={[
                      {
                        validator: (_: unknown, value: unknown) => {
                          if (
                            value === null ||
                            value === undefined ||
                            value === ""
                          ) {
                            return Promise.resolve();
                          }
                          const num = Number(value);
                          if (!Number.isInteger(num) || num < 0) {
                            return Promise.reject(
                              new Error(
                                "请输入有效的非负整数",
                              ),
                            );
                          }
                          return Promise.resolve();
                        },
                      },
                    ]}
                  >
                    <InputNumber
                      min={0}
                      step={100}
                      style={{ width: "100%" }}
                      placeholder="0"
                    />
                  </Form.Item>
                ) : null
              }
            </Form.Item>
          </>
        );

      case "yuanbao":
        return (
          <>
            <Form.Item
              name="app_id"
              label="App ID"
              rules={[{ required: true, message: "Please input App ID" }]}
            >
              <Input placeholder="App ID from Yuanbao platform" />
            </Form.Item>
            <Form.Item
              name="app_secret"
              label="App Secret"
              rules={[{ required: true, message: "Please input App Secret" }]}
            >
              <Input.Password placeholder="App Secret from Yuanbao platform" />
            </Form.Item>
            <Form.Item
              name="api_domain"
              label="API Domain"
              tooltip="REST API domain for sign-token auth (default: bot.yuanbao.tencent.com)"
            >
              <Input placeholder="bot.yuanbao.tencent.com" />
            </Form.Item>
            <Form.Item name="media_dir" label={"媒体文件目录"}>
              <Input placeholder={defaultMediaDir} />
            </Form.Item>
            <Form.Item
              name="accept_bot_messages"
              label={"接收机器人消息"}
              valuePropName="checked"
              tooltip={"开启后，将接收来自其他机器人的消息"}
            >
              <Switch />
            </Form.Item>
          </>
        );

      case "onebot":
        return (
          <>
            <Form.Item
              name="ws_host"
              label="WebSocket Host"
              rules={[{ required: true }]}
            >
              <Input placeholder="0.0.0.0" />
            </Form.Item>
            <Form.Item
              name="ws_port"
              label="WebSocket Port"
              rules={[
                { required: true },
                {
                  type: "number",
                  min: 1,
                  max: 65535,
                  message: "Port must be between 1 and 65535",
                },
              ]}
            >
              <InputNumber
                min={1}
                max={65535}
                style={{ width: "100%" }}
                placeholder="6199"
              />
            </Form.Item>
            <Form.Item name="access_token" label="Access Token">
              <Input.Password placeholder="Access token for authentication" />
            </Form.Item>
            <Form.Item
              name="share_session_in_group"
              label={"群聊共享上下文"}
              valuePropName="checked"
              tooltip={"启用时，群内所有成员共享同一会话上下文；禁用时，每位成员维护各自独立的会话。"}
            >
              <Switch />
            </Form.Item>
          </>
        );

      default:
        return null;
    }
  };

  // ── Custom channel fields (key-value editor) ─────────────────────────────

  const renderCustomExtraFields = (
    values: Record<string, unknown> | undefined,
  ) => {
    // If we have a schema from the plugin system, render based on it
    if (channelSchema && channelSchema.config_fields.length > 0) {
      return (
        <>
          {channelSchema.description && (
            <div className={styles.schemaDescription}>
              {channelSchema.description}
            </div>
          )}
          {channelSchema.config_fields.map((field) => {
            const rules = field.required
              ? [{ required: true, message: `Please enter ${field.label}` }]
              : undefined;

            switch (field.type) {
              case "password":
                return (
                  <Form.Item
                    key={field.name}
                    name={field.name}
                    label={field.label}
                    rules={rules}
                    tooltip={field.help}
                    initialValue={field.default}
                  >
                    <Input.Password placeholder={field.placeholder} />
                  </Form.Item>
                );
              case "number":
                return (
                  <Form.Item
                    key={field.name}
                    name={field.name}
                    label={field.label}
                    rules={rules}
                    tooltip={field.help}
                    initialValue={field.default}
                  >
                    <InputNumber
                      style={{ width: "100%" }}
                      placeholder={field.placeholder}
                    />
                  </Form.Item>
                );
              case "switch":
                return (
                  <Form.Item
                    key={field.name}
                    name={field.name}
                    label={field.label}
                    valuePropName="checked"
                    tooltip={field.help}
                    initialValue={field.default}
                  >
                    <Switch />
                  </Form.Item>
                );
              case "select":
                return (
                  <Form.Item
                    key={field.name}
                    name={field.name}
                    label={field.label}
                    rules={rules}
                    tooltip={field.help}
                    initialValue={field.default}
                  >
                    <Select
                      placeholder={field.placeholder}
                      options={(field.options || []).map((opt) => ({
                        label: opt,
                        value: opt,
                      }))}
                    />
                  </Form.Item>
                );
              default:
                return (
                  <Form.Item
                    key={field.name}
                    name={field.name}
                    label={field.label}
                    rules={rules}
                    tooltip={field.help}
                    initialValue={field.default}
                  >
                    <Input placeholder={field.placeholder} />
                  </Form.Item>
                );
            }
          })}
        </>
      );
    }

    // Fallback: infer field types from existing values (legacy behavior)
    if (!values) return null;
    const extraKeys = Object.keys(values).filter(
      (k) => !BASE_FIELDS.includes(k),
    );
    if (extraKeys.length === 0) return null;

    return (
      <>
        <div style={{ marginBottom: 8, fontWeight: 500 }}>Custom Fields</div>
        {extraKeys.map((fieldKey) => {
          const value = values[fieldKey];
          return (
            <Form.Item key={fieldKey} name={fieldKey} label={fieldKey}>
              {typeof value === "boolean" ? (
                <Switch />
              ) : typeof value === "number" ? (
                <InputNumber style={{ width: "100%" }} />
              ) : (
                <Input />
              )}
            </Form.Item>
          );
        })}
      </>
    );
  };

  // ── Drawer title ─────────────────────────────────────────────────────────

  const drawerTitle = (
    <div className={styles.drawerTitle}>
      <span>
        {label
          ? `${label} ${"设置"}`
          : "频道设置"}
      </span>
      {activeKey &&
        CHANNEL_DOC_EN_URLS[activeKey] &&
        CHANNEL_DOC_ZH_URLS[activeKey] && (
          <Button
            type="text"
            size="small"
            icon={<LinkOutlined />}
            onClick={() => {
              const url =
                CHANNEL_DOC_EN_URLS[activeKey]! ||
                CHANNEL_DOC_ZH_URLS[activeKey]!;
              const isMinionsDoc = url.includes(
                "minions.agentscope.io/docs/channels/",
              );
              const finalUrl =
                isMinionsDoc && currentLang === "zh"
                  ? CHANNEL_DOC_ZH_URLS[activeKey]!
                  : CHANNEL_DOC_EN_URLS[activeKey]!;
              openExternalLink(finalUrl);
            }}
            className={styles.dingtalkDocBtn}
            style={{ color: "#FF7F16" }}
          >
            {label} Doc
          </Button>
        )}
      {activeKey === "voice" && (
        <Button
          type="text"
          size="small"
          icon={<LinkOutlined />}
          onClick={() => openExternalLink(TWILIO_CONSOLE_URL)}
          className={styles.dingtalkDocBtn}
          style={{ color: "#FF7F16" }}
        >
          {"打开 Twilio 控制台"}
        </Button>
      )}
    </div>
  );

  // ── Render ───────────────────────────────────────────────────────────────

  const drawerFooter = (
    <div className={styles.formActions}>
      <Button onClick={onClose}>{"取消"}</Button>
      <Button type="primary" loading={saving} onClick={() => form.submit()}>
        {"保存"}
      </Button>
    </div>
  );

  return (
    <Drawer
      width={420}
      placement="right"
      title={drawerTitle}
      open={open}
      onClose={onClose}
      destroyOnHidden
      footer={drawerFooter}
      key={activeKey} // Force remount when switching channels
    >
      {activeKey && (
        <Form
          form={form}
          layout="vertical"
          initialValues={initialValues}
          onFinish={(values: Record<string, unknown>) => {
            if (activeKey !== "matrix") {
              onSubmit(values);
              return;
            }
            const { auth_method, ...rest } = values;
            if (auth_method === "password") {
              onSubmit({ ...rest, access_token: "" });
            } else {
              onSubmit({ ...rest, password: "", encryption: false });
            }
          }}
        >
          <Form.Item
            name="enabled"
            label={"已启用"}
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>

          {activeKey !== "voice" && (
            <Form.Item name="bot_prefix" label="Bot Prefix">
              <Input placeholder="@bot" />
            </Form.Item>
          )}

          {activeKey !== "console" && (
            <>
              <Form.Item
                name="filter_tool_messages"
                label={"显示工具消息"}
                valuePropName="checked"
                tooltip={"向用户显示工具调用和输出消息（关闭则隐藏）"}
              >
                <Switch />
              </Form.Item>
              <Form.Item
                name="filter_thinking"
                label={"显示思考过程"}
                valuePropName="checked"
                tooltip={"向用户显示模型的思考/推理内容（关闭则隐藏）"}
              >
                <Switch />
              </Form.Item>
            </>
          )}

          {(activeKey === "wecom" ||
            activeKey === "telegram" ||
            activeKey === "dingtalk" ||
            activeKey === "feishu" ||
            activeKey === "discord" ||
            activeKey === "slack" ||
            activeKey === "matrix") && (
            <Form.Item
              name="streaming_enabled"
              label={"流式输出"}
              valuePropName="checked"
              tooltip={
                activeKey === "dingtalk"
                  ? "仅在消息类型为 Card 时生效"
                  : activeKey === "feishu"
                  ? "需要在飞书开放平台权限管理界面开通 cardkit:card:write 权限"
                  : undefined
              }
            >
              <Switch />
            </Form.Item>
          )}

          {isBuiltin
            ? renderBuiltinExtraFields(activeKey)
            : renderCustomExtraFields(initialValues)}

          {CHANNELS_WITH_ACCESS_CONTROL.includes(activeKey) &&
            renderAccessControlFields()}

          {activeKey !== "console" && (
            <Form.Item
              name="no_text_debounce"
              label={"无文本消息防抖"}
              valuePropName="checked"
              tooltip={"开启后，仅含媒体（图片/视频/文件）的消息会暂存，等待后续文本消息合并处理；关闭则所有消息立即处理。语音消息始终立即处理"}
              initialValue={true}
            >
              <Switch />
            </Form.Item>
          )}
        </Form>
      )}
    </Drawer>
  );
}
