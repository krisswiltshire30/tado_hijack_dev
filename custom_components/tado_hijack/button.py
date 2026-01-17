"""Button platform for Tado Hijack."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.button import ButtonEntity
from homeassistant.core import CALLBACK_TYPE, HassJob, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import DEBOUNCE_COOLDOWN_S
from .entity import TadoHomeEntity

if TYPE_CHECKING:
    from . import TadoConfigEntry
    from .coordinator import TadoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: Any,
    entry: TadoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tado buttons based on a config entry."""
    coordinator: TadoDataUpdateCoordinator = entry.runtime_data
    async_add_entities(
        [
            TadoManualPollButton(coordinator),
            TadoResumeAllSchedulesButton(coordinator),
        ]
    )


class TadoManualPollButton(TadoHomeEntity, ButtonEntity):
    """Button to trigger a manual poll."""

    def __init__(self, coordinator: TadoDataUpdateCoordinator) -> None:
        """Initialize manual poll button."""
        super().__init__(coordinator, "manual_poll")
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_manual_poll"
        self._pending_timer: CALLBACK_TYPE | None = None

    async def async_press(self) -> None:
        """Handle button press with trailing debounce."""
        # Cancel existing timer if any
        if self._pending_timer is not None:
            self._pending_timer()
            self._pending_timer = None
            _LOGGER.debug("Manual poll: timer reset")

        @callback
        def _execute_after_debounce(_now: Any = None) -> None:
            self._pending_timer = None
            _LOGGER.info("Manual poll triggered via button (after debounce)")
            self.hass.async_create_task(self._execute_and_update())

        self._pending_timer = async_call_later(
            self.hass,
            DEBOUNCE_COOLDOWN_S,
            HassJob(_execute_after_debounce, cancel_on_shutdown=True),
        )
        _LOGGER.debug("Manual poll: debounce timer started (%ds)", DEBOUNCE_COOLDOWN_S)

    async def _execute_and_update(self) -> None:
        """Execute the action and update the UI state."""
        await self.tado_coordinator.async_manual_poll()
        self.async_write_ha_state()


class TadoResumeAllSchedulesButton(TadoHomeEntity, ButtonEntity):
    """Button to resume all zone schedules."""

    def __init__(self, coordinator: TadoDataUpdateCoordinator) -> None:
        """Initialize resume all schedules button."""
        super().__init__(coordinator, "resume_all_schedules")
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_resume_all"
        self._pending_timer: CALLBACK_TYPE | None = None

    async def async_press(self) -> None:
        """Handle button press with trailing debounce."""
        # Cancel existing timer if any
        if self._pending_timer is not None:
            self._pending_timer()
            self._pending_timer = None
            _LOGGER.debug("Resume all: timer reset")

        @callback
        def _execute_after_debounce(_now: Any = None) -> None:
            self._pending_timer = None
            _LOGGER.info("Resume all schedules triggered via button (after debounce)")
            self.hass.async_create_task(self._execute_and_update())

        self._pending_timer = async_call_later(
            self.hass,
            DEBOUNCE_COOLDOWN_S,
            HassJob(_execute_after_debounce, cancel_on_shutdown=True),
        )
        _LOGGER.debug("Resume all: debounce timer started (%ds)", DEBOUNCE_COOLDOWN_S)

    async def _execute_and_update(self) -> None:
        """Execute the action and update the UI state."""
        await self.tado_coordinator.async_resume_all_schedules()
        self.async_write_ha_state()
