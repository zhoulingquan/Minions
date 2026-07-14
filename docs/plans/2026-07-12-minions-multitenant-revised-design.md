# Minions 企业多租户改造计划（生产安全修订版）

> 版本：2.0 Proposed  
> 日期：2026-07-12  
> 适用代码库：当前 Minions（`src/minions`）  
> 适用场景：中小企业私有化部署、管理员统一接入模型和资源、用户自管 Agent  
> 关联方案：SAGE 多租户企业经验与成长引擎

## 1. 修订结论

本修订稿保留原方案中有效的业务边界：管理员创建账号、统一配置 Provider、管理全局 Skill/MCP/Plugin 资源、按用户授权、用户管理自己的 Agent、Agent 可安全复制共享，并保留单用户兼容路径。

同时修正以下生产阻断问题：

1. 中间件注册顺序可能导致 TenantGuard 在 `agent_id` 解析前执行；
2. 只在 HTTP 路由层鉴权，无法覆盖 Cron、频道、ACP、WebSocket 和内部调用；
3. 使用可修改的 username 作为 Agent 和目录的稳定身份；
4. `auth.json` 与 `config.json` 双写用户和密码信息；
5. 固定初始化账号 `admin/123456`；
6. 租户模式仍允许 localhost 免认证；
7. Agent 共享复制 sessions、业务数据和 credentials；
8. Entitlement 关闭后所有普通用户自动获得全部资源；
9. JSON 文件无法保证多管理员并发更新的一致性；
10. 缺少审计、配额、离职、撤权、密钥引用和事务恢复。

### 1.1 Go/No-Go

- 可以按本修订稿进入实施；
- 不应直接执行旧 WBS；
- 必须先完成阶段 M0 的身份与授权基础，再开发用户界面和 Agent 共享；
- SAGE 与多租户控制面共用身份和 PostgreSQL，但数据权限与工具授权分开管理。

## 2. 场景与边界

### 2.1 当前目标

第一阶段主要服务“一个企业内多个用户”，但所有核心表都保留 `tenant_id`，避免未来需要承载多个企业时再次重构。

```text
Tenant（企业）
  ├── Users（员工）
  ├── Teams（可选部门）
  ├── Agents（业务 Agent）
  ├── Resources（Skill/MCP/Tool/Model）
  └── SAGE（企业经验数据）
```

私有化单企业部署创建一个默认 Tenant；SaaS 或集团部署可创建多个 Tenant。

### 2.2 硬约束

- 不损失 ReAct、Loop、Sandbox、Tool Guard、渠道、MCP、ACP、Coding Mode 等现有能力；
- 所有安全决定默认拒绝，不因字段缺失而放行；
- 认证、授权和 Agent 归属必须在服务层再次校验；
- Provider/MCP/API Key 不复制到用户目录，只保存 Secret Reference；
- SAGE 私有数据不随 Agent 默认共享；
- 单用户兼容只适用于尚未产生多用户数据的实例；
- 每个工作包都有独立测试和回滚方式；
- 改动使用当前 `src/minions` 路径，不再使用旧 `src/qwenpaw` 名称。

## 3. 方案取舍

| 方案 | 优点 | 缺点 | 选择 |
|---|---|---|---|
| JSON + 路由中间件 | 改动少 | 并发、越权、审计和恢复风险高 | 放弃 |
| SQLite 控制面 | 部署简单 | 多进程与高可用能力有限 | 开发/小型试点 |
| PostgreSQL 控制面 | 事务、并发、审计、RLS、可与 SAGE 共用 | 多一个基础服务 | **生产推荐** |
| 独立 IAM + 多微服务 | 能力完整 | 对中小企业过重 | 暂不采用 |

生产模式采用模块化单体 + PostgreSQL。控制面、SAGE 和审计可以共用一个 PostgreSQL 实例，但使用不同 Schema 和数据库角色。

## 4. 不可变身份模型

### 4.1 核心实体

