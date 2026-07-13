"""Device capability schema (Layer 1 of the scenario redesign) — domain data.

The capability *data* lives in JSON under ``config/capabilities/`` and is loaded
at runtime by ``infrastructure/capabilities/loader.py``; this package holds only
the pure Pydantic schema (``models``). See
``docs/design/scenarios/scenario_system_redesign.md`` §5 and §16.
"""
