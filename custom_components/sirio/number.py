"""Numeric parameters of the Sirio pump controller."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfPressure
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SirioConfigEntry
from .entity import SirioParamEntity
from .parameters import NUMBER_PARAMS, NumberParam

PSI_FACTOR = 14.5  # only used to widen the UI range when the controller runs in psi


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SirioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sirio numeric parameters."""
    async_add_entities(SirioNumber(entry, param) for param in NUMBER_PARAMS)


class SirioNumber(SirioParamEntity, NumberEntity):
    """A numeric parameter, changed by stepping the controller up or down."""

    _attr_mode = NumberMode.BOX

    def __init__(self, entry: SirioConfigEntry, param: NumberParam) -> None:
        super().__init__(entry, param.index)
        self._param = param
        self._attr_name = param.name
        self._attr_device_class = param.device_class

    @property
    def _psi(self) -> bool:
        status = self._data.status.data or {}
        return status.get("barOrPsi", 0) != 0

    @property
    def _scale(self) -> float:
        if self._param.pressure:
            return 1.0 if self._psi else 0.1
        return self._param.scale

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self._param.pressure:
            return UnitOfPressure.PSI if self._psi else UnitOfPressure.BAR
        return self._param.unit

    @property
    def native_min_value(self) -> float:
        return self._param.min_value

    @property
    def native_max_value(self) -> float:
        if self._param.pressure and self._psi:
            return round(self._param.max_value * PSI_FACTOR)
        return self._param.max_value

    @property
    def native_step(self) -> float:
        return self._scale

    def _to_native(self, raw: int) -> float:
        return round((raw + self._param.offset) * self._scale, 1)

    def _describe(self, raw: int) -> str:
        unit = self.native_unit_of_measurement
        value = self._to_native(raw)
        return f"{value} {unit}" if unit else str(value)

    @property
    def native_value(self) -> float | None:
        raw = self._raw
        return None if raw is None else self._to_native(raw)

    async def async_set_native_value(self, value: float) -> None:
        raw = round(value / self._scale) - self._param.offset
        await self._async_write(raw)
