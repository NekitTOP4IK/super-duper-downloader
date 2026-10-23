import pytest

from tests.fakes import single

LINKS = ["https://a.example/1", "https://a.example/2"]


@pytest.fixture
def probes(queue):
    async def handler(url):
        return {"ok": True, "info": single(url=url).model_dump(mode="json")}

    queue.probe_handler = handler


async def test_probes_over_the_limit_are_refused(client, settings, probes):
    settings.rate_probes_per_minute = 2
    codes = [
        (await client.post("/api/probe", json={"url": LINKS[0]})).status_code for _ in range(3)
    ]
    assert codes == [200, 200, 429]


async def test_downloads_count_every_link(client, settings):
    settings.rate_downloads_per_hour = 3
    first = await client.post("/api/batches", json={"urls": LINKS})
    second = await client.post("/api/batches", json={"urls": LINKS})
    assert first.status_code == 201
    assert second.status_code == 429
    assert second.json()["detail"]["code"] == "RATE_LIMITED"
    assert 0 < int(second.headers["retry-after"]) <= 3600


async def test_each_address_has_its_own_limit(client, settings):
    settings.rate_downloads_per_hour = 2

    async def send(address):
        body = {"urls": LINKS}
        response = await client.post("/api/batches", json=body, headers={"X-Real-IP": address})
        return response.status_code

    assert [await send("203.0.113.1"), await send("203.0.113.2")] == [201, 201]
    assert await send("203.0.113.1") == 429


async def test_zero_turns_a_limit_off(client, settings, probes):
    settings.rate_probes_per_minute = 0
    for _ in range(5):
        assert (await client.post("/api/probe", json={"url": LINKS[0]})).status_code == 200
