# Integration Tests for WB-MQTT Bridge

This document describes the integration tests implemented as part of Phase 7 of the WB-MQTT Bridge application layer changes.

## Overview

The integration tests verify three key aspects of the system:

1. **State Type Preservation** - Ensure concrete state types are preserved during updates
2. **MQTT Command Propagation** - Verify MQTT commands are properly included in handler responses
3. **API Response Structure** - Check that API endpoints return properly typed responses

## Test Implementation

The tests are implemented in `tests/test_integration.py` using the Python `unittest` framework.

### 1. State Type Preservation Tests

These tests verify that the concrete state types (e.g., `KitchenHoodState`, `WirenboardIRState`) are preserved when calling `update_state()`. This ensures that type-safety is maintained throughout the application.

```python
def test_kitchen_hood_state_preservation(self):
    """Test that KitchenHoodState type is preserved during update_state."""
    # Create a real KitchenHood device with mocked config
    device = BroadlinkKitchenHood(self.hood_config, self.mock_mqtt_client)
    
    # Verify initial state type
    self.assertIsInstance(device.state, KitchenHoodState)
    
    # Update state with new values
    device.update_state(light="on", speed=2)
    
    # Verify type is preserved and values are updated
    self.assertIsInstance(device.state, KitchenHoodState)
    self.assertEqual(device.state.light, "on")
    self.assertEqual(device.state.speed, 2)
```

### 2. MQTT Command Propagation Tests

These tests ensure that device handlers correctly include MQTT commands in their responses and that these commands are properly propagated through `execute_action()` to the API responses.

```python
async def test_kitchen_hood_mqtt_command_propagation(self, mock_send_rf_code):
    """Test that kitchen hood handler includes mqtt_command in result."""
    # Configure mock
    mock_send_rf_code.return_value = True
    
    # Create a real KitchenHood device with mocked config and client
    device = BroadlinkKitchenHood(self.hood_config, self.mock_mqtt_client)
    
    # Execute action
    cmd_config = StandardCommandConfig(action="set_light")
    params = {"state": "on"}
    result = await device.handle_set_light(cmd_config, params)
    
    # Verify result includes mqtt_command
    self.assertTrue("mqtt_command" in result)
    mqtt_command = result.get("mqtt_command")
    self.assertIsInstance(mqtt_command, dict)
    
    # Verify action propagates through execute_action
    response = await device.execute_action("set_light", {"state": "on"})
    
    # Verify CommandResponse includes mqtt_command
    self.assertTrue("mqtt_command" in response)
```

### 3. API Response Tests

These tests validate that the API endpoints return properly typed responses, with direct state access (no wrapping) and including MQTT commands when applicable.

```python
def test_get_device_returns_typed_state(self):
    """Test that GET /devices/{device_id} returns properly typed state."""
    # Configure mock
    self.mock_device.get_current_state.return_value = self.mock_state
    
    # Make request
    response = self.client.get("/devices/kitchen_hood")
    
    # Verify response
    self.assertEqual(response.status_code, 200)
    data = response.json()
    
    # Verify it's not wrapped (no 'state' field at the top level)
    self.assertNotIn("state", data)
    
    # Verify fields are directly accessible
    self.assertEqual(data["device_id"], "kitchen_hood")
    self.assertEqual(data["device_name"], "Kitchen Hood")
    self.assertEqual(data["light"], "on")
```

## Running the Tests

To run the integration tests:

```bash
python -m unittest tests/test_integration.py
```

To run a specific test:

```bash
python -m unittest tests.test_integration.TestStateTypePreservation
```

## Test Coverage

The integration tests cover:

1. **Devices**:
   - KitchenHood
   - WirenboardIR

2. **API Endpoints**:
   - GET /devices/{device_id}
   - POST /devices/{device_id}/action

3. **Type Safety**:
   - State model type preservation
   - CommandResponse structure
   - MQTT command inclusion

## Success Criteria

The integration tests successfully verify that:

1. ✅ Device states are properly typed with specific state classes
2. ✅ CommandResponse is generic and preserves specific state types
3. ✅ Concrete state types are preserved through update_state()
4. ✅ HTTP endpoints return properly typed responses
5. ✅ MQTT commands propagate correctly through the system

These tests ensure that the application layer changes maintain type safety and correct behavior throughout the system. 