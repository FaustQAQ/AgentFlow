# AgentFlow

AgentFlow 是一个本地、可观测的单 Agent 销售分析应用：DeepSeek 负责选择已注册工具，Python 后端负责参数校验和执行，SQLite 保存完整执行历史，React 展示结果。

## 已实现能力

- FastAPI 健康检查与执行 API。
- Pydantic 参数模型、工具注册表和三个确定性销售分析工具。
- 最大步骤数、有限重试、超时异常、错误分类和执行日志。
- SQLite + SQLAlchemy 2.x 执行记录、步骤记录、事务保存、历史查询和级联删除。
- OpenAI 兼容的 DeepSeek Chat Completions 客户端和多轮 Tool Calling Orchestrator。
- React + TypeScript 前端，可提交任务、查看步骤和浏览历史。

当前销售数据是代码内固定的模拟数据，不代表真实企业数据。真实 DeepSeek 调用需要用户自行配置 API Key；自动化测试不访问真实 API。

## 架构

```text
React/Vite -> FastAPI API -> AgentOrchestrator -> DeepSeek
                                |                    |
                                v                    v
                         AgentExecutor <- ToolRegistry
                                |
                                v
                    ExecutionPersistenceService -> SQLite
```

## 目录

```text
app/api/v1/       FastAPI 路由
app/db/           Engine、SessionLocal、get_db
app/models/       SQLAlchemy ORM
app/schemas/      Pydantic 模型
app/services/     执行、LLM、查询和持久化服务
app/tools/        工具基类、注册表和销售工具
frontend/         React + TypeScript + Vite
tests/            后端自动化测试
docs/             架构、API、数据库和开发文档
```

## 本地启动

```powershell
Copy-Item .env.example .env
# 编辑 .env，填写 LLM_API_KEY
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

默认 SQLite 文件为 `D:\Codex\AgentFlow\data\agentflow\.db`。前端默认请求 `http://localhost:8000`，可通过 `VITE_API_BASE_URL` 覆盖。

## API

- `GET /health`
- `POST /api/v1/executions`
- `GET /api/v1/executions?page=1&page_size=20&status=succeeded`
- `GET /api/v1/executions/{execution_id}`
- `DELETE /api/v1/executions/{execution_id}`
- `GET /docs`

未配置 LLM API Key 时，提交请求仍会生成一条失败执行记录，便于查询错误原因；真实模型调用需要先配置密钥。

## 测试

```powershell
.venv\Scripts\python.exe -m pytest -v
```

测试使用临时 SQLite 数据库和 Fake/Mock LLM，不需要 API Key，也不会访问开发数据库。

## 当前限制

- 真实 DeepSeek API 联调需要用户配置密钥，本次自动化测试未验证外部网络调用。
- 当前使用同步 FastAPI/SQLAlchemy；SQLite 适合本地 Demo，不适合高并发生产写入。
- 前端是轻量单页界面，未引入身份认证、流式输出或实时 WebSocket。
- 模拟销售数据范围有限，查询范围必须覆盖已有记录。
