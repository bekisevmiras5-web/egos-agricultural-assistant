"""EGOS entry point: Telegram polling plus FastAPI health endpoints."""

from __future__ import annotations

import asyncio
import logging

import uvicorn
from aiogram import Bot, Dispatcher
from fastapi import FastAPI

from .config import get_settings
from .database import init_db
from .handlers.forecast import router as forecast_router
from .handlers.plan import router as plan_router
from .handlers.start import router as start_router
from .handlers.survey import router as survey_router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="EGOS Agricultural Yield & Care Assistant", version="0.1.0")


@app.get("/")
async def root() -> dict[str, str]:
    """Simple service identity endpoint."""
    return {"service": "EGOS", "status": "ok"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Health endpoint suitable for a process monitor."""
    return {"status": "healthy"}


async def run() -> None:
    """Initialize storage and run bot and HTTP health server together."""
    settings = get_settings()
    settings.require_bot_token()
    init_db()

    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(start_router)
    dispatcher.include_router(survey_router)
    dispatcher.include_router(forecast_router)
    dispatcher.include_router(plan_router)

    logger.info(
        "Starting EGOS in %s mode. HTTP health server on %s:%s",
        "DEMO" if settings.demo_mode else "LIVE",
        settings.host,
        settings.port,
    )
    server_config = uvicorn.Config(
        app,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )
    server = uvicorn.Server(server_config)
    polling_task = asyncio.create_task(dispatcher.start_polling(bot))
    http_task = asyncio.create_task(server.serve())
    try:
        await asyncio.gather(polling_task, http_task)
    finally:
        for task in (polling_task, http_task):
            if not task.done():
                task.cancel()
        await bot.session.close()


def main() -> None:
    """Synchronous console entry point."""
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("EGOS stopped")
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()