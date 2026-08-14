"""
Small generic helpers used across the scraper and services layers.
"""
import asyncio
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Optional


def make_lead_id(maps_url: str, name: str) -> str:
    """Deterministic id. maps_url is the primary identity; falls back to name."""
    seed = maps_url or name or ""
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


def normalize_whitespace(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def normalize_name(value: Optional[str]) -> str:
    return normalize_whitespace(value).lower()


def normalize_phone_for_matching(phone: Optional[str]) -> str:
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    # Keep the last 10 digits so country-code variants still match.
    return digits[-10:] if len(digits) >= 10 else digits


def normalize_url(url: Optional[str]) -> str:
    if not url:
        return ""
    url = url.strip()
    url = re.sub(r"^https?://(www\.)?", "", url, flags=re.IGNORECASE)
    url = url.rstrip("/")
    return url.lower()


def safe_read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def safe_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp_path.replace(path)


async def run_with_timeout(coro, timeout_seconds: float):
    """Wrap a coroutine with a hard timeout. Raises asyncio.TimeoutError on expiry."""
    return await asyncio.wait_for(coro, timeout=timeout_seconds)


def extract_city_from_address(address: str) -> str:
    """Best-effort city extraction: assume the second-to-last comma segment."""
    if not address:
        return ""
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if len(parts) >= 2:
        # Strip trailing pincode-only tokens from the candidate segment.
        candidate = parts[-2]
        candidate = re.sub(r"\d{6}", "", candidate).strip()
        return candidate
    return ""