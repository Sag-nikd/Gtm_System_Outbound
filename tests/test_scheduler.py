"""
Tests for Epics 7, 8, 9: stage registry, staging persistence, status tracking,
dependency validation, retry logic, locking, schedule config, and runner CLI.
"""
from __future__ import annotations

import json
import os
import time
import uuid

import pytest


# ── Story 7.1: Stage registry ─────────────────────────────────────────────────

class TestRegistry:
    def test_all_stages_present(self):
        from src.scheduler.registry import STAGES
        assert set(STAGES) == {"stage0", "stage1", "stage2", "stage3", "stage4"}

    def test_stage0_has_no_dependencies(self):
        from src.scheduler.registry import STAGES
        assert STAGES["stage0"]["dependencies"] == []

    def test_stage2_depends_on_stage1(self):
        from src.scheduler.registry import STAGES
        assert "stage1" in STAGES["stage2"]["dependencies"]

    def test_stage3_depends_on_stage1_and_stage2(self):
        from src.scheduler.registry import STAGES
        deps = STAGES["stage3"]["dependencies"]
        assert "stage1" in deps and "stage2" in deps

    def test_stage4_has_no_dependencies(self):
        from src.scheduler.registry import STAGES
        assert STAGES["stage4"]["dependencies"] == []

    def test_topological_order_stage3_requires_stage1_first(self):
        from src.scheduler.registry import topological_order
        order = topological_order(["stage3", "stage1"])
        assert order.index("stage1") < order.index("stage3")

    def test_topological_order_all_stages(self):
        from src.scheduler.registry import topological_order
        order = topological_order(["stage1", "stage2", "stage3", "stage4"])
        assert order.index("stage1") < order.index("stage2")
        assert order.index("stage2") < order.index("stage3")

    def test_get_stage_raises_on_unknown(self):
        from src.scheduler.registry import get_stage
        with pytest.raises(KeyError):
            get_stage("stage99")

    def test_no_cycles_in_graph(self):
        from src.scheduler.registry import validate_no_cycles
        validate_no_cycles()  # should not raise

    def test_get_all_prerequisites_stage3(self):
        from src.scheduler.registry import get_all_prerequisites
        prereqs = get_all_prerequisites("stage3")
        assert "stage1" in prereqs
        assert "stage2" in prereqs
        assert "stage3" not in prereqs


# ── Story 7.2: Staging persistence ───────────────────────────────────────────

class TestStaging:
    def test_write_and_read_roundtrip(self, tmp_path):
        from src.scheduler import staging
        run_id = str(uuid.uuid4())
        data = [{"company_id": "C001", "icp_score": 85}]
        staging.write_stage_output("stage1", data, run_id, str(tmp_path))
        result = staging.read_stage_output("stage1", run_id, str(tmp_path))
        assert result == data

    def test_written_file_has_metadata(self, tmp_path):
        from src.scheduler import staging
        run_id = str(uuid.uuid4())
        data = [{"a": 1}, {"a": 2}]
        path = staging.write_stage_output("stage1", data, run_id, str(tmp_path))
        with open(path) as f:
            payload = json.load(f)
        assert payload["stage"] == "stage1"
        assert payload["run_id"] == run_id
        assert payload["record_count"] == 2
        assert "created_at" in payload

    def test_stage_output_exists_true_after_write(self, tmp_path):
        from src.scheduler import staging
        run_id = str(uuid.uuid4())
        staging.write_stage_output("stage1", [{"x": 1}], run_id, str(tmp_path))
        assert staging.stage_output_exists("stage1", run_id, str(tmp_path))

    def test_stage_output_exists_false_before_write(self, tmp_path):
        from src.scheduler import staging
        run_id = str(uuid.uuid4())
        assert not staging.stage_output_exists("stage1", run_id, str(tmp_path))

    def test_read_missing_raises_file_not_found(self, tmp_path):
        from src.scheduler import staging
        run_id = str(uuid.uuid4())
        with pytest.raises(FileNotFoundError, match="stage1"):
            staging.read_stage_output("stage2", run_id, str(tmp_path))

    def test_cleanup_removes_old_dirs(self, tmp_path, monkeypatch):
        from src.scheduler import staging
        # Create a fake run dir with an old mtime.
        old_dir = tmp_path / "staging" / "old-run-id"
        old_dir.mkdir(parents=True)
        old_time = time.time() - (10 * 86400)  # 10 days ago
        os.utime(str(old_dir), (old_time, old_time))
        monkeypatch.setenv("STAGING_RETENTION_DAYS", "7")
        import importlib
        import src.scheduler.staging as sm
        importlib.reload(sm)
        removed = sm.cleanup_old_staging_dirs(str(tmp_path))
        assert removed >= 1


