"""Feed health report for the /feederrors admin command (main and liturgy bots)."""

from datetime import datetime

import pytz

from util.datehandler import DateHandler

DEFAULT_STALE_DAYS = 60
MAX_MESSAGE_LENGTH = 3500  # Telegram max is 4096; leave room for overhead

_TZ = pytz.timezone("America/Belem")


def _fmt(date_str: str) -> str:
    return DateHandler.parse_datetime(date_str).astimezone(_TZ).strftime("%d/%m/%Y %H:%M")


def feed_problem(metadata: dict, now: datetime, stale_days: int) -> tuple[int, str] | None:
    """Classify a feed from its url:^...^ metadata.

    Returns (sort_key, description) for a problem feed, or None if healthy.
    Errors (last fetch failed) sort before stale feeds (no new post in
    more than stale_days days).
    """
    error = metadata.get("last_error")
    if error:
        count = metadata.get("error_count", "?")
        since = metadata.get("error_since")
        since_text = f" desde {_fmt(since)}" if since else ""
        return 0, f"🔴 {error}{since_text} ({count} verificações seguidas)"

    if not metadata.get("last_url"):
        return 1, "🟡 nenhum post entregue ainda"

    last_update = metadata.get("last_update")
    if last_update:
        days = (now - DateHandler.parse_datetime(last_update)).days
        if days > stale_days:
            return 2, f"🟡 sem posts novos há {days} dias (último: {_fmt(last_update)})"
    return None


async def build_feed_errors_report(db, stale_days: int = DEFAULT_STALE_DAYS) -> list[str]:
    """Build the /feederrors reply, split into Telegram-sized messages."""
    urls = await db.get_urls_activated()
    if not urls:
        return ["Nenhum feed ativo."]

    now = datetime.now(pytz.utc)
    problems = []
    for url in urls:
        metadata = await db.get_url_metadata(url) or {}
        problem = feed_problem(metadata, now, stale_days)
        if problem:
            groups = len(await db.get_chats_for_url(url))
            problems.append((problem[0], url, problem[1], groups))

    if not problems:
        return [
            f"✅ Nenhum feed com erro ou parado há mais de {stale_days} dias "
            f"({len(urls)} verificados)."
        ]

    problems.sort(key=lambda p: (p[0], p[1]))
    header = (
        f"⚠️ Feeds com problema: {len(problems)} de {len(urls)}\n"
        f"(parado = sem posts novos há mais de {stale_days} dias)\n\n"
    )
    messages, current = [], header
    for _, url, description, groups in problems:
        plural = "grupo" if groups == 1 else "grupos"
        entry = f"{url}\n   {description} · {groups} {plural}\n\n"
        if len(current) + len(entry) > MAX_MESSAGE_LENGTH:
            messages.append(current.strip())
            current = ""
        current += entry
    messages.append(current.strip())
    return messages
