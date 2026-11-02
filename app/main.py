from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1 import router as executions_router
from app.db.database import engine
from app.models import Base
from app.models import execution as _execution_models
from app.services.agent_executor import AgentExecutor
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.llm.client import DeepSeekClient
from app.tools.markdown_report import MarkdownReportGeneratorTool
from app.tools.registry import ToolRegistry
from app.tools.sales_data import SalesDataQueryTool
from app.tools.sales_metrics import SalesMetricsCalculatorTool

@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    description="A foundation for building observable and recoverable AI agent workflows.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

tool_registry = ToolRegistry()
for tool in (
    SalesDataQueryTool(),
    SalesMetricsCalculatorTool(),
    MarkdownReportGeneratorTool(),
):
    tool_registry.register(tool)

orchestrator = AgentOrchestrator(
    llm=DeepSeekClient(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
    ),
    registry=tool_registry,
    executor=AgentExecutor(tool_registry),
)

app.include_router(executions_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "AgentFlow"}
