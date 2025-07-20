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


@pytest.mark.asyncio
async def test_connection_error_handling():
    """Test that the SQLiteStateStore handles connection errors correctly."""
    # Mock aiosqlite.connect to raise an exception
    with patch('aiosqlite.connect') as mock_connect:
        mock_connect.side_effect = aiosqlite.Error("Simulated connection error")
        
        # Create SQLiteStateStore with non-existent path
        store = SQLiteStateStore(db_path="non_existent_path.db")
        
        # Call initialize, which should exit the application
        with pytest.raises(SystemExit):
            await store.initialize()


@pytest_asyncio.fixture
async def initialized_store():
    """Create and initialize a store for testing."""
    store = SQLiteStateStore(db_path=":memory:")
    await store.initialize()
    try:
        yield store
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_get_error_handling(initialized_store):
    """Test that get() handles database errors correctly."""
    # Replace the connection with a mock that raises an exception
    initialized_store.connection = AsyncMock()
    initialized_store.connection.execute.side_effect = aiosqlite.Error("Simulated query error")
    
    # Call get, which should exit the application
    with pytest.raises(SystemExit):
        await initialized_store.get("test_key")


@pytest.mark.asyncio
async def test_set_error_handling(initialized_store):
    """Test that set() handles database errors correctly."""
    # Replace the connection with a mock that raises an exception
    initialized_store.connection = AsyncMock()
    initialized_store.connection.execute.side_effect = aiosqlite.Error("Simulated insert error")
    
    # Call set, which should exit the application
    with pytest.raises(SystemExit):
        await initialized_store.set("test_key", {"value": "test"})


@pytest.mark.asyncio
async def test_delete_error_handling(initialized_store):
    """Test that delete() handles database errors correctly."""
    # Replace the connection with a mock that raises an exception
    initialized_store.connection = AsyncMock()
    initialized_store.connection.execute.side_effect = aiosqlite.Error("Simulated delete error")
    
    # Call delete, which should exit the application
    with pytest.raises(SystemExit):
        await initialized_store.delete("test_key")


@pytest.mark.asyncio
async def test_connection_not_initialized():
    """Test that operations fail properly when connection isn't initialized."""
    # Create a store without initializing
    store = SQLiteStateStore(db_path=":memory:")
    
    # Try to perform operations without initializing
    with pytest.raises(RuntimeError, match="Database connection not initialized"):
        await store.get("test_key")
    
    with pytest.raises(RuntimeError, match="Database connection not initialized"):
        await store.set("test_key", {"value": "test"})
    
    with pytest.raises(RuntimeError, match="Database connection not initialized"):
        await store.delete("test_key") 