from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
import models  # noqa: F401  ensure all models are registered with Base
import models.machine  # noqa: F401  register Machine model

from api.auth import router as auth_router
from api.audit import router as audit_router
from api.chat import router as chat_router
from api.dashboard import router as dashboard_router
from api.inspection import router as inspection_router
from api.knowledge import router as knowledge_router
from api.machines import router as machines_router
from api.notification import router as notification_router
from api.terminal import router as terminal_router
from api.topology import router as topology_router
from api.users import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    from services.scheduler import scheduler
    await scheduler.start()
    # Track SSE connections for graceful shutdown
    app.state.active_sse_connections = set()
    yield
    # Shutdown: stop scheduler, cancel pending SSE connections
    await scheduler.stop()
    for task in list(app.state.active_sse_connections):
        task.cancel()


app = FastAPI(title="AI-Ops Platform", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(audit_router)
app.include_router(chat_router)
app.include_router(dashboard_router)
app.include_router(knowledge_router)
app.include_router(notification_router)
app.include_router(inspection_router)
app.include_router(terminal_router)
app.include_router(topology_router)
app.include_router(machines_router)
app.include_router(users_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