```python
class Tenant:
    tenant_id: UUID
    slug: str
    display_name: str
    status: str  # active | suspended | deleted

class UserAccount:
    user_id: UUID
    tenant_id: UUID
    username: str
    display_name: str
    password_hash: str
    status: str  # invited | active | disabled | deleted
    token_version: int

class AgentRef:
    agent_uid: UUID
    tenant_id: UUID
    owner_user_id: UUID
    slug: str
    display_name: str
    workspace_dir: str
    kind: str  # private | builtin | copied
    status: str
```

`username`、Agent 名和目录均可修改；数据库关联只能使用 UUID。

### 4.2 外部标识

- UI 可继续显示 `alice_coder`；
- API 主路径建议使用 `agent_uid`；
- 兼容 API 可接受旧 `agent_id`，先解析为 `agent_uid`；
- 路由 slug 不得直接参与文件路径拼接；
- username 和 slug 只允许规范化字符、限定长度，并拒绝保留名称。

### 4.3 工作区布局

```text
WORKING_DIR/workspaces/
└── {tenant_id}/
    └── {user_id}/
        └── {agent_uid}/
            ├── agent.json
            ├── AGENTS.md
            ├── SOUL.md
            ├── PROFILE.md
            ├── skills/
            ├── drivers/
            └── sessions/
```

目录服务只能接收 UUID，并使用 `resolve()` + `relative_to()` 验证目标仍在租户根目录内。禁止跟随工作区中的外部符号链接进行复制或备份。

## 5. Principal：统一执行主体

所有入口统一生成不可变 `Principal`：

```python
@dataclass(frozen=True)
class Principal:
    tenant_id: UUID
    user_id: UUID
    role_ids: tuple[UUID, ...]
    permissions: frozenset[str]
    source: str       # web/channel/cron/acp/internal
    session_id: str
    token_id: str | None
    service_id: str | None
```

### 5.1 Principal 来源

| 入口 | Principal 生成方式 |
|---|---|
| Web/REST | JWT 认证后生成 |
| WebSocket/SSE | 一次性握手票据生成 |
| 渠道消息 | 渠道绑定表映射到 tenant/user |
| Cron/Heartbeat | 任务所有者 + 受限 service principal |
| ACP/内部 Agent | 调用方 Agent + 原始用户委托链 |
| 管理任务 | 专用 admin/service principal |

不得使用匿名字符串、agent 名或 request.state 中可选字段代替 Principal。

## 6. 认证设计

### 6.1 单一身份真源

多租户模式下，用户、密码、角色、刷新会话和禁用状态全部进入 PostgreSQL。`config.json` 只保存部署功能开关，不保存用户或密码哈希；`auth.json` 仅作为迁移来源，迁移完成后停止写入。

建议表：

- `tenant`；
- `user_account`；
- `user_role_binding`；
- `auth_session`；
- `password_history`；
- `invitation`；
- `login_audit`。

### 6.2 密码与 Token

- 密码使用 Argon2id；
- Access Token 默认 15 分钟；
- Refresh Token 默认 7 天，数据库仅保存哈希；
- JWT 包含 `tenant_id/user_id/token_version/jti/iss/aud/iat/exp`；
- 修改密码、禁用用户、角色变更时递增 `token_version`；
- 每次请求校验用户未禁用、Tenant 未停用；
- 普通 HTTP 禁止 query parameter 传 Token；WebSocket 使用短时一次性 ticket；
- 登录、重置密码和邀请接口实施速率限制。

### 6.3 管理员引导

禁止固定默认密码。初始化方式：

1. 优先读取环境变量或 Secret Store；
2. 若未提供，生成一次性高强度随机密码；
3. 写入权限 `0600` 的 bootstrap 文件，并仅记录文件路径；
4. 首次登录必须修改密码；
5. 未修改前只允许访问修改密码和退出接口；
6. 生产模式也可配置为“无管理员凭据则拒绝启动”。

### 6.4 关闭 localhost 免认证

当 `tenancy.mode != "legacy"` 时：

- 忽略 `allow_no_auth_hosts`；
- 所有 `/api`、WebSocket、SSE 和文件下载均要求身份；
- 仅健康检查和登录接口公开；
- 可信代理列表由部署配置显式指定；
- 不信任来自非可信代理的 `X-Forwarded-For`。

## 7. 授权设计

### 7.1 权限而非二元角色

UI 可以继续显示 admin/user，但后端使用权限：

