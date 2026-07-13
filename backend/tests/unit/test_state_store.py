import pytest
import pytest_asyncio


# Import the mock_sqlite module first to handle SQLite issues
from tests import mock_sqlite

# Skip all tests if aiosqlite is not available
if not mock_sqlite.HAS_AIOSQLITE:
    pytest.skip("aiosqlite is not available", allow_module_level=True)

from locveil_bridge.infrastructure.persistence.sqlite import SQLiteStateStore

pytestmark = pytest.mark.integration


def _without_timestamp(d):
    """SQLiteStateStore.get() adds a '_timestamp' to returned dicts; strip it for equality checks."""
    return {k: v for k, v in d.items() if k != "_timestamp"}


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
    """Test that set() followed by get() returns the original dict (plus a _timestamp)."""
    test_data = {"name": "test", "value": 42, "nested": {"key": "value"}}

    await test_db.set("test_key", test_data)
    result = await test_db.get("test_key")

    # Original payload must round-trip; get() additionally annotates _timestamp.
    assert _without_timestamp(result) == test_data
    assert "_timestamp" in result
    assert result["name"] == "test"
    assert result["value"] == 42
    assert result["nested"]["key"] == "value"


@pytest.mark.asyncio
async def test_delete(test_db):
    """Test that delete() removes a key."""
    test_data = {"name": "to_be_deleted"}
    await test_db.set("delete_key", test_data)

    result = await test_db.get("delete_key")
    assert result is not None

    await test_db.delete("delete_key")

    result = await test_db.get("delete_key")
    assert result is None


@pytest.mark.asyncio
async def test_update_existing(test_db):
    """Test that set() updates existing keys."""
    initial_data = {"name": "initial", "value": 1}
    await test_db.set("update_key", initial_data)

    updated_data = {"name": "updated", "value": 2, "new_field": True}
    await test_db.set("update_key", updated_data)

    result = await test_db.get("update_key")

    assert _without_timestamp(result) == updated_data
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

    await test_db.set("complex_key", complex_data)
    result = await test_db.get("complex_key")

    assert _without_timestamp(result) == complex_data
    assert result["nested_dict"]["c"]["e"][0]["f"] == "complex"


@pytest.mark.asyncio
async def test_load_save_aliases(test_db):
    """Test the StateRepositoryPort interface methods load()/save() (introduced after this test was first written)."""
    payload = {"x": 1}
    await test_db.save("entity_1", payload)
    result = await test_db.load("entity_1")
    assert _without_timestamp(result) == payload


@pytest.mark.asyncio
async def test_list_entities(test_db):
    """Test that list_entities() returns all persisted keys."""
    await test_db.set("a", {"v": 1})
    await test_db.set("b", {"v": 2})
    entities = await test_db.list_entities()
    assert set(entities) == {"a", "b"}