# ── Story 7.4: Status tracking ───────────────────────────────────────────────

class TestStatus:
    def test_mark_running_then_completed(self, tmp_path):
        from src.scheduler import status as sm
        run_id = str(uuid.uuid4())
        sm.mark_running("stage1", run_id, str(tmp_path))
        s = sm.load_status(str(tmp_path))
        assert s["stage1"]["status"] == "running"

        sm.mark_completed("stage1", run_id, 42, 3.5, str(tmp_path))
        s = sm.load_status(str(tmp_path))
        assert s["stage1"]["status"] == "completed"
        assert s["stage1"]["record_count"] == 42
        assert s["stage1"]["duration_seconds"] == 3.5

    def test_mark_failed_records_error(self, tmp_path):
        from src.scheduler import status as sm
        run_id = str(uuid.uuid4())
        sm.mark_failed("stage2", run_id, "API timeout", 5.0, str(tmp_path))
        s = sm.load_status(str(tmp_path))
        assert s["stage2"]["status"] == "failed"
        assert "timeout" in s["stage2"]["error"]

    def test_mark_failed_accumulates_retries(self, tmp_path):
        from src.scheduler import status as sm
        run_id = str(uuid.uuid4())
        sm.mark_failed("stage2", run_id, "err1", 1.0, str(tmp_path), attempt=1)
        sm.mark_failed("stage2", run_id, "err2", 2.0, str(tmp_path), attempt=2)
        s = sm.load_status(str(tmp_path))
        assert len(s["stage2"]["retry_attempts"]) == 2

    def test_status_file_is_atomic(self, tmp_path):
        from src.scheduler import status as sm
        run_id = str(uuid.uuid4())
        sm.mark_completed("stage1", run_id, 10, 1.0, str(tmp_path))
        # File should not have a .tmp sibling.
        assert not os.path.exists(os.path.join(str(tmp_path), "stage_status.json.tmp"))

    def test_load_status_returns_empty_dict_when_no_file(self, tmp_path):
        from src.scheduler import status as sm
        assert sm.load_status(str(tmp_path)) == {}


# ── Story 7.3: Dependency validation ─────────────────────────────────────────