```text
tenant.users.manage
tenant.resources.manage
tenant.providers.manage
tenant.audit.read
agent.create
agent.read
agent.update
agent.delete
agent.share
resource.skill.use
resource.mcp.use
resource.tool.use
sage.case.read
sage.playbook.publish
```

内置角色：

- `system_admin`：部署运维，不默认读取业务正文；
- `tenant_admin`：企业账号与授权管理；
- `resource_admin`：Provider/Skill/MCP/Plugin 管理；
- `business_owner`：SAGE 团队经验审批；
- `user`：管理自己的 Agent 和已授权资源。

### 7.2 授权决策

统一接口：

```python
decision = policy.authorize(
    principal=principal,
    action="agent.update",
    resource=AgentResource(agent_uid),
)
decision.require_allowed()
```

授权同时检查：

- tenant 是否一致；
- 用户状态和角色；
- Agent 所有权或显式 Grant；
- 资源 Entitlement；
- 操作类型；
- 数据敏感级别；
- 委托链和来源入口。

### 7.3 服务层强制校验

以下服务必须强制接收 Principal，不能提供无 Principal 重载：

- `MultiAgentManager.get_agent`；
- Agent 创建、修改、删除和共享；
- Workspace 文件读写；
- Skill/MCP/Tool 启用；
- Provider 选择；
- Cron、频道和 ACP 调度；
- Backup 导入、导出和恢复；
- SAGE 查询、发布和删除。

路由中间件只是第一层，服务层和数据访问层是最终安全边界。

## 8. 中间件执行顺序

中间件只负责构建上下文和粗粒度拒绝，不能承担所有资源授权。

目标执行顺序：

```text
AuthMiddleware
  -> AgentContextMiddleware
  -> TenantBoundaryMiddleware
  -> Route Dependency
  -> Domain Service Policy
  -> Repository tenant filter / RLS
```

Starlette 后注册的中间件先执行，因此建议注册顺序：

```python
app.add_middleware(TenantBoundaryMiddleware)  # 最先注册，较内层
app.add_middleware(AgentContextMiddleware)
app.add_middleware(AuthMiddleware)            # 最后注册，最先执行
```

Entitlement 不再通过解析 URL 和消费 Request Body 的通用中间件实现。每个受控路由使用明确依赖，同时领域服务再次校验：

```python
@router.post("/skills/{resource_id}/enable")
async def enable_skill(
    resource_id: UUID,
    principal: Principal = Depends(require_principal),
    _: None = Depends(require_permission("resource.skill.use")),
): ...
```

## 9. 资源目录与 Entitlement

### 9.1 稳定资源 ID

资源授权不能只保存名称，改为：

```text
resource_id
tenant_id / global
resource_type      skill | mcp | tool | model | plugin
name
version
status
risk_level
manifest_hash
```

Entitlement 保存：

```text
subject_type       user | team | role
subject_id
resource_id
version_constraint
actions            use | configure | distribute
expires_at
granted_by
```

### 9.2 安全默认值

- 多租户模式始终执行 Entitlement；
- 找不到授权时默认拒绝；
- `entitlements.enabled=False` 只允许在 legacy 单用户模式使用；
- Tenant 开启后不得通过关闭 Entitlement 给所有人放权；
- 授权撤销后立即失效，并清除相关缓存。

### 9.3 Provider 和密钥

- 普通用户只能看到 Provider 名称、可用模型和状态；
- API Key、OAuth Token、MCP 凭据存入现有 Secret Store 或企业密钥系统；
- Agent 配置仅保存 Secret Reference；
- API 响应、日志、备份预览和共享包均不得返回密钥；
- 密钥读取需要资源权限并记录审计事件。

## 10. Agent 归属和可见性

### 10.1 Agent 类型

| 类型 | 所有者 | 行为 |
|---|---|---|
| private | 用户 | 仅所有者和显式授权者可操作 |
| builtin | system | 只读模板，可复制实例化 |
| copied | 目标用户 | 共享产生的独立私有副本 |

不再使用 `visibility="shared"` 表示一个实际共享实例。共享结果是新的 `copied` Agent；源 Agent 只记录审计关系。

### 10.2 Builtin 只读

