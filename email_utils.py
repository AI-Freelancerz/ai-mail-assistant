"""
Email Deliverability Utilities

Helper functions for:
- HTML to plain-text conversion
- Content validation (spam triggers, link density)
- Send time validation
- Reputation monitoring
"""

import re
import html
import logging
from datetime import datetime
from typing import Tuple, List, Dict
import config

logger = logging.getLogger(__name__)


def html_to_plain_text(html_body: str) -> str:
    """
    Convert HTML email body to clean plain-text version.
    
    Required for RFC-compliant multipart emails and better spam scores.
    
    Args:
        html_body: HTML email content
        
    Returns:
        Clean plain-text version
    """
    if not html_body:
        return ""
    
    # Decode HTML entities first
    text = html.unescape(html_body)
    
    # Replace <br> and <p> tags with newlines
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</?p>', '\n', text, flags=re.IGNORECASE)
    
    # Replace list items with dashes
    text = re.sub(r'<li>', '\n- ', text, flags=re.IGNORECASE)
    
    # Add newlines before headings
    text = re.sub(r'<h[1-6]>', '\n\n', text, flags=re.IGNORECASE)
    
    # Remove all remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Clean up excessive whitespace
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Max 2 consecutive newlines
    text = re.sub(r' +', ' ', text)  # Multiple spaces to single space
    
    # Strip leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    
    return text.strip()


def detect_spam_triggers(subject: str, body: str) -> List[str]:
    """
    Detect spam trigger words in email content.
    
    Args:
        subject: Email subject line
        body: Email body (plain text or HTML)
        
    Returns:
        List of detected trigger words/issues
    """
    warnings = []
    
    # Combine subject and body for analysis
    full_content = f"{subject} {body}".lower()
    
    # Check for spam trigger words
    detected_words = []
    for trigger_word in config.SPAM_TRIGGER_WORDS:
        if trigger_word in full_content:
            detected_words.append(trigger_word)
    
    if detected_words:
        warnings.append(f"Spam trigger words detected: {', '.join(detected_words[:3])}")
    
    # Check for excessive capitalization in subject
    if subject and sum(1 for c in subject if c.isupper()) / len(subject) > 0.5:
        warnings.append("Subject has excessive capital letters")
    
    # Check for excessive exclamation marks
    exclamation_count = full_content.count('!')
    if exclamation_count > 3:
        warnings.append(f"Excessive exclamation marks ({exclamation_count})")
    
    # Check for excessive question marks
    question_count = full_content.count('?')
    if question_count > 2:
        warnings.append(f"Multiple question marks ({question_count})")
    
    # Check for empty subject
    if not subject or not subject.strip():
        warnings.append("Empty or missing subject line")
    
    return warnings


def calculate_link_density(body: str) -> Tuple[int, float]:
    """
    Calculate link density in email body.
    
    High link density is a spam indicator.
    
    Args:
        body: Email body (HTML or plain text)
        
    Returns:
        Tuple of (link_count, text_to_link_ratio)
    """
    # Count HTTP/HTTPS links
    link_pattern = r'https?://[^\s<>"\']+|www\.[^\s<>"\']+' 
    links = re.findall(link_pattern, body, re.IGNORECASE)
    link_count = len(links)
    
    # Calculate text length (excluding HTML tags)
    plain_text = html_to_plain_text(body)
    text_length = len(plain_text)
    
    # Calculate total link length
    link_length = sum(len(link) for link in links)
    
    # Ratio of text to links
    if link_length > 0:
        ratio = text_length / link_length
    else:
        ratio = float('inf')
    
    return link_count, ratio


def validate_email_content(subject: str, body: str) -> Tuple[bool, List[str]]:
    """
    Comprehensive email content validation.
    
    Args:
        subject: Email subject
        body: Email body
        
    Returns:
        Tuple of (is_valid, list_of_warnings)
    """
    warnings = []
    
    # Spam trigger detection
    if config.EMAIL_BLOCK_SPAM_TRIGGERS:
        spam_warnings = detect_spam_triggers(subject, body)
        warnings.extend(spam_warnings)
    
    # Link density check
    link_count, link_ratio = calculate_link_density(body)
    if link_count > config.EMAIL_MAX_LINK_DENSITY:
        warnings.append(
            f"High link count: {link_count} links "
            f"(max recommended: {config.EMAIL_MAX_LINK_DENSITY})"
        )
    
    # Body length check
    plain_body = html_to_plain_text(body)
    if len(plain_body) < 50:
        warnings.append("Email body is very short (< 50 characters)")
    
    # Check for very long emails (may truncate on mobile)
    if len(plain_body) > 10000:
        warnings.append("Email body is very long (> 10,000 characters)")
    
    # If blocking spam triggers, fail validation on certain issues
    blocking_keywords = ['empty or missing subject', 'excessive capital letters']
    has_blocking_issue = any(
        any(keyword in warning.lower() for keyword in blocking_keywords)
        for warning in warnings
    )
    
    is_valid = not has_blocking_issue
    
    return is_valid, warnings


