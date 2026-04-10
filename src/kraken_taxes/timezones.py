from __future__ import annotations

from datetime import UTC, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def resolve_timezone(name: str) -> tzinfo:
    if name.upper() == "UTC":
        return UTC
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            f"Could not load timezone {name!r}. "
            "Install the `tzdata` dependency or correct the configuration value."
        ) from exc