只读判断基于业务 action，而不是简单判断 HTTP method。读取型 POST、导出操作和模拟执行需逐项定义权限。

## 11. Agent 安全共享

### 11.1 共享原则

共享 Agent 是“创建经过过滤的新 Agent”，不是复制完整工作区。

默认允许复制：

- AGENTS/SOUL/PROFILE 等非敏感人设文件；
- agent.json 中允许共享的配置；
- 目标用户已授权资源的 ID 和版本引用；
- SAGE 已发布且标记 portable 的 Playbook 引用。

默认禁止复制：

- sessions、聊天历史、工具结果；
- SAGE 迹证、私有案例、用户偏好、洞见候选；
- credentials.yaml、API Key、OAuth Token；
- 项目文件、客户资料和附件；
- 未知文件、外部符号链接和执行缓存。

### 11.2 共享事务

```text
创建 share_operation（pending）
  -> 锁定源 Agent 版本
  -> 获取目标 Entitlement 快照
  -> 在 staging 目录按白名单生成副本
  -> 扫描秘密、路径、权限和 manifest
  -> 提交前再次检查目标用户和授权
  -> 数据库创建 AgentRef
  -> staging 原子 rename 为正式目录
  -> share_operation=completed + 审计
```

任一步失败都删除 staging 并保留不含敏感正文的失败记录。接口使用 idempotency key，重复请求返回同一结果。

### 11.3 SAGE 经验共享

私有经验只能通过 `SageBundle` 单独发布：选择内容、脱敏、审批、目标数据权限检查，然后在目标作用域创建新对象。Agent 共享服务不得直接读取或复制 SAGE 私有表。

## 12. 数据持久化

建议 PostgreSQL Schema：

```text
iam.tenant
iam.user_account
iam.auth_session
iam.role
iam.permission
iam.role_binding

control.agent_registry
control.resource_catalog
control.entitlement
control.share_operation
control.channel_binding
control.job_owner

audit.security_event
audit.admin_event
audit.data_access_event

sage.*
```

### 12.1 一致性

- 配置变更使用事务和乐观锁版本；
- 文件工作区变更使用 staging + 原子 rename；
- 数据库保存工作区 manifest hash；
- 后台修复任务扫描孤儿目录和失效引用；
- 所有写操作支持 idempotency key；
- 不使用多个 JSON 文件模拟跨实体事务。

## 13. 管理 API

### 13.1 Tenant 与用户

| 方法 | 路径 | 权限 |
|---|---|---|
| GET | `/api/admin/tenants` | system_admin |
| POST | `/api/admin/tenants` | system_admin |
| GET | `/api/admin/users` | tenant.users.manage |
| POST | `/api/admin/users` | tenant.users.manage |
| PATCH | `/api/admin/users/{user_id}` | tenant.users.manage |
| POST | `/api/admin/users/{user_id}/reset-password` | tenant.users.manage |
| POST | `/api/admin/users/{user_id}/disable` | tenant.users.manage |
| POST | `/api/admin/users/{user_id}/offboard` | tenant.users.manage |

### 13.2 资源与授权

| 方法 | 路径 | 权限 |
|---|---|---|
| POST | `/api/admin/resources/skills/install` | tenant.resources.manage |
| POST | `/api/admin/resources/mcp/register` | tenant.resources.manage |
| POST | `/api/admin/resources/plugins/install` | tenant.resources.manage |
| GET | `/api/admin/entitlements` | tenant.resources.manage |
| PUT | `/api/admin/entitlements/{subject_id}/{resource_id}` | tenant.resources.manage |
| DELETE | `/api/admin/entitlements/{subject_id}/{resource_id}` | tenant.resources.manage |

### 13.3 Agent

- 用户只能列出自己所有或被显式授权的 Agent；
- 创建时 owner 从 Principal 获取，不接受客户端提交 owner；
- 更新、删除、运行和共享都在服务层检查 AgentResource；
- system_admin 的跨租户访问必须显式指定 Tenant，并记录 break-glass 审计。

## 14. 审计、配额与离职

### 14.1 审计

必须记录：

