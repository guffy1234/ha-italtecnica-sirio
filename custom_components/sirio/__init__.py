"""The Sirio pump controller integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .api import SirioClient
from .coordinator import (
    SirioConfigEntry,
    SirioCoordinator,
    SirioData,
    SirioParamCoordinator,
)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: SirioConfigEntry) -> bool:
    """Set up Sirio from a config entry."""
    client = SirioClient(hass, entry.data[CONF_HOST], entry.data[CONF_PORT])

    status = SirioCoordinator(hass, entry, client)
    await status.async_config_entry_first_refresh()

    # Parameters are secondary: a failed first read must not block setup.
    params = SirioParamCoordinator(hass, entry, client)
    await params.async_refresh()

    entry.runtime_data = SirioData(client=client, status=status, params=params)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SirioConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: SirioConfigEntry) -> None:
    """Reload when the options change."""
    await hass.config_entries.async_reload(entry.entry_id)
