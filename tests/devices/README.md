# Device Testing

This directory contains tests for device implementations.

## Running the Tests

To run all tests:

```bash
pytest tests/devices/
```

To run a specific test file:

```bash
pytest tests/devices/test_auralic_device.py
```

To run a specific test:

```bash
pytest tests/devices/test_auralic_device.py::TestAuralicDevice::test_handle_power_on
```

## Test Coverage

The tests verify:

1. Device initialization and setup
2. Command handling
3. Update task behavior and cancellation
4. Error handling

### Current Coverage

For Auralic device, the current test coverage is 56%, with 270 statements and 120 missing.

```bash
# Run coverage report
pytest tests/devices/test_auralic_device.py tests/devices/test_auralic_update_task.py --cov=devices.auralic_device --cov-report term-missing
```

#### Areas for Improvement

The following areas could use additional test coverage:

1. More command handlers (power_toggle, pause, stop, next, previous, volume_up, volume_down, track_info)
2. Edge case handling in various methods
3. Discovery mode testing with more complex scenarios
4. Error conditions in device setup and update

## Auralic Device Tests

The Auralic device tests are split into two files:

- `test_auralic_device.py` - Tests for general functionality
- `test_auralic_update_task.py` - Specific tests for the update task behavior

The update task tests specifically verify that:
- The task runs at the specified interval
- The task handles errors gracefully and continues running
- The task properly terminates when cancelled during shutdown

## Adding New Tests

When adding new device tests, follow these patterns:

1. Use pytest fixtures for setup
2. Use AsyncMock for mocking async methods
3. Properly test both success and error scenarios
4. Test cancellation behavior for long-running tasks

## Test Dependencies

Required dependencies for testing are in `tests/requirements-test.txt`:

```bash
# Install test dependencies
pip install -r tests/requirements-test.txt
```

Main dependencies:
- pytest
- pytest-asyncio
- pytest-cov 