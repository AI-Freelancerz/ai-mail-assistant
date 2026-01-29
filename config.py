# CHANGELOG
# - v0.3 (2025-11-05): Add email sending configuration parameters for reliability improvements.
# - v0.2 (2025-09-01): Add AI_MESSENGER_MODE env gate ("email" default; "sms" enables SMS-only UI).
# - v0.1: Consolidated secrets access and log path.

# config.py - Consolidated Secrets Access and Configuration

import streamlit as st

# --- SECRETS CONFIGURATION ---
# Get the entire 'app_credentials' section as a dictionary from Streamlit Secrets
APP_CREDENTIALS = st.secrets.get("app_credentials", {})

# --- APP MODE CONFIGURATION ---
# Controls which UI the app renders. Set AI_MESSENGER_MODE="sms" to enable SMS-only mode.
AI_MESSENGER_MODE = APP_CREDENTIALS.get("AI_MESSENGER_MODE", "email")

# Extract individual credentials from the APP_CREDENTIALS dictionary
SENDER_EMAIL = APP_CREDENTIALS.get("SENDER_EMAIL")
# SENDER_PASSWORD is no longer needed for Brevo API authentication.
OPENAI_API_KEY = APP_CREDENTIALS.get("OPENAI_API_KEY")
BREVO_API_KEY = APP_CREDENTIALS.get("BREVO_API_KEY")

# The SENDER_CREDENTIALS dictionary is also no longer necessary
# as Brevo uses API keys for authentication.

# --- ANDROID SMS GATEWAY CONFIGURATION ---
ANDROID_SMS_GATEWAY_LOGIN = APP_CREDENTIALS.get("ANDROID_SMS_GATEWAY_LOGIN")
ANDROID_SMS_GATEWAY_PASSWORD = APP_CREDENTIALS.get("ANDROID_SMS_GATEWAY_PASSWORD")

# --- LOGGING CONFIGURATION ---
# Path for logging failed email attempts. This is not a secret.
FAILED_EMAILS_LOG_PATH = "logs/failed_emails.log" # This path will be created in your app's root directory on Streamlit Cloud

# === EMAIL SENDING CONFIGURATION ===
# These parameters control the reliability and performance of email sending
# Can be overridden in Streamlit secrets for production tuning

# Helper functions for safe type conversion with fallback defaults
def _safe_int(value, default):
    """Safely convert to int with fallback to default on error"""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def _safe_float(value, default):
    """Safely convert to float with fallback to default on error"""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default

# Retry configuration
EMAIL_MAX_RETRIES = _safe_int(APP_CREDENTIALS.get("EMAIL_MAX_RETRIES"), 3)
EMAIL_INITIAL_RETRY_DELAY = _safe_float(APP_CREDENTIALS.get("EMAIL_INITIAL_RETRY_DELAY"), 2.0)  # seconds
EMAIL_MAX_RETRY_DELAY = _safe_float(APP_CREDENTIALS.get("EMAIL_MAX_RETRY_DELAY"), 60.0)  # seconds

# Rate limiting configuration
EMAIL_RATE_LIMIT_DELAY = _safe_float(APP_CREDENTIALS.get("EMAIL_RATE_LIMIT_DELAY"), 0.1)  # seconds between API calls
EMAIL_CHUNK_DELAY = _safe_float(APP_CREDENTIALS.get("EMAIL_CHUNK_DELAY"), 1.0)  # seconds between chunks

# Batch size configuration
# Conservative default of 500 (Brevo allows up to 2000)
# Lower values = more reliable, better error isolation, slower overall
# Higher values = faster, but one error affects more emails
EMAIL_DEFAULT_CHUNK_SIZE = _safe_int(APP_CREDENTIALS.get("EMAIL_DEFAULT_CHUNK_SIZE"), 500)

# Attachment configuration
EMAIL_MAX_ATTACHMENT_SIZE_MB = _safe_int(APP_CREDENTIALS.get("EMAIL_MAX_ATTACHMENT_SIZE_MB"), 10)  # MB per attachment

# === DOMAIN AUTHENTICATION & SENDER REPUTATION ===
# CRITICAL: Use verified organizational domain, NOT @gmail.com
# Gmail prohibits bulk sending and causes DMARC failures
SENDER_DOMAIN = APP_CREDENTIALS.get("SENDER_DOMAIN", "migdal.org")  # Your verified domain
REQUIRE_DOMAIN_VERIFICATION = APP_CREDENTIALS.get("REQUIRE_DOMAIN_VERIFICATION", "true").lower() == "true"

