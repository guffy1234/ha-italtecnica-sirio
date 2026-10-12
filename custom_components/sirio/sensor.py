"""Sensors for the Sirio pump controller."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import ERRORS
from .coordinator import SirioConfigEntry, SirioCoordinator
from .entity import SirioEntity


@dataclass(frozen=True, kw_only=True)
class SirioSensorDescription(SensorEntityDescription):
    """Sensor description with a value extractor."""

    value_fn: Callable[[dict[str, Any]], StateType]
    unit_fn: Callable[[dict[str, Any]], str | None] | None = None


def _raw(key: str) -> Callable[[dict[str, Any]], StateType]:
    return lambda d: d.get(key)


def _tenths(key: str) -> Callable[[dict[str, Any]], StateType]:
    """Controller reports pressure/current in tenths."""

    def fn(d: dict[str, Any]) -> StateType:
        value = d.get(key)
        return None if value is None else round(value / 10, 1)

    return fn


def _pressure_unit(d: dict[str, Any]) -> str:
    return UnitOfPressure.BAR if d.get("barOrPsi", 0) == 0 else UnitOfPressure.PSI


ERROR_NONE = "none"
ERROR_UNKNOWN = "unknown"


def _active_error(d: dict[str, Any]) -> StateType:
    # Same rule as the controller's page: an error shows only while both are set.
    if d.get("flagError") != 1 or not d.get("errorActive"):
        return ERROR_NONE
    return ERRORS.get(d.get("errorNumber"), ERROR_UNKNOWN)


SENSORS: tuple[SirioSensorDescription, ...] = (
    SirioSensorDescription(
        key="pressure",
        name="Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_tenths("press"),
        unit_fn=_pressure_unit,
    ),
    SirioSensorDescription(
        key="frequency",
        name="Frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        value_fn=_raw("freq"),
    ),
    SirioSensorDescription(
        key="current",
        name="Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=_tenths("amp"),
    ),
    SirioSensorDescription(
        key="voltage",
        name="Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=_raw("volt"),
    ),
    SirioSensorDescription(
        key="board_temperature",
        name="Board temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=_raw("temp"),
    ),
    SirioSensorDescription(
        key="igbt_temperature",
        name="IGBT temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=_raw("tempIgbt"),
    ),
    SirioSensorDescription(
        key="power_on_hours",
        name="Power-on hours",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_raw("hPowerOn"),
    ),
    SirioSensorDescription(
        key="running_hours",
        name="Running hours",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_raw("hPowerRunning"),
    ),
    SirioSensorDescription(
        key="pump_starts",
        name="Pump starts",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_raw("nrStarts"),
    ),
    SirioSensorDescription(
        key="active_error",
        name="Active error",
        device_class=SensorDeviceClass.ENUM,
        options=[ERROR_NONE, *ERRORS.values(), ERROR_UNKNOWN],
        value_fn=_active_error,
    ),
)

# Lifetime counters per error code; disabled by default to avoid clutter.
ERROR_COUNTERS: tuple[SirioSensorDescription, ...] = tuple(
    SirioSensorDescription(
        key=f"e{number}",
        name=f"{label} count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_raw(f"e{number}"),
    )
    for number, label in ERRORS.items()
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SirioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sirio sensors."""
    coordinator = entry.runtime_data.status
    async_add_entities(
        SirioSensor(coordinator, description)
        for description in (*SENSORS, *ERROR_COUNTERS)
    )


class SirioSensor(SirioEntity, SensorEntity):
    """A value read from the Sirio status JSON."""

    entity_description: SirioSensorDescription

    def __init__(
        self, coordinator: SirioCoordinator, description: SirioSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.entity_description.unit_fn is not None:
            return self.entity_description.unit_fn(self.coordinator.data)
        return self.entity_description.native_unit_of_measurement
