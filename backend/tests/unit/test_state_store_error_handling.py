import os
import sys
import pytest
from unittest.mock import patch, AsyncMock
import pytest_asyncio

# Add the app directory to sys.path for importing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Import the mock_sqlite module first to handle SQLite issues
from tests import mock_sqlite

# Import after setting up sys.path
from wb_mqtt_bridge.infrastructure.persistence.sqlite import SQLiteStateStore

# Skip all tests if aiosqlite is not available
if not mock_sqlite.HAS_AIOSQLITE:
    pytest.skip("aiosqlite is not available", allow_module_level=True)

# Import aiosqlite after ensuring it's available
import aiosqlite

pytestmark = pytest.mark.integration


# Production behavior (sqlite.py):
#   - initialize() on driver error -> raises RuntimeError
#   - get/set/delete on driver error -> log and return None / False (never raise / never SystemExit)
#   - get/set/delete on uninitialized connection -> log and return None / False
# These tests verify those error contracts hold so callers can rely on them.


@pytest.mark.asyncio
async def test_initialize_raises_runtime_error_on_connection_failure():
    """initialize() must wrap driver errors as RuntimeError so startup fails loudly."""
    with patch('aiosqlite.connect') as mock_connect:
        mock_connect.side_effect = aiosqlite.Error("Simulated connection error")

        store = SQLiteStateStore(db_path="non_existent_path.db")

        with pytest.raises(RuntimeError, match="Failed to initialize database"):
            await store.initialize()


def _store_with_failing_connection(side_effect_msg: str) -> SQLiteStateStore:
    """Build a SQLiteStateStore whose connection raises aiosqlite.Error on execute().

    We bypass the initialize() / close() lifecycle entirely so test teardown does
    not have to await on a mocked connection (which hangs under pytest-asyncio).
    """
    store = SQLiteStateStore(db_path=":memory:")
    store.connection = AsyncMock()
    store.connection.execute.side_effect = aiosqlite.Error(side_effect_msg)
    return store


@pytest.mark.asyncio
async def test_get_returns_none_on_driver_error():
    """get() swallows driver errors so reads remain non-fatal for callers."""
    store = _store_with_failing_connection("Simulated query error")
    result = await store.get("test_key")
    assert result is None


@pytest.mark.asyncio
async def test_set_returns_false_on_driver_error():
    """set() returns False (does not raise) when the driver reports an error."""
    store = _store_with_failing_connection("Simulated insert error")
    result = await store.set("test_key", {"value": "test"})
    assert result is False


@pytest.mark.asyncio
async def test_delete_returns_false_on_driver_error():
    """delete() returns False (does not raise) when the driver reports an error."""
    store = _store_with_failing_connection("Simulated delete error")
    result = await store.delete("test_key")
    assert result is False


@pytest.mark.asyncio
async def test_uninitialized_connection_safe_defaults():
    """Operations on an uninitialized store log and return safe defaults (None/False)."""
    store = SQLiteStateStore(db_path=":memory:")
    # Note: not calling initialize() — connection stays None.

    assert await store.get("test_key") is None
    assert await store.set("test_key", {"value": "test"}) is False
    assert await store.delete("test_key") is False