class TestDependencyValidation:
    def _make_ctx(self, run_id, output_dir, force=False):
        return {
            "run_id": run_id,
            "output_dir": output_dir,
            "force": force,
        }

    def test_stage1_passes_with_no_deps(self, tmp_path):
        from src.runner import _validate_dependencies
        ctx = self._make_ctx(str(uuid.uuid4()), str(tmp_path))
        # Should not raise.
        _validate_dependencies("stage1", ctx)

    def test_stage2_fails_when_stage1_missing(self, tmp_path):
        from src.runner import _validate_dependencies
        ctx = self._make_ctx(str(uuid.uuid4()), str(tmp_path))
        with pytest.raises(RuntimeError, match="stage1"):
            _validate_dependencies("stage2", ctx)

    def test_stage2_passes_when_stage1_exists(self, tmp_path):
        from src.runner import _validate_dependencies
        from src.scheduler import staging
        run_id = str(uuid.uuid4())
        staging.write_stage_output("stage1", [{"x": 1}], run_id, str(tmp_path))
        ctx = self._make_ctx(run_id, str(tmp_path))
        _validate_dependencies("stage2", ctx)  # should not raise

    def test_force_skips_dependency_check(self, tmp_path):
        from src.runner import _validate_dependencies
        run_id = str(uuid.uuid4())
        ctx = self._make_ctx(run_id, str(tmp_path), force=True)
        # stage2 deps not met but force=True — no raise.
        _validate_dependencies("stage2", ctx)

    def test_stale_output_raises(self, tmp_path, monkeypatch):
        from src.runner import _validate_dependencies
        from src.scheduler import staging
        import src.runner as runner_mod
        run_id = str(uuid.uuid4())
        staging.write_stage_output("stage1", [{"x": 1}], run_id, str(tmp_path))
        # Fake age as 200 hours.
        monkeypatch.setattr(staging, "get_stage_output_age_hours", lambda *a: 200.0)
        monkeypatch.setattr(runner_mod, "_MAX_AGE_HOURS", 168.0)
        ctx = self._make_ctx(run_id, str(tmp_path))
        with pytest.raises(RuntimeError, match="old"):
            _validate_dependencies("stage2", ctx)


# ── Story 7.5: Retry logic ────────────────────────────────────────────────────

class TestRetryLogic:
    def test_succeeds_on_first_attempt(self):
        from src.scheduler.retry import run_with_retry
        calls = []
        def fn(ctx):
            calls.append(1)
            return [1, 2, 3]
        result = run_with_retry(fn, {}, "stage1", {})
        assert result == [1, 2, 3]
        assert len(calls) == 1

    def test_retries_on_retryable_error(self):
        from src.scheduler.retry import run_with_retry
        import requests
        attempts = []
        def fn(ctx):
            attempts.append(1)
            if len(attempts) < 3:
                raise requests.ConnectionError("timeout")
            return "ok"
        cfg = {"stage1": {"max_retries": 3, "retry_delay_seconds": 0, "retry_on": ["ConnectionError"]}}
        result = run_with_retry(fn, {}, "stage1", cfg)
        assert result == "ok"
        assert len(attempts) == 3

    def test_non_retryable_raises_immediately(self):
        from src.scheduler.retry import run_with_retry
        calls = []
        def fn(ctx):
            calls.append(1)
            raise ValueError("bad config")
        cfg = {"stage1": {"max_retries": 3, "retry_delay_seconds": 0, "retry_on": ["ConnectionError"]}}
        with pytest.raises(ValueError):
            run_with_retry(fn, {}, "stage1", cfg)
        assert len(calls) == 1

    def test_exceeds_max_retries_raises(self):
        from src.scheduler.retry import run_with_retry
        import requests
        def fn(ctx):
            raise requests.ConnectionError("always fails")
        cfg = {"stage1": {"max_retries": 2, "retry_delay_seconds": 0, "retry_on": ["ConnectionError"]}}
        with pytest.raises(requests.ConnectionError):
            run_with_retry(fn, {}, "stage1", cfg)

    def test_is_retryable_error_matches_base_class(self):
        from src.scheduler.retry import is_retryable_error
        import requests
        exc = requests.Timeout("slow")
        assert is_retryable_error(exc, ["Timeout"])

    def test_is_retryable_error_false_for_unknown(self):
        from src.scheduler.retry import is_retryable_error
        assert not is_retryable_error(ValueError("x"), ["ConnectionError"])


# ── Story 9.1: Execution locking ─────────────────────────────────────────────

