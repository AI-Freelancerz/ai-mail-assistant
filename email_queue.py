"""
Email Sending Queue System

Allows users to upload large contact lists and have emails sent gradually over days/weeks
according to warm-up schedule and rate limits.

Features:
- Queue jobs for future sending
- Automatic scheduling based on daily/hourly limits
- Pause/resume campaigns
- Priority queue support
- Automatic retry on failures
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from enum import Enum
import config
from sending_limits_tracker import get_limits_tracker

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job status types"""
    PENDING = "pending"      # Waiting to be sent
    SCHEDULED = "scheduled"  # Scheduled for future time
    SENDING = "sending"      # Currently being sent
    COMPLETED = "completed"  # Successfully sent
    FAILED = "failed"        # Failed after retries
    PAUSED = "paused"       # Manually paused
    CANCELLED = "cancelled"  # Manually cancelled


class EmailQueueManager:
    """Manages scheduled email sending queue"""
    
    def __init__(self, queue_file: str = None):
        self.queue_file = queue_file or config.EMAIL_QUEUE_PATH
        self.queue_path = Path(self.queue_file)
        self.limits_tracker = get_limits_tracker()
        self._ensure_queue_file_exists()
    
    def _ensure_queue_file_exists(self):
        """Create queue file if it doesn't exist"""
        if not self.queue_path.exists():
            self.queue_path.parent.mkdir(parents=True, exist_ok=True)
            initial_data = {
                'jobs': {},
                'campaigns': {},
            }
            self._save_queue_data(initial_data)
            logger.info(f"Created new email queue file: {self.queue_path}")
    
    def _load_queue_data(self) -> Dict:
        """Load queue data from file"""
        try:
            with open(self.queue_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading queue data: {e}")
            return {'jobs': {}, 'campaigns': {}}
    
    def _save_queue_data(self, data: Dict):
        """Save queue data to file"""
        try:
            with open(self.queue_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving queue data: {e}")
    
    def create_campaign(
        self,
        name: str,
        sender_email: str,
        sender_name: str,
        subject: str,
        body: str,
        contacts: List[Dict],
        priority: int = 5,
        attachments: List[str] = None
    ) -> str:
        """
        Create a new email campaign and schedule it for gradual sending.
        
        Args:
            name: Campaign name/description
            sender_email: From email
            sender_name: From name
            subject: Email subject
            body: Email body (HTML)
            contacts: List of contact dicts with 'email' and 'name'
            priority: Priority 1-10 (1=highest, 10=lowest)
            attachments: List of attachment file paths
            
        Returns:
            Campaign ID
        """
        campaign_id = f"campaign_{uuid.uuid4().hex[:12]}"
        
        data = self._load_queue_data()
        
        # Create campaign record
        data['campaigns'][campaign_id] = {
            'id': campaign_id,
            'name': name,
            'created_at': datetime.now().isoformat(),
            'sender_email': sender_email,
            'sender_name': sender_name,
            'subject': subject,
            'body': body,
            'priority': priority,
            'attachments': attachments or [],
            'total_contacts': len(contacts),
            'status': JobStatus.PENDING,
            'job_ids': [],
            'sent_count': 0,
            'failed_count': 0,
        }
        
        # Schedule jobs for each contact
        scheduled_time = datetime.now()
        
        for i, contact in enumerate(contacts):
            job_id = self._create_job(
                data,
                campaign_id=campaign_id,
                sender_email=sender_email,
                sender_name=sender_name,
                to_email=contact['email'],
                to_name=contact['name'],
                subject=subject,
                body=body,
                attachments=attachments,
                scheduled_time=scheduled_time,
                priority=priority
            )
            
            data['campaigns'][campaign_id]['job_ids'].append(job_id)
            
            # Calculate next scheduled time based on limits
            scheduled_time = self._calculate_next_send_time(data, scheduled_time)
        
        self._save_queue_data(data)
        
        logger.info(
            f"Created campaign {campaign_id}: {name} "
            f"with {len(contacts)} contacts scheduled over time"
        )
        
        return campaign_id
    
    def _create_job(
        self,
        data: Dict,
        campaign_id: str,
        sender_email: str,
        sender_name: str,
        to_email: str,
        to_name: str,
        subject: str,
        body: str,
        scheduled_time: datetime,
        priority: int = 5,
        attachments: List[str] = None
    ) -> str:
        """Create a single email job"""
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        
        data['jobs'][job_id] = {
            'id': job_id,
            'campaign_id': campaign_id,
            'created_at': datetime.now().isoformat(),
            'scheduled_time': scheduled_time.isoformat(),
            'sender_email': sender_email,
            'sender_name': sender_name,
            'to_email': to_email,
            'to_name': to_name,
            'subject': subject,
            'body': body,
            'attachments': attachments or [],
            'priority': priority,
            'status': JobStatus.SCHEDULED,
            'retry_count': 0,
            'max_retries': 3,
            'last_error': None,
            'sent_at': None,
        }
        
        return job_id
    
    def _calculate_next_send_time(self, data: Dict, current_time: datetime) -> datetime:
        """
        Calculate when the next email can be sent based on:
        - Hourly limits
        - Daily limits
        - Business hours restrictions
        - Warm-up schedule
        """
        # Start from current time
        next_time = current_time
        
        # Get limits summary
        limits = self.limits_tracker.get_limits_summary()
        
        # Count jobs scheduled for same hour
        current_hour = next_time.replace(minute=0, second=0, microsecond=0)
        jobs_this_hour = sum(
            1 for job in data['jobs'].values()
            if job['status'] in [JobStatus.SCHEDULED, JobStatus.PENDING]
            and datetime.fromisoformat(job['scheduled_time']).replace(minute=0, second=0, microsecond=0) == current_hour
        )
        
        # If hourly limit reached, move to next hour
        if jobs_this_hour >= config.EMAIL_MAX_HOURLY_VOLUME:
            next_time = next_time + timedelta(hours=1)
            next_time = next_time.replace(minute=0, second=0, microsecond=0)
        
        # Ensure within business hours
        next_time = self._ensure_business_hours(next_time)
        
        # Add minimum interval between emails
        next_time = next_time + timedelta(seconds=config.EMAIL_MIN_SEND_INTERVAL_SECONDS)
        
        return next_time
    
    def _ensure_business_hours(self, dt: datetime) -> datetime:
        """Ensure datetime is within business hours, skip to next valid time if not"""
        if not config.EMAIL_REQUIRE_SAFE_SEND_TIME:
            return dt
        
        # Check if within business days
        while dt.weekday() not in config.EMAIL_SEND_DAYS:
            # Skip to next Monday
            days_ahead = (7 - dt.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            dt = dt + timedelta(days=days_ahead)
            dt = dt.replace(hour=config.EMAIL_SEND_HOURS_START, minute=0, second=0)
        
        # Check if within business hours
        if dt.hour < config.EMAIL_SEND_HOURS_START:
            dt = dt.replace(hour=config.EMAIL_SEND_HOURS_START, minute=0, second=0)
        elif dt.hour >= config.EMAIL_SEND_HOURS_END:
            # Move to next business day
            dt = dt + timedelta(days=1)
            dt = dt.replace(hour=config.EMAIL_SEND_HOURS_START, minute=0, second=0)
            # Recursive call to handle weekends
            dt = self._ensure_business_hours(dt)
        
        return dt
    
    def get_ready_jobs(self, limit: int = 100) -> List[Dict]:
        """
        Get jobs that are ready to be sent now.
        
        Args:
            limit: Maximum number of jobs to return
            
        Returns:
            List of job dicts ready for sending
        """
        data = self._load_queue_data()
        now = datetime.now()
        
        ready_jobs = []
        
        for job in data['jobs'].values():
            # Skip non-scheduled jobs
            if job['status'] not in [JobStatus.SCHEDULED, JobStatus.PENDING]:
                continue
            
            # Check if scheduled time has passed
            scheduled_time = datetime.fromisoformat(job['scheduled_time'])
            if scheduled_time <= now:
                ready_jobs.append(job)
        
        # Sort by priority (lower number = higher priority) then by scheduled time
        ready_jobs.sort(key=lambda j: (j['priority'], j['scheduled_time']))
        
        return ready_jobs[:limit]
    
    def mark_job_sending(self, job_id: str):
        """Mark a job as currently being sent"""
        data = self._load_queue_data()
        if job_id in data['jobs']:
            data['jobs'][job_id]['status'] = JobStatus.SENDING
            self._save_queue_data(data)
    
    def mark_job_completed(self, job_id: str):
        """Mark a job as successfully sent"""
        data = self._load_queue_data()
        if job_id in data['jobs']:
            job = data['jobs'][job_id]
            job['status'] = JobStatus.COMPLETED
            job['sent_at'] = datetime.now().isoformat()
            
            # Update campaign stats
            campaign_id = job['campaign_id']
            if campaign_id in data['campaigns']:
                data['campaigns'][campaign_id]['sent_count'] += 1
            
            self._save_queue_data(data)
    
    def mark_job_failed(self, job_id: str, error_message: str):
        """Mark a job as failed"""
        data = self._load_queue_data()
        if job_id in data['jobs']:
            job = data['jobs'][job_id]
            job['retry_count'] += 1
            job['last_error'] = error_message
            
            # If retries exhausted, mark as failed
            if job['retry_count'] >= job['max_retries']:
                job['status'] = JobStatus.FAILED
                
                # Update campaign stats
                campaign_id = job['campaign_id']
                if campaign_id in data['campaigns']:
                    data['campaigns'][campaign_id]['failed_count'] += 1
            else:
                # Reschedule for retry (exponential backoff)
                retry_delay_minutes = 5 * (2 ** job['retry_count'])
                new_scheduled_time = datetime.now() + timedelta(minutes=retry_delay_minutes)
                job['scheduled_time'] = new_scheduled_time.isoformat()
                job['status'] = JobStatus.SCHEDULED
            
            self._save_queue_data(data)
    
    def get_campaign_status(self, campaign_id: str) -> Optional[Dict]:
        """Get current status of a campaign"""
        data = self._load_queue_data()
        campaign = data['campaigns'].get(campaign_id)
        
        if not campaign:
            return None
        
        # Calculate current progress
        total = campaign['total_contacts']
        sent = campaign['sent_count']
        failed = campaign['failed_count']
        pending = total - sent - failed
        
        return {
            'id': campaign_id,
            'name': campaign['name'],
            'created_at': campaign['created_at'],
            'status': campaign['status'],
            'total_contacts': total,
            'sent_count': sent,
            'failed_count': failed,
            'pending_count': pending,
            'progress_pct': (sent / total * 100) if total > 0 else 0,
        }
    
    def pause_campaign(self, campaign_id: str) -> bool:
        """Pause all pending jobs in a campaign"""
        data = self._load_queue_data()
        
        if campaign_id not in data['campaigns']:
            return False
        
        campaign = data['campaigns'][campaign_id]
        campaign['status'] = JobStatus.PAUSED
        
        # Pause all pending/scheduled jobs
        for job_id in campaign['job_ids']:
            if job_id in data['jobs']:
                job = data['jobs'][job_id]
                if job['status'] in [JobStatus.PENDING, JobStatus.SCHEDULED]:
                    job['status'] = JobStatus.PAUSED
        
        self._save_queue_data(data)
        logger.info(f"Paused campaign: {campaign_id}")
        return True
    
    def resume_campaign(self, campaign_id: str) -> bool:
        """Resume a paused campaign"""
        data = self._load_queue_data()
        
        if campaign_id not in data['campaigns']:
            return False
        
        campaign = data['campaigns'][campaign_id]
        campaign['status'] = JobStatus.PENDING
        
        # Resume all paused jobs
        for job_id in campaign['job_ids']:
            if job_id in data['jobs']:
                job = data['jobs'][job_id]
                if job['status'] == JobStatus.PAUSED:
                    job['status'] = JobStatus.SCHEDULED
        
        self._save_queue_data(data)
        logger.info(f"Resumed campaign: {campaign_id}")
        return True
    
    def get_all_campaigns(self) -> List[Dict]:
        """Get list of all campaigns with status"""
        data = self._load_queue_data()
        
        campaigns = []
        for campaign_id in data['campaigns'].keys():
            status = self.get_campaign_status(campaign_id)
            if status:
                campaigns.append(status)
        
        # Sort by created_at descending (newest first)
        campaigns.sort(key=lambda c: c['created_at'], reverse=True)
        
        return campaigns
    
    def create_campaign_with_bucket_mode(
        self,
        name: str,
        sender_email: str,
        sender_name: str,
        subject: str,
        body: str,
        contacts: List[Dict],
        num_buckets: int = 5,
        delay_between_buckets_hours: float = 1.0,
        priority: int = 5,
        attachments: List[str] = None
    ) -> str:
        """
        Create campaign with bucket sending mode.
        Sends all emails in same day, split into buckets with delays.
        
        WARNING: Use only AFTER warm-up period complete!
        This bypasses daily limits for immediate same-day sending.
        
        Args:
            name: Campaign name
            sender_email: From email
            sender_name: From name  
            subject: Email subject
            body: Email body (HTML)
            contacts: List of contact dicts
            num_buckets: Number of buckets to split into (default 5)
            delay_between_buckets_hours: Hours between buckets (default 1.0)
            priority: Priority 1-10
            attachments: List of attachment paths
            
        Returns:
            Campaign ID
        """
        campaign_id = f"campaign_{uuid.uuid4().hex[:12]}"
        
        data = self._load_queue_data()
        
        # Create campaign record
        data['campaigns'][campaign_id] = {
            'id': campaign_id,
            'name': f"{name} (BUCKET MODE)",
            'created_at': datetime.now().isoformat(),
            'sender_email': sender_email,
            'sender_name': sender_name,
            'subject': subject,
            'body': body,
            'priority': priority,
            'attachments': attachments or [],
            'total_contacts': len(contacts),
            'status': JobStatus.PENDING,
            'job_ids': [],
            'sent_count': 0,
            'failed_count': 0,
            'mode': 'bucket',
            'num_buckets': num_buckets,
        }
        
        # Calculate bucket size
        bucket_size = len(contacts) // num_buckets
        remainder = len(contacts) % num_buckets
        
        # Schedule jobs in buckets
        start_time = datetime.now()
        current_bucket_start = start_time
        
        for bucket_idx in range(num_buckets):
            # Determine contacts for this bucket
            start_idx = bucket_idx * bucket_size
            end_idx = start_idx + bucket_size
            if bucket_idx == num_buckets - 1:
                end_idx += remainder  # Add remaining to last bucket
            
            bucket_contacts = contacts[start_idx:end_idx]
            
            # Schedule all contacts in this bucket at same time
            for contact in bucket_contacts:
                job_id = self._create_job(
                    data,
                    campaign_id=campaign_id,
                    sender_email=sender_email,
                    sender_name=sender_name,
                    to_email=contact['email'],
                    to_name=contact['name'],
                    subject=subject,
                    body=body,
                    attachments=attachments,
                    scheduled_time=current_bucket_start,
                    priority=priority
                )
                data['campaigns'][campaign_id]['job_ids'].append(job_id)
            
            # Move to next bucket start time
            current_bucket_start = current_bucket_start + timedelta(hours=delay_between_buckets_hours)
        
        self._save_queue_data(data)
        
        logger.info(
            f"Created BUCKET MODE campaign {campaign_id}: {name} "
            f"with {len(contacts)} contacts in {num_buckets} buckets"
        )
        logger.warning(
            "BUCKET MODE bypasses daily limits. "
            "Use only after warm-up period!"
        )
        
        return campaign_id
    
    def create_campaign_with_custom_schedule(
        self,
        name: str,
        sender_email: str,
        sender_name: str,
        subject: str,
        body: str,
        contacts: List[Dict],
        custom_schedule: List[Dict],
        priority: int = 5,
        attachments: List[str] = None
    ) -> str:
        """
        Create campaign with manually specified schedule.
        
        Schedule format:
        [
            {'date': '2026-01-03', 'count': 100},
            {'date': '2026-01-04', 'count': 200},
            ...
        ]
        
        Args:
            name: Campaign name
            sender_email: From email
            sender_name: From name
            subject: Email subject
            body: Email body (HTML)
            contacts: List of contact dicts
            custom_schedule: List of date+count dicts
            priority: Priority 1-10
            attachments: List of attachment paths
            
        Returns:
            Campaign ID
        """
        campaign_id = f"campaign_{uuid.uuid4().hex[:12]}"
        
        data = self._load_queue_data()
        
        # Validate schedule
        total_scheduled = sum(item['count'] for item in custom_schedule)
        if total_scheduled != len(contacts):
            logger.error(
                f"Schedule mismatch: {total_scheduled} scheduled "
                f"but {len(contacts)} contacts provided"
            )
            raise ValueError(
                f"Custom schedule total ({total_scheduled}) must match "
                f"contact count ({len(contacts)})"
            )
        
        # Create campaign record
        data['campaigns'][campaign_id] = {
            'id': campaign_id,
            'name': f"{name} (CUSTOM SCHEDULE)",
            'created_at': datetime.now().isoformat(),
            'sender_email': sender_email,
            'sender_name': sender_name,
            'subject': subject,
            'body': body,
            'priority': priority,
            'attachments': attachments or [],
            'total_contacts': len(contacts),
            'status': JobStatus.PENDING,
            'job_ids': [],
            'sent_count': 0,
            'failed_count': 0,
            'mode': 'custom',
            'custom_schedule': custom_schedule,
        }
        
        # Schedule jobs according to custom schedule
        contact_idx = 0
        
        for schedule_item in custom_schedule:
            date_str = schedule_item['date']
            count = schedule_item['count']
            
            # Parse target date
            target_date = datetime.fromisoformat(date_str)
            
            # Ensure within business hours
            target_date = target_date.replace(
                hour=config.EMAIL_SEND_HOURS_START,
                minute=0,
                second=0
            )
            target_date = self._ensure_business_hours(target_date)
            
            # Schedule 'count' contacts for this date
            for _ in range(count):
                if contact_idx >= len(contacts):
                    break
                
                contact = contacts[contact_idx]
                job_id = self._create_job(
                    data,
                    campaign_id=campaign_id,
                    sender_email=sender_email,
                    sender_name=sender_name,
                    to_email=contact['email'],
                    to_name=contact['name'],
                    subject=subject,
                    body=body,
                    attachments=attachments,
                    scheduled_time=target_date,
                    priority=priority
                )
                data['campaigns'][campaign_id]['job_ids'].append(job_id)
                
                contact_idx += 1
                
                # Add small interval between emails on same day
                target_date = target_date + timedelta(
                    seconds=config.EMAIL_MIN_SEND_INTERVAL_SECONDS
                )
        
        self._save_queue_data(data)
        
        logger.info(
            f"Created CUSTOM SCHEDULE campaign {campaign_id}: {name} "
            f"with {len(contacts)} contacts over {len(custom_schedule)} days"
        )
        
        return campaign_id


# Singleton instance
_queue_manager = None

def get_queue_manager() -> EmailQueueManager:
    """Get or create the global queue manager instance"""
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = EmailQueueManager()
    return _queue_manager
