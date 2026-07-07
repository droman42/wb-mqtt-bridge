"""OPS-12: startup log rollover + retention pruning.

Voice-repo behavior: each startup renames the previous live log aside and
begins a fresh file; daily rotation still covers permanent operation. The
rotated names stay in the `service.log.*` family so the report-evidence
collector's glob (domain/reports/service.py::_collect_logs) needs no change.
"""

import logging
import re
import time
from pathlib import Path

from wb_mqtt_bridge.app.bootstrap import (
    LOG_RETENTION_DAYS,
    _prune_old_logs,
    _startup_rollover,
    setup_logging,
)


def _teardown_root_handlers():
    root = logging.getLogger()
    for h in list(root.handlers):
        h.close()
        root.handlers.remove(h)


def test_startup_rollover_renames_existing_log(tmp_path: Path):
    live = tmp_path / "service.log"
    live.write_text("previous run\n")

    _startup_rollover(live)

    assert not live.exists()
    rotated = list(tmp_path.glob("service.log.*"))
    assert len(rotated) == 1
    assert rotated[0].read_text() == "previous run\n"
    # Same filename family the daily rotation uses: service.log.<stamp>.log
    assert re.fullmatch(r"service\.log\.\d{8}_\d{6}\.log", rotated[0].name)


def test_startup_rollover_skips_missing_and_empty(tmp_path: Path):
    live = tmp_path / "service.log"
    _startup_rollover(live)  # missing: no-op, no raise
    assert list(tmp_path.iterdir()) == []

    live.touch()
    _startup_rollover(live)  # empty: reused, not renamed
    assert live.exists()
    assert list(tmp_path.glob("service.log.*")) == []


def test_prune_removes_only_expired_siblings(tmp_path: Path):
    live = tmp_path / "service.log"
    live.write_text("live\n")
    old_daily = tmp_path / "service.log.20250101.log"
    old_startup = tmp_path / "service.log.20250101_120000.log"
    fresh = tmp_path / "service.log.20260707_090000.log"
    for f in (old_daily, old_startup, fresh):
        f.write_text("x")
    expired = time.time() - (LOG_RETENTION_DAYS + 5) * 86400
    import os

    os.utime(old_daily, (expired, expired))
    os.utime(old_startup, (expired, expired))

    removed = _prune_old_logs(live)

    assert removed == 2
    assert not old_daily.exists()
    assert not old_startup.exists()
    assert fresh.exists()
    assert live.exists()  # the live file itself is never pruned


def test_setup_logging_starts_fresh_and_fixes_ext_match(tmp_path: Path):
    live = tmp_path / "service.log"
    live.write_text("previous run\n")
    try:
        setup_logging(str(live), "INFO")

        # Previous content moved aside; the live file is a fresh one.
        rotated = list(tmp_path.glob("service.log.*"))
        assert len(rotated) == 1
        assert rotated[0].read_text() == "previous run\n"
        assert "previous run" not in live.read_text()

        # The retention fix: extMatch must recognize the custom daily suffix,
        # or TimedRotatingFileHandler.getFilesToDelete() deletes nothing.
        handler = next(
            h
            for h in logging.getLogger().handlers
            if h.__class__.__name__ == "TimedRotatingFileHandler"
        )
        assert handler.extMatch.match("20260707.log")
        # Startup-renamed files stay outside the handler's cleanup (ours covers them).
        assert not handler.extMatch.match("20260707_120000.log")
    finally:
        _teardown_root_handlers()
