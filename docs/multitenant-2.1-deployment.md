# Minions 多租户 2.1 部署与升级手册

本手册对应全新的 Minions 租户控制面和 SAGE 经验成长系统。开发阶段可继续使用
SQLite；企业正式部署强制使用 PostgreSQL，不会在数据库异常时静默退回 SQLite。

## 1. 当前开发环境：不安装 PostgreSQL

在项目根目录设置：

```bash
export MINIONS_TENANCY_ENABLED=true
export MINIONS_TENANCY_MODE=development
export MINIONS_TENANCY_STORE=sqlite
export MINIONS_SAGE_MODE=development
export MINIONS_SAGE_STORE=sqlite
```

然后按原方式启动 `minions app`。首次打开时：

- 旧 Minions 已有账号会自动成为“默认企业空间”的所有者，用户名和密码不变；
- 原租户 ID、用户 ID 会保留，已有 SAGE 数据不会改换归属；
- 没有旧账号时，登录页会显示企业空间初始化表单；
- 原有 Agent 自动归入该企业空间；新 Agent 工作区位于
  `working/tenants/<tenant_id>/workspaces/<agent_id>`；
- 租户控制面默认数据库是 `working/control/tenancy.db`，SAGE 仍使用各 Agent
  工作区内的 `sage/sage.db`。

SQLite 模式适用于本机单进程开发和自动化测试，不适合多实例并发、容器横向扩容或
企业生产运行。

## 2. 产品内的入口

- “企业空间”：成员、邀请、角色、Agent 归属、配额与审计记录；
- 企业空间所有者可以在该页面新建另一个完全隔离的企业空间；同一账户属于多个空间
  时，可在页面顶部直接切换，也可在下次登录时选择；
- 管理员创建邀请后，系统只显示一次邀请码。成员在登录页选择“我收到了企业邀请码”
  即可加入；已有账户必须再次验证原密码，不能只凭邀请码劫持账户；
- “经验成长”：业务复盘、心得、成长规则、整理建议与运行记录；
- 业务执行成功后先进入“等待复盘”，Agent 不能自行声明业务成功；
- 相似心得达到独立案例门槛后才进入审核；批准并投入使用后，才会参与后续召回；
- 夜间整理与知识合并都明确设为“自动”时，系统只自动处理同一私有范围内的低风险
  重复项。跨用户、团队、企业共享、高风险、归档和方法手册晋升仍要求人工批准。
- 并发任务使用可续期租约计数，进程异常退出后的遗留名额会自动过期；工作区容量在
  任务开始、结束和企业空间总览时重新核对，达到上限后拒绝新的 Agent 任务。

## 3. PostgreSQL 正式部署

要求 PostgreSQL 15+。SAGE 的语义检索还需要 `pgvector`。数据库迁移账号与应用运行
账号必须分开，应用账号保持 `NOSUPERUSER`、`NOCREATEDB`、`NOCREATEROLE`、
`NOBYPASSRLS`。

先使用数据库所有者执行控制面 Schema 和最小权限角色脚本：

```bash
psql "$MINIONS_MIGRATION_DSN" -v ON_ERROR_STOP=1 \
  -f packages/minions-app/src/minions/tenancy/migrations/0001_control_plane.sql
psql "$MINIONS_MIGRATION_DSN" -v ON_ERROR_STOP=1 \
  -f packages/minions-app/src/minions/tenancy/migrations/0002_task_leases.sql
psql "$MINIONS_MIGRATION_DSN" -v ON_ERROR_STOP=1 \
  -f packages/minions-app/src/minions/tenancy/migrations/0003_invite_uniqueness.sql
psql "$MINIONS_MIGRATION_DSN" -v ON_ERROR_STOP=1 \
  -f packages/minions-app/src/minions/tenancy/migrations/runtime_role.sql
```

`runtime_role.sql` 只创建示例角色，不包含明文密码。由数据库管理员通过密钥管理系统
设置密码，并将连接串注入运行环境。登录前无法知道租户的少数查询由收窄的
`SECURITY DEFINER` 函数完成；函数不返回密码摘要，且已撤销 PUBLIC 执行权。

SAGE Schema 继续使用受校验的迁移流程：

