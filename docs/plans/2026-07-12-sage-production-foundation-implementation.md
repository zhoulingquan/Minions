# SAGE 第二阶段：生产基础实施计划

## 目标

在不信任客户端租户字段、不引用旧记忆运行时的前提下，将 SAGE 接入认证
身份，并提供 PostgreSQL/RLS 生产基础。阶段完成后，HTTP 认证用户可以获得
稳定的默认企业身份；未经认证、localhost 绕过和普通渠道请求不会进入 SAGE。

## Step 1：可信身份传播

- 新增 `TrustedSageIdentity` 和请求级 `ContextVar`。
- 新增 PRE_DISPATCH Hook，将受信身份复制到 `HookContext.extras`。
- `resolve_sage_principal` 只接受该不可变类型，不接受字典或请求扩展字段。
- 测试 ContextVar 隔离、缺失身份关闭和伪造字典拒绝。

## Step 2：现有认证迁移桥

- 为已注册单用户生成稳定 `tenant_id/user_id` 并持久化。
- 新 token 携带 `iss/aud/tenant_id/user_id/token_version/jti`。
- 验证 token 签名、期限、issuer、audience、身份一致性和撤销状态。
- AuthMiddleware 在 `call_next` 生命周期内绑定受信 SAGE 身份并可靠 reset。
- 保留 `verify_token() -> username` 的兼容接口，但内部使用结构化 claims。

## Step 3：PostgreSQL Schema 与 RLS

- 新增版本化 SQL migration，创建 `sage` schema 和核心表。
- 所有表以 `tenant_id` 作为索引首列。
- 启用 `ENABLE ROW LEVEL SECURITY` 与 `FORCE ROW LEVEL SECURITY`。
- 每张表建立 tenant policy；事务通过
  `set_config('sage.tenant_id', ..., true)` 注入租户。
- SQL 静态测试检查表、索引、RLS、策略、角色约束和参数化租户设置。

## Step 4：存储选择与失败策略

- 新增存储配置解析与工厂。
- `development/test` 可显式选择 SQLite。
- `production/tenant` 必须提供 PostgreSQL DSN；缺失驱动、DSN 或迁移版本时
  启动失败。
- 任何失败都不能回退到旧 memory manager、Scroll 或 SQLite。

## Step 5：遗留运行入口收口

- 旧 memory manager 不注册、旧 dream 不调度的行为增加回归测试。
- 旧配置只作为迁移输入，不再决定运行时长期经验后端。
- 后续独立阶段删除旧配置模型、命令和 Console 页面，避免与当前大量前端
  改动交叉。

## 验收

- 客户端伪造 tenant 字段不能启用 SAGE。
- 两个并发请求的 TrustedSageIdentity 不串租户。
- 认证 token 的 tenant/user 与服务端身份记录不一致时拒绝。
- PostgreSQL SQL 对所有主表启用并强制 RLS。
- 目标回归集、SAGE 测试、Ruff 和 diff check 全部通过。
