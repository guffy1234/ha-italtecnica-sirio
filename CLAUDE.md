# CLAUDE.md

Project notes for Claude sessions working on this repository.

## What this is

A Home Assistant custom integration (`custom_components/sirio`, domain `sirio`) for
Italtecnica **Sirio** pump controllers with the Wi-Fi web interface. It polls the
controller's own web API locally and exposes one device with sensors, binary sensors and the
controller's Base Parameters (number / select / switch). See `README.md` for the user-facing
description.

## Environment

* Controller web page: `http://192.168.20.112:8080/management.html` (user's LAN).
* Home Assistant config share: `\\192.168.20.101\config` (SMB). Deploy by copying
  `custom_components/sirio` into `config\custom_components\`, then restart Home Assistant.
  The Claude file bridge refuses UNC paths, so the user copies files themselves (or maps the
  share to a drive letter and tells Claude which one).
* Target Home Assistant 2025.2+ (`AddConfigEntryEntitiesCallback`; Python 3.12+ syntax such as `type X = ...`,
  `ConfigEntry.runtime_data`, `OptionsFlow` without `__init__`).
* Home Assistant is not installed in the sandbox: `tests/test_api.py` stubs it.
* Brand images (`brand/`) are only honoured by Home Assistant 2026.3+.

## Layout

```
custom_components/sirio/
  __init__.py       setup/unload; builds SirioClient + two coordinators -> entry.runtime_data
  api.py            SirioClient: all HTTP, request lock, stepped parameter writes
  coordinator.py    SirioCoordinator (status, user interval), SirioParamCoordinator (5 min), SirioData
  entity.py         SirioEntity (status values) and SirioParamEntity (settings + guarded writes)
  parameters.py     table of Base Parameters: scaling, ranges, choice maps
  sensor.py / binary_sensor.py / number.py / select.py / switch.py
  config_flow.py    host/port/name/interval; options: interval + allow_parameter_changes
  const.py, manifest.json, translations/en.json, brand/*.png
tools/make_brand.py  builds brand/ images from tools/source/italtecnica-logo.png
tests/test_api.py    simulated-controller tests for SirioClient.set_param
```

## Controller API (read from the controller's own `management.js`)

All requests: `POST`, `application/x-www-form-urlencoded`.

| Request | Meaning |
|---------|---------|
| `/ajax/get-registers` `key=001` | runtime status JSON, no login needed |
| `/ajax/get-registers` `key=002&index=N` | read base parameter N -> `{key,result,parIndex,value}` |
| `/ajax/get-registers` `key=003&index=N` | read advanced parameter N (needs login) |
| `/ajax/set-registers` `key=007\|008&index=N` | base parameter N one step up / down |
| `/ajax/set-registers` `key=009\|010&index=N` | advanced parameter N up / down (needs login) |
| `/ajax/set-registers` `key=011` | status icon click on the page: toggles stand-by/run (inferred) |
| `/ajax/login` | session check; login page is `/user.html` |

Parameter index = page code without the dot (0.0 -> 0, 1.4 -> 14, 2.8 -> 28; advanced 4.0 -> 40 ... 5.9 -> 59).

### Status JSON (`key=001`) fields

`press`, `setPointPress`, `amp`, `ampMax` are in tenths (bar/A) and `barOrPsi` 0 = bar.
`temp` (board) and `tempIgbt` are in degrees C, `volt` in V, `freq`/`freqMax` in Hz.
`standBy`, `flagError`, `master`, `doubleSetPoint`, `extEnabled`, `extErr`, `motorOn`,
`pilota`, `pumpMan` are 0/1 flags. `errorActive` (bool) + `errorNumber` give the current
error; `e0`..`e13` are lifetime counters per error code. `hPowerOn`, `hPowerRunning`
(hours), `nrStarts`. `noException`, `backLightState` are unused.
Verified on the live device: `setPointPress` = param 0 (Pmax), `ampMax` = param 10 (Imax),
`freqMax` = param 14 (nominal motor frequency), which is why those are parameters, not sensors.

### Raw parameter values (as the page decodes them)

* 0-5 pressures: raw/10 bar (raw psi if `barOrPsi` != 0). 6 unit: 9 = BAR, 10 = PSI (not exposed).
* 10 Imax: raw/10 A. 12/13/14 Hz. 15 switching: raw = kHz. 16 correction: raw - 10 Hz.
* 17, 20, 28 on/off: 7 = ON, 8 = OFF.
* 11 rotation: 21 = `-->`, 22 = `<--`. 21 command: 18 MAN, 19 0-10V, 20 PRESS.
* 22 aux contact: 23 `1<->`, 24 `2<-`, 25 `3 X2`. 23 input fn: 24 `2<-`, 25 `3 X2`, 26 ERR, 27 OFF.
* 24 output fn: 3 OFF, 4 ERR, 5 P.ON, 6 AUX. 25 delay on stop: raw/10 s. 26 interval: min. 27 tests: count.
* Advanced (not implemented): 40 Vboost %, 41 dry-run delay s, 42 starts/hour (11 = OFF, 12..17 -> 10..60), 43 anti-block 7/8,
  44 dead time x125 ns, 45 Ki, 46 Kp, 47 boost time x10 ms, 48 relay NO(1)/NC(2), 50/51 Ta/Tm max C, 52/53 reduction idx,
  54 min flow l/min, 55 ramp Hz/s, 56/57 min/max mains V = ((raw+255)*8/14)-4.

Manual: "Uni-Fitt Sirio Universal" technical passport (Russian, not in the repo). Limits taken from it:
working pressure up to 8 bar, Imax 0.5-16 A (0.5 A = "not set yet"), nominal frequency 50/60 Hz,
switching 3/5/10 kHz, correction +-5 Hz, autoreset interval up to 240 min, tests 0-20,
minimum Pmax-Pmin 0.3 bar. MAN command source disables dry-running and pressure protection.

## Design decisions

* **One request at a time.** The controller is a tiny embedded server and one read of
  param 6 failed once during probing. `SirioClient._post` holds a lock and sends
  `Connection: close`.
* **Two coordinators.** Status every `scan_interval` (default 10 s, allowed 1-300). Parameters
  every 5 min and immediately after a write; a single failed parameter read keeps the old value.
  `SirioClient.get_params` holds the write lock, so a parameter poll never reads (and stores)
  a value from the middle of a stepped write.
* **Writes are stepped and verified** (`SirioClient.set_param`): read, then `007`/`008` until
  the target; abort on no change (limit), wrong direction (wrap), overshoot, or 60 steps.
  A failed write can stop part-way: the entity reads the value back and puts it in the error.
* Repo: https://github.com/guffy1234/ha-italtecnica-sirio (public). `docs/` (manufacturer
  PDFs) is git-ignored on purpose: copyrighted, keep it local.
* **Writes are opt-in.** Option `allow_parameter_changes` defaults to False; while off,
  parameter entities raise `HomeAssistantError` on any change.
* Entity unique ids use the config entry id, so an IP change would not rename entities
  (but there is no reconfigure flow yet).
* Entity UI ranges in `parameters.py` are hints; the controller enforces its own limits.

## Safety rules for Claude

* Reading the live controller is fine (`key=001`, `key=002`).
* **Never** send `set-registers` (`007`-`011`) to the real controller without the user's explicit
  go-ahead for that specific change: it changes a running pump's configuration.
* Never touch the login/advanced endpoints or enter credentials.
* The built-in browser asks for approval per page load on the private address; read the live
  device by running `fetch()` from a tab on the controller's own origin.

## Status and open points

* Writes have **not** been tested against the real controller (only against the simulator in
  `tests/test_api.py`). The `set-registers` response shape (`result`, `parIndex`, `value`) is inferred
  from the page's JavaScript. A first live test should be a harmless parameter such as
  "Autoreset interval" (+1, then -1), with the user's approval.
* Unknown: whether the controller wraps around at the ends or skips unused codes; the stepper
  aborts on anything unexpected.
* Ideas: reconfigure flow for host/port, stand-by/run switch (key 011), advanced parameters
  with a login, Ukrainian/other translations, HACS release.
