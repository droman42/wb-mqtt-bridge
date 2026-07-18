"""The bridge's DynamicLoader singleton (CORE-7, PROD-8 consumer #2).

core-py ships the class only — each consumer owns its instance (no module-level
singleton travels with the vendored file). This module is that instance's home:
`utils/` is the foundation layer, so `domain/` may import it without a new
import-linter exception (the `hexagonal-architecture` binding condition — the
loader lives here, never in `domain/`).

The vendored engine beside this file is a strict pin: byte-identical to
`contracts/pins/core-py/entry_point_loader.py` (enforced by
`tests/unit/test_core_py_pin_identity.py`). Never edit it — changes happen in
locveil-commons `packages/core-py`, re-tag, re-pin.
"""

from locveil_bridge.utils.entry_point_loader import DynamicLoader

dynamic_loader = DynamicLoader()
