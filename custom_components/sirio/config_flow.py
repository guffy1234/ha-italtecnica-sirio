"""Config flow for the Sirio pump controller."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .api import SirioError, async_get_status
from .const import (
    CONF_ALLOW_WRITE,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

INTERVAL_VALIDATOR = vol.All(
    vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
)


class SirioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sirio."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> SirioOptionsFlow:
        return SirioOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input[CONF_PORT]

            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            try:
                await async_get_status(self.hass, host, port)
            except SirioError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME) or DEFAULT_NAME,
                    data={CONF_HOST: host, CONF_PORT: port},
                    options={
                        CONF_SCAN_INTERVAL: user_input.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                        # Parameters stay read-only until the user turns this on.
                        CONF_ALLOW_WRITE: False,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOST, default=(user_input or {}).get(CONF_HOST, "")
                ): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): INTERVAL_VALIDATOR,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class SirioOptionsFlow(OptionsFlow):
    """Options: polling interval and whether parameters may be changed."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): INTERVAL_VALIDATOR,
                vol.Required(
                    CONF_ALLOW_WRITE, default=options.get(CONF_ALLOW_WRITE, False)
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
