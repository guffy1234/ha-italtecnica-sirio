"""On/off parameters of the Sirio pump controller."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SirioConfigEntry
from .entity import SirioParamEntity
from .parameters import RAW_OFF, RAW_ON, SWITCH_PARAMS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SirioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sirio on/off parameters."""
    async_add_entities(SirioSwitch(entry, index, name) for index, name in SWITCH_PARAMS)


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
