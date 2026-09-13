import datetime
import json
import re
from typing import Any, Optional


def mask_phone(phone: Optional[str]) -> str:
    """Masks a phone number for privacy display: +79991234567 -> +7 *** *** 4567."""
    if not phone:
        return "Unknown"
    digits = re.sub(r"\D", "", phone)
    if len(digits) <= 4:
        return "****"
    prefix = "+" if phone.startswith("+") else ""
    country_code = digits[: len(digits) - 8] if len(digits) > 8 else digits[:1]
    last_four = digits[-4:]
    return f"{prefix}{country_code} *** *** {last_four}"


def mask_token(token: Optional[str]) -> str:
    """Masks a token or secret showing only first 4 and last 4 characters."""
    if not token or len(token) <= 8:
        return "********"
    return f"{token[:4]}...{token[-4:]}"


def format_timestamp(dt: Optional[datetime.datetime] = None) -> str:
    """Returns ISO format or current UTC formatted timestamp."""
    if dt is None:
        dt = datetime.datetime.now(datetime.timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def format_bytes(num_bytes: int) -> str:
    """Formats bytes into human readable KB, MB, GB."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def safe_json_dumps(obj: Any) -> str:
    """Safely serializes objects containing dates and non-standard types to JSON."""
    def default_serializer(o: Any) -> Any:
        if isinstance(o, (datetime.datetime, datetime.date)):
            return o.isoformat()
        if hasattr(o, "__dict__"):
            return o.__dict__
        return str(o)

    return json.dumps(obj, default=default_serializer, ensure_ascii=False, indent=2)
