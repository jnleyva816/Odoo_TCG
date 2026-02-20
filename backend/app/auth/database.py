"""SQLite database for authentication."""

from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite

# Database path - store in /data for Docker persistence
DB_PATH = Path("/data/auth.db") if Path("/data").exists() else Path("auth.db")


async def init_db():
    """Initialize database tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Users table with warehouse support
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                is_active BOOLEAN DEFAULT 1,
                warehouse_id INTEGER,
                warehouse_ids TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        """
        )

        # Migration: Add warehouse columns if they don't exist
        try:
            await db.execute("ALTER TABLE users ADD COLUMN warehouse_id INTEGER")
        except Exception:
            pass  # Column already exists

        try:
            await db.execute("ALTER TABLE users ADD COLUMN warehouse_ids TEXT")
        except Exception:
            pass  # Column already exists

        # Login attempts table (for security monitoring)
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                success BOOLEAN NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Sessions table (for token invalidation)
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                revoked BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """
        )

        await db.commit()


async def get_user_by_username(username: str) -> dict[str, Any] | None:
    """Get user by username."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_user_by_email(email: str) -> dict[str, Any] | None:
    """Get user by email."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    """Get user by ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def create_user(
    username: str,
    email: str,
    hashed_password: str,
    role: str = "user",
    warehouse_id: int | None = None,
    warehouse_ids: list[int] | None = None,
) -> int:
    """Create a new user."""
    import json

    warehouse_ids_json = json.dumps(warehouse_ids) if warehouse_ids else None

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO users (username, email, hashed_password, role, warehouse_id, warehouse_ids)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (username, email, hashed_password, role, warehouse_id, warehouse_ids_json),
        )
        await db.commit()
        return cursor.lastrowid or 0


async def update_user_warehouse(user_id: int, warehouse_id: int) -> bool:
    """Update user's active warehouse."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET warehouse_id = ? WHERE id = ?",
            (warehouse_id, user_id),
        )
        await db.commit()
        return True


async def update_user_warehouse_ids(user_id: int, warehouse_ids: list[int]) -> bool:
    """Update user's allowed warehouse IDs (for admins)."""
    import json

    warehouse_ids_json = json.dumps(warehouse_ids)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET warehouse_ids = ? WHERE id = ?",
            (warehouse_ids_json, user_id),
        )
        await db.commit()
        return True


async def get_all_users() -> list[dict[str, Any]]:
    """Get all users (admin only)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT id, username, email, role, is_active, warehouse_id,
            warehouse_ids, created_at, last_login FROM users ORDER BY username"""
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def update_last_login(user_id: int):
    """Update user's last login timestamp."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (datetime.utcnow(), user_id),
        )
        await db.commit()


async def log_login_attempt(
    username: str,
    ip_address: str,
    user_agent: str,
    success: bool,
):
    """Log a login attempt."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO login_attempts (username, ip_address, user_agent, success)
            VALUES (?, ?, ?, ?)
            """,
            (username, ip_address, user_agent, success),
        )
        await db.commit()


async def get_failed_attempts(username: str, since_minutes: int = 15) -> int:
    """Get number of failed login attempts in the last N minutes."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT COUNT(*) as count FROM login_attempts
            WHERE username = ?
            AND success = 0
            AND timestamp > datetime('now', ?)
            """,
            (username, f"-{since_minutes} minutes"),
        )
        row = await cursor.fetchone()
        return row["count"] if row else 0


async def get_recent_login_attempts(limit: int = 50) -> list[dict[str, Any]]:
    """Get recent login attempts (for admin dashboard)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM login_attempts
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_user_count() -> int:
    """Get total number of users."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT COUNT(*) as count FROM users")
        row = await cursor.fetchone()
        return row["count"] if row else 0
