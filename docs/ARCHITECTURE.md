# AgentFlow 架构

用户请求进入 FastAPI 路由后，由 `AgentOrchestrator` 向 DeepSeek 提供注册工具的 JSON Schema。模型只能返回工具调用意图；`AgentExecutor` 负责工具查找、Pydantic 校验、步骤限制、重试和错误分类。工具输出回到 Orchestrator，直到模型生成最终文本或达到轮次/调用上限。

执行完成后由 `ExecutionPersistenceService` 在单个 SQLAlchemy Session 中保存任务和全部步骤。历史读取通过 `ExecutionQueryService` 使用 `selectinload` 加载步骤，避免 N+1 查询。
