"""Canonical param-descriptor projection (canonical_first.md §6, SCN-7/VWB-15).

THE single code path that turns a native command's param specs into client-facing
parameter descriptors — consumed by the Layer-3 manifest (native-name view, SCN-7)
and by the catalog's ``CatalogAction.params`` (canonical-name view, VWB-15). One
metadata source means one function, not a synchronization discipline.

Rules (decided 2026-07-04):
- constraints (type/min/max/required/default/description) come from the native config
  param spec — where the driver enforces them; nothing is authored twice;
- params FIXED by the capability action (``cap_action.params``, e.g. ``{"zone": 2}``)
  are excluded — they are implementation, not signature;
- with ``canonical_names=True`` the native name is renamed through the REVERSED
  ``param_map`` (the capability layer owns the canonical↔native correspondence);
  names absent from the map pass through unchanged — mirroring the dispatch-side
  pass-through semantics;
- sequence-form actions project the union of their steps' params (first spec wins).
"""

from typing import Any, Dict, List, Optional


def _spec_dict(p: Any, name: str) -> Dict[str, Any]:
    return {
        "name": name,
        "type": getattr(p, "type", "string") or "string",
        "required": bool(getattr(p, "required", False)),
        "default": getattr(p, "default", None),
        "min": getattr(p, "min", None),
        "max": getattr(p, "max", None),
        "description": getattr(p, "description", "") or "",
        # VWB-20/G4: the semantic unit rides the descriptor (°C, %, dB, min, …) —
        # voice parses «поставь двадцать два градуса» against a °C-shaped target.
        "unit": getattr(p, "units", None),
    }


def project_params(
    native_cmd: Any,
    cap_action: Any = None,
    *,
    canonical_names: bool = False,
) -> List[Dict[str, Any]]:
    """Project one native command's param specs to client-facing descriptors.

    ``native_cmd`` is the config command object (carries ``.params`` specs);
    ``cap_action`` is the capability action binding it (carries ``param_map`` +
    fixed ``params``), or None for a bare native projection.
    """
    fixed = set((getattr(cap_action, "params", None) or {}).keys()) if cap_action else set()
    param_map: Dict[str, str] = dict(getattr(cap_action, "param_map", None) or {}) if cap_action else {}
    # reversed: native name -> canonical name
    reverse = {native: canonical for canonical, native in param_map.items()}

    out: List[Dict[str, Any]] = []
    for p in (getattr(native_cmd, "params", None) or []):
        native_name = str(getattr(p, "name", "") or "")
        if not native_name or native_name in fixed:
            continue
        name = reverse.get(native_name, native_name) if canonical_names else native_name
        out.append(_spec_dict(p, name))
    return out


def project_action_params(
    cap_action: Any,
    available_commands: Dict[str, Any],
    *,
    canonical_names: bool = True,
) -> Optional[List[Dict[str, Any]]]:
    """Project a capability action's client-facing params (canonical view by default —
    the catalog's ``CatalogAction.params`` shape). Sequence-form actions union their
    steps' descriptors (first spec per name wins). Returns None when the action takes
    no client params."""
    steps = [cap_action] if getattr(cap_action, "command", None) else list(getattr(cap_action, "sequence", None) or [])
    seen: Dict[str, Dict[str, Any]] = {}
    for step in steps:
        step_command = getattr(step, "command", None)
        if not step_command:
            continue
        cmd = available_commands.get(step_command)
        if cmd is None:
            continue
        for d in project_params(cmd, step, canonical_names=canonical_names):
            seen.setdefault(d["name"], d)
    return list(seen.values()) or None
