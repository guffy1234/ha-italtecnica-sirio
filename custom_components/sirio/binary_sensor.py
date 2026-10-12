"""Binary sensors for the Sirio pump controller."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SirioConfigEntry, SirioCoordinator
from .entity import SirioEntity


@dataclass(frozen=True, kw_only=True)
class SirioBinarySensorDescription(BinarySensorEntityDescription):
    """Binary sensor description with a value extractor."""

    value_fn: Callable[[dict[str, Any]], bool | None]


def _flag(key: str) -> Callable[[dict[str, Any]], bool | None]:
    def fn(d: dict[str, Any]) -> bool | None:
        value = d.get(key)
        return None if value is None else value == 1

    return fn


BINARY_SENSORS: tuple[SirioBinarySensorDescription, ...] = (
    SirioBinarySensorDescription(
        key="motor_on",
        name="Motor on",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=_flag("motorOn"),
    ),
    SirioBinarySensorDescription(
        key="error",
        name="Error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_flag("flagError"),
    ),
    SirioBinarySensorDescription(
        key="external_error",
        name="External error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_flag("extErr"),
    ),
    SirioBinarySensorDescription(
        key="master",
        name="Master",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_flag("master"),
    ),
    SirioBinarySensorDescription(
        key="external_enable",
        name="External enable",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_flag("extEnabled"),
    ),
    SirioBinarySensorDescription(
        key="double_set_point",
        name="Double set-point",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_flag("doubleSetPoint"),
    ),
    SirioBinarySensorDescription(
        key="pilot_pump",
        name="Pilot pump active",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_flag("pilota"),
    ),
    SirioBinarySensorDescription(
        key="manual_adjustment",
        name="Manual adjustment",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_flag("pumpMan"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SirioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sirio binary sensors."""
    coordinator = entry.runtime_data.status
    async_add_entities(
        SirioBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class SirioBinarySensor(SirioEntity, BinarySensorEntity):
    """A flag read from the Sirio status JSON."""

    entity_description: SirioBinarySensorDescription

    def __init__(
        self, coordinator: SirioCoordinator, description: SirioBinarySensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator.data)
