import streamlit as st
import pandas as pd
import os
import shutil
import tempfile
import re
from data_handler import load_contacts_from_excel # Assuming this exists
from email_agent import SmartEmailAgent # Assuming this exists
from email_tool import send_bulk_email_messages, get_email_events
from config import SENDER_EMAIL, OPENAI_API_KEY, BREVO_API_KEY # Assuming these exist
from translations import LANGUAGES, _t, set_language # Assuming these exists
import datetime

# --- CSS Styling ---
st.markdown("""
<style>
body {
    background: linear-gradient(135deg, #f0f4fc, #c8d8f8);
}
.card {
    background: white;
    border-radius: 12px;
    padding: 1rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    margin-bottom: 1rem;
}
/* Ensure Streamlit elements don't create extra unwanted space */
div.stActionButton, div.stDownloadButton, div.stFileUploadDropzone {
    margin-bottom: 0.5rem; /* Adjust as needed */
}

/* Custom button styling for language selection */
.stButton>button {
    width: 100%; /* Make buttons take full column width */
    height: 3em; /* Make buttons a bit taller */
    font-size: 1.1em;
    font-weight: bold;
    border-radius: 8px;
    transition: all 0.2s ease-in-out;
    /* Default for secondary buttons (unselected) */
    border: 1px solid #ccc;
    background-color: white;
    color: #333;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.stButton>button:hover {
    border-color: #2563eb; /* Blue border on hover */
    box-shadow: 0 4px 10px rgba(0,0,0,0.1);
}

/* Styling for the SELECTED language button (primary type) */
.stButton button[kind="primary"] {
    background-color: #2563eb; /* Strong blue background */
    color: white; /* White text */
    border-color: #2563eb; /* Blue border */
    font-weight: bold; /* Make it bolder */
    box-shadow: 0 4px 12px rgba(0,0,0,0.2); /* More prominent shadow */
}

/* Hover effect for the primary (selected) button too */
.stButton button[kind="primary"]:hover {
    background-color: #1a4fbd; /* Slightly darker blue on hover */
    border-color: #1a4fbd;
}

/* Minimal metric-like card styling */
.colored-metric {
    background: white;
    border-radius: 12px;
    padding: 0.75rem 1rem;
    text-align: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    border: 1px solid rgba(0,0,0,0.06);
}
.colored-metric .cm-label {
    font-size: 0.95rem;
    font-weight: 600;
    line-height: 1.2;
    opacity: 0.95;
}
.colored-metric .cm-value {
    font-size: 2rem;
    font-weight: 700;
    line-height: 1.2;
    margin-top: 0.25rem;
}

</style>
""", unsafe_allow_html=True)

# --- Language Selection (moved to main content area) ---
st.markdown("""
<style>
/* — ENGLISH button: use UK flag as background image — */
div.st-key-lang_button_en button {
    padding-left: 28px !important;              /* make room for the icon */
    background-image: url('https://flagcdn.com/16x12/gb.png') !important;
    background-repeat: no-repeat !important;
    background-position: 6px center !important;
}
/* — FRENCH button: use French flag — */
div.st-key-lang_button_fr button {
    padding-left: 28px !important;
    background-image: url('https://flagcdn.com/16x12/fr.png') !important;
    background-repeat: no-repeat !important;
    background-position: 6px center !important;
}
</style>
""", unsafe_allow_html=True)

# --- Page Config ---
st.set_page_config(layout="wide", page_title=_t("AI Email Assistant"))

# --- Session State Initialization ---
def init_state():
    if 'initialized' not in st.session_state:
        st.session_state.language = 'fr'
        st.session_state.page = 'generate'
        st.session_state.contacts = []
        st.session_state.contact_issues = []
        st.session_state.attachments = [] # Stores UploadedFile objects
        st.session_state.email_sending_status = []
        st.session_state.sending_summary = {'total_contacts':0, 'successful':0, 'failed':0}
        st.session_state.detailed_response = None
        st.session_state.generation_in_progress = False
        st.session_state.sending_in_progress = False
        st.session_state.user_prompt = ''
        st.session_state.user_email_context = ''
        st.session_state.personalize_emails = False
        st.session_state.generic_greeting = ''
        st.session_state.template_subject = ''
        st.session_state.template_body = ''
        st.session_state.editable_subject = ''
        st.session_state.editable_body = ''
        st.session_state.uploaded_file_name = None # To track if the file has changed by name
        st.session_state.show_generation_section = False # Control visibility of AI generation form
        st.session_state.email_generated = False # New flag to control display of generated email fields
        st.session_state.message_details = [] # NEW: To store structured message IDs and their events
        st.session_state.initialized = True
        
        ### NEW FEATURE: Donate & Custom Buttons ###
        st.session_state.add_custom_button = False
        st.session_state.custom_button_text = ''
        st.session_state.custom_button_url = ''
        st.session_state.custom_button_color = '#0e2fc2'  # Default blue color like the example
        st.session_state.custom_button_text_before = ''  # NEW: Text before custom button
        ### END NEW FEATURE ###
        
