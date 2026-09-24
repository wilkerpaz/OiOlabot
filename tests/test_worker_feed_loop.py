"""Feed loop: FEED_PAUSE_SECONDS counts from the end of each cycle."""

import asyncio
import time
from unittest.mock import patch

from worker import feed_loop


class SlowJob:
    """FeedJob stand-in that records when each cycle starts and ends."""

    def __init__(self, duration):
        self.duration = duration
        self.cycles = []

    async def run(self):
        start = time.monotonic()
        await asyncio.sleep(self.duration)
        self.cycles.append((start, time.monotonic()))


async def test_pause_starts_after_cycle_ends():
    job = SlowJob(duration=0.1)
    stop = asyncio.Event()

    with patch.object(feed_loop, "FEED_PAUSE_SECONDS", 0.05):
        task = asyncio.create_task(feed_loop.run_feed_loop(job, stop))
        await asyncio.sleep(0.5)
        stop.set()
        await task

    assert len(job.cycles) >= 3
    for (_, prev_end), (next_start, _) in zip(job.cycles, job.cycles[1:]):
        assert next_start - prev_end >= 0.05
    for start, end in job.cycles:  # cycles never overlap
        assert end - start >= 0.1


async def test_stop_interrupts_pause():
    job = SlowJob(duration=0)
    stop = asyncio.Event()

    with patch.object(feed_loop, "FEED_PAUSE_SECONDS", 60):
        task = asyncio.create_task(feed_loop.run_feed_loop(job, stop))
        await asyncio.sleep(0.05)
        stop.set()
        await asyncio.wait_for(task, timeout=1)

    assert len(job.cycles) == 1


async def test_stop_waits_for_in_flight_cycle():
    job = SlowJob(duration=0.2)
    stop = asyncio.Event()

    task = asyncio.create_task(feed_loop.run_feed_loop(job, stop))
    await asyncio.sleep(0.05)
    stop.set()
    await task

    assert len(job.cycles) == 1  # the cycle running at stop time completed
