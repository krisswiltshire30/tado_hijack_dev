"""Data Update Coordinator for Tado Hijack."""

from __future__ import annotations

import functools
import logging
import time
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from tadoasync import Tado, TadoError

if TYPE_CHECKING:
    from tadoasync.models import Device, Zone
    from . import TadoConfigEntry

from .const import (
    CONF_DISABLE_POLLING_WHEN_THROTTLED,
    CONF_OFFSET_POLL_INTERVAL,
    CONF_REFRESH_TOKEN,
    CONF_SLOW_POLL_INTERVAL,
    CONF_THROTTLE_THRESHOLD,
    DEFAULT_OFFSET_POLL_INTERVAL,
    DEFAULT_SLOW_POLL_INTERVAL,
    DEFAULT_THROTTLE_THRESHOLD,
    DOMAIN,
    OPTIMISTIC_GRACE_PERIOD_S,
)
from .helpers.api_manager import TadoApiManager
from .helpers.data_manager import TadoDataManager
from .helpers.patch import RATE_LIMIT_DATA
from .models import RateLimit

_LOGGER = logging.getLogger(__name__)


class TadoDataUpdateCoordinator(DataUpdateCoordinator):
    """Orchestrates Tado integration logic via specialized managers."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TadoConfigEntry,
        client: Tado,
        scan_interval: int,
    ):
        """Initialize Tado coordinator."""
        self._tado = client

        # scan_interval = 0 means no periodic polling
        update_interval = (
            timedelta(seconds=scan_interval) if scan_interval > 0 else None
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self._refresh_token = entry.data.get(CONF_REFRESH_TOKEN)

        # Throttle Configuration (0 = disabled, >0 = throttle when remaining < threshold)
        self._throttle_threshold: int = int(
            entry.data.get(CONF_THROTTLE_THRESHOLD, DEFAULT_THROTTLE_THRESHOLD)
        )
        self._disable_polling_when_throttled: bool = bool(
            entry.data.get(CONF_DISABLE_POLLING_WHEN_THROTTLED, False)
        )
        self._internal_remaining: int = 100  # Will be synced from headers

        # Initialize Managers
        slow_poll_s = (
            entry.data.get(CONF_SLOW_POLL_INTERVAL, DEFAULT_SLOW_POLL_INTERVAL) * 3600
        )
        offset_poll_s = (
            entry.data.get(CONF_OFFSET_POLL_INTERVAL, DEFAULT_OFFSET_POLL_INTERVAL)
            * 3600
        )
        self.data_manager = TadoDataManager(self, client, slow_poll_s, offset_poll_s)
        self.api_manager = TadoApiManager(hass, self)

        # State Tracking
        self.optimistic_presence: str | None = None
        self.optimistic_time: float = 0
        self.optimistic_zones: dict[int, dict[str, Any]] = {}

        self.zones_meta: dict[int, Zone] = {}
        self.devices_meta: dict[str, Device] = {}

        self.api_manager.start(entry)

    @property
    def zones_meta_public(self):
        """Return the zones metadata."""
        return self.zones_meta

    @property
    def is_throttled(self) -> bool:
        """Return True if throttled mode is active based on threshold and remaining calls."""
        # threshold = 0 means throttling is disabled
        if self._throttle_threshold == 0:
            return False
        # Otherwise throttle when remaining drops below threshold
        return self._internal_remaining < self._throttle_threshold

    @property
    def api_status(self) -> str:
        """Return current API status for sensor."""
        remaining = self._internal_remaining
        if remaining <= 0:
            return "rate_limited"
        return "throttled" if self.is_throttled else "connected"

    def decrement_internal_remaining(self, count: int = 1) -> None:
        """Decrement internal remaining counter (used in throttled mode)."""
        self._internal_remaining = max(0, self._internal_remaining - count)
        _LOGGER.debug("Internal remaining decremented to %d", self._internal_remaining)

    def sync_remaining_from_headers(self) -> None:
        """Sync internal remaining from actual API headers."""
        header_remaining = int(
            RATE_LIMIT_DATA.get("remaining", self._internal_remaining)
        )
        if header_remaining != self._internal_remaining:
            _LOGGER.debug(
                "Syncing internal remaining: %d -> %d",
                self._internal_remaining,
                header_remaining,
            )
            self._internal_remaining = header_remaining

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch update via DataManager."""
        try:
            data = await self.data_manager.fetch_full_update()

            self.zones_meta = self.data_manager.zones_meta
            self.devices_meta = self.data_manager.devices_meta

            # Sync rotated token
            if self._tado.refresh_token != self._refresh_token:
                self._refresh_token = self._tado.refresh_token
                if self.config_entry is None:
                    raise UpdateFailed("Config entry not available for token sync")
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        **self.config_entry.data,
                        CONF_REFRESH_TOKEN: self._refresh_token,
                    },
                )

            self._cleanup_optimistic()

            # Sync internal remaining from headers
            self.sync_remaining_from_headers()

            # Inject real-time RateLimit and API status
            data["rate_limit"] = RateLimit(
                limit=int(RATE_LIMIT_DATA.get("limit", 0)),
                remaining=self._internal_remaining,
            )
            data["api_status"] = self.api_status
            return data
        except TadoError as err:
            raise UpdateFailed(f"Tado API error: {err}") from err

    def _cleanup_optimistic(self):
        """Clean up expired optimistic states."""
        now = time.monotonic()
        if (now - self.optimistic_time) > OPTIMISTIC_GRACE_PERIOD_S:
            self.optimistic_presence = None

        to_delete = [
            z_id
            for z_id, d in self.optimistic_zones.items()
            if (now - d["time"]) > OPTIMISTIC_GRACE_PERIOD_S
        ]
        for z_id in to_delete:
            del self.optimistic_zones[z_id]

    async def async_manual_poll(self) -> None:
        """Trigger a manual poll."""
        self.data_manager.invalidate_cache()
        await self.async_refresh()

    def update_rate_limit_local(self, silent: bool = False) -> None:
        """Update local stats and sync internal remaining from headers."""
        self.sync_remaining_from_headers()
        self.data["rate_limit"] = RateLimit(
            limit=int(RATE_LIMIT_DATA.get("limit", 0)),
            remaining=self._internal_remaining,
        )
        self.data["api_status"] = self.api_status
        if not silent:
            self.async_update_listeners()

    async def async_sync_states(self, types: list[str]) -> None:
        """Targeted refresh after worker actions."""
        if "presence" in types:
            self.data["home_state"] = await self._tado.get_home_state()
        if "zone" in types:
            self.data["zone_states"] = await self._tado.get_zone_states()

        self.update_rate_limit_local(silent=False)

    async def async_set_zone_auto(self, zone_id: int):
        """Set zone to auto mode."""
        self.optimistic_zones[zone_id] = {"overlay": False, "time": time.monotonic()}
        self.async_update_listeners()
        self.api_manager.queue_action(
            f"zone_{zone_id}",
            "zone",
            functools.partial(self._tado.reset_zone_overlay, zone_id),
        )

    async def async_set_zone_heat(self, zone_id: int, temp: float = 25.0):
        """Set zone to manual heat mode."""
        self.optimistic_zones[zone_id] = {"overlay": True, "time": time.monotonic()}
        self.async_update_listeners()
        self.api_manager.queue_action(
            f"zone_{zone_id}",
            "zone",
            functools.partial(
                self._tado.set_zone_overlay,
                zone_id,
                "MANUAL",
                set_temp=temp,
                power="ON",
            ),
        )

    async def async_set_presence_debounced(self, presence: str):
        """Set presence state."""
        self.optimistic_presence = presence
        self.optimistic_time = time.monotonic()
        self.async_update_listeners()
        self.api_manager.queue_action(
            "presence", "presence", functools.partial(self._tado.set_presence, presence)
        )

    async def async_resume_all_schedules(self) -> None:
        """Resume all zone schedules."""
        for zone_id in self.zones_meta:
            await self.async_set_zone_auto(zone_id)
