"""Regression: every device driver class registered via the `wb_mqtt_bridge.devices`
entry-point group must accept the constructor kwargs DeviceManager.initialize_devices
passes. Otherwise the moment DeviceManager passes a new kwarg, every driver TypeErrors
at instantiation and the bridge boots with no devices -- a real production bug surfaced
in §P3.7 #18 follow-up when `wb_service=` was added to the constructor call (BaseDevice
accepts it; the AV subclasses override __init__ with a narrower signature and don't).

Keep `INIT_KWARGS_PASSED_BY_DEVICEMANAGER` in lock-step with the actual call in
`domain/devices/service.py::DeviceManager.initialize_devices`. When that signature
changes, this set is the one place to update -- the test then auto-fails for any driver
that hasn't widened to match, instead of the bridge silently losing devices at boot.
"""
import inspect
from importlib.metadata import entry_points

# The set of kwargs DeviceManager.initialize_devices currently passes at construction.
# `config` is positional and unconditional. Anything else here MUST be acceptable to every
# driver class -- either as a named param OR absorbed by **kwargs.
INIT_KWARGS_PASSED_BY_DEVICEMANAGER = {"mqtt_client"}


def _registered_device_classes():
    eps = entry_points()
    if hasattr(eps, "select"):  # py3.10+
        devs = eps.select(group="wb_mqtt_bridge.devices")
    else:  # py3.8-3.9
        devs = eps.get("wb_mqtt_bridge.devices", [])
    for ep in devs:
        yield ep.name, ep.load()


def test_every_registered_driver_accepts_devicemanager_kwargs():
    failures = []
    for name, cls in _registered_device_classes():
        sig = inspect.signature(cls.__init__)
        params = sig.parameters
        has_var_kw = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
        )
        for required in INIT_KWARGS_PASSED_BY_DEVICEMANAGER:
            if required not in params and not has_var_kw:
                failures.append(
                    f"  {cls.__name__} (entry point {name!r}) does not accept "
                    f"{required!r}; signature is {sig}"
                )
    assert not failures, (
        "Some device driver classes can't accept the kwargs DeviceManager passes -- the "
        "bridge would boot with these devices missing. Widen the offending __init__s OR "
        "remove the offending kwarg from DeviceManager.initialize_devices.\n"
        + "\n".join(failures)
    )
