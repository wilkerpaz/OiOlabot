"""Worker process: background jobs for feed distribution and daily liturgy."""

import asyncio
import logging
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

    # Feed jobs for both bots
    main_feed_job = FeedJob(MainDatabase(int(config("DB", default="0"))), config("DEV_TOKEN"))
    liturgy_feed_job = FeedJob(LiturgyDatabase(int(config("DB_LD", default="1"))), config("DEV_TOKEN_LD"))

    scheduler.add_job(
        main_feed_job.run,
        CronTrigger(minute="*/5"),  # Every 5 minutes
        id="feed_job_main",
        name="Feed distribution (main)",
    )

    scheduler.add_job(
        liturgy_feed_job.run,
        CronTrigger(minute="*/5"),  # Every 5 minutes
        id="feed_job_liturgy",
        name="Feed distribution (liturgy)",
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

    scheduler.add_job(
        liturgy_job.run,
        CronTrigger(hour=7, minute=0, timezone=config("TZ", default="America/Belem")),
        id="daily_liturgy",
        name="Daily liturgy delivery",
    )

    scheduler.start()
    logger.info("Scheduler started with 3 jobs")

    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutdown signal received")
        scheduler.shutdown()
        logger.info("Worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
