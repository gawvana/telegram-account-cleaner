import pytest
from config import settings
from database import Database
from services.consent_service import ConsentService


@pytest.mark.asyncio
async def test_consent_lifecycle_and_versioning(tmp_path):
    test_db_path = str(tmp_path / "test_consent.db")
    db_instance = Database(db_path=test_db_path)
    await db_instance.init_db()

    user_id = 998877
    # Ensure user exists for foreign key constraint
    await db_instance.get_or_create_user(telegram_id=user_id, salt="testsalt123")

    # Monkeypatch db in consent_service
    import services.consent_service as cs_module
    old_db = cs_module.db
    cs_module.db = db_instance

    try:
        service = ConsentService()

        # 1. Before consent: has_valid_consent should be False
        has_consent = await service.has_valid_consent(user_id)
        assert has_consent is False

        status = await service.get_consent_status(user_id)
        assert status["has_consent"] is False
        assert status["required_agreement_version"] == settings.AGREEMENT_VERSION

        # 2. Record consent
        recorded = await service.record_user_consent(user_id, ip_address="127.0.0.1", user_agent="PyTest")
        assert recorded["has_consent"] is True
        assert recorded["agreement_version"] == settings.AGREEMENT_VERSION

        # 3. After consent: has_valid_consent should be True
        has_consent = await service.has_valid_consent(user_id)
        assert has_consent is True

        # 4. Withdraw consent
        withdrawn = await service.withdraw_user_consent(user_id)
        assert withdrawn is True

        # 5. After withdrawal: has_valid_consent should be False again
        has_consent = await service.has_valid_consent(user_id)
        assert has_consent is False

    finally:
        cs_module.db = old_db
