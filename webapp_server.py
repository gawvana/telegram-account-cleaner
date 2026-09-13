from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from database import db
from services.scheduler_service import scheduler_service
from webapp.api.cleanup import router as cleanup_router
from webapp.api.history import router as history_router
from webapp.api.login import router as login_router
from webapp.api.scan import router as scan_router
from webapp.api.settings import router as settings_router
from utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting FastAPI WebApp Server...")
    await db.init_db()
    if settings.SCHEDULER_ENABLED:
        scheduler_service.start()
        await scheduler_service.sync_all_schedules()
    yield
    # Shutdown
    logger.info("Shutting down FastAPI WebApp Server...")
    scheduler_service.shutdown()


app = FastAPI(
    title="Maximum Telegram Account Cleaner - Mini App API",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Mini App opens inside Telegram WebView
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(login_router, prefix="/api")
app.include_router(scan_router, prefix="/api")
app.include_router(cleanup_router, prefix="/api")
app.include_router(history_router, prefix="/api")
app.include_router(settings_router, prefix="/api")

# Static files for Mini App
public_path = Path(__file__).parent / "public"
static_path = public_path if public_path.exists() else (Path(__file__).parent / "webapp" / "static")

if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(static_path / "index.html")


@app.get("/health")
@app.get("/api/health")
@app.get("/api/index.py")
async def health_check(request: Request = None):
    headers = dict(request.headers) if request else {}
    return {
        "status": "ok",
        "version": "2.0.0",
        "path": request.url.path if request else None,
        "headers": headers,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "webapp_server:app",
        host=settings.WEBAPP_HOST,
        port=settings.WEBAPP_PORT,
        reload=False,
    )
