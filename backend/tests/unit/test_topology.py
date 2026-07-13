"""Tests for the topology schema + loader (scenario redesign, Layer 0)."""

import json
from pathlib import Path

import pytest

from locveil_bridge.domain.topology.loader import load_topology
from locveil_bridge.domain.topology.models import Topology

TOPOLOGY = Path(__file__).resolve().parents[3] / "config" / "topology.json"


def test_real_topology_loads():
    t = load_topology(TOPOLOGY)
    assert len(t.links) >= 10
    assert len(t.ordering) >= 6
    # the Dodocus manual node carries the analog-source switch instructions
    assert "dodocus" in t.nodes
    assert set(t.nodes["dodocus"].positions) == {"ld", "vhs", "reel", "tape", "phono"}
    # passive analog gear (no driver) are manual nodes too: the two sources + the phono corrector
    assert {"b215", "kuzma", "sugden_pa4"} <= set(t.nodes)


def test_link_dst_port_is_the_input_value():
    t = load_topology(TOPOLOGY)
    # eMotiva output -> amp 'aux2' input; dst_port is the value the sink selects
    amp_link = next(l for l in t.links if l.dst_node == "mf_amplifier" and l.dst_port == "aux2")
    assert amp_link.src_node == "processor"
    assert "audio" in amp_link.carries
    tv_link = next(l for l in t.links if l.dst_node == "living_room_tv")
    assert tv_link.dst_port == "hdmi2"


def test_ordering_uses_first_then():
    t = load_topology(TOPOLOGY)
    pairs = {(o.first, o.then) for o in t.ordering}
    assert ("living_room_tv.power", "processor.power") in pairs
    assert ("living_room_tv.input", "processor.input") in pairs
    # the IR upscaler edge carries a fixed delay (no feedback)
    ups = next(o for o in t.ordering if o.then == "upscaler.input" and o.first == "ld_player.power")
    assert ups.delay_ms == 4500


def test_missing_topology_is_empty(tmp_path):
    t = load_topology(tmp_path / "nope.json")
    assert t.links == [] and t.ordering == [] and t.nodes == {}


def test_unknown_link_field_rejected():
    with pytest.raises(Exception):
        Topology.model_validate({"links": [{"from": "a:1", "to": "b:2", "carries": ["video"], "bogus": 1}]})
