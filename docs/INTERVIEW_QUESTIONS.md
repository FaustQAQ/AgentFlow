# 面试题与参考答案

## 为什么不能把测试中的固定销售金额放回生产工具？

测试数据应在独立 SQLite fixture 中提供，生产工具必须要求 `dataset_id` 并查询 `sales_records`。这样既保留业务语义，又避免真实用户误看到模拟经营结果。

## 如何保证 Agent 不跨数据集查询？

执行请求保存 `dataset_id`，编排器把它注入每一轮工具参数，`sales_data_query` 的所有查询条件都包含 `SalesRecordModel.dataset_id == arguments.dataset_id`。

## 为什么同比不能交给 LLM 计算？

LLM 负责理解意图和选择工具；金额汇总、增长率和排名由 Python/SQLAlchemy 确定性计算。上期为零或缺失时返回明确不可计算状态，避免生成虚假数字。

## 如何证明真实联调不是 Mock？

本次浏览器验收使用生成的 `acceptance_sales.xlsx`，真实上传并写入 SQLite，真实 DeepSeek 返回多轮 Function Calling，执行历史中的工具步骤和输出均可追溯。
