"""The Sirio pump controller integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .api import SirioClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
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
    _remove_old_entities(hass, entry)
    client = SirioClient(hass, entry.data[CONF_HOST], entry.data[CONF_PORT])

    status = SirioCoordinator(hass, entry, client)
    await status.async_config_entry_first_refresh()

    params = SirioParamCoordinator(hass, entry, client)
    entry.runtime_data = SirioData(client=client, status=status, params=params)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Each parameter read takes ~1.7 s on the controller (~40 s for all of them),
    # so read them in the background: setup finishes as soon as the status is in,
    # and the parameter entities fill in when the read completes.
    entry.async_create_background_task(
        hass, params.async_refresh(), f"{entry.title} parameters first read"
    )
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


# Entities that earlier versions created: (platform, unique id suffix)
REMOVED_ENTITIES = (
    (Platform.BINARY_SENSOR, "stand_by"),  # replaced by the "Pump" switch
)


def _remove_old_entities(hass: HomeAssistant, entry: SirioConfigEntry) -> None:
    """Drop registry entries of entities this version no longer provides."""
    registry = er.async_get(hass)
    for platform, key in REMOVED_ENTITIES:
        entity_id = registry.async_get_entity_id(
            platform, DOMAIN, f"{entry.entry_id}_{key}"
        )
        if entity_id:
            registry.async_remove(entity_id)


async def async_unload_entry(hass: HomeAssistant, entry: SirioConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: SirioConfigEntry) -> None:
    """Apply changed options without a reload.

    The update interval goes straight to the status coordinator; the
    "allow parameter changes" option is read on every write anyway.
    """
    status = entry.runtime_data.status
    interval = timedelta(
        seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    if status.update_interval != interval:
        status.update_interval = interval
        # Refreshing reschedules the next poll with the new interval.
        await status.async_request_refresh()
    # Entities showing an option (the update interval) pick up the new value.
    status.async_update_listeners()