```bash
export MINIONS_SAGE_MIGRATION_DSN="$MINIONS_MIGRATION_DSN"
minions sage migrate
minions sage migrate --yes
```

正式运行配置示例：

```bash
export MINIONS_TENANCY_ENABLED=true
export MINIONS_TENANCY_MODE=production
export MINIONS_TENANCY_STORE=postgres
export MINIONS_TENANCY_POSTGRES_DSN='postgresql://minions_tenancy_runtime:***@db/minions'
export MINIONS_TENANCY_TOKEN_TTL_SECONDS=604800

export MINIONS_SAGE_MODE=production
export MINIONS_SAGE_STORE=postgres
export MINIONS_SAGE_POSTGRES_DSN='postgresql://sage_runtime:***@db/minions'
```

生产模式启动时只校验控制面 Schema 版本，不使用运行账号建表。Schema 缺失、DSN
缺失、依赖缺失或指定 SQLite 都会直接阻止启动。

## 4. 升级顺序

1. 停止写入并备份 `working`、`working.secret`、配置文件和旧 `auth.json`；
2. 在副本环境启动 SQLite 多租户模式，确认旧账号、Agent 与 SAGE 案例归属；
3. 执行 PostgreSQL Schema，创建不具备 RLS 绕过权的运行角色；
4. 迁移并核对租户、成员、Agent 授权、SAGE 数据量与审计记录；
5. 切换正式 DSN，先单实例观察，再逐步放量；
6. 验证登录、邀请、角色变更、跨租户 404、Agent 执行、业务复盘、心得审核和回滚；
7. 稳定观察期结束前保留旧数据只读副本。

旧账号迁移是幂等的。若控制面已有所有者，启动程序不会重复创建；若旧密码仍是历史
SHA-256 格式，第一次成功登录后会自动升级到 PBKDF2-HMAC-SHA256（600,000 次）。

## 5. 备份、恢复与回滚

- SQLite 开发：停止服务后同时备份 `tenancy.db`、`tenancy.db-wal`、
  `tenancy.db-shm` 和各 Agent 的 `sage` 目录；更推荐使用 SQLite 在线备份 API；
- PostgreSQL：每日全量备份并启用 WAL 归档，目标 RPO 不超过 5 分钟；
- 每月至少做一次隔离环境恢复演练，并实际完成登录、租户隔离和心得回滚检查；
- `working.secret/tenancy.key` 必须独立备份。丢失该密钥会使现有登录会话全部失效；
- 回滚应用版本前先停止写入并恢复数据库快照。新增成员、邀请和复盘数据写入后，不可
  仅关闭环境变量回到旧单用户系统，否则会丢失新控制面的变更。

## 6. 上线验收

- 未登录访问 `/api/agents` 返回 401；本机白名单在显式多租户模式下也不能绕过；
- 两个租户使用相同 Agent ID、案例 ID 或请求头探测时，越权资源统一表现为 404；
- 禁用成员或撤销当前会话后，旧令牌立即失效；
- 创建或切换企业空间后，旧空间会话立即撤销；同一账户修改密码时，所有企业空间的
  既有会话都会撤销；
- 同一账户可创建并加入两个企业空间；不指定空间登录会要求选择，切换后只能看到
  目标空间的成员、Agent、审计和 SAGE 经验；
- 普通成员不能创建企业空间，管理员不能变更所有者，最后一名有效所有者不能被
  降级或停用；
- 私有 Agent 仅向其拥有者及具备 Agent 管理权限的角色显示；
- Agent 创建中途失败时，租户 Agent 用量和授权预留自动回滚；
- 邀请、成员角色变化、Agent 创建/归档、登录会话撤销均能在审计页查询；
- 业务成功不会自动生成“已验证心得”，必须由有权限成员完成复盘；
- 所有知识合并与心得发布均可查看来源并执行回滚；
- PostgreSQL 运行角色查询 `rolbypassrls`、`rolsuper` 均为 false。

架构与边界说明见
[多租户 2.1 设计](./plans/2026-07-13-minions-multitenant-v2.1-design.md)，
SAGE 的专项运维要求见 [SAGE 运维手册](./sage-operations-runbook.md)。
