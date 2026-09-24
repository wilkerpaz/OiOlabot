import asyncio

from worker.feed_job import FeedJob

# Pause between the end of one feed cycle and the start of the next
FEED_PAUSE_SECONDS = 10


async def run_feed_loop(job: FeedJob, stop_event: asyncio.Event) -> None:
    """Run a FeedJob continuously, pausing FEED_PAUSE_SECONDS after each cycle."""
    while not stop_event.is_set():
        await job.run()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=FEED_PAUSE_SECONDS)
        except asyncio.TimeoutError:
            pass
