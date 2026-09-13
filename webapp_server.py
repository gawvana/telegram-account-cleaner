from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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
from webapp.api.history import router as history_router
from webapp.api.login import router as login_router
from webapp.api.scan import router as scan_router
from webapp.api.settings import router as settings_router
from utils.logger import logger

# Initialize Dispatcher for processing webhook updates
bot_dp = Dispatcher(storage=MemoryStorage())
bot_dp.include_router(bot_router)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting FastAPI WebApp Server...")
    await db.init_db()
    if settings.SCHEDULER_ENABLED:
        scheduler_service.start()
        await scheduler_service.sync_all_schedules()

    # Auto-register webhook in Vercel / production if configured
    if settings.BOT_TOKEN and settings.WEBAPP_URL and "vercel.app" in settings.WEBAPP_URL:
        try:
            webhook_url = f"{settings.WEBAPP_URL.rstrip('/')}/api/webhook"
            async with Bot(token=settings.BOT_TOKEN) as b:
                await b.set_webhook(url=webhook_url, drop_pending_updates=False)
                logger.info(f"Telegram Bot webhook registered: {webhook_url}")
        except Exception as e:
            logger.warning(f"Could not automatically set webhook on startup: {e}")

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


# Telegram Bot Webhook Integration
@app.post("/api/webhook")
async def telegram_webhook(request: Request):
    if not settings.BOT_TOKEN:
        return {"ok": False, "error": "BOT_TOKEN not configured"}
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
async def setup_webhook():
    if not settings.BOT_TOKEN:
        return {"ok": False, "error": "BOT_TOKEN not configured"}
    webhook_url = f"{settings.WEBAPP_URL.rstrip('/')}/api/webhook"
    async with Bot(token=settings.BOT_TOKEN) as bot:
        res = await bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
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
