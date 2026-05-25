"""Scenario reconciler (Layer R): derive the ordered action plan to reach an activity's
desired state.

Pipeline (see docs/scenarios/scenario_system_redesign.md §7):

1. **resolve** desired state from the thin scenario selection (``source``/``display``/``audio``)
   + the signal topology: which devices are involved, each sink's target input (the link's
   destination port), and any manual-node instructions on the path.
2. **diff** the targets against assumed device state (``device.get_current_state()``); emit an
   action only where current != target.
3. **translate** each action to a native command/params via the device's capability map
   (``param_map`` rename or value-mapped ``by_value``; multi-zone power; toggle-from-assumed-state).
4. **order** by the topology's ``ordering`` edges plus the universal "power before input" rule.

Execution is a separate concern (the ``ScenarioManager`` wires an executor around this plan).
This module is pure: it reads capability maps and assumed state and returns a plan.
"""

import asyncio
import heapq
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

from wb_mqtt_bridge.domain.topology.models import Topology, TopologyLink


@dataclass
class PlannedAction:
    """One translated, ready-to-execute step in the plan."""

    device_id: str
    domain: str  # "power" | "input"
    target: str  # "on" or the input value
    command: str  # native command name
    params: Dict[str, Any] = field(default_factory=dict)
    feedback: bool = False
    state_field: Optional[str] = None
    poll_timeout_ms: Optional[int] = None  # feedback: poll the state field to target
    delay_ms: int = 0  # device-declared post-action wait (no-feedback)
    pre_delay_ms: int = 0  # extra wait before this action (from a topology ordering edge)
    zone: Optional[str] = None  # multi-zone power
    reason: str = ""


@dataclass
class ManualStep:
    """A human action required on the path (e.g. a manual RCA hub)."""

    node: str
    instruction: str


@dataclass
class ReconcilePlan:
    actions: List[PlannedAction] = field(default_factory=list)
    manual_steps: List[ManualStep] = field(default_factory=list)
    already_satisfied: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# --- 1. resolve desired state from the topology ------------------------------


def _adjacency(topology: Topology) -> Dict[str, List[TopologyLink]]:
    adj: Dict[str, List[TopologyLink]] = defaultdict(list)
    for link in topology.links:
        adj[link.src_node].append(link)
    return adj


def _find_path(
    adj: Dict[str, List[TopologyLink]], source: str, target: str, signal: str
) -> Optional[List[TopologyLink]]:
    """DFS for a path ``source`` -> ``target`` following links that carry ``signal``."""
    stack: List[Tuple[str, List[TopologyLink]]] = [(source, [])]
    visited: Set[str] = set()
    while stack:
        node, path = stack.pop()
        if node == target:
            return path
        if node in visited:
            continue
        visited.add(node)
        for link in adj.get(node, []):
            if signal in link.carries and link.dst_node not in visited:
                stack.append((link.dst_node, path + [link]))
    return None


def resolve_targets(scenario, topology: Topology):
    """Return ``(input_targets, involved, manual_steps, warnings)`` for a thin scenario."""
    adj = _adjacency(topology)
    manual_nodes = set(topology.nodes)
    input_targets: Dict[str, str] = {}
    involved: Set[str] = set()
    manual_steps: List[ManualStep] = []
    warnings: List[str] = []

    if scenario.source:
        involved.add(scenario.source)

    def walk(target_node: Optional[str], signal: str) -> None:
        if not target_node or not scenario.source:
            return
        path = _find_path(adj, scenario.source, target_node, signal)
        if path is None:
            warnings.append(f"no {signal} path from '{scenario.source}' to '{target_node}'")
            return
        for link in path:
            dst = link.dst_node
            if dst in manual_nodes:
                instruction = topology.nodes[dst].positions.get(link.dst_port)
                if instruction:
                    manual_steps.append(ManualStep(node=dst, instruction=instruction))
                continue
            if dst in input_targets and input_targets[dst] != link.dst_port:
                warnings.append(
                    f"conflicting input for '{dst}': {input_targets[dst]} vs {link.dst_port}"
                )
            input_targets[dst] = link.dst_port
            involved.add(dst)

    walk(scenario.display, "video")
    walk(scenario.audio, "audio")
    return input_targets, involved, manual_steps, warnings


# --- 2/3. diff + translate ---------------------------------------------------


def _state_value(state: Any, field_name: Optional[str]) -> Any:
    return getattr(state, field_name, None) if field_name else None


