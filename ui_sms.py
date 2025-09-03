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

from __future__ import annotations

import re
from typing import List, Dict, Optional

import pandas as pd
import streamlit as st

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


# ---------------------------
# Helpers (kept minimal)
# ---------------------------
PHONE_COLUMN_CANDIDATES = {
    "phone", "phones", "telephone", "tel", "mobile", "mobile_phone",
    "cell", "cellphone", "מטל", "טלפון", "פלאפון", "נייד",
}
NAME_COLUMN_CANDIDATES = {
    "name", "full_name", "שם", "contact", "recipient",
    "first name", "last name", "first", "last",
}


def _find_first_matching_column(df: pd.DataFrame, candidates: set[str]) -> Optional[str]:
    lower_map = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand in lower_map:
            return lower_map[cand]
    # Try looser contains check
    for c in df.columns:
        lc = c.lower()
        if any(cand in lc for cand in candidates):
            return c
    return None


def _looks_like_e164(phone: str) -> bool:
    return bool(re.fullmatch(r"\+[0-9]{6,15}", phone.strip()))


def _normalize_phone_minimal(raw: str) -> Optional[str]:
    if not isinstance(raw, str):
        raw = str(raw)
    raw = raw.strip()
    # Minimal v1 rule: accept only E.164-like strings that start with '+' and digits.
    if _looks_like_e164(raw):
        return raw
    return None


def _compose_name(row: pd.Series, name_col: Optional[str]) -> str:
    if name_col and pd.notna(row.get(name_col)):
        return str(row.get(name_col))
    # Try first/last heuristic
    first = None
    last = None
    for c in row.index:
        lc = c.lower()
        if "first" in lc:
            first = row.get(c)
        if "last" in lc:
            last = row.get(c)
    parts = [p for p in [first, last] if isinstance(p, str) and p.strip()]
    return " ".join(parts) if parts else ""


def _extract_recipients_from_df(df: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame with columns [name, phone] for valid phone rows only."""
    if df.empty:
        return pd.DataFrame(columns=["name", "phone"])

    phone_col = _find_first_matching_column(df, PHONE_COLUMN_CANDIDATES)
    name_col = _find_first_matching_column(df, NAME_COLUMN_CANDIDATES)

    rows = []
    for _, row in df.iterrows():
        raw_phone = row.get(phone_col) if phone_col else None
        if pd.isna(raw_phone):
            continue
        phone = _normalize_phone_minimal(str(raw_phone))
        if not phone:
            continue
        name = _compose_name(row, name_col)
        rows.append({"name": name, "phone": phone})

    return pd.DataFrame(rows, columns=["name", "phone"]) if rows else pd.DataFrame(columns=["name", "phone"])


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

    st.markdown("---")
    st.header(_t("Upload Contacts"))

    uploaded = st.file_uploader(_t("Upload an Excel file with contacts"), type=["xlsx", "xls"])

    contacts_df: Optional[pd.DataFrame] = None
    if uploaded is not None:
        try:
            contacts_df = pd.read_excel(uploaded)
            st.session_state["contacts"] = contacts_df  # Reuse canonical key
            st.success(_t("Contacts loaded"))
        except Exception as e:
            st.error(_t("Failed to read the Excel file. Please verify the format."))
            st.stop()
    else:
        # Consider existing contacts in session_state (if user navigated back)
        if isinstance(st.session_state.get("contacts"), pd.DataFrame):
            contacts_df = st.session_state.get("contacts")

    # Derive recipients table
    recipients_df = _extract_recipients_from_df(contacts_df) if contacts_df is not None else pd.DataFrame(columns=["name", "phone"])

    if recipients_df.empty:
        st.warning(_t("No recipients with a phone number found"))
        # We still render the compose box to let the user pre-write the SMS
    else:
        st.subheader(_t("Recipients"))
        st.dataframe(recipients_df, use_container_width=True, hide_index=True)
        st.caption(_t("{n} recipients will receive this SMS").format(n=len(recipients_df)))

    st.markdown("---")
    st.header(_t("Compose"))

    sms_text = st.text_area(
        label=_t("SMS Text"),
        value=st.session_state.get("sms_text", ""),
        height=140,
        placeholder=_t("Write the SMS text here..."),
    )
    st.session_state["sms_text"] = sms_text

    # Minimal character count hint (no GSM-7/UCS-2 segmentation yet)
    st.caption(_t("Characters: {n}", n=len(sms_text or "")))

    st.markdown("---")

    # Send button row
    col_send, col_summary = st.columns([1, 2])
    with col_send:
        disabled = recipients_df.empty or not (sms_text and sms_text.strip())
        if st.button(_t("Send SMS"), type="primary", disabled=disabled):
            versions = [
                {"recipient": row["phone"], "text": sms_text}
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
                        st.warning(_t("Sent with some errors: {acc} accepted, {fail} failed").format(acc=accepted, fail=failed))
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
                        st.caption(_t("Last checked: {ts}").format(ts=msg.get("last_checked_at") or _t("n/a")))


# If this file is executed directly (rare in Streamlit), render for convenience.
if __name__ == "__main__":
    render()
