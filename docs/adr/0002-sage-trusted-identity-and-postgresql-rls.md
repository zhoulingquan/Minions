# ADR-0002：SAGE 使用可信身份桥和 PostgreSQL RLS

## 状态

Accepted

## 背景

SAGE 的第一阶段已经实现独立领域模型、SQLite 开发存储、受控成长和
Minions 生命周期接入，但现有 Minions 认证仍是单用户 `auth.json` 模式，
没有可直接作为企业边界的 `tenant_id`。如果直接接受聊天请求体或
`channel_meta` 中的租户字段，攻击者可以伪造租户并访问不属于自己的经验。

企业生产环境还要求数据库在应用层策略失误时继续阻止跨租户访问。SQLite
没有 Row Level Security，不能作为多用户生产事实源。

## 决策

1. 只有认证中间件或受信入口能够创建 `TrustedSageIdentity`；它通过
   `ContextVar` 传播，SAGE 生命周期 Hook 再构建不可变 `Principal`。
2. 请求体、模型输出和普通 `channel_meta` 中的租户、用户、角色字段一律
   不作为可信身份来源。
3. 现有单用户账号迁移时生成并持久化稳定的 `tenant_id/user_id`，作为默认
   企业的 bootstrap 身份；这不是最终多用户账号库。
4. 企业生产模式使用 PostgreSQL。每个事务通过 `set_config` 设置本地
   `sage.tenant_id`，所有 SAGE 主表启用并强制 RLS。
5. PostgreSQL 应用角色不得是 superuser，不得拥有 `BYPASSRLS`；迁移角色
   与运行角色分离。
6. SQLite 仅用于单进程开发与测试。生产配置缺少 PostgreSQL 时启动失败，
   不静默切换到其他实现或在生产环境使用 SQLite。

## 后果

### 正面

- 客户端无法通过自报 `tenant_id` 切换数据边界。
- 应用策略与数据库 RLS 构成双重隔离。
- 单用户实例可获得稳定身份并平滑迁移。
- SAGE 保持独立的领域模型与运行时边界。

### 负面

- 非 HTTP 渠道必须增加受信身份映射后才能启用 SAGE。
- 生产部署需要 PostgreSQL、迁移角色和应用角色配置。
- 当前单用户身份桥仍需在多用户控制面上线后迁移并删除。

### 中性

- 开发测试继续使用 SQLite，但其结果不能证明 PostgreSQL RLS 正确运行。

## 备选方案

- **直接信任请求体 tenant_id**：实现简单，但属于严重越权漏洞，拒绝。
- **从用户名即时推导租户且不持久化**：缺少可审计身份真源，拒绝。
- **每租户独立数据库**：隔离强，但中小企业运维和跨租户升级成本过高，
  当前不采用。
- **只做应用层 tenant 过滤**：无法抵御漏写过滤条件，拒绝。

## 参考

- （设计计划文档已归档移除）
