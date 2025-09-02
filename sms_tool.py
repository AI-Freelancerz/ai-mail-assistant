from typing import List, Dict, Optional
from android_sms_gateway import client, domain
from config import ANDROID_SMS_GATEWAY_LOGIN as login, ANDROID_SMS_GATEWAY_PASSWORD as password

def send_bulk_sms(versions: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Sends multiple SMS messages using the Android SMS Gateway.

    Args:
        versions: A list of dictionaries, where each dictionary contains:
            - "recipient": The phone number in E.164 format (e.g., "+1234567890").
            - "text": The SMS message content.

    Returns:
        A list of dictionaries, each containing:
            - "recipient": The original recipient phone number.
            - "message_id": The ID of the sent message if successful, otherwise None.
            - "error": An error message if sending failed for that recipient, otherwise None.
    """
    results = []
    with client.APIClient(login, password) as c:
        for version in versions:
            recipient = version.get("recipient")
            text = version.get("text")

            if not recipient or not text:
                results.append({"recipient": recipient, "message_id": None, "error": "Missing recipient or text"})
                continue

            try:
                message = domain.Message(
                    text,
                    [recipient],
                    with_delivery_report=True
                )
                state = c.send(message)
                results.append({"recipient": recipient, "message_id": state.id, "error": None})
            except Exception as e:
                results.append({"recipient": recipient, "message_id": None, "error": str(e)})
    return results

def get_sms_event(message_id: str) -> Dict[str, str]:
    """
    Retrieves the status of a sent SMS message.

    Args:
        message_id: The ID of the message to check.

    Returns:
        A dictionary containing the message status, typically with keys like:
            - "message_id": The ID of the message.
            - "state": The current state of the message (e.g., "queued", "sent", "delivered", "failed").
            - "updated_at": Timestamp of the last status update.
    """
    with client.APIClient(login, password) as c:
        status = c.get_state(message_id)
        return {
            "message_id": status.id,
            "state": status.state,
            "updated_at": status.updated_at.isoformat() if status.updated_at else None
        }
