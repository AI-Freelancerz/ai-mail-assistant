"""
Brevo Email Status Client
Wrapper for Brevo API to fetch email event reports and transaction details.
Automatically updates suppression list with bounces, complaints, and blocks.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
try:
    import brevo_python as sib_api_v3_sdk
    from brevo_python.rest import ApiException
except ModuleNotFoundError:
    try:
        import sib_api_v3_sdk
        from sib_api_v3_sdk.rest import ApiException
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Brevo SDK not installed. Install 'brevo-python' or 'sib-api-v3-sdk'."
        ) from exc
from suppression_list_manager import get_suppression_manager
from campaign_cache import get_cache
import config

logger = logging.getLogger(__name__)


class BrevoStatusClient:
    """Client for fetching email status and events from Brevo API."""
    
    def __init__(self, api_key: str, use_cache: bool = True, cache_ttl_minutes: int = 15):
        """
        Initialize the Brevo status client.
        
        Args:
            api_key: Brevo API key
            use_cache: Enable caching to reduce API calls
            cache_ttl_minutes: Cache time-to-live in minutes
        """
        self.api_key = api_key
        self.use_cache = use_cache
        self.configuration = sib_api_v3_sdk.Configuration()
        self.configuration.api_key['api-key'] = api_key
        self.api_client = sib_api_v3_sdk.ApiClient(self.configuration)
        self.transactional_api = sib_api_v3_sdk.TransactionalEmailsApi(self.api_client)
        self.suppression_manager = get_suppression_manager()
        
        # Initialize cache if enabled
        if self.use_cache:
            self.cache = get_cache(cache_ttl_minutes=cache_ttl_minutes)
            logger.info(f"Cache enabled with TTL of {cache_ttl_minutes} minutes")
        else:
            self.cache = None
            logger.info("Cache disabled")
        
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
        
        # This should be unreachable, but if somehow we get here, raise the last exception
        logger.error(f"Unexpected: retry loop completed without return or exception after {max_retries} attempts")
        raise ApiException(status=500, reason="Retry loop exhausted without proper exception handling")
        
    def get_email_events(
        self,
        limit: int = 50,
        offset: int = 0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        email: Optional[str] = None,
        event: Optional[str] = None,
        tags: Optional[str] = None,
        sort: str = "desc",
        force_refresh: bool = False
    ) -> Tuple[List[Dict], int]:
        """
        Fetch email event reports from Brevo with caching.
        
        Args:
            limit: Maximum number of events to return (max 100)
            offset: Offset for pagination
            start_date: Start date for filtering events
            end_date: End date for filtering events
            email: Filter by recipient email
            event: Filter by event type (e.g., 'delivered', 'opened', 'clicked', 'bounce')
            tags: Filter by tags
            sort: Sort order ('asc' or 'desc')
            force_refresh: Force API fetch even if cache is fresh
            
        Returns:
            Tuple of (list of normalized event dicts, total count)
        """
        # Check cache first (only for date-range queries without specific filters)
        if (self.use_cache and self.cache and start_date and end_date and 
            not email and not event and not tags and not force_refresh):
            
            if self.cache.is_cache_fresh(start_date, end_date):
                logger.info("✅ Cache HIT: Using cached events (cache is fresh)")
                cached_events, cached_total = self.cache.get_cached_events(start_date, end_date)
                logger.info(f"   Retrieved {cached_total} events from cache")
                return cached_events, cached_total
            else:
                logger.info("❌ Cache MISS: Cache is stale or empty, fetching from API")
        
        # Fetch from API with smart pagination and rate limiting
        try:
            # Format dates to ISO format if provided
            # Brevo API only accepts date format (YYYY-MM-DD), not datetime
            start_date_str = start_date.strftime("%Y-%m-%d") if start_date else None
            end_date_str = end_date.strftime("%Y-%m-%d") if end_date else None
            
            # Limit to max 100 per API requirements
            limit = min(limit, 100)
            
            logger.info(f"Fetching email events from API: limit={limit}, offset={offset}, start={start_date_str}, end={end_date_str}")
            
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
            
            # Auto-update suppression list with problematic addresses
            self._update_suppression_from_events(events)
            
            # Note: Caching is now handled at the get_email_events_paginated() level
            # to avoid partial page caching issues
            
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
                except (ValueError, TypeError, json.JSONDecodeError) as parse_error:
                    logger.error(f"Error body (unparsed): {e.body}")
            
            logger.error(error_msg)
            
            # Raise with more context
            raise Exception(f"Failed to fetch email events: {error_msg}") from e
        except Exception as e:
            logger.error(f"Unexpected error fetching email events: {str(e)}", exc_info=True)
            raise
    
    def get_email_events_paginated(
        self,
        max_events: int = 500,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        email: Optional[str] = None,
        event: Optional[str] = None,
        tags: Optional[str] = None,
        sort: str = "desc",
        force_refresh: bool = False,
        pagination_delay: float = 0.6
    ) -> Tuple[List[Dict], int]:
        """
        Fetch email events with smart pagination and rate limiting.
        
        Args:
            max_events: Maximum total events to fetch
            start_date: Start date for filtering
            end_date: End date for filtering
            email: Filter by email
            event: Filter by event type
            tags: Filter by tags
            sort: Sort order
            force_refresh: Force API refresh
            pagination_delay: Delay between pagination requests (default 0.6s for safety)
            
        Returns:
            Tuple of (list of all events, total count)
        """
        logger.info(f"Fetching up to {max_events} events with pagination (delay={pagination_delay}s between pages)")
        
        # Check cache ONCE at this level (not per-page) to avoid pagination issues
        if (self.use_cache and self.cache and start_date and end_date and 
            not email and not event and not tags and not force_refresh):
            
            if self.cache.is_cache_fresh(start_date, end_date):
                logger.info("✅ Cache HIT: Using cached events (cache is fresh)")
                cached_events, cached_total = self.cache.get_cached_events(start_date, end_date)
                logger.info(f"   Retrieved {cached_total} events from cache")
                return cached_events, cached_total
            else:
                logger.info("❌ Cache MISS: Cache is stale or empty, fetching from API")
        
        # Fetch from API with pagination
        all_events = []
        page_offset = 0
        page_limit = 100  # Brevo API max per request
        
        while len(all_events) < max_events:
            # Fetch one page - use force_refresh=True to bypass cache at page level
            events_page, total = self.get_email_events(
                limit=page_limit,
                offset=page_offset,
                start_date=start_date,
                end_date=end_date,
                email=email,
                event=event,
                tags=tags,
                sort=sort,
                force_refresh=True  # Always bypass cache here - we already checked above
            )
            
            if not events_page:
                # No more events available
                logger.info("No more events available")
                break
            
            all_events.extend(events_page)
            logger.info(f"Fetched page at offset {page_offset}: {len(events_page)} events (total so far: {len(all_events)})")
            
            # If we got fewer events than requested, we've reached the end
            if len(events_page) < page_limit:
                logger.info("Reached end of available events")
                break
            
            page_offset += page_limit
            
            # Don't fetch more pages if we've hit our limit
            if page_offset >= max_events:
                logger.info(f"Reached max_events limit of {max_events}")
                break
            
            # Smart rate limiting: add delay between pagination requests
            # This prevents hitting rate limits proactively
            if page_offset < max_events and len(events_page) == page_limit:
                logger.debug(f"Pausing {pagination_delay}s before next page to avoid rate limiting")
                time.sleep(pagination_delay)
        
        # Store ALL fetched events in cache (if caching enabled)
        if self.use_cache and self.cache and start_date and end_date and all_events:
            from email_status_page import extract_message_batch
            self.cache.store_events(all_events, extract_message_batch)
            self.cache.update_cache_metadata(start_date, end_date)
            logger.info(f"Stored {len(all_events)} events in cache for future use")
        
        logger.info(f"Total events fetched: {len(all_events)}")
        return all_events, len(all_events)
    
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
    
    def _update_suppression_from_events(self, events: List[Dict]):
        """
        Automatically add problematic addresses to suppression list.

        Suppresses emails that:
        - Hard bounced (invalid address)
        - Spam complained
        - Blocked by ISP

        Args:
            events: List of email events
        """
        if not (config.EMAIL_AUTO_SUPPRESS_HARD_BOUNCE or 
                config.EMAIL_AUTO_SUPPRESS_COMPLAINTS or 
                config.EMAIL_AUTO_SUPPRESS_BLOCKS):
            return
        
        to_suppress = []
        
        for event in events:
            email = event.get('email', '').strip().lower()
            event_type = event.get('event', '').lower()
            reason = event.get('reason', '')
            message_id = event.get('message_id', '')
            
            if not email:
                continue
            
            # Hard bounces - invalid/non-existent email addresses
            if config.EMAIL_AUTO_SUPPRESS_HARD_BOUNCE and 'hardbounce' in event_type:
                to_suppress.append({
                    'email': email,
                    'reason': 'hardbounce',
                    'campaign_id': message_id,
                    'details': reason
                })
            
            # Spam complaints - user marked as spam
            elif config.EMAIL_AUTO_SUPPRESS_COMPLAINTS and 'spam' in event_type:
                to_suppress.append({
                    'email': email,
                    'reason': 'spam_complaint',
                    'campaign_id': message_id,
                    'details': reason
                })
            
            # Blocked by ISP or email provider
            elif config.EMAIL_AUTO_SUPPRESS_BLOCKS and 'blocked' in event_type:
                to_suppress.append({
                    'email': email,
                    'reason': 'blocked',
                    'campaign_id': message_id,
                    'details': reason
                })
            
            # Unsubscribed (optional, usually handled separately)
            elif 'unsubscribe' in event_type:
                to_suppress.append({
                    'email': email,
                    'reason': 'unsubscribed',
                    'campaign_id': message_id,
                    'details': 'User unsubscribed'
                })
        
        # Bulk add to suppression list
        if to_suppress:
            added, skipped = self.suppression_manager.add_bulk_to_suppression(to_suppress)
            if added > 0:
                logger.info(
                    f"[SUPPRESSION] Auto-suppressed {added} addresses from events "
                    f"(bounces/complaints/blocks)"
                )

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

