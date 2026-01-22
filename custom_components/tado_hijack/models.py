"""Models for Tado Hijack."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, TypedDict


@dataclass(slots=True)
class RateLimit:
    """Model for API Rate Limit statistics."""

    limit: int
    remaining: int


class TadoCoordinatorData(TypedDict):
    """Type definition for coordinator.data dictionary.

    Provides type safety and IDE autocomplete for data dictionary access.
    Updated by DataManager.fetch_full_update() and coordinator._async_update_data().
    """

    home_state: dict[str, Any]
    zone_states: dict[str, Any]
    rate_limit: RateLimit
    api_status: str
    zones: list[Any]
    devices: list[Any]
    capabilities: dict[int, Any]
    offsets: dict[str, Any]
    away_config: dict[int, float]


class CommandType(StrEnum):
    """Types of API commands."""

    SET_OVERLAY = "set_overlay"
    RESUME_SCHEDULE = "resume_schedule"
    SET_PRESENCE = "set_presence"
    MANUAL_POLL = "manual_poll"
    SET_CHILD_LOCK = "set_child_lock"
    SET_OFFSET = "set_offset"
    SET_AWAY_TEMP = "set_away_temp"
    SET_DAZZLE = "set_dazzle"
    SET_EARLY_START = "set_early_start"
    SET_OPEN_WINDOW = "set_open_window"
    IDENTIFY = "identify"


@dataclass
class TadoCommand:
    """Represents a queued API command."""

    cmd_type: CommandType
    zone_id: int | None = None
    data: dict[str, Any] | None = None
