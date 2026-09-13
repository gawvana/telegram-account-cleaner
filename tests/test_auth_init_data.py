import hashlib
import hmac
import time
import urllib.parse
import pytest
from fastapi import HTTPException

from webapp.api.auth import validate_telegram_init_data


def generate_valid_init_data(bot_token: str, user_id: int = 12345678, age_seconds: int = 10) -> str:
    auth_date = int(time.time()) - age_seconds
    user_json = f'{{"id":{user_id},"first_name":"Alex","username":"alex_test"}}'

    params = {
        "auth_date": str(auth_date),
        "query_id": "AAHdF6IQAAAAAN0XohD5p_aE",
        "user": user_json,
    }

    # Sort items
    sorted_items = sorted(params.items(), key=lambda x: x[0])
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted_items)

    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    data_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    params["hash"] = data_hash
    return urllib.parse.urlencode(params)


def test_validate_init_data_success():
    bot_token = "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ1234567"
    raw_init_data = generate_valid_init_data(bot_token, user_id=987654)

    parsed = validate_telegram_init_data(raw_init_data, bot_token=bot_token)
    assert parsed["user_parsed"]["id"] == 987654
    assert parsed["user_parsed"]["username"] == "alex_test"


def test_validate_init_data_tampered():
    bot_token = "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ1234567"
    raw_init_data = generate_valid_init_data(bot_token, user_id=987654)

    # Tamper with user parameter
    tampered_data = raw_init_data.replace("alex_test", "hacker")

    with pytest.raises(HTTPException) as exc_info:
        validate_telegram_init_data(tampered_data, bot_token=bot_token)
    assert exc_info.value.status_code == 401
    assert "signature invalid" in exc_info.value.detail.lower()


def test_validate_init_data_expired():
    bot_token = "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ1234567"
    # Age 100000 seconds > default 86400 max age
    expired_data = generate_valid_init_data(bot_token, user_id=987654, age_seconds=100000)

    with pytest.raises(HTTPException) as exc_info:
        validate_telegram_init_data(expired_data, bot_token=bot_token, max_age_seconds=86400)
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()
