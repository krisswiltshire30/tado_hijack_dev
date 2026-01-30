"""Helper to link Tado Hijack entities to existing HomeKit devices."""

from __future__ import annotations

from typing import cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .logging_utils import get_redacted_logger

_LOGGER = get_redacted_logger(__name__)

# Cache for device lookups (serial_no -> identifiers)
_device_cache: dict[str, set[tuple[str, str]] | None] = {}
_cache_built = False


def _build_device_cache(hass: HomeAssistant) -> None:
    """Build device cache from registry (called once per integration load)."""
    global _cache_built
    if _cache_built:
        return

    registry = dr.async_get(hass)
    _LOGGER.debug(
        "Building device registry cache from %d devices", len(registry.devices)
    )

    for device in registry.devices.values():
        if (
            device.manufacturer
            and "tado" in device.manufacturer.lower()
            and device.serial_number
        ):
            _device_cache[device.serial_number] = cast(
                set[tuple[str, str]], device.identifiers
            )
            _LOGGER.debug(
                "Cached device: serial=%s, name=%s",
                device.serial_number,
                device.name,
            )

    _cache_built = True
    _LOGGER.debug("Device cache built with %d Tado devices", len(_device_cache))


def get_homekit_identifiers(
    hass: HomeAssistant, serial_no: str
) -> set[tuple[str, str]] | None:
    """Find a device in the registry matching the serial number and return its identifiers.

    Uses a cache to avoid O(n*m) complexity during setup.
    """
    # Build cache on first call
    _build_device_cache(hass)

    # Lookup from cache
    return _device_cache.get(serial_no)


def get_climate_entity_id(hass: HomeAssistant, serial_no: str) -> str | None:
    """Find the climate entity ID associated with a Tado device serial via HomeKit."""
    d_registry = dr.async_get(hass)
    e_registry = er.async_get(hass)

    target_device = next(
        (
            device
            for device in d_registry.devices.values()
            if (
                device.manufacturer
                and "tado" in device.manufacturer.lower()
                and device.serial_number == serial_no
            )
        ),
        None,
    )
    if not target_device:
        return None

    # 2. Find the Climate Entity for this Device
    entries = er.async_entries_for_device(e_registry, target_device.id)
    return next(
        (str(entry.entity_id) for entry in entries if entry.domain == "climate"),
        None,
    )
