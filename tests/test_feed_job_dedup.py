"""FeedJob must never resend an entry already delivered (last_update/last_url).

FeedJob is shared by the main bot (DB 0) and the liturgy bot (DB 1), so these
tests cover the dedup logic of both.
"""

from unittest.mock import patch

import pytest

from util.feedhandler import FeedHandler
from worker.feed_job import FeedJob

FEED_URL = "https://example.com/feed"


def make_entries(*days):
    """Feed entries as feedparser returns them: newest first."""
    return [
        {
            "title": f"Post {day}",
            "link": f"https://example.com/{day}",
            "published": f"2026-09-{day:02d} 10:00:00+00:00",
        }
        for day in sorted(days, reverse=True)
    ]


class FakeDB:
    """In-memory stand-in for MainDatabase/LiturgyDatabase feed methods."""

    def __init__(self):
        self.meta = {"last_update": "2000-01-01 00:00:00+00:00", "last_url": ""}

    async def get_urls_activated(self):
        return [FEED_URL]

    async def get_url_metadata(self, url):
        return dict(self.meta)

    async def get_chats_for_url(self, url):
        return [{"chat_id": 1, "chat_name": "Grupo"}]

    async def record_feed_health(self, url, error):
        pass

    async def update_url_metadata(self, url, last_update, last_url, last_urls=None):
        self.meta = {
            "last_update": last_update,
            "last_url": last_url,
            "last_urls": "\n".join(last_urls or [last_url]),
        }
        return True


class FakeParsed:
    def __init__(self, entries):
        self.entries = [dict(e) for e in entries]


@pytest.fixture
def feed():
    """Mutable feed content plus a record of every link sent."""
    state = {"entries": [], "sent": [], "send_ok": True}

    async def fake_send(self, client, chat_id, entry):
        if state["send_ok"]:
            state["sent"].append(entry["link"])
        return state["send_ok"]

    with patch.object(FeedHandler, "_fetch", lambda url: FakeParsed(state["entries"])), \
         patch.object(FeedJob, "_send_entry_to_chat", fake_send):
        yield state


async def run_cycle(job, feed):
    feed["sent"].clear()
    await job.run()
    return list(feed["sent"])


async def test_each_entry_sent_once_across_cycles(feed):
    db = FakeDB()
    job = FeedJob(db, "TOKEN12345678")
    feed["entries"] = make_entries(1, 2, 3, 4)

    assert await run_cycle(job, feed) == ["https://example.com/4"]
    assert db.meta["last_url"] == "https://example.com/4"

    for _ in range(4):
        assert await run_cycle(job, feed) == []


async def test_only_new_entry_sent_when_feed_updates(feed):
    db = FakeDB()
    job = FeedJob(db, "TOKEN12345678")
    feed["entries"] = make_entries(1, 2, 3, 4)
    await run_cycle(job, feed)

    feed["entries"] = make_entries(2, 3, 4, 5)
    assert await run_cycle(job, feed) == ["https://example.com/5"]
    assert await run_cycle(job, feed) == []


async def test_first_sync_sends_only_latest_entry(feed):
    db = FakeDB()
    job = FeedJob(db, "TOKEN12345678")
    feed["entries"] = make_entries(1, 2, 3, 4)

    assert await run_cycle(job, feed) == ["https://example.com/4"]


async def test_after_first_sync_all_new_entries_sent_oldest_first(feed):
    db = FakeDB()
    job = FeedJob(db, "TOKEN12345678")
    feed["entries"] = make_entries(1, 2)
    await run_cycle(job, feed)

    feed["entries"] = make_entries(2, 3, 4, 5)
    assert await run_cycle(job, feed) == [
        "https://example.com/3", "https://example.com/4", "https://example.com/5",
    ]
    assert db.meta["last_url"] == "https://example.com/5"


def same_time(*names, day=10):
    """Entries sharing one timestamp, in feed order (newest first)."""
    return [
        {
            "title": name,
            "link": f"https://example.com/{name}",
            "published": f"2026-09-{day:02d} 10:00:00+00:00",
        }
        for name in names
    ]


async def test_same_date_entries_all_sent_once(feed):
    db = FakeDB()
    job = FeedJob(db, "TOKEN12345678")
    feed["entries"] = make_entries(1)
    await run_cycle(job, feed)

    feed["entries"] = same_time("b", "a")
    assert sorted(await run_cycle(job, feed)) == ["https://example.com/a", "https://example.com/b"]
    for _ in range(3):
        assert await run_cycle(job, feed) == []


async def test_new_entry_with_same_date_as_last_update_is_sent(feed):
    db = FakeDB()
    job = FeedJob(db, "TOKEN12345678")
    feed["entries"] = same_time("a")
    await run_cycle(job, feed)

    feed["entries"] = same_time("b", "a")
    assert await run_cycle(job, feed) == ["https://example.com/b"]
    assert await run_cycle(job, feed) == []


async def test_legacy_metadata_without_last_urls(feed):
    """Records written before last_urls existed fall back to last_url."""
    db = FakeDB()
    db.meta = {"last_update": "2026-09-10 10:00:00+00:00", "last_url": "https://example.com/a"}
    job = FeedJob(db, "TOKEN12345678")

    feed["entries"] = same_time("b", "a")
    assert await run_cycle(job, feed) == ["https://example.com/b"]
    assert await run_cycle(job, feed) == []


async def test_failed_send_keeps_metadata_for_retry(feed):
    db = FakeDB()
    job = FeedJob(db, "TOKEN12345678")
    feed["entries"] = make_entries(1)
    feed["send_ok"] = False

    await run_cycle(job, feed)
    assert db.meta["last_url"] == ""

    feed["send_ok"] = True
    assert await run_cycle(job, feed) == ["https://example.com/1"]
