"""Base parameters of the Sirio controller ("Base Parameters" on its web page).

Parameter index = the page's parameter code without the dot (0.0 -> 0, 1.4 -> 14,
2.8 -> 28). Raw register values are scaled as the controller's own page does.

Not exposed: 0.6 pressure unit (follows the status data) and the Advanced
Parameters (4.x / 5.x), which need a login on the controller.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberDeviceClass
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfFrequency,
    UnitOfTime,
)

# Raw codes used by on/off parameters
RAW_ON = 7
RAW_OFF = 8


@dataclass(frozen=True, kw_only=True)
class NumberParam:
    """A numeric parameter: displayed = (raw + offset) * scale."""

    index: int
    name: str
    unit: str | None = None
    device_class: NumberDeviceClass | None = None
    scale: float = 1.0
    offset: int = 0
    min_value: float
    max_value: float
    pressure: bool = False  # scale and unit follow the controller's bar/psi setting


# Ranges follow the Sirio Universal manual where it states them (working pressure
# up to 8 bar, Imax 0.5-16 A (UI allows 30 A for the higher-current Universal XP), nominal frequency 50/60 Hz, correction +-5 Hz,
# autoreset interval up to 240 min, autoreset tests 0-20). They are UI hints only; the controller enforces its own limits and the
# integration stops with an error if a step is refused.
NUMBER_PARAMS: tuple[NumberParam, ...] = (
    NumberParam(
        index=0,
        name="Pmax (set-point)",
        pressure=True,
        device_class=NumberDeviceClass.PRESSURE,
        min_value=0.5,
        max_value=8,
    ),
    NumberParam(
        index=1,
        name="Start delta pressure",
        pressure=True,
        device_class=NumberDeviceClass.PRESSURE,
        min_value=0.3,
        max_value=8,
    ),
    NumberParam(
        index=2,
        name="Dry-running pressure",
        pressure=True,
        device_class=NumberDeviceClass.PRESSURE,
        min_value=0,
        max_value=8,
    ),
    NumberParam(
        index=3,
        name="Pressure limit",
        pressure=True,
        device_class=NumberDeviceClass.PRESSURE,
        min_value=0,
        max_value=10,
    ),
    NumberParam(
        index=4,
        name="Pmax 2 (set-point 2)",
        pressure=True,
        device_class=NumberDeviceClass.PRESSURE,
        min_value=0.5,
        max_value=8,
    ),
    NumberParam(
        index=5,
        name="Stop delta pressure",
        pressure=True,
        device_class=NumberDeviceClass.PRESSURE,
        min_value=0,
        max_value=8,
    ),
    NumberParam(
        index=10,
        name="Imax (max motor current)",
        unit=UnitOfElectricCurrent.AMPERE,
        device_class=NumberDeviceClass.CURRENT,
        scale=0.1,
        min_value=0.5,
        max_value=30,  # Universal: 16 A; the XP goes higher. The controller enforces its own.
    ),
    NumberParam(
        index=12,
        name="Minimum frequency",
        unit=UnitOfFrequency.HERTZ,
        device_class=NumberDeviceClass.FREQUENCY,
        min_value=10,
        max_value=60,
    ),
    NumberParam(
        index=13,
        name="Stop frequency",
        unit=UnitOfFrequency.HERTZ,
        device_class=NumberDeviceClass.FREQUENCY,
        min_value=10,
        max_value=60,
    ),
    NumberParam(
        index=14,
        name="Nominal motor frequency",
        unit=UnitOfFrequency.HERTZ,
        device_class=NumberDeviceClass.FREQUENCY,
        min_value=50,
        max_value=60,
    ),
    NumberParam(
        index=16,
        name="Frequency correction",
        unit=UnitOfFrequency.HERTZ,
        device_class=NumberDeviceClass.FREQUENCY,
        offset=-10,  # page shows raw - 10
        min_value=-5,
        max_value=5,
    ),
    NumberParam(
        index=25,
        name="Delay on stop",
        unit=UnitOfTime.SECONDS,
        device_class=NumberDeviceClass.DURATION,
        scale=0.1,
        min_value=0,
        max_value=60,
    ),
    NumberParam(
        index=26,
        name="Autoreset interval",
        unit=UnitOfTime.MINUTES,
        device_class=NumberDeviceClass.DURATION,
        min_value=1,
        max_value=240,
    ),
    NumberParam(
        index=27,
        name="Autoreset tests",
        min_value=0,
        max_value=20,
    ),
)

# index -> (name, {raw value: label})
SELECT_PARAMS: tuple[tuple[int, str, dict[int, str]], ...] = (
    (11, "Rotation direction (3-phase only)", {21: "-->", 22: "<--"}),
    (15, "Switching frequency", {3: "3 kHz", 5: "5 kHz", 10: "10 kHz"}),
    (21, "Command source", {18: "MAN", 19: "0-10V", 20: "PRESS"}),
    (22, "Auxiliary contact function", {23: "1 <-> standalone / twin pump", 24: "2 <- remote start/stop", 25: "3 x2 second set-point (Pmax2)"}),
    (
        23,
        "I/O board input function",
        {24: "2 <- remote start/stop", 25: "3 x2 second set-point (Pmax2)", 26: "ERR external error", 27: "OFF"},
    ),
    (
        24,
        "I/O board output function",
        {3: "OFF", 4: "ERR", 5: "P.ON", 6: "AUX"},
    ),
)

# index -> name (raw 7 = ON, 8 = OFF)
SWITCH_PARAMS: tuple[tuple[int, str], ...] = (
    (17, "Soft-start"),
    (20, "Flow switch"),
    (28, "Total automatic reset"),
)

PARAM_INDEXES: tuple[int, ...] = tuple(
    sorted(
        {p.index for p in NUMBER_PARAMS}
        | {i for i, _, _ in SELECT_PARAMS}
        | {i for i, _ in SWITCH_PARAMS}
    )
)
