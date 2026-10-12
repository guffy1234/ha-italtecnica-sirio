"""Switches of the Sirio pump controller: run/stand-by and on/off parameters."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import SirioError
from .coordinator import SirioConfigEntry
from .entity import SirioEntity, SirioParamEntity, ensure_changes_allowed
from .parameters import RAW_OFF, RAW_ON, SWITCH_PARAMS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SirioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the run/stand-by switch and the on/off parameters."""
    async_add_entities(
        [
            SirioRunSwitch(entry),
            *(SirioSwitch(entry, index, name) for index, name in SWITCH_PARAMS),
        ]
    )


class SirioRunSwitch(SirioEntity, SwitchEntity):
    """Run / stand-by: the status icon (green ON / yellow STAND-BY) on the page."""

    _attr_name = "Pump"
    _attr_icon = "mdi:water-pump"

    def __init__(self, entry: SirioConfigEntry) -> None:
        super().__init__(entry.runtime_data.status, "run")
        self._entry = entry

    @property
    def is_on(self) -> bool | None:
        stand_by = self.coordinator.data.get("standBy")
        return None if stand_by is None else stand_by == 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set_running(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set_running(False)

    async def _async_set_running(self, run: bool) -> None:
        ensure_changes_allowed(self._entry)
        try:
            status = await self.coordinator.client.set_running(run)
        except SirioError as err:
            await self.coordinator.async_request_refresh()
            raise HomeAssistantError(
                f"Could not switch the pump {'on' if run else 'to stand-by'}: {err}"
            ) from err
        self.coordinator.async_set_updated_data(status)


class SirioSwitch(SirioParamEntity, SwitchEntity):
    """A parameter that is either ON (7) or OFF (8) on the controller."""

    def __init__(self, entry: SirioConfigEntry, index: int, name: str) -> None:
        super().__init__(entry, index)
        self._attr_name = name

    def _describe(self, raw: int) -> str:
        return {RAW_ON: "ON", RAW_OFF: "OFF"}.get(raw, f"code {raw}")

    @property
    def is_on(self) -> bool | None:
        raw = self._raw
        if raw == RAW_ON:
            return True
        if raw == RAW_OFF:
            return False
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_write(RAW_ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_write(RAW_OFF)
