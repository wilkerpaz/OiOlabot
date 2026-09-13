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

    # Feed job for main bot (RSS distribution)
    main_feed_job = FeedJob(
        MainDatabase(int(config("DB", default="0"))),
        config("DEV_TOKEN")
    )
    feed_job_lock = asyncio.Lock()

    async def run_feed_job() -> None:
        async with feed_job_lock:
            await main_feed_job.run()

    scheduler.add_job(
        run_feed_job,
        CronTrigger(minute="*/5"),  # Every 5 minutes
        id="feed_job_main",
        name="Feed distribution (main)",
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
    logger.info("Scheduler started with 2 jobs: FeedJob (5min) + LiturgyJob (7am)")

    stop_event = asyncio.Event()

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
    # completed before we shut the scheduler down.
    async with feed_job_lock:
        pass
    async with liturgy_job_lock:
        pass
    scheduler.shutdown(wait=False)
    logger.info("Worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
