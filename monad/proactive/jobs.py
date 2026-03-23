"""
MONAD Proactive: Job Model
Defines scheduled job types and YAML persistence.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml
from loguru import logger

from monad.config import CONFIG


@dataclass
class Job:
    """A proactive task definition persisted as YAML."""

    id: str
    type: str  # "cron", "monitor", "idle"
    task: str
    schedule: str = ""
    interval_minutes: int = 60
    min_idle_minutes: int = 30
    condition: str = ""
    notify: str = "auto"
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_run: str | None = None
    daily_budget: int = 0

    def is_due(self, now: datetime, idle_minutes: float = 0) -> bool:
        """Check if this job should run now."""
        if not self.enabled:
            return False

        if self.type == "idle":
            if idle_minutes < self.min_idle_minutes:
                return False
            if self.last_run:
                last = datetime.fromisoformat(self.last_run)
                elapsed = (now - last).total_seconds() / 60
                if elapsed < self.min_idle_minutes:
                    return False
            return True

        if self.type == "monitor":
            if not self.last_run:
                return True
            last = datetime.fromisoformat(self.last_run)
            return (now - last).total_seconds() / 60 >= self.interval_minutes

        if self.type == "cron":
            return _schedule_matches(self.schedule, now, self.last_run)

        return False

    def mark_executed(self, now: datetime) -> None:
        self.last_run = now.isoformat()

    def to_yaml_path(self) -> Path:
        return CONFIG.schedules_path / f"{self.id}.yaml"

    def save(self) -> Path:
        """Persist this job to YAML."""
        path = self.to_yaml_path()
        data = {
            "id": self.id,
            "type": self.type,
            "task": self.task,
            "notify": self.notify,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "last_run": self.last_run,
        }
        if self.type == "cron":
            data["schedule"] = self.schedule
        elif self.type == "monitor":
            data["interval_minutes"] = self.interval_minutes
            if self.condition:
                data["condition"] = self.condition
        elif self.type == "idle":
            data["min_idle_minutes"] = self.min_idle_minutes
            if self.daily_budget:
                data["daily_budget"] = self.daily_budget
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.dump(data, allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )
        return path

    @classmethod
    def from_yaml(cls, path: Path) -> "Job | None":
        """Load a job from a YAML file."""
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "id" not in data:
                return None
            return cls(
                id=data["id"],
                type=data.get("type", "cron"),
                task=data.get("task", ""),
                schedule=data.get("schedule", ""),
                interval_minutes=data.get("interval_minutes", 60),
                min_idle_minutes=data.get("min_idle_minutes", 30),
                condition=data.get("condition", ""),
                notify=data.get("notify", "auto"),
                enabled=data.get("enabled", True),
                created_at=data.get("created_at", ""),
                last_run=data.get("last_run"),
                daily_budget=data.get("daily_budget", 0),
            )
        except Exception as e:
            logger.warning(f"Failed to load job from {path}: {e}")
            return None


def load_all_jobs() -> dict[str, Job]:
    """Load all jobs from ~/.monad/schedules/*.yaml."""
    jobs: dict[str, Job] = {}
    sched_dir = CONFIG.schedules_path
    if not sched_dir.exists():
        return jobs
    for path in sorted(sched_dir.glob("*.yaml")):
        job = Job.from_yaml(path)
        if job:
            jobs[job.id] = job
    return jobs


def delete_job(job_id: str) -> bool:
    """Delete a job YAML file."""
    path = CONFIG.schedules_path / f"{job_id}.yaml"
    if path.exists():
        path.unlink()
        return True
    return False


# ── Schedule format parser ──────────────────────────────────────

_WEEKDAYS = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3,
    "fri": 4, "sat": 5, "sun": 6,
}


def _schedule_matches(schedule: str, now: datetime, last_run: str | None) -> bool:
    """Check if a simple schedule expression matches the current time.

    Supported formats:
        daily HH:MM
        hourly
        every Nm  (every N minutes)
        every Nh  (every N hours)
        weekly MON HH:MM
        monthly DD HH:MM
    """
    schedule = schedule.strip().lower()
    if not schedule:
        return False

    if last_run:
        last = datetime.fromisoformat(last_run)
    else:
        last = None

    if schedule == "hourly":
        if last and (now - last).total_seconds() < 3500:
            return False
        return now.minute == 0

    m = re.match(r"every\s+(\d+)\s*([mh])", schedule)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        interval_sec = n * 60 if unit == "m" else n * 3600
        if not last:
            return True
        return (now - last).total_seconds() >= interval_sec

    m = re.match(r"daily\s+(\d{1,2}):(\d{2})", schedule)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        if last and last.date() == now.date():
            return False
        return now.hour == hour and now.minute == minute

    m = re.match(r"weekly\s+(\w{3})\s+(\d{1,2}):(\d{2})", schedule)
    if m:
        day_str, hour, minute = m.group(1), int(m.group(2)), int(m.group(3))
        weekday = _WEEKDAYS.get(day_str)
        if weekday is None:
            return False
        if now.weekday() != weekday:
            return False
        if last and last.date() == now.date():
            return False
        return now.hour == hour and now.minute == minute

    m = re.match(r"monthly\s+(\d{1,2})\s+(\d{1,2}):(\d{2})", schedule)
    if m:
        day, hour, minute = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if now.day != day:
            return False
        if last and last.date() == now.date():
            return False
        return now.hour == hour and now.minute == minute

    logger.warning(f"Unrecognized schedule format: {schedule}")
    return False
