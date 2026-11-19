import asyncio
import importlib.util
from pathlib import Path

path = Path(__file__).parents[1] / "scripts" / "measure_pool.py"
spec = importlib.util.spec_from_file_location("measure_pool", path)
if spec is None or spec.loader is None:
    raise ImportError(f"Unable to load script at {path}")
measure_pool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure_pool)
REQUEST_COUNT = measure_pool.REQUEST_COUNT
send_requests = measure_pool.send_requests


class FakeResponse:
    def raise_for_status(self):
        return None


class FakeClient:
    def __init__(self):
        self.requests = []

    async def get(self, path, *, params=None):
        self.requests.append((path, params or {}))
        return FakeResponse()


def test_pool_measurement_sends_50_read_only_requests():
    client = FakeClient()

    completed = asyncio.run(send_requests(client))

    assert completed == REQUEST_COUNT == 50
    assert client.requests == [("/ready", {})] * 50