- 登录成功/失败、Token 撤销、密码与角色变更；
- 用户创建、禁用、删除和恢复；
- Agent 创建、运行、更新、共享和删除；
- Skill/MCP/Tool/Provider 授权与撤销；
- Secret 读取和轮换；
- Backup 导入、导出和恢复；
- SAGE 查询、发布、删除和管理员访问。

审计日志追加写，正文与密钥不进入日志，并配置独立保留期限。

### 14.2 配额

按 Tenant/User/Agent 配置：

- 并发任务数；
- 每日模型 Token 与费用；
- 存储空间和上传大小；
- Cron 数量和执行频率；
- Agent、Skill、MCP 数量；
- 共享操作速率。

### 14.3 用户禁用与离职

禁用用户时立即：

1. 递增 token_version，撤销 Refresh Session；
2. 停止其活动 Agent、Cron、频道和后台任务；
3. 禁止新的 SAGE 查询和资源使用；
4. 保留数据等待管理员选择转移、归档或删除；
5. 对 Agent、项目和 Playbook 所有权执行转移工作流；
6. 记录完整审计。

## 15. 兼容与迁移

### 15.1 模式

```text
legacy       当前单用户行为
migrating    只允许管理员执行迁移，普通写入暂停
tenant       多租户生产行为
```

不再使用两个互相独立的布尔开关表达安全状态。

### 15.2 激活约束

- 初始默认 `legacy`；
- 迁移成功后进入 `tenant`；
- 一旦创建第二个用户或产生多租户数据，不允许直接切回 `legacy`；
- 回滚代码版本必须通过数据库备份恢复，而不是关闭鉴权；
- 强制降级需要离线维护工具和显式数据确认。

### 15.3 迁移步骤

1. 对 auth/config/workspaces/secret 做加密备份；
2. 把旧单用户迁移为默认 Tenant 的首个 tenant_admin；
3. 生成不可变 tenant_id、user_id、agent_uid；
4. 建立旧 agent_id 到 agent_uid 的映射；
5. 默认不移动工作区，先登记现有路径并校验；
6. 将用户、Agent、资源和授权写入数据库；
7. 校验 Provider/MCP 密钥已转为 Secret Reference；
8. 运行越权与回归测试；
9. 原子切换为 tenant 模式；
10. 保留只读迁移报告，不继续双写 auth.json/config.json。

迁移脚本必须支持 dry-run、幂等重跑、校验报告和备份恢复。

## 16. 前端改造

- 登录响应保存 tenant、user、显示角色和权限摘要；
- 菜单基于权限渲染，但后端始终重新授权；
- 移除公开注册入口；
- 首次登录强制修改初始化密码；
- Agent 页面按“我的/授权给我的/内置模板”分组；
- 共享页面明确显示“不会复制会话、客户数据、SAGE 私有数据和凭据”；
- 用户管理增加禁用、离职、所有权转移状态；
- 授权页面使用稳定资源 ID 和版本；
- 增加审计、配额、共享任务和失败恢复页面；
- 403 不跳转登录，401 才清理登录状态。

## 17. 测试门禁

### 17.1 P0 安全测试

1. Tenant A 不能通过任何 API、WebSocket、频道、Cron、ACP 或内部工具访问 Tenant B；
2. 同 Tenant 的用户不能访问未授权 Agent；
3. TenantBoundary 在 agent_id 缺失时默认拒绝受保护 Agent 路由；
4. 绕过路由直接调用 Domain Service 仍然被拒绝；
5. 反向代理场景下 localhost 不会绕过认证；
6. 用户禁用、角色变更和撤权立即使旧 Token/缓存失效；
7. Agent 共享不包含 sessions、SAGE 私有内容、credentials 和符号链接目标；
8. 普通用户不能读取 Provider/MCP Secret；
9. `tenant` 模式不能关闭 Entitlement 获得全部资源；
10. Backup 导出和恢复不能跨 Tenant。

### 17.2 一致性测试

- 两个管理员并发修改授权不丢更新；
- 共享中断不产生可见的半成品 Agent；
- 重复共享请求只创建一个副本；
- 数据库提交失败时工作区不进入正式目录；
- 文件提交失败时数据库操作可补偿；
- 迁移脚本重跑不会重复创建用户或 Agent；
- 用户名和 Agent 名修改不影响 UUID 引用。