def is_safe_send_time() -> Tuple[bool, str]:
    """
    Check if current time is within safe sending hours.
    
    Safe sending = business hours (Mon-Fri, 8 AM - 6 PM local time)
    Higher engagement and better for sender reputation.
    
    Returns:
        Tuple of (is_safe, reason_message)
    """
    if not config.EMAIL_REQUIRE_SAFE_SEND_TIME:
        return True, "Send time restrictions disabled"
    
    now = datetime.now()
    
    # Check day of week (0=Monday, 6=Sunday)
    if now.weekday() not in config.EMAIL_SEND_DAYS:
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        return False, f"Current day is {day_names[now.weekday()]}. Only send Monday-Friday."
    
    # Check hour of day
    if not (config.EMAIL_SEND_HOURS_START <= now.hour < config.EMAIL_SEND_HOURS_END):
        return False, (
            f"Current time is {now.hour}:00. "
            f"Only send between {config.EMAIL_SEND_HOURS_START}:00 - "
            f"{config.EMAIL_SEND_HOURS_END}:00."
        )
    
    return True, "Safe send time"


def build_email_headers(unsubscribe_url: str = None, campaign_id: str = None) -> Dict[str, str]:
    """
    Build RFC-compliant email headers for better deliverability.
    
    Includes:
    - List-Unsubscribe (RFC 2369)
    - List-Unsubscribe-Post (RFC 8058 one-click)
    - Campaign tracking headers
    
    Args:
        unsubscribe_url: URL for one-click unsubscribe
        campaign_id: Campaign identifier for tracking
        
    Returns:
        Dict of email headers
    """
    headers = {
        'Precedence': 'bulk',  # Indicates bulk mail
        'X-Mailer': 'Migdal-Mailer/2.0',
    }
    
    # Add campaign ID if provided
    if campaign_id:
        headers['X-Campaign-ID'] = campaign_id
    
    # Add List-Unsubscribe headers (CRITICAL for Gmail/Yahoo)
    if config.EMAIL_REQUIRE_LIST_UNSUBSCRIBE:
        if config.EMAIL_UNSUBSCRIBE_METHOD == "brevo":
            # Use Brevo's built-in unsubscribe (recommended)
            # The {{unsubscribe}} tag will be in footer, headers handled by Brevo
            pass
        elif unsubscribe_url:
            # Custom unsubscribe URL
            headers['List-Unsubscribe'] = f'<{unsubscribe_url}>'
            headers['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'
    
    return headers


def format_unsubscribe_footer(email: str, method: str = None) -> str:
    """
    Generate unsubscribe footer HTML.
    
    Args:
        email: Recipient email address
        method: Unsubscribe method ("brevo" or "custom")
        
    Returns:
        HTML footer with unsubscribe link
    """
    if not method:
        method = config.EMAIL_UNSUBSCRIBE_METHOD
    
    if method == "brevo":
        # Use Brevo's merge tag for automatic unsubscribe handling
        unsubscribe_link = '{{ unsubscribe }}'
    else:
        # Use legacy Google Forms or custom URL
        unsubscribe_link = config.GOOGLE_FORM_UNSUBSCRIBE_URL_TEMPLATE + email
    
    footer_html = f"""
<br><br>
<div style="text-align: center; font-size: 12px; color: #888888; margin-top: 40px; border-top: 1px solid #dddddd; padding-top: 20px;">
    <p style="margin: 5px 0;">
        <strong>Migdal France</strong><br>
        38 rue Servan, 75011 Paris<br>
        <a href="http://www.migdal.org" style="color: #4A90E2; text-decoration: none;">www.migdal.org</a>
    </p>
    <p style="margin: 15px 0;">
        <a href="{unsubscribe_link}" style="color: #888888; text-decoration: underline;">
            Se désinscrire
        </a>
    </p>
</div>
"""
    return footer_html


def get_domain_from_email(email: str) -> str:
    """Extract domain from email address"""
    if '@' in email:
        return email.split('@')[1].lower()
    return ""


def is_gmail_address(email: str) -> bool:
    """Check if email is from Gmail domain"""
    return get_domain_from_email(email) == "gmail.com"
