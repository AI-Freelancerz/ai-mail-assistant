import datetime
import os
import base64
import json
import time

# Import Brevo SDK
import brevo_python as sib_api_v3_sdk
from brevo_python.rest import ApiException
from config import BREVO_API_KEY, FAILED_EMAILS_LOG_PATH  # Import your BREVO_API_KEY and log path constants


def _log_failed_email_to_file(sender_email, to_email, subject, body, error_message, log_path=FAILED_EMAILS_LOG_PATH):
    """Logs details of a failed email attempt to a file."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = (
        f"Timestamp: {timestamp}\n"
        f"Sender: {sender_email}\n"
        f"Recipient: {to_email}\n"
        f"Subject: {subject}\n"
        f"Error: {error_message}\n"
        f"Body Snippet: {body[:200]}...\n"
        f"{'-'*50}\n\n"
    )
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)

def _build_message_versions(messages):
    """
    Build and return a list of SendSmtpEmailMessageVersions instances
    for bulk batch sends.

    :param messages: List of dicts with keys 'to_email', 'to_name', 'subject', 'body'
    :return: List of sib_api_v3_sdk.SendSmtpEmailMessageVersions
    """
    versions = []

    for i, msg in enumerate(messages):
        to_email = msg['to_email']
        to_name = msg.get('to_name', '')
        subject = msg.get('subject', '')
        body = msg.get('body', '')
        html_body = body.replace('\n', '<br>')

        # Create nested SDK model objects
        to_obj = sib_api_v3_sdk.SendSmtpEmailTo(email=to_email, name=to_name)
        version_obj = sib_api_v3_sdk.SendSmtpEmailMessageVersions(
            to=[to_obj],
            subject=subject,
            html_content=html_body
        )
        versions.append(version_obj)

    return versions


def send_email_message(sender_email, sender_name, to_email, to_name, subject, body, attachments=None):
    """Send a single transactional email."""
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = BREVO_API_KEY
    api = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

    # Process attachments
    attachment_list = []
    if attachments:
        for path in attachments:
            try:
                with open(path, 'rb') as f:
                    data = f.read()
                encoded = base64.b64encode(data).decode('utf-8')
                attachment_list.append({
                    'content': encoded,
                    'name': os.path.basename(path)
                })
            except Exception as e:
                _log_failed_email_to_file(sender_email, to_email, subject, body, str(e))

    html_body = body.replace('\n', '<br>')
    email_args = {
        'sender': {'email': sender_email, 'name': sender_name},
        'to': [ {'email': to_email, 'name': to_name} ],
        'subject': subject,
        'html_content': html_body,
    }
    if attachment_list:
        email_args['attachment'] = attachment_list

    email_model = sib_api_v3_sdk.SendSmtpEmail(**email_args)

    try:
        response = api.send_transac_email(email_model)
        return {'status': 'success', 'response': response}
    except ApiException as e:
        err = e.body if hasattr(e, 'body') else str(e)
        _log_failed_email_to_file(sender_email, to_email, subject, body, err)
        return {'status': 'error', 'message': err}


def send_bulk_email_messages(sender_email, sender_name, messages, attachments=None):
    """Send multiple transactional emails in one batch call."""
    if not messages:
        return {'status': 'error', 'message': 'No messages provided'}

    if len(messages) > 2000:
        return {'status': 'error', 'message': 'Brevo limit is 2000 recipients per batch'}

    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = BREVO_API_KEY
    api = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

    # Process attachments once
    attachment_list = []
    if attachments:
        for path in attachments:
            try:
                with open(path, 'rb') as f:
                    data = f.read()
                encoded = base64.b64encode(data).decode('utf-8')
                attachment_list.append({'content': encoded, 'name': os.path.basename(path)})
            except Exception as e:
                pass

    # Build versions with proper SDK models
    versions = _build_message_versions(messages)

    # Use first message as global default
    first = messages[0]
    global_html = first.get('body', '').replace('\n', '<br>')
    global_subject = first.get('subject', '')

    batch_args = {
        'sender': {'email': sender_email, 'name': sender_name},
        'subject': global_subject,
        'html_content': global_html,
        'message_versions': versions
    }
    if attachment_list:
        batch_args['attachment'] = attachment_list

    batch_model = sib_api_v3_sdk.SendSmtpEmail(**batch_args)

    try:
        response = api.send_transac_email(batch_model)
        # Extract message IDs from the response
        message_ids = []
        if hasattr(response, 'message_ids') and response.message_ids:
            message_ids = response.message_ids
        elif hasattr(response, 'message_id') and response.message_id:
            message_ids = [response.message_id]
        
        return {
            'status': 'success', 
            'response': response,
            'message_ids': message_ids,
            'total_sent': len(message_ids)
        }
    except ApiException as e:
        err = e.body if hasattr(e, 'body') else str(e)
        for msg in messages:
            _log_failed_email_to_file(sender_email, msg['to_email'], msg.get('subject', ''), msg.get('body', ''), err)
        return {'status': 'error', 'message': err}

def get_email_events(message_ids: list):
    """
    Retrieves the event history for a list of message IDs from Brevo.

    :param message_ids: A list of message ID strings (e.g., '<...-...@smtp-relay.mailin.fr>').
    :return: A dictionary where keys are message IDs and values are a list of event dicts
             or a list containing a single error event dict.
    """
    if not message_ids:
        return {}

    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = BREVO_API_KEY
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

    results = {}
    for msg_id in message_ids:
        if not isinstance(msg_id, str) or '@' not in msg_id:
            results[msg_id] = [{'event': 'error', 'reason': 'Invalid Message ID format'}]
            continue

        try:
            # The API expects the full message_id, often including angle brackets
            api_response = api_instance.get_email_event_report(message_id=msg_id)
            # The response object has an 'events' attribute which is a list of objects
            results[msg_id] = [e.to_dict() for e in api_response.events] if api_response.events else []
        except ApiException as e:
            err_body = e.body
            try:
                # Brevo often returns JSON in the body, try to parse it
                err_json = json.loads(err_body)
                err_reason = err_json.get('message', err_body)
            except (json.JSONDecodeError, AttributeError):
                err_reason = str(err_body)
            results[msg_id] = [{'event': 'error', 'reason': err_reason}]
        except Exception as e:
            results[msg_id] = [{'event': 'error', 'reason': str(e)}]

        # A small delay to avoid hitting API rate limits.
        time.sleep(0.3)

    return results
