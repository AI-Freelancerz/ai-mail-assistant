"""
Sending Limits Tracker

Tracks daily and hourly email send counts to enforce:
- Warm-up schedule (gradual volume ramp)
- Daily volume limits
- Hourly rate limits

Prevents reputation damage from sudden high-volume sending.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Tuple
import config

logger = logging.getLogger(__name__)


class SendingLimitsTracker:
    """Track and enforce email sending limits"""
    
    def __init__(self, limits_file: str = None):
        self.limits_file = limits_file or config.SENDING_LIMITS_PATH
        self.limits_path = Path(self.limits_file)
        self._ensure_limits_file_exists()
        
    def _ensure_limits_file_exists(self):
        """Create limits file if it doesn't exist"""
        if not self.limits_path.exists():
            self.limits_path.parent.mkdir(parents=True, exist_ok=True)
            initial_data = {
                'domain_verified_date': None,  # Set when domain is verified
                'daily_counts': {},  # {date: count}
                'hourly_counts': {},  # {datetime_hour: count}
            }
            self._save_limits_data(initial_data)
            logger.info(f"Created new sending limits file: {self.limits_path}")
    
    def _load_limits_data(self) -> Dict:
        """Load limits data from file"""
        try:
            with open(self.limits_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading limits data: {e}")
            return {
                'domain_verified_date': None,
                'daily_counts': {},
                'hourly_counts': {},
            }
    
    def _save_limits_data(self, data: Dict):
        """Save limits data to file"""
        try:
            with open(self.limits_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving limits data: {e}")
    
    def get_domain_age_days(self) -> int:
        """
        Get number of days since domain was verified.
        Used to determine warm-up schedule.
        
        Returns:
            Days since verification, or 0 if not set
        """
        data = self._load_limits_data()
        verified_date_str = data.get('domain_verified_date')
        
        if not verified_date_str:
            logger.warning("Domain verified date not set. Set it with set_domain_verified_date()")
            return 0
        
        try:
            verified_date = datetime.fromisoformat(verified_date_str)
            age = (datetime.now() - verified_date).days
            return max(0, age)
        except Exception as e:
            logger.error(f"Error calculating domain age: {e}")
            return 0
    
    def set_domain_verified_date(self, date: datetime = None):
        """
        Set the date when domain was verified in Brevo.
        
        Args:
            date: Verification date (default: today)
        """
        if date is None:
            date = datetime.now()
        
        data = self._load_limits_data()
        data['domain_verified_date'] = date.isoformat()
        self._save_limits_data(data)
        logger.info(f"Set domain verified date to: {date.date()}")
    
    def get_daily_limit(self) -> int:
        """
        Get current daily sending limit based on warm-up schedule.
        
        Returns:
            Maximum emails allowed today
        """
        domain_age_days = self.get_domain_age_days()
        
        # During warm-up period
        if domain_age_days < config.EMAIL_WARMUP_DAYS:
            if domain_age_days < len(config.EMAIL_WARMUP_DAILY_LIMITS):
                limit = config.EMAIL_WARMUP_DAILY_LIMITS[domain_age_days]
                logger.debug(f"Warm-up day {domain_age_days + 1}: limit = {limit}")
                return limit
        
        # After warm-up
        return config.EMAIL_MAX_DAILY_VOLUME
    
    def get_today_send_count(self) -> int:
        """Get number of emails sent today"""
        data = self._load_limits_data()
        today = datetime.now().date().isoformat()
        return data.get('daily_counts', {}).get(today, 0)
    
    def get_this_hour_send_count(self) -> int:
        """Get number of emails sent in current hour"""
        data = self._load_limits_data()
        current_hour = datetime.now().replace(minute=0, second=0, microsecond=0).isoformat()
        return data.get('hourly_counts', {}).get(current_hour, 0)
    
    def get_daily_remaining(self) -> int:
        """Get remaining emails allowed today"""
        daily_limit = self.get_daily_limit()
        today_sent = self.get_today_send_count()
        return max(0, daily_limit - today_sent)
    
    def get_hourly_remaining(self) -> int:
        """Get remaining emails allowed this hour"""
        this_hour_sent = self.get_this_hour_send_count()
        return max(0, config.EMAIL_MAX_HOURLY_VOLUME - this_hour_sent)
    
    def can_send(self, count: int = 1) -> Tuple[bool, str]:
        """
        Check if we can send specified number of emails now.
        
        Args:
            count: Number of emails to send
            
        Returns:
            Tuple of (can_send, reason_message)
        """
        # Check safe send time
        is_safe, time_message = is_safe_send_time()
        if not is_safe:
            return False, time_message
        
        # Check daily limit
        daily_remaining = self.get_daily_remaining()
        if count > daily_remaining:
            domain_age = self.get_domain_age_days()
            daily_limit = self.get_daily_limit()
            today_sent = self.get_today_send_count()
            
            if domain_age < config.EMAIL_WARMUP_DAYS:
                return False, (
                    f"Daily limit reached: {today_sent}/{daily_limit} sent. "
                    f"Warm-up day {domain_age + 1}/{config.EMAIL_WARMUP_DAYS}. "
                    f"Can send {daily_remaining} more today."
                )
            else:
                return False, (
                    f"Daily limit reached: {today_sent}/{daily_limit} sent. "
                    f"Can send {daily_remaining} more today."
                )
        
        # Check hourly limit
        hourly_remaining = self.get_hourly_remaining()
        if count > hourly_remaining:
            this_hour_sent = self.get_this_hour_send_count()
            return False, (
                f"Hourly limit reached: {this_hour_sent}/{config.EMAIL_MAX_HOURLY_VOLUME} sent this hour. "
                f"Can send {hourly_remaining} more this hour."
            )
        
        return True, "OK"
    
    def record_sends(self, count: int):
        """
        Record that emails were sent.
        
        Args:
            count: Number of emails sent
        """
        data = self._load_limits_data()
        
        # Update daily count
        today = datetime.now().date().isoformat()
        daily_counts = data.get('daily_counts', {})
        daily_counts[today] = daily_counts.get(today, 0) + count
        data['daily_counts'] = daily_counts
        
        # Update hourly count
        current_hour = datetime.now().replace(minute=0, second=0, microsecond=0).isoformat()
        hourly_counts = data.get('hourly_counts', {})
        hourly_counts[current_hour] = hourly_counts.get(current_hour, 0) + count
        data['hourly_counts'] = hourly_counts
        
        # Clean up old data (keep last 30 days)
        self._cleanup_old_data(data)
        
        self._save_limits_data(data)
        logger.info(f"Recorded {count} sends. Today: {daily_counts[today]}, This hour: {hourly_counts[current_hour]}")
    
    def _cleanup_old_data(self, data: Dict):
        """Remove data older than 30 days to keep file size manageable"""
        cutoff_date = (datetime.now() - timedelta(days=30)).date().isoformat()
        
        # Clean daily counts
        daily_counts = data.get('daily_counts', {})
        data['daily_counts'] = {
            date: count for date, count in daily_counts.items()
            if date >= cutoff_date
        }
        
        # Clean hourly counts (keep last 7 days)
        hourly_cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        hourly_counts = data.get('hourly_counts', {})
        data['hourly_counts'] = {
            hour: count for hour, count in hourly_counts.items()
            if hour >= hourly_cutoff
        }
    
    def get_limits_summary(self) -> Dict:
        """Get summary of current limits and usage"""
        domain_age = self.get_domain_age_days()
        daily_limit = self.get_daily_limit()
        today_sent = self.get_today_send_count()
        daily_remaining = self.get_daily_remaining()
        
        this_hour_sent = self.get_this_hour_send_count()
        hourly_remaining = self.get_hourly_remaining()
        
        is_warmup = domain_age < config.EMAIL_WARMUP_DAYS
        
        return {
            'domain_age_days': domain_age,
            'is_warmup_period': is_warmup,
            'warmup_day': f"{domain_age + 1}/{config.EMAIL_WARMUP_DAYS}" if is_warmup else "Complete",
            'daily_limit': daily_limit,
            'daily_sent': today_sent,
            'daily_remaining': daily_remaining,
            'daily_usage_pct': (today_sent / daily_limit * 100) if daily_limit > 0 else 0,
            'hourly_limit': config.EMAIL_MAX_HOURLY_VOLUME,
            'hourly_sent': this_hour_sent,
            'hourly_remaining': hourly_remaining,
            'hourly_usage_pct': (this_hour_sent / config.EMAIL_MAX_HOURLY_VOLUME * 100),
        }


# Singleton instance
_limits_tracker = None

def get_limits_tracker() -> SendingLimitsTracker:
    """Get or create the global limits tracker instance"""
    global _limits_tracker
    if _limits_tracker is None:
        _limits_tracker = SendingLimitsTracker()
    return _limits_tracker
