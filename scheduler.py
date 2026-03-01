"""
scheduler.py — Runs the job agent daily at the configured time.

Usage:
    python scheduler.py          # Runs the scheduler (keeps running)
    python main.py               # Run once immediately
    crontab: 0 8 * * * cd /path/to/job-agent && python main.py
"""
import logging
import time
from datetime import datetime

import schedule
import yaml

from main import main as run_agent


def load_schedule_config():
    with open("config.yaml") as f:
        config = yaml.safe_load(f)
    return config.get("schedule", {})


def run_with_logging():
    """Wrapper that adds timing and error handling."""
    start = datetime.now()
    print(f"\n{'='*60}")
    print(f"🕐 Job Agent triggered at {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    try:
        run_agent()
    except Exception as e:
        logging.error(f"Pipeline failed: {e}", exc_info=True)

    elapsed = (datetime.now() - start).total_seconds()
    print(f"\n⏱️  Completed in {elapsed:.0f} seconds")


if __name__ == "__main__":
    sched_config = load_schedule_config()
    run_time = sched_config.get("run_time", "08:00")
    tz = sched_config.get("timezone", "Europe/London")

    print(f"📅 Job Agent Scheduler")
    print(f"   Scheduled daily at {run_time} ({tz})")
    print(f"   Press Ctrl+C to stop\n")

    schedule.every().day.at(run_time).do(run_with_logging)

    # Also run immediately on first start (optional — comment out if not wanted)
    # run_with_logging()

    while True:
        schedule.run_pending()
        time.sleep(60)
