# CHANGELOG
# - v0.1 (2025-09-01): Initial SMS-only UI module.
#   * Provides a minimal Streamlit UI for composing and sending SMS to contacts loaded from an Excel file.
#   * No AI generation; a single shared SMS text is written by the user.
#   * Renders a recipients preview table (only rows with a valid phone number).
#   * Sends via sms_tool.send_bulk_sms(); shows per-recipient message_id and manual status refresh.
#   * Adds/uses session_state keys: sms_text, sms_send_result, sms_message_details, contacts (reused if present).
#   * All user-facing strings routed through translations._t().
#   * Designed to be called exclusively when AI_MESSENGER_MODE == "sms" from streamlit_app.py.
#
# TODOs (follow-ups suggested):
#   * Move/centralize phone normalization into data_handler.py to avoid duplication.
#   * Add full GSM-7/UCS-2 segment calculation and warnings for long messages.
#   * Extend translations.py with the new keys (EN + HE if present) used below.
#   * Wire proper country-aware E.164 normalization (DEFAULT_SMS_COUNTRY) if needed.

from typing import List, Dict, Optional

import pandas as pd
import streamlit as st
import tempfile
import shutil
import os # Import os for path existence check
try:
    # Project-local translation function
    from translations import _t
except Exception:
    # Fallback for development if translations module isn't available
    def _t(key: str) -> str:
        return key

# sms_tool is implemented in a separate module per plan.
# Expected interface:
#   send_bulk_sms(versions: List[Dict[str, str]]) -> List[Dict[str, str]]
#   get_sms_event(message_id: str) -> Dict[str, str]
try:
    from sms_tool import send_bulk_sms, get_sms_event
except Exception:
    # Lightweight placeholders to keep the UI importable before sms_tool.py exists.
    def send_bulk_sms(versions: List[Dict[str, str]]) -> List[Dict[str, str]]:  # type: ignore
        return [
            {"recipient": v.get("recipient", ""), "message_id": f"demo-{i}", "error": None}
            for i, v in enumerate(versions)
        ]

    def get_sms_event(message_id: str) -> Dict[str, str]:  # type: ignore
        return {"message_id": message_id, "state": "queued", "updated_at": None}

# Import the new data handler for phone numbers
from data_handler_phone_numbers import load_contacts_from_excel


# ---------------------------
# Helpers (kept minimal)
# ---------------------------

def _status_badge(state: Optional[str]) -> str:
    state = (state or "").lower()
    mapping = {
        "queued": _t("Queued"),
        "sent": _t("Sent"),
        "delivered": _t("Delivered"),
        "failed": _t("Failed"),
    }
    return mapping.get(state, _t("Unknown"))


# ---------------------------
# Main render function (called by streamlit_app when mode==sms)
# ---------------------------