def _power_actions(device_id, cap, state, warnings) -> List[PlannedAction]:
    """Emit power actions to bring a device ON (multi-zone aware, toggle aware)."""
    out: List[PlannedAction] = []
    gate = cap.gate

    if cap.zones:
        for zone_key, zone in cap.zones.items():
            if _state_value(state, zone.state_field) == zone.on_value:
                continue
            act = zone.actions.get("on")
            if not act:
                warnings.append(f"{device_id} power zone {zone_key} has no 'on' action")
                continue
            out.append(PlannedAction(
                device_id=device_id, domain="power", target=zone.on_value,
                command=act.command, params=dict(act.params), feedback=cap.feedback,
                state_field=zone.state_field, poll_timeout_ms=gate.poll_timeout_ms,
                delay_ms=gate.delay_ms, zone=zone_key, reason=f"power zone {zone_key} on",
            ))
        return out

    if _state_value(state, cap.state_field) == cap.on_value:
        return out
    act = cap.actions.get("on") or cap.actions.get("toggle")
    if not act:
        warnings.append(f"{device_id} power has no 'on' or 'toggle' action")
        return out
    is_toggle = "on" not in cap.actions and "toggle" in cap.actions
    out.append(PlannedAction(
        device_id=device_id, domain="power", target=cap.on_value,
        command=act.command, params=dict(act.params), feedback=cap.feedback,
        state_field=cap.state_field, poll_timeout_ms=gate.poll_timeout_ms,
        delay_ms=gate.delay_ms, reason="power on (toggle)" if is_toggle else "power on",
    ))
    return out


def _power_off_actions(device_id, cap, state) -> List[PlannedAction]:
    """Emit power-off actions for a device that is currently on (multi-zone/toggle aware)."""
    out: List[PlannedAction] = []
    gate = cap.gate
    if cap.zones:
        for zone_key, zone in cap.zones.items():
            if _state_value(state, zone.state_field) != zone.on_value:
                continue  # already off
            act = zone.actions.get("off") or zone.actions.get("toggle")
            if not act:
                continue
            out.append(PlannedAction(
                device_id=device_id, domain="power", target="off",
                command=act.command, params=dict(act.params), feedback=cap.feedback,
                state_field=zone.state_field, poll_timeout_ms=gate.poll_timeout_ms,
                delay_ms=gate.delay_ms, zone=zone_key, reason=f"power zone {zone_key} off",
            ))
        return out

    if _state_value(state, cap.state_field) != cap.on_value:
        return out  # already off
    act = cap.actions.get("off") or cap.actions.get("toggle")
    if not act:
        return out
    out.append(PlannedAction(
        device_id=device_id, domain="power", target="off",
        command=act.command, params=dict(act.params), feedback=cap.feedback,
        state_field=cap.state_field, poll_timeout_ms=gate.poll_timeout_ms,
        delay_ms=gate.delay_ms, reason="power off",
    ))
    return out


def build_power_off_plan(device_ids, devices: Dict[str, Any]) -> ReconcilePlan:
    """Build a teardown plan that powers off the given devices (those currently on)."""
    plan = ReconcilePlan()
    for device_id in device_ids:
        device = devices.get(device_id)
        if device is None:
            plan.warnings.append(f"device '{device_id}' not found")
            continue
        cap_map = getattr(device, "capabilities", None)
        power_cap = cap_map.get("power") if cap_map else None
        if power_cap is None:
            continue
        plan.actions.extend(_power_off_actions(device_id, power_cap, device.get_current_state()))
    return plan


def _input_action(device_id, cap, state, target_value, warnings) -> Optional[PlannedAction]:
    if _state_value(state, cap.state_field) == target_value:
        return None
    sel = cap.select
    if sel is None:
        warnings.append(f"{device_id} has no input.select")
        return None
    gate = cap.gate

    if sel.by_value is not None:
        act = sel.by_value.get(target_value)
        if not act:
            warnings.append(f"{device_id} input has no value '{target_value}'")
            return None
        command, params = act.command, dict(act.params)
    else:
        command = sel.command
        native_param = sel.param_map.get("input", "input")
        params = {native_param: target_value, **sel.params}

    return PlannedAction(
        device_id=device_id, domain="input", target=target_value, command=command,
        params=params, feedback=cap.feedback, state_field=cap.state_field,
        poll_timeout_ms=gate.poll_timeout_ms, delay_ms=gate.delay_ms,
        reason=f"input -> {target_value}",
    )


# --- 4. order ----------------------------------------------------------------


def _matches(action: PlannedAction, key: str) -> bool:
    device, _, domain = key.partition(".")
    return action.device_id == device and action.domain == domain


def _order(actions: List[PlannedAction], topology: Topology) -> List[PlannedAction]:
    """Topologically order actions by power-before-input + topology ordering edges.

    Stable: ties break by original index. ``delay_ms`` from an ordering edge becomes the
    successor action's ``pre_delay_ms``.
    """
    n = len(actions)
    succ: Dict[int, Set[int]] = defaultdict(set)
    indeg = [0] * n
    pre_delay = [0] * n

    def add_edge(i: int, j: int, delay: int = 0) -> None:
        if i != j and j not in succ[i]:
            succ[i].add(j)
            indeg[j] += 1
        if delay:
            pre_delay[j] = max(pre_delay[j], delay)

    # universal: power before input, per device
    for i, a in enumerate(actions):
        if a.domain != "power":
            continue
        for j, b in enumerate(actions):
            if b.domain == "input" and b.device_id == a.device_id:
                add_edge(i, j)

    # topology ordering edges (first -> then), applied to all matching action pairs
    for edge in topology.ordering:
        firsts = [i for i, a in enumerate(actions) if _matches(a, edge.first)]
        thens = [j for j, b in enumerate(actions) if _matches(b, edge.then)]
        for i in firsts:
            for j in thens:
                add_edge(i, j, edge.delay_ms)

    ready = [i for i in range(n) if indeg[i] == 0]
    heapq.heapify(ready)
    order: List[int] = []
    while ready:
        i = heapq.heappop(ready)
        order.append(i)
        for j in sorted(succ[i]):
            indeg[j] -= 1
            if indeg[j] == 0:
                heapq.heappush(ready, j)

    if len(order) != n:  # cycle (shouldn't happen); fall back to input order
        order = list(range(n))

    result: List[PlannedAction] = []
    for idx in order:
        actions[idx].pre_delay_ms = pre_delay[idx]
        result.append(actions[idx])
    return result


