# Pin: report-protocol (v1)

The Locveil problem-report protocol's machine core, pinned from its owner
`locveil-commons` (`contracts/report-protocol/`, tag `report-protocol-v1`) — a
verbatim artifact copy plus the owner's `STAMP.json`, per the org contract
convention (`locveil-commons/process/contracts.md` §2). `PIN.json` records the
pinned hashes and the tag.

The bridge's filing surface (labels, title prefix, report-id/bundle shape, the
target reports repo) is locked to this pin by
`backend/tests/unit/test_report_protocol_pin.py`. On a protocol bump: re-pin
first (fetch at the new tag, refresh `PIN.json`), then adjust the `REPORT_*`
constants in `domain/reports/service.py` until conformance passes.
