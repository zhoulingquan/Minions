# ADR-0001：SAGE 采用完整建设、分级启用

## Status

Accepted

## Context

SAGE 需要同时满足自动学习、自我成长、企业长期稳定、多租户隔离和低运维成本。直接自动修改全部企业知识风险过高；拆分消息队列、向量库和图数据库又会显著增加中小企业部署成本。现有系统已经有 SQLite/PostgreSQL 适配器、pgvector 字段、RLS、成长任务表、审批和回滚基础。

## Decision

继续采用模块化单体和数据库 Outbox，一次建设混合召回、反馈学习、夜间巩固、治理、管理 API/UI 与评估能力。每项能力由 PolicyCenter 设置为 `OFF / SHADOW / APPROVAL / AUTO`。模型生成内容只能成为候选；高风险和跨作用域变更不能自动生效。

## Consequences

### Positive

- 可以一次完成产品和数据闭环，避免反复修改底层模型。
- 能先影子验证，再逐租户开放自动化。
- SQLite 保持低门槛开发，PostgreSQL 保持企业可靠性。
- 不增加新的基础设施和备份故障面。

### Negative

- 数据模型、测试矩阵和管理界面比单一自动开关复杂。
- 在积累真实反馈前，部分自动能力只能以影子模式运行。
- PostgreSQL 需要维护增量迁移和后台任务监控。

### Neutral

- “完整实现”和“全部自动生效”成为两个独立里程碑。
- 旧 Dream 的名称和实现不复用，等价能力命名为 SAGE Nightly。

## Alternatives Considered

- **全部自动生效**：实现简单，但无法满足稳定、审计和错误恢复要求。
- **外部向量库 + 队列 + 图数据库**：能力强，但部署和运维成本不适合目标客户。
- **继续只做单案例复盘**：风险低，但无法解决重复、冲突、过期和组织知识沉淀。

## References

- `docs/plans/2026-07-13-sage-complete-system-design.md`
- `docs/plans/2026-07-13-sage-evolution-design.md`

