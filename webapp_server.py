from contextlib import asynccontextmanager
from pathlib import Path
import secrets
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from bot.handlers import router as bot_router
from config import settings
from database import db
from services.scheduler_service import scheduler_service
from webapp.api.cleanup import router as cleanup_router
from webapp.api.consent import router as consent_router
from webapp.api.diagnostics import router as diagnostics_router
from webapp.api.history import router as history_router
from webapp.api.login import router as login_router
from webapp.api.scan import router as scan_router
from webapp.api.settings import router as settings_router
from webapp.api.support import router as support_router
from webapp.api.features import router as features_router
from utils.logger import logger

# Initialize Dispatcher for processing webhook updates
bot_dp = Dispatcher(storage=MemoryStorage())
bot_dp.include_router(bot_router)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting CLIN FastAPI WebApp Server...")
    from features import auto_discover_features
    auto_discover_features()
    await db.init_db()

    if settings.SCHEDULER_ENABLED:
        scheduler_service.start()
        await scheduler_service.sync_all_schedules()

    # Auto-register webhook in Vercel / production if configured
    if settings.BOT_TOKEN and settings.WEBAPP_URL and "vercel.app" in settings.WEBAPP_URL:
        try:
            webhook_url = f"{settings.WEBAPP_URL.rstrip('/')}/api/webhook"
            async with Bot(token=settings.BOT_TOKEN) as b:
                await b.set_webhook(
                    url=webhook_url,
                    drop_pending_updates=False,
                    secret_token=settings.WEBHOOK_SECRET_TOKEN or None,
                )
                logger.info(f"CLIN Telegram Bot webhook registered: {webhook_url}")
        except Exception as e:
            logger.warning(f"Could not automatically set webhook on startup: {e}")

    yield
    # Shutdown
    logger.info("Shutting down CLIN FastAPI WebApp Server...")
    if settings.SCHEDULER_ENABLED:
        scheduler_service.shutdown()


app = FastAPI(
    title="CLIN — Telegram Account Cleaner API",
    version="2.1.0",
    lifespan=lifespan,
)

# Standardized Error Handling
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = f"CLIN-{secrets.randbelow(90000) + 10000}"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "request_id": request_id,
            },
        },
    )


# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://telegram.org https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://telegram.org https://*.telegram.org; "
        "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org; "
        "object-src 'none'; "
        "base-uri 'self';"
    )
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response


# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Mini App opens inside Telegram WebView
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# API Routers
app.include_router(login_router, prefix="/api")
app.include_router(scan_router, prefix="/api")
app.include_router(cleanup_router, prefix="/api")
app.include_router(history_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(consent_router, prefix="/api")
app.include_router(support_router, prefix="/api")
app.include_router(diagnostics_router, prefix="/api")
app.include_router(features_router)

# Feature Routers
try:
    from features.deleted_messages.router import router as dm_router
    app.include_router(dm_router)
except ImportError:
    pass
try:
    from features.edited_messages.router import router as em_router
    app.include_router(em_router)
except ImportError:
    pass
try:
    from features.auto_responder.router import router as ar_router
    app.include_router(ar_router)
except ImportError:
    pass
try:
    from features.translator.router import router as tr_router
    app.include_router(tr_router)
except ImportError:
    pass
try:
    from features.mute.router import router as mute_router
    app.include_router(mute_router)
except ImportError:
    pass

# Static files for Mini App
public_path = Path(__file__).parent / "public"
static_path = public_path if public_path.exists() else (Path(__file__).parent / "webapp" / "static")

if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(static_path / "index.html")

    @app.get("/style.css")
    async def serve_style():
        return FileResponse(static_path / "style.css", media_type="text/css")

    @app.get("/app.js")
    async def serve_script():
        return FileResponse(static_path / "app.js", media_type="application/javascript")


# Telegram Bot Webhook Integration
@app.post("/api/webhook")
async def telegram_webhook(request: Request):
    if not settings.BOT_TOKEN:
        return JSONResponse(status_code=500, content={"ok": False, "error": "BOT_TOKEN not configured"})

    # Validate secret token if configured
    if settings.WEBHOOK_SECRET_TOKEN:
        token_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if token_header != settings.WEBHOOK_SECRET_TOKEN:
            logger.warning("Rejected webhook request with invalid secret token")
            return JSONResponse(status_code=403, content={"ok": False, "error": "Invalid webhook secret token"})

    try:
        data = await request.json()
        async with Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
        ) as bot:
            update = Update.model_validate(data, context={"bot": bot})
            await bot_dp.feed_update(bot=bot, update=update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Error handling Telegram webhook: {e}", exc_info=True)
        return {"ok": False, "error": str(e)}


@app.get("/api/setup-webhook")
async def setup_webhook(secret: str = ""):
    if not settings.BOT_TOKEN:
        return {"ok": False, "error": "BOT_TOKEN not configured"}

    # Basic authorization check for setup endpoint
    if settings.WEBHOOK_SECRET_TOKEN and secret != settings.WEBHOOK_SECRET_TOKEN:
        return JSONResponse(status_code=403, content={"ok": False, "error": "Unauthorized"})

    webhook_url = f"{settings.WEBAPP_URL.rstrip('/')}/api/webhook"
    async with Bot(token=settings.BOT_TOKEN) as bot:
        res = await bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
            secret_token=settings.WEBHOOK_SECRET_TOKEN or None,
        )
        info = await bot.get_webhook_info()
        return {
            "ok": True,
            "webhook_url": webhook_url,
            "set_webhook_result": res,
            "webhook_info": {
                "url": info.url,
                "has_custom_certificate": info.has_custom_certificate,
                "pending_update_count": info.pending_update_count,
                "last_error_date": info.last_error_date,
                "last_error_message": info.last_error_message,
            },
        }


@app.get("/api/webhook-info")
async def webhook_info():
    if not settings.BOT_TOKEN:
        return {"ok": False, "error": "BOT_TOKEN not configured"}
    async with Bot(token=settings.BOT_TOKEN) as bot:
        info = await bot.get_webhook_info()
        return {
            "ok": True,
            "webhook_info": {
                "url": info.url,
                "has_custom_certificate": info.has_custom_certificate,
                "pending_update_count": info.pending_update_count,
                "last_error_date": info.last_error_date,
                "last_error_message": info.last_error_message,
            },
        }


@app.get("/health")
@app.get("/api/health")
@app.get("/api/index.py")
async def health_check(request: Request = None):
    # Safe healthcheck without leaking request headers
    return {
        "status": "ok",
        "app": "CLIN",
        "version": "2.1.0",
        "timestamp": 1789287000,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "webapp_server:app",
        host=settings.WEBAPP_HOST,
        port=settings.WEBAPP_PORT,
        reload=False,
    )
