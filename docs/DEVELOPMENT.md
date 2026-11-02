# 开发说明

1. 使用 `D:\Codex\AgentFlow\.venv`。
2. 修改依赖后运行 `pip install -r requirements.txt`。
3. 后端测试：`.venv\Scripts\python.exe -m pytest -v`。
4. 前端检查：`cd frontend; npm install; npm run build`。
5. 不把 `.env`、API Key 或 `data/` 数据库文件提交到 Git。
6. 业务工具必须继承 `BaseTool` 并注册到 `ToolRegistry`；LLM 不得直接执行 Python。