init_state()

# Ensure message_details is initialized at the top level
if "message_details" not in st.session_state:
    st.session_state.message_details = []

# --- Language Selection (moved to main content area) ---
# Apply the selected language immediately after initialization
set_language(st.session_state.language)

# Dictionary to map language codes to display strings
LANGUAGE_BUTTON_LABELS = {
    "en": "EN",
    "fr": "FR",
}

# Use st.columns to place the language selector on the right of a potential title
col_title, col_lang = st.columns([8, 2])

with col_lang:
    # Use columns for language selection buttons
    lang_col1, lang_col2 = st.columns(2)
    
    with lang_col1:
        if st.button(
            LANGUAGE_BUTTON_LABELS["en"],
            key="lang_button_en",
            # Logic: primary (blue) if selected, secondary (white) if not
            type="primary" if st.session_state.language == "en" else "secondary", 
            use_container_width=True
        ):
            st.session_state.language = "en"
            set_language("en")
            st.rerun()
    with lang_col2:
        if st.button(
            LANGUAGE_BUTTON_LABELS["fr"],
            key="lang_button_fr",
            # Logic: primary (blue) if selected, secondary (white) if not
            type="primary" if st.session_state.language == "fr" else "secondary", 
            use_container_width=True
        ):
            st.session_state.language = "fr"
            set_language("fr")
            st.rerun()

with col_title:
    st.title(_t("AI Email Assistant")) # Main application title

# --- UI Helpers ---
def render_step_indicator(current_step: int):
    steps = [
        {"label": _t("Generation & Setup"), "number": 1},
        {"label": _t("Preview & Send"), "number": 2},
        {"label": _t("Results"), "number": 3},
    ]
    step_html = "<div style='display: flex; justify-content: center; align-items: flex-start; gap: 60px; margin-bottom: 2rem;'>"
    for idx, step in enumerate(steps, start=1):
        if idx < current_step:
            # Completed step: green circle with checkmark
            circle = f"<div style='background: #22c55e; color: white; border-radius: 50%; width: 38px; height: 38px; display: flex; align-items: center; justify-content: center; font-size: 1.3rem; font-weight: bold; box-shadow: 0 2px 8px rgba(0,0,0,0.07); border: 2px solid #22c55e;'>✓</div>"
            label_color = "#22c55e"
        elif idx == current_step:
            # Current step: blue circle with number
            circle = f"<div style='background: #2563eb; color: white; border-radius: 50%; width: 38px; height: 38px; display: flex; align-items: center; justify-content: center; font-size: 1.3rem; font-weight: bold; box-shadow: 0 2px 8px rgba(0,0,0,0.07); border: 2px solid #2563eb;'>{step['number']}</div>"
            label_color = "#2563eb"
        else:
            # Upcoming step: gray circle with number
            circle = f"<div style='background: #e5e7eb; color: #9ca3af; border-radius: 50%; width: 38px; height: 38px; display: flex; align-items: center; justify-content: center; font-size: 1.3rem; font-weight: bold; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border: 2px solid #e5e7eb;'>{step['number']}</div>"
            label_color = "#9ca3af"
        step_html += f"<div style='display: flex; flex-direction: column; align-items: center; min-width: 90px;'>"
        step_html += circle
        step_html += f"<div style='margin-top: 0.5rem; font-size: 1rem; color: {label_color}; text-align: center; font-weight: {'bold' if idx == current_step else 'normal'};'>{step['label']}</div>"
        step_html += "</div>"
    step_html += "</div>"
    st.markdown(step_html, unsafe_allow_html=True)

# New helper: colored metric block

