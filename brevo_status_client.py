"""
Brevo Email Status Client
Wrapper for Brevo API to fetch email event reports and transaction details.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import brevo_python as sib_api_v3_sdk
from brevo_python.rest import ApiException

logger = logging.getLogger(__name__)


class BrevoStatusClient:
    """Client for fetching email status and events from Brevo API."""
    
    def __init__(self, api_key: str):
        """
        Initialize the Brevo status client.
        
        Args:
            api_key: Brevo API key
        """
        self.api_key = api_key
        self.configuration = sib_api_v3_sdk.Configuration()
        self.configuration.api_key['api-key'] = api_key
        self.api_client = sib_api_v3_sdk.ApiClient(self.configuration)
        self.transactional_api = sib_api_v3_sdk.TransactionalEmailsApi(self.api_client)
        
    def _retry_with_backoff(self, func, max_retries=3, initial_delay=1.0):
        """
        Execute a function with exponential backoff on rate limiting.
        
        Args:
            func: Function to execute
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds
            
        Returns:
            Result of the function call
            
        Raises:
            ApiException: If all retries are exhausted or a non-retryable error occurs
        """
        delay = initial_delay
        for attempt in range(max_retries):
            try:
                return func()
            except ApiException as e:
                if e.status == 429:  # Rate limited
                    if attempt < max_retries - 1:
                        # Check for Retry-After header
                        retry_after = None
                        if hasattr(e, 'headers') and e.headers:
                            retry_after = e.headers.get('Retry-After') or e.headers.get('retry-after')
                        
                        # Use Retry-After if available, otherwise exponential backoff
                        if retry_after:
                            try:
                                delay = float(retry_after)
                                logger.warning(f"Rate limited. Retry-After header suggests waiting {delay}s (attempt {attempt + 1}/{max_retries})")
                            except (ValueError, TypeError):
                                logger.warning(f"Rate limited. Using exponential backoff: {delay}s (attempt {attempt + 1}/{max_retries})")
                        else:
                            logger.warning(f"Rate limited. Retrying in {delay}s... (attempt {attempt + 1}/{max_retries})")
                        
                        time.sleep(delay)
                        delay *= 2  # Exponential backoff for next attempt
                    else:
                        logger.error(f"Rate limit exceeded after {max_retries} attempts")
                        raise
                else:
                    # Non-retryable error, raise immediately
                    raise
        
        # Should never reach here, but just in case
        raise Exception(f"Failed after {max_retries} retries")
        
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
        Fetch email event reports from Brevo.
        
        Args:
            limit: Maximum number of events to return (max 100)
            offset: Offset for pagination
            start_date: Start date for filtering events
            end_date: End date for filtering events
            email: Filter by recipient email
            event: Filter by event type (e.g., 'delivered', 'opened', 'clicked', 'bounce')
            tags: Filter by tags
            sort: Sort order ('asc' or 'desc')
            
        Returns:
            Tuple of (list of normalized event dicts, total count)
        """
        try:
            # Format dates to ISO format if provided
            start_date_str = start_date.strftime("%Y-%m-%d") if start_date else None
            end_date_str = end_date.strftime("%Y-%m-%d") if end_date else None
            
            # Limit to max 100 per API requirements
            limit = min(limit, 100)
            
            logger.info(f"Fetching email events: limit={limit}, offset={offset}, start={start_date_str}, end={end_date_str}, email={email}, event={event}")
            
            def fetch():
                # Build kwargs dict, only including non-None values
                kwargs = {
                    'limit': limit,
                    'offset': offset,
                    'sort': sort
                }
                
                # Only add optional parameters if they have values
                if start_date_str:
                    kwargs['start_date'] = start_date_str
                if end_date_str:
                    kwargs['end_date'] = end_date_str
                if email:
                    kwargs['email'] = email
                if event:
                    kwargs['event'] = event
                if tags:
                    kwargs['tags'] = tags
                
                return self.transactional_api.get_email_event_report(**kwargs)
            
            response = self._retry_with_backoff(fetch)
            
            # Normalize the response
            events = []
            if hasattr(response, 'events') and response.events:
                for event_obj in response.events:
                    event_dict = event_obj.to_dict() if hasattr(event_obj, 'to_dict') else {}
                    
                    # Log first event for debugging
                    if len(events) == 0:
                        logger.info(f"Sample event data: {event_dict}")
                    
                    # Normalize the event data
                    # Note: Brevo API returns '_date' with underscore
                    normalized = {
                        'event': event_dict.get('event', 'unknown'),
                        'email': event_dict.get('email', 'N/A'),
                        'subject': event_dict.get('subject', 'N/A'),
                        'message_id': event_dict.get('message_id', 'N/A'),
                        'date': event_dict.get('_date') or event_dict.get('date', 'N/A'),
                        'tag': event_dict.get('tag', ''),
                        'template_id': event_dict.get('template_id'),
                        'reason': event_dict.get('reason', ''),
                        'link': event_dict.get('link', ''),
                    }
                    events.append(normalized)
            
            # Get total count - Brevo doesn't always provide this, so estimate
            total = len(events) + offset
            
            logger.info(f"Retrieved {len(events)} events")
            return events, total
            
        except ApiException as e:
            # Log detailed error information
            error_msg = f"Brevo API error: HTTP {e.status}"
            
            if hasattr(e, 'reason') and e.reason:
                error_msg += f" - {e.reason}"
            
            if hasattr(e, 'body') and e.body:
                try:
                    # Try to parse error body for more details
                    import json
                    error_body = json.loads(e.body) if isinstance(e.body, str) else e.body
                    if isinstance(error_body, dict) and 'message' in error_body:
                        error_msg += f" - {error_body['message']}"
                    logger.error(f"Error body: {error_body}")
                except:
                    logger.error(f"Error body: {e.body}")
            
            logger.error(error_msg)
            
            # Raise with more context
            raise Exception(f"Failed to fetch email events: {error_msg}") from e
        except Exception as e:
            logger.error(f"Unexpected error fetching email events: {str(e)}", exc_info=True)
            raise
    
    def get_email_content(self, uuid: str) -> Optional[Dict]:
        """
        Fetch detailed email content by UUID.
        
        Args:
            uuid: The email UUID
            
        Returns:
            Dictionary with email details or None if not found
        """
        try:
            logger.info(f"Fetching email content for UUID: {uuid}")
            
            def fetch():
                return self.transactional_api.get_transac_email_content(uuid)
            
            response = self._retry_with_backoff(fetch)
            
            # Convert to dict
            if hasattr(response, 'to_dict'):
                return response.to_dict()
            return None
            
        except ApiException as e:
            if e.status == 404:
                logger.warning(f"Email content not found for UUID: {uuid}")
                return None
            logger.error(f"API error fetching email content: {e.status} - {e.reason}")
            raise Exception(f"Failed to fetch email content: {e.reason}")
        except Exception as e:
            logger.error(f"Unexpected error fetching email content: {str(e)}")
            raise
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test the Brevo API connection.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Try to fetch just one event to test connectivity
            self.get_email_events(limit=1)
            return True, "Successfully connected to Brevo API"
        except Exception as e:
            return False, f"Failed to connect: {str(e)}"


def format_event_badge(event_type: str) -> str:
    """
    Generate a colored badge for an event type.
    
    Args:
        event_type: The event type string
        
    Returns:
        HTML string with colored badge
    """
    colors = {
        'request': '#6c757d',       # gray
        'delivered': '#22c55e',     # green
        'opened': '#3b82f6',        # blue
        'clicked': '#0ea5e9',       # cyan
        'hardBounce': '#ef4444',    # red
        'softBounce': '#f97316',    # orange
        'bounce': '#ef4444',        # red
        'blocked': '#dc2626',       # dark red
        'spam': '#7c2d12',          # brown
        'invalid': '#991b1b',       # dark red
        'deferred': '#f59e0b',      # amber
        'unsubscribed': '#6b7280',  # gray
        'error': '#991b1b',         # dark red
        'sent': '#10b981',          # emerald
    }
    
    color = colors.get(event_type.lower(), '#6c757d')
    return f'<span style="background-color: {color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; font-weight: 500;">{event_type}</span>'
