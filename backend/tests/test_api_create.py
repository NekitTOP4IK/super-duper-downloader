from app.api import guards
from app.models import Preset
from tests.fakes import single


async def test_probe_returns_media_info(client, queue):
    seen = []

    async def handler(url):
        seen.append(url)
        return {"ok": True, "info": single(url=url).model_dump(mode="json")}

    queue.probe_handler = handler
    response = await client.post("/api/probe", json={"url": "глянь https://example.com/v пж"})
    assert response.status_code == 200
    assert response.json()["title"] == "Video"
    assert seen == ["https://example.com/v"]


async def test_probe_engine_error_is_422(client, queue):
    async def handler(url):
        return {"ok": False, "error": {"code": "PRIVATE", "message": "private video"}}

    queue.probe_handler = handler
    response = await client.post("/api/probe", json={"url": "https://example.com/v"})
    assert response.status_code == 422
    assert response.json()["detail"] == {"code": "PRIVATE", "message": "private video"}


async def test_probe_timeout_is_504(client, queue):
    async def handler(url):
        raise TimeoutError

    queue.probe_handler = handler
    response = await client.post("/api/probe", json={"url": "https://example.com/v"})
    assert response.status_code == 504
    assert response.json()["detail"]["code"] == "PROBE_TIMEOUT"


async def test_probe_busy_is_503(client, queue, settings):
    queue.probe_length = settings.max_probe_queue
    response = await client.post("/api/probe", json={"url": "https://example.com/v"})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "BUSY"


async def test_probe_without_url_is_422(client):
    response = await client.post("/api/probe", json={"url": "просто текст"})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "NO_URLS"


async def test_create_batch_from_text(client, queue, store):
    text = "https://a.example/1\nhttps://a.example/2 https://a.example/1"
    response = await client.post("/api/batches", json={"text": text, "preset": "720"})
    assert response.status_code == 201
    body = response.json()
    assert body["jobs"] == 2
    assert body["truncated"] is False
    batch = await store.get_batch(body["batch_id"])
    assert batch.preset is Preset.P720
    jobs = await store.list_jobs(batch.id)
    assert queue.downloads == [j.id for j in jobs]


async def test_create_batch_merges_urls_and_text(client):
    response = await client.post(
        "/api/batches", json={"urls": ["https://a.example/1"], "text": "https://b.example/2"}
    )
    assert response.json()["jobs"] == 2


async def test_create_batch_truncates_to_limit(client, settings):
    settings.max_batch_urls = 2
    text = " ".join(f"https://a.example/{i}" for i in range(5))
    body = (await client.post("/api/batches", json={"text": text})).json()
    assert body["jobs"] == 2
    assert body["truncated"] is True


async def test_create_batch_without_urls_is_422(client):
    response = await client.post("/api/batches", json={"text": "nothing here"})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "NO_URLS"


async def test_create_batch_busy_queue_is_503(client, queue, settings):
    queue.download_length = settings.max_queue
    response = await client.post("/api/batches", json={"text": "https://a.example/1"})
    assert response.status_code == 503


async def test_create_batch_low_disk_is_503(client, settings, monkeypatch):
    settings.min_free_disk_gb = 5
    monkeypatch.setattr(guards, "free_disk_gb", lambda path: 1.0)
    response = await client.post("/api/batches", json={"text": "https://a.example/1"})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "BUSY"


async def test_upload_txt_creates_batch(client):
    files = {"file": ("links.txt", b"https://a.example/1\nhttps://a.example/2\n", "text/plain")}
    response = await client.post("/api/batches/upload", files=files, data={"preset": "audio"})
    assert response.status_code == 201
    assert response.json()["jobs"] == 2


async def test_upload_too_large_is_413(client):
    files = {"file": ("links.txt", b"x" * 1_000_001, "text/plain")}
    response = await client.post("/api/batches/upload", files=files)
    assert response.status_code == 413
