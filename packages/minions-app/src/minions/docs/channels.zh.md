# 频道配置

**频道** = 你和 Minions 在「哪里」对话：接钉钉就在钉钉里回，接 QQ 就在 QQ 里回。不熟悉这个词的话可以先看 [项目介绍](./intro)。

配置频道有两种方式：

- **控制台**（推荐）— 在 [控制台](./console) 的 **Control → Channels** 页面，点击频道卡片，在抽屉里启用并填写鉴权信息，保存即生效。
- **手动编辑 `agent.json`** — 在智能体工作区的 `agent.json` 中（如 `~/.minions/workspaces/default/agent.json`），将需要的频道设 `enabled: true` 并填好鉴权信息；保存后自动重载，无需重启。

下面按频道说明如何获取凭证并填写配置。

---

## 钉钉（推荐）

### 创建钉钉应用

视频操作流程：

![视频操作流程](https://cloud.video.taobao.com/vod/Fs7JecGIcHdL-np4AS7cXaLoywTDNj7BpiO7_Hb2_cA.mp4)

图文操作流程：

1. 打开 [钉钉开发者后台](https://open-dev.dingtalk.com/)

2. 进入"应用开发→企业内部应用→钉钉应用→创建 **应用**"

   ![钉钉开发者后台](https://img.alicdn.com/imgextra/i1/O1CN01KLtwvu1rt9weVn8in_!!6000000005688-2-tps-2809-1585.png)

3. 在"应用能力→添加应用能力"中添加 **「机器人」**

   ![添加机器人](https://img.alicdn.com/imgextra/i2/O1CN01AboPsn1XGQ84utCG8_!!6000000002896-2-tps-2814-1581.png)

4. 配置机器人基础信息，设置消息接收模式为 **Stream 模式**（流式接收），点击发布

   ![机器人基础信息](https://img.alicdn.com/imgextra/i3/O1CN01KwmNZ61GwhDhKxgSv_!!6000000000687-2-tps-2814-1581.png)

   ![Stream模式+发布](https://img.alicdn.com/imgextra/i2/O1CN01tk8QW11NqvXYqcoPH_!!6000000001622-2-tps-2809-1590.png)

5. 在"应用发布→版本管理与发布"中创建新版本，填写基础信息后保存

   ![创建新版本](https://img.alicdn.com/imgextra/i3/O1CN01lRCPuf1PQwIeFL4AL_!!6000000001836-2-tps-2818-1590.png)

   ![保存](https://img.alicdn.com/imgextra/i1/O1CN01vrzbIA1Qey2x8Jbua_!!6000000002002-2-tps-2809-1585.png)

6. 在"基础信息→凭证与基础信息"中获取：

   - **Client ID**（即 AppKey）
   - **Client Secret**（即 AppSecret）

   ![client](https://img.alicdn.com/imgextra/i3/O1CN01JsRrwx1hJImLfM7O1_!!6000000004256-2-tps-2809-1585.png)

7. （可选） **将服务器 IP 加入白名单** — 调用钉钉开放平台 API（如下载用户发送的图片和文件）时需要此配置。在应用设置中进入 **"安全设置→服务器出口 IP"**，添加运行 Minions 的机器的公网 IP。可在终端执行 `curl ifconfig.me` 查看公网 IP。若未配置白名单，图片和文件下载将报 `Forbidden.AccessDenied.IpNotInWhiteList` 错误。

### 绑定应用

可以在console前端配置，或者修改智能体工作区的 `agent.json`（如 `~/.minions/workspaces/default/agent.json`）。

**方法1**: 在console前端配置

从“控制→频道”找到**DingTalk**，点击后填入刚刚获取的**Client ID**和**Client Secret**

![console](https://img.alicdn.com/imgextra/i4/O1CN01YVQdZe1WsbXoxJOnJ_!!6000000002844-2-tps-3822-2070.png)

**方法2**: 修改 `agent.json`

在智能体工作区的 `agent.json`（如 `~/.minions/workspaces/default/agent.json`）里找到 `channels.dingtalk`，填入对应信息：

```json
"dingtalk": {
  "enabled": true,
  "bot_prefix": "[BOT]",
  "client_id": "你的 Client ID",
  "client_secret": "你的 Client Secret",
  "filter_tool_messages": false
}
```

**钉钉专属字段说明：**

| 字段                | 类型   | 默认值       | 说明                                                           |
| ------------------- | ------ | ------------ | -------------------------------------------------------------- |
| `client_id`         | string | `""`（必填） | 钉钉应用 Client ID（即 AppKey）                                |
| `client_secret`     | string | `""`（必填） | 钉钉应用 Client Secret（即 AppSecret）                         |
| `message_type`      | string | `"markdown"` | 消息类型：`"markdown"` 或 `"card"`（AI 卡片）                  |
| `card_template_id`  | string | `""`         | AI 卡片模板 ID（当 `message_type` 为 `"card"` 时必填）         |
| `card_template_key` | string | `"content"`  | AI 卡片模板变量名（必须与钉钉模板中的变量名完全一致）          |
| `robot_code`        | string | `""`         | 机器人编码（群聊卡片场景建议配置，留空时回退使用 `client_id`） |
| `media_dir`         | string | `null`       | 媒体文件下载目录（留空则不保存）                               |

> **提示：**
>
> - 若希望隐藏工具执行详情，可设置 `filter_tool_messages: true`。
> - AI Card 模式：将 `message_type` 设为 `card`，并填写 `card_template_id`；`card_template_key` 必须与钉钉模板变量名完全一致。
> - 群聊场景建议显式配置 `robot_code`；留空时 Minions 会回退使用 `client_id`。

保存后若服务已运行会自动重载；未运行则执行 `minions app` 启动。

### 找到创建的应用

视频操作流程：

![视频操作流程](https://cloud.video.taobao.com/vod/e0icQREdiZ1LI0b1mWdBDQI94KdJSaJxO09X5BPaWvk.mp4)

图文操作流程：

1. 点击钉钉【消息】栏的“搜索框”

![机器人名称](https://img.alicdn.com/imgextra/i4/O1CN019tRcAi1IIy630Kttu_!!6000000000871-2-tps-2809-2241.png)

2. 搜索刚刚创建的 “机器人名称”，在【功能】下找到机器人

![机器人](https://img.alicdn.com/imgextra/i3/O1CN01Ha69lm23sx9kLX8eD_!!6000000007312-2-tps-2809-2236.png)

3. 点击后进入对话框

![对话框](https://img.alicdn.com/imgextra/i1/O1CN01zjnc7J23hxeOJGYiO_!!6000000007288-2-tps-2046-1630.png)

> 注：可以在钉钉群中通过**群设置→机器人→添加机器人**将机器人添加到群聊。需要注意的是，从与机器人的单聊界面中创建群聊，会无法触发机器人的回复。

---

## 飞书

飞书频道通过 **WebSocket 长连接** 接收消息，无需公网 IP 或 webhook；发送走飞书开放平台 Open API。支持文本、图片、文件收发；群聊场景下会将 `chat_id`、`message_id` 放入请求消息的 metadata，便于下游去重与群上下文识别。

### 创建飞书应用并获取凭证

1. 打开 [飞书开放平台](https://open.feishu.cn/app)，创建企业自建应用

![飞书](https://img.alicdn.com/imgextra/i1/O1CN01awX3Nc1WjRc43kDSk_!!6000000002824-2-tps-4082-2126.png)

![build](https://img.alicdn.com/imgextra/i3/O1CN01OXSFsM1EDh4Xa2aOz_!!6000000000318-2-tps-4082-2126.png)

2. 在「凭证与基础信息」中获取 **App ID**、**App Secret**

![id & secret](https://img.alicdn.com/imgextra/i2/O1CN01tWGGEE1PAuR7APQcs_!!6000000001801-2-tps-4082-2126.png)

3. 在 `agent.json` 中填写上述 **App ID** 和 **App Secret**（见下方「填写 agent.json」），保存

4. 执行 **`minions app`** 启动 Minions 服务

5. 回到飞书开放平台，在「能力」中启用 **机器人**

![bot](https://img.alicdn.com/imgextra/i1/O1CN01eFPe0d1wU2IY4Fyvt_!!6000000006310-2-tps-4082-2126.png)

6. 选择「权限管理」中的「批量导入/导出权限」，将以下JSON代码复制进去

```json
{
  "scopes": {
    "tenant": [
      "aily:file:read",
      "aily:file:write",
      "aily:message:read",
      "aily:message:write",
      "corehr:file:download",
      "im:chat",
      "im:message",
      "im:message.group_msg",
      "im:message.p2p_msg:readonly",
      "im:message.reactions:read",
      "im:resource",
      "contact:user.base:readonly"
    ],
    "user": []
  }
}
```

![in/out](https://img.alicdn.com/imgextra/i4/O1CN01CpUMJn1ey7E6FIpOU_!!6000000003939-2-tps-4082-2126.png)

![json](https://img.alicdn.com/imgextra/i3/O1CN01idxezh1G04WY9SYZR_!!6000000000559-2-tps-4082-2126.png)

![confirm](https://img.alicdn.com/imgextra/i3/O1CN017nCNTC1Lj1TVH1OIt_!!6000000001334-2-tps-4082-2126.png)

![confirm](https://img.alicdn.com/imgextra/i3/O1CN01hwOxur1EV67a7clee_!!6000000000356-2-tps-4082-2126.png)

7. 在「事件与回调」中，点击「事件配置」，选择订阅方式为**长连接（WebSocket）** 模式（无需公网 IP）

> 注：**操作顺序**为先配置 App ID/Secret → 启动 `minions app` → 再在开放平台配置长连接，如果此处仍显示错误，尝试先暂停 Minions 服务并重新启动 `minions app`。

![websocket](https://img.alicdn.com/imgextra/i2/O1CN01LQwKON1x7QMNP41kC_!!6000000006396-2-tps-4082-2126.png)

8. 选择「添加事件」，搜索**接收消息**，订阅**接收消息 v2.0**

![reveive](https://img.alicdn.com/imgextra/i3/O1CN01svBdl41HTDLCtKFed_!!6000000000758-2-tps-4082-2126.png)

![click](https://img.alicdn.com/imgextra/i4/O1CN01Rat93U1sLYV9f5dhe_!!6000000005750-2-tps-4082-2126.png)

![result](https://img.alicdn.com/imgextra/i2/O1CN015GPfGr1BsxuoOXbYC_!!6000000000002-2-tps-4082-2126.png)

<div id="feishu-callback-config"></div>

9. 在「事件与回调」中，点击「回调配置」，选择订阅方式为**长连接（WebSocket）** 模式（无需公网 IP）

![websocket](https://img.alicdn.com/imgextra/i4/O1CN015r6kS71DLBxFDJQWe_!!6000000000199-2-tps-1671-848.png)

10. 选择「添加回调」，搜索**卡片回传交互**，订阅**卡片回传交互**

![reveive](https://img.alicdn.com/imgextra/i3/O1CN017s7lz724GJMzKKKnC_!!6000000007363-2-tps-1685-855.png)

![click](https://img.alicdn.com/imgextra/i4/O1CN01CcGGmW1K0JCp7cQQV_!!6000000001101-2-tps-1679-847.png)

![result](https://img.alicdn.com/imgextra/i3/O1CN01V9kzMj1CbqkBnSI0x_!!6000000000100-2-tps-1682-847.png)

11. 在「应用发布」的「版本管理与发布」中，**创建版本**，填写基础信息，**保存**并**发布**

![create](https://img.alicdn.com/imgextra/i1/O1CN01zOqMGk1lhoREn9Lip_!!6000000004851-2-tps-4082-2126.png)

![info](https://img.alicdn.com/imgextra/i1/O1CN01SQg28h1nAUrLKTH1J_!!6000000005049-2-tps-4082-2126.png)

![save](https://img.alicdn.com/imgextra/i1/O1CN01ebVPlq1lzDUM1Mwej_!!6000000004889-2-tps-4082-2126.png)

### 填写 agent.json

在智能体工作区的 `agent.json`（如 `~/.minions/workspaces/default/agent.json`）中找到`channels.feishu`，只需填 **App ID** 和 **App Secret**（在开放平台「凭证与基础信息」里复制）：

```json
"feishu": {
  "enabled": true,
  "bot_prefix": "[BOT]",
  "app_id": "cli_xxxxx",
  "app_secret": "你的 App Secret",
  "domain": "feishu"
}
```

**飞书专属字段说明：**

| 字段                 | 类型   | 默认值       | 说明                                       |
| -------------------- | ------ | ------------ | ------------------------------------------ |
| `app_id`             | string | `""`（必填） | 飞书应用 App ID                            |
| `app_secret`         | string | `""`（必填） | 飞书应用 App Secret                        |
| `domain`             | string | `"feishu"`   | `"feishu"`（国内）或 `"lark"`（国际版）    |
| `encrypt_key`        | string | `""`         | 消息加密密钥（可选，WebSocket 模式可不填） |
| `verification_token` | string | `""`         | 验证 Token（可选，WebSocket 模式可不填）   |
| `media_dir`          | string | `null`       | 媒体文件下载目录（留空则不保存）           |

> **提示：** 其他字段（encrypt_key、verification_token、media_dir）可选，WebSocket 模式可不填，有默认值。

**依赖：** `pip install lark-oapi`

如果你使用 SOCKS 代理联网，还需安装 `python-socks`（例如 `pip install python-socks`），否则可能报错：`python-socks is required to use a SOCKS proxy`。

> 注: **App ID** 和 **App Secret** 信息也可以在Console前端填写，但需重启 Minions 服务，才能继续配置长链接的操作。
> ![console](https://img.alicdn.com/imgextra/i3/O1CN01KCQj1b1z8utMnRr6y_!!6000000006670-2-tps-3822-2070.png)

### 机器人权限建议

第6步中的json文件为应用配备了以下权限（应用身份、已开通），以保证收发消息与文件正常：

| 权限名称                       | 权限标识                       | 权限类型     | 说明           |
| ------------------------------ | ------------------------------ | ------------ | -------------- |
| 获取文件                       | aily:file:read                 | 应用身份     | -              |
| 上传文件                       | aily:file:write                | 应用身份     | -              |
| 获取消息                       | aily:message:read              | 应用身份     | -              |
| 发送消息                       | aily:message:write             | 应用身份     | -              |
| 下载文件                       | corehr:file:download           | 应用身份     | -              |
| 获取与更新群组信息             | im:chat                        | 应用身份     | -              |
| 获取与发送单聊、群组消息       | im:message                     | 应用身份     | -              |
| 获取群组中所有消息（敏感权限） | im:message.group_msg           | 应用身份     | -              |
| 读取用户发给机器人的单聊消息   | im:message.p2p_msg:readonly    | 应用身份     | -              |
| 查看消息表情回复               | im:message.reactions:read      | 应用身份     | -              |
| 获取与上传图片或文件资源       | im:resource                    | 应用身份     | -              |
| **以应用身份读取通讯录**       | **contact:user.base:readonly** | **应用身份** | **见下方说明** |

> **获取用户昵称（推荐）**：若希望会话和日志中显示**用户昵称**（如「张三#1d1a」）而非「unknown#1d1a」，需额外开通通讯录只读权限 **以应用身份读取通讯录**（`contact:user.base:readonly`）。未开通时，飞书仅返回 open_id 等身份字段，不返回姓名，Minions 无法解析昵称。开通后需重新发布/更新应用版本，权限生效后即可正常显示用户名称。

### 将机器人添加到常用

1. 在**工作台**点击**添加常用**

![添加常用](https://img.alicdn.com/imgextra/i2/O1CN01bSKw0t1tCgReoZNRr_!!6000000005866-2-tps-2614-1488.png)

2. 搜索刚刚创建的机器人名称并**添加**

![添加](https://img.alicdn.com/imgextra/i1/O1CN01aNNTI51IZSM4TYqis_!!6000000000907-2-tps-3785-2158.png)

3. 可以看到机器人已添加到常用中，双击可进入对话界面

![已添加](https://img.alicdn.com/imgextra/i1/O1CN01Kulh7i1Hfa2Dnfpa4_!!6000000000785-2-tps-2614-1488.png)

![对话界面](https://img.alicdn.com/imgextra/i4/O1CN01vsnwn71UMQTaEa0XX_!!6000000002503-2-tps-2614-1488.png)

---

## QQ

### 获取 QQ 机器人凭证

1. 打开 [QQ 开放平台](https://q.qq.com/)

![开放平台](https://img.alicdn.com/imgextra/i4/O1CN01OjCvUf1oT6ZDWpEk5_!!6000000005225-2-tps-4082-2126.png)

2. 创建 **机器人应用**，点击进入编辑页面

![bot](https://img.alicdn.com/imgextra/i3/O1CN01xBbXWa1pSTdioYFdg_!!6000000005359-2-tps-4082-2126.png)

![confirm](https://img.alicdn.com/imgextra/i3/O1CN01zt7w0V1Ij4fjcm5MS_!!6000000000928-2-tps-4082-2126.png)

3. 选择**回调配置**，首先在**单聊事件**中勾选**C2C消息事件**，再在**群事件**中勾选**群消息事件AT事件**，确认配置

![c2c](https://img.alicdn.com/imgextra/i4/O1CN01HDSoX91iOAbTVULZf_!!6000000004402-2-tps-4082-2126.png)

![at](https://img.alicdn.com/imgextra/i4/O1CN01UJn1AK1UKatKkjMv4_!!6000000002499-2-tps-4082-2126.png)

4. 选择**沙箱配置**中的**消息列表配置项**，点击**添加成员**，选择添加**自己**

![1](https://img.alicdn.com/imgextra/i4/O1CN01BSdkXl1ckG0dC7vH9_!!6000000003638-2-tps-4082-2126.png)

![1](https://img.alicdn.com/imgextra/i4/O1CN01LGYUMe1la1hmtcuyY_!!6000000004834-2-tps-4082-2126.png)

5. 在**开发管理**中获取**AppID**和**AppSecret**（即 ClientSecret），填入 `agent.json`，方式见下方填写 agent.json。在**IP白名单**中添加一个IP。

   > **提示：** 如果使用魔搭创空间部署Minions，QQ频道的IP白名单应填写：`47.92.200.108`

![1](https://img.alicdn.com/imgextra/i4/O1CN012UQWI21cnvBAUcz54_!!6000000003646-2-tps-4082-2126.png)

6. 在沙箱配置中，使用QQ扫码，将机器人添加到消息列表

![1](https://img.alicdn.com/imgextra/i3/O1CN01r1OvPy1kcwc30w32K_!!6000000004705-2-tps-4082-2126.png)

### 填写 agent.json

在智能体工作区的 `agent.json`（如 `~/.minions/workspaces/default/agent.json`）里找到 `channels.qq`，把上面两个值分别填进 `app_id` 和 `client_secret`：

```json
"qq": {
  "enabled": true,
  "bot_prefix": "[BOT]",
  "app_id": "你的 AppID",
  "client_secret": "你的 AppSecret",
  "markdown_enabled": false,
  "max_reconnect_attempts": -1
}
```

**QQ 专属字段说明：**

| 字段                     | 类型   | 默认值       | 说明                                      |
| ------------------------ | ------ | ------------ | ----------------------------------------- |
| `app_id`                 | string | `""`（必填） | QQ 机器人 App ID                          |
| `client_secret`          | string | `""`（必填） | QQ 机器人 Client Secret（即 AppSecret）   |
| `markdown_enabled`       | bool   | `false`      | 是否启用 Markdown 消息（需 QQ 平台授权）  |
| `max_reconnect_attempts` | int    | `-1`         | WebSocket 最大重连次数（`-1` = 无限重连） |

> **注意：** 这里填的是 **AppID** 和 **AppSecret** 两个字段，不是拼成一条 Token。

或者也可以在console前端填写：

![console](https://img.alicdn.com/imgextra/i3/O1CN01FJrXGd1dNBgbrPZMf_!!6000000003723-2-tps-3822-2070.png)

---

## 企业微信

### 创建新企业

个人使用者可以访问[企业微信官网](https://work.weixin.qq.com)注册账号，创建新企业，成为企业管理员。

![创建企业](https://img.alicdn.com/imgextra/i2/O1CN01Xg8B3i1EQWAKt5xj0_!!6000000000346-2-tps-2938-1588.png)

填写企业信息与管理员信息，并绑定微信账号

![新建账号](https://img.alicdn.com/imgextra/i4/O1CN01uRF1Mv1TX87bOQ045_!!6000000002391-2-tps-1538-905.png)

注册成功之后即可登陆企业微信开始使用。

若已经有企业微信账号或是企业普通员工，可以直接在当前企业创建API模式机器人。

### 创建机器人

可在工作台点击智能机器人-创建机器人，选择API模式创建-通过长链接配置

![创建机器人1](https://img.alicdn.com/imgextra/i3/O1CN01lcA2rX1fm2P19SLcB_!!6000000004048-2-tps-1440-814.png)

![新建机器人2](https://img.alicdn.com/imgextra/i1/O1CN014R3a0f1mnb3qbycMV_!!6000000004999-2-tps-1440-814.png)

![新建机器人3](https://img.alicdn.com/imgextra/i4/O1CN01kZDNVk1ugHf73ybs2_!!6000000006066-2-tps-2938-1594.png)

获取`Bot ID`和`Secret`

![新建机器人4](https://img.alicdn.com/imgextra/i1/O1CN01Znm7aQ1Tfpe5Ha9WL_!!6000000002410-2-tps-1482-992.png)

### 绑定bot

可以在Console或是智能体工作区的 `agent.json` 填写Bot ID和Secret绑定bot

**方法一**在console填写

![console](https://img.alicdn.com/imgextra/i1/O1CN01pyx6Ma1YMCl1kMnje_!!6000000003044-2-tps-3822-2070.png)

**方法二**在 `agent.json` 填写（如 `~/.minions/workspaces/default/agent.json`）

找到`wecom`，填写对应信息：

```json
"wecom": {
  "enabled": true,
  "bot_prefix": "[BOT]",
  "dm_policy": "open",
  "group_policy": "open",
  "bot_id": "your bot_id",
  "secret": "your secret",
  "media_dir": "~/.minions/media",
  "max_reconnect_attempts": -1
}
```

**企业微信专属字段说明：**

| 字段                     | 类型   | 默认值             | 说明                                      |
| ------------------------ | ------ | ------------------ | ----------------------------------------- |
| `bot_id`                 | string | `""`（必填）       | 企业微信机器人 Bot ID                     |
| `secret`                 | string | `""`（必填）       | 企业微信机器人 Secret                     |
| `media_dir`              | string | `~/.minions/media` | 媒体文件（图片、文件等）下载目录          |
| `max_reconnect_attempts` | int    | `-1`               | WebSocket 最大重连次数（`-1` = 无限重连） |

### 在企业微信开始与机器人聊天

![开始使用](https://img.alicdn.com/imgextra/i3/O1CN01ZsmpYr1tq4ViIbO80_!!6000000005952-2-tps-1308-1130.png)

---

## 微信个人（iLink）

微信 iLink Bot 频道允许通过**个人微信账号**运行 AI 机器人，无需企业资质，使用官方 [iLink Bot HTTP API](https://weixin.qq.com/cgi-bin/readtemplate?t=ilink/chatbot) 协议。

> **注意**：微信个人 Bot（iLink 协议）目前仍处于内测阶段，需申请接入资格后方可使用。

### 工作原理

- **登录方式**：首次使用时扫描二维码授权，Token 自动持久化到本地文件（默认 `~/.minions/wechat_bot_token`），后续启动无需重复扫码。
- **消息接收**：通过 HTTP 长轮询（`getupdates`）持续拉取新消息，支持文本、图片、语音（ASR 转录）和文件。
- **消息发送**：通过 `sendmessage` 接口回复用户，当前仅支持文本（iLink API 限制）。

### 扫码登录（推荐通过 Console）

1. 在 Minions Web Console 中进入 **设置 → 通道 → 微信个人（iLink）**。
2. 点击 **获取登录二维码**，等待二维码显示。
3. 用手机微信扫描二维码并确认授权。
4. 扫码成功后，Bot Token 会自动填入表单，点击 **保存** 即可。

### 在配置文件中填写

也可直接在智能体工作区的 `agent.json`（如 `~/.minions/workspaces/default/agent.json`）中配置：

```json
"wechat": {
  "enabled": true,
  "bot_prefix": "[BOT]",
  "bot_token": "your_bot_token",
  "bot_token_file": "~/.minions/wechat_bot_token",
  "base_url": "",
  "media_dir": "~/.minions/media",
  "dm_policy": "open",
  "group_policy": "open"
}
```

**微信个人专属字段说明：**

| 字段             | 类型   | 默认值                        | 说明                                                |
| ---------------- | ------ | ----------------------------- | --------------------------------------------------- |
| `bot_token`      | string | `""`                          | 扫码登录后获取的 Bearer Token；留空则启动时引导扫码 |
| `bot_token_file` | string | `~/.minions/wechat_bot_token` | Token 持久化路径，下次启动自动读取                  |
| `base_url`       | string | 官方默认地址                  | iLink API 地址，一般留空使用默认值                  |
| `media_dir`      | string | `~/.minions/media`            | 接收到的图片、文件保存目录                          |

### 环境变量方式

也可通过环境变量配置：

```bash
WECHAT_CHANNEL_ENABLED=1
WECHAT_BOT_TOKEN=your_bot_token
WECHAT_BOT_TOKEN_FILE=~/.minions/wechat_bot_token
WECHAT_MEDIA_DIR=~/.minions/media
WECHAT_DM_POLICY=open
WECHAT_GROUP_POLICY=open
```

---

## 腾讯元宝（Yuanbao）

元宝频道通过 protobuf WebSocket 连接腾讯元宝 AI 助手平台，支持私聊和群聊，支持图片/文件发送。

### 创建 Bot 并配置

1. 打开腾讯元宝，点击 **我的Bot** → **创建Bot**。

   ![创建Bot](https://img.alicdn.com/imgextra/i3/O1CN01ChYAcN1L0b4pj7ODV_!!6000000001237-2-tps-2112-1440.png)

2. 在 Bot 设置中找到 **方式2**，获取 **AppID** 和 **AppSecret**，填入 Minions 的频道设置中，点击 **我已操作**。

   ![AppID 和 AppSecret](https://img.alicdn.com/imgextra/i2/O1CN01F4vbLs29ID63r4cGf_!!6000000008044-2-tps-2112-1440.png)

**配置示例：**

```json
"yuanbao": {
  "enabled": true,
  "app_id": "你的 AppID",
  "app_secret": "你的 AppSecret"
}
```

**元宝专属字段说明：**

| 字段         | 类型   | 默认值                    | 说明                 |
| ------------ | ------ | ------------------------- | -------------------- |
| `app_id`     | string | `""`（必填）              | 元宝平台的 AppID     |
| `app_secret` | string | `""`（必填）              | 元宝平台的 AppSecret |
| `api_domain` | string | `bot.yuanbao.tencent.com` | REST API 域名        |

---

## 附录

### 配置总览

| 频道       | 配置键     | 必填/主要字段                                                                                          |
| ---------- | ---------- | ------------------------------------------------------------------------------------------------------ |
| 钉钉       | dingtalk   | client_id, client_secret, message_type, card_template_id, card_template_key, robot_code                |
| 飞书       | feishu     | app_id, app_secret；可选 encrypt_key, verification_token, media_dir                                    |
| QQ         | qq         | app_id, client_secret                                                                                  |
| 企业微信   | wecom      | bot_id, secret；可选 media_dir                                                                         |
| 微信个人   | wechat     | bot_token（或扫码登录）；可选 bot_token_file, base_url, media_dir                                      |
| 元宝       | yuanbao    | app_id, app_secret；可选 api_domain, media_dir                                                         |

所有频道均支持本页顶部「通用字段」中介绍的访问控制字段（`dm_policy`、`group_policy`、`allow_from`、`deny_message`、`require_mention`）。

各频道字段与完整结构见上文表格及 [配置与工作目录](./config)。

### 通用字段说明

所有频道都支持以下通用字段：

| 字段                   | 类型     | 默认值   | 说明                                                    |
| ---------------------- | -------- | -------- | ------------------------------------------------------- |
| `enabled`              | bool     | `false`  | 是否启用该频道                                          |
| `bot_prefix`           | string   | `""`     | 机器人回复前缀（如 `[BOT]`）                            |
| `filter_tool_messages` | bool     | `false`  | 是否过滤工具调用/输出消息                               |
| `filter_thinking`      | bool     | `false`  | 是否过滤思考/推理内容                                   |
| `dm_policy`            | string   | `"open"` | 私聊访问策略：`"open"`（开放）/ `"allowlist"`（白名单） |
| `group_policy`         | string   | `"open"` | 群聊访问策略：`"open"`（开放）/ `"allowlist"`（白名单） |
| `allow_from`           | string[] | `[]`     | 白名单列表（当 policy 为 `"allowlist"` 时生效）         |
| `deny_message`         | string   | `""`     | 拒绝访问时的提示消息                                    |
| `require_mention`      | bool     | `false`  | 是否需要 @机器人 才响应                                 |

### 多模态消息支持

不同频道对「文本 / 图片 / 视频 / 音频 / 文件」的**接收**（用户发给机器人）与**发送**（机器人回复用户）支持程度如下。
「✓」= 已支持；「🚧」= 施工中（可实现但尚未实现）；「✗」= 不支持（该频道本身无法支持）。

| 频道       | 接收文本 | 接收图片 | 接收视频 | 接收音频 | 接收文件 | 发送文本 | 发送图片 | 发送视频 | 发送音频 | 发送文件 |
| ---------- | -------- | -------- | -------- | -------- | -------- | -------- | -------- | -------- | -------- | -------- |
| 钉钉       | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        |
| 飞书       | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        |
| QQ         | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        |
| 企业微信   | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        |
| 微信个人   | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        |
| 元宝       | ✓        | ✓        | ✗        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        | ✓        |

说明：

- **钉钉**：接收支持富文本与单文件（downloadCode），发送通过会话 webhook 支持图片 / 语音 / 视频 / 文件。
- **飞书**：WebSocket 长连接收消息，Open API 发送；支持文本 / 图片 / 文件收发；群聊时在消息 metadata 中带 `feishu_chat_id`、`feishu_message_id` 便于下游去重与群上下文。
- **QQ**：接收侧附件解析为多模态、发送侧真实媒体均为 🚧 施工中，当前仅文本 + 链接形式。
- **企业微信**：WebSocket 长连接接收，markdown/template_card 发送；支持接收和发送文本、图片、语音、视频和文件。
- **微信个人（iLink）**：HTTP 长轮询接收，支持文本、图片（AES-128-ECB 解密）、语音（ASR 转录文字）、文件和视频；发送支持文本、图片、文件和视频；音频文件（如 MP3）因 iLink API 限制暂不支持。
- **元宝**：支持接收文本、图片、音频；发送支持文本、图片、视频、音频和文件（通过 COS CDN 上传）；平台不转发视频消息给 Bot。

### 通过 HTTP 修改配置

服务运行时可读写频道配置，修改会写回 `agent.json` 并自动生效：

- `GET /config/channels` — 获取全部频道
- `PUT /config/channels` — 整体覆盖
- `GET /config/channels/{channel_name}` — 获取单个（如 `dingtalk`、`feishu`）
- `PUT /config/channels/{channel_name}` — 更新单个

---

## 扩展渠道

如需接入新平台（如飞书、企业微信等），可基于 **BaseChannel** 实现子类，无需改核心源码。

### 数据流与队列

- **ChannelManager** 为每个启用队列的 channel 维护一个队列；收到消息时 channel 调用 **`self._enqueue(payload)`**（由 manager 启动时注入），manager 在消费循环中再调用 **`channel.consume_one(payload)`**。
- 基类已实现 **默认 `consume_one`**：把 payload 转成 `AgentRequest`、跑 `_process`、对每条完成消息调用 `send_message_content`、错误时调用 `_on_consume_error`。多数渠道只需实现「入口→请求」和「回复→出口」，不必重写 `consume_one`。

### 子类必须实现

| 方法                                                    | 说明                                                                                                                                       |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `build_agent_request_from_native(self, native_payload)` | 将渠道原生消息转为 `AgentRequest`（使用 runtime 的 `Message`/`TextContent`/`ImageContent` 等），并设置 `request.channel_meta` 供发送使用。 |
| `from_env` / `from_config`                              | 从环境变量或配置构建实例。                                                                                                                 |
| `async start()` / `async stop()`                        | 生命周期（建连、订阅、清理等）。                                                                                                           |
| `async send(self, to_handle, text, meta=None)`          | 发送一条文本（及可选附件）。                                                                                                               |

### 基类提供的通用能力

- **消费流程**：`_payload_to_request`（payload→AgentRequest）、`get_to_handle_from_request`（解析发送目标，默认 `user_id`）、`get_on_reply_sent_args`（回调参数）、`_before_consume_process`（处理前钩子，如保存 receive_id）、`_on_consume_error`（错误时发送，默认 `send_content_parts`）、可选 **`refresh_webhook_or_token`**（空实现，子类需刷新 token 时覆盖）。
- **辅助**：`resolve_session_id`、`build_agent_request_from_user_content`、`_message_to_content_parts`、`send_message_content`、`send_content_parts`、`to_handle_from_target`。

需要不同消费逻辑时（如控制台打印、钉钉合并去抖）再覆盖 **`consume_one`**；需要不同发送目标或回调参数时覆盖 **`get_to_handle_from_request`** / **`get_on_reply_sent_args`**。

### 示例：最简渠道（仅文本）

只处理文本、使用 manager 队列时，不必实现 `consume_one`，基类默认即可：

```python
# my_channel.py
from agentscope_runtime.engine.schemas.agent_schemas import TextContent, ContentType
from minions.app.channels.base import BaseChannel
from minions.app.channels.schema import ChannelType

class MyChannel(BaseChannel):
    channel: ChannelType = "my_channel"

    def __init__(self, process, enabled=True, bot_prefix="", **kwargs):
        super().__init__(process, on_reply_sent=kwargs.get("on_reply_sent"))
        self.enabled = enabled
        self.bot_prefix = bot_prefix

    @classmethod
    def from_config(cls, process, config, on_reply_sent=None, show_tool_details=True):
        return cls(process=process, enabled=getattr(config, "enabled", True),
                   bot_prefix=getattr(config, "bot_prefix", ""), on_reply_sent=on_reply_sent)

    @classmethod
    def from_env(cls, process, on_reply_sent=None):
        return cls(process=process, on_reply_sent=on_reply_sent)

    def build_agent_request_from_native(self, native_payload):
        payload = native_payload if isinstance(native_payload, dict) else {}
        channel_id = payload.get("channel_id") or self.channel
        sender_id = payload.get("sender_id") or ""
        meta = payload.get("meta") or {}
        session_id = self.resolve_session_id(sender_id, meta)
        text = payload.get("text", "")
        content_parts = [TextContent(type=ContentType.TEXT, text=text)]
        request = self.build_agent_request_from_user_content(
            channel_id=channel_id, sender_id=sender_id, session_id=session_id,
            content_parts=content_parts, channel_meta=meta,
        )
        request.channel_meta = meta
        return request

    async def start(self):
        pass

    async def stop(self):
        pass

    async def send(self, to_handle, text, meta=None):
        # 调用你的 HTTP API 等发送
        pass
```

收到消息时组一个 native 字典并入队（`_enqueue` 由 manager 注入）：

```python
native = {
    "channel_id": "my_channel",
    "sender_id": "user_123",
    "text": "你好",
    "meta": {},
}
self._enqueue(native)
```

### 示例：多模态（文本 + 图片/视频/音频/文件）

在 `build_agent_request_from_native` 里把附件解析成 runtime 的 content，再调用 `build_agent_request_from_user_content`：

```python
from agentscope_runtime.engine.schemas.agent_schemas import (
    TextContent, ImageContent, VideoContent, AudioContent, FileContent, ContentType,
)

def build_agent_request_from_native(self, native_payload):
    payload = native_payload if isinstance(native_payload, dict) else {}
    channel_id = payload.get("channel_id") or self.channel
    sender_id = payload.get("sender_id") or ""
    meta = payload.get("meta") or {}
    session_id = self.resolve_session_id(sender_id, meta)
    content_parts = []
    if payload.get("text"):
        content_parts.append(TextContent(type=ContentType.TEXT, text=payload["text"]))
    for att in payload.get("attachments") or []:
        t = (att.get("type") or "file").lower()
        url = att.get("url") or ""
        if not url:
            continue
        if t == "image":
            content_parts.append(ImageContent(type=ContentType.IMAGE, image_url=url))
        elif t == "video":
            content_parts.append(VideoContent(type=ContentType.VIDEO, video_url=url))
        elif t == "audio":
            content_parts.append(AudioContent(type=ContentType.AUDIO, data=url))
        else:
            content_parts.append(FileContent(type=ContentType.FILE, file_url=url))
    if not content_parts:
        content_parts = [TextContent(type=ContentType.TEXT, text="")]
    request = self.build_agent_request_from_user_content(
        channel_id=channel_id, sender_id=sender_id, session_id=session_id,
        content_parts=content_parts, channel_meta=meta,
    )
    request.channel_meta = meta
    return request
```

### 通过插件添加自定义频道

自定义频道现在通过**插件系统**注册。完整教程请参阅
[插件系统 — 示例 8：注册自定义消息频道](./plugins)。

添加自定义频道的步骤：

1. 创建插件，在 `plugin.json` 中设置 `type: "channel"`
2. 实现一个 `BaseChannel` 子类，设置唯一的 `channel` 类属性
3. 在插件的 `register()` 方法中调用 `api.register_channel(...)`
4. 使用 `minions plugin install <路径>` 安装

插件频道会在控制台 UI 中与内置频道并列显示，完整支持启用/禁用、配置字段和访问控制。

如果频道需要 Webhook HTTP 端点，请在同一个插件中使用 `api.register_http_router()`
在 `/api` 下挂载路由。

> **从 `custom_channels/` 迁移**：旧的 `custom_channels/` 目录和
> `minions channels install/add/remove` CLI 命令已被移除。如果你有现存的
> 自定义频道在 `custom_channels/` 下，请按以下步骤迁移到插件系统：
>
> 1. 创建插件目录，编写 `plugin.json`（设置 `"type": "channel"`）
> 2. 将 `BaseChannel` 子类移入插件目录
> 3. 创建 `plugin.py`，在其中调用 `api.register_channel(...)` 注册频道类
>    和 `config_fields`
> 4. 如果频道之前使用了 `register_app_routes(app)`，请替换为
>    `api.register_http_router(router, prefix="/your-channel")`，使用
>    FastAPI `APIRouter`
> 5. 安装插件：`minions plugin install <路径>`
> 6. 删除 `custom_channels/` 下的旧模块

---

## 相关页面

- [项目介绍](./intro) — 这个项目可以做什么
- [快速开始](./quickstart) — 安装与首次启动
- [心跳](./heartbeat) — 定时自检/摘要
- [CLI](./cli) — init、app、cron、clean
- [配置与工作目录](./config) — 配置文件与工作目录
