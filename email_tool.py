import datetime
import os
import base64
import json
import time
import logging
import warnings
from typing import Dict, List, Optional, Tuple
from functools import wraps

# Import Brevo SDK
import brevo_python as sib_api_v3_sdk
from brevo_python.rest import ApiException
from config import (
    BREVO_API_KEY, 
    FAILED_EMAILS_LOG_PATH,
    EMAIL_MAX_RETRIES,
    EMAIL_INITIAL_RETRY_DELAY,
    EMAIL_MAX_RETRY_DELAY,
    EMAIL_RATE_LIMIT_DELAY,
    EMAIL_CHUNK_DELAY,
    EMAIL_DEFAULT_CHUNK_SIZE,
    EMAIL_MAX_ATTACHMENT_SIZE_MB
)

# === CONFIGURATION CONSTANTS ===
# Import from config for consistency
MAX_RETRIES = EMAIL_MAX_RETRIES
INITIAL_RETRY_DELAY = EMAIL_INITIAL_RETRY_DELAY
MAX_RETRY_DELAY = EMAIL_MAX_RETRY_DELAY
RATE_LIMIT_DELAY = EMAIL_RATE_LIMIT_DELAY
CHUNK_DELAY = EMAIL_CHUNK_DELAY
DEFAULT_CHUNK_SIZE = EMAIL_DEFAULT_CHUNK_SIZE
MAX_ATTACHMENT_SIZE_BYTES = EMAIL_MAX_ATTACHMENT_SIZE_MB * 1024 * 1024

# Error categories for intelligent retry logic
RETRYABLE_ERROR_CODES = {429, 500, 502, 503, 504}  # HTTP status codes worth retrying
PERMANENT_ERROR_CODES = {400, 401, 403, 404}  # Don't retry these