# === SUPPRESSION LIST MANAGEMENT ===
# Never send to addresses that bounced, complained, or unsubscribed
EMAIL_SUPPRESSION_LIST_PATH = "suppression_list.csv"
EMAIL_AUTO_SUPPRESS_HARD_BOUNCE = True  # Automatically add hard bounces
EMAIL_AUTO_SUPPRESS_COMPLAINTS = True   # Automatically add spam complaints
EMAIL_AUTO_SUPPRESS_BLOCKS = True       # Automatically add blocked addresses

# === VOLUME LIMITS & WARM-UP ===
# Gradual volume ramping to build sender reputation
EMAIL_WARMUP_DAYS = 14  # 14-day warm-up period
EMAIL_WARMUP_DAILY_LIMITS = [
    50, 100, 200, 400, 800, 1600, 2400,      # Week 1
    3000, 3500, 4000, 4500, 5000, 5000, 5000  # Week 2
]
EMAIL_MAX_DAILY_VOLUME = 5000       # Maximum emails per day after warm-up
EMAIL_MAX_HOURLY_VOLUME = 500       # Maximum emails per hour (spread throughout day)
EMAIL_MIN_SEND_INTERVAL_SECONDS = 0.5  # Minimum delay between individual emails

# === SEND TIMING RESTRICTIONS ===
# Only send during business hours for better engagement
EMAIL_SEND_HOURS_START = 8      # 8 AM local time
EMAIL_SEND_HOURS_END = 18       # 6 PM local time
EMAIL_SEND_DAYS = [0, 1, 2, 3, 4]  # Monday=0 to Friday=4
EMAIL_REQUIRE_SAFE_SEND_TIME = True  # Enforce send time restrictions

# === REPUTATION THRESHOLDS (Circuit Breakers) ===
# Auto-pause campaigns if these rates are exceeded
EMAIL_MAX_BOUNCE_RATE = 0.05        # 5% bounce rate = pause
EMAIL_MAX_COMPLAINT_RATE = 0.001    # 0.1% complaint rate = pause
EMAIL_MAX_HARD_BOUNCE_RATE = 0.02   # 2% hard bounce = flag list quality

# === CONTENT SAFETY ===
# Validation rules for email content
EMAIL_REQUIRE_PLAIN_TEXT = True      # Always include plain-text version
EMAIL_REQUIRE_LIST_UNSUBSCRIBE = True  # RFC 8058 one-click unsubscribe
EMAIL_MAX_LINK_DENSITY = 5           # Maximum links per email
EMAIL_BLOCK_SPAM_TRIGGERS = True     # Warn on spam trigger words

# Spam trigger words to detect in content
SPAM_TRIGGER_WORDS = {
    'urgent', 'act now', 'limited time', 'click here', 'free money',
    'guarantee', 'no obligation', 'winner', 'congratulations',
    'cash bonus', 'prize', 'earn money', 'work from home',
    'click below', 'order now', 'buy now', 'call now',
    'double your', 'extra income', 'risk free'
}

# === LIST QUALITY ===
# Only email recently engaged subscribers
EMAIL_REQUIRE_ENGAGEMENT_WINDOW = APP_CREDENTIALS.get("EMAIL_REQUIRE_ENGAGEMENT_WINDOW", "false").lower() == "true"
EMAIL_ENGAGEMENT_WINDOW_DAYS = 180  # Only email if engaged in last 6 months

# === TESTING & VALIDATION ===
# Seed list for pre-campaign testing
EMAIL_REQUIRE_SEED_TEST = APP_CREDENTIALS.get("EMAIL_REQUIRE_SEED_TEST", "false").lower() == "true"
EMAIL_SEED_LIST = [
    'test@mail-tester.com',  # Spam score testing
]
EMAIL_MIN_SPAM_SCORE = 9.0  # Minimum mail-tester.com score

# === SCHEDULED SENDING ===
# Job queue for spreading emails over time
EMAIL_QUEUE_ENABLED = True
EMAIL_QUEUE_PATH = "email_queue.json"
EMAIL_QUEUE_CHECK_INTERVAL = 300  # Check queue every 5 minutes
SENDING_LIMITS_PATH = "sending_limits.json"  # Track daily/hourly send counts

# === UNSUBSCRIBE CONFIGURATION ===
# One-click unsubscribe implementation
EMAIL_UNSUBSCRIBE_METHOD = "brevo"  # Options: "brevo", "custom"
GOOGLE_FORM_UNSUBSCRIBE_URL_TEMPLATE = "https://docs.google.com/forms/d/e/1FAIpQLSeM9ZMN2UmmVtBTXMD2V1qaJYJjtEGTt64auNfOKJgK-zz3dw/viewform?usp=pp_url&entry.1980793212="  # Legacy, deprecated
