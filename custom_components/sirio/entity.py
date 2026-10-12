"""Base entities for the Sirio pump controller."""

from __future__ import annotations

from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import SirioError
from .const import CONF_ALLOW_WRITE
from .coordinator import SirioConfigEntry, SirioCoordinator, SirioParamCoordinator


def ensure_changes_allowed(entry: SirioConfigEntry) -> None:
    """Raise unless the user allowed changing the pump in the options."""
    if not entry.options.get(CONF_ALLOW_WRITE, False):
        raise HomeAssistantError(
            "Changing the pump is turned off. Turn on 'Allow changing pump "
            "parameters' in the Sirio integration options first."
        )


class SirioEntity(CoordinatorEntity[SirioCoordinator]):
    """Read-only values from the status data; one device, one coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SirioCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_device_info = coordinator.device_info


class SirioParamEntity(CoordinatorEntity[SirioParamCoordinator]):
    """A controller parameter (settings; EntityCategory.CONFIG)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: SirioConfigEntry, index: int) -> None:
        data = entry.runtime_data
        super().__init__(data.params)
        self._entry = entry
        self._data = data
        self._index = index
        self._attr_unique_id = f"{entry.entry_id}_param_{index}"
        self._attr_device_info = data.status.device_info

    @property
    def _raw(self) -> int | None:
        return (self.coordinator.data or {}).get(self._index)

    def _describe(self, raw: int) -> str:
        """A raw value as the user sees it (overridden per platform)."""
        return str(raw)

    def _store(self, raw: int) -> None:
        self.coordinator.async_set_updated_data(
            {**(self.coordinator.data or {}), self._index: raw}
        )

    async def _async_write(self, raw: int) -> None:
        """Change the parameter to a raw value, if changes are allowed."""
        ensure_changes_allowed(self._entry)
        try:
            new = await self._data.client.set_param(self._index, raw)
        except SirioError as err:
            # A failed change can stop part-way: read back what the controller
            # has now, show it and say so.
            try:
                now = await self._data.client.get_param(self._index)
            except SirioError:
                await self.coordinator.async_request_refresh()
                raise HomeAssistantError(
                    f"Could not change parameter: {err}. The current value could "
                    "not be read back; check the controller."
                ) from err
            self._store(now)
            raise HomeAssistantError(
                f"Could not change parameter: {err}. It is now {self._describe(now)}."
            ) from err
        self._store(new)
