"""
Database Connection Pool Manager
Provides connection pooling and context manager support for SQLite
"""
import sqlite3
import threading
from contextlib import contextmanager
from typing import Optional, Iterator
from queue import Queue, Empty

class DatabasePool:
    """Simple connection pool for SQLite"""
    
    def __init__(self, db_path: str, max_connections: int = 5):
        self.db_path = db_path
        self.max_connections = max_connections
        self._pool: Queue = Queue(maxsize=max_connections)
        self._lock = threading.Lock()
        self._created = 0
        # Pre-populate pool with initial connections
        for _ in range(min(2, max_connections)):
            try:
                conn = self._create_connection()
                self._pool.put_nowait(conn)
                self._created += 1
            except:
                pass  # If pre-population fails, connections will be created on demand
        
    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrency
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=30000')  # 30 second timeout
        # Optimize for read-heavy workloads
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.execute('PRAGMA cache_size=-64000')  # 64MB cache
        return conn
    
    def get_connection(self) -> sqlite3.Connection:
        """Get a connection from the pool"""
        try:
            # Try to get existing connection from pool
            conn = self._pool.get_nowait()
            # Check if connection is still valid
            try:
                conn.execute('SELECT 1')
                return conn
            except sqlite3.Error:
                # Connection is dead, create new one
                with self._lock:
                    if self._created < self.max_connections:
                        self._created += 1
                return self._create_connection()
        except Empty:
            # Pool is empty, create new connection if under limit
            with self._lock:
                if self._created < self.max_connections:
                    self._created += 1
                    return self._create_connection()
                else:
                    # Wait for a connection to become available
                    try:
                        return self._pool.get(timeout=30.0)
                    except Empty:
                        # Still empty after timeout, create one anyway (shouldn't happen normally)
                        with self._lock:
                            if self._created < self.max_connections * 2:  # Allow some overflow
                                self._created += 1
                                return self._create_connection()
                            else:
                                raise RuntimeError("Connection pool exhausted and no connections available")
    
    def return_connection(self, conn: sqlite3.Connection) -> None:
        """Return a connection to the pool"""
        try:
            # Reset connection state
            conn.rollback()
            self._pool.put_nowait(conn)
        except:
            # Pool is full or connection is bad, close it
            try:
                conn.close()
            except:
                pass
            with self._lock:
                self._created -= 1
    
    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Context manager for database connections"""
        conn = self.get_connection()
        try:
            yield conn
        finally:
            self.return_connection(conn)
    
    def close_all(self) -> None:
        """Close all connections in the pool"""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except:
                pass
        self._created = 0

# Global pool instance (will be initialized in database.py)
_pool: Optional[DatabasePool] = None

def init_pool(db_path: str, max_connections: int = 5) -> DatabasePool:
    """Initialize the global connection pool"""
    global _pool
    _pool = DatabasePool(db_path, max_connections)
    return _pool

def get_pool() -> Optional[DatabasePool]:
    """Get the global connection pool"""
    return _pool
