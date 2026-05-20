"""Guard the OpenAPI contract that the UI build depends on.

The sibling wb-mqtt-ui repo generates its TypeScript types and device pages from
this app's /openapi.json. Device-state models are injected into the schema by
bootstrap._install_openapi_with_state_models so the UI codegen can read state
shapes from the contract instead of importing this package and AST-parsing the
Pydantic classes. If a state model stops appearing here, the UI build silently
loses that device's typed state — so assert it explicitly.
"""

import pytest

from wb_mqtt_bridge.app.bootstrap import create_app, OPENAPI_EXTRA_MODELS

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def openapi_schema():
    app = create_app()
    return app.openapi()


def test_all_device_state_models_present(openapi_schema):
    schemas = openapi_schema["components"]["schemas"]
    for model in OPENAPI_EXTRA_MODELS:
        assert model.__name__ in schemas, f"{model.__name__} missing from OpenAPI components.schemas"


def test_state_models_carry_their_fields(openapi_schema):
    """Spot-check that device-specific fields survive into the schema."""
    schemas = openapi_schema["components"]["schemas"]
    assert "volume" in schemas["LgTvState"]["properties"]
    assert "zone2_volume" in schemas["EmotivaXMC2State"]["properties"]
    assert "speed" in schemas["KitchenHoodState"]["properties"]


def test_nested_models_are_lifted_into_components(openapi_schema):
    """LastCommand is nested inside BaseDeviceState; its $ref must resolve."""
    schemas = openapi_schema["components"]["schemas"]
    assert "LastCommand" in schemas
    # the last_command property should $ref the lifted component, not an inline $defs entry
    last_command = schemas["BaseDeviceState"]["properties"]["last_command"]
    refs = str(last_command)
    assert "#/components/schemas/LastCommand" in refs
    assert "$defs" not in refs


def test_openapi_is_cached(openapi_schema):
    """custom_openapi must memoize so repeated /openapi.json hits are cheap."""
    app = create_app()
    first = app.openapi()
    second = app.openapi()
    assert first is second
