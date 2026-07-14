# SAGE 运维与启用手册

本手册用于把 SAGE 从开发验证稳定推进到中小企业生产环境。核心原则是：
先观察，再审核，最后只对低风险动作开放自动执行；任何共享知识变化都可追溯、
可撤销。

## 1. 能力启用顺序

首次上线建议在“工作区 → 经验成长 → 成长规则”按以下顺序操作：

1. 保持“业务经验召回”为自动采用；它只读取已授权的有效知识。
2. “反馈学习”和“夜间知识整理”设为“只观察”，至少观察 7 天或 100 次召回。
3. “知识合并”和“方法沉淀”保持“审核后采用”。
4. “跨范围复用”保持关闭，直到团队、项目的授权数据已经接入。
5. 达到放量阈值后，先将反馈学习改为“审核后采用”；再把低风险反馈学习改为
   “自动采用”。共享知识归并、归档、冲突处理和业务手册发布仍保留人工审批。

放量前必须同时满足：

- 跨租户读取/写入测试为 0 次泄漏；
- 召回降级率低于 5%；
- 明确“错误”的反馈率低于 3%，且已人工抽检；
- 夜间任务成功率不低于 99%，没有持续积压；
- 候选应用后的回滚率处于业务可接受范围；
- 备份恢复演练已经通过。

## 2. 夜间整理如何运行

每个租户、每个本地日期只会生成三项确定性任务：知识整理、经验效果校准和召回
评估。任务先写入数据库队列，再由进程领取；应用重启不会丢失任务。当天第一次
业务请求会自动补建当日任务，也可以在“经验成长”中点击“立即整理一次”。

默认单次整理最多扫描 1000 条知识、生成 500 条建议、运行 30 秒。可在
`nightly_consolidation` 策略的 `settings` 中调整：

```json
{
  "max_items": 2000,
  "max_candidates": 500,
  "time_budget_seconds": 60
}
```

系统会把这些值限制在安全上限内。失败任务最多尝试三次，之后转为失败状态，避免
无限重试压垮数据库。过期租约可以被其他工作进程安全接管；PostgreSQL 使用
`FOR UPDATE SKIP LOCKED` 防止同一任务被并发执行。

普通业务完成时，Agent 输出迹证、案例状态和初步复盘任务在同一数据库事务中提交。
复核人员确认结果时，结果迹证、案例完成状态和正式复盘任务也使用同一事务。进程若
在同步复盘前退出，事务性任务会在重启后继续；同步复盘成功则确认该任务，避免重复
学习同一个案例。

整理阶段会同时使用精确规则和语义相似度发现候选。语义结果只能生成中风险建议，
不能直接自动合并或覆盖知识；否定词命中时按可能冲突处理，仍需要人工判断。

## 3. 审批与回滚

整理建议有以下生命周期：

`待审核 → 已批准 → 已采用 → 已回滚`

也可以从“待审核”进入“已拒绝”。如果来源知识在审批期间被修改，建议会进入
“需重新检查”，不会继续应用。以下动作始终要求人工批准：

- 归档知识；
- 修改租户、团队或项目范围的共享知识；
- 发布业务手册；
- 高风险或关键风险变化；
- 同时涉及多个范围的变化。

权限最小集合：

- 审核：`sage.consolidation.approve`
- 应用：`sage.consolidation.apply`
- 回滚：`sage.consolidation.rollback`
- 管理成长规则：`sage.policy.manage`

## 4. 监控与告警

管理 API `GET /api/sage/overview` 和“经验成长”页面提供以下指标：

- 有效知识数、反馈数和正向反馈率；
- 召回次数、降级次数和降级率；
- 待审核、已应用、已回滚建议数；
- 整理批次成功/失败数；
- 后台任务等待、完成、失败数和平均耗时。

建议告警条件：任务连续 3 次失败、待处理任务超过一个夜间窗口、降级率连续一天
高于 10%、候选回滚率突然翻倍，或出现任何 RLS/跨租户拒绝异常峰值。

## 5. SQLite 开发备份与恢复

SQLite 只用于单进程开发。备份前暂停写入或停止 Minions：

```bash
sqlite3 ~/.minions/workspaces/default/sage/sage.db \
  ".backup '/path/to/backup/sage-YYYYMMDD.db'"
sqlite3 /path/to/backup/sage-YYYYMMDD.db "PRAGMA integrity_check;"
```

恢复时先保留当前文件，再把通过完整性检查的备份复制回原位置，然后启动服务并
打开“经验成长”核对知识、策略、任务和建议数量。不要在多个 Minions 进程之间
共享同一个 SQLite 文件。

## 6. PostgreSQL 迁移与恢复演练

每次发布前在临时数据库执行：

```bash
createdb minions_sage_rehearsal
pg_restore --clean --if-exists --no-owner \
  --dbname=minions_sage_rehearsal /backup/minions.dump
export MINIONS_SAGE_MIGRATION_DSN='postgresql://.../minions_sage_rehearsal'
minions sage migrate
minions sage migrate --yes
minions sage status
```

然后运行 SAGE 集成测试和一次“只观察”夜间整理，确认：迁移校验和一致、所有租户
表启用并强制 RLS、运行角色没有 `BYPASSRLS`、旧数据可读取、新任务可恢复。

生产备份建议使用：

```bash
pg_dump --format=custom --no-owner --file=/backup/minions-$(date +%F).dump minions
```

迁移 `0002_sage_governance.sql` 与 `0003_sage_semantic.sql` 是向前兼容的增量迁移。
后者为现有知识向量增加模型和版本元数据。应用版本回退时，优先回退应用而保留新增
列和表；不要在线删除治理表。若必须回退数据库结构，应停止写入，使用发布前的完整
备份恢复到新数据库，校验后切换连接串。任何 `DROP TABLE` 都不作为常规回滚步骤。

## 7. 故障处置

- 向量服务超时：系统自动退化为关键词、实体、时效和反馈排序，请检查降级率，
  不需要停止业务请求。
- 本地向量模型或维度改变：系统按知识版本和模型标识逐步重建索引；放量前应在测试
  环境检查召回准确率，避免仅凭“有结果”判断质量。
- 夜间整理失败：查看失败任务和整理批次错误；修复外部原因后重新安排当日整理。
- 建议来源变化：重新运行整理，禁止强制应用旧建议。
- PostgreSQL 不可用：生产/租户模式会失败关闭，不会降级到 SQLite；恢复数据库后
  重启服务，租约过期任务会被重新领取。
- 错误知识已应用：在整理建议中执行回滚；审计记录和原始快照会继续保留。

## 8. 发布门禁

发布前必须通过：

```bash
python -m compileall -q src/minions/sage
python -m pytest -q tests/unit/sage tests/unit/tenancy/test_runtime.py tests/unit/app/routers/test_sage_router.py
python -m pytest -q tests/integration/test_sage_complete_flow.py
ruff check src/minions/sage src/minions/app/routers/sage.py
cd console
npm run test:run -- src/pages/Settings/Sage/SagePage.test.tsx
npm run build
```

若完整仓库构建或测试被无关的既有错误阻断，发布记录必须列明阻断文件，且仍需保证
上述 SAGE 定向测试全部通过。
