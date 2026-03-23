"""
MONAD Proactive: Scheduler
Background scheduler that checks for due jobs and submits them to the task queue.
Uses APScheduler for reliable background job checking.
"""

import queue
import time
from dataclasses import dataclass
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from loguru import logger

from monad.config import IDLE_THRESHOLD_MINUTES, PROACTIVE_CHECK_INTERVAL
from monad.proactive.jobs import Job, load_all_jobs


@dataclass
class ProactiveTask:
    """A task submitted by the scheduler for MonadLoop to process."""

    job_id: str
    task: str
    notify: str
    job_type: str


class Scheduler:
    """Background scheduler that monitors jobs and submits due tasks."""

    def __init__(self, task_queue: queue.Queue):
        self._task_queue = task_queue
        self._last_interaction = time.time()
        self._running = False
        self._processing_proactive = False
        self._scheduler: BackgroundScheduler | None = None

    def start(self) -> None:
        """Start the background scheduler."""
        self._running = True
        self._scheduler = BackgroundScheduler(daemon=True)
        self._scheduler.add_job(
            self._check_due_jobs,
            "interval",
            seconds=PROACTIVE_CHECK_INTERVAL,
            id="monad_proactive_check",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info("Proactive scheduler started")

    def stop(self) -> None:
        """Stop the background scheduler."""
        self._running = False
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
        logger.info("Proactive scheduler stopped")

    def touch(self) -> None:
        """Reset idle timer — called on every user interaction."""
        self._last_interaction = time.time()

    @property
    def idle_minutes(self) -> float:
        return (time.time() - self._last_interaction) / 60

    @property
    def is_processing_proactive(self) -> bool:
        return self._processing_proactive

    @is_processing_proactive.setter
    def is_processing_proactive(self, value: bool) -> None:
        self._processing_proactive = value

    def _check_due_jobs(self) -> None:
        """Check all jobs and enqueue due ones."""
        if not self._running:
            return
        if self._processing_proactive:
            return

        now = datetime.now()
        idle = self.idle_minutes

        try:
            jobs = load_all_jobs()
        except Exception as e:
            logger.warning(f"Failed to load jobs: {e}")
            return

        for job in jobs.values():
            if not job.is_due(now, idle):
                continue

            if job.type == "idle" and idle < IDLE_THRESHOLD_MINUTES:
                continue

            ptask = ProactiveTask(
                job_id=job.id,
                task=job.task,
                notify=job.notify,
                job_type=job.type,
            )

            try:
                self._task_queue.put_nowait(ptask)
            except queue.Full:
                logger.warning(f"Proactive task queue full, skipping job {job.id}")
                continue

            job.mark_executed(now)
            job.save()
            logger.info(f"Enqueued proactive task: {job.id} ({job.type})")
            break  # one proactive task at a time
