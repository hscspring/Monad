"""
MONAD Tools: Schedule Helpers
Injected into python_exec namespace so LLM can create/manage scheduled tasks.
"""

from datetime import datetime

from monad.proactive.jobs import Job, delete_job, load_all_jobs


def schedule_task(
    task: str,
    schedule: str,
    notify: str = "auto",
    name: str | None = None,
) -> str:
    """Create a scheduled recurring task.

    Args:
        task: Task description (same as what you'd tell MONAD).
        schedule: Schedule expression — "daily HH:MM", "hourly",
                  "every Nm", "every Nh", "weekly MON HH:MM",
                  "monthly DD HH:MM".
        notify: Notification channel — "auto", "web", "feishu", "cli", "desktop".
        name: Job name (auto-generated from task if not provided).

    Returns:
        Confirmation message with the job ID.
    """
    job_id = name or _auto_id(task)
    job = Job(
        id=job_id,
        type="cron",
        task=task,
        schedule=schedule,
        notify=notify,
        created_at=datetime.now().isoformat(),
    )
    path = job.save()
    return f"Scheduled task created: {job_id} ({schedule}) → {path}"


def monitor_condition(
    condition_code: str,
    task: str,
    interval_minutes: int = 60,
    notify: str = "auto",
    name: str | None = None,
) -> str:
    """Set up a monitoring job that triggers when a condition is met.

    Args:
        condition_code: Python code that returns True when the condition is met.
        task: What to do when the condition triggers.
        interval_minutes: How often to check (default 60 minutes).
        notify: Notification channel.
        name: Job name.

    Returns:
        Confirmation message with the job ID.
    """
    job_id = name or _auto_id(task)
    job = Job(
        id=job_id,
        type="monitor",
        task=task,
        condition=condition_code,
        interval_minutes=interval_minutes,
        notify=notify,
        created_at=datetime.now().isoformat(),
    )
    path = job.save()
    return f"Monitor job created: {job_id} (check every {interval_minutes}m) → {path}"


def list_schedules() -> str:
    """List all scheduled jobs and their status.

    Returns:
        Formatted table of all jobs.
    """
    jobs = load_all_jobs()
    if not jobs:
        return "No scheduled jobs."

    lines = ["ID | Type | Schedule/Interval | Enabled | Last Run"]
    lines.append("-" * 60)
    for job in jobs.values():
        sched = job.schedule or f"every {job.interval_minutes}m" if job.type == "monitor" else ""
        if job.type == "idle":
            sched = f"idle >{job.min_idle_minutes}m"
        elif job.type == "cron":
            sched = job.schedule
        last = job.last_run[:16] if job.last_run else "never"
        lines.append(
            f"{job.id} | {job.type} | {sched} | "
            f"{'yes' if job.enabled else 'no'} | {last}"
        )
    return "\n".join(lines)


def cancel_schedule(name: str) -> str:
    """Cancel (delete) a scheduled job.

    Args:
        name: The job ID to cancel.

    Returns:
        Confirmation or error message.
    """
    if delete_job(name):
        return f"Job '{name}' has been cancelled and removed."
    return f"Job '{name}' not found."


def _auto_id(task: str) -> str:
    """Generate a job ID from the task description."""
    clean = "".join(c if c.isalnum() or c in " _-" else "" for c in task)
    words = clean.strip().split()[:4]
    base = "_".join(w.lower() for w in words) if words else "job"
    return base[:40]
