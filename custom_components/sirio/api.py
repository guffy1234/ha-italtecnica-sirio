"""Client for the Sirio controller's web API.

Endpoints used (the same ones the controller's own web page calls):
  POST /ajax/get-registers  key=001            runtime status (JSON)
  POST /ajax/get-registers  key=002 index=N    read base parameter N
  POST /ajax/set-registers  key=007 index=N    parameter N one step up
  POST /ajax/set-registers  key=008 index=N    parameter N one step down

The controller has no "set to value" call: parameters are changed one step at
a time, and every step returns the new value.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import REQUEST_TIMEOUT

GET_URL = "/ajax/get-registers"
SET_URL = "/ajax/set-registers"

MAX_STEPS = 60  # safety cap for one parameter change
RETRY_DELAY = 0.5  # seconds before a failed parameter read is tried again

_LOGGER = logging.getLogger(__name__)


class SirioError(Exception):
    """Raised when the controller cannot be reached or answers unexpectedly."""


class SirioClient:
    """Talks to one controller, one request at a time."""

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        self._session = async_get_clientsession(hass)
        self._base = f"http://{host}:{port}"
        # The controller is a tiny embedded web server: never overlap requests.
        self._lock = asyncio.Lock()
        # Only one parameter change at a time.
        self._write_lock = asyncio.Lock()

    async def _post(self, path: str, data: dict[str, str]) -> dict[str, Any]:
        url = f"{self._base}{path}"
        async with self._lock:
            try:
                async with asyncio.timeout(REQUEST_TIMEOUT):
                    # "Connection: close" avoids stale keep-alive sockets.
                    async with self._session.post(
                        url, data=data, headers={"Connection": "close"}
                    ) as resp:
                        resp.raise_for_status()
                        payload = await resp.json(content_type=None)
            except (TimeoutError, aiohttp.ClientError, ValueError) as err:
                raise SirioError(f"Error communicating with {url}: {err}") from err
        if not isinstance(payload, dict):
            raise SirioError(f"Unexpected response from {url}")
        return payload

    async def get_status(self) -> dict[str, Any]:
        """Read the runtime status."""
        payload = await self._post(GET_URL, {"key": "001"})
        if payload.get("key") != 1:
            raise SirioError("Unexpected status response")
        return payload

    async def get_param(self, index: int) -> int:
        """Read one base parameter (raw register value)."""
        payload = await self._post(GET_URL, {"key": "002", "index": str(index)})
        if (
            not payload.get("result")
            or payload.get("parIndex") != index
            or "value" not in payload
        ):
            raise SirioError(f"Could not read parameter {index}")
        return int(payload["value"])

    async def get_params(self, indexes: Iterable[int]) -> dict[int, int]:
        """Read several base parameters; failed reads are left out.

        Holds the write lock so a read never sees a change half-way through.
        """
        values: dict[int, int] = {}
        async with self._write_lock:
            for index in indexes:
                # The controller is easily busy (e.g. its own page open in a
                # browser polls it 5 times a second): try each read twice.
                for attempt in range(2):
                    try:
                        values[index] = await self.get_param(index)
                        break
                    except SirioError as err:
                        _LOGGER.debug(
                            "Could not read parameter %s (try %s): %s",
                            index, attempt + 1, err,
                        )
                        if attempt == 0:
                            await asyncio.sleep(RETRY_DELAY)
        return values

    async def _step_param(self, index: int, increment: bool) -> int:
        payload = await self._post(
            SET_URL, {"key": "007" if increment else "008", "index": str(index)}
        )
        if (
            not payload.get("result")
            or payload.get("parIndex") != index
            or "value" not in payload
        ):
            raise SirioError(f"Controller rejected a step on parameter {index}")
        return int(payload["value"])

    async def set_param(self, index: int, target: int) -> int:
        """Move a parameter to the raw target value by stepping; return the result.

        Stops with an error if the controller stops changing the value (limit
        reached), moves the wrong way, or passes the target.
        """
        async with self._write_lock:
            current = await self.get_param(index)
            if current == target:
                return current
            increment = target > current
            for _ in range(MAX_STEPS):
                new = await self._step_param(index, increment)
                if new == target:
                    return new
                if new == current:
                    raise SirioError(
                        f"Parameter {index} stopped at {new} (limit reached?)"
                    )
                if (new > current) != increment:
                    raise SirioError(
                        f"Parameter {index} moved the wrong way ({current} -> {new})"
                    )
                if (increment and new > target) or (not increment and new < target):
                    raise SirioError(
                        f"Parameter {index} stepped past {target} (now {new})"
                    )
                current = new
            raise SirioError(f"Parameter {index}: too many steps towards {target}")


async def async_get_status(hass: HomeAssistant, host: str, port: int) -> dict[str, Any]:
    """Read the status once (used to validate the config flow)."""
    return await SirioClient(hass, host, port).get_status()
