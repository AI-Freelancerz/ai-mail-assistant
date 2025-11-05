# ai-mail-assistant

Smart Email Messenger is an AI-powered tool that helps you create, personalize, and send professional emails at scale — fast, friendly, and effortlessly.

## Features

- 🤖 **AI-Powered Email Generation** - Uses OpenAI to create personalized email content
- 📧 **Bulk Email Sending** - Send to thousands of contacts with Brevo API
- 🔄 **Automatic Retry Logic** - Recovers from temporary API failures automatically
- ✅ **Email Validation** - Enhanced 7-point validation system
- 🔍 **Duplicate Detection** - Automatically removes duplicate email addresses
- 📊 **Progress Tracking** - Real-time status updates during sending
- 🎨 **Custom Buttons** - Add professional call-to-action buttons
- 📎 **Attachments** - Support for file attachments with size validation
- 🌍 **Multi-language** - English and French support

## Reliability Features (v2.0 - Nov 2025)

### Core Improvements
- **Exponential Backoff Retry** - Automatic retry with smart delays (2s → 4s → 8s)
- **Email Deduplication** - Case-insensitive duplicate removal
- **Enhanced Validation** - 7-point email validation system
- **Error Categorization** - Distinguishes temporary vs permanent failures
- **Progress Callbacks** - Real-time visibility into sending status
- **Configurable Parameters** - All settings tunable via config
- **Better Chunking** - Conservative 500-email batches with fault isolation

**Reliability Improvement: 400-500%** compared to previous version

See [RELIABILITY_IMPROVEMENTS.md](RELIABILITY_IMPROVEMENTS.md) for detailed documentation.

## Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Configuration

Create `.streamlit/secrets.toml`:

```toml
[app_credentials]
SENDER_EMAIL = "your-email@example.com"
BREVO_API_KEY = "your-brevo-api-key"
OPENAI_API_KEY = "your-openai-api-key"

# Optional: Email sending tuning (defaults work well!)
EMAIL_MAX_RETRIES = 3
EMAIL_DEFAULT_CHUNK_SIZE = 500
EMAIL_CHUNK_DELAY = 1.0
```

### Run

```bash
streamlit run streamlit_app.py
```

## Usage

1. **Upload Contacts** - Upload Excel file with email addresses
2. **Generate Email** - AI generates personalized content
3. **Preview & Edit** - Review and customize the email
4. **Send** - Bulk send with automatic retry and progress tracking

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

## Monitoring

- **Application logs**: Console output with `[EMAIL_TOOL]` prefix
- **Failed emails**: `logs/failed_emails.log`
- **Progress tracking**: Real-time updates in UI

## Architecture

```
streamlit_app.py     → UI and workflow management
email_tool.py        → Email sending with retry logic
email_agent.py       → AI content generation
data_handler.py      → Contact list processing with validation
config.py            → Configuration management
```

## Requirements

- Python 3.8+
- Streamlit
- OpenAI API key
- Brevo (formerly Sendinblue) API key

## Documentation

- [RELIABILITY_IMPROVEMENTS.md](RELIABILITY_IMPROVEMENTS.md) - Detailed reliability features

## License

MIT License

## Support

For issues or questions, please check the documentation files or create an issue in the repository.