# --- top-level ---------------------------------------------------------------


def build_plan(scenario, topology: Topology, devices: Dict[str, Any]) -> ReconcilePlan:
    """Build the ordered reconcile plan for a thin ``scenario``.

    ``devices`` maps device_id -> device (each with ``.capabilities`` and ``.get_current_state()``).
    """
    plan = ReconcilePlan()
    input_targets, involved, manual_steps, warnings = resolve_targets(scenario, topology)
    plan.manual_steps = manual_steps
    plan.warnings.extend(warnings)

    raw: List[PlannedAction] = []
    for device_id in sorted(involved):
        device = devices.get(device_id)
        if device is None:
            plan.warnings.append(f"device '{device_id}' not found")
            continue
        cap_map = getattr(device, "capabilities", None)
        if cap_map is None:
            plan.warnings.append(f"device '{device_id}' has no capability map")
            continue
        state = device.get_current_state()

        power_cap = cap_map.get("power")
        if power_cap is not None and power_cap.reconcile:
            power_actions = _power_actions(device_id, power_cap, state, plan.warnings)
            if power_actions:
                raw.extend(power_actions)
            else:
                plan.already_satisfied.append(f"{device_id}.power")

        if device_id in input_targets:
            input_cap = cap_map.get("input")
            if input_cap is None:
                plan.warnings.append(f"device '{device_id}' has no input capability")
            elif input_cap.reconcile:
                action = _input_action(device_id, input_cap, state, input_targets[device_id], plan.warnings)
                if action is not None:
                    raw.append(action)
                else:
                    plan.already_satisfied.append(f"{device_id}.input")

    plan.actions = _order(raw, topology)
    return plan


# --- execution ---------------------------------------------------------------


@dataclass
class ExecutionResult:
    executed: List[PlannedAction] = field(default_factory=list)
    failures: List[Tuple[PlannedAction, str]] = field(default_factory=list)
    manual_steps: List[ManualStep] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return not self.failures


def _response_ok(resp: Any) -> Tuple[bool, Optional[str]]:
    """Read success/error from a CommandResponse (dict-like) without assuming a type."""
    if isinstance(resp, dict):
        return bool(resp.get("success", True)), resp.get("error")
    return bool(getattr(resp, "success", True)), getattr(resp, "error", None)


async def _gate(device: Any, action: PlannedAction, poll_interval_ms: int) -> bool:
    """Wait for an action to take effect: poll feedback devices to the target value (up to
    ``poll_timeout_ms``); otherwise wait the fixed ``delay_ms``. Returns False on poll timeout."""
    if action.feedback and action.state_field and action.poll_timeout_ms:
        elapsed = 0
        while elapsed < action.poll_timeout_ms:
            if getattr(device.get_current_state(), action.state_field, None) == action.target:
                return True
            await asyncio.sleep(poll_interval_ms / 1000)
            elapsed += poll_interval_ms
        logger.warning(
            "gate timeout: %s.%s did not reach %r within %dms (proceeding optimistically)",
            action.device_id, action.domain, action.target, action.poll_timeout_ms,
        )
        return False
    if action.delay_ms:
        await asyncio.sleep(action.delay_ms / 1000)
    return True


async def execute_plan(
    plan: ReconcilePlan,
    devices: Dict[str, Any],
    *,
    abort_on_failure: bool = False,
    poll_interval_ms: int = 200,
) -> ExecutionResult:
    """Execute an ordered plan: honor pre-delays, dispatch the native command, check success
    (failures are surfaced, not swallowed -- fixes RC2), then gate before the next step."""
    result = ExecutionResult(manual_steps=list(plan.manual_steps))

    for action in plan.actions:
        if action.pre_delay_ms:
            await asyncio.sleep(action.pre_delay_ms / 1000)

        device = devices.get(action.device_id)
        if device is None:
            result.failures.append((action, "device not found"))
            if abort_on_failure:
                break
            continue

        try:
            resp = await device.execute_action(action.command, action.params, source="scenario")
            ok, err = _response_ok(resp)
        except Exception as exc:  # noqa: BLE001 - surface any driver error as a failure
            ok, err = False, str(exc)

        if not ok:
            result.failures.append((action, err or "command failed"))
            logger.error(
                "scenario step failed: %s %s(%s) -> %s",
                action.device_id, action.command, action.params, err,
            )
            if abort_on_failure:
                break
            continue

        result.executed.append(action)
        await _gate(device, action, poll_interval_ms)

    return result
