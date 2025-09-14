# CHANGELOG
# - v0.2 (2025-09-01): Add AI_MESSENGER_MODE env gate ("email" default; "sms" enables SMS-only UI).
# - v0.1: Consolidated secrets access and log path.

# config.py - Consolidated Secrets Access and Log Path

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
