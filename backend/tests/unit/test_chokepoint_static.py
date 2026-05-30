"""Static-analysis regression test for the state-sync chokepoint convention.

Every runtime mutation of ``self.state.X`` in a device driver must route through
``BaseDevice.update_state(**)`` rather than direct attribute assignment. Direct
assignment bypasses the chokepoint and silently breaks all three downstream
callbacks: ``state.db`` persistence, WB virtual-device value-topic publish, and
SSE broadcast.

Pre-callback-registration assignments inside ``__init__`` are allowed — the state
callbacks aren't wired yet, so the chokepoint can't fire. LG TV's ``ip_address``
and ``mac_address`` are the documented examples (config copies, never mutated at
runtime).

This complements the functional tests in ``test_state_change_chokepoint.py`` —
those lock in the chokepoint's *behaviour*; this one locks in that drivers
*reach* it.

History: 2026-05-27 audit found 33 direct-assignment sites in the LG TV driver;
rewrite to ``update_state(**)`` made the WB UI reflect real state for the first
time. See memory: state-sync-chokepoint.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

DEVICES_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src" / "wb_mqtt_bridge" / "infrastructure" / "devices"
)


def _discover_drivers() -> list[Path]:
    return sorted(DEVICES_ROOT.glob("*/driver.py"))


def _is_self_state_target(target: ast.expr) -> str | None:
    """If ``target`` is ``self.state.X``, return ``X``. Otherwise ``None``."""
    if (
        isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Attribute)
        and isinstance(target.value.value, ast.Name)
        and target.value.value.id == "self"
        and target.value.attr == "state"
    ):
        return target.attr
    return None


def _containing_function(tree: ast.AST, lineno: int) -> str | None:
    """Name of the deepest function definition containing ``lineno``."""
    best: str | None = None
    best_start = -1
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = node.end_lineno or node.lineno
            if node.lineno <= lineno <= end and node.lineno > best_start:
                best, best_start = node.name, node.lineno
    return best


@pytest.mark.parametrize(
    "driver_path",
    _discover_drivers(),
    ids=lambda p: p.parent.name,
)
def test_no_direct_state_assignments_outside_init(driver_path: Path) -> None:
    tree = ast.parse(driver_path.read_text())

    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            targets = [node.target]
        else:
            continue

        for tgt in targets:
            attr = _is_self_state_target(tgt)
            if attr is None:
                continue
            method = _containing_function(tree, node.lineno)
            if method == "__init__":
                continue  # pre-callback-registration, no chokepoint to bypass
            violations.append(
                f"{driver_path.relative_to(DEVICES_ROOT)}:{node.lineno} "
                f"in {method}() — `self.state.{attr} = ...` bypasses update_state()"
            )

    assert not violations, (
        "State-sync chokepoint convention violated. Use "
        "`self.update_state({field}=value)` instead — see memory: "
        "state-sync-chokepoint.\n"
        + "\n".join(f"  - {v}" for v in violations)
    )
