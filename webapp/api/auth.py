import hashlib
import hmac
import json
import time
import urllib.parse
from typing import Any, Dict, Optional
from fastapi import Header, HTTPException, status
from jose import JWTError, jwt

from config import settings
from utils.logger import logger


def validate_telegram_init_data(
    init_data_raw: str,
    bot_token: str = "",
    max_age_seconds: int = 86400,
) -> Dict[str, Any]:
    """
    Validates official Telegram WebApp initData string using HMAC-SHA256.
    Returns parsed dictionary if valid, raises HTTPException(401) if invalid.
    """
    token = bot_token or settings.BOT_TOKEN
    if not token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bot token is not configured on the server."
        )

    try:
        parsed_qsl = urllib.parse.parse_qsl(init_data_raw, keep_blank_values=True)
        data_dict = dict(parsed_qsl)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth format")

    if "hash" not in data_dict:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing hash parameter")

    received_hash = data_dict.pop("hash")

    # Step 1: Create data_check_string by sorting keys alphabetically
    sorted_items = sorted(data_dict.items(), key=lambda x: x[0])
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted_items)

    # Step 2: Compute secret key = HMAC-SHA256(b"WebAppData", bot_token)
    secret_key = hmac.new(b"WebAppData", token.encode("utf-8"), hashlib.sha256).digest()

    # Step 3: Compute calculated hash = HMAC-SHA256(secret_key, data_check_string)
    calculated_hash = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    # Step 4: Timing-safe comparison
    if not hmac.compare_digest(calculated_hash, received_hash):
        logger.warning("Telegram WebApp initData HMAC verification failed.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="HMAC signature invalid")

    # Step 5: Check auth_date expiration and clock skew
    auth_date_str = data_dict.get("auth_date")
    if not auth_date_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth_date")

    try:
        auth_date = int(auth_date_str)
        now = time.time()
        # Clock skew / future timestamp check (max 60 seconds tolerance)
        if auth_date > now + 60:
            logger.warning(f"Telegram initData has future auth_date: {auth_date} > {now}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="InitData timestamp is in the future")

        if now - auth_date > max_age_seconds:
            logger.warning(f"Telegram initData expired (age: {int(now - auth_date)}s)")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="InitData expired")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed auth_date")

    # Parse user JSON if present
    if "user" in data_dict:
        try:
            data_dict["user_parsed"] = json.loads(data_dict["user"])
        except Exception:
            data_dict["user_parsed"] = {}

    return data_dict


def create_access_token(data: dict, expires_delta_seconds: Optional[int] = None) -> str:
    """Creates signed JWT token for session storage using effective secret."""
    to_encode = data.copy()
    expire = time.time() + (expires_delta_seconds or (settings.JWT_EXPIRATION_MINUTES * 60))
    to_encode.update({"exp": expire})
    secret = settings.get_effective_jwt_secret()
    return jwt.encode(to_encode, secret, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decodes and validates JWT token."""
    try:
        secret = settings.get_effective_jwt_secret()
        payload = jwt.decode(token, secret, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


async def get_current_user_id(authorization: Optional[str] = Header(None)) -> int:
    """
    FastAPI dependency extracting and validating authenticated Telegram User ID.
    Supports either:
      Authorization: tma <raw_init_data>
      Authorization: Bearer <jwt_token>
    """
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization required")

    parts = authorization.split(" ", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth header format")

    auth_type, auth_value = parts[0].strip(), parts[1].strip()

    if auth_type.lower() == "tma":
        # Validate initData directly
        data = validate_telegram_init_data(auth_value)
        user_info = data.get("user_parsed")
        if not user_info or "id" not in user_info:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User id missing in initData")
        return int(user_info["id"])

    elif auth_type.lower() == "bearer":
        payload = decode_access_token(auth_value)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")
        return int(user_id)

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unsupported auth scheme")