class TestLocking:
    def test_acquire_and_release(self, tmp_path):
        from src.scheduler import locking
        run_id = str(uuid.uuid4())
        assert locking.acquire_lock("stage1", run_id, str(tmp_path))
        assert locking.is_locked("stage1", str(tmp_path)) is not None
        locking.release_lock("stage1", str(tmp_path))
        assert locking.is_locked("stage1", str(tmp_path)) is None

    def test_second_acquire_returns_false(self, tmp_path):
        from src.scheduler import locking
        run_id = str(uuid.uuid4())
        locking.acquire_lock("stage1", run_id, str(tmp_path))
        result = locking.acquire_lock("stage1", run_id, str(tmp_path))
        assert result is False
        locking.release_lock("stage1", str(tmp_path))

    def test_stale_lock_is_overridden(self, tmp_path, monkeypatch):
        from src.scheduler import locking
        import src.scheduler.locking as lm
        monkeypatch.setattr(lm, "_LOCK_TIMEOUT_MINUTES", 0)
        run_id = str(uuid.uuid4())
        locking.acquire_lock("stage1", run_id, str(tmp_path))
        # With timeout=0, any existing lock is stale.
        result = locking.acquire_lock("stage1", run_id, str(tmp_path))
        assert result is True
        locking.release_lock("stage1", str(tmp_path))

    def test_conflict_detected(self, tmp_path):
        from src.scheduler import locking
        run_id = str(uuid.uuid4())
        locking.acquire_lock("stage2", run_id, str(tmp_path))
        with pytest.raises(RuntimeError, match="cannot run concurrently"):
            locking.acquire_lock("stage3", run_id, str(tmp_path))
        locking.release_lock("stage2", str(tmp_path))

    def test_clear_all_locks(self, tmp_path):
        from src.scheduler import locking
        run_id = str(uuid.uuid4())
        locking.acquire_lock("stage1", run_id, str(tmp_path))
        locking.acquire_lock("stage4", run_id, str(tmp_path))
        locking.clear_all_locks(str(tmp_path))
        assert locking.is_locked("stage1", str(tmp_path)) is None
        assert locking.is_locked("stage4", str(tmp_path)) is None


# ── Story 8.1: Schedule config ───────────────────────────────────────────────

class TestScheduleConfig:
    def test_load_scheduler_config(self, tmp_path):
        from src.scheduler.config import load_scheduler_config
        cfg_data = {
            "schedules": {
                "stage1": {"enabled": True, "cron": "0 7 * * 1", "description": "test"}
            },
            "defaults": {"timezone": "UTC"}
        }
        (tmp_path / "scheduler.json").write_text(json.dumps(cfg_data))
        cfg = load_scheduler_config(str(tmp_path))
        assert cfg["schedules"]["stage1"]["enabled"] is True

    def test_validate_cron_expression_valid(self):
        from src.scheduler.config import validate_cron_expression
        assert validate_cron_expression("0 7 * * 1") is True
        assert validate_cron_expression("0 */4 * * *") is True

    def test_validate_cron_expression_invalid(self):
        from src.scheduler.config import validate_cron_expression
        assert validate_cron_expression("not a cron") is False
        assert validate_cron_expression("0 25 * * *") is False

    def test_invalid_cron_raises_on_load(self, tmp_path):
        from src.scheduler.config import load_scheduler_config
        cfg_data = {"schedules": {"stage1": {"cron": "invalid cron expression"}}}
        (tmp_path / "scheduler.json").write_text(json.dumps(cfg_data))
        with pytest.raises(ValueError, match="Invalid cron"):
            load_scheduler_config(str(tmp_path))

    def test_apply_preset_conservative(self, tmp_path):
        from src.scheduler.config import apply_preset, load_scheduler_config, save_scheduler_config
        cfg = {"schedules": {}, "defaults": {}}
        cfg = apply_preset("conservative", cfg)
        assert cfg["schedules"]["stage1"]["enabled"] is True
        assert "cron" in cfg["schedules"]["stage1"]

    def test_apply_preset_unknown_raises(self):
        from src.scheduler.config import apply_preset
        with pytest.raises(ValueError, match="Unknown preset"):
            apply_preset("ultrafast", {})

    def test_save_and_reload_config(self, tmp_path):
        from src.scheduler.config import save_scheduler_config, load_scheduler_config
        cfg = {"schedules": {"stage4": {"enabled": False, "cron": "0 * * * *"}}, "defaults": {}}
        save_scheduler_config(cfg, str(tmp_path))
        reloaded = load_scheduler_config(str(tmp_path))
        assert reloaded["schedules"]["stage4"]["enabled"] is False


