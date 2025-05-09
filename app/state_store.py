from typing import Protocol, Optional, Dict, Any
import json
import aiosqlite
import asyncio
import sys
from pathlib import Path


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


class SQLiteStateStore:
    """
    Implements StateStore using an SQLite database for JSON blobs.
    Table schema:
      - key TEXT PRIMARY KEY
      - value TEXT NOT NULL (JSON-encoded)
    """
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None

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
                  value TEXT NOT NULL
                )
                '''
            )
            await self.connection.commit()
        except aiosqlite.Error as e:
            print(f"Critical SQLite error during initialization: {e}", file=sys.stderr)
            sys.exit(1)

    async def close(self) -> None:
        """Close database connection."""
        if self.connection:
            await self.connection.close()
            self.connection = None

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Return the JSON-loaded dict for `key`, or None if missing."""
        if not self.connection:
            raise RuntimeError("Database connection not initialized")
            
        try:
            cursor = await self.connection.execute(
                'SELECT value FROM state_store WHERE key = ?', (key,)
            )
            row = await cursor.fetchone()
            await cursor.close()
            return json.loads(row[0]) if row else None
        except aiosqlite.Error as e:
            print(f"Critical SQLite error during get operation: {e}", file=sys.stderr)
            sys.exit(1)

    async def set(self, key: str, value: Dict[str, Any]) -> None:
        """Persist `value` as JSON under `key`. Overwrite if exists."""
        if not self.connection:
            raise RuntimeError("Database connection not initialized")
            
        try:
            text = json.dumps(value)
            await self.connection.execute(
                '''
                INSERT INTO state_store (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                ''',
                (key, text)
            )
            await self.connection.commit()
        except aiosqlite.Error as e:
            print(f"Critical SQLite error during set operation: {e}", file=sys.stderr)
            sys.exit(1)

    async def delete(self, key: str) -> None:
        """Remove the persisted entry for `key`, if any."""
        if not self.connection:
            raise RuntimeError("Database connection not initialized")
            
        try:
            await self.connection.execute('DELETE FROM state_store WHERE key = ?', (key,))
            await self.connection.commit()
        except aiosqlite.Error as e:
            print(f"Critical SQLite error during delete operation: {e}", file=sys.stderr)
            sys.exit(1) 