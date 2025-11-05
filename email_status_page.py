"""
Email Status Page
Displays latest sent email activity from Brevo in a concise, stateless way.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import logging
import os
import re

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

def main():
    # IMPORTANT: Do NOT call st.set_page_config here (already set in parent streamlit_app.py)

    # Initialize session state for this page
    if "status_page_offset" not in st.session_state:
        st.session_state.status_page_offset = 0
    if "status_page_limit" not in st.session_state:
        st.session_state.status_page_limit = 50
    if "selected_campaign" not in st.session_state:
        st.session_state.selected_campaign = None

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
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Header
    st.title("📧 " + _t("Email Status Dashboard"))
    st.markdown(_t("View latest email activity from Brevo. Data is fetched live on each refresh."))

    # Check for Brevo API key
    if not BREVO_API_KEY:
        st.error(_t("Brevo API key not found in configuration. Please configure BREVO_API_KEY in config.py or secrets."))
        st.code(
            """
# In .streamlit/secrets.toml:
BREVO_API_KEY = "your-brevo-api-key"

# Or in config.py:
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
            """
        )
        st.stop()

    # Initialize client
    client = BrevoStatusClient(BREVO_API_KEY)

    # Sidebar - simplified with only refresh
    start_date = datetime.now() - timedelta(days=7)
    end_date = datetime.now()
    limit = 100
    event_filter = None
    email_search = None

    # Refresh button
    if st.sidebar.button(_t("🔄 Refresh Data"), type="primary", use_container_width=True):
        st.session_state.status_page_offset = 0
        st.rerun()

    # Main content
    try:
        with st.spinner(_t("Fetching email events from Brevo...")):
            events, total = client.get_email_events(
                limit=limit,
                offset=st.session_state.status_page_offset,
                start_date=start_date,
                end_date=end_date,
                email=email_search if email_search else None,
                event=event_filter,
                sort="desc",
            )

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
                        "click_links": [],
                    }

                event_type = event["event"]
                if event_type in email_data[msg_id]:
                    email_data[msg_id][event_type] += 1

                if not email_data[msg_id]["last_event_date"] or event["date"] > email_data[msg_id]["last_event_date"]:
                    email_data[msg_id]["last_event"] = event_type
                    email_data[msg_id]["last_event_date"] = event["date"]

                if event_type == "clicks" and event.get("link"):
                    email_data[msg_id]["click_links"].append(event["link"])

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

                if data["last_event_date"] and (
                    not grouped_data[group_key]["last_event_date"]
                    or data["last_event_date"] > grouped_data[group_key]["last_event_date"]
                ):
                    grouped_data[group_key]["last_event_date"] = data["last_event_date"]

            # Overall metrics
            total_emails = len(email_data)
            total_delivered = sum(1 for e in email_data.values() if e["delivered"] > 0)
            total_opened = sum(1 for e in email_data.values() if e["opened"] > 0)
            total_clicked = sum(1 for e in email_data.values() if e["clicks"] > 0)
            total_bounced = sum(1 for e in email_data.values() if e["hardBounces"] > 0 or e["softBounces"] > 0)

            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric(_t("Total Recipients"), total_emails)
            with col2:
                delivery_rate = f"{(total_delivered/total_emails*100):.1f}%" if total_emails > 0 else "N/A"
                st.metric(_t("Delivered"), f"{total_delivered} ({delivery_rate})")
            with col3:
                open_rate = f"{(total_opened/total_delivered*100):.1f}%" if total_delivered > 0 else "N/A"
                st.metric(_t("Opened"), f"{total_opened} ({open_rate})")
            with col4:
                click_rate = f"{(total_clicked/total_delivered*100):.1f}%" if total_delivered > 0 else "N/A"
                st.metric(_t("Clicked"), f"{total_clicked} ({click_rate})")
            with col5:
                bounce_rate = f"{(total_bounced/total_emails*100):.1f}%" if total_emails > 0 else "N/A"
                st.metric(_t("Bounced"), f"{total_bounced} ({bounce_rate})")

            st.markdown("---")

            # Sort campaigns by date (newest first)
            sorted_campaigns = sorted(
                grouped_data.items(),
                key=lambda x: x[1]["last_event_date"] if x[1]["last_event_date"] else "",
                reverse=True
            )
            
            # Group campaigns by date
            campaigns_by_date = {}
            for group_key, group in sorted_campaigns:
                date_str = group["last_event_date"]
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
                        
                        # === Campaign Title & Metadata ===
                        st.markdown(f'<div class="campaign-title">{group["subject"]}</div>', unsafe_allow_html=True)
                        
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
                        bounced = group["total_hardBounces"] + group["total_softBounces"]
                        pending = group["total_sent"] - group["total_delivered"] - bounced
                        
                        sent_pct = 100
                        delivered_pct = (group['total_delivered']/group['total_sent']*100) if group['total_sent'] > 0 else 0
                        failed_pct = (bounced/group['total_sent']*100) if group['total_sent'] > 0 else 0
                        opened_pct = (group['total_opened']/group['total_delivered']*100) if group['total_delivered'] > 0 else 0
                        pending_pct = (pending/group['total_sent']*100) if group['total_sent'] > 0 else 0
                        
                        # Create 5 columns for KPI tiles
                        kpi_cols = st.columns(5)
                        
                        # Sent KPI
                        with kpi_cols[0]:
                            st.markdown(
                                f"""
                                <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1.25rem;">
                                    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;">
                                        <span style="font-size: 1.25rem;">📧</span>
                                        <span style="font-size: 0.8rem; font-weight: 500; color: #6b7280; text-transform: uppercase;">Sent</span>
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
                        with kpi_cols[1]:
                            st.markdown(
                                f"""
                                <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1.25rem;">
                                    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;">
                                        <span style="font-size: 1.25rem;">✅</span>
                                        <span style="font-size: 0.8rem; font-weight: 500; color: #6b7280; text-transform: uppercase;">Delivered</span>
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
                        
                        # Failed KPI
                        with kpi_cols[2]:
                            st.markdown(
                                f"""
                                <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1.25rem;">
                                    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;">
                                        <span style="font-size: 1.25rem;">❌</span>
                                        <span style="font-size: 0.8rem; font-weight: 500; color: #6b7280; text-transform: uppercase;">Failed</span>
                                    </div>
                                    <div style="font-size: 2rem; font-weight: 700; color: #111827; margin-bottom: 0.5rem;">{bounced}</div>
                                    <div style="width: 100%; height: 4px; background: #e5e7eb; border-radius: 2px; overflow: hidden; margin-bottom: 0.25rem;">
                                        <div style="height: 100%; width: {failed_pct}%; background: linear-gradient(90deg, #ef4444, #dc2626); border-radius: 2px;"></div>
                                    </div>
                                    <div style="font-size: 0.75rem; color: #6b7280;">{failed_pct:.0f}%</div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                        
                        # Read KPI
                        with kpi_cols[3]:
                            st.markdown(
                                f"""
                                <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1.25rem;">
                                    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;">
                                        <span style="font-size: 1.25rem;">📖</span>
                                        <span style="font-size: 0.8rem; font-weight: 500; color: #6b7280; text-transform: uppercase;">Read</span>
                                    </div>
                                    <div style="font-size: 2rem; font-weight: 700; color: #111827; margin-bottom: 0.5rem;">{group["total_opened"]}</div>
                                    <div style="width: 100%; height: 4px; background: #e5e7eb; border-radius: 2px; overflow: hidden; margin-bottom: 0.25rem;">
                                        <div style="height: 100%; width: {opened_pct}%; background: linear-gradient(90deg, #10b981, #059669); border-radius: 2px;"></div>
                                    </div>
                                    <div style="font-size: 0.75rem; color: #6b7280;">{opened_pct:.0f}% of delivered</div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                        
                        # Pending KPI
                        with kpi_cols[4]:
                            st.markdown(
                                f"""
                                <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1.25rem;">
                                    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;">
                                        <span style="font-size: 1.25rem;">⏳</span>
                                        <span style="font-size: 0.8rem; font-weight: 500; color: #6b7280; text-transform: uppercase;">Pending</span>
                                    </div>
                                    <div style="font-size: 2rem; font-weight: 700; color: #111827; margin-bottom: 0.5rem;">{pending}</div>
                                    <div style="width: 100%; height: 4px; background: #e5e7eb; border-radius: 2px; overflow: hidden; margin-bottom: 0.25rem;">
                                        <div style="height: 100%; width: {pending_pct}%; background: linear-gradient(90deg, #f59e0b, #d97706); border-radius: 2px;"></div>
                                    </div>
                                    <div style="font-size: 0.75rem; color: #6b7280;">{pending_pct:.0f}%</div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        # === Activity Log Table ===
                        st.markdown('<div class="activity-section">', unsafe_allow_html=True)
                        st.markdown('<div class="activity-header">📋 Activity Log</div>', unsafe_allow_html=True)
                        
                        # Build activity table data
                        activity_rows = []
                        for r in group["recipients"]:
                            # Determine delivery status
                            if r["hardBounces"] > 0 or r["blocked"] > 0:
                                delivery_status = "Failed"
                            elif r["softBounces"] > 0 or r["deferred"] > 0:
                                delivery_status = "Delayed"
                            elif r["delivered"] > 0:
                                delivery_status = "Delivered"
                            else:
                                delivery_status = "Pending"
                            
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
                            
                            activity_rows.append({
                                "Recipient": r["email"],
                                "Delivery Status": delivery_status,
                                "Delivered": "✓" if r["delivered"] > 0 else "",
                                "Read": "✓" if r["opened"] > 0 else "",
                                "Clicked": "✓" if r["clicks"] > 0 else "",
                                "Timestamp": timestamp_str
                            })
                        
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

    except Exception as e:
        st.error(_t("Error fetching email events: ") + str(e))
        logger.error(f"Error in email status page: {str(e)}", exc_info=True)
        with st.expander(_t("Debug Information")):
            st.code(str(e))

    # Footer
    st.markdown("---")
    st.markdown(
        f"<div style='text-align: center; color: #6b7280; font-size: 0.9rem;'>"
        f"{_t('Data fetched live from Brevo')} | "
        f"{_t('Last updated')}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        f"</div>",
        unsafe_allow_html=True,
    )