# ── Story 8.5: Schedule CLI ───────────────────────────────────────────────────

class TestScheduleCLI:
    def _write_cfg(self, tmp_path):
        from src.scheduler.config import save_scheduler_config
        cfg = {
            "schedules": {
                "stage1": {"enabled": True, "cron": "0 7 * * 1", "description": "test"},
                "stage2": {"enabled": False, "cron": "0 8 * * 1", "description": "test2"},
            },
            "defaults": {}
        }
        save_scheduler_config(cfg, str(tmp_path))
        return cfg

    def _patch_settings(self, monkeypatch, tmp_path):
        from src.config.settings import settings
        monkeypatch.setattr(settings, "CONFIG_DIR", str(tmp_path))
        monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))

    def test_enable_stage(self, tmp_path, monkeypatch):
        from src.scheduler import cli
        self._patch_settings(monkeypatch, tmp_path)
        self._write_cfg(tmp_path)
        monkeypatch.setattr(cli, "_signal_daemon_reload", lambda: None)
        rc = cli.handle_schedule_command(["enable", "stage2"])
        assert rc == 0
        from src.scheduler.config import load_scheduler_config
        cfg = load_scheduler_config(str(tmp_path))
        assert cfg["schedules"]["stage2"]["enabled"] is True

    def test_disable_stage(self, tmp_path, monkeypatch):
        from src.scheduler import cli
        self._patch_settings(monkeypatch, tmp_path)
        self._write_cfg(tmp_path)
        monkeypatch.setattr(cli, "_signal_daemon_reload", lambda: None)
        rc = cli.handle_schedule_command(["disable", "stage1"])
        assert rc == 0
        from src.scheduler.config import load_scheduler_config
        cfg = load_scheduler_config(str(tmp_path))
        assert cfg["schedules"]["stage1"]["enabled"] is False

    def test_set_valid_cron(self, tmp_path, monkeypatch):
        from src.scheduler import cli
        self._patch_settings(monkeypatch, tmp_path)
        self._write_cfg(tmp_path)
        monkeypatch.setattr(cli, "_signal_daemon_reload", lambda: None)
        rc = cli.handle_schedule_command(["set", "stage1", "0 7 * * 1,4"])
        assert rc == 0

    def test_set_invalid_cron_returns_error(self, tmp_path, monkeypatch):
        from src.scheduler import cli
        self._patch_settings(monkeypatch, tmp_path)
        self._write_cfg(tmp_path)
        monkeypatch.setattr(cli, "_signal_daemon_reload", lambda: None)
        rc = cli.handle_schedule_command(["set", "stage1", "not valid"])
        assert rc == 1

    def test_unknown_subcommand_returns_error(self, tmp_path, monkeypatch):
        from src.scheduler import cli
        self._patch_settings(monkeypatch, tmp_path)
        rc = cli.handle_schedule_command(["bogus"])
        assert rc == 1


# ── Story 9.2: Per-stage logging ──────────────────────────────────────────────

class TestStageLogging:
    def test_setup_creates_log_file(self, tmp_path):
        from src.scheduler.logging_config import setup_stage_logging, teardown_stage_logging
        import logging
        run_id = str(uuid.uuid4())
        handler = setup_stage_logging("stage1", run_id, str(tmp_path))
        log = logging.getLogger("test_stage_log")
        log.setLevel(logging.INFO)
        log.addHandler(handler)
        log.info("test message")
        teardown_stage_logging(handler)
        log_dir = tmp_path / "logs"
        log_files = list(log_dir.glob("stage1_*.log"))
        assert len(log_files) == 1

    def test_log_rotation_removes_old_files(self, tmp_path):
        from src.scheduler.logging_config import rotate_old_logs
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        old_file = logs_dir / "stage1_abc12345.log"
        old_file.write_text("old log")
        old_time = time.time() - (35 * 86400)
        os.utime(str(old_file), (old_time, old_time))
        removed = rotate_old_logs(str(tmp_path), keep_days=30)
        assert removed >= 1


