# SAGE 部署说明

## 开发与测试

默认使用工作区内的 `sage/sage.db`：

```bash
export MINIONS_SAGE_MODE=development
export MINIONS_SAGE_STORE=sqlite
export MINIONS_SAGE_EMBEDDING_PROVIDER=local-hash
```

SQLite 只适用于单进程开发和自动化测试，不作为企业多用户生产数据库。
`local-hash` 会把有效知识向量保存到同一个 SQLite 数据库，不访问外部网络；适合
验证中文相似表达召回，但不能替代生产级语义模型。

如需关闭语义召回：

```bash
export MINIONS_SAGE_EMBEDDING_PROVIDER=off
```

## PostgreSQL 生产部署

安装可选依赖：

```bash
pip install 'minions[postgres]'
```

使用 PostgreSQL 管理员或专用迁移角色审阅并执行 Schema：

```bash
minions sage schema-sql
export MINIONS_SAGE_MIGRATION_DSN='postgresql://...'
minions sage migrate                 # dry-run
minions sage migrate --yes           # 显式执行
minions sage schema-sql --runtime-role
```

`runtime-role` SQL 需要数据库中已经存在 `sage_runtime` 登录角色。实际生产可替换
为自己的角色名，但必须保持 `NOSUPERUSER` 和 `NOBYPASSRLS`。

运行服务：

```bash
export MINIONS_SAGE_MODE=production
export MINIONS_SAGE_STORE=postgres
export MINIONS_SAGE_POSTGRES_DSN='postgresql://sage_runtime:...@db/minions'
minions sage status
```

生产环境可以继续使用本地向量基线，也可以配置独立的 OpenAI 兼容向量端点：

```bash
export MINIONS_SAGE_EMBEDDING_PROVIDER=openai-compatible
export MINIONS_SAGE_EMBEDDING_BASE_URL='https://embedding.example.com/v1'
export MINIONS_SAGE_EMBEDDING_MODEL='your-embedding-model'
export MINIONS_SAGE_EMBEDDING_DIMENSIONS=1536
export MINIONS_SAGE_EMBEDDING_API_KEY='由密钥管理系统注入'
export MINIONS_SAGE_EMBEDDING_TIMEOUT_SECONDS=1.5
```

端点异常、超时或维度不匹配时，当前请求会降级到关键词与结构化召回，不会跳过
租户、作用域、密级和有效期过滤。

生产或 tenant 模式下，SQLite 被显式拒绝；缺少 DSN、psycopg、Schema 版本或
迁移校验和时，Workspace 启动失败，不会静默切换到其他存储实现。

## 身份要求

- 只有认证中间件绑定的 `TrustedSageIdentity` 可以进入 SAGE。
- 请求体、Agent 输出和普通渠道 metadata 中的 `tenant_id` 不受信任。
- tenant/production 模式关闭 localhost 免认证绕过。
- 多租户 2.1 控制面是 Tenant/User/Session 的唯一在线真源；旧 `auth.json` 只在
  首次幂等迁移时读取，迁移后登录、权限与会话均由控制面处理。
- HTTP、本地免登录、飞书等渠道、Cron 与 ACP 最终都通过同一个 Agent 运行作用域
  转换为 SAGE 身份；请求字段不能覆盖控制面的租户主体。

## 运维最低要求

- PostgreSQL 每日全量备份并启用 WAL 归档；建议 RPO 不超过 5 分钟。
- 定期做恢复演练，不把“备份成功日志”等同于可恢复。
- 监控连接池耗尽、RLS 拒绝、成长任务积压、召回延迟和回滚率。
- 迁移 DSN 与运行 DSN 分离；应用进程不得持有建表或关闭 RLS 的权限。

完整的启用阈值、备份恢复、故障处置和回滚步骤见
[SAGE 运维与启用手册](./sage-operations-runbook.md)。