def _log_failed_email_to_file(sender_email, to_email, subject, body, error_message, log_path=FAILED_EMAILS_LOG_PATH):
    """Logs details of a failed email attempt to a file."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = (
        f"Timestamp: {timestamp}\n"
        f"Sender: {sender_email}\n"
        f"Recipient: {to_email}\n"
        f"Subject: {subject}\n"
        f"Error: {error_message}\n"
        f"Body Snippet: {body[:200] if body else 'N/A'}...\n"
        f"{'-'*50}\n\n"
    )
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        logging.error(f"Failed to write to log file {log_path}: {e}")


def _categorize_api_error(exception: ApiException) -> Tuple[bool, str]:
    """
    Categorize an API exception to determine if it's retryable.
    
    Returns:
        Tuple of (is_retryable: bool, error_message: str)
    """
    try:
        status_code = exception.status if hasattr(exception, 'status') else None
        error_body = exception.body if hasattr(exception, 'body') else str(exception)
        
        # Try to parse error body as JSON for more details
        try:
            error_json = json.loads(error_body)
            error_message = error_json.get('message', error_body)
        except (json.JSONDecodeError, TypeError):
            error_message = str(error_body)
        
        # Determine if retryable based on status code
        if status_code in RETRYABLE_ERROR_CODES:
            return True, f"Retryable error (HTTP {status_code}): {error_message}"
        elif status_code in PERMANENT_ERROR_CODES:
            return False, f"Permanent error (HTTP {status_code}): {error_message}"
        else:
            # Unknown error - be conservative and allow retry
            return True, f"Unknown error (HTTP {status_code}): {error_message}"
            
    except Exception as e:
        # If we can't categorize, assume retryable to be safe
        return True, f"Error categorization failed: {str(e)}"


def retry_with_exponential_backoff(max_retries=MAX_RETRIES):
    """
    Decorator that implements exponential backoff retry logic for API calls.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                    
                except ApiException as e:
                    is_retryable, error_msg = _categorize_api_error(e)
                    last_exception = e
                    
                    if not is_retryable:
                        logging.error(f"[EMAIL_TOOL] Permanent error in {func.__name__}: {error_msg}")
                        raise  # Don't retry permanent errors
                    
                    if attempt < max_retries - 1:  # Don't sleep on last attempt
                        delay = min(INITIAL_RETRY_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
                        logging.warning(
                            f"[EMAIL_TOOL] Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {error_msg}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                    else:
                        logging.error(
                            f"[EMAIL_TOOL] All {max_retries} attempts failed for {func.__name__}: {error_msg}"
                        )
                        
                except Exception as e:
                    # Non-API exceptions (network errors, etc.) are also retryable
                    last_exception = e
                    
                    if attempt < max_retries - 1:
                        delay = min(INITIAL_RETRY_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
                        logging.warning(
                            f"[EMAIL_TOOL] Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {str(e)}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                    else:
                        logging.error(
                            f"[EMAIL_TOOL] All {max_retries} attempts failed for {func.__name__}: {str(e)}"
                        )
            
            # If we get here, all retries failed
            raise last_exception
            
        return wrapper
    return decorator


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
    """
    Send a single transactional email with retry logic.
    
    Args:
        sender_email: Sender's email address
        sender_name: Sender's display name
        to_email: Recipient's email address
        to_name: Recipient's name
        subject: Email subject
        body: Email body (plain text, will be converted to HTML)
        attachments: Optional list of file paths to attach
        
    Returns:
        Dictionary with 'status' (success/error) and additional info
    """
    # Input validation
    if not to_email or '@' not in to_email:
        error_msg = f"Invalid email address: {to_email}"
        logging.error(f"[EMAIL_TOOL] {error_msg}")
        return {'status': 'error', 'message': error_msg}
    
    return _send_email_message_with_retry(sender_email, sender_name, to_email, to_name, subject, body, attachments)


@retry_with_exponential_backoff(max_retries=MAX_RETRIES)
def _send_email_message_with_retry(sender_email, sender_name, to_email, to_name, subject, body, attachments=None):
    """Internal function with retry decorator applied."""
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
                logging.error(f"[EMAIL_TOOL] Failed to process attachment {path}: {e}")
                _log_failed_email_to_file(sender_email, to_email, subject, body, f"Attachment error: {str(e)}")

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
        logging.info(f"[EMAIL_TOOL] Successfully sent email to {to_email}")
        return {'status': 'success', 'response': response}
    except ApiException as e:
        is_retryable, err_msg = _categorize_api_error(e)
        _log_failed_email_to_file(sender_email, to_email, subject, body, err_msg)
        
        # Re-raise to trigger retry logic
        raise


def send_bulk_email_messages(sender_email, sender_name, messages, attachments=None, chunk_size=None, 
                              progress_callback=None):
    """
    Send multiple transactional emails in one or more batch calls with retry logic and progress tracking.
    Automatically splits the message list into chunks to respect API limits.
    
    Args:
        sender_email: Sender's email address
        sender_name: Sender's display name  
        messages: List of message dictionaries with keys 'to_email', 'to_name', 'subject', 'body'
        attachments: Optional list of attachment file paths
        chunk_size: Maximum messages per API call (default DEFAULT_CHUNK_SIZE)
        progress_callback: Optional callback function(current, total, message) for progress updates
    
    Returns:
        Dictionary with:
            - status: 'success' | 'partial' | 'error'
                * 'success': All emails sent successfully
                * 'partial': Some emails sent, some failed
                * 'error': All emails failed
            - message: Summary message string
            - message_ids: List of successfully sent message IDs (strings)
            - total_sent: Number of successfully sent emails (int)
            - failed_count: Number of failed emails (int)
            - failed_emails: List of failed email addresses (strings)
            - duplicates_removed: Number of duplicate emails removed (int)
    
    Note:
        This function is called by streamlit_app.py with chunk_size=500 and progress_callback.
        Ensure status values match what UI expects: 'success', 'partial', 'error'.
        Message IDs align with messages list order (accounting for failed sends).
            - failed_emails: List of failed email addresses
    """
    logging.info(f"[EMAIL_TOOL] Starting bulk email send for {len(messages)} messages")
    
    if not messages:
        logging.warning("[EMAIL_TOOL] No messages provided for sending")
        return {
            'status': 'error', 
            'message': 'No messages provided',
            'total_sent': 0,
            'failed_count': 0,
            'message_ids': [],
            'failed_emails': []
        }
    
    # Use default chunk size if not provided
    if chunk_size is None:
        chunk_size = DEFAULT_CHUNK_SIZE
    
    # Deduplicate messages by email address
    unique_messages = _deduplicate_messages(messages)
    duplicates_removed = len(messages) - len(unique_messages)
    
    if duplicates_removed > 0:
        logging.info(f"[EMAIL_TOOL] Removed {duplicates_removed} duplicate email addresses")
        if progress_callback:
            progress_callback(0, len(unique_messages), 
                            f"Removed {duplicates_removed} duplicate email addresses")
    
    total_messages = len(unique_messages)
    successful_sends = 0
    failed_sends = 0
    all_message_ids = []
    failed_emails = []
    
    # Process attachments once for all chunks
    attachment_list = []
    if attachments:
        logging.info(f"[EMAIL_TOOL] Processing {len(attachments)} attachment(s)")
        attachment_list = _process_attachments(attachments, sender_email)
    
    # Chunk the messages and process each chunk
    # Note: Each message has its own subject and body for personalization
    total_chunks = (total_messages + chunk_size - 1) // chunk_size
    
    for chunk_idx in range(0, total_messages, chunk_size):
        chunk = unique_messages[chunk_idx:chunk_idx + chunk_size]
        chunk_num = (chunk_idx // chunk_size) + 1
        
        logging.info(f"[EMAIL_TOOL] Processing chunk {chunk_num}/{total_chunks}: messages {chunk_idx} to {chunk_idx+len(chunk)}")
        
        if progress_callback:
            progress_callback(successful_sends, total_messages, 
                            f"Processing chunk {chunk_num}/{total_chunks}...")
        
        try:
            # Send chunk with retry logic (each message has its own subject/body)
            chunk_result = _send_email_chunk_with_retry(
                sender_email, sender_name, chunk, attachment_list
            )
            
            # Process successful sends
            message_ids = chunk_result.get('message_ids', [])
            all_message_ids.extend(message_ids)
            successful_sends += len(message_ids)
            
            logging.info(f"[EMAIL_TOOL] Chunk {chunk_num} sent successfully: {len(message_ids)} emails")
            
            if progress_callback:
                progress_callback(successful_sends, total_messages, 
                                f"Chunk {chunk_num} completed: {len(message_ids)} emails sent")
            
        except ApiException as e:
            # Chunk failed after all retries
            is_retryable, err_msg = _categorize_api_error(e)
            logging.error(f"[EMAIL_TOOL] Chunk {chunk_num} failed permanently: {err_msg}")
            
            # Mark all emails in this chunk as failed
            failed_sends += len(chunk)
            failed_emails.extend([msg['to_email'] for msg in chunk])
            
            _log_failed_email_to_file(
                sender_email, "Bulk Send", "Batch Send Failed", 
                f"Chunk {chunk_num} (messages {chunk_idx} to {chunk_idx+len(chunk)})", 
                err_msg
            )
            
            if progress_callback:
                progress_callback(successful_sends, total_messages, 
                                f"⚠️ Chunk {chunk_num} failed: {err_msg[:100]}")
            
            # Continue processing other chunks
            continue
            
        except Exception as e:
            # Unexpected error
            logging.error(f"[EMAIL_TOOL] Unexpected error in chunk {chunk_num}: {str(e)}")
            failed_sends += len(chunk)
            failed_emails.extend([msg['to_email'] for msg in chunk])
            
            if progress_callback:
                progress_callback(successful_sends, total_messages, 
                                f"⚠️ Chunk {chunk_num} failed unexpectedly")
            
            continue
        
        # Rate limiting: Add delay between chunks
        if chunk_idx + chunk_size < total_messages:
            time.sleep(CHUNK_DELAY)
    
    # Determine overall status
    if failed_sends == 0:
        status = 'success'
    elif successful_sends == 0:
        status = 'error'
    else:
        status = 'partial'
    
    logging.info(
        f"[EMAIL_TOOL] Bulk send completed: {successful_sends} sent, {failed_sends} failed "
        f"out of {total_messages} ({duplicates_removed} duplicates removed)"
    )
    
    return {
        'status': status,
        'message': f"{successful_sends}/{total_messages} emails sent successfully. {failed_sends} failed.",
        'total_sent': successful_sends,
        'message_ids': all_message_ids,
        'failed_count': failed_sends,
        'failed_emails': failed_emails,
        'duplicates_removed': duplicates_removed
    }


def _deduplicate_messages(messages: List[Dict]) -> List[Dict]:
    """
    Remove duplicate email addresses from message list, keeping the first occurrence.
    
    Args:
        messages: List of message dictionaries
        
    Returns:
        List of unique messages
    """
    seen_emails = set()
    unique_messages = []
    
    for msg in messages:
        email = msg.get('to_email', '').lower().strip()
        if email and email not in seen_emails:
            seen_emails.add(email)
            unique_messages.append(msg)
        elif email in seen_emails:
            logging.debug(f"[EMAIL_TOOL] Skipping duplicate email: {email}")
    
    return unique_messages


def _process_attachments(attachments: List[str], sender_email: str) -> List[Dict]:
    """
    Process attachment files and convert to base64.
    
    Args:
        attachments: List of file paths
        sender_email: Sender email for logging
        
    Returns:
        List of attachment dictionaries with 'content' and 'name' keys
    """
    attachment_list = []
    
    for path in attachments:
        try:
            if not os.path.exists(path):
                logging.error(f"[EMAIL_TOOL] Attachment file not found: {path}")
                continue
                
            file_size = os.path.getsize(path)
            if file_size > MAX_ATTACHMENT_SIZE_BYTES:
                logging.error(
                    f"[EMAIL_TOOL] Attachment too large ({file_size / (1024*1024):.2f}MB, "
                    f"max {EMAIL_MAX_ATTACHMENT_SIZE_MB}MB): {path}"
                )
                continue
            
            with open(path, 'rb') as f:
                data = f.read()
            encoded = base64.b64encode(data).decode('utf-8')
            attachment_list.append({
                'content': encoded,
                'name': os.path.basename(path)
            })
            logging.info(f"[EMAIL_TOOL] Processed attachment: {os.path.basename(path)} ({file_size / 1024:.1f}KB)")
            
        except Exception as e:
            logging.error(f"[EMAIL_TOOL] Failed to process attachment {path}: {e}")
            _log_failed_email_to_file(sender_email, "N/A", "Attachment Error", "", str(e))
    
    return attachment_list


@retry_with_exponential_backoff(max_retries=MAX_RETRIES)
def _send_email_chunk_with_retry(sender_email: str, sender_name: str, chunk: List[Dict],
                                  attachment_list: List[Dict]) -> Dict:
    """
    Send a chunk of emails with retry logic applied.
    Each message in the chunk has its own personalized subject and body.
    
    Args:
        sender_email: Sender's email address
        sender_name: Sender's display name
        chunk: List of message dictionaries (each with 'subject', 'body', 'to_email', 'to_name')
        attachment_list: List of processed attachments
        
    Returns:
        Dictionary with 'message_ids' list
    """
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = BREVO_API_KEY
    api = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
    
    # Build versions for the current chunk (each with its own subject/body)
    versions = _build_message_versions(chunk)
    
    # Build batch request
    # Note: When using message_versions, the global subject/html_content are optional fallbacks
    # Since we're setting subject/html_content in each version, we don't need global ones
    batch_args = {
        'sender': {'email': sender_email, 'name': sender_name},
        'message_versions': versions,
    }
    
    # Only add attachments if present
    if attachment_list and len(attachment_list) > 0:
        batch_args['attachment'] = attachment_list
    
    # Rate limiting before API call
    time.sleep(RATE_LIMIT_DELAY)
    
    response = api.send_transac_email(sib_api_v3_sdk.SendSmtpEmail(**batch_args))
    
    # Extract message IDs from response
    message_ids = _extract_message_ids(response, len(chunk))
    
    return {'message_ids': message_ids}


def _extract_message_ids(response, expected_count: int) -> List[str]:
    """
    Extract message IDs from API response with fallback handling.
    
    Args:
        response: API response object
        expected_count: Number of messages sent
        
    Returns:
        List of message ID strings
    """
    message_ids = []
    
    if hasattr(response, 'message_ids') and response.message_ids:
        message_ids = response.message_ids
    elif hasattr(response, 'message_id') and response.message_id:
        message_ids = [response.message_id]
    else:
        # Try to convert to dict
        try:
            response_dict = response.to_dict()
            message_ids = response_dict.get('messageIds', [])
        except:
            # Last resort: generate placeholder IDs
            logging.warning("[EMAIL_TOOL] Could not extract message IDs from response")
            message_ids = [f"unknown_id_{i}_{int(time.time())}" for i in range(expected_count)]
    
    return message_ids

    
def get_email_events(message_ids: list, max_retries: int = 2):
    """
    Retrieves the event history for a list of message IDs from Brevo with retry logic.

    Args:
        message_ids: A list of message ID strings (e.g., '<...-...@smtp-relay.mailin.fr>')
        max_retries: Maximum number of retry attempts per message (default 2)
    
    Returns:
        A dictionary where keys are message IDs and values are a list of event dicts
        or a list containing a single error event dict.
    """
    if not message_ids:
        return {}

    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = BREVO_API_KEY
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

    results = {}
    
    for msg_id in message_ids:
        # Validate message ID format
        if not isinstance(msg_id, str) or '@' not in msg_id:
            results[msg_id] = [{'event': 'error', 'reason': 'Invalid Message ID format'}]
            continue

        # Retry logic for each message ID
        last_error = None
        for attempt in range(max_retries):
            try:
                # Rate limiting
                time.sleep(RATE_LIMIT_DELAY)
                
                # The API expects the full message_id, often including angle brackets
                api_response = api_instance.get_email_event_report(message_id=msg_id)
                
                # Success - extract events
                results[msg_id] = [e.to_dict() for e in api_response.events] if api_response.events else []
                break  # Success, exit retry loop
                
            except ApiException as e:
                last_error = e
                is_retryable, err_msg = _categorize_api_error(e)
                
                # If it's a permanent error (like 404), don't retry
                if not is_retryable:
                    results[msg_id] = [{'event': 'error', 'reason': err_msg}]
                    break
                
                # If retryable and not last attempt, continue
                if attempt < max_retries - 1:
                    delay = min(INITIAL_RETRY_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
                    logging.warning(
                        f"[EMAIL_TOOL] Failed to get events for {msg_id} (attempt {attempt + 1}/{max_retries}). "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    # Last attempt failed
                    results[msg_id] = [{'event': 'error', 'reason': err_msg}]
                    
            except Exception as e:
                last_error = e
                
                if attempt < max_retries - 1:
                    delay = min(INITIAL_RETRY_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
                    logging.warning(
                        f"[EMAIL_TOOL] Unexpected error for {msg_id} (attempt {attempt + 1}/{max_retries}): {str(e)}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    results[msg_id] = [{'event': 'error', 'reason': str(e)}]

    return results
