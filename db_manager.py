import os
import logging
import sqlite3
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import aiosqlite

logger = logging.getLogger(__name__)

class DatabaseManager:
    """SQLite database manager for the Calendar AI Agent"""
    
    def __init__(self, db_path: str = "calendar_agent.db"):
        self.db_path = db_path
        self.initialized = False
    
    async def initialize(self):
        """Initialize the database and create tables if they don't exist"""
        try:
            # Create the database directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
            
            async with aiosqlite.connect(self.db_path) as db:
                # Enable foreign keys
                await db.execute("PRAGMA foreign_keys = ON")
                
                # Create users table
                await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    email TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                
                # Create calendars table
                await db.execute("""
                CREATE TABLE IF NOT EXISTS calendars (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    name TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    provider_id TEXT,
                    color TEXT,
                    is_primary BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
                """)
                
                # Create tokens table
                await db.execute("""
                CREATE TABLE IF NOT EXISTS tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    provider TEXT NOT NULL,
                    access_token TEXT,
                    refresh_token TEXT,
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
                """)
                
                # Create settings table
                await db.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    key TEXT NOT NULL,
                    value TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    UNIQUE(user_id, key)
                )
                """)
                
                # Create activity_log table
                await db.execute("""
                CREATE TABLE IF NOT EXISTS activity_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action_type TEXT NOT NULL,
                    description TEXT,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
                """)
                
                await db.commit()
            
            self.initialized = True
            logger.info("Database initialized successfully")
            return True
        
        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
            return False
    
    async def get_user(self, email: str) -> Optional[Dict[str, Any]]:
        """Get a user by email"""
        if not self.initialized:
            await self.initialize()
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = sqlite3.Row
                async with db.execute(
                    "SELECT * FROM users WHERE email = ?",
                    (email,)
                ) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        return dict(row)
                    return None
        
        except Exception as e:
            logger.error(f"Error getting user: {str(e)}")
            return None
    
    async def create_user(self, name: str, email: str) -> Optional[int]:
        """Create a new user"""
        if not self.initialized:
            await self.initialize()
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "INSERT INTO users (name, email) VALUES (?, ?)",
                    (name, email)
                )
                await db.commit()
                return cursor.lastrowid
        
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            return None
    
    async def get_calendars(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all calendars for a user"""
        if not self.initialized:
            await self.initialize()
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = sqlite3.Row
                async with db.execute(
                    "SELECT * FROM calendars WHERE user_id = ?",
                    (user_id,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        
        except Exception as e:
            logger.error(f"Error getting calendars: {str(e)}")
            return []
    
    async def add_calendar(self, calendar_data: Dict[str, Any]) -> bool:
        """Add a new calendar for a user"""
        if not self.initialized:
            await self.initialize()
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO calendars 
                    (id, user_id, name, provider, provider_id, color, is_primary) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        calendar_data.get('id'),
                        calendar_data.get('user_id'),
                        calendar_data.get('name'),
                        calendar_data.get('provider'),
                        calendar_data.get('provider_id'),
                        calendar_data.get('color'),
                        calendar_data.get('is_primary', 0)
                    )
                )
                await db.commit()
                return True
        
        except Exception as e:
            logger.error(f"Error adding calendar: {str(e)}")
            return False
    
    async def remove_calendar(self, calendar_id: str) -> bool:
        """Remove a calendar"""
        if not self.initialized:
            await self.initialize()
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "DELETE FROM calendars WHERE id = ?",
                    (calendar_id,)
                )
                await db.commit()
                return True
        
        except Exception as e:
            logger.error(f"Error removing calendar: {str(e)}")
            return False
    
    async def save_token(self, user_id: int, provider: str, tokens: Dict[str, Any]) -> bool:
        """Save authentication tokens for a provider"""
        if not self.initialized:
            await self.initialize()
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Check if token already exists
                async with db.execute(
                    "SELECT id FROM tokens WHERE user_id = ? AND provider = ?",
                    (user_id, provider)
                ) as cursor:
                    existing = await cursor.fetchone()
                
                if existing:
                    # Update existing token
                    await db.execute(
                        """
                        UPDATE tokens 
                        SET access_token = ?, refresh_token = ?, expires_at = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = ? AND provider = ?
                        """,
                        (
                            tokens.get('access_token'),
                            tokens.get('refresh_token'),
                            tokens.get('expires_at'),
                            user_id,
                            provider
                        )
                    )
                else:
                    # Insert new token
                    await db.execute(
                        """
                        INSERT INTO tokens 
                        (user_id, provider, access_token, refresh_token, expires_at) 
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            user_id,
                            provider,
                            tokens.get('access_token'),
                            tokens.get('refresh_token'),
                            tokens.get('expires_at')
                        )
                    )
                
                await db.commit()
                return True
        
        except Exception as e:
            logger.error(f"Error saving token: {str(e)}")
            return False
    
    async def get_token(self, user_id: int, provider: str) -> Optional[Dict[str, Any]]:
        """Get authentication tokens for a provider"""
        if not self.initialized:
            await self.initialize()
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = sqlite3.Row
                async with db.execute(
                    "SELECT * FROM tokens WHERE user_id = ? AND provider = ?",
                    (user_id, provider)
                ) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        return dict(row)
                    return None
        
        except Exception as e:
            logger.error(f"Error getting token: {str(e)}")
            return None
    
    async def save_setting(self, user_id: int, key: str, value: Any) -> bool:
        """Save a user setting"""
        if not self.initialized:
            await self.initialize()
        
        try:
            # Convert value to JSON string if it's not a string
            if not isinstance(value, str):
                value = json.dumps(value)
            
            async with aiosqlite.connect(self.db_path) as db:
                # Check if setting already exists
                async with db.execute(
                    "SELECT id FROM settings WHERE user_id = ? AND key = ?",
                    (user_id, key)
                ) as cursor:
                    existing = await cursor.fetchone()
                
                if existing:
                    # Update existing setting
                    await db.execute(
                        """
                        UPDATE settings 
                        SET value = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = ? AND key = ?
                        """,
                        (value, user_id, key)
                    )
                else:
                    # Insert new setting
                    await db.execute(
                        """
                        INSERT INTO settings 
                        (user_id, key, value) 
                        VALUES (?, ?, ?)
                        """,
                        (user_id, key, value)
                    )
                
                await db.commit()
                return True
        
        except Exception as e:
            logger.error(f"Error saving setting: {str(e)}")
            return False
    
    async def get_setting(self, user_id: int, key: str) -> Optional[Any]:
        """Get a user setting"""
        if not self.initialized:
            await self.initialize()
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT value FROM settings WHERE user_id = ? AND key = ?",
                    (user_id, key)
                ) as cursor:
                    row = await cursor.fetchone()
                    
                    if row and row[0]:
                        # Try to parse as JSON, otherwise return as string
                        try:
                            return json.loads(row[0])
                        except:
                            return row[0]
                    
                    return None
        
        except Exception as e:
            logger.error(f"Error getting setting: {str(e)}")
            return None
    
    async def log_activity(self, user_id: int, action_type: str, description: str, details: Optional[Dict[str, Any]] = None) -> bool:
        """Log user activity"""
        if not self.initialized:
            await self.initialize()
        
        try:
            # Convert details to JSON string if provided
            details_json = json.dumps(details) if details else None
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO activity_log 
                    (user_id, action_type, description, details) 
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_id, action_type, description, details_json)
                )
                await db.commit()
                return True
        
        except Exception as e:
            logger.error(f"Error logging activity: {str(e)}")
            return False
    
    async def get_activity_log(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent activity log for a user"""
        if not self.initialized:
            await self.initialize()
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = sqlite3.Row
                async with db.execute(
                    """
                    SELECT * FROM activity_log 
                    WHERE user_id = ? 
                    ORDER BY created_at DESC 
                    LIMIT ?
                    """,
                    (user_id, limit)
                ) as cursor:
                    rows = await cursor.fetchall()
                    
                    activities = []
                    for row in rows:
                        activity = dict(row)
                        
                        # Parse details JSON if present
                        if activity.get('details'):
                            try:
                                activity['details'] = json.loads(activity['details'])
                            except:
                                pass
                        
                        activities.append(activity)
                    
                    return activities
        
        except Exception as e:
            logger.error(f"Error getting activity log: {str(e)}")
            return []
