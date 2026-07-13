"""Device capability loading (Layer 1 of the scenario redesign).

Capability *data* lives in JSON under ``config/capabilities/`` and is loaded at
runtime by ``loader`` here; the pure Pydantic schema now lives in the domain at
``locveil_bridge.domain.capabilities.models``. See
``docs/design/scenarios/scenario_system_redesign.md`` §5 and §16.
"""
