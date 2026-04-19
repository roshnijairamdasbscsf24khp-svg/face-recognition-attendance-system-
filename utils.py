"""Utility helpers shared across modules."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable


def ensure_directories(paths: Iterable[Path]) -> None:
    """Create missing directories required by the application."""
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def current_timestamp() -> str:
    """Return current local timestamp in database-friendly format."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_date() -> str:
    """Return current local date."""
    return datetime.now().strftime("%Y-%m-%d")