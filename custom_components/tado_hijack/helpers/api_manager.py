"""Manages prioritized and debounced API access for Tado Hijack."""

from __future__ import annotations

import asyncio
import functools
import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from ..const import DEBOUNCE_COOLDOWN_S

if TYPE_CHECKING:
    from ..coordinator import TadoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class TadoApiManager:
    """Handles queuing, debouncing and sequential execution of API commands."""

    def __init__(
        self, hass: HomeAssistant, coordinator: TadoDataUpdateCoordinator
    ) -> None:
        """Initialize Tado API manager."""

        self.hass = hass
        self.coordinator = coordinator
        self._api_queue: asyncio.Queue[tuple[str, functools.partial]] = asyncio.Queue()
        self._action_queue: dict[str, tuple[str, functools.partial]] = {}
        self._pending_timers: dict[str, CALLBACK_TYPE] = {}
        self._worker_task: asyncio.Task | None = None

    def start(self, entry: ConfigEntry) -> None:
        """Start the background worker task using Home Assistant's background task handler."""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = entry.async_create_background_task(
                self.hass, self._worker_loop(), name="tado_api_manager_worker"
            )
            _LOGGER.debug("TadoApiManager background worker task started")

    def queue_action(
        self, key: str, type_key: str, target_func: functools.partial
    ) -> None:
        """Add an action to the debounce queue."""
        if "batch_timer" in self._pending_timers:
            self._pending_timers.pop("batch_timer")()

        self._action_queue[key] = (type_key, target_func)
        _LOGGER.debug(
            "Queue: Action '%s' added. Current batch size: %d",
            key,
            len(self._action_queue),
        )

        @callback
        def _move_to_worker(_now=None):
            self._pending_timers.pop("batch_timer", None)
            _LOGGER.info(
                "Queue: Batch window expired. Moving %d actions to worker.",
                len(self._action_queue),
            )
            for t_key, func in self._action_queue.values():
                self._api_queue.put_nowait((t_key, func))
            self._action_queue.clear()

        self._pending_timers["batch_timer"] = async_call_later(
            self.hass,
            DEBOUNCE_COOLDOWN_S,
            HassJob(_move_to_worker, cancel_on_shutdown=True),
        )

    async def _worker_loop(self) -> None:
        """Background loop to process the queue sequentially."""
        types_in_batch: set[str] = set()
        commands_in_batch: int = 0

        while True:
            try:
                type_key, target_func = await self._api_queue.get()
                types_in_batch.add(type_key)
                commands_in_batch += 1

                _LOGGER.debug("Worker: Executing %s command", type_key)
                try:
                    await target_func()
                    # Sync from headers if available (passive update)
                    self.coordinator.update_rate_limit_local(silent=True)
                except Exception as e:
                    _LOGGER.error("Worker: Command failed: %s", e)
                finally:
                    self._api_queue.task_done()

                # Batch confirmation after final command
                if self._api_queue.empty():
                    if self.coordinator.is_throttled:
                        # Throttled mode: skip refresh, just decrement internal counter
                        _LOGGER.debug(
                            "Worker: Batch complete (throttled mode), "
                            "skipping refresh for %d commands",
                            commands_in_batch,
                        )
                        self.coordinator.decrement_internal_remaining(commands_in_batch)
                        self.coordinator.update_rate_limit_local(silent=False)
                    else:
                        # Normal mode: sync states from API
                        _LOGGER.debug(
                            "Worker: Batch complete, syncing types: %s", types_in_batch
                        )
                        await self.coordinator.async_sync_states(list(types_in_batch))
                    types_in_batch.clear()
                    commands_in_batch = 0

            except asyncio.CancelledError:
                _LOGGER.debug("API worker loop cancelled")
                break
            except Exception as e:
                _LOGGER.exception("Unexpected error in worker loop: %s", e)
                await asyncio.sleep(DEBOUNCE_COOLDOWN_S)
