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

    # Custom CSS
    st.markdown(
        """
        <style>
        .status-card { background: white; border-radius: 8px; padding: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 1rem; }
        .metric-container { display: flex; justify-content: space-around; gap: 1rem; margin: 1rem 0; }
        .metric-box { background: #f8f9fa; padding: 1rem; border-radius: 8px; text-align: center; flex: 1; }
        .metric-value { font-size: 2rem; font-weight: bold; color: #2563eb; }
        .metric-label { font-size: 0.9rem; color: #6b7280; margin-top: 0.5rem; }
        .campaign-item { 
            background: white; 
            border: 1px solid #e5e7eb; 
            border-radius: 8px; 
            padding: 1rem; 
            margin-bottom: 0.5rem; 
            cursor: pointer; 
            transition: all 0.2s;
        }
        .campaign-item:hover { 
            box-shadow: 0 2px 8px rgba(0,0,0,0.1); 
            border-color: #2563eb;
        }
        .campaign-item.selected { 
            border-color: #2563eb;
            background: #eff6ff;
        }
        .sidebar-detail { 
            background: #f9fafb; 
            border-left: 1px solid #e5e7eb; 
            padding: 1.5rem; 
            border-radius: 8px;
            height: 100%;
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

            tab1, tab2 = st.tabs([_t("📊 Detailed View"), _t("📥 Download Report")])
            with tab1:
                st.markdown("### " + _t("Email Campaigns"))

                # Create two columns: list view and detail sidebar
                list_col, detail_col = st.columns([2, 3])

                with list_col:
                    # Create a simple clickable list of campaigns
                    campaign_keys = list(grouped_data.keys())
                    
                    if campaign_keys:
                        # Initialize selection if not set
                        if st.session_state.selected_campaign not in campaign_keys:
                            st.session_state.selected_campaign = campaign_keys[0]
                        
                        # Display each campaign as a clickable button
                        for group_key in campaign_keys:
                            group = grouped_data[group_key]
                            is_selected = st.session_state.selected_campaign == group_key
                            
                            # Create button with full subject
                            if st.button(
                                group["subject"],
                                key=f"btn_{group_key}",
                                use_container_width=True,
                                type="primary" if is_selected else "secondary"
                            ):
                                st.session_state.selected_campaign = group_key
                                st.rerun()

                with detail_col:
                    # Display selected campaign details in sidebar
                    if st.session_state.selected_campaign and st.session_state.selected_campaign in grouped_data:
                        group = grouped_data[st.session_state.selected_campaign]
                        group_key = st.session_state.selected_campaign
                        
                        st.markdown(f"<div class='sidebar-detail'>", unsafe_allow_html=True)
                        
                        # Format date
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
                        
                        # Campaign metrics
                        delivery_rate = f"{(group['total_delivered']/group['total_sent']*100):.0f}%" if group["total_sent"] > 0 else "0%"
                        open_rate = f"{(group['total_opened']/group['total_delivered']*100):.0f}%" if group["total_delivered"] > 0 else "0%"
                        click_rate = f"{(group['total_clicks']/group['total_delivered']*100):.0f}%" if group["total_delivered"] > 0 else "0%"
                        
                        # Show quick stats at the top
                        st.markdown(f"**🎯 {group['total_sent']} recipients | ✅ {delivery_rate} delivered | 📖 {open_rate} opened | 🔗 {click_rate} clicked**")
                        st.markdown("---")
                        
                        st.markdown("#### " + _t("Campaign Metrics"))
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            st.metric(_t("Sent"), group["total_sent"])
                            st.metric(_t("Delivered"), f"{group['total_delivered']}")
                        with c2:
                            st.metric(_t("Opened"), f"{group['total_opened']}")
                            st.metric(_t("Clicked"), f"{group['total_clicks']}")
                        with c3:
                            bounced = group["total_hardBounces"] + group["total_softBounces"]
                            st.metric(_t("Bounced"), bounced)
                            st.metric(_t("Last Activity"), date_str if date_str != "N/A" else "-")
                        
                        st.markdown("#### " + _t("Rates"))
                        rate_c1, rate_c2, rate_c3 = st.columns(3)
                        with rate_c1:
                            st.metric(_t("Delivery Rate"), delivery_rate)
                        with rate_c2:
                            st.metric(_t("Open Rate"), open_rate)
                        with rate_c3:
                            st.metric(_t("Click Rate"), click_rate)
                        
                        st.markdown("---")
                        
                        # Campaign info
                        st.markdown(f"**Batch ID:** `{group_key}`")
                        if group["tag"]:
                            st.markdown(f"**Tag:** {group['tag']}")
                        
                        st.markdown("---")
                        st.markdown("#### " + _t("Recipients"))
                        
                        # Recipients table
                        rows = []
                        for r in group["recipients"]:
                            if r["hardBounces"] > 0 or r["blocked"] > 0:
                                status = "❌ Failed"
                            elif r["softBounces"] > 0 or r["deferred"] > 0:
                                status = "⚠️ Delayed"
                            elif r["clicks"] > 0:
                                status = "✅ Clicked"
                            elif r["opened"] > 0:
                                status = "📖 Opened"
                            elif r["delivered"] > 0:
                                status = "📧 Delivered"
                            else:
                                status = "⏳ Pending"
                            rows.append(
                                {
                                    "Status": status,
                                    "Email": r["email"],
                                    "Delivered": "✓" if r["delivered"] > 0 else "",
                                    "Opened": f"{r['opened']}x" if r["opened"] > 0 else "",
                                    "Clicked": f"{r['clicks']}x" if r["clicks"] > 0 else "",
                                }
                            )
                        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=400)
                        st.markdown("</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"**🎯 Select a campaign tab to view details**")

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
