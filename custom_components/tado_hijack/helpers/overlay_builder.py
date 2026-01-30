"""Helpers for building Tado API overlay payloads."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..const import (
    OVERLAY_NEXT_BLOCK,
    OVERLAY_PRESENCE,
    OVERLAY_TIMER,
    POWER_ON,
    TEMP_MAX_AC,
    TEMP_MAX_HEATING,
    TEMP_MAX_HOT_WATER,
    TERMINATION_MANUAL,
    TERMINATION_NEXT_TIME_BLOCK,
    TERMINATION_TADO_MODE,
    TERMINATION_TIMER,
    ZONE_TYPE_HEATING,
    ZONE_TYPE_HOT_WATER,
)
from .logging_utils import get_redacted_logger
from .overlay_validator import validate_overlay_payload

if TYPE_CHECKING:
    from tadoasync.models import Zone

_LOGGER = get_redacted_logger(__name__)


def get_capped_temperature(
    zone_id: int, temperature: float, zones_meta: dict[int, Zone]
) -> float:
    """Get safety-capped temperature based on zone type."""
    zone = zones_meta.get(zone_id)
    ztype = getattr(zone, "type", ZONE_TYPE_HEATING) if zone else ZONE_TYPE_HEATING

    limit = TEMP_MAX_HEATING if ztype == ZONE_TYPE_HEATING else TEMP_MAX_AC
    if ztype == ZONE_TYPE_HOT_WATER:
        limit = TEMP_MAX_HOT_WATER

    return min(temperature, limit)


def build_overlay_data(
    zone_id: int,
    zones_meta: dict[int, Zone],
    power: str = POWER_ON,
    temperature: float | None = None,
    duration: int | None = None,
    overlay_type: str | None = None,
    overlay_mode: str | None = None,
    ac_mode: str | None = None,
    supports_temp: bool = True,
) -> dict[str, Any]:
    """Build the overlay data dictionary for Tado API.

    Args:
        zone_id: Zone ID
        zones_meta: Zone metadata dict
        power: Power state (ON/OFF)
        temperature: Target temperature (optional)
        duration: Duration in minutes (optional)
        overlay_type: Zone type override (optional)
        overlay_mode: Overlay mode (manual/next_block/presence)
        ac_mode: AC mode for AIR_CONDITIONING zones (optional)
        supports_temp: Whether zone supports temperature (for HOT_WATER OpenTherm detection)

    """
    if not overlay_type:
        zone = zones_meta.get(zone_id)
        overlay_type = (
            getattr(zone, "type", ZONE_TYPE_HEATING) if zone else ZONE_TYPE_HEATING
        )

    if overlay_mode == OVERLAY_NEXT_BLOCK:
        termination: dict[str, Any] = {"typeSkillBasedApp": TERMINATION_NEXT_TIME_BLOCK}
    elif overlay_mode == OVERLAY_PRESENCE:
        termination = {"type": TERMINATION_TADO_MODE}
    elif overlay_mode == OVERLAY_TIMER or duration:
        duration_seconds = duration * 60 if duration else 1800
        termination = {
            "typeSkillBasedApp": TERMINATION_TIMER,
            "durationInSeconds": duration_seconds,
        }
    else:
        termination = {"typeSkillBasedApp": TERMINATION_MANUAL}

    setting: dict[str, Any] = {"type": overlay_type, "power": power}
    if ac_mode:
        setting["mode"] = ac_mode

    # Add temperature if supported and provided
    # Hot Water without OpenTherm does NOT support temperature in overlays
    if (
        temperature is not None
        and power == POWER_ON
        and (overlay_type != ZONE_TYPE_HOT_WATER or supports_temp)
    ):
        capped_temp = get_capped_temperature(zone_id, temperature, zones_meta)
        setting["temperature"] = {"celsius": capped_temp}

    payload = {"setting": setting, "termination": termination}

    # Validate payload before returning (saves API quota on invalid requests)
    is_valid, error = validate_overlay_payload(payload, overlay_type, supports_temp)
    if not is_valid:
        _LOGGER.error(
            "Overlay validation failed for zone %d (type=%s): %s",
            zone_id,
            overlay_type,
            error,
        )
        raise ValueError(f"Invalid overlay payload: {error}")

    return payload
