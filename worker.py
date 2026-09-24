"""Worker process: background jobs for feed distribution and daily liturgy."""

import asyncio
import logging
import signal
from decouple import config
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from util.datehandler import DateHandler
from util.database.main_db import MainDatabase
from util.database.liturgy_db import LiturgyDatabase
from util.scrapers.liturgia import LiturgiaScraper
from util.scrapers.homilia import HomiliaScraper
from util.scrapers.santo import SantoScraper
from worker.feed_job import FeedJob
from worker.feed_loop import FEED_PAUSE_SECONDS, run_feed_loop
from worker.liturgy_job import LiturgyJob

logging.basicConfig(
    level=config("LOG", default="INFO"),
    format="%(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def main():
    """Initialize and run the worker scheduler."""
    logger.info("Starting Worker...")

    scheduler = AsyncIOScheduler()
    stop_event = asyncio.Event()

    # Feed jobs (RSS distribution) for main and liturgy bots: continuous
    # loops, not cron, so the pause counts from the end of each cycle.
    main_feed_job = FeedJob(
        MainDatabase(int(config("DB", default="0"))),
        config("DEV_TOKEN")
    )
    liturgy_feed_job = FeedJob(
        LiturgyDatabase(int(config("DB_LD", default="1"))),
        config("DEV_TOKEN_LD")
    )

    # Daily liturgy job at 7 AM in America/Belem timezone
    scrapers = [
        LiturgiaScraper(),
        HomiliaScraper(),
        SantoScraper(),
    ]
    liturgy_job = LiturgyJob(
        LiturgyDatabase(int(config("DB_LD", default="1"))),
        config("DEV_TOKEN_LD"),
        scrapers,
    )
    liturgy_job_lock = asyncio.Lock()

    async def run_liturgy_job() -> None:
        async with liturgy_job_lock:
            await liturgy_job.run()

    scheduler.add_job(
        run_liturgy_job,
        CronTrigger(hour=7, minute=0, timezone=config("TZ", default="America/Belem")),
        id="daily_liturgy",
        name="Daily liturgy delivery",
    )

    scheduler.start()
    feed_loops = [
        asyncio.create_task(run_feed_loop(main_feed_job, stop_event)),
        asyncio.create_task(run_feed_loop(liturgy_feed_job, stop_event)),
    ]
    logger.info(
        f"Worker started: FeedJob main + FeedJob liturgy (loop, {FEED_PAUSE_SECONDS}s "
        "pause between cycles) + LiturgyJob (7am)"
    )

    def _handle_shutdown_signal() -> None:
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_shutdown_signal)

    await stop_event.wait()

    logger.info("Waiting for in-flight jobs to finish before exiting...")
    # AsyncIOScheduler's executor does not honor shutdown(wait=True) — it
    # cancels running jobs outright. Acquiring each job's lock blocks until
    # any in-flight run (and its Redis metadata write) has actually
    # completed before we shut the scheduler down. Feed loops exit on their
    # own after finishing the current cycle.
    await asyncio.gather(*feed_loops)
    async with liturgy_job_lock:
        pass
    scheduler.shutdown(wait=False)
    logger.info("Worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