def render() -> None:
    """Render the SMS-only UI flow.

    This function assumes the caller (streamlit_app.py) has decided the app is in SMS mode.
    The UI is intentionally minimal: Upload → Compose → Send → Results.
    """

    st.title(_t("SMS (beta)"))

    # Initialize session state keys we use
    st.session_state.setdefault("sms_text", "")
    st.session_state.setdefault("sms_send_result", None)
    st.session_state.setdefault("sms_message_details", [])  # list of dicts
    st.session_state.setdefault("contacts", []) # List of dicts from data_handler_phone_numbers
    st.session_state.setdefault("contact_issues", []) # List of strings from data_handler_phone_numbers
    st.session_state.setdefault("uploaded_file_name", None) # To track if the file has changed by name
    st.session_state.setdefault("uploaded_file_path", None) # To store path for access

    st.markdown("---")
    st.header(_t("Upload Contacts"))

    uploaded_file = st.file_uploader(_t("Upload an Excel file with contacts"), type=["xlsx", "xls"])

    # Process file only if a new file is uploaded (by name or initial upload)
    if uploaded_file is not None and \
       (st.session_state.uploaded_file_name is None or \
        st.session_state.uploaded_file_name != uploaded_file.name):
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
            shutil.copyfileobj(uploaded_file, tmp_file)
            st.session_state.uploaded_file_path = tmp_file.name # Store path for access
        
        st.session_state.uploaded_file_name = uploaded_file.name
        
        # Use the new data handler
        contacts, issues = load_contacts_from_excel(st.session_state.uploaded_file_path)
        st.session_state.contacts = contacts
        st.session_state.contact_issues = issues
        
        if issues:
            st.warning(_t("WARNING: Some contacts had issues (e.g., missing/invalid phone numbers). They will be skipped."))
            for issue in issues:
                st.info(f"  - {issue}")
        
        if contacts:
            st.success(_t("Successfully loaded {count} valid contacts.", count=len(contacts)))
        else:
            st.error(_t("No valid contacts found in the Excel file."))

    # Consider existing contacts in session_state (if user navigated back)
    if not st.session_state.contacts and st.session_state.uploaded_file_name:
        # If contacts were cleared but file name exists, try reloading
        if st.session_state.uploaded_file_path and os.path.exists(st.session_state.uploaded_file_path):
            contacts, issues = load_contacts_from_excel(st.session_state.uploaded_file_path)
            st.session_state.contacts = contacts
            st.session_state.contact_issues = issues
            if contacts:
                st.success(_t("Re-loaded {count} valid contacts from previous upload.", count=len(contacts)))
            if issues:
                st.warning(_t("WARNING: Some contacts had issues (e.g., missing/invalid phone numbers). They will be skipped."))
                for issue in issues:
                    st.info(f"  - {issue}")
        else:
            st.info(_t("Please upload an Excel file to get started."))
    elif not st.session_state.uploaded_file_name:
        st.info(_t("Please upload an Excel file to get started."))


    # Derive recipients table from st.session_state.contacts
    # The data handler already returns contacts in the desired format: [{"name": "...", "phone_number": "..."}]
    recipients_df = pd.DataFrame(st.session_state.contacts)
    if not recipients_df.empty:
        recipients_df = recipients_df.rename(columns={"phone_number": "phone"}) # Rename for UI consistency

    if recipients_df.empty:
        # Only show this warning if a file has been uploaded and processed, but no valid recipients were found.
        # Otherwise, the "Please upload an Excel file to get started." message should take precedence.
        if st.session_state.uploaded_file_name: # This means a file was uploaded and processed
            st.warning(_t("No recipients with a phone number found"))
        # We still render the compose box to let the user pre-write the SMS
    else:
        st.subheader(_t("Recipients"))
        st.dataframe(recipients_df, use_container_width=True, hide_index=True)
        st.caption(_t("{n} recipients will receive this SMS", n=len(recipients_df)))

    st.markdown("---")
    st.header(_t("Compose"))

    st.text_area(
        label=_t("SMS Text"),
        value=st.session_state.get("sms_text", ""),
        height=140,
        placeholder=_t("Write the SMS text here..."),
        key="sms_text", # Bind directly to session_state
    )

    # Minimal character count hint (no GSM-7/UCS-2 segmentation yet)
    # Access sms_text directly from session_state for dynamic updates
    st.caption(_t("Characters: {n}", n=len(st.session_state.sms_text or "")))

    st.markdown("---")

    # Send button row
    col_send, col_summary = st.columns([1, 2])
    with col_send:
        disabled = recipients_df.empty or not (st.session_state.sms_text and st.session_state.sms_text.strip())
        if st.button(_t("Send SMS"), type="primary", disabled=disabled):
            versions = [
                {"recipient": row["phone"], "text": st.session_state.sms_text}
                for _, row in recipients_df.iterrows()
            ]

            # Safety cap: align with email batch cap (2000). sms_tool may enforce too.
            if len(versions) > 2000:
                st.error(_t("Too many recipients. Please send in batches of up to 2000."))
            else:
                try:
                    results = send_bulk_sms(versions)
                except Exception as e:  # Surface library/network errors without crashing the UI
                    st.error(_t("Failed to send SMS. Please check credentials/network and try again."))
                else:
                    # Persist details for the Results section
                    details = []
                    accepted = 0
                    failed = 0
                    for item in results:
                        recipient = item.get("recipient")
                        message_id = item.get("message_id")
                        error = item.get("error")
                        if message_id and not error:
                            accepted += 1
                        else:
                            failed += 1
                        details.append({
                            "recipient": recipient,
                            "message_id": message_id,
                            "error": error,
                            "last_status": None,
                            "last_checked_at": None,
                        })

                    st.session_state["sms_message_details"] = details
                    st.session_state["sms_send_result"] = {
                        "requested": len(versions),
                        "accepted": accepted,
                        "failed": failed,
                    }

                    if failed == 0 and accepted > 0:
                        st.success(_t("SMS batch sent"))
                    elif accepted > 0 and failed > 0:
                        st.warning(_t("Sent with some errors: {acc} accepted, {fail} failed", acc=accepted, fail=failed))
                    else:
                        st.error(_t("All messages failed to send"))

    with col_summary:
        if st.session_state.get("sms_send_result"):
            res = st.session_state["sms_send_result"]
            st.metric(label=_t("Requested"), value=res.get("requested", 0))
            st.metric(label=_t("Accepted"), value=res.get("accepted", 0))
            st.metric(label=_t("Failed"), value=res.get("failed", 0))

    # Results & Events section
    details = st.session_state.get("sms_message_details") or []
    if details:
        st.markdown("---")
        st.subheader(_t("Individual SMS Status & Events"))

        for i, msg in enumerate(details):
            recipient = msg.get("recipient") or ""
            message_id = msg.get("message_id") or ""
            header = f"{_t('Recipient')}: {recipient} | {_t('Message ID')}: {message_id}"

            with st.expander(header, expanded=False):
                st.markdown(f"**{_t('Recipient')}:** `{recipient}`")
                st.markdown(f"**{_t('Message ID')}:** `{message_id}`")

                cols = st.columns([1, 1, 2])
                with cols[0]:
                    if st.button(_t("Refresh SMS Events"), key=f"refresh_sms_{message_id}_{i}"):
                        try:
                            event = get_sms_event(message_id)
                            msg["last_status"] = event.get("state")
                            msg["last_checked_at"] = event.get("updated_at")
                            st.session_state["sms_message_details"][i] = msg
                        except Exception:
                            st.error(_t("Failed to fetch SMS events for this message."))
                with cols[1]:
                    st.write(_t("Delivery status"))
                    st.info(_status_badge(msg.get("last_status")))
                with cols[2]:
                    if msg.get("error"):
                        st.error(str(msg.get("error")))
                    else:
                        st.caption(_t("Last checked: {ts}", ts=msg.get("last_checked_at") or _t("n/a")))


# If this file is executed directly (rare in Streamlit), render for convenience.
if __name__ == "__main__":
    render()
