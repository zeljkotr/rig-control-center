from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.health import router as health_router
from app.api.mining import router as mining_router
from app.api.pools import router as pools_router
from app.api.rigs import router as rigs_router
from app.core.config import settings
from app.core.database import close_database, init_database

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_database()
    yield
    await close_database()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Centralized management for authorized XMRig workers.",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "static"), name="static")
app.include_router(health_router, prefix="/api")
app.include_router(rigs_router, prefix="/api")
app.include_router(pools_router, prefix="/api")
app.include_router(mining_router, prefix="/api")


@app.get("/", include_in_schema=False)
@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    return FileResponse(PROJECT_ROOT / "templates" / "dashboard.html")


@app.get("/api/status", tags=["System"])
async def status():
    return {
        "application": settings.app_name,
        "version": settings.app_version,
        "database": "sqlite",
        "mining_execution_enabled": False,
    }
