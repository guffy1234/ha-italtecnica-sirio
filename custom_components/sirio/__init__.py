"""The Sirio pump controller integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import async_get_platforms

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
    client = SirioClient(hass, entry.data[CONF_HOST], entry.data[CONF_PORT])

    status = SirioCoordinator(hass, entry, client)
    await status.async_config_entry_first_refresh()

    params = SirioParamCoordinator(hass, entry, client)
    entry.runtime_data = SirioData(client=client, status=status, params=params)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _remove_old_entities(hass, entry)

    # Each parameter read takes ~1.7 s on the controller (~40 s for all of them),
    # so read them in the background: setup finishes as soon as the status is in,
    # and the parameter entities fill in when the read completes.
    entry.async_create_background_task(
        hass, params.async_refresh(), f"{entry.title} parameters first read"
    )
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


def _remove_old_entities(hass: HomeAssistant, entry: SirioConfigEntry) -> None:
    """Drop registry entries of entities this version no longer provides.

    Earlier versions had other entities (e.g. "Max current", "Max frequency",
    "Stand-by"); without this they stay behind as unavailable. Runs after the
    platforms are set up: an enabled entry that no platform added is stale.
    Disabled entries are kept, since disabled entities are never added.
    """
    platforms = [
        platform
        for platform in async_get_platforms(hass, DOMAIN)
        if platform.config_entry is entry
    ]
    if {platform.domain for platform in platforms} != set(PLATFORMS):
        # A platform failed to set up: its entities are missing, not stale.
        return
    provided = {
        entity_id for platform in platforms for entity_id in platform.entities
    }
    registry = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg_entry.disabled_by is None and reg_entry.entity_id not in provided:
            registry.async_remove(reg_entry.entity_id)


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
