"""Data update coordinators for the Sirio pump controller."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SirioClient, SirioError
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MANUFACTURER,
    PARAM_RETRY_INTERVAL,
    PARAM_SCAN_INTERVAL,
)
from .parameters import PARAM_INDEXES

_LOGGER = logging.getLogger(__name__)


class SirioCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll the runtime status once per interval and share the result."""

    config_entry: SirioConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: SirioConfigEntry, client: SirioClient
    ) -> None:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} status",
            update_interval=timedelta(seconds=interval),
        )
        self.client = client
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model="Sirio Universal",
            configuration_url=(
                f"http://{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}/management.html"
            ),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.client.get_status()
        except SirioError as err:
            raise UpdateFailed(str(err)) from err


class SirioParamCoordinator(DataUpdateCoordinator[dict[int, int]]):
    """Read the base parameters (raw values) every few minutes and after changes."""

    config_entry: SirioConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: SirioConfigEntry, client: SirioClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} parameters",
            update_interval=timedelta(seconds=PARAM_SCAN_INTERVAL),
        )
        self.client = client

    async def _async_update_data(self) -> dict[int, int]:
        read = await self.client.get_params(PARAM_INDEXES)
        if not read:
            raise UpdateFailed("Could not read any parameter")
        # A failed read keeps the previous value for that parameter. Merge into
        # the current data (not a copy taken before the reads), so a value set
        # by a parameter change is never replaced by an older one.
        values = {**(self.data or {}), **read}
        # Never read yet: try again soon instead of showing nothing for 5 minutes.
        missing = set(PARAM_INDEXES) - values.keys()
        self.update_interval = timedelta(
            seconds=PARAM_RETRY_INTERVAL if missing else PARAM_SCAN_INTERVAL
        )
        if missing:
            _LOGGER.debug("Parameters not read yet: %s", sorted(missing))
        return values


@dataclass
class SirioData:
    """Everything one config entry needs at runtime."""

    client: SirioClient
    status: SirioCoordinator
    params: SirioParamCoordinator


type SirioConfigEntry = ConfigEntry[SirioData]
