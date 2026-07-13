"""Load and validate the signal topology from ``config/topology.json``."""

import json
from pathlib import Path

from locveil_bridge.domain.topology.models import Topology


def load_topology(path: Path) -> Topology:
    """Load + validate ``config/topology.json``. Returns an empty topology if absent.

    Raises ``pydantic.ValidationError`` if the file is malformed.
    """
    if not path.exists():
        return Topology()
    return Topology.model_validate(json.loads(path.read_text(encoding="utf-8")))