# ── Story 9.3: Notifications ─────────────────────────────────────────────────

class TestNotifications:
    def test_no_slack_without_webhook(self, capsys):
        from src.scheduler.notifications import send_stage_notification
        cfg = {"stage1": {"notify_on_success": True}, "defaults": {}}
        send_stage_notification("stage1", "completed", 10, 2.0, scheduler_cfg=cfg)
        # Should log but not crash.

    def test_no_notification_when_disabled(self, monkeypatch):
        from src.scheduler import notifications as nm
        sent = []
        monkeypatch.setattr(nm, "_send_slack", lambda *a, **kw: sent.append(1))
        cfg = {"stage1": {"notify_on_success": False, "notify_on_failure": False}, "defaults": {}}
        nm.send_stage_notification("stage1", "completed", 10, 1.0, scheduler_cfg=cfg)
        assert not sent

    def test_failure_notification_sent(self, monkeypatch):
        from src.scheduler import notifications as nm
        sent = []
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
        monkeypatch.setattr(nm, "_send_slack", lambda msg, ch, url, **kw: sent.append(msg))
        cfg = {"stage2": {"notify_on_failure": True}, "defaults": {}}
        nm.send_stage_notification("stage2", "failed", 0, 5.0, error="API 401", scheduler_cfg=cfg)
        assert sent
        assert "FAILED" in sent[0]

    def test_consecutive_failures_tracked(self, monkeypatch):
        from src.scheduler import notifications as nm
        nm._CONSECUTIVE_FAILURES.clear()
        nm._LAST_ALERT.clear()
        monkeypatch.setattr(nm, "_send_slack", lambda *a, **kw: None)
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://fake")
        cfg = {"stage1": {"notify_on_failure": True}, "defaults": {}}
        for i in range(3):
            nm._LAST_ALERT.clear()
            nm.send_stage_notification("stage1", "failed", 0, 1.0, error=f"err{i}", scheduler_cfg=cfg)
        assert nm._CONSECUTIVE_FAILURES.get("stage1", 0) >= 3

    def test_consecutive_failures_reset_on_success(self, monkeypatch):
        from src.scheduler import notifications as nm
        nm._CONSECUTIVE_FAILURES["stage1"] = 5
        monkeypatch.setattr(nm, "_send_slack", lambda *a, **kw: None)
        cfg = {"stage1": {"notify_on_success": True}, "defaults": {}}
        nm.send_stage_notification("stage1", "completed", 10, 1.0, scheduler_cfg=cfg)
        assert nm._CONSECUTIVE_FAILURES["stage1"] == 0


# ── Runner CLI ────────────────────────────────────────────────────────────────

class TestRunnerCLI:
    def test_list_flag_does_not_crash(self, capsys):
        from src.runner import main
        rc = main(["--list"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "stage1" in out

    def test_status_flag_does_not_crash(self, capsys):
        from src.runner import main
        rc = main(["--status"])
        assert rc == 0

    def test_status_json_flag_outputs_json(self, capsys):
        from src.runner import main
        rc = main(["--status", "--json"])
        assert rc == 0
        out = capsys.readouterr().out
        json.loads(out)  # must be valid JSON

    def test_unknown_stage_returns_nonzero(self):
        from src.runner import main
        rc = main(["stage99"])
        assert rc != 0

    def test_dry_run_stage1_does_not_write_csv(self, tmp_path, monkeypatch):
        from src.config.settings import settings
        import src.runner as runner_mod
        monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
        rc = runner_mod.main(["stage1", "--dry-run"])
        assert rc == 0
        # No CSV files should be written in dry-run.
        csvs = list(tmp_path.glob("*.csv"))
        assert len(csvs) == 0

    def test_no_args_prints_help(self, capsys):
        from src.runner import main
        rc = main([])
        assert rc == 0
