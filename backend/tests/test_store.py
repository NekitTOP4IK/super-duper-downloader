from app.models import Job, JobStatus, MediaInfo, MediaKind, Preset
from app.store.redis_store import events_channel

URLS = ["https://a.example/1", "https://a.example/2"]


async def next_message(pubsub):
    for _ in range(20):
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
        if message is not None:
            return message
    raise AssertionError("no pub/sub message received")


async def test_create_batch_persists_batch_and_jobs(store):
    batch, jobs = await store.create_batch(Preset.P720, URLS)
    assert await store.get_batch(batch.id) == batch
    assert len(batch.id) >= 20
    listed = await store.list_jobs(batch.id)
    assert [j.url for j in listed] == URLS
    assert [j.id for j in listed] == [j.id for j in jobs]
    assert all(j.status is JobStatus.QUEUED and j.expires_at == batch.expires_at for j in listed)


async def test_keys_expire_with_batch(store, redis, settings):
    batch, jobs = await store.create_batch(Preset.BEST, URLS[:1])
    for key in (f"batch:{batch.id}", f"batch:{batch.id}:jobs", f"job:{jobs[0].id}"):
        assert 0 < await redis.ttl(key) <= settings.file_ttl_sec


async def test_save_job_updates_and_publishes(store, redis):
    batch, [job] = await store.create_batch(Preset.BEST, URLS[:1])
    pubsub = redis.pubsub()
    await pubsub.subscribe(events_channel(batch.id))
    job.status = JobStatus.DONE
    await store.save_job(job)
    assert (await store.get_job(job.id)).status is JobStatus.DONE
    message = await next_message(pubsub)
    assert Job.model_validate_json(message["data"]).status is JobStatus.DONE
    await pubsub.aclose()


async def test_add_jobs_appends_children(store):
    batch, [parent] = await store.create_batch(Preset.BEST, URLS[:1])
    children = await store.add_jobs(batch, ["https://c.example/1"], parent_id=parent.id)
    listed = await store.list_jobs(batch.id)
    assert [j.id for j in listed] == [parent.id, children[0].id]
    assert listed[1].parent_id == parent.id


async def test_missing_entities(store):
    assert await store.get_batch("nope") is None
    assert await store.get_job("nope") is None
    assert await store.list_jobs("nope") == []
    assert await store.batch_exists("nope") is False


async def test_probe_cache_roundtrip(store):
    info = MediaInfo(kind=MediaKind.SINGLE, url="https://v.example/1", title="T")
    assert await store.get_probe(info.url) is None
    await store.set_probe(info.url, info, 60)
    assert await store.get_probe(info.url) == info
