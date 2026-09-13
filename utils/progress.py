import asyncio
import time
from typing import Callable, Awaitable, Optional


class ProgressTracker:
    """Tracks task progress and provides throttled updates for Telegram messages and SSE."""

    def __init__(
        self,
        total: int,
        title: str = "Cleaning in progress",
        throttle_interval: float = 1.5,
        update_callback: Optional[Callable[["ProgressTracker"], Awaitable[None]]] = None,
    ):
        self.total = max(total, 1)
        self.processed = 0
        self.skipped = 0
        self.errors = 0
        self.current_item = ""
        self.current_action = ""
        self.title = title
        self.throttle_interval = throttle_interval
        self.update_callback = update_callback

        self.start_time = time.time()
        self.last_update_time = 0.0
        self._lock = asyncio.Lock()
        self.is_finished = False

    @property
    def percentage(self) -> int:
        return min(int((self.processed / self.total) * 100), 100)

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time

    @property
    def progress_bar(self) -> str:
        blocks = 12
        filled = int(blocks * (self.percentage / 100.0))
        return "█" * filled + "░" * (blocks - filled)

    def format_elapsed(self) -> str:
        mins, secs = divmod(int(self.elapsed_seconds), 60)
        return f"{mins:02d}:{secs:02d}"

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "total": self.total,
            "processed": self.processed,
            "skipped": self.skipped,
            "errors": self.errors,
            "current_item": self.current_item,
            "current_action": self.current_action,
            "percentage": self.percentage,
            "progress_bar": self.progress_bar,
            "elapsed": self.format_elapsed(),
            "is_finished": self.is_finished,
        }

    def render_telegram_text(self) -> str:
        return (
            f"⚡ **{self.title}**\n\n"
            f"`[{self.progress_bar}]` {self.percentage}%\n\n"
            f"📊 **Прогресс:** {self.processed}/{self.total}\n"
            f"✅ Успешно: {self.processed - self.skipped - self.errors}\n"
            f"⏭ Пропущено: {self.skipped}\n"
            f"❌ Ошибок: {self.errors}\n"
            f"⏱ Время: {self.format_elapsed()}\n"
            f"🔍 Текущий: `{self.current_item[:30] if self.current_item else '—'}`"
        )

    async def advance(
        self,
        item_title: str = "",
        action: str = "",
        skipped: bool = False,
        error: bool = False,
        force_update: bool = False,
    ) -> None:
        async with self._lock:
            self.processed += 1
            if skipped:
                self.skipped += 1
            elif error:
                self.errors += 1

            self.current_item = item_title
            self.current_action = action

            now = time.time()
            if force_update or (now - self.last_update_time >= self.throttle_interval):
                self.last_update_time = now
                if self.update_callback:
                    try:
                        await self.update_callback(self)
                    except Exception:
                        pass

    async def finish(self) -> None:
        async with self._lock:
            self.is_finished = True
            if self.update_callback:
                try:
                    await self.update_callback(self)
                except Exception:
                    pass