def colored_metric(label: str, value, label_color: str, value_color: str) -> None:
    """Render a simple metric-like card with independently colored label and value."""
    safe_label = str(label)
    safe_value = str(value)
    st.markdown(
        f"""
        <div class="colored-metric">
            <div class="cm-label" style="color:{label_color};">{safe_label}</div>
            <div class="cm-value" style="color:{value_color};">{safe_value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# --- Helper function for adding greeting ---
def _add_greeting_to_body(body_content, greeting_text, current_language):
    """
    Prepends a translated greeting to the body content, avoiding duplicates.
    """
    if not greeting_text:
        return body_content # No greeting to add

    # Get the appropriate salutation prefix based on language
    salutation_prefix = _t("Dear") # Default to "Dear"
    if current_language == 'fr':
        salutation_prefix = _t("Bonjour") # Use "Bonjour" for French

    # Check if the greeting_text already starts with a salutation in the current language
    salutations_to_check = {
        'en': ['dear', 'hello', 'hi'],
        'fr': ['cher', 'chère', 'chers', 'chères', 'bonjour', 'salut']
    }
    
    greeting_already_has_salutation = False
    for salutation_word in salutations_to_check.get(current_language, []):
        if greeting_text.lower().startswith(salutation_word):
            greeting_already_has_salutation = True
            break

    if not greeting_already_has_salutation:
        body_prefix = f"{salutation_prefix} {greeting_text},\n\n"
    else:
        body_prefix = f"{greeting_text},\n\n" # Use the greeting as is if it already contains a salutation
    
    return body_prefix + body_content

# --- Helper function to generate professional button HTML ---
def generate_professional_button_html(button_text, button_url, button_color="#e52937"):
    """
    Generate professional button HTML similar to the email marketing example provided.
    Uses the same structure: a -> span -> div pattern with proper styling.
    """
    # REDUCED FONT SIZE AND PADDING
    return f"""
    <a href="{button_url}" style="margin:0px;padding:0px;border:0px;text-align:center;text-decoration:none;display:block;color:rgb(255,255,255);font-family:Arial;font-style:inherit;font-weight:inherit;font-size:9px" target="_blank">
        <span style="margin:0px;padding:2px 5px;border:1px solid {button_color};display:block;background-color:{button_color};border-radius:2px">
            <div style="margin:0px;padding:0px;border:0px;text-align:center;font-size:12px;color:rgb(255,255,255)">
                <span style="margin:0px;padding:0px;border:0px;font-size:12px">{button_text}</span>
            </div>
        </span>
    </a>
    """

# --- Business Logic ---
def generate_email_preview_and_template():
    st.session_state.generation_in_progress = True
    if not OPENAI_API_KEY:
        st.error(_t("OpenAI API Key is not configured. Please set it in Streamlit secrets."))
        st.session_state.generation_in_progress = False
        return

    agent = SmartEmailAgent(openai_api_key=OPENAI_API_KEY)

    generate_nonpersonalized_greeting = not bool(st.session_state.generic_greeting.strip())

    template = agent.generate_email_template(
        prompt=st.session_state.user_prompt,
        user_email_context=st.session_state.user_email_context,
        output_language=st.session_state.language,
        personalize_emails=st.session_state.personalize_emails,
        generate_nonpersonalized_greeting=generate_nonpersonalized_greeting
    )

    st.session_state.template_subject = template['subject']
    st.session_state.template_body = template['body']
    st.session_state.editable_subject = template['subject']
    st.session_state.editable_body = template['body']

    # Apply greeting manually only if not personalizing AND we did NOT ask the agent to add one
    if not st.session_state.personalize_emails and not generate_nonpersonalized_greeting:
        actual_greeting = st.session_state.generic_greeting if st.session_state.generic_greeting else _t("Valued Customer")
        st.session_state.editable_body = _add_greeting_to_body(
            st.session_state.editable_body,
            actual_greeting,
            st.session_state.language
        )
        st.session_state.template_body = st.session_state.editable_body

    st.session_state.generation_in_progress = False
    st.session_state.email_generated = True
    st.session_state.page = 'preview'
    st.rerun()

# NEW: Function to refresh events for a specific message ID
def refresh_message_events(message_id, message_index):
    st.session_state.email_sending_status.append(f"Refreshing events for message ID: {message_id}...")
    try:
        new_events_data = get_email_events([message_id])
        if message_id in new_events_data:
            st.session_state.message_details[message_index]['events'] = new_events_data[message_id]
            st.session_state.email_sending_status.append(f"✅ Events refreshed for {message_id}.")
        else:
            st.session_state.email_sending_status.append(f"⚠️ Could not find events for {message_id}.")
    except Exception as e:
        st.session_state.email_sending_status.append(f"❌ Error refreshing events for {message_id}: {e}")
    st.rerun()


def send_all_emails():
    st.session_state.sending_in_progress = True
    total_contacts = len(st.session_state.contacts)

    # Prepare attachments in a temp dir
    temp_attachment_paths = []
    with tempfile.TemporaryDirectory() as temp_dir:
        for uploaded_file in st.session_state.attachments:
            path = os.path.join(temp_dir, uploaded_file.name)
            with open(path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            temp_attachment_paths.append(path)

        # Build the list of message dicts
        messages = []
        
        ### UPDATED FEATURE: Professional Email Buttons ###
        # We'll build the full button HTML once, before the loop
        full_button_html = "" # Start with an empty string
        
        # Add custom button first, if enabled
        if st.session_state.add_custom_button and st.session_state.custom_button_text and st.session_state.custom_button_url:
            custom_btn_text = st.session_state.custom_button_text
            custom_btn_url = st.session_state.custom_button_url
            custom_btn_color = st.session_state.custom_button_color
            
            # Add text before custom button if exists
            if st.session_state.custom_button_text_before:
                full_button_html += f"""
                    <div style="text-align: center;">
                        <p style="margin: 5px 0; font-size: 14px;">
                            {st.session_state.custom_button_text_before}
                        </p>
                """
            else:
                full_button_html += f"""<div style="text-align: center;">"""
                
            custom_button_html = generate_professional_button_html(custom_btn_text, custom_btn_url, custom_btn_color)
            full_button_html += f"""{custom_button_html}<br>"""
        
        # Add the donation button and its text
        donate_text_above = _t("Je souhaite continuer de participer à équiper et sauver les soldats d'Israel, je fais un don en ligne, déductible à 66% de mon impôt sur le revenu.")
        donate_btn_text = _t("Donate Button Text")
        donate_btn_url = _t("Donate Button URL")
        donate_button_html = generate_professional_button_html(donate_btn_text, donate_btn_url)

        if not st.session_state.add_custom_button:
            # If no custom button, we need to open the div here
            full_button_html += f"""<div style="text-align: center;">"""

        full_button_html += f"""
            <p style="margin: 5px 0; font-size: 14px;">{donate_text_above}</p>
            <br>{donate_button_html}
        """
        
        #full_button_html += "</div>" # Close the centered div
        ### END UPDATED FEATURE ###

        # NEW: Footer HTML with unsubscribe and association info
        footer_html = f"""
            <br><br>
            <div style="text-align: center; font-size: 12px; color: #888888; margin-top: 20px;">
                <p style="margin: 0; padding: 0;">Migdal France / 38 rue servan 75011 Paris / tel: 0749589118 / <a href="http://www.migdal.org" style="color: #888888;">www.migdal.org</a></p>
                <br>
                <p style="margin: 0; padding: 0;"><a href="[UNSUBSCRIBE]" style="color: #888888;">Se désinscrire</a></p>
            </div>
        """
        
        for contact in st.session_state.contacts:
            email = contact.get('email')
            name  = contact.get('name', '')

            if not email:
                continue  # skip missing emails

            # Start from the editable template
            subj = st.session_state.editable_subject
            body = st.session_state.editable_body

            # Personalize if needed
            if st.session_state.personalize_emails:
                for ph in ["{{Name}}", "{{Nom}}"]:
                    subj = subj.replace(ph, name)
                    body = body.replace(ph, name)
                for ph in ["{{Email}}", "{{Courriel}}"]:
                    subj = subj.replace(ph, email)
                    body = body.replace(ph, email)
            else:
                # strip any leftover placeholders
                for ph in ["{{Name}}","{{Nom}}","{{Email}}","{{Courriel}}"]:
                    subj = subj.replace(ph, "")
                    body = body.replace(ph, "")

            # Append the footer and button HTML to the end of the email body
            body_with_buttons = f"{body}<br>{full_button_html}<br>{footer_html}"
            
            messages.append({
                "to_email": email,
                "to_name": name,
                "subject": subj,
                "body": body_with_buttons
            })

        # Send all at once
        result = send_bulk_email_messages(
            sender_email=SENDER_EMAIL,
            sender_name=SENDER_EMAIL.split('@')[0].replace('.', ' ').title(),
            messages=messages,
            attachments=temp_attachment_paths if temp_attachment_paths else None
        )

    # Build status & summary
    status = []
    result_status = result.get("status")
    result_message = result.get("message", "")
    
    if result_status == "success":
        message_ids = result.get("message_ids", [])
        total_sent = result.get("total_sent", len(messages))
        success = total_sent
        fail = total_contacts - success
        
        # Add detailed status information
        status.append(_t("✅ Bulk send completed successfully!"))
        status.append(_t("📧 Total emails sent: ") + str(success))
        status.append(_t("📊 Success rate: ") + f"{success}/{total_contacts} ({(success/total_contacts*100):.1f}%)")
        
        # NEW: Populate st.session_state.message_details with structured data
        st.session_state.message_details = []
        if message_ids:
            # Fetch initial events (if any) for all messages
            email_events_initial = get_email_events(message_ids)
            for i, msg_id in enumerate(message_ids, 1):
                recipient_email = messages[i-1]['to_email'] if i <= len(messages) else f"Recipient {i}"
                st.session_state.message_details.append({
                    'recipient': recipient_email,
                    'message_id': msg_id,
                    'events': email_events_initial.get(msg_id, []) # Store initial events
                })
        
        if fail > 0:
            status.append(f"⚠️ {fail} emails failed to send")
            
    elif result_status == "partial_success":
        # Extract success count from message
        import re
        success_match = re.search(r'(\d+) emails sent successfully', result_message)
        success = int(success_match.group(1)) if success_match else 0
        fail = total_contacts - success
        status.append(f"⚠️ Partial success: {result_message}")
        # For partial success, we might not have message_ids for all,
        # so we'll just log the overall status.
        st.session_state.message_details = [] # Clear any previous details
    else:
        success = 0
        fail = total_contacts
        status.append(f"❌ Bulk send failed: {result_message}")
        st.session_state.message_details = [] # Clear any previous details

    st.session_state.email_sending_status = status
    st.session_state.sending_summary = {
        'total_contacts': total_contacts,
        'successful': success,
        'failed': fail
    }
    # Store detailed response data for the results page
    st.session_state.detailed_response = result
    st.session_state.page = 'results'
    st.session_state.sending_in_progress = False
    st.rerun()

# --- Page: Generate ---
def page_generate():
    st.subheader(_t("1. Generation"))
    render_step_indicator(1)

    # --- Sender Information (Always visible at the top) ---
    st.markdown("---")
    st.markdown(f"**{_t('Sender Email')}:** `{SENDER_EMAIL if SENDER_EMAIL else _t('Not configured')}`")
    if not SENDER_EMAIL or not BREVO_API_KEY:
        st.warning(_t("Sender email credentials are not configured. Please set SENDER_EMAIL and BREVO_API_KEY in Streamlit secrets."))
    st.markdown("---")

    # --- File Upload ---
    uploaded_file = st.file_uploader(
        _t("Upload Excel (.xlsx/.xls)"),
        type=["xlsx","xls"]
    )

    # Process file only if a new file is uploaded (by name or initial upload)
    if uploaded_file is not None and \
       (st.session_state.uploaded_file_name is None or \
        st.session_state.uploaded_file_name != uploaded_file.name):
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
            shutil.copyfileobj(uploaded_file, tmp_file)
            st.session_state.uploaded_file_path = tmp_file.name # Store path for access
        
        st.session_state.uploaded_file_name = uploaded_file.name
        contacts, issues = load_contacts_from_excel(st.session_state.uploaded_file_path)
        st.session_state.contacts = contacts
        st.session_state.contact_issues = issues
        st.session_state.show_generation_section = True # Show the AI generation form
        
        if issues:
            st.warning(_t("WARNING: Some contacts had issues (e.g., missing/invalid/duplicate emails). They will be skipped."))
            for issue in issues:
                st.info(f"  - {issue}")
        
        if contacts:
            st.success(_t("Successfully loaded {count} valid contacts.", count=len(contacts)))
        else:
            st.error(_t("No valid contacts found in the Excel file."))
            st.session_state.show_generation_section = False # Hide generation if no contacts

    # Moved this block to only show if no file has been successfully uploaded yet,
    # preventing duplicate messages.
    if not st.session_state.uploaded_file_name and not st.session_state.contacts:
        st.info(_t("Please upload an Excel file to get started."))

    if st.session_state.show_generation_section:
        st.markdown("---")

        st.markdown(f"**{_t('AI Instruction: Describe the email you want to generate.')}**")
        st.session_state.user_prompt = st.text_area(
            _t("e.g., 'Draft a newsletter about our new product features.'"),
            value=st.session_state.user_prompt,
            height=100,
            key="user_prompt_input"
        )

        st.markdown(f"**{_t('Email Context (optional): Add style, tone, or specific details.')}**")
        st.session_state.user_email_context = st.text_area(
            _t("e.g., 'Friendly tone, include a call to action to visit our website.'"),
            value=st.session_state.user_email_context,
            height=80,
            key="user_email_context_input"
        )

        st.session_state.personalize_emails = st.checkbox(
            _t("Personalize emails?"),
            value=st.session_state.personalize_emails,
            key="personalize_emails_checkbox"
        )
        
        if not st.session_state.personalize_emails:
            st.session_state.generic_greeting = st.text_input(
                _t("Generic Greeting (e.g., 'Dear Valued Customer')"),
                value=st.session_state.generic_greeting,
                placeholder=_t("Enter a generic greeting if not personalizing"),
                key="generic_greeting_input"
            )

        ### UPDATED FEATURE: Enhanced Custom Button Options ###
        st.markdown("---")
        st.markdown(f"**{_t('Email Buttons Configuration')}**")
        
        st.session_state.add_custom_button = st.checkbox(
            _t("Add a Custom Button?"),
            value=st.session_state.add_custom_button,
            key="custom_button_checkbox"
        )
        
        if st.session_state.add_custom_button:
            col1, col2 = st.columns(2)
            with col1:
                st.session_state.custom_button_text = st.text_input(
                    _t("Custom Button Text"),
                    value=st.session_state.custom_button_text,
                    placeholder=_t("e.g., 'Learn More'"),
                    key="custom_button_text_input"
                )
                st.session_state.custom_button_url = st.text_input(
                    _t("Button URL"),
                    value=st.session_state.custom_button_url,
                    placeholder=_t("e.g., 'https://your-website.com'"),
                    key="custom_button_url_input"
                )
                st.session_state.custom_button_text_before = st.text_input(
                    _t("Text Before Button"),
                    value=st.session_state.custom_button_text_before,
                    placeholder=_t("e.g., 'Click the button below to learn more'"),
                    key="custom_button_text_before_input"
                )
            with col2:
                st.session_state.custom_button_color = st.color_picker(
                    _t("Button Color"),
                    value=st.session_state.custom_button_color,
                    key="custom_button_color_input"
                )

        # Color preview
                st.markdown(f"""
                <div style="background-color: {st.session_state.custom_button_color}; 
                           color: white; padding: 8px; border-radius: 5px; 
                           text-align: center; margin-top: 10px;">
                    {_t("Preview Color")}
                </div>
                """, unsafe_allow_html=True)
        ### END UPDATED FEATURE ###

        st.markdown("---")
        if st.button(
            _t("Generate Email"),
            use_container_width=True,
            key="generate_email_button",
            disabled=st.session_state.generation_in_progress,
            type="primary"
        ):
            if st.session_state.user_prompt:
                generate_email_preview_and_template()
            else:
                st.warning(_t("Please provide instructions for the AI to generate the email."))


# --- Page: Preview ---
def page_preview():
    # --- Custom CSS for this page ---
    st.markdown("""
    <style>
        /* Style for the blue instruction text */
        .info-text-blue {
            color: #0d6efd;
            font-size: 1em;
            margin-bottom: 2rem;
        }
        /* Style for the black instruction text */
        .info-text-normal {
             font-size: 1em;
             margin-bottom: 2rem;
        }
        /* Enlarge titles inside boxes */
        h4 {
            font-size: 1.25em;
            font-weight: 600;
        }
    </style>
    """, unsafe_allow_html=True)

    # --- Header: Back Button and Centered Title ---
    header_cols = st.columns([0.25, 0.5, 0.25])
    with header_cols[0]:
        if st.button(f"← {_t('Back to Generation')}", use_container_width=True):
            st.session_state.page = 'generate'
            st.rerun()
    with header_cols[1]:
        st.markdown(f"<h2 style='text-align: center;'>{_t('2. Preview')}</h2>", unsafe_allow_html=True)
    
    # --- Progress Indicator ---
    render_step_indicator(2)
    st.markdown("<br>", unsafe_allow_html=True)

    # --- Section Titles (above the boxes) ---
    title_cols = st.columns(2)
    with title_cols[0]:
        st.markdown(f"<h4>{_t('Editable Email Content')}</h4>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='info-text-blue'>{_t('Edit the email template here. Changes will reflect in the live preview.')}</div>",
            unsafe_allow_html=True
        )
    with title_cols[1]:
        st.markdown(f"<h4>{_t('Live Preview for First Contact')}</h4>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='info-text-normal'>{_t('This shows how the email will appear for the first contact. To make changes, use the *Editable Email Content* section on the left.')}</div>",
            unsafe_allow_html=True
        )

    # --- Main Content Columns (the actual boxes) ---
    col1, col2 = st.columns(2)

    with col1:
        with st.container(border=True):
            st.text_input(_t("Recipient"), value="Recipient <email@example.com>", disabled=True)
            
            st.session_state.editable_subject = st.text_input(
                _t("Subject"),
                value=st.session_state.editable_subject,
                key="preview_subject_input"
            )
            st.session_state.editable_body = st.text_area(
                _t("Body"),
                value=st.session_state.editable_body,
                height=350,
                key="preview_body_input"
            )

    with col2:
        with st.container(border=True):
            
            if st.session_state.contacts:
                first_contact = st.session_state.contacts[0]
                preview_name = first_contact.get('name', '')
                preview_email = first_contact.get('email', '')

                st.text_input(_t("Recipient"), value=f"{preview_name} <{preview_email}>", disabled=True)

                preview_subj = st.session_state.editable_subject
                preview_body = st.session_state.editable_body

                if st.session_state.personalize_emails:
                    for placeholder in ["{{Name}}", "{{Nom}}"]:
                        preview_subj = preview_subj.replace(placeholder, preview_name)
                        preview_body = preview_body.replace(placeholder, preview_name)
                    for placeholder in ["{{Email}}", "{{Courriel}}"]:
                        preview_subj = preview_subj.replace(placeholder, preview_email)
                        preview_body = preview_body.replace(placeholder, preview_email)
                else:
                    for ph in ["{{Name}}","{{Nom}}","{{Email}}","{{Courriel}}"]:
                        preview_subj = preview_subj.replace(ph, "")
                        preview_body = preview_body.replace(ph, "")

                ### UPDATED FEATURE: Professional Button Preview ###
                # We'll build the full button HTML once, before the loop
                full_button_html = "" # Start with an empty string
                
                # Add custom button first, if enabled
                if st.session_state.add_custom_button and st.session_state.custom_button_text and st.session_state.custom_button_url:
                    custom_btn_text = st.session_state.custom_button_text
                    custom_btn_url = st.session_state.custom_button_url
                    custom_btn_color = st.session_state.custom_button_color
                    
                    # Add text before custom button if exists
                    if st.session_state.custom_button_text_before:
                        full_button_html += f"""
                            <div style="text-align: center;">
                                <p style="margin: 5px 0; font-size: 14px;">
                                    {st.session_state.custom_button_text_before}
                                </p>
                        """
                    else:
                        full_button_html += f"""<div style="text-align: center;">"""
                        
                    custom_button_html = generate_professional_button_html(custom_btn_text, custom_btn_url, custom_btn_color)
                    full_button_html += f"""{custom_button_html}<br>"""
                
                # Add the donation button and its text
                donate_text_above = _t("Je souhaite continuer de participer à équiper et sauver les soldats d'Israel, je fais un don en ligne, déductible à 66% de mon impôt sur le revenu.")
                donate_btn_text = _t("Donate Button Text")
                donate_btn_url = _t("Donate Button URL")
                donate_button_html = generate_professional_button_html(donate_btn_text, donate_btn_url)

                if not st.session_state.add_custom_button:
                    # If no custom button, we need to open the div here
                    full_button_html += f"""<div style="text-align: center;">"""
                
                full_button_html += f"""
                    <p style="margin: 5px 0; font-size: 14px;">{donate_text_above}</p>
                    <br>{donate_button_html}
                """
                
                full_button_html += "</div>" # Close the centered div
                
                # NEW: Footer HTML with unsubscribe and association info
                footer_html = f"""
                    <br><br>
                    <div style="text-align: center; font-size: 12px; color: #888888; margin-top: 20px;">
                        <p style="margin: 0; padding: 0;">Migdal France / 38 rue servan 75011 Paris / tel: 0749589118 / <a href="http://www.migdal.org" style="color: #888888;">www.migdal.org</a></p>
                        <br>
                        <p style="margin: 0; padding: 0;"><a href="[UNSUBSCRIBE]" style="color: #888888;">Se désinscrire</a></p>
                    </div>
                """
                
                # Display the preview body normally
                st.text_input(_t("Subject"), value=preview_subj, disabled=True, key="preview_subj_display")
                
                # Display the email body normally
                st.write(preview_body)
                
                # Add a horizontal line separator
                st.markdown("---", unsafe_allow_html=True)
                
                # Display the new combined footer, starting with buttons
                st.markdown(full_button_html, unsafe_allow_html=True)
                
                # Then display the association info and unsubscribe link
                st.markdown(footer_html, unsafe_allow_html=True)
            
            else:
                st.info(_t("Upload contacts in the first step to see a preview."))

    # --- Attachments Section (spans full width) ---
    st.markdown("---")
    st.markdown(f"**{_t('Add Attachments')}**")
    uploaded_attachments = st.file_uploader(
        _t("Upload files"),
        type=None,
        accept_multiple_files=True,
        key="attachment_uploader"
    )
    if uploaded_attachments:
        for uploaded_file in uploaded_attachments:
            if not any(att.name == uploaded_file.name for att in st.session_state.attachments):
                st.session_state.attachments.append(uploaded_file)
        st.info(_t("Attachments selected: {count}", count=len(st.session_state.attachments)))

    if st.session_state.attachments:
        st.markdown(f"**{_t('Current Attachments')}**")
        for i, att in enumerate(st.session_state.attachments):
            col_att_name, col_att_remove = st.columns([0.8, 0.2])
            with col_att_name:
                st.write(f"- {att.name}")
            with col_att_remove:
                if st.button("X", key=f"remove_attachment_{i}"):
                    st.session_state.attachments.pop(i)
                    st.rerun()

    st.markdown("---")
    # --- Final Send Button ---
    if st.button(_t("Confirm Send"), use_container_width=True, key="confirm_send_button", disabled=st.session_state.sending_in_progress, type="primary"):
        if not st.session_state.contacts:
            st.warning(_t("No contacts loaded to send emails to."))
        elif not st.session_state.editable_subject or not st.session_state.editable_body:
            st.warning(_t("Subject and Body cannot be empty. Please go back to Generation if needed."))
        else:
            send_all_emails()

# --- Page: Results ---
def page_results():
    st.subheader(_t("3. Results"))
    render_step_indicator(3)

    summary = st.session_state.sending_summary
    total = summary['total_contacts']
    successful = summary['successful']
    failed = summary['failed']

    st.markdown("---")
    if total > 0 and successful == total:
        st.success(_t("All emails sent successfully!"))
        st.write(_t("All {count} emails were sent without any issues.", count=total))
    elif total > 0:
        st.warning(_t("Sending complete with errors."))
        st.write(_t("Some emails failed to send. Please check the log below for details."))
    else:
        st.info(_t("No emails were processed."))
    st.markdown("---")

    # Colored metrics instead of st.metric
    col1, col2, col3 = st.columns(3)
    with col1:
        colored_metric(
            _t("Total Contacts Processed"),
            f"{total}",
            label_color="#334155",    # slate-700
            value_color="#2563eb",    # blue-600
        )
    with col2:
        colored_metric(
            _t("Emails Sent Successfully"),
            f"{successful}",
            label_color="#166534",    # green-800
            value_color="#22c55e",    # green-500
        )
    with col3:
        colored_metric(
            _t("Emails Failed to Send"),
            f"{failed}",
            label_color="#991b1b",    # red-800
            value_color="#ef4444",    # red-500
        )
    
    st.markdown("---")
    # Drawer: Delivery details (per-message statuses) + logs, opened by default
    with st.expander(_t("Show Activity Log and Errors"), expanded=False):
        # Per-message statuses moved inside the drawer and shown expanded (no per-message expanders)
        if st.session_state.message_details:
            st.subheader(_t("Individual Email Status & Events"))
            for i, msg_detail in enumerate(st.session_state.message_details):
                with st.container(border=True):
                    st.markdown(f"**Recipient:** `{msg_detail['recipient']}`")
                    st.markdown(f"**Message ID:** `{msg_detail['message_id']}`")

                    # Refresh button for this specific message
                    if st.button(_t("Refresh Events for this Email"), key=f"refresh_event_{msg_detail['message_id']}_{i}"):
                        refresh_message_events(msg_detail['message_id'], i)

                    st.markdown("**Events:**")
                    if msg_detail['events']:
                        for event in msg_detail['events']:
                            event_type = event.get('event', 'N/A')
                            event_date = event.get('_date', 'N/A')
                            reason = event.get('reason', 'N/A')
                            st.markdown(f"- **Type:** `{event_type}` | **Date:** `{event_date}` | **Reason:** `{reason}`")
                    else:
                        st.info(_t("No events found yet for this message. Click 'Refresh Events' to check."))
        else:
            st.info(_t("No detailed message status available."))

        st.markdown("---")
        # Activity log lives inside the same drawer; no extra totals here
        st.subheader(_t("Activity Log"))
        log_display_container = st.container()
        if st.session_state.email_sending_status:
            for log_entry in st.session_state.email_sending_status:
                if "❌" in log_entry or "error" in log_entry.lower() or "failed" in log_entry.lower():
                    log_display_container.error(log_entry)
                elif "✅" in log_entry or "success" in log_entry.lower():
                    log_display_container.success(log_entry)
                elif "📋" in log_entry or log_entry.strip().startswith("   "):  # Message ID entries
                    log_display_container.markdown(f"```{log_entry}```")
                elif "⚠️" in log_entry:
                    log_display_container.warning(log_entry)
                else:
                    log_display_container.info(log_entry)

    st.markdown("---")
    if st.button(_t("Start New Email Session"), use_container_width=True, key="start_new_session_button", type="primary"):
        # Clear all relevant session state variables
        keys_to_clear = [
            'initialized', 'language', 'page', 'contacts', 'contact_issues', 
            'attachments', 'email_sending_status', 'sending_summary', 'detailed_response',
            'generation_in_progress', 'sending_in_progress', 'user_prompt', 
            'user_email_context', 'personalize_emails', 'generic_greeting', 
            'template_subject', 'template_body', 'editable_subject', 'editable_body',
            'uploaded_file_name', 'show_generation_section', 'email_generated',
            'message_details' # NEW: Clear message_details
        ]
        for k in keys_to_clear:
            if k in st.session_state:
                del st.session_state[k]
        init_state() # Re-initialize to default states
        st.rerun() # Force a rerun to restart the app


# --- Main Navigation ---
if st.session_state.page == 'generate':
    page_generate()
elif st.session_state.page == 'preview':
    page_preview()
elif st.session_state.page == 'results':
    page_results()