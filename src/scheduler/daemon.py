"""
Scheduler daemon — long-running process that executes stages on their cron schedules.

Usage:
  python -m src.scheduler.daemon                  # foreground (default)
  python -m src.scheduler.daemon --once           # run due stages once and exit
  python -m src.scheduler.daemon --background     # daemonize (Unix only)
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Optional

from src.utils.logger import get_logger
from src.config.settings import settings
from src.scheduler.config import load_scheduler_config, get_next_run_time

log = get_logger(__name__)

_HEARTBEAT_INTERVAL = 60  # seconds
_CONFIG_RELOAD_INTERVAL = 60  # seconds


class SchedulerDaemon:
    def __init__(
        self,
        config_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
    ) -> None:
        self.config_dir = config_dir or settings.CONFIG_DIR
        self.output_dir = output_dir or settings.OUTPUT_DIR
        self._running = False
        self._cfg: dict = {}
        self._last_config_load = 0.0
        self._last_heartbeat = 0.0

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self, once: bool = False) -> None:
        if not self._acquire_daemon_lock():
            log.error("Another scheduler daemon is already running. Exiting.")
            sys.exit(1)

        self._write_pid()
        self._running = True
        self._cfg = load_scheduler_config(self.config_dir)
        self._log_startup()

        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        try:
            if once:
                self._run_due_stages()
            else:
                self._loop()
        finally:
            self._release_daemon_lock()
            self._remove_pid()

    def stop(self) -> None:
        self._running = False

    # ── Main loop ─────────────────────────────────────────────────────────────

    def _loop(self) -> None:
        while self._running:
            now = time.time()

            # Reload config if changed.
            if now - self._last_config_load > _CONFIG_RELOAD_INTERVAL:
                self._cfg = load_scheduler_config(self.config_dir)
                self._last_config_load = now

            self._run_due_stages()

            # Heartbeat.
            if now - self._last_heartbeat > _HEARTBEAT_INTERVAL:
                self._write_heartbeat()
                self._last_heartbeat = now

            time.sleep(30)

    def _run_due_stages(self) -> None:
        schedules = self._cfg.get("schedules", {})
        for stage_name, s in schedules.items():
            if not s.get("enabled", False):
                continue
            if self._is_due(stage_name, s):
                log.info("Scheduler: running %s (scheduled)", stage_name)
                self._run_stage(stage_name)

    def _is_due(self, stage_name: str, schedule_cfg: dict) -> bool:
        """Check if stage_name is due to run now (within the last check interval)."""
        from src.scheduler.status import load_status
        cron = schedule_cfg.get("cron", "")
        if not cron:
            return False
        try:
            from croniter import croniter
            from datetime import timedelta
            tz_name = self._cfg.get("defaults", {}).get("timezone", "America/New_York")
            try:
                import pytz
                tz = pytz.timezone(tz_name)
                now_tz = datetime.now(tz)
            except Exception:
                now_tz = datetime.now()
            # Was the scheduled time within the last 31 seconds?
            prev = croniter(cron, now_tz).get_prev(datetime)
            delta = abs((now_tz.replace(tzinfo=None) if now_tz.tzinfo else now_tz) -
                        (prev.replace(tzinfo=None) if prev.tzinfo else prev))
            if delta.total_seconds() > 31:
                return False
            # Don't re-run if already ran in this minute.
            status = load_status(self.output_dir)
            stage_status = status.get(stage_name, {})
            last_run = stage_status.get("last_run_at", "")
            if last_run:
                last_dt = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
                elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
                if elapsed < 55:
                    return False
            return True
        except Exception:
            return False

    def _run_stage(self, stage_name: str) -> None:
        try:
            import subprocess
            result = subprocess.run(
                [sys.executable, "-m", "src.runner", stage_name],
                cwd=settings.BASE_DIR,
                timeout=3600,
            )
            if result.returncode != 0:
                log.error("Scheduled %s exited with code %d", stage_name, result.returncode)
        except Exception as exc:
            log.error("Scheduler failed to run %s: %s", stage_name, exc)

    # ── Files ─────────────────────────────────────────────────────────────────

    def _lock_path(self) -> str:
        os.makedirs(self.output_dir, exist_ok=True)
        return os.path.join(self.output_dir, ".scheduler.lock")

    def _pid_path(self) -> str:
        return os.path.join(self.output_dir, ".scheduler.pid")

    def _heartbeat_path(self) -> str:
        return os.path.join(self.output_dir, ".scheduler_heartbeat")

    def _acquire_daemon_lock(self) -> bool:
        path = self._lock_path()
        if os.path.exists(path):
            try:
                mtime = os.path.getmtime(path)
                if time.time() - mtime < 90:  # active within 90s
                    with open(path) as f:
                        info = json.load(f)
                    pid = info.get("pid", 0)
                    # Check if process is still alive.
                    if _pid_alive(pid):
                        return False
            except Exception:
                pass
        payload = {"pid": os.getpid(), "started_at": datetime.now(timezone.utc).isoformat()}
        with open(path, "w") as f:
            json.dump(payload, f)
        return True

    def _release_daemon_lock(self) -> None:
        try:
            os.remove(self._lock_path())
        except FileNotFoundError:
            pass

    def _write_pid(self) -> None:
        with open(self._pid_path(), "w") as f:
            f.write(str(os.getpid()))

    def _remove_pid(self) -> None:
        try:
            os.remove(self._pid_path())
        except FileNotFoundError:
            pass

    def _write_heartbeat(self) -> None:
        with open(self._heartbeat_path(), "w") as f:
            f.write(datetime.now(timezone.utc).isoformat())

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _log_startup(self) -> None:
        log.info("GTM Scheduler daemon started (PID %d)", os.getpid())
        schedules = self._cfg.get("schedules", {})
        tz = self._cfg.get("defaults", {}).get("timezone", "America/New_York")
        for stage_name, s in schedules.items():
            if s.get("enabled"):
                nxt = get_next_run_time(s.get("cron", ""), tz)
                nxt_str = nxt.strftime("%Y-%m-%d %H:%M") if nxt else "—"
                log.info("  %-8s  cron=%s  next=%s", stage_name, s.get("cron"), nxt_str)

    def _handle_signal(self, signum, frame) -> None:
        log.info("Scheduler received signal %d — shutting down after current stage.", signum)
        self._running = False


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="GTM Pipeline Scheduler Daemon")
    parser.add_argument("--once", action="store_true", help="Run due stages once and exit")
    parser.add_argument("--foreground", action="store_true", help="Run in foreground (default)")
    parser.add_argument("--background", action="store_true", help="Daemonize (Unix only)")
    args = parser.parse_args()

    if args.background:
        _daemonize()

    daemon = SchedulerDaemon()
    daemon.start(once=args.once)


def _daemonize() -> None:
    """Fork to background (Unix only)."""
    try:
        pid = os.fork()
        if pid > 0:
            print(f"Scheduler daemon started with PID {pid}")
            sys.exit(0)
    except AttributeError:
        print("--background is not supported on Windows. Running in foreground.")


if __name__ == "__main__":
    main()
