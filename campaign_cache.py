"""
Campaign Cache - SQLite-backed caching for Brevo email events
Reduces API calls and provides historical campaign tracking
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class BrevoCache:
    """SQLite-backed cache for Brevo email events and campaigns."""
    
    def __init__(self, db_path: str = "./data/campaign_cache.db", cache_ttl_minutes: int = 15):
        """
        Initialize the cache.
        
        Args:
            db_path: Path to SQLite database file
            cache_ttl_minutes: How long cached data is considered fresh (default: 15 minutes)
        """
        self.db_path = db_path
        self.cache_ttl_minutes = cache_ttl_minutes
        
        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
        
    def _init_database(self):
        """Create database tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Email events table - stores individual event records
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS email_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL,
                    campaign_batch_id TEXT NOT NULL,
                    email TEXT NOT NULL,
                    subject TEXT,
                    tag TEXT,
                    event_type TEXT NOT NULL,
                    event_date TEXT NOT NULL,
                    link TEXT,
                    reason TEXT,
                    cached_at TEXT NOT NULL,
                    UNIQUE(message_id, event_type, event_date)
                )
            """)
            
            # Campaign metadata table - stores batch-level information
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS campaigns (
                    campaign_batch_id TEXT PRIMARY KEY,
                    subject TEXT,
                    tag TEXT,
                    send_date TEXT NOT NULL,
                    total_recipients INTEGER DEFAULT 0,
                    total_delivered INTEGER DEFAULT 0,
                    total_opened INTEGER DEFAULT 0,
                    total_clicks INTEGER DEFAULT 0,
                    total_bounces INTEGER DEFAULT 0,
                    last_updated TEXT NOT NULL
                )
            """)
            
            # Cache metadata table - tracks when data was last fetched
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Create indices for fast queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_message_id 
                ON email_events(message_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_campaign_batch 
                ON email_events(campaign_batch_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_date 
                ON email_events(event_date)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_campaigns_send_date 
                ON campaigns(send_date)
            """)
            
            conn.commit()
            logger.info(f"Cache database initialized at {self.db_path}")
    
    def is_cache_fresh(self, start_date: datetime, end_date: datetime) -> bool:
        """
        Check if cached data for a date range is fresh enough.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            True if cache is fresh, False if needs refresh
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check when this date range was last fetched
                cache_key = f"fetch_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
                cursor.execute("""
                    SELECT updated_at FROM cache_metadata WHERE key = ?
                """, (cache_key,))
                
                result = cursor.fetchone()
                if not result:
                    return False
                
                last_updated = datetime.fromisoformat(result[0])
                age_minutes = (datetime.now(timezone.utc) - last_updated).total_seconds() / 60
                
                is_fresh = age_minutes < self.cache_ttl_minutes
                logger.info(f"Cache for {cache_key}: age={age_minutes:.1f}min, fresh={is_fresh}")
                return is_fresh
                
        except Exception as e:
            logger.error(f"Error checking cache freshness: {e}")
            return False
    
    def get_cached_events(
        self, 
        start_date: datetime, 
        end_date: datetime,
        email: Optional[str] = None,
        event_type: Optional[str] = None
    ) -> Tuple[List[Dict], int]:
        """
        Retrieve cached events for a date range.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            email: Optional email filter
            event_type: Optional event type filter
            
        Returns:
            Tuple of (list of event dicts, total count)
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Build query with filters
                query = """
                    SELECT message_id, campaign_batch_id, email, subject, tag, 
                           event_type, event_date, link, reason
                    FROM email_events
                    WHERE event_date >= ? AND event_date <= ?
                """
                params = [start_date.isoformat(), end_date.isoformat()]
                
                if email:
                    query += " AND email = ?"
                    params.append(email)
                
                if event_type:
                    query += " AND event_type = ?"
                    params.append(event_type)
                
                query += " ORDER BY event_date DESC"
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                # Convert to dict format matching Brevo API response
                events = []
                for row in rows:
                    event = {
                        "message_id": row[0],
                        "campaign_batch_id": row[1],
                        "email": row[2],
                        "subject": row[3] or "",
                        "tag": row[4] or "",
                        "event": row[5],
                        "date": row[6],
                        "link": row[7] or "",
                        "reason": row[8] or ""
                    }
                    events.append(event)
                
                logger.info(f"Retrieved {len(events)} cached events from {start_date} to {end_date}")
                return events, len(events)
                
        except Exception as e:
            logger.error(f"Error retrieving cached events: {e}")
            return [], 0
    
    def store_events(self, events: List[Dict], campaign_batch_extractor) -> int:
        """
        Store events in cache.
        
        Args:
            events: List of event dicts from Brevo API
            campaign_batch_extractor: Function to extract campaign batch ID from message_id
            
        Returns:
            Number of events stored
        """
        if not events:
            return 0
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cached_at = datetime.now(timezone.utc).isoformat()
                stored_count = 0
                
                for event in events:
                    message_id = event.get("message_id", "")
                    if not message_id:
                        continue
                    
                    campaign_batch_id = campaign_batch_extractor(message_id)
                    
                    # Insert or ignore (duplicate protection)
                    cursor.execute("""
                        INSERT OR IGNORE INTO email_events
                        (message_id, campaign_batch_id, email, subject, tag, 
                         event_type, event_date, link, reason, cached_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        message_id,
                        campaign_batch_id,
                        event.get("email", ""),
                        event.get("subject", ""),
                        event.get("tag", ""),
                        event.get("event", ""),
                        event.get("date", ""),
                        event.get("link", ""),
                        event.get("reason", ""),
                        cached_at
                    ))
                    
                    if cursor.rowcount > 0:
                        stored_count += 1
                
                conn.commit()
                logger.info(f"Stored {stored_count} new events in cache (out of {len(events)} total)")
                return stored_count
                
        except Exception as e:
            logger.error(f"Error storing events in cache: {e}")
            return 0
    
    def update_cache_metadata(self, start_date: datetime, end_date: datetime):
        """Update metadata to mark this date range as freshly cached."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cache_key = f"fetch_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
                updated_at = datetime.now(timezone.utc).isoformat()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO cache_metadata (key, value, updated_at)
                    VALUES (?, ?, ?)
                """, (cache_key, "fetched", updated_at))
                
                conn.commit()
                logger.info(f"Updated cache metadata for {cache_key}")
                
        except Exception as e:
            logger.error(f"Error updating cache metadata: {e}")
    
    def get_campaign_summary(
        self, 
        start_date: datetime, 
        end_date: datetime,
        use_send_date: bool = True
    ) -> List[Dict]:
        """
        Get aggregated campaign summaries from cache.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            use_send_date: If True, filter by campaign send_date; if False, by any event activity
            
        Returns:
            List of campaign summary dicts
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if use_send_date:
                    # Filter by campaign send date (when campaign was actually sent)
                    query = """
                        SELECT c.campaign_batch_id, c.subject, c.tag, c.send_date,
                               c.total_recipients, c.total_delivered, c.total_opened,
                               c.total_clicks, c.total_bounces
                        FROM campaigns c
                        WHERE c.send_date >= ? AND c.send_date <= ?
                        ORDER BY c.send_date DESC
                    """
                else:
                    # Filter by any event activity in range (old behavior)
                    query = """
                        SELECT DISTINCT c.campaign_batch_id, c.subject, c.tag, c.send_date,
                               c.total_recipients, c.total_delivered, c.total_opened,
                               c.total_clicks, c.total_bounces
                        FROM campaigns c
                        JOIN email_events e ON c.campaign_batch_id = e.campaign_batch_id
                        WHERE e.event_date >= ? AND e.event_date <= ?
                        ORDER BY c.send_date DESC
                    """
                
                cursor.execute(query, [start_date.isoformat(), end_date.isoformat()])
                rows = cursor.fetchall()
                
                campaigns = []
                for row in rows:
                    campaigns.append({
                        "campaign_batch_id": row[0],
                        "subject": row[1],
                        "tag": row[2],
                        "send_date": row[3],
                        "total_recipients": row[4],
                        "total_delivered": row[5],
                        "total_opened": row[6],
                        "total_clicks": row[7],
                        "total_bounces": row[8]
                    })
                
                return campaigns
                
        except Exception as e:
            logger.error(f"Error getting campaign summary: {e}")
            return []
    
    def clear_old_cache(self, days: int = 90):
        """
        Clear cached events older than specified days.
        
        Args:
            days: Keep events from last N days, delete older
        """
        try:
            cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    DELETE FROM email_events WHERE event_date < ?
                """, (cutoff_date,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                logger.info(f"Cleared {deleted_count} events older than {days} days")
                
        except Exception as e:
            logger.error(f"Error clearing old cache: {e}")


# Global cache instance
_cache_instance = None


def get_cache(db_path: str = "./data/campaign_cache.db", cache_ttl_minutes: int = 15) -> BrevoCache:
    """Get or create the global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = BrevoCache(db_path, cache_ttl_minutes)
    return _cache_instance
