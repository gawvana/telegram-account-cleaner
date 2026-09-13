from typing import Any, Dict, List
from telegram_client.models import ChatType, ScanResult


class PreviewService:
    """Formats scan results for user inspection before cleanup actions."""

    def format_bot_preview(self, scan: ScanResult) -> str:
        """Formats an executive summary for Telegram Bot UI."""
        return (
            "🔎 **ПРЕДПРОСМОТР ОЧИСТКИ (SCAN & PREVIEW)**\n\n"
            f"👤 Личные чаты: `{scan.private_chats}`\n"
            f"🤖 Боты: `{scan.bot_chats}`\n"
            f"👥 Группы: `{scan.group_chats}`\n"
            f"📢 Каналы: `{scan.channel_chats}`\n\n"
            f"⭐ **В белом списке (Whitelist):** `{scan.whitelisted_count}`\n"
            f"🧠 **Рекомендовано к очистке:** `{scan.recommended_count}`\n\n"
            f"✅ Доступно к обработке: `{scan.actionable_count}`\n"
            f"⚠️ Требует спец. прав: `{scan.special_rights_count}`\n"
            f"❌ Недоступно: `{scan.inaccessible_count}`\n\n"
            "💡 _Выберите категорию ниже или перейдите в Mini App для точечного выбора диалогов._"
        )

    def format_recommendations_text(self, scan: ScanResult, limit: int = 10) -> str:
        """Formats list of smart recommendations for the bot."""
        rec_items = [i for i in scan.items if i.heuristics.recommended_for_cleanup and not i.is_whitelisted]
        if not rec_items:
            return "🧠 **Умные рекомендации:**\n\n_Подозрительных или мёртвых диалогов не обнаружено._"

        lines = [f"🧠 **Умные рекомендации ({len(rec_items)}):**\n"]
        for idx, item in enumerate(rec_items[:limit], 1):
            tag_str = ", ".join(item.heuristics.tags) if item.heuristics.tags else "Неактивен"
            lines.append(f"{idx}. **{item.title}** ({item.chat_type.value})\n   🏷 _{tag_str}_\n")

        if len(rec_items) > limit:
            lines.append(f"_...и ещё {len(rec_items) - limit} диалогов в Mini App._")

        return "\n".join(lines)

    def to_webapp_dict(self, scan: ScanResult) -> Dict[str, Any]:
        """Serializes scan preview for Mini App REST API."""
        return {
            "summary": {
                "total_dialogs": scan.total_dialogs,
                "private_chats": scan.private_chats,
                "bot_chats": scan.bot_chats,
                "group_chats": scan.group_chats,
                "channel_chats": scan.channel_chats,
                "whitelisted_count": scan.whitelisted_count,
                "recommended_count": scan.recommended_count,
                "actionable_count": scan.actionable_count,
                "special_rights_count": scan.special_rights_count,
            },
            "items": [
                {
                    "chat_id": i.chat_id,
                    "title": i.title,
                    "username": i.username,
                    "chat_type": i.chat_type.value,
                    "unread_count": i.unread_count,
                    "is_pinned": i.is_pinned,
                    "is_whitelisted": i.is_whitelisted,
                    "requires_special_rights": i.requires_special_rights,
                    "last_message_date": i.last_message_date.isoformat() if i.last_message_date else None,
                    "inactive_days": i.heuristics.inactive_days,
                    "recommended": i.heuristics.recommended_for_cleanup,
                    "tags": i.heuristics.tags,
                }
                for i in scan.items
            ],
        }


preview_service = PreviewService()
