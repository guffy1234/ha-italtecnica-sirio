"""Choice parameters of the Sirio pump controller."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SirioConfigEntry
from .entity import SirioParamEntity
from .parameters import SELECT_PARAMS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SirioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sirio choice parameters."""
    async_add_entities(
        SirioSelect(entry, index, name, options) for index, name, options in SELECT_PARAMS
    )


class SirioSelect(SirioParamEntity, SelectEntity):
    """A parameter with a fixed set of values."""

    def __init__(
        self,
        entry: SirioConfigEntry,
        index: int,
        name: str,
        options: dict[int, str],
    ) -> None:
        super().__init__(entry, index)
        self._attr_name = name
        self._to_label = options
        self._to_raw = {label: raw for raw, label in options.items()}
        self._attr_options = list(options.values())

    def _describe(self, raw: int) -> str:
        return self._to_label.get(raw, f"code {raw}")

    @property
    def current_option(self) -> str | None:
        raw = self._raw
        return None if raw is None else self._to_label.get(raw)

    async def async_select_option(self, option: str) -> None:
        await self._async_write(self._to_raw[option])
