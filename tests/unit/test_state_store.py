import os
import sys
import pytest
import pytest_asyncio

# Add the app directory to sys.path for importing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Import the mock_sqlite module first to handle SQLite issues
from tests import mock_sqlite

# Skip all tests if aiosqlite is not available
if not mock_sqlite.HAS_AIOSQLITE:
    pytest.skip("aiosqlite is not available", allow_module_level=True)

from wb_mqtt_bridge.infrastructure.persistence.sqlite import SQLiteStateStore


@pytest_asyncio.fixture
async def test_db():
    """Create an in-memory database for testing."""
    store = SQLiteStateStore(db_path=":memory:")
    await store.initialize()
    try:
        yield store
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_get_missing_key(test_db):
    """Test that get() returns None for missing keys."""
    result = await test_db.get("non_existent_key")
    assert result is None


@pytest.mark.asyncio
async def test_set_and_get(test_db):
    """Test that set() followed by get() returns the original dict."""
    test_data = {"name": "test", "value": 42, "nested": {"key": "value"}}
    
    # Set the data
    await test_db.set("test_key", test_data)
    
    # Get the data
    result = await test_db.get("test_key")
    
    # Verify the result
    assert result == test_data
    assert result["name"] == "test"
    assert result["value"] == 42
    assert result["nested"]["key"] == "value"


@pytest.mark.asyncio
async def test_delete(test_db):
    """Test that delete() removes a key."""
    # Set some data
    test_data = {"name": "to_be_deleted"}
    await test_db.set("delete_key", test_data)
    
    # Verify it exists
    result = await test_db.get("delete_key")
    assert result is not None
    
    # Delete it
    await test_db.delete("delete_key")
    
    # Verify it's gone
    result = await test_db.get("delete_key")
    assert result is None


@pytest.mark.asyncio
async def test_update_existing(test_db):
    """Test that set() updates existing keys."""
    # Set initial data
    initial_data = {"name": "initial", "value": 1}
    await test_db.set("update_key", initial_data)
    
    # Update with new data
    updated_data = {"name": "updated", "value": 2, "new_field": True}
    await test_db.set("update_key", updated_data)
    
    # Get the data
    result = await test_db.get("update_key")
    
    # Verify the update
    assert result == updated_data
    assert result["name"] == "updated"
    assert result["value"] == 2
    assert result["new_field"] is True


@pytest.mark.asyncio
async def test_complex_data_serialization(test_db):
    """Test that complex nested data structures are preserved."""
    complex_data = {
        "string": "text",
        "integer": 42,
        "float": 3.14,
        "boolean": True,
        "null_value": None,
        "list": [1, 2, 3],
        "nested_dict": {
            "a": 1,
            "b": [4, 5, 6],
            "c": {
                "d": "nested",
                "e": [{"f": "complex"}]
            }
        }
    }
    
    # Set the complex data
    await test_db.set("complex_key", complex_data)
    
    # Get the data
    result = await test_db.get("complex_key")
    
    # Verify full equality
    assert result == complex_data
    
    # Verify specific nested fields
    assert result["nested_dict"]["c"]["e"][0]["f"] == "complex" 