# API 说明

## POST `/api/v1/executions`

请求：`{"user_request": "分析 2024 年 1 月销售额"}`。执行结果会保存并返回；LLM 未配置或上游失败时返回状态为 `failed` 的执行记录及错误信息。

## GET `/api/v1/executions`

查询参数：`page`、`page_size`、`status`。结果包含 `items`、`total`、分页参数。

## GET/DELETE `/api/v1/executions/{execution_id}`

详情返回用户请求、状态、工具步骤、输入输出、错误和时间；删除会级联删除步骤。不存在时返回 404。
# API

## 数据集

- `POST /api/v1/datasets/upload`：上传 `.csv`/`.xlsx`，返回预览、字段映射、成功/失败行和错误定位。
- `POST /api/v1/datasets/{dataset_id}/import`：提交 `preview_id`，在同一事务内持久化数据集和全部有效记录。
- `GET /api/v1/datasets`、`GET /api/v1/datasets/{id}`：数据集列表与详情。
- `GET /api/v1/datasets/{id}/records?page=1&page_size=50`：分页记录。
- `DELETE /api/v1/datasets/{id}`：只删除数据集和销售记录，执行历史通过外键 SET NULL 保留。

## 执行

`POST /api/v1/executions` 请求体：`{"user_request":"...", "dataset_id": 1}`。未选择数据集或数据集不存在时拒绝执行。