### 17.3 兼容回归

- legacy 模式保持现有单用户功能；
- 现有渠道、Skill、MCP、Provider、ACP 和 Coding Mode 可用；
- tenant 模式下所有入口携带 Principal；
- SAGE 与资源 Entitlement、数据 Grant 分开测试。

## 18. 分阶段实施与估算

| 阶段 | 工作内容 | 估算 |
|---|---|---:|
| M0 安全基础 | Threat Model、Principal、身份 UUID、权限矩阵、PostgreSQL Schema | 8–12 人日 |
| M1 认证与迁移 | 多用户认证、Token、bootstrap、legacy 迁移 | 10–15 人日 |
| M2 授权控制面 | 服务层 Policy、Agent 所有权、资源目录、Entitlement | 12–18 人日 |
| M3 安全共享 | staging、白名单复制、Secret Ref、SageBundle 边界 | 8–12 人日 |
| M4 管理与前端 | 用户、权限、Agent、共享、审计、配额页面 | 12–18 人日 |
| M5 加固 | 跨入口测试、反向代理、并发、离职、备份恢复 | 10–15 人日 |
| **合计** | 生产级多租户控制面 | **60–90 人日** |

SAGE 成长引擎按独立计划实施，可与 M2 之后并行开发。

## 19. 风险与回滚

| 风险 | 等级 | 缓解 |
|---|---|---|
| 鉴权遗漏 | 严重 | Principal 强制参数、服务层 Policy、仓储 tenant filter、P0 测试 |
| 反向代理绕过认证 | 严重 | tenant 模式关闭 localhost bypass、可信代理白名单 |
| 共享泄密 | 严重 | 白名单生成、Secret Ref、SAGE 隔离、扫描与审计 |
| 身份迁移错误 | 高 | UUID 映射、dry-run、加密备份、抽样校验 |
| PostgreSQL 不可用 | 高 | 连接池、健康检查、备份恢复、明确降级策略 |
| 上游同步冲突 | 中 | 新模块优先、薄适配层、ADR 和契约测试 |
| 实施周期扩大 | 中 | M0–M2 先交付安全可用 MVP，前端和共享后置 |

安全功能不能通过 `tenancy.mode=legacy` 作为线上回滚。正确回滚方式是恢复应用版本和数据库备份，并保持数据不可跨用户访问。

## 20. 关键架构决策

### ADR-MT-001：使用不可变 UUID 身份

**决定：** Tenant、User、Agent 和 Resource 使用 UUID，名称仅用于展示。  
**原因：** 重命名不能破坏所有权、审计和 SAGE 来源链。

### ADR-MT-002：授权下沉到服务层

**决定：** 中间件只构建 Principal 和粗粒度边界，所有领域服务强制授权。  
**原因：** 覆盖 REST 之外的频道、Cron、ACP、WebSocket 和内部调用。

### ADR-MT-003：PostgreSQL 是控制面真源

**决定：** 用户、角色、Agent、资源、授权、共享和审计进入事务数据库。  
**原因：** 避免 JSON 双写、并发覆盖和不完整事务。

### ADR-MT-004：多租户模式默认拒绝

**决定：** 缺少 Tenant、Principal、Owner 或 Entitlement 时拒绝操作。  
**原因：** 防止配置缺失和新入口造成隐式放行。

### ADR-MT-005：共享是白名单生成

**决定：** 从允许内容生成新 Agent，不复制完整工作区。  
**原因：** 避免会话、客户数据、SAGE 私有数据和凭据泄漏。

## 21. 生产就绪标准

- 不存在固定默认账号密码；
- tenant 模式不存在 localhost 免认证；
- 所有 Agent/资源/SAGE 服务都强制接收 Principal；
- 数据库和仓储查询都包含 tenant 条件；
- 用户名和 Agent 重命名不影响所有权或历史；
- 共享副本不包含会话、凭据或私有经验；
- 用户禁用和撤权能立即生效；
- 多管理员并发更新不丢失；
- 审计、配额、离职和备份恢复可用；
- P0 越权测试、迁移测试和 legacy 回归全部通过；
- SAGE 数据 Grant 与 Skill/MCP/Tool Entitlement 相互独立。
