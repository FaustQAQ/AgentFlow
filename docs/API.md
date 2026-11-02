# API 说明

## POST `/api/v1/executions`

请求：`{"user_request": "分析 2024 年 1 月销售额"}`。执行结果会保存并返回；LLM 未配置或上游失败时返回状态为 `failed` 的执行记录及错误信息。

## GET `/api/v1/executions`

查询参数：`page`、`page_size`、`status`。结果包含 `items`、`total`、分页参数。

## GET/DELETE `/api/v1/executions/{execution_id}`

详情返回用户请求、状态、工具步骤、输入输出、错误和时间；删除会级联删除步骤。不存在时返回 404。
