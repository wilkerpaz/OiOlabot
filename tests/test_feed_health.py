"""/feederrors: feed health recording and report."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytz

from mixins.admin_liturgy import AdminLiturgyMixin
from mixins.admin_main import AdminMainMixin
from util.feed_health import build_feed_errors_report, feed_problem
from util.feedhandler import FeedHandler
from worker.feed_job import FeedJob

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=pytz.utc)


def ago(days):
    return str(NOW - timedelta(days=days))


def healthy(days=1):
    return {"last_update": ago(days), "last_url": "https://x/post", "last_ok": ago(0)}


# --- feed_problem -----------------------------------------------------------

def test_healthy_feed_is_not_a_problem():
    assert feed_problem(healthy(days=10), NOW, 60) is None


def test_fetch_error_reported_with_streak():
    meta = {**healthy(), "last_error": "timeout", "error_since": ago(2), "error_count": "57"}
    kind, text = feed_problem(meta, NOW, 60)
    assert kind == 0
    assert "timeout" in text and "57 verificações" in text


def test_stale_feed_uses_threshold():
    assert feed_problem(healthy(days=59), NOW, 60) is None
    kind, text = feed_problem(healthy(days=61), NOW, 60)
    assert kind == 2 and "61 dias" in text
    assert feed_problem(healthy(days=31), NOW, 30) is not None


def test_never_delivered_feed():
    meta = {"last_update": "2000-01-01 00:00:00+00:00", "last_url": ""}
    kind, text = feed_problem(meta, NOW, 60)
    assert kind == 1 and "nenhum post" in text


# --- build_feed_errors_report -----------------------------------------------

class FakeDB:
    def __init__(self, feeds):
        self.feeds = feeds  # url -> metadata

    async def get_urls_activated(self):
        return sorted(self.feeds)

    async def get_url_metadata(self, url):
        return self.feeds[url]

    async def get_chats_for_url(self, url):
        return [{"chat_id": 1}]


async def test_report_lists_errors_before_stale():
    db = FakeDB({
        "https://a/ok": healthy(),
        "https://b/stale": healthy(days=100),
        "https://c/broken": {**healthy(), "last_error": "HTTP 404", "error_count": "3"},
    })
    [text] = await build_feed_errors_report(db, 60)
    assert "2 de 3" in text
    assert "https://a/ok" not in text
    assert text.index("https://c/broken") < text.index("https://b/stale")
    assert "1 grupo" in text


async def test_report_all_healthy():
    db = FakeDB({"https://a/ok": healthy()})
    assert await build_feed_errors_report(db, 60) == [
        "✅ Nenhum feed com erro ou parado há mais de 60 dias (1 verificados)."
    ]


async def test_report_splits_long_output():
    db = FakeDB({f"https://site{i}.example.com/feed/{'x' * 80}": healthy(days=100) for i in range(60)})
    messages = await build_feed_errors_report(db, 60)
    assert len(messages) > 1
    assert all(len(m) <= 4096 for m in messages)
    assert sum(m.count("https://site") for m in messages) == 60


# --- /feederrors handler ----------------------------------------------------

def make_message(*args):
    return SimpleNamespace(
        command=["feederrors", *args],
        from_user=SimpleNamespace(id=42),
        reply=AsyncMock(),
    )


@pytest.mark.parametrize("mixin", [AdminMainMixin, AdminLiturgyMixin])
@pytest.mark.parametrize("args, expected_days", [((), 60), (("30",), 30)])
async def test_handler_days_argument(mixin, args, expected_days):
    bot = SimpleNamespace(db=object(), _check_admin=AsyncMock(return_value=True))
    message = make_message(*args)
    with patch(f"{mixin.__module__}.build_feed_errors_report", AsyncMock(return_value=["ok"])) as report:
        await mixin._on_feederrors(bot, None, message)
    report.assert_awaited_once_with(bot.db, expected_days)
    message.reply.assert_awaited_once_with("ok")


@pytest.mark.parametrize("bad", ["abc", "0", "-5"])
async def test_handler_rejects_invalid_days(bad):
    bot = SimpleNamespace(db=object(), _check_admin=AsyncMock(return_value=True))
    message = make_message(bad)
    with patch("mixins.admin_main.build_feed_errors_report", AsyncMock()) as report:
        await AdminMainMixin._on_feederrors(bot, None, message)
    report.assert_not_awaited()
    assert "Uso: /feederrors [dias]" in message.reply.await_args.args[0]


async def test_handler_requires_admin():
    bot = SimpleNamespace(db=object(), _check_admin=AsyncMock(return_value=False))
    message = make_message()
    with patch("mixins.admin_main.build_feed_errors_report", AsyncMock()) as report:
        await AdminMainMixin._on_feederrors(bot, None, message)
    report.assert_not_awaited()
    message.reply.assert_awaited_once_with("❌ Você não é administrador.")


# --- FeedJob records health -------------------------------------------------

@pytest.mark.parametrize("fetch_result", [([], "timeout"), ([], "vazio"), ([{"link": "x"}], None)])
async def test_feed_job_records_fetch_result(fetch_result):
    db = SimpleNamespace(
        get_url_metadata=AsyncMock(return_value=healthy()),
        record_feed_health=AsyncMock(),
        get_chats_for_url=AsyncMock(return_value=[]),
    )
    job = FeedJob(db, "TOKEN12345678")
    with patch.object(FeedHandler, "parse_feed_with_status", AsyncMock(return_value=fetch_result)):
        await job._process_url(None, "https://a/feed")
    db.record_feed_health.assert_awaited_once_with("https://a/feed", fetch_result[1])
