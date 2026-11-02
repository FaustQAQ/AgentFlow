# 数据库设计

SQLite 默认位置由 `DATABASE_URL` 控制，当前默认值是 `D:/Codex/AgentFlow/data/agentflow/.db`。

`agent_executions` 保存任务级字段，`execution_steps` 通过 `execution_id` 外键关联任务。任务与步骤是一对多关系；同一任务内的 `step_index` 唯一；删除任务时步骤级联删除。SQLite 连接开启 `PRAGMA foreign_keys=ON`。
