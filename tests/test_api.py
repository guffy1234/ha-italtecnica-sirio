import asyncio, importlib, sys, types
from pathlib import Path
SIRIO = str(Path(__file__).resolve().parent.parent / "custom_components" / "sirio")

# Stubs so api.py can be imported without Home Assistant installed
for name in ("homeassistant", "homeassistant.core", "homeassistant.helpers", "homeassistant.helpers.aiohttp_client"):
    sys.modules[name] = types.ModuleType(name)
sys.modules["homeassistant.core"].HomeAssistant = object
sys.modules["homeassistant.helpers.aiohttp_client"].async_get_clientsession = lambda hass: None
aio = types.ModuleType("aiohttp")
class _ClientError(Exception): pass
aio.ClientError = _ClientError
sys.modules["aiohttp"] = aio
pkg = types.ModuleType("pkg"); pkg.__path__ = [SIRIO]; sys.modules["pkg"] = pkg
api = importlib.import_module("pkg.api")


class FakeController:
    """Mimics get-registers key=002 / set-registers key=007|008 for one parameter."""
    def __init__(self, codes, value, wrap=False):
        self.codes, self.value, self.wrap, self.calls = codes, value, wrap, []
    async def post(self, path, data):
        self.calls.append((path, dict(data)))
        idx = int(data["index"])
        if data["key"] == "002":
            return {"key": 2, "result": True, "parIndex": idx, "value": self.value}
        i = self.codes.index(self.value)
        i = i + 1 if data["key"] == "007" else i - 1
        if self.wrap:
            i %= len(self.codes)
        i = max(0, min(len(self.codes) - 1, i))
        self.value = self.codes[i]
        return {"key": int(data["key"]), "result": True, "parIndex": idx, "value": self.value}


def make(fake):
    c = api.SirioClient(None, "h", 1)
    c._post = fake.post
    return c

async def main():
    # 1. numeric parameter, step 1, reach target going up and down
    f = FakeController(list(range(0, 101)), 21); c = make(f)
    assert await c.set_param(0, 25) == 25 and f.value == 25
    assert await c.set_param(0, 20) == 20 and f.value == 20
    assert await c.set_param(0, 20) == 20          # already there: no write calls
    n_writes = sum(1 for _, d in f.calls if d["key"] in ("007", "008"))
    assert n_writes == 9, n_writes                  # 4 up + 5 down

    # 2. limit reached -> error, stops at the limit
    f = FakeController(list(range(0, 31)), 28); c = make(f)
    try:
        await c.set_param(0, 40); raise SystemExit("expected SirioError")
    except api.SirioError as e:
        assert f.value == 30, f.value

    # 3. enum codes (e.g. I/O input function 24..27), down by decrement
    f = FakeController([24, 25, 26, 27], 27); c = make(f)
    assert await c.set_param(23, 24) == 24

    # 4. controller wraps around -> detected as wrong way
    f = FakeController([24, 25, 26, 27], 27, wrap=True); c = make(f)
    try:
        await c.set_param(23, 28); raise SystemExit("expected SirioError")
    except api.SirioError:
        pass

    # 5. target that is not a valid code (step lands past it) -> overshoot error
    f = FakeController([3, 5, 10], 5); c = make(f)
    try:
        await c.set_param(15, 7); raise SystemExit("expected SirioError")
    except api.SirioError as e:
        assert "past" in str(e), e
    # 6. valid code that is 2 'steps' away works (3,5,10 are consecutive codes)
    f = FakeController([3, 5, 10], 3); c = make(f)
    assert await c.set_param(15, 10) == 10

    # 7. get_params leaves out failed reads
    f = FakeController(list(range(0, 101)), 21); c = make(f)
    async def flaky(path, data):
        if data["index"] == "6":
            raise api.SirioError("no answer")
        return await f.post(path, data)
    c._post = flaky
    assert await c.get_params([0, 6]) == {0: 21}

    # 8. get_params waits for a running change, so it never reads a half-way value
    f = FakeController(list(range(0, 101)), 21); c = make(f)
    async def slow(path, data):
        await asyncio.sleep(0)
        return await f.post(path, data)
    c._post = slow
    write = asyncio.create_task(c.set_param(0, 30))
    await asyncio.sleep(0)
    assert await c.get_params([0]) == {0: 30}
    await write
    print("all stepping tests passed")

asyncio.run(main())
