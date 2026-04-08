from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import create_tables
from app.pipeline.graph import build_graph
from app.pipeline.runtime import set_graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    graph = build_graph(settings.DATABASE_URL)
    app.state.graph = graph
    set_graph(graph)
    yield


app = FastAPI(
    title="Loss Run Triage API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.routes import jobs, hitl, outputs, stream  # noqa: E402

app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["jobs"])
app.include_router(hitl.router, prefix="/api/v1/hitl", tags=["hitl"])
app.include_router(outputs.router, prefix="/api/v1/outputs", tags=["outputs"])
app.include_router(stream.router, prefix="/api/v1/jobs", tags=["stream"])


@app.get("/health")
def health():
    return {"status": "ok"}
