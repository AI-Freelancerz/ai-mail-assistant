"""
Email Status Page
Displays latest sent email activity from Brevo in a concise, stateless way.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
import logging
import os
import re
from brevo_python.rest import ApiException

from brevo_status_client import BrevoStatusClient
from translations import _t, set_language
from config import BREVO_API_KEY

logger = logging.getLogger(__name__)

def extract_message_batch(message_id: str) -> str:
    """
    Extract batch identifier from Brevo message_id.
    Example: <202511051257.97702503576.1@smtp-relay.mailin.fr> -> 202511051257.97702503576
    """
    match = re.match(r"<(\d+\.\d+)\.\d+@", message_id)
    if match:
        return match.group(1)
    return message_id  # Fallback to full message_id if pattern doesn't match

def is_soft_bounce_actually_invalid(bounce_reason: str) -> bool:
    """
    Check if a soft bounce reason indicates an actually invalid email.
    Some soft bounces are permanent failures that should be treated as invalid:
    - Connection timeout (domain doesn't exist or unreachable)
    - Domain not found
    - No mail server found for domain
    - Invalid recipient
    """
    if not bounce_reason:
        return False
    
    reason_lower = bounce_reason.lower()
    
    # Patterns that indicate truly invalid emails
    invalid_patterns = [
        "connection timeout",
        "domain not found",
        "no mail server",
        "invalid recipient",
        "recipient unknown",
        "user unknown",
        "mailbox not found",
        "address rejected",
        "does not exist",
        "no such user",
        "unrouteable address",
        "bad destination mailbox",
    ]
    
    return any(pattern in reason_lower for pattern in invalid_patterns)

def main():
    # IMPORTANT: Do NOT call st.set_page_config here (already set in parent streamlit_app.py)

    # Initialize session state for this page
    if "status_page_offset" not in st.session_state:
        st.session_state.status_page_offset = 0
    if "status_page_limit" not in st.session_state:
        st.session_state.status_page_limit = 50
    if "selected_campaign" not in st.session_state:
        st.session_state.selected_campaign = None
    if "exclude_filters" not in st.session_state:
        st.session_state.exclude_filters = ""
    if "include_filters" not in st.session_state:
        st.session_state.include_filters = ""
    if "time_filter" not in st.session_state:
        st.session_state.time_filter = "1h"  # Default to last hour

    # Apply language from main app if available
    if "language" in st.session_state:
        set_language(st.session_state.language)

    # Modern SaaS Dashboard CSS
    st.markdown(
        """
        <style>
        /* Global Dashboard Styles */
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 100%;
        }
        
        /* Fixed Left Sidebar for Campaign Tabs */
        div[data-testid="column"]:first-child {
            background: #fafafa;
            border-right: 1px solid #e5e7eb;
            padding: 0 !important;
            min-height: 500px;
        }
        
        /* Style Streamlit buttons to look like vertical tabs */
        div[data-testid="column"]:first-child button {
            background: white !important;
            border: none !important;
            border-left: 3px solid transparent !important;
            color: #374151 !important;
            font-weight: 400 !important;
            padding: 0.875rem 1rem !important;
            text-align: left !important;
            transition: all 0.2s ease !important;
            border-radius: 0 !important;
            box-shadow: none !important;
            margin-bottom: 1px !important;
            margin-top: 0 !important;
        }
        
        div[data-testid="column"]:first-child button:hover {
            background: #f3f4f6 !important;
            border-left-color: #9ca3af !important;
        }
        
        div[data-testid="column"]:first-child button[kind="primary"],
        div[data-testid="column"]:first-child button[data-baseweb="button"][kind="primary"] {
            background: #eff6ff !important;
            border-left-color: #3b82f6 !important;
            font-weight: 500 !important;
            color: #1e40af !important;
        }
        
        div[data-testid="column"]:first-child button[kind="primary"]:hover {
            background: #dbeafe !important;
            border-left-color: #2563eb !important;
        }
        
        /* Remove default Streamlit spacing in sidebar */
        div[data-testid="column"]:first-child > div {
            padding: 0 !important;
            margin: 0 !important;
            gap: 0 !important;
        }
        
        div[data-testid="column"]:first-child .element-container {
            padding: 0 !important;
            margin: 0 !important;
        }
        
        /* Date Divider Styling */
        .date-divider {
            font-size: 0.75rem;
            font-weight: 600;
            color: #374151;
            padding: 0.5rem;
            background: #e5e7eb;
            margin: 0;
            border-radius: 0;
        }
        
        /* Sidebar Scrollbar */
        .campaign-sidebar::-webkit-scrollbar {
            width: 5px;
        }
        
        .campaign-sidebar::-webkit-scrollbar-track {
            background: transparent;
        }
        
        .campaign-sidebar::-webkit-scrollbar-thumb {
            background: #cbd5e1;
            border-radius: 10px;
        }
        
        .campaign-sidebar::-webkit-scrollbar-thumb:hover {
            background: #94a3b8;
        }
        
        /* Main Content Panel */
        .main-panel {
            padding-left: 2rem;
        }
        
        .campaign-title {
            font-size: 1.75rem;
            font-weight: 600;
            color: #111827;
            margin-bottom: 0.5rem;
            line-height: 1.2;
        }
        
        .campaign-meta {
            font-size: 0.875rem;
            color: #6b7280;
            margin-bottom: 2rem;
            display: flex;
            gap: 1rem;
            align-items: center;
        }
        
        /* KPI Tiles */
        .kpi-container {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 1rem;
            margin-bottom: 2rem;
        }
        
        .kpi-tile {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 1.25rem;
            transition: all 0.2s ease;
        }
        
        .kpi-tile:hover {
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            border-color: #cbd5e1;
        }
        
        .kpi-header {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.75rem;
        }
        
        .kpi-icon {
            font-size: 1.25rem;
        }
        
        .kpi-label {
            font-size: 0.8rem;
            font-weight: 500;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.025em;
        }
        
        .kpi-value {
            font-size: 2rem;
            font-weight: 700;
            color: #111827;
            margin-bottom: 0.5rem;
            line-height: 1;
        }
        
        .kpi-progress-bar {
            width: 100%;
            height: 4px;
            background: #e5e7eb;
            border-radius: 2px;
            overflow: hidden;
            margin-bottom: 0.25rem;
        }
        
        .kpi-progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #3b82f6, #2563eb);
            border-radius: 2px;
            transition: width 0.3s ease;
        }
        
        .kpi-progress-fill.success {
            background: linear-gradient(90deg, #10b981, #059669);
        }
        
        .kpi-progress-fill.warning {
            background: linear-gradient(90deg, #f59e0b, #d97706);
        }
        
        .kpi-progress-fill.danger {
            background: linear-gradient(90deg, #ef4444, #dc2626);
        }
        
        .kpi-percentage {
            font-size: 0.75rem;
            color: #6b7280;
        }
        
        /* Activity Table Section */
        .activity-section {
            margin-top: 2rem;
        }
        
        .activity-header {
            font-size: 1.125rem;
            font-weight: 600;
            color: #111827;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .activity-table-container {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            overflow: hidden;
        }
        
        /* Responsive adjustments */
        @media (max-width: 1400px) {
            .kpi-container {
                grid-template-columns: repeat(3, 1fr);
            }
        }
        
        @media (max-width: 900px) {
            .kpi-container {
                grid-template-columns: repeat(2, 1fr);
            }
        }
        
        /* Remove default Streamlit padding */
        .element-container {
            margin-bottom: 0 !important;
        }
        
        /* Clean dataframe styling */
        .stDataFrame {
            border: none !important;
        }
        
        .stDataFrame > div {
            border: none !important;
        }
        
        /* Dataframe cell styling */
        .stDataFrame [data-testid="stDataFrameResizable"] tbody td {
            vertical-align: middle !important;
            padding: 8px !important;
        }
        
        /* Make Clicked Links column compact but readable */
        .stDataFrame [data-testid="stDataFrameResizable"] tbody tr td:nth-child(6),
        .stDataFrame [data-testid="stDataFrameResizable"] thead tr th:nth-child(6) {
            max-width: 150px !important;
            min-width: 80px !important;
            text-align: center !important;
        }
        
        /* Make checkmark columns compact */
        .stDataFrame [data-testid="stDataFrameResizable"] tbody tr td:nth-child(3),
        .stDataFrame [data-testid="stDataFrameResizable"] tbody tr td:nth-child(4),
        .stDataFrame [data-testid="stDataFrameResizable"] tbody tr td:nth-child(5),
        .stDataFrame [data-testid="stDataFrameResizable"] thead tr th:nth-child(3),
        .stDataFrame [data-testid="stDataFrameResizable"] thead tr th:nth-child(4),
        .stDataFrame [data-testid="stDataFrameResizable"] thead tr th:nth-child(5) {
            max-width: 80px !important;
            min-width: 60px !important;
            text-align: center !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Header
    st.title("📧 " + _t("Email Status Dashboard"))
    st.markdown(_t("View latest email activity from Brevo. Data is fetched live on each refresh."))
    
    # Time range filter
    time_filter_col1, time_filter_col2 = st.columns([3, 1])
    with time_filter_col1:
        time_options = {
            "1h": _t("Last hour"),
            "24h": _t("Last 24 hours"),
            "48h": _t("Last 48 hours"),
            "7days": _t("Last 7 days"),
            "3months": _t("Last 3 months")
        }
        selected_time = st.radio(
            _t("Time Range"),
            options=list(time_options.keys()),
            format_func=lambda x: time_options[x],
            horizontal=True,
            key="time_filter_radio",
            index=list(time_options.keys()).index(st.session_state.time_filter)
        )
        if selected_time != st.session_state.time_filter:
            st.session_state.time_filter = selected_time
            st.rerun()

    # --- NEW: View Options for Filtering ---
    with st.expander(_t("⚙️ View Options & Filters")):
        st.info(_t("Exclude test emails or filter to specific campaigns. This does not delete any data."))
        
        col_exclude, col_include = st.columns(2)
        
        with col_exclude:
            st.markdown("**" + _t("Exclusion Filter") + "**")
            new_exclude_filters = st.text_area(
                _t("Exclude items containing:"),
                value=st.session_state.exclude_filters,
                placeholder=_t("e.g., @mycompany.com, test@example.com, [TEST]"),
                help=_t("Enter comma-separated email addresses, domains, or subject keywords to exclude."),
                key="exclude_input"
            )
        
        with col_include:
            st.markdown("**" + _t("Inclusion Filter") + "**")
            new_include_filters = st.text_area(
                _t("Include only items containing:"),
                value=st.session_state.include_filters,
                placeholder=_t("e.g., [PROD], newsletter, @client.com"),
                help=_t("Enter comma-separated email addresses, domains, or subject keywords. Only matching items will be shown."),
                key="include_input"
            )

        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            if st.button(_t("Apply Filters"), use_container_width=True, type="primary"):
                st.session_state.exclude_filters = new_exclude_filters
                st.session_state.include_filters = new_include_filters
                st.rerun()
        with filter_col2:
            if st.button(_t("Clear Filters"), use_container_width=True):
                st.session_state.exclude_filters = ""
                st.session_state.include_filters = ""
                st.rerun()
    # --- END NEW ---

    # Check for Brevo API key with better validation
    if not BREVO_API_KEY or BREVO_API_KEY.strip() == "":
        st.error(_t("❌ Brevo API key not found in configuration"))
        st.warning(_t("Please configure your Brevo API key to use this feature."))
        
        with st.expander(_t("📖 How to configure")):
            st.markdown("""
            **Option 1: Using Streamlit Secrets (Recommended for production)**
            
            Create or edit `.streamlit/secrets.toml`:
            ```toml
            BREVO_API_KEY = "xkeysib-your-api-key-here"
            ```
            
            **Option 2: Using Environment Variable**
            
            Set environment variable before running:
            ```bash
            export BREVO_API_KEY="xkeysib-your-api-key-here"  # Linux/Mac
            set BREVO_API_KEY=xkeysib-your-api-key-here       # Windows
            ```
            
            **Option 3: Using .env file**
            
            Create `.env` file:
            ```
            BREVO_API_KEY=xkeysib-your-api-key-here
            ```
            
            **How to get your Brevo API key:**
            1. Log in to your Brevo account
            2. Go to Settings → SMTP & API → API Keys
            3. Create a new API key or copy an existing one
            4. Make sure it has permission to access "Email Campaigns"
            """)
        
        st.stop()

    # Validate API key format
    if not BREVO_API_KEY.startswith("xkeysib-"):
        st.warning(_t("⚠️ API key format looks unusual. Brevo API keys typically start with 'xkeysib-'"))

    # Initialize client with error handling
    try:
        client = BrevoStatusClient(BREVO_API_KEY)
    except Exception as e:
        st.error(_t("❌ Failed to initialize Brevo client: ") + str(e))
        logger.error(f"Failed to initialize BrevoStatusClient: {str(e)}", exc_info=True)
        st.stop()

    # Set date range based on time filter
    # Use UTC timezone for proper comparison with Brevo API timestamps
    now_utc = datetime.now(timezone.utc)
    
    if st.session_state.time_filter == "1h":
        start_date = now_utc - timedelta(hours=1)
        # For short time ranges, fetch today's and yesterday's events
        api_start_date = (now_utc - timedelta(days=1)).replace(tzinfo=None)
    elif st.session_state.time_filter == "24h":
        start_date = now_utc - timedelta(hours=24)
        # Fetch last 2 days to cover timezone differences
        api_start_date = (now_utc - timedelta(days=2)).replace(tzinfo=None)
    elif st.session_state.time_filter == "48h":
        start_date = now_utc - timedelta(hours=48)
        # Fetch last 3 days to cover timezone differences
        api_start_date = (now_utc - timedelta(days=3)).replace(tzinfo=None)
    elif st.session_state.time_filter == "7days":
        start_date = now_utc - timedelta(days=7)
        # Fetch 8 days to cover timezone differences
        api_start_date = (now_utc - timedelta(days=8)).replace(tzinfo=None)
    else:  # 3months
        start_date = now_utc - timedelta(days=90)
        # For 3 months, use exactly 90 days (Brevo's maximum)
        api_start_date = (now_utc - timedelta(days=90)).replace(tzinfo=None)
    
    end_date = now_utc
    api_end_date = end_date.replace(tzinfo=None)
    
    # Adjust limit based on time range to ensure we fetch all events
    # Brevo API maximum is 500 events per request
    if st.session_state.time_filter == "1h":
        limit = 100  # 1 hour, 100 should be enough
    elif st.session_state.time_filter == "24h":
        limit = 300  # 24 hours, need more
    elif st.session_state.time_filter == "48h":
        limit = 500  # 48 hours, need even more (API max)
    elif st.session_state.time_filter == "7days":
        limit = 500  # 7 days, use API maximum
    else:  # 3months
        limit = 500  # 3 months, use API maximum
    
    event_filter = None
    email_search = None

    # Main content
    try:
        with st.spinner(_t("Fetching email events from Brevo...")):
            # Fetch events with pagination to get all data
            # Brevo API limit is 100 per request, so we need to paginate for longer time ranges
            all_events = []
            page_offset = 0
            page_limit = 100  # Max per Brevo API
            max_events = limit  # Total events we want
            
            # Keep fetching until we have enough or no more events
            while len(all_events) < max_events:
                events_page, total = client.get_email_events(
                    limit=page_limit,
                    offset=page_offset,
                    start_date=api_start_date,
                    end_date=api_end_date,
                    email=email_search if email_search else None,
                    event=event_filter,
                    sort="desc",
                )
                
                if not events_page:
                    # No more events available
                    break
                
                all_events.extend(events_page)
                
                # If we got fewer events than requested, we've reached the end
                if len(events_page) < page_limit:
                    break
                
                page_offset += page_limit
                
                # Safety check: don't fetch more than 1000 events total
                if page_offset >= 1000:
                    st.warning(_t("⚠️ Stopped at 1000 events to avoid excessive API calls. Use filters for more specific results."))
                    break
            
            events = all_events

        # --- NEW: Filter events by exact time range (client-side filtering) ---
        # This is needed because Brevo API only accepts date, not datetime
        # Strategy: Filter by SEND time (request/delivered events), not by any activity
        # Then include ALL events for those message_ids to maintain data consistency
        
        # Step 1: Find message_ids where the email was SENT in the time range
        # We look for 'request' or 'delivered' events as these indicate send time
        message_ids_in_range = set()
        for event in events:
            event_type_raw = event.get("event", "").lower()
            
            # Only check send-related events (request or delivered)
            if event_type_raw not in ['request', 'requests', 'delivered']:
                continue
            
            event_date_str = event.get("date", "")
            if event_date_str:
                try:
                    # Parse the event date - Brevo returns ISO format like "2025-11-06T14:30:45.000Z"
                    if 'T' in event_date_str:
                        # Parse ISO format with timezone
                        if event_date_str.endswith('Z'):
                            # Z means UTC
                            event_datetime = datetime.fromisoformat(event_date_str.replace('Z', '+00:00'))
                        elif '+' in event_date_str or event_date_str.count('-') > 2:
                            # Has timezone offset
                            event_datetime = datetime.fromisoformat(event_date_str)
                        else:
                            # No timezone, assume UTC
                            event_datetime = datetime.fromisoformat(event_date_str).replace(tzinfo=timezone.utc)
                    else:
                        # If only date, assume midnight UTC
                        event_datetime = datetime.strptime(event_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    
                    # Ensure event_datetime has timezone info
                    if event_datetime.tzinfo is None:
                        event_datetime = event_datetime.replace(tzinfo=timezone.utc)
                    
                    # Check if email was sent within our time range
                    if start_date <= event_datetime <= end_date:
                        message_ids_in_range.add(event.get("message_id"))
                except (ValueError, AttributeError) as e:
                    # If we can't parse the date, include this message_id to be safe
                    logger.warning(f"Could not parse event date '{event_date_str}': {e}")
                    message_ids_in_range.add(event.get("message_id"))
        
        # Step 2: Include ALL events for message_ids that were sent in the time range
        filtered_by_time = [event for event in events if event.get("message_id") in message_ids_in_range]
        
        # Log filtering results for debugging
        logger.info(f"Time filter '{st.session_state.time_filter}': {len(events)} events fetched from API, "
                   f"{len(message_ids_in_range)} unique emails sent in range, "
                   f"{len(filtered_by_time)} total events after filtering")
        logger.info(f"Time range: {start_date.isoformat()} to {end_date.isoformat()}")
        
        events = filtered_by_time
        # --- END NEW ---

        # --- NEW: Filter out excluded events ---
        if st.session_state.exclude_filters or st.session_state.include_filters:
            excluded_count = 0
            included_count = 0
            original_count = len(events)
            
            # Parse filters from the text areas
            exclude_filters = [f.strip().lower() for f in st.session_state.exclude_filters.split(',') if f.strip()]
            include_filters = [f.strip().lower() for f in st.session_state.include_filters.split(',') if f.strip()]
            
            filtered_events = []
            for event in events:
                email_lower = event.get("email", "").lower()
                subject_lower = event.get("subject", "").lower()
                
                # Check inclusion filter first (if specified, must match)
                if include_filters:
                    is_included = False
                    for f in include_filters:
                        if (f.startswith('@') and email_lower.endswith(f)) or \
                           (f in email_lower) or \
                           (f in subject_lower):
                            is_included = True
                            break
                    
                    if not is_included:
                        included_count += 1
                        continue  # Skip this event
                
                # Check exclusion filter
                is_excluded = False
                for f in exclude_filters:
                    if (f.startswith('@') and email_lower.endswith(f)) or \
                       (f in email_lower) or \
                       (f in subject_lower):
                        is_excluded = True
                        break
                
                if not is_excluded:
                    filtered_events.append(event)
                else:
                    excluded_count += 1
            
            events = filtered_events  # Overwrite with the filtered list
            
            if excluded_count > 0 or included_count > 0:
                filter_msg = []
                if excluded_count > 0:
                    filter_msg.append(_t("Excluded: {count}", count=excluded_count))
                if included_count > 0:
                    filter_msg.append(_t("Filtered by inclusion: {count}", count=included_count))
                st.toast(" | ".join(filter_msg))
        # --- END NEW ---

        if events:
            st.markdown("### " + _t("Summary"))

            # Group by message_id
            email_data = {}
            for event in events:
                msg_id = event["message_id"]
                if msg_id not in email_data:
                    email_data[msg_id] = {
                        "message_id": msg_id,
                        "email": event["email"],
                        "subject": event["subject"],
                        "tag": event["tag"],
                        "requests": 0,
                        "delivered": 0,
                        "opened": 0,
                        "clicks": 0,
                        "hardBounces": 0,
                        "softBounces": 0,
                        "blocked": 0,
                        "spam": 0,
                        "deferred": 0,
                        "unsubscribed": 0,
                        "error": 0,
                        "last_event": "",
                        "last_event_date": "",
                        "send_date": "",  # Track earliest send date for sorting
                        "bounce_reason": "",  # Track bounce reason for debugging
                        "click_links": [],
                    }

                # Normalize event type to canonical form
                event_type_raw = event["event"]
                event_type_lower = event_type_raw.lower() if event_type_raw else ""
                
                # Map all variations to canonical event types
                event_type_map = {
                    'request': 'requests',
                    'requests': 'requests',
                    'delivered': 'delivered',
                    'open': 'opened',
                    'opened': 'opened',
                    'click': 'clicks',
                    'clicks': 'clicks',
                    'hard_bounce': 'hardBounces',
                    'hardbounce': 'hardBounces',
                    'hardbounces': 'hardBounces',
                    'soft_bounce': 'softBounces',
                    'softbounce': 'softBounces',
                    'softbounces': 'softBounces',
                    'blocked': 'blocked',
                    'spam': 'spam',
                    'deferred': 'deferred',
                    'unsubscribed': 'unsubscribed',
                    'unsubscribe': 'unsubscribed',
                    'error': 'error',
                }
                
                event_type = event_type_map.get(event_type_lower, event_type_raw)
                
                # Count each event type
                if event_type in email_data[msg_id]:
                    email_data[msg_id][event_type] += 1

                # Track most recent event - compare dates safely
                current_date = event["date"]
                last_date = email_data[msg_id]["last_event_date"]
                
                # Update if this is the first event or if current is newer
                if not last_date or (current_date and current_date > last_date):
                    email_data[msg_id]["last_event"] = event_type_raw
                    email_data[msg_id]["last_event_date"] = current_date
                
                # Track earliest send date (request or delivered events)
                if event_type in ('requests', 'delivered'):
                    if not email_data[msg_id]["send_date"] or (current_date and current_date < email_data[msg_id]["send_date"]):
                        email_data[msg_id]["send_date"] = current_date

                # Track clicked links
                if event_type == "clicks" and event.get("link"):
                    email_data[msg_id]["click_links"].append(event["link"])
                
                # Track bounce reason for hard and soft bounces
                if event_type in ('hardBounces', 'softBounces', 'blocked') and event.get("reason"):
                    if not email_data[msg_id]["bounce_reason"]:  # Keep first reason
                        email_data[msg_id]["bounce_reason"] = event["reason"]

            # Always group by message batch
            grouped_data = {}
            for msg_id, data in email_data.items():
                group_key = extract_message_batch(msg_id)
                if group_key not in grouped_data:
                    grouped_data[group_key] = {
                        "group_key": group_key,
                        "subject": data["subject"],
                        "tag": data["tag"],
                        "recipients": [],
                        "total_sent": 0,
                        "total_delivered": 0,
                        "total_opened": 0,
                        "total_clicks": 0,
                        "total_hardBounces": 0,
                        "total_softBounces": 0,
                        "total_blocked": 0,
                        "total_spam": 0,
                        "total_deferred": 0,
                        "last_event_date": "",
                        "send_date": "",  # Earliest send date for this campaign
                    }

                grouped_data[group_key]["recipients"].append(data)
                grouped_data[group_key]["total_sent"] += 1
                grouped_data[group_key]["total_delivered"] += 1 if data["delivered"] > 0 else 0
                grouped_data[group_key]["total_opened"] += 1 if data["opened"] > 0 else 0
                grouped_data[group_key]["total_clicks"] += 1 if data["clicks"] > 0 else 0
                grouped_data[group_key]["total_hardBounces"] += 1 if data["hardBounces"] > 0 else 0
                grouped_data[group_key]["total_softBounces"] += 1 if data["softBounces"] > 0 else 0
                grouped_data[group_key]["total_blocked"] += 1 if data["blocked"] > 0 else 0
                grouped_data[group_key]["total_spam"] += 1 if data["spam"] > 0 else 0
                grouped_data[group_key]["total_deferred"] += 1 if data["deferred"] > 0 else 0

                # Update last event date
                if data["last_event_date"] and (
                    not grouped_data[group_key]["last_event_date"]
                    or data["last_event_date"] > grouped_data[group_key]["last_event_date"]
                ):
                    grouped_data[group_key]["last_event_date"] = data["last_event_date"]
                
                # Update send date (earliest)
                if data["send_date"]:
                    if not grouped_data[group_key]["send_date"] or data["send_date"] < grouped_data[group_key]["send_date"]:
                        grouped_data[group_key]["send_date"] = data["send_date"]

            # Overall metrics
            total_emails = len(email_data)
            total_delivered = sum(1 for e in email_data.values() if e["delivered"] > 0)
            total_opened = sum(1 for e in email_data.values() if e["opened"] > 0)
            total_clicked = sum(1 for e in email_data.values() if e["clicks"] > 0)
            # Invalid = hard bounces OR soft bounces with invalid reasons (like connection timeout)
            total_invalid = sum(1 for e in email_data.values() 
                              if (e["hardBounces"] > 0 or 
                                  (e["softBounces"] > 0 and is_soft_bounce_actually_invalid(e["bounce_reason"]))))
            # Failed = blocked, errors, or soft bounces (excluding those that are actually invalid)
            total_failed = sum(1 for e in email_data.values() 
                             if ((e["blocked"] > 0 or e["error"] > 0 or 
                                  (e["softBounces"] > 0 and not is_soft_bounce_actually_invalid(e["bounce_reason"]))) 
                                 and e["hardBounces"] == 0))

            # Create two rows: first row with 3 cols, second row with 3 cols
            row1_col1, row1_col2, row1_col3 = st.columns(3, gap="medium")
            with row1_col1:
                st.markdown(
                    f"""
                    <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1.25rem; text-align: center; margin-bottom: 1rem; min-height: 180px; display: flex; flex-direction: column; justify-content: center;">
                        <div style="font-size: 1.5rem;">📧</div>
                        <div style="font-size: 0.875rem; color: #6b7280; margin-bottom: 0.5rem;">{_t("Total Recipients")}</div>
                        <div style="font-size: 1.75rem; font-weight: 700;">{total_emails}</div>
                        <div style="font-size: 0.75rem; color: transparent; margin-top: 0.25rem; user-select: none;">-</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            with row1_col2:
                delivery_rate = f"{(total_delivered/total_emails*100):.1f}%" if total_emails > 0 else "N/A"
                st.markdown(
                    f"""
                    <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1.25rem; text-align: center; margin-bottom: 1rem; min-height: 180px; display: flex; flex-direction: column; justify-content: center;">
                        <div style="font-size: 1.5rem;">✅</div>
                        <div style="font-size: 0.875rem; color: #6b7280; margin-bottom: 0.5rem;">{_t("Delivered")}</div>
                        <div style="font-size: 1.75rem; font-weight: 700;">{total_delivered}</div>
                        <div style="font-size: 0.75rem; color: #10b981; margin-top: 0.25rem;">{delivery_rate}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            with row1_col3:
                open_rate = f"{(total_opened/total_delivered*100):.1f}%" if total_delivered > 0 else "N/A"
                st.markdown(
                    f"""
                    <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1.25rem; text-align: center; margin-bottom: 1rem; min-height: 180px; display: flex; flex-direction: column; justify-content: center;">
                        <div style="font-size: 1.5rem;">📖</div>
                        <div style="font-size: 0.875rem; color: #6b7280; margin-bottom: 0.5rem;">{_t("Opened")}</div>
                        <div style="font-size: 1.75rem; font-weight: 700;">{total_opened}</div>
                        <div style="font-size: 0.75rem; color: #10b981; margin-top: 0.25rem;">{open_rate}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            
            row2_col1, row2_col2, row2_col3 = st.columns(3, gap="medium")
            with row2_col1:
                click_rate = f"{(total_clicked/total_delivered*100):.1f}%" if total_delivered > 0 else "N/A"
                st.markdown(
                    f"""
                    <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1.25rem; text-align: center; min-height: 180px; display: flex; flex-direction: column; justify-content: center;">
                        <div style="font-size: 1.5rem;">🔗</div>
                        <div style="font-size: 0.875rem; color: #6b7280; margin-bottom: 0.5rem;">{_t("Clicked")}</div>
                        <div style="font-size: 1.75rem; font-weight: 700;">{total_clicked}</div>
                        <div style="font-size: 0.75rem; color: #3b82f6; margin-top: 0.25rem;">{click_rate}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            with row2_col2:
                invalid_rate = f"{(total_invalid/total_emails*100):.1f}%" if total_emails > 0 else "N/A"
                st.markdown(
                    f"""
                    <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1.25rem; text-align: center; min-height: 180px; display: flex; flex-direction: column; justify-content: center;">
                        <div style="font-size: 1.5rem;">🚫</div>
                        <div style="font-size: 0.875rem; color: #6b7280; margin-bottom: 0.5rem;">{_t("Invalid Email")}</div>
                        <div style="font-size: 1.75rem; font-weight: 700;">{total_invalid}</div>
                        <div style="font-size: 0.75rem; color: #ef4444; margin-top: 0.25rem;">{invalid_rate}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            with row2_col3:
                failed_rate = f"{(total_failed/total_emails*100):.1f}%" if total_emails > 0 else "N/A"
                st.markdown(
                    f"""
                    <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1.25rem; text-align: center; min-height: 180px; display: flex; flex-direction: column; justify-content: center;">
                        <div style="font-size: 1.5rem;">❌</div>
                        <div style="font-size: 0.875rem; color: #6b7280; margin-bottom: 0.5rem;">{_t("Failed")}</div>
                        <div style="font-size: 1.75rem; font-weight: 700;">{total_failed}</div>
                        <div style="font-size: 0.75rem; color: #f59e0b; margin-top: 0.25rem;">{failed_rate}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            st.markdown("---")

            # Sort campaigns by send date (newest first)
            # Use send_date (earliest send time) instead of last_event_date for proper chronological order
            sorted_campaigns = sorted(
                grouped_data.items(),
                key=lambda x: x[1]["send_date"] if x[1]["send_date"] else x[1]["last_event_date"] if x[1]["last_event_date"] else "",
                reverse=True
            )
            
            # Group campaigns by date
            campaigns_by_date = {}
            for group_key, group in sorted_campaigns:
                # Use send_date if available, fallback to last_event_date
                date_str = group["send_date"] if group["send_date"] else group["last_event_date"]
                if date_str and date_str != "N/A":
                    try:
                        if "T" in date_str or "+" in date_str or "Z" in date_str:
                            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        else:
                            dt = datetime.fromtimestamp(float(date_str))
                        date_key = dt.strftime("%Y-%m-%d")
                    except Exception:
                        date_key = "Unknown"
                else:
                    date_key = "Unknown"
                
                if date_key not in campaigns_by_date:
                    campaigns_by_date[date_key] = []
                campaigns_by_date[date_key].append((group_key, group))

            # Initialize selection to first campaign if not set
            if st.session_state.selected_campaign not in grouped_data:
                if sorted_campaigns:
                    st.session_state.selected_campaign = sorted_campaigns[0][0]

            # Main dashboard layout: Sidebar + Content Panel
            tab1, tab2 = st.tabs([_t("📊 Campaign Dashboard"), _t("📥 Download Report")])
            
            with tab1:
                # Create two columns: fixed sidebar and main content
                sidebar_col, main_col = st.columns([1, 3])

                # === LEFT SIDEBAR: Campaign Tabs ===
                with sidebar_col:
                    # Display campaigns grouped by date
                    for date_key in sorted(campaigns_by_date.keys(), reverse=True):
                        st.markdown(f'<div class="date-divider">📅 {date_key}</div>', unsafe_allow_html=True)
                        
                        for group_key, group in campaigns_by_date[date_key]:
                            is_selected = st.session_state.selected_campaign == group_key
                            
                            # Create campaign tab button
                            if st.button(
                                group["subject"][:60] + ("..." if len(group["subject"]) > 60 else ""),
                                key=f"campaign_tab_{group_key}",
                                help=group["subject"],
                                use_container_width=True,
                                type="primary" if is_selected else "secondary"
                            ):
                                st.session_state.selected_campaign = group_key
                                st.rerun()

                # === MAIN CONTENT PANEL ===
                with main_col:
                    if st.session_state.selected_campaign and st.session_state.selected_campaign in grouped_data:
                        group = grouped_data[st.session_state.selected_campaign]
                        group_key = st.session_state.selected_campaign
                        
                        st.markdown('<div class="main-panel">', unsafe_allow_html=True)
                        
                        # === Campaign Title & Metadata with Refresh Button ===
                        title_col, refresh_col = st.columns([10, 1])
                        with title_col:
                            st.markdown(f'<div class="campaign-title">{group["subject"]}</div>', unsafe_allow_html=True)
                        with refresh_col:
                            if st.button("🔄", key=f"refresh_{group_key}", help=_t("Refresh Data"), type="primary"):
                                st.rerun()
                        
                        # Format timestamp
                        date_str = group["last_event_date"]
                        if date_str and date_str != "N/A":
                            try:
                                if "T" in date_str or "+" in date_str or "Z" in date_str:
                                    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                                else:
                                    dt = datetime.fromtimestamp(float(date_str))
                                date_str = dt.strftime("%Y-%m-%d %H:%M")
                            except Exception:
                                pass
                        
                        meta_html = f'<div class="campaign-meta">'
                        meta_html += f'<span>🕐 {date_str}</span>'
                        meta_html += f'<span>·</span>'
                        meta_html += f'<span>Batch: <code>{group_key}</code></span>'
                        if group['tag']:
                            meta_html += f'<span>·</span><span>Tag: {group["tag"]}</span>'
                        meta_html += '</div>'
                        st.markdown(meta_html, unsafe_allow_html=True)
                        
                        # === KPI Tiles ===
                        # Calculate metrics
                        # Invalid = hard bounces OR soft bounces with invalid reasons (like connection timeout)
                        soft_bounces_invalid = sum(1 for r in group["recipients"] 
                                                  if r["softBounces"] > 0 and is_soft_bounce_actually_invalid(r["bounce_reason"]))
                        invalid = group["total_hardBounces"] + soft_bounces_invalid
                        # Failed = blocked + soft bounces (excluding those that are actually invalid)
                        soft_bounces_failed = group["total_softBounces"] - soft_bounces_invalid
                        failed_other = group["total_blocked"] + soft_bounces_failed
                        total_failures = invalid + failed_other
                        
                        sent_pct = 100
                        delivered_pct = (group['total_delivered']/group['total_sent']*100) if group['total_sent'] > 0 else 0
                        invalid_pct = (invalid/group['total_sent']*100) if group['total_sent'] > 0 else 0
                        failed_other_pct = (failed_other/group['total_sent']*100) if group['total_sent'] > 0 else 0
                        opened_pct = (group['total_opened']/group['total_delivered']*100) if group['total_delivered'] > 0 else 0
                        clicked_pct = (group['total_clicks']/group['total_delivered']*100) if group['total_delivered'] > 0 else 0
                        
                        # Create first row with 3 KPI tiles
                        kpi_row1 = st.columns(3, gap="medium")
                        
                        # Sent KPI
                        with kpi_row1[0]:
                            st.markdown(
                                f"""
                                <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1.25rem; margin-bottom: 1rem;">
                                    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;">
                                        <span style="font-size: 1.25rem;">📧</span>
                                        <span style="font-size: 0.8rem; font-weight: 500; color: #6b7280; text-transform: uppercase;">{_t("Sent")}</span>
                                    </div>
                                    <div style="font-size: 2rem; font-weight: 700; color: #111827; margin-bottom: 0.5rem;">{group["total_sent"]}</div>
                                    <div style="width: 100%; height: 4px; background: #e5e7eb; border-radius: 2px; overflow: hidden; margin-bottom: 0.25rem;">
                                        <div style="height: 100%; width: {sent_pct}%; background: linear-gradient(90deg, #3b82f6, #2563eb); border-radius: 2px;"></div>
                                    </div>
                                    <div style="font-size: 0.75rem; color: #6b7280;">{sent_pct:.0f}%</div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                        
                        # Delivered KPI
                        with kpi_row1[1]:
                            st.markdown(
                                f"""
                                <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1.25rem; margin-bottom: 1rem;">
                                    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;">
                                        <span style="font-size: 1.25rem;">✅</span>
                                        <span style="font-size: 0.8rem; font-weight: 500; color: #6b7280; text-transform: uppercase;">{_t("Delivered")}</span>
                                    </div>
                                    <div style="font-size: 2rem; font-weight: 700; color: #111827; margin-bottom: 0.5rem;">{group["total_delivered"]}</div>
                                    <div style="width: 100%; height: 4px; background: #e5e7eb; border-radius: 2px; overflow: hidden; margin-bottom: 0.25rem;">
                                        <div style="height: 100%; width: {delivered_pct}%; background: linear-gradient(90deg, #10b981, #059669); border-radius: 2px;"></div>
                                    </div>
                                    <div style="font-size: 0.75rem; color: #6b7280;">{delivered_pct:.0f}%</div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                        
                        # Read KPI
                        with kpi_row1[2]:
                            st.markdown(
                                f"""
                                <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1.25rem; margin-bottom: 1rem;">
                                    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;">
                                        <span style="font-size: 1.25rem;">📖</span>
                                        <span style="font-size: 0.8rem; font-weight: 500; color: #6b7280; text-transform: uppercase;">{_t("Read")}</span>
                                    </div>
                                    <div style="font-size: 2rem; font-weight: 700; color: #111827; margin-bottom: 0.5rem;">{group["total_opened"]}</div>
                                    <div style="width: 100%; height: 4px; background: #e5e7eb; border-radius: 2px; overflow: hidden; margin-bottom: 0.25rem;">
                                        <div style="height: 100%; width: {opened_pct}%; background: linear-gradient(90deg, #10b981, #059669); border-radius: 2px;"></div>
                                    </div>
                                    <div style="font-size: 0.75rem; color: #6b7280;">{opened_pct:.0f}% {_t("of delivered")}</div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                        
                        # Create second row with 3 KPI tiles
                        kpi_row2 = st.columns(3, gap="medium")
                        
                        # Invalid Email KPI
                        with kpi_row2[0]:
                            st.markdown(
                                f"""
                                <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1.25rem;">
                                    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;">
                                        <span style="font-size: 1.25rem;">🚫</span>
                                        <span style="font-size: 0.8rem; font-weight: 500; color: #6b7280; text-transform: uppercase;">{_t("Invalid Email")}</span>
                                    </div>
                                    <div style="font-size: 2rem; font-weight: 700; color: #111827; margin-bottom: 0.5rem;">{invalid}</div>
                                    <div style="width: 100%; height: 4px; background: #e5e7eb; border-radius: 2px; overflow: hidden; margin-bottom: 0.25rem;">
                                        <div style="height: 100%; width: {invalid_pct}%; background: linear-gradient(90deg, #ef4444, #dc2626); border-radius: 2px;"></div>
                                    </div>
                                    <div style="font-size: 0.75rem; color: #6b7280;">{invalid_pct:.0f}% (hard bounces)</div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                        
                        # Failed KPI
                        with kpi_row2[1]:
                            st.markdown(
                                f"""
                                <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1.25rem;">
                                    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;">
                                        <span style="font-size: 1.25rem;">❌</span>
                                        <span style="font-size: 0.8rem; font-weight: 500; color: #6b7280; text-transform: uppercase;">{_t("Failed")}</span>
                                    </div>
                                    <div style="font-size: 2rem; font-weight: 700; color: #111827; margin-bottom: 0.5rem;">{failed_other}</div>
                                    <div style="width: 100%; height: 4px; background: #e5e7eb; border-radius: 2px; overflow: hidden; margin-bottom: 0.25rem;">
                                        <div style="height: 100%; width: {failed_other_pct}%; background: linear-gradient(90deg, #f59e0b, #d97706); border-radius: 2px;"></div>
                                    </div>
                                    <div style="font-size: 0.75rem; color: #6b7280;">{failed_other_pct:.0f}% (blocked/soft)</div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                        
                        # Clicked KPI
                        with kpi_row2[2]:
                            st.markdown(
                                f"""
                                <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1.25rem;">
                                    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;">
                                        <span style="font-size: 1.25rem;">🔗</span>
                                        <span style="font-size: 0.8rem; font-weight: 500; color: #6b7280; text-transform: uppercase;">{_t("Clicked")}</span>
                                    </div>
                                    <div style="font-size: 2rem; font-weight: 700; color: #111827; margin-bottom: 0.5rem;">{group["total_clicks"]}</div>
                                    <div style="width: 100%; height: 4px; background: #e5e7eb; border-radius: 2px; overflow: hidden; margin-bottom: 0.25rem;">
                                        <div style="height: 100%; width: {clicked_pct}%; background: linear-gradient(90deg, #3b82f6, #2563eb); border-radius: 2px;"></div>
                                    </div>
                                    <div style="font-size: 0.75rem; color: #6b7280;">{clicked_pct:.0f}% {_t("of delivered")}</div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        # === Activity Log Table ===
                        st.markdown('<div class="activity-section">', unsafe_allow_html=True)
                        st.markdown(f'<div class="activity-header">{_t("📋 Activity Log")}</div>', unsafe_allow_html=True)
                        
                        # Add explanation about tracking
                        with st.expander(_t("ℹ️ Understanding email tracking")):
                            st.markdown(f"""
                            **{_t("Email Delivery Statuses:")}**
                            - **🚫 {_t("Invalid Email")}: {_t("Permanent failure - email address doesn't exist, domain is invalid, or unreachable")}**
                            - **❌ {_t("Failed")}: {_t("Temporary issues (mailbox full, server busy), blocked by server, or other errors")}**
                            - **⚠️ {_t("Delayed")}: {_t("Deferred - email is still being retried by the server")}**
                            - **✅ {_t("Delivered")}: {_t("Email successfully reached the recipient's inbox")}**
                            - **📖 {_t("Opened")}: {_t("Recipient opened the email and loaded images (tracking pixel)")}**
                            - **🔗 {_t("Clicked")}: {_t("Recipient clicked a link in the email")}**
                            - **🎯 {_t("Engaged")}: {_t("Recipient both opened and clicked links")}**
                            - **⏳ {_t("Pending")}: {_t("No delivery status received yet from Brevo")}**
                            
                            **{_t("Clicked Links Icons:")}**
                            - **🔕** = {_t("Unsubscribe link clicked")}
                            - **💝** = {_t("Donation/payment link clicked")}
                            - {_t("Multiple icons show when recipient clicked multiple links (e.g., 🔕 💝 means both unsubscribe and donate were clicked)")}
                            
                            **{_t("Understanding Bounces:")}**
                            - **{_t("Hard Bounce → Invalid")}: {_t("The email address is permanently invalid. Brevo marks these automatically.")}**
                            - **{_t("Soft Bounce → Invalid (Smart Detection)")}: {_t("Reasons like 'connection timeout', 'domain not found', 'no mail server' indicate the email is actually invalid.")}**
                            - **{_t("Soft Bounce → Failed")}: {_t("Temporary issues - mailbox full, server temporarily down, message too large, etc. May succeed if retried later.")}**
                            - **{_t("Blocked → Failed")}: {_t("Recipient's server blocked the email due to spam filters or policy rules.")}**
                            
                            **{_t("Smart Invalid Detection:")}**
                            {_t("The system automatically identifies invalid emails by checking:")}
                            - {_t("Hard bounces from Brevo (always invalid)")}
                            - {_t("Soft bounces with reasons indicating permanent failures:")}
                              - {_t("Connection timeout (domain unreachable)")}
                              - {_t("Domain not found")}
                              - {_t("No mail server for domain")}
                              - {_t("Invalid/unknown recipient")}
                            
                            **{_t('Why you might see "Clicked" without "Read":')}**
                            - {_t("Recipient has images disabled/blocked in their email client")}
                            - {_t("Recipient clicked a link from email preview without fully opening")}
                            - {_t("Some email clients block tracking pixels but allow link clicks")}
                            
                            **{_t("This is normal and indicates engagement even without open tracking!")}**
                            
                            **💡 Tip:** {_t("Enable debug mode below the table to see detailed bounce reasons from Brevo.")}
                            """)





                        
                        # Build activity table data
                        # First, check if we should show debug info (will be set by checkbox below table)
                        show_debug = st.session_state.get(f"debug_{group_key}", False)
                        
                        activity_rows = []
                        for r in group["recipients"]:
                            # Determine delivery status with improved logic
                            # Priority: Invalid > Failed > Delivered (with engagement) > Delayed > Pending
                            
                            # Check for invalid email addresses (hard bounces OR soft bounces with invalid reasons)
                            # Hard bounces are permanent failures from Brevo - truly invalid/non-existent addresses
                            # Some soft bounces (like connection timeout) also indicate invalid emails
                            if r["hardBounces"] > 0 or (r["softBounces"] > 0 and is_soft_bounce_actually_invalid(r["bounce_reason"])):
                                delivery_status = _t("🚫 Invalid Email")
                                status_priority = 1
                            # Check for other failures (blocked, errors, soft bounces with temporary issues)
                            # Soft bounces = temporary issues (mailbox full, etc.)
                            elif r["blocked"] > 0 or r["error"] > 0 or r["softBounces"] > 0:
                                delivery_status = _t("❌ Failed")
                                status_priority = 2
                            # Check for successful delivery
                            elif r["delivered"] > 0:
                                # Determine engagement level
                                has_opened = r["opened"] > 0
                                has_clicked = r["clicks"] > 0
                                
                                if has_clicked and has_opened:
                                    delivery_status = _t("🎯 Engaged (Opened & Clicked)")
                                    status_priority = 3
                                elif has_clicked:
                                    delivery_status = _t("🔗 Clicked (without open tracking)")
                                    status_priority = 4
                                elif has_opened:
                                    delivery_status = _t("📖 Opened")
                                    status_priority = 5
                                else:
                                    delivery_status = _t("✅ Delivered")
                                    status_priority = 6
                            # Check for deferred (temporary delay, might still be sending)
                            elif r["deferred"] > 0:
                                delivery_status = _t("⚠️ Delayed")
                                status_priority = 7
                            # Default to pending (no events received yet)
                            else:
                                delivery_status = _t("⏳ Pending")
                                status_priority = 8
                            
                            # Format timestamp
                            timestamp_str = r["last_event_date"]
                            if timestamp_str and timestamp_str != "N/A":
                                try:
                                    if "T" in timestamp_str or "+" in timestamp_str or "Z" in timestamp_str:
                                        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                                    else:
                                        ts = datetime.fromtimestamp(float(timestamp_str))
                                    timestamp_str = ts.strftime("%Y-%m-%d %H:%M")
                                except Exception:
                                    pass
                            
                            # Build row data with validated checkmarks
                            # Rule: Can only show Read/Clicked if delivered
                            # Note: Clicked can happen without Read (images blocked)
                            is_delivered = r["delivered"] > 0
                            
                            # Format clicked links for display
                            clicked_links_display = ""
                            if r["click_links"]:
                                # Helper function to identify link type
                                def identify_link_type(link):
                                    """Identify the type of link and return a display name"""
                                    link_lower = link.lower()
                                    
                                    # Check for unsubscribe patterns
                                    if ("unsubscribe" in link_lower or 
                                        "désabonnement" in link_lower or
                                        "desinscription" in link_lower or
                                        # Google Forms often used for unsubscribe
                                        ("docs.google.com/forms" in link_lower) or
                                        ("forms.gle" in link_lower)):
                                        return ("🔕 Unsubscribe", "unsubscribe")
                                    
                                    # Check for donate patterns
                                    elif ("donate" in link_lower or 
                                          "donation" in link_lower or
                                          "don" in link_lower or
                                          "dons" in link_lower or
                                          "paiement" in link_lower or
                                          "stripe" in link_lower):
                                        return ("💝 Donate", "donate")
                                    
                                    # Other links - show shortened URL
                                    else:
                                        display_link = link.replace("https://", "").replace("http://", "").replace("www.", "")
                                        if len(display_link) > 30:
                                            display_link = display_link[:27] + "..."
                                        return (display_link, "other")
                                
                                # Show unique links that were clicked
                                unique_links = list(set(r["click_links"]))
                                if len(unique_links) == 1:
                                    link = unique_links[0]
                                    display_name, link_type = identify_link_type(link)
                                    clicked_links_display = display_name
                                else:
                                    # Multiple links clicked - show each link type clearly
                                    link_displays = []
                                    for link in unique_links:
                                        display_name, link_type = identify_link_type(link)
                                        # For multiple links, use very compact format
                                        if link_type == "unsubscribe":
                                            link_displays.append("🔕")
                                        elif link_type == "donate":
                                            link_displays.append("💝")
                                        else:
                                            # For other links, just show first part of domain
                                            short_name = display_name.split("/")[0].split(".")[0]
                                            if len(short_name) > 10:
                                                short_name = short_name[:8] + ".."
                                            link_displays.append(short_name)
                                    
                                    # Join with spaces for compact display
                                    clicked_links_display = " ".join(link_displays)
                            
                            row_data = {
                                _t("Recipient"): r["email"],
                                _t("Delivery Status"): delivery_status,
                                _t("Delivered"): "✓" if is_delivered else "—",
                                _t("Read"): "✓" if (r["opened"] > 0 and is_delivered) else "—",
                                _t("Clicked"): "✓" if (r["clicks"] > 0 and is_delivered) else "—",
                                _t("Clicked Links"): clicked_links_display if clicked_links_display else "—",
                                _t("Timestamp"): timestamp_str
                            }
                            
                            # Add debug columns if enabled
                            if show_debug:
                                row_data[_t("Last Event")] = r["last_event"]
                                row_data[_t("Delivered Count")] = r["delivered"]
                                row_data[_t("Opened Count")] = r["opened"]
                                row_data[_t("Clicks Count")] = r["clicks"]
                                row_data[_t("Hard Bounces")] = r["hardBounces"]
                                row_data[_t("Soft Bounces")] = r["softBounces"]
                                row_data[_t("Blocked")] = r["blocked"]
                                row_data[_t("Deferred")] = r["deferred"]
                                row_data[_t("Bounce Reason")] = r.get("bounce_reason", "")  # Show Brevo's bounce reason
                                row_data[_t("Status Priority")] = status_priority
                            
                            activity_rows.append(row_data)
                        
                        # Display table in a container - auto-size based on number of rows
                        # Calculate appropriate height: header (38px) + rows (35px each) + padding
                        num_rows = len(activity_rows)
                        table_height = min(38 + (num_rows * 35) + 10, 600)  # Max 600px
                        
                        st.markdown('<div class="activity-table-container">', unsafe_allow_html=True)
                        st.dataframe(
                            pd.DataFrame(activity_rows),
                            use_container_width=True,
                            hide_index=True,
                            height=table_height
                        )
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        # Add debug toggle below the table
                        if st.checkbox(_t("🔍 Show debug info"), value=show_debug, key=f"debug_checkbox_{group_key}"):
                            if not show_debug:
                                st.session_state[f"debug_{group_key}"] = True
                                st.rerun()
                        else:
                            if show_debug:
                                st.session_state[f"debug_{group_key}"] = False
                                st.rerun()
                        
                        st.markdown('</div>', unsafe_allow_html=True)  # Close activity-section
                        st.markdown('</div>', unsafe_allow_html=True)  # Close main-panel
                    else:
                        st.info(_t("👈 Select a campaign from the sidebar to view details"))

            with tab2:
                st.markdown("### " + _t("Download Report"))
                st.markdown(_t("Export the current email status data"))

                export_rows = []
                for msg_id, data in email_data.items():
                    export_rows.append(
                        {
                            _t("Message ID"): msg_id,
                            _t("Email"): data["email"],
                            _t("Subject"): data["subject"],
                            _t("Tag"): data["tag"],
                            _t("Delivered Count"): data["delivered"],
                            _t("Opened Count"): data["opened"],
                            _t("Clicked Count"): data["clicks"],
                            _t("Hard Bounce"): data["hardBounces"],
                            _t("Soft Bounce"): data["softBounces"],
                            _t("Blocked"): data["blocked"],
                            _t("Spam"): data["spam"],
                            _t("Last Event"): data["last_event"],
                            _t("Last Event Date"): data["last_event_date"],
                        }
                    )
                export_df = pd.DataFrame(export_rows)
                st.download_button(
                    label=_t("📥 Download as CSV"),
                    data=export_df.to_csv(index=False).encode("utf-8"),
                    file_name=f"email_status_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
                st.markdown("#### " + _t("Preview"))
                st.dataframe(export_df.head(10), use_container_width=True, hide_index=True)
                st.caption(_t("Showing first 10 rows of {total} total", total=len(export_df)))

            # Pagination controls
            c1, c2, c3 = st.columns([1, 2, 1])
            with c1:
                if st.session_state.status_page_offset > 0:
                    if st.button("← " + _t("Previous"), use_container_width=True):
                        st.session_state.status_page_offset = max(0, st.session_state.status_page_offset - limit)
                        st.rerun()
            with c2:
                current_page = (st.session_state.status_page_offset // limit) + 1
                st.markdown(
                    f"<div style='text-align: center; padding: 0.5rem;'>{_t('Page')} {current_page}</div>",
                    unsafe_allow_html=True,
                )
            with c3:
                if len(events) == limit:
                    if st.button(_t("Next") + " →", use_container_width=True):
                        st.session_state.status_page_offset += limit
                        st.rerun()

        else:
            st.info(_t("No email events found for the selected time range and filters."))
            st.markdown(_t("Try adjusting your filters or time range."))

    except ApiException as e:
        # Handle Brevo API exceptions with structured error checking
        error_message = str(e)
        status_code = e.status if hasattr(e, 'status') else None
        
        # Categorize error by HTTP status code (more reliable than substring matching)
        if status_code == 429:
            st.error("⚠️ " + _t("Rate limit exceeded. Please wait a moment and try again."))
            st.info(_t("Brevo API has rate limits. The system will automatically retry with exponential backoff."))
        elif status_code in (401, 403):
            st.error("🔑 " + _t("Authentication error. Please check your Brevo API key."))
            st.warning(_t("Your API key may be invalid or may not have the required permissions."))
        elif status_code == 404:
            st.error("❓ " + _t("Resource not found. The requested data may not exist."))
        else:
            st.error("❌ " + _t("Error fetching email events: ") + error_message)
        
        logger.error(f"Brevo API error in email status page: HTTP {status_code} - {error_message}", exc_info=True)
        
        # Show detailed debug info
        with st.expander(_t("🔍 Debug Information")):
            st.markdown("**" + _t("Error Type:") + "** ApiException")
            if status_code:
                st.markdown(f"**HTTP Status:** {status_code}")
            st.code(error_message)
            
            # Show potential solutions
            st.markdown("**" + _t("Possible Solutions:") + "**")
            if status_code == 429:
                st.markdown("- Wait 1-2 minutes before retrying")
                st.markdown("- Reduce the frequency of requests")
                st.markdown("- Contact Brevo support to increase your rate limit")
            elif status_code in (401, 403):
                st.markdown("- Verify your API key in Brevo dashboard")
                st.markdown("- Ensure the API key has 'Email Campaigns' permissions")
                st.markdown("- Check if the API key is correctly configured in secrets/config")
            else:
                st.markdown("- Check your internet connection")
                st.markdown("- Try refreshing the page")
                st.markdown("- Contact support if the issue persists")
    
    except Exception as e:
        # Handle unexpected errors with fallback to substring matching
        error_message = str(e)
        error_type = type(e).__name__
        
        # Fallback categorization for non-API exceptions
        if "timeout" in error_message.lower():
            st.error("⏱️ " + _t("Request timed out. Please try again."))
        elif "Rate limit" in error_message or "429" in error_message:
            st.error("⚠️ " + _t("Rate limit exceeded. Please wait a moment and try again."))
            st.info(_t("Brevo API has rate limits. The system will automatically retry with exponential backoff."))
        elif "API key" in error_message or "401" in error_message or "403" in error_message:
            st.error("🔑 " + _t("Authentication error. Please check your Brevo API key."))
            st.warning(_t("Your API key may be invalid or may not have the required permissions."))
        elif "404" in error_message:
            st.error("❓ " + _t("Resource not found. The requested data may not exist."))
        else:
            st.error("❌ " + _t("Error fetching email events: ") + error_message)
        
        logger.error(f"Unexpected error in email status page: {error_type} - {error_message}", exc_info=True)
        
        # Show detailed debug info
        with st.expander(_t("🔍 Debug Information")):
            st.markdown("**" + _t("Error Type:") + "** " + type(e).__name__)
            st.code(error_message)
            
            # Show potential solutions
            st.markdown("**" + _t("Possible Solutions:") + "**")
            if "Rate limit" in error_message:
                st.markdown("- Wait 1-2 minutes before retrying")
                st.markdown("- Reduce the frequency of requests")
                st.markdown("- Contact Brevo support to increase your rate limit")
            elif "API key" in error_message:
                st.markdown("- Verify your API key in Brevo dashboard")
                st.markdown("- Ensure the API key has 'Email Campaigns' permissions")
                st.markdown("- Check if the API key is correctly configured in secrets/config")
            else:
                st.markdown("- Check your internet connection")
                st.markdown("- Try refreshing the page")
                st.markdown("- Contact support if the issue persists")

    # Footer
    st.markdown("---")
    st.markdown(
        f"<div style='text-align: center; color: #6b7280; font-size: 0.9rem;'>"
        f"{_t('Data fetched live from Brevo')} | "
        f"{_t('Last updated')}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        f"</div>",
        unsafe_allow_html=True,
    )
