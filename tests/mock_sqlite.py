import sys
import importlib.util

# Check if native sqlite3 module works
try:
    import sqlite3
    sqlite3.connect(":memory:")
    HAS_SQLITE = True
except (ImportError, AttributeError):
    HAS_SQLITE = False

# If native sqlite3 doesn't work, try to use pysqlite3-binary
if not HAS_SQLITE:
    try:
        import pysqlite3
        # Replace the sqlite3 module with pysqlite3
        sys.modules['sqlite3'] = pysqlite3
        print("Using pysqlite3 as a replacement for sqlite3")
    except ImportError:
        print("Warning: Neither sqlite3 nor pysqlite3 is available. SQLite-based tests will fail.")

# Now import aiosqlite (which will use either native sqlite3 or our patched version)
try:
    import aiosqlite
    HAS_AIOSQLITE = True
except ImportError:
    HAS_AIOSQLITE = False
    print("Warning: aiosqlite is not available. SQLite-based tests will fail.") 