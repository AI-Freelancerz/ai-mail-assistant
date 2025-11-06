"""
Mock Brevo Status Client for Testing
This file provides fake data for testing the email status dashboard at scale
without using real API calls or sending actual emails.

Usage:
------
In email_status_page.py, temporarily replace:
    from brevo_status_client import BrevoStatusClient
with:
    from brevo_status_client_mock import MockBrevoStatusClient as BrevoStatusClient

Then change it back when done testing.
"""

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class MockBrevoStatusClient:
    """Mock client that generates fake email events for testing."""
    
    def __init__(self, api_key: str):
        """Initialize the mock client."""
        self.api_key = api_key
        logger.info("🧪 MockBrevoStatusClient initialized - generating fake data")
        
    def get_email_events(
        self,
        limit: int = 50,
        offset: int = 0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        email: Optional[str] = None,
        event: Optional[str] = None,
        tags: Optional[str] = None,
        sort: str = "desc"
    ) -> Tuple[List[Dict], int]:
        """
        Generate fake email events for testing.
        
        Returns a realistic set of email events with various states.
        """
        logger.info(f"🧪 Generating {limit} mock events (offset={offset}, start={start_date}, end={end_date})")
        
        # Sample data
        test_subjects = [
            "Weekly Newsletter - November Edition",
            "Important Update: New Features",
            "Thank you for your registration",
            "Special Offer - 50% Off",
            "Monthly Report Summary",
            "Action Required: Verify Your Account",
            "Welcome to Our Platform!",
            "Your Invoice for October",
            "Reminder: Meeting Tomorrow",
            "Product Launch Announcement"
        ]
        
        test_recipients = [
            f"test.user{i}@example.com" for i in range(1, 31)
        ] + [
            f"john.doe{i}@testmail.com" for i in range(1, 21)
        ] + [
            f"contact{i}@company.org" for i in range(1, 21)
        ] + [
            f"user{i}@domain.net" for i in range(1, 31)
        ]
        
        event_types = [
            'request',      # Email sent
            'delivered',    # Email delivered
            'opened',       # Email opened (read)
            'click',        # Link clicked
            'hardBounce',   # Hard bounce (invalid email)
            'softBounce',   # Soft bounce (temporary issue)
            'blocked',      # Blocked by provider
            'spam',         # Marked as spam
            'unsubscribed', # User unsubscribed
        ]
        
        # Weights for realistic distribution
        # Most emails are delivered and opened, fewer bounces/spam
        event_weights = [20, 80, 50, 30, 2, 3, 1, 1, 2]
        
        tags = ["newsletter", "transactional", "marketing", "notification"]
        
        # Generate events
        events = []
        
        # If no date range specified, use last 7 days
        if not start_date:
            start_date = datetime.now(timezone.utc) - timedelta(days=7)
        if not end_date:
            end_date = datetime.now(timezone.utc)
        
        # Generate events within the date range
        total_to_generate = min(limit, 100)  # Respect API limit
        
        # Create batches of emails (simulate sending campaigns)
        num_batches = random.randint(3, 8)
        emails_per_batch = total_to_generate // num_batches
        
        for batch_idx in range(num_batches):
            # Each batch has a specific send time
            batch_time = start_date + timedelta(
                seconds=random.randint(0, int((end_date - start_date).total_seconds()))
            )
            
            # Pick a subject for this batch
            batch_subject = random.choice(test_subjects)
            batch_tag = random.choice(tags)
            
            # Generate a batch ID (like Brevo does)
            batch_id = batch_time.strftime("%Y%m%d%H%M") + f".{random.randint(10000000, 99999999)}"
            
            # Generate events for this batch
            for i in range(emails_per_batch):
                recipient = random.choice(test_recipients)
                message_id = f"<{batch_id}.{i+1}@smtp-relay.mailin.fr>"
                
                # Generate multiple events per email (lifecycle)
                # Most emails: request -> delivered -> opened -> maybe clicked
                email_events = []
                
                # Always start with request
                email_events.append('request')
                
                # 90% get delivered
                if random.random() < 0.90:
                    email_events.append('delivered')
                    
                    # 60% of delivered get opened
                    if random.random() < 0.60:
                        email_events.append('opened')
                        
                        # 40% of opened get clicked
                        if random.random() < 0.40:
                            email_events.append('click')
                else:
                    # Not delivered - pick a bounce/block reason
                    email_events.append(random.choice(['hardBounce', 'softBounce', 'blocked', 'spam']))
                
                # Create event objects for each lifecycle event
                for event_idx, event_type in enumerate(email_events):
                    event_time = batch_time + timedelta(minutes=event_idx * 5 + random.randint(0, 300))
                    
                    # Make sure event is within range
                    if event_time > end_date:
                        event_time = end_date - timedelta(seconds=random.randint(1, 3600))
                    
                    event_dict = {
                        'event': event_type,
                        'email': recipient,
                        'subject': batch_subject,
                        'message_id': message_id,
                        'date': event_time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                        'tag': batch_tag,
                        'template_id': random.randint(1, 5),
                        'reason': self._get_reason(event_type),
                        'link': self._get_link(event_type),
                    }
                    events.append(event_dict)
        
        # Sort by date (newest first if desc)
        events.sort(key=lambda x: x['date'], reverse=(sort == 'desc'))
        
        # Apply pagination
        paginated_events = events[offset:offset + limit]
        
        logger.info(f"🧪 Generated {len(paginated_events)} mock events (total available: {len(events)})")
        
        return paginated_events, len(events)
    
    def _get_reason(self, event_type: str) -> str:
        """Get a realistic reason for the event type."""
        reasons = {
            'hardBounce': random.choice([
                'Mailbox not found',
                'Invalid recipient',
                'Domain does not exist',
                'User unknown'
            ]),
            'softBounce': random.choice([
                'Mailbox full',
                'Temporary server error',
                'Message too large',
                'Temporarily unavailable'
            ]),
            'blocked': random.choice([
                'IP blacklisted',
                'Content filtered',
                'Sender reputation',
                'Policy violation'
            ]),
            'spam': 'Marked as spam by recipient',
            'unsubscribed': 'User unsubscribed',
        }
        return reasons.get(event_type, '')
    
    def _get_link(self, event_type: str) -> str:
        """Get a realistic link for click events."""
        if event_type == 'click':
            links = [
                'https://example.com/products',
                'https://example.com/unsubscribe',
                'https://example.com/learn-more',
                'https://example.com/contact',
                'https://example.com/special-offer',
            ]
            return random.choice(links)
        return ''
    
    def get_email_content(self, uuid: str) -> Optional[Dict]:
        """Mock method - returns fake email content."""
        logger.info(f"🧪 Mock: get_email_content called with uuid={uuid}")
        return {
            'subject': 'Test Email Subject',
            'body': '<p>This is a test email body</p>',
            'from': 'test@example.com',
        }


# For convenience, also provide a function to easily switch between real and mock
def get_client(api_key: str, use_mock: bool = False):
    """
    Get either real or mock Brevo client.
    
    Args:
        api_key: Brevo API key
        use_mock: If True, returns MockBrevoStatusClient, else real BrevoStatusClient
    
    Returns:
        Client instance
    """
    if use_mock:
        return MockBrevoStatusClient(api_key)
    else:
        from brevo_status_client import BrevoStatusClient
        return BrevoStatusClient(api_key)
