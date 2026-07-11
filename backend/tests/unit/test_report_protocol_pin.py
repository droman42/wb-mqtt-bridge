"""VWB-37 (PROD-6/PROD-14, council HK-3): the problem-report filing surface must
conform to the pinned Locveil report-protocol core.

The commons repo owns the wire-visible surface as a small versioned machine core
(`locveil-commons/process/report-protocol/report-protocol.json`, tags
`report-protocol-vN`); this repo pins a copy at the repo root
(`report-protocol.pin.json`) and this test locks the collector's emitted
labels / title prefix / report-id shape / bundle path — the `REPORT_*` constants
in `domain/reports/service.py` — plus `system.json`'s explicit `reports.repo`
to that pin. On a protocol bump: re-pin first, then adjust the constants until
this passes.
"""

import json
from pathlib import Path

import pytest

from wb_mqtt_bridge.domain.reports.service import (
    REPORT_BUNDLE_NAME,
    REPORT_FILED_LABELS,
    REPORT_SOURCE,
    REPORT_TITLE_PREFIX,
)

pytestmark = pytest.mark.unit

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
PIN = json.loads((REPO / "report-protocol.pin.json").read_text(encoding="utf-8"))
PROBLEM_REPORT = PIN["types"]["problem-report"]


def test_pin_is_protocol_v1():
    assert PIN["protocol"] == 1


def test_filed_labels_match_pin():
    lens_label = PIN["lenses"]["bridge"]["label"]
    expected = [
        lens_label if raw == "<lens label>" else raw
        for raw in PROBLEM_REPORT["filed_with"]
    ]
    assert list(REPORT_FILED_LABELS) == expected
    # every emitted label is one the protocol defines (the reports repo generates
    # its label set from the same pin — an unknown label would file unlabeled)
    defined = {label["name"] for label in PIN["labels"]}
    assert set(REPORT_FILED_LABELS) <= defined


def test_title_prefix_matches_pin():
    assert REPORT_TITLE_PREFIX == PROBLEM_REPORT["title_prefixes"]["bridge"]


def test_bundle_path_shape_matches_pin():
    # pin: reports/<utc_stamp>-<source>-<room>/bundle.tar.gz ; the sink builds
    # reports/{report_id}/{bundle_name}, and the report-id carries exactly
    # <utc_stamp>-<source>-<room> (plus a uuid8 uniqueness suffix behind the
    # room slot — the VWB-30 collision fix). The emitted-value half — that a
    # real filing's id/title/labels equal these constants — is locked by
    # test_reports.py::test_file_report_builds_envelope_and_respects_rate_limit.
    assert PIN["bundle_path"] == f"reports/<utc_stamp>-<source>-<room>/{REPORT_BUNDLE_NAME}"
    assert "<source>" in PIN["bundle_path"] and REPORT_SOURCE == "bridge-ui"
    assert PROBLEM_REPORT["bundle_required"] is True


def test_system_json_repo_matches_pin():
    system = json.loads((BACKEND / "config" / "system.json").read_text(encoding="utf-8"))
    assert system["reports"]["repo"] == PIN["repos"]["reports"]
    assert PIN["repos"]["code"]["bridge"] == "locveil/locveil-bridge"
