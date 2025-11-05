# AI Mail Assistant

Smart Email Messenger is an AI-powered tool that helps you create, personalize, and send professional emails at scale — fast, friendly, and effortlessly.

## Features

### 📧 Email Campaign Management
- **AI-Powered Generation**: Create professional email content using OpenAI
- **Bulk Sending**: Send to multiple recipients with Brevo (Sendinblue)
- **Personalization**: Dynamic placeholders for personalized content
- **Attachments**: Support for file attachments
- **Custom Buttons**: Add custom CTA buttons with configurable colors
- **Multi-language Support**: English and French translations
- **Email Validation**: Enhanced 7-point validation system
- **Duplicate Detection**: Automatically removes duplicate email addresses
- **Automatic Retry Logic**: Recovers from temporary API failures automatically

### 📊 Email Status Dashboard
A real-time monitoring page that displays the latest sent email activity from Brevo:

- **Live Data Fetching**: Stateless pulls from Brevo API on each refresh
- **Summary Metrics**: View delivery rates, open rates, and click rates
- **Batch Grouping**: Groups emails by send batch for easier tracking
- **Event Details**: Expandable rows with full event information per recipient
- **CSV Export**: Download detailed reports of email activity
- **Pagination**: Navigate through large result sets
- **Color-Coded Status**: Visual indicators for different delivery states

## Installation

1. Clone the repository:
```bash
git clone https://github.com/AI-Freelancerz/ai-mail-assistant.git
cd ai-mail-assistant
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure secrets in `.streamlit/secrets.toml`:
```toml
# Brevo (Sendinblue) Configuration
BREVO_API_KEY = "your-brevo-api-key"
SENDER_EMAIL = "your-sender@example.com"

# OpenAI Configuration
OPENAI_API_KEY = "your-openai-api-key"

# Application Mode (optional)
AI_MESSENGER_MODE = "email"  # or "sms"

# Optional: Email sending tuning (defaults work well!)
EMAIL_MAX_RETRIES = 3
EMAIL_DEFAULT_CHUNK_SIZE = 500
EMAIL_CHUNK_DELAY = 1.0
```

## Usage

### Running the Application

```bash
streamlit run streamlit_app.py
```

The application will start on `http://localhost:8501`

### Main Email Campaign Flow

1. **Generation & Setup**
   - Upload Excel file with contacts (columns: name, email)
   - Provide AI instructions for email generation
   - Optional: Add context, enable personalization, configure custom buttons
   - Generate email template

2. **Preview & Send**
   - Review and edit the generated email
   - See live preview for first contact
   - Add attachments if needed
   - Confirm and send

3. **Results**
   - View sending summary (success/failed counts)
   - Check individual email statuses
   - Review activity log and errors
   - Refresh event status for specific emails

### Email Status Dashboard

Access the dashboard via the sidebar navigation: **Email Status Dashboard**

**Key Features:**
- **Summary Metrics**: View totals for recipients, delivery, opens, clicks, and bounces with percentage rates
- **Detailed View**: See emails grouped by batch with expandable details for individual recipients
- **Download Report**: Export email status data to CSV with full event details
- **Refresh Button**: Manually refresh data from Brevo API

## Project Structure

```
ai-mail-assistant/
├── streamlit_app.py              # Main application entry point
├── email_status_page.py          # Email status dashboard page
├── brevo_status_client.py        # Brevo API client wrapper
├── email_tool.py                 # Email sending utilities
├── email_agent.py                # AI email generation agent
├── data_handler.py               # Excel contact processing
├── translations.py               # Multi-language support
├── config.py                     # Configuration management
├── requirements.txt              # Python dependencies
└── .streamlit/
    └── secrets.toml              # Secret configuration (not in repo)
```

## API Integration

### Brevo (Sendinblue) API

The application uses Brevo's transactional email API for:
- Sending individual and bulk emails
- Fetching email event reports (delivered, opened, clicked, etc.)
- Retrieving detailed email content

**Rate Limiting**: The client includes automatic retry with exponential backoff for rate-limited requests (429 errors).

### OpenAI API

Used for AI-powered email content generation with customizable:
- Tone and style
- Personalization options
- Language selection

## Configuration Presets

### Balanced (Default)
Already configured - no changes needed!

### Fast Mode (Newsletters)
```toml
EMAIL_DEFAULT_CHUNK_SIZE = 1000
EMAIL_CHUNK_DELAY = 0.5
```

### Maximum Reliability (Critical)
```toml
EMAIL_DEFAULT_CHUNK_SIZE = 100
EMAIL_CHUNK_DELAY = 2.0
EMAIL_MAX_RETRIES = 5
```

## Development

### Adding New Translations

Edit `translations.py` and add entries to both `"en"` and `"fr"` dictionaries:

```python
TRANSLATIONS = {
    "en": {
        "Your Key": "Your English Text",
        # ...
    },
    "fr": {
        "Your Key": "Votre Texte Français",
        # ...
    }
}
```

Use in code: `_t("Your Key")`

### Event Types

Supported Brevo event types:
- `request`: Email request received
- `delivered`: Successfully delivered
- `opened`: Recipient opened email
- `clicks`: Recipient clicked link
- `hardBounces`: Permanent delivery failure
- `softBounces`: Temporary delivery failure
- `blocked`: Email blocked
- `spam`: Marked as spam
- `deferred`: Temporarily deferred
- `unsubscribed`: Recipient unsubscribed
- `error`: General error

## Troubleshooting

### Email Status Dashboard Issues

**Problem**: "Brevo API key not found in secrets"
- **Solution**: Ensure `.streamlit/secrets.toml` contains `BREVO_API_KEY = "..."`

**Problem**: No events showing up
- **Solution**: 
  - Check that emails have been sent through Brevo
  - The dashboard shows events from the last 7 days by default
  - Verify API key has read permissions

**Problem**: Rate limit errors (429)
- **Solution**: The client automatically retries with backoff. If persistent, reduce the frequency of refresh operations.

### General Issues

**Problem**: Import errors for `brevo_python`
- **Solution**: Run `pip install brevo-python` or `pip install -r requirements.txt`

## Monitoring

- **Application logs**: Console output with `[EMAIL_TOOL]` prefix
- **Failed emails**: `logs/failed_emails.log`
- **Progress tracking**: Real-time updates in UI

## Requirements

- Python 3.8+
- Streamlit
- OpenAI API key
- Brevo (formerly Sendinblue) API key

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is part of AI-Freelancerz organization.

## Support

For issues and questions:
- Create an issue on GitHub
- Contact: AI-Freelancerz organization
