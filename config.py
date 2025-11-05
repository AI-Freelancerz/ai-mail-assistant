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
