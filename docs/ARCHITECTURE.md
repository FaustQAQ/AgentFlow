# AgentFlow——智能销售数据分析 Agent 平台架构

用户请求进入 FastAPI 路由后，由 `AgentOrchestrator` 向 DeepSeek 提供注册工具的 JSON Schema。模型只能返回工具调用意图；`AgentExecutor` 负责工具查找、Pydantic 校验、步骤限制、重试和错误分类。工具输出回到 Orchestrator，直到模型生成最终文本或达到轮次/调用上限。

执行完成后由 `ExecutionPersistenceService` 在单个 SQLAlchemy Session 中保存任务和全部步骤。历史读取通过 `ExecutionQueryService` 使用 `selectinload` 加载步骤，避免 N+1 查询。
# AgentFlow 架构补充：真实销售数据

上传接口先在内存中完成 CSV/XLSX 解析、表头映射和逐行校验，返回 `preview_id`；确认导入时使用单一 SQLAlchemy 事务写入 `sales_datasets` 与 `sales_records`，任何异常都会回滚。销售记录按数据集、日期、产品和地区建立索引，并以 `(dataset_id, order_id)` 防止重复订单。

执行请求必须携带 `dataset_id`。编排器将它写入执行记录并注入每轮工具参数，因此 DeepSeek 不需要也不能猜测当前数据集。`sales_data_query` 只读 SQLite 真实记录，`sales_metrics_calculator` 使用 Python 计算增长率，报告工具只渲染已返回的统计结果。删除数据集使用级联删除销售记录，同时执行历史的外键为 SET NULL，不会删除历史。

数据库启动时仅执行 `create_all` 和添加式迁移；不会删除或重建既有 SQLite 文件。
