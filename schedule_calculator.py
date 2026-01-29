"""
Email Schedule Calculator & Visualizer

Shows exactly when emails will be sent based on:
- Current warm-up day
- Daily/hourly limits  
- Business hours restrictions
- Contact list size
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import pandas as pd
from sending_limits_tracker import get_limits_tracker
from email_utils import is_safe_send_time
import config

logger = logging.getLogger(__name__)


class ScheduleCalculator:
    def __init__(self):
        self.limits_tracker = get_limits_tracker()
    
    def calculate_schedule(
        self, 
        total_emails: int,
        start_date: datetime = None,
        respect_warmup: bool = True,
        custom_daily_limit: int = None
    ) -> List[Dict]:
        if start_date is None:
            start_date = datetime.now()
        
        start_date = self._next_business_time(start_date)
        
        schedule = []
        remaining = total_emails
        cumulative = 0
        current_date = start_date
        
        domain_age_at_start = self.limits_tracker.get_domain_age_days()
        days_elapsed = 0
        
        while remaining > 0:
            if respect_warmup:
                warm_up_day = domain_age_at_start + days_elapsed
                if warm_up_day < config.EMAIL_WARMUP_DAYS:
                    daily_limit = config.EMAIL_WARMUP_DAILY_LIMITS[warm_up_day]
                else:
                    daily_limit = config.EMAIL_MAX_DAILY_VOLUME
            else:
                daily_limit = custom_daily_limit or config.EMAIL_MAX_DAILY_VOLUME
            
            to_send_today = min(remaining, daily_limit)
            hours_needed = (to_send_today + config.EMAIL_MAX_HOURLY_VOLUME - 1) // config.EMAIL_MAX_HOURLY_VOLUME
            
            schedule.append({
                'date': current_date.date(),
                'day_of_week': current_date.strftime('%A'),
                'warmup_day': domain_age_at_start + days_elapsed + 1 if respect_warmup else None,
                'daily_limit': daily_limit,
                'emails_to_send': to_send_today,
                'cumulative_sent': cumulative + to_send_today,
                'hours_needed': hours_needed,
                'start_time': current_date.strftime('%H:%M'),
                'estimated_end_time': self._calculate_end_time(current_date, to_send_today).strftime('%H:%M'),
                'percentage_complete': ((cumulative + to_send_today) / total_emails * 100),
            })
            
            remaining -= to_send_today
            cumulative += to_send_today
            current_date = self._next_business_day(current_date)
            days_elapsed += 1
            
            if days_elapsed > 365:
                logger.error('Schedule calculation exceeded 1 year!')
                break
        
        return schedule
    
    def _next_business_time(self, dt: datetime) -> datetime:
        dt = dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        
        while dt.weekday() not in config.EMAIL_SEND_DAYS:
            dt = dt + timedelta(days=1)
            dt = dt.replace(hour=config.EMAIL_SEND_HOURS_START, minute=0)
        
        if dt.hour < config.EMAIL_SEND_HOURS_START:
            dt = dt.replace(hour=config.EMAIL_SEND_HOURS_START)
        elif dt.hour >= config.EMAIL_SEND_HOURS_END:
            dt = dt + timedelta(days=1)
            dt = dt.replace(hour=config.EMAIL_SEND_HOURS_START)
            return self._next_business_time(dt)
        
        return dt
    
    def _next_business_day(self, dt: datetime) -> datetime:
        dt = dt + timedelta(days=1)
        dt = dt.replace(hour=config.EMAIL_SEND_HOURS_START, minute=0, second=0, microsecond=0)
        
        while dt.weekday() not in config.EMAIL_SEND_DAYS:
            dt = dt + timedelta(days=1)
        
        return dt
    
    def _calculate_end_time(self, start_time: datetime, email_count: int) -> datetime:
        hours_needed = email_count / config.EMAIL_MAX_HOURLY_VOLUME
        hours_needed *= 1.1
        
        end_time = start_time + timedelta(hours=hours_needed)
        
        if end_time.hour >= config.EMAIL_SEND_HOURS_END:
            end_time = end_time.replace(
                hour=config.EMAIL_SEND_HOURS_END - 1,
                minute=59
            )
        
        return end_time
    
    def format_schedule_table(self, schedule: List[Dict]) -> pd.DataFrame:
        df = pd.DataFrame(schedule)
        
        if not df.empty:
            df['Date'] = df['date'].apply(lambda x: x.strftime('%Y-%m-%d'))
            df['Day'] = df['day_of_week']
            
            if 'warmup_day' in df.columns and df['warmup_day'].iloc[0] is not None:
                df['Warm-up Day'] = df['warmup_day'].apply(
                    lambda x: f'Day {x}' if x <= config.EMAIL_WARMUP_DAYS else 'Complete'
                )
            
            df['Daily Limit'] = df['daily_limit']
            df['Emails'] = df['emails_to_send']
            df['Cumulative'] = df['cumulative_sent']
            df['Progress'] = df['percentage_complete'].apply(lambda x: f'{x:.1f}%')
            df['Time Window'] = df['start_time'] + ' - ' + df['estimated_end_time']
            
            display_cols = ['Date', 'Day', 'Emails', 'Cumulative', 'Progress', 'Time Window']
            if 'Warm-up Day' in df.columns:
                display_cols.insert(2, 'Warm-up Day')
                display_cols.insert(3, 'Daily Limit')
            
            df = df[display_cols]
        
        return df
    
    def estimate_completion(self, total_emails: int, respect_warmup: bool = True) -> Dict:
        schedule = self.calculate_schedule(total_emails, respect_warmup=respect_warmup)
        
        if not schedule:
            return {
                'days_needed': 0,
                'completion_date': None,
                'warning_messages': ['Unable to calculate schedule']
            }
        
        first_day = schedule[0]['date']
        last_day = schedule[-1]['date']
        days_needed = (last_day - first_day).days + 1
        
        warnings = []
        
        if respect_warmup and schedule[0].get('warmup_day', 100) <= config.EMAIL_WARMUP_DAYS:
            warnings.append(
                f'⚠️ Campaign spans warm-up period. Daily limits are restricted.'
            )
        
        if days_needed > 14:
            warnings.append(
                f'⚠️ Campaign will take {days_needed} days. Consider segmenting your list.'
            )
        
        today_sent = self.limits_tracker.get_today_send_count()
        today_limit = self.limits_tracker.get_daily_limit()
        if today_sent >= today_limit * 0.9:
            warnings.append(
                f'⚠️ Today''s limit almost reached ({today_sent}/{today_limit}). '
                f'Campaign will start tomorrow.'
            )
        
        return {
            'days_needed': days_needed,
            'completion_date': last_day,
            'first_batch_date': first_day,
            'first_batch_size': schedule[0]['emails_to_send'],
            'total_emails': total_emails,
            'warning_messages': warnings
        }
    
    def calculate_bucket_schedule(
        self,
        total_emails: int,
        num_buckets: int,
        delay_between_buckets_hours: float = 1.0
    ) -> List[Dict]:
        emails_per_bucket = (total_emails + num_buckets - 1) // num_buckets
        
        current_time = datetime.now()
        buckets = []
        
        for i in range(num_buckets):
            emails_in_bucket = min(emails_per_bucket, total_emails - (i * emails_per_bucket))
            
            if emails_in_bucket <= 0:
                break
            
            duration_minutes = (emails_in_bucket / config.EMAIL_MAX_HOURLY_VOLUME) * 60
            
            buckets.append({
                'bucket_number': i + 1,
                'scheduled_time': current_time,
                'emails_count': emails_in_bucket,
                'cumulative_sent': min((i + 1) * emails_per_bucket, total_emails),
                'estimated_duration_minutes': int(duration_minutes),
                'status': 'pending'
            })
            
            current_time = current_time + timedelta(hours=delay_between_buckets_hours)
        
        return buckets


def get_schedule_calculator() -> ScheduleCalculator:
    return ScheduleCalculator()
