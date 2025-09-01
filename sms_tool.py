# CHANGELOG
# - v0.1 (2025-09-01): Initial minimal wrapper around SMSGate (android-sms-gateway).
#   * Public functions:
#       - send_bulk_sms(versions)
#       - get_sms_event(message_id)
#   * Sequential sends, per-recipient error isolation, normalized responses.
#   * Reads credentials from config.py (env-backed); safe imports if library missing.
#   * Conservative batch cap (2000), no background polling.
#
# Notes:
# - This module intentionally avoids Streamlit/UI concerns.
# - Keep error messages concise; callers surface them to users with translations.
# - Future: add phone normalization here if we centralize it (currently in UI layer draft).

from __future__ import annotations

from typing import Dict, List, Optional, Any
import os

# ---------------------------
# Config
# ---------------------------
try:
    # Preferred: project config provides env-backed secrets
    from config import (
        ANDROID_SMS_GATEWAY_LOGIN as _CONF_LOGIN,
        ANDROID_SMS_GATEWAY_PASSWORD as _CONF_PASSWORD,
    )
except Exception:
    # Fallback: read directly from environment
    _CONF_LOGIN = os.getenv("ANDROID_SMS_GATEWAY_LOGIN", "")
    _CONF_PASSWORD = os.getenv("ANDROID_SMS_GATEWAY_PASSWORD", "")

# Conservative cap to mirror email batch semantics
BATCH_CAP: int = 2000

# Soft import of provider SDK to keep this file importable when the lib is absent
try:
    from android_sms_gateway import api as _smsg_api  # type: ignore
    from android_sms_gateway import domain as _smsg_domain  # type: ignore
except Exception:  # pragma: no cover - environment without the lib
    _smsg_api = None
    _smsg_domain = None


# ---------------------------
# Internals
# ---------------------------

def _ensure_client(login: Optional[str] = None, password: Optional[str] = None):
    """Create and return an SMSGate API client; raises RuntimeError if SDK missing or creds invalid."""
    if _smsg_api is None:
        raise RuntimeError(
            "android-sms-gateway package is not available. Install it with `pip install android-sms-gateway`."
        )

    user = (login or _CONF_LOGIN or "").strip()
    pwd = (password or _CONF_PASSWORD or "").strip()

    if not user or not pwd:
        raise RuntimeError("Missing SMS credentials. Set ANDROID_SMS_GATEWAY_LOGIN/PASSWORD.")

    return _smsg_api.APIClient(user, pwd)


def _make_message(text: str, recipients: List[str]):
    if _smsg_domain is None:
        raise RuntimeError(
            "android-sms-gateway package is not available. Install it with `pip install android-sms-gateway`."
        )
    # with_delivery_report=True is required so we can poll status later
    return _smsg_domain.Message(text=text, phones=recipients, with_delivery_report=True)


def _extract_message_id(send_result: Any) -> Optional[str]:
    """Provider may return an object or dict; try common patterns."""
    if send_result is None:
        return None
    # Attribute style
    for attr in ("id", "message_id", "uuid"):
        if hasattr(send_result, attr):
            val = getattr(send_result, attr)
            if isinstance(val, (str, int)):
                return str(val)
    # Mapping style
    if isinstance(send_result, dict):
        for key in ("id", "message_id", "uuid"):
            if key in send_result and send_result[key] is not None:
                return str(send_result[key])
    return None


def _normalize_state(raw_state: Optional[str]) -> str:
    s = (raw_state or "").strip().lower()
    if s in {"queued", "queue", "pending"}:
        return "queued"
    if s in {"sent", "submitted"}:
        return "sent"
    if s in {"delivered", "ok", "success"}:
        return "delivered"
    if s in {"failed", "error", "undeliverable", "dead"}:
        return "failed"
    return "unknown"


# ---------------------------
# Public API
# ---------------------------

def send_bulk_sms(
    versions: List[Dict[str, str]],
    *,
    login: Optional[str] = None,
    password: Optional[str] = None,
) -> List[Dict[str, Optional[str]]]:
    """Send SMS messages sequentially.

    Args:
        versions: list of {"recipient": "+972...", "text": "..."}
        login, password: optional override credentials (usually omitted)

    Returns:
        A list with one entry per input item: {
            "recipient": str,
            "message_id": Optional[str],
            "error": Optional[str],
        }
    """

    results: List[Dict[str, Optional[str]]] = []

    if not isinstance(versions, list):
        return [{"recipient": None, "message_id": None, "error": "invalid_input"}]  # type: ignore

    if len(versions) == 0:
        return []

    if len(versions) > BATCH_CAP:
        return [
            {
                "recipient": v.get("recipient"),
                "message_id": None,
                "error": "batch_too_large",
            }
            for v in versions
        ]

    try:
        client = _ensure_client(login=login, password=password)
    except Exception as e:
        # If creds or SDK missing, nothing was sent; reflect the same error for all
        err = str(e)
        for v in versions:
            results.append({
                "recipient": v.get("recipient"),
                "message_id": None,
                "error": err,
            })
        return results

    # Sequential send; per-item isolation
    for v in versions:
        recipient = (v.get("recipient") or "").strip()
        text = v.get("text") or ""

        if not recipient or not text.strip():
            results.append({
                "recipient": recipient or None,
                "message_id": None,
                "error": "missing_recipient_or_text",
            })
            continue

        try:
            msg_obj = _make_message(text=text, recipients=[recipient])
            send_resp = client.send(msg_obj)
            mid = _extract_message_id(send_resp)
            if not mid:
                results.append({
                    "recipient": recipient,
                    "message_id": None,
                    "error": "no_message_id",
                })
            else:
                results.append({
                    "recipient": recipient,
                    "message_id": mid,
                    "error": None,
                })
        except Exception as e:
            results.append({
                "recipient": recipient,
                "message_id": None,
                "error": str(e),
            })

    return results


def get_sms_event(
    message_id: str,
    *,
    login: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """Fetch and normalize delivery state for a message.

    Returns a dict with keys: message_id, state, raw_state, updated_at.
    """
    if not message_id:
        raise ValueError("message_id is required")

    client = _ensure_client(login=login, password=password)

    try:
        provider_state = client.get_state(message_id)
    except Exception as e:
        # Surface failure to caller; they will present a translated error
        raise RuntimeError(f"failed_to_fetch_state: {e}") from e

    # provider_state may be an object or dict; try to read fields
    raw_state: Optional[str] = None
    updated_at: Optional[str] = None

    # Attribute style
    for attr in ("state", "status"):
        if hasattr(provider_state, attr):
            raw_state = getattr(provider_state, attr)
            break
    for attr in ("updated_at", "timestamp", "time", "updatedAt"):
        if hasattr(provider_state, attr):
            updated_at = getattr(provider_state, attr)
            break

    # Mapping style
    if isinstance(provider_state, dict):
        if raw_state is None:
            raw_state = provider_state.get("state") or provider_state.get("status")
        if updated_at is None:
            updated_at = (
                provider_state.get("updated_at")
                or provider_state.get("timestamp")
                or provider_state.get("time")
                or provider_state.get("updatedAt")
            )

    normalized = _normalize_state(raw_state)

    return {
        "message_id": str(message_id),
        "state": normalized,
        "raw_state": (raw_state if isinstance(raw_state, str) else None),
        "updated_at": (str(updated_at) if updated_at is not None else None),
    }


__all__ = [
    "send_bulk_sms",
    "get_sms_event",
    "BATCH_CAP",
]
