from typing import Protocol, Optional, Dict, Any, List
import json
import aiosqlite
import logging
from pathlib import Path
from datetime import datetime

from wb_mqtt_bridge.domain.ports import StateRepositoryPort

logger = logging.getLogger(__name__)

class StateStore(Protocol):
    """Protocol defining the interface for state persistence."""
    
    async def initialize(self) -> None:
        """Initialize database connection and create necessary tables."""
        ...
        
    async def close(self) -> None:
        """Close database connection and release resources."""
        ...
        
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Return the JSON-loaded dict for `key`, or None if missing."""
        ...
        
    async def set(self, key: str, value: Dict[str, Any]) -> None:
        """Persist `value` as JSON under `key`. Overwrite if exists."""
        ...
        
    async def delete(self, key: str) -> None:
        """Remove the persisted entry for `key`, if any."""
        ...


class SQLiteStateStore(StateRepositoryPort):
    """
    Implements StateStore using an SQLite database for JSON blobs.
    Table schema:
      - key TEXT PRIMARY KEY
      - timestamp TEXT NOT NULL (format: 'DD-MM-YYYY HH:MM:SS')
      - value TEXT NOT NULL (JSON-encoded)
    """
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None
        self._closing = False  # Flag to indicate the connection is being closed

    async def initialize(self) -> None:
        """Open database connection and create table if needed."""
        try:
            # Ensure parent directory exists
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            
            self.connection = await aiosqlite.connect(self.db_path)
            await self.connection.execute(
                '''
                CREATE TABLE IF NOT EXISTS state_store (
                  key TEXT PRIMARY KEY,
                  timestamp TEXT NOT NULL,
                  value TEXT NOT NULL
                )
                '''
            )
            await self.connection.commit()
            logger.info(f"SQLite state store initialized at {self.db_path}")
        except aiosqlite.Error as e:
            logger.critical(f"SQLite error during initialization: {e}")
            raise RuntimeError(f"Failed to initialize database: {e}")

    async def close(self) -> None:
        """Close database connection."""
        if self.connection:
            self._closing = True
            logger.info("Closing SQLite state store connection")
            try:
                await self.connection.close()
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")
            finally:
                self.connection = None
                self._closing = False

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Return the JSON-loaded dict for `key`, or None if missing."""
        if not self.connection:
            logger.error("Database connection not initialized during get operation")
            return None
            
        if self._closing:
            logger.warning(f"Attempted to get key '{key}' while database is closing")
            return None
            
        try:
            cursor = await self.connection.execute(
                'SELECT value, timestamp FROM state_store WHERE key = ?', (key,)
            )
            row = await cursor.fetchone()
            await cursor.close()
            
            if not row:
                return None
                
            value_data = json.loads(row[0])
            timestamp = row[1]
            
            # Add timestamp to the returned data
            if isinstance(value_data, dict):
                value_data['_timestamp'] = timestamp
                
            return value_data
        except aiosqlite.Error as e:
            logger.error(f"SQLite error during get operation for key '{key}': {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for key '{key}': {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during get operation for key '{key}': {e}")
            return None

    async def set(self, key: str, value: Dict[str, Any]) -> bool:
        """
        Persist `value` as JSON under `key`. Overwrite if exists.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connection:
            logger.error("Database connection not initialized during set operation")
            return False
            
        if self._closing:
            logger.warning(f"Attempted to set key '{key}' while database is closing")
            return False
            
        try:
            # Generate current timestamp in 'DD-MM-YYYY HH:MM:SS' format
            timestamp = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
            
            text = json.dumps(value)
            await self.connection.execute(
                '''
                INSERT INTO state_store (key, timestamp, value)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET 
                    timestamp = excluded.timestamp,
                    value = excluded.value
                ''',
                (key, timestamp, text)
            )
            await self.connection.commit()
            return True
        except aiosqlite.Error as e:
            logger.error(f"SQLite error during set operation for key '{key}': {e}")
            return False
        except json.JSONEncodeError as e:
            logger.error(f"JSON encode error for key '{key}': {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during set operation for key '{key}': {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Remove the persisted entry for `key`, if any.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connection:
            logger.error("Database connection not initialized during delete operation")
            return False
            
        if self._closing:
            logger.warning(f"Attempted to delete key '{key}' while database is closing")
            return False
            
        try:
            await self.connection.execute('DELETE FROM state_store WHERE key = ?', (key,))
            await self.connection.commit()
            return True
        except aiosqlite.Error as e:
            logger.error(f"SQLite error during delete operation for key '{key}': {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during delete operation for key '{key}': {e}")
            return False
    
    # StateRepositoryPort interface implementation
    async def load(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Load state for an entity by ID."""
        return await self.get(entity_id)
    
    async def save(self, entity_id: str, state: Dict[str, Any]) -> None:
        """Save state for an entity."""
        await self.set(entity_id, state)
    
    async def bulk_save(self, states: Dict[str, Dict[str, Any]]) -> None:
        """Save multiple entity states in a single operation."""
        for entity_id, state in states.items():
            await self.save(entity_id, state)
    
    async def list_entities(self) -> List[str]:
        """List all entity IDs that have persisted state."""
        if not self.connection:
            logger.error("Database connection not initialized")
            return []
            
        try:
            cursor = await self.connection.execute('SELECT key FROM state_store')
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
        except aiosqlite.Error as e:
            logger.error(f"SQLite error during list_entities operation: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error during list_entities operation: {e}")
            return [] 