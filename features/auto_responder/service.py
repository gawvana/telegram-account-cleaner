import re
import logging
from typing import List, Optional
from database import db
from features.auto_responder.models import AutoResponderRuleCreate, AutoResponderRuleUpdate, AutoResponderRuleDTO, MatchType
from features.auto_responder.safety import auto_responder_safety

logger = logging.getLogger(__name__)

class AutoResponderService:
    async def get_rules(self, telegram_id: int, active_only: bool = False) -> List[AutoResponderRuleDTO]:
        async with db.get_connection() as conn:
            query = "SELECT * FROM auto_responder_rules WHERE telegram_id = ?"
            params = [telegram_id]
            if active_only:
                query += " AND is_active = 1"
            
            cursor = await conn.execute(query, tuple(params))
            rows = await cursor.fetchall()
            
            return [AutoResponderRuleDTO(**dict(row)) for row in rows]

    async def create_rule(self, telegram_id: int, data: AutoResponderRuleCreate) -> AutoResponderRuleDTO:
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO auto_responder_rules 
                (telegram_id, match_type, pattern, response, chat_id, user_id_filter, cooldown_seconds, max_daily)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    telegram_id, 
                    data.match_type.value, 
                    data.pattern, 
                    data.response, 
                    data.chat_id, 
                    data.user_id_filter, 
                    data.cooldown_seconds, 
                    data.max_daily
                )
            )
            rule_id = cursor.lastrowid
            await conn.commit()
            
            cursor = await conn.execute("SELECT * FROM auto_responder_rules WHERE id = ?", (rule_id,))
            row = await cursor.fetchone()
            return AutoResponderRuleDTO(**dict(row))

    async def update_rule(self, rule_id: int, telegram_id: int, data: AutoResponderRuleUpdate) -> Optional[AutoResponderRuleDTO]:
        async with db.get_connection() as conn:
            updates = []
            params = []
            for k, v in data.model_dump(exclude_unset=True).items():
                if isinstance(v, MatchType):
                    v = v.value
                updates.append(f"{k} = ?")
                params.append(v)
            
            if not updates:
                cursor = await conn.execute("SELECT * FROM auto_responder_rules WHERE id = ? AND telegram_id = ?", (rule_id, telegram_id))
                row = await cursor.fetchone()
                return AutoResponderRuleDTO(**dict(row)) if row else None
                
            params.extend([rule_id, telegram_id])
            
            await conn.execute(
                f"UPDATE auto_responder_rules SET {', '.join(updates)} WHERE id = ? AND telegram_id = ?",
                tuple(params)
            )
            await conn.commit()
            
            cursor = await conn.execute("SELECT * FROM auto_responder_rules WHERE id = ? AND telegram_id = ?", (rule_id, telegram_id))
            row = await cursor.fetchone()
            return AutoResponderRuleDTO(**dict(row)) if row else None

    async def delete_rule(self, rule_id: int, telegram_id: int) -> bool:
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM auto_responder_rules WHERE id = ? AND telegram_id = ?",
                (rule_id, telegram_id)
            )
            await conn.commit()
            return cursor.rowcount > 0

    def test_rule(self, pattern: str, match_type: MatchType, test_message: str) -> bool:
        if not test_message:
            return False
            
        test_message_lower = test_message.lower()
        pattern_lower = pattern.lower()
        
        try:
            if match_type == MatchType.EXACT:
                return test_message_lower == pattern_lower
            elif match_type == MatchType.CONTAINS:
                return pattern_lower in test_message_lower
            elif match_type == MatchType.STARTS_WITH:
                return test_message_lower.startswith(pattern_lower)
            elif match_type == MatchType.REGEX:
                return bool(re.search(pattern, test_message, re.IGNORECASE))
        except re.error:
            logger.warning(f"Invalid regex pattern: {pattern}")
            return False
        except Exception as e:
            logger.error(f"Error evaluating rule: {e}")
            return False
            
        return False
        
    async def match_message(self, rule: AutoResponderRuleDTO, text: str) -> bool:
        return self.test_rule(rule.pattern, rule.match_type, text)

    async def process_incoming_message(self, telegram_id: int, event, client) -> None:
        text = getattr(event, 'text', '')
        if not text:
            return
            
        rules = await self.get_rules(telegram_id, active_only=True)
        if not rules:
            return
            
        chat_id = event.chat_id
        sender_id = event.sender_id
        
        for rule in rules:
            if rule.chat_id and rule.chat_id != chat_id:
                continue
            if rule.user_id_filter and rule.user_id_filter != sender_id:
                continue
                
            if rule.daily_count >= rule.max_daily:
                continue
                
            if auto_responder_safety.is_on_cooldown(telegram_id, chat_id, rule.id, rule.cooldown_seconds):
                continue
                
            is_match = await self.match_message(rule, text)
            if is_match:
                if auto_responder_safety.is_safe_to_respond(event, rule.response):
                    try:
                        await event.reply(rule.response)
                        
                        async with db.get_connection() as conn:
                            await conn.execute(
                                "UPDATE auto_responder_rules SET daily_count = daily_count + 1 WHERE id = ?",
                                (rule.id,)
                            )
                            await conn.execute(
                                "INSERT INTO feature_activity (telegram_id, feature_id, action, details) VALUES (?, ?, ?, ?)",
                                (telegram_id, "auto_responder", "responded", f"Rule {rule.id} matched in chat {chat_id}")
                            )
                            await conn.commit()
                            
                        break
                    except Exception as e:
                        logger.error(f"Failed to reply with auto responder: {e}")

auto_responder_service = AutoResponderService()
