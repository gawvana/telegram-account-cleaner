import hashlib
from typing import Any, Dict, Optional
from config import settings
from database import db
from domain.models import ConsentDTO
from telegram_client.manager import client_manager
from utils.logger import logger

RULES_SUMMARY = """CLIN Service Rules & Privacy Terms (v1.0):
1. CLIN provides tools to inspect, organize, and clean your Telegram account dialogs, channels, and bots.
2. All operations (deletion, leaving channels, blocking bots) require explicit user confirmation.
3. Your session is encrypted locally using Fernet AES-128 with per-user salt. We do not store plaintext credentials or passwords.
4. You can withdraw consent and delete your session at any time.
"""


def get_terms_hash() -> str:
    """Returns SHA256 hash of the current legal terms."""
    return hashlib.sha256(RULES_SUMMARY.encode("utf-8")).hexdigest()[:16]


class ConsentService:
    """Manages versioned legal consent, compliance gating, and consent withdrawal."""

    async def has_valid_consent(self, telegram_id: int) -> bool:
        """Checks whether the user has actively accepted the current agreement and privacy versions."""
        record = await db.get_active_consent(telegram_id)
        if not record:
            return False

        # Verify version match
        try:
            agr_ver = int(record["agreement_version"])
            priv_ver = int(record["privacy_version"])
            return (
                agr_ver >= settings.AGREEMENT_VERSION
                and priv_ver >= settings.PRIVACY_VERSION
                and record["withdrawn_at"] is None
            )
        except (ValueError, TypeError):
            return False

    async def get_consent_status(self, telegram_id: int) -> Dict[str, Any]:
        """Returns structured consent status and required terms info."""
        has_consent = await self.has_valid_consent(telegram_id)
        record = await db.get_active_consent(telegram_id)

        return {
            "has_consent": has_consent,
            "required_agreement_version": settings.AGREEMENT_VERSION,
            "required_privacy_version": settings.PRIVACY_VERSION,
            "current_terms_hash": get_terms_hash(),
            "accepted_agreement_version": record["agreement_version"] if record else None,
            "accepted_privacy_version": record["privacy_version"] if record else None,
            "accepted_at": record["accepted_at"] if record else None,
            "rules_summary": RULES_SUMMARY,
        }

    async def record_user_consent(
        self,
        telegram_id: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Records explicit acceptance of CLIN terms and privacy policy."""
        terms_hash = get_terms_hash()
        consent_id = await db.record_consent(
            telegram_id=telegram_id,
            agreement_version=str(settings.AGREEMENT_VERSION),
            privacy_version=str(settings.PRIVACY_VERSION),
            terms_hash=terms_hash,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await db.append_audit_log(telegram_id, action="CONSENT_ACCEPTED")
        logger.info(f"User {telegram_id} accepted consent v{settings.AGREEMENT_VERSION}/{settings.PRIVACY_VERSION}")

        return {
            "consent_id": consent_id,
            "telegram_id": telegram_id,
            "agreement_version": settings.AGREEMENT_VERSION,
            "privacy_version": settings.PRIVACY_VERSION,
            "terms_hash": terms_hash,
            "has_consent": True,
        }

    async def withdraw_user_consent(self, telegram_id: int) -> bool:
        """
        Withdraws consent, logs out user session, and marks all active consents as revoked.
        """
        # 1. Revoke in DB
        withdrawn = await db.withdraw_consent(telegram_id)

        # 2. Logout active session and shred key files
        try:
            await client_manager.logout_user(telegram_id)
        except Exception as e:
            logger.warning(f"Error logging out session during consent withdrawal for {telegram_id}: {e}")

        # 3. Audit log
        await db.append_audit_log(telegram_id, action="CONSENT_WITHDRAWN")
        logger.info(f"User {telegram_id} withdrew consent. Session destroyed.")
        return withdrawn


consent_service = ConsentService()
