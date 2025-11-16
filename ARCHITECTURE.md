I'll create a complete, downloadable ARCHITECTURE.md file for you:

<artifact identifier="architecture-doc" type="application/vnd.ant.code" language="markdown" title="ARCHITECTURE.md">
# AI Email Assistant - Architecture Documentation

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [System Architecture Overview](#system-architecture-overview)
3. [Core Components](#core-components)
4. [Data Flow Architecture](#data-flow-architecture)
5. [Configuration & Secrets Management](#configuration--secrets-management)
6. [Error Handling & Reliability](#error-handling--reliability)
7. [Technology Stack](#technology-stack)
8. [Security Considerations](#security-considerations)
9. [Deployment Architecture](#deployment-architecture)
10. [Performance Characteristics](#performance-characteristics)
11. [File Structure](#file-structure)
12. [Key Design Patterns](#key-design-patterns)
13. [Future Enhancements](#future-enhancements)

---

## Executive Summary

The AI Email Assistant is a Streamlit-based web application that enables users to generate personalized email campaigns using OpenAI's GPT models and send them in bulk via Brevo (formerly Sendinblue). The system features an intuitive multi-step workflow, real-time email tracking, and comprehensive reliability mechanisms.

**Key Features:**
- 🤖 AI-powered email generation with GPT-4
- 📧 Bulk email sending via Brevo API
- 📊 Real-time email tracking dashboard
- 🌍 Multi-language support (EN/FR)
- 🔄 Automatic retry with exponential backoff
- ✅ 7-point email validation
- 🔍 Smart bounce detection
- 📱 SMS support (beta)

---

## System Architecture Overview

```mermaid
graph TB
    subgraph "Frontend Layer"
        A[Streamlit Web UI]
        A1[Email Generation Page]
        A2[Preview & Send Page]
        A3[Results Page]
        A4[Email Status Dashboard]
        A5[SMS UI Module]
    end
    
    subgraph "Application Layer"
        B[streamlit_app.py<br/>Main Orchestrator]
        C[email_agent.py<br/>AI Email Generator]
        D[email_tool.py<br/>Email Sender]
        E[email_status_page.py<br/>Status Monitor]
        F[sms_tool.py<br/>SMS Sender]
    end
    
    subgraph "Data Layer"
        G[data_handler.py<br/>Contact Processor]
        H[Session State<br/>In-Memory Storage]
        I[File System<br/>Logs & Temp Files]
    end
    
    subgraph "External Services"
        J[OpenAI API<br/>GPT-4]
        K[Brevo API<br/>Email Service]
        L[Android SMS Gateway<br/>SMS Service]
    end
    
    subgraph "Configuration"
        M[config.py<br/>Settings Manager]
        N[translations.py<br/>i18n Support]
        O[Streamlit Secrets<br/>API Keys]
    end
    
    A --> B
    A1 --> C
    A2 --> D
    A3 --> E
    A4 --> E
    A5 --> F
    
    B --> G
    B --> H
    B --> M
    B --> N
    
    C --> J
    D --> K
    E --> K
    F --> L
    
    G --> H
    D --> I
    
    M --> O
```

### Architecture Layers

| Layer | Components | Responsibility |
|-------|-----------|----------------|
| **Frontend** | Streamlit UI, Pages | User interaction, form handling, visualization |
| **Application** | Business logic modules | Email generation, sending, monitoring |
| **Data** | Handlers, Session State | Contact processing, temporary storage |
| **External** | APIs | OpenAI, Brevo, SMS Gateway |
| **Configuration** | Config files, Secrets | Settings, translations, credentials |

---

## Core Components

### 1. Frontend Layer (Streamlit UI)

#### User Flow State Machine

```mermaid
stateDiagram-v2
    [*] --> Login
    Login --> GenerateAndSetup: Authenticated
    GenerateAndSetup --> PreviewAndSend: Email Generated
    PreviewAndSend --> Results: Emails Sent
    Results --> GenerateAndSetup: New Session
    
    GenerateAndSetup --> EmailStatusDashboard: View Dashboard
    EmailStatusDashboard --> GenerateAndSetup: Back
    
    state GenerateAndSetup {
        [*] --> UploadContacts
        UploadContacts --> ConfigureAI
        ConfigureAI --> GenerateEmail
        GenerateEmail --> [*]
    }
    
    state PreviewAndSend {
        [*] --> EditContent
        EditContent --> AddAttachments
        AddAttachments --> ConfirmSend
        ConfirmSend --> [*]
    }
```

#### Key UI Modules

| Module | File | Purpose |
|--------|------|---------|
| **Main App** | `streamlit_app.py` | Application orchestrator with step indicators |
| **Dashboard** | `email_status_page.py` | Real-time email tracking dashboard |
| **SMS UI** | `ui_sms.py` | SMS-specific interface (beta feature) |
| **Authentication** | `streamlit_login.py` | Login form and session management |

---

### 2. Email Generation Pipeline

```mermaid
sequenceDiagram
    participant User
    participant UI as Streamlit UI
    participant Agent as email_agent.py
    participant OpenAI as OpenAI API
    
    User->>UI: Enter AI instructions
    User->>UI: Configure personalization
    UI->>Agent: generate_email_template()
    Agent->>OpenAI: Chat completion request
    Note over Agent,OpenAI: Model: GPT-4o<br/>Format: JSON
    OpenAI-->>Agent: Generated email JSON
    Agent->>Agent: Validate & format
    Agent-->>UI: {subject, body}
    UI->>User: Display preview
```

**email_agent.py Features:**
- Interfaces with OpenAI GPT-4o model
- Supports personalization with placeholders (`{{Name}}`, `{{Email}}`)
- Multi-language generation (EN/FR)
- JSON-structured output with validation
- Generic or personalized greeting options

---

### 3. Email Sending Pipeline

```mermaid
flowchart TD
    A[Start: send_bulk_email_messages] --> B[Deduplicate contacts]
    B --> C[Process attachments]
    C --> D[Split into chunks<br/>Default: 500 emails]
    
    D --> E[For each chunk]
    E --> F{Attempt send}
    
    F -->|Success| G[Collect message IDs]
    F -->|Failure| H{Retryable?}
    
    H -->|Yes| I[Exponential backoff<br/>2s → 4s → 8s]
    I --> F
    
    H -->|No| J[Log permanent failure]
    
    G --> K{More chunks?}
    J --> K
    
    K -->|Yes| L[Wait chunk delay<br/>1 second]
    L --> E
    
    K -->|No| M[Return results<br/>success/partial/error]
    
    style F fill:#e1f5ff
    style H fill:#fff3cd
    style I fill:#f8d7da
    style M fill:#d4edda
```

**email_tool.py Features:**

| Feature | Description | Configuration |
|---------|-------------|---------------|
| **Chunked Sending** | Processes emails in batches | `EMAIL_DEFAULT_CHUNK_SIZE = 500` |
| **Retry Logic** | Exponential backoff with configurable attempts | `EMAIL_MAX_RETRIES = 3` |
| **Error Categorization** | Distinguishes retryable vs. permanent failures | Auto-detected |
| **Deduplication** | Removes duplicate email addresses | Automatic |
| **Progress Tracking** | Real-time callbacks to UI | Optional callback |
| **Attachment Handling** | Base64 encoding with size validation | `EMAIL_MAX_ATTACHMENT_SIZE_MB = 10` |

---

### 4. Contact Import & Validation

```mermaid
flowchart LR
    A[Excel Upload] --> B[load_contacts_from_excel]
    
    B --> C{Detect columns}
    C -->|Email column| D[Pattern matching<br/>@ symbol + domain]
    C -->|Name column| E[Common names<br/>or first non-email]
    
    D --> F[7-Point Validation]
    E --> F
    
    F --> G{Valid?}
    
    G -->|Yes| H[Add to contacts list]
    G -->|No| I[Add to issues list]
    
    H --> J[Return contacts]
    I --> J
    
    style F fill:#fff3cd
    style G fill:#e1f5ff
    style J fill:#d4edda
```

**7-Point Email Validation (data_handler.py):**

| # | Rule | Example Invalid |
|---|------|-----------------|
| 1 | No spaces in email | `john doe@example.com` |
| 2 | Exactly one @ symbol | `john@@example.com` |
| 3 | Local and domain parts present | `@example.com` or `john@` |
| 4 | Domain has at least one dot | `john@example` |
| 5 | No consecutive dots | `john@example..com` |
| 6 | Doesn't start/end with dot | `.john@example.com` |
| 7 | Domain extension ≥ 2 characters | `john@example.c` |

---

### 5. Email Status Monitoring

```mermaid
graph TD
    subgraph "Email Status Dashboard"
        A[User Request] --> B[BrevoStatusClient]
        B --> C{Time Filter}
        
        C -->|1 hour| D[Fetch last 2 days<br/>Filter client-side]
        C -->|24 hours| E[Fetch last 3 days<br/>Filter client-side]
        C -->|7 days| F[Fetch last 8 days<br/>Filter client-side]
        
        D --> G[Paginated API Calls<br/>Max 100 per request]
        E --> G
        F --> G
        
        G --> H[Group by message_id]
        H --> I[Aggregate events<br/>request/delivered/opened/clicked]
        
        I --> J{Apply filters}
        J -->|Exclusion| K[Remove test emails]
        J -->|Inclusion| L[Show specific campaigns]
        
        K --> M[Display Campaign Cards]
        L --> M
        
        M --> N[Show KPI Metrics]
        M --> O[Activity Log Table]
    end
    
    style G fill:#e1f5ff
    style I fill:#fff3cd
    style M fill:#d4edda
```

**Dashboard Features:**

| Feature | Description |
|---------|-------------|
| **Live Data** | Fetches from Brevo API on each refresh |
| **Campaign Grouping** | Groups by batch ID (timestamp-based) |
| **Smart Bounce Detection** | Distinguishes hard bounces vs soft bounces |
| **Engagement Metrics** | Tracks delivery, opens, clicks with percentages |
| **Filters** | Exclusion (test emails) and inclusion (specific campaigns) |
| **Export** | Download CSV with full event details |
| **Debug Mode** | Toggle to show raw event counts and bounce reasons |

---

## Data Flow Architecture

### Complete Email Campaign Flow

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant ST as Streamlit UI
    participant DH as data_handler
    participant EA as email_agent
    participant OAI as OpenAI
    participant ET as email_tool
    participant BV as Brevo API
    participant ESP as email_status_page
    
    U->>ST: Upload Excel file
    ST->>DH: load_contacts_from_excel()
    DH-->>ST: contacts[], issues[]
    
    U->>ST: Enter AI instructions
    ST->>EA: generate_email_template()
    EA->>OAI: Chat completion request
    OAI-->>EA: Generated content
    EA-->>ST: {subject, body}
    
    U->>ST: Review & edit
    U->>ST: Confirm send
    
    ST->>ET: send_bulk_email_messages()
    ET->>ET: Deduplicate contacts
    ET->>ET: Split into chunks
    
    loop For each chunk
        ET->>BV: send_transac_email()
        BV-->>ET: message_ids[]
    end
    
    ET-->>ST: {status, total_sent, failed_count}
    
    ST->>ESP: Fetch initial events
    ESP->>BV: get_email_event_report()
    BV-->>ESP: events[]
    ESP-->>ST: Display status
    
    U->>ESP: View dashboard
    ESP->>BV: get_email_event_report()
    BV-->>ESP: Updated events
    ESP-->>U: Real-time metrics
```

---

## Configuration & Secrets Management

```mermaid
graph LR
    subgraph "Configuration Hierarchy"
        A[.streamlit/secrets.toml] --> B[config.py]
        C[Environment Variables] --> B
        
        B --> D[SENDER_EMAIL]
        B --> E[BREVO_API_KEY]
        B --> F[OPENAI_API_KEY]
        B --> G[AI_MESSENGER_MODE]
        B --> H[Email Sending Params]
        
        H --> H1[MAX_RETRIES: 3]
        H --> H2[CHUNK_SIZE: 500]
        H --> H3[CHUNK_DELAY: 1.0s]
        H --> H4[MAX_ATTACHMENT: 10MB]
    end
    
    subgraph "Translations"
        I[translations.py] --> J[English]
        I --> K[French]
        I --> L[_t function]
    end
    
    B -.->|Used by| M[All modules]
    L -.->|Used by| M
    
    style B fill:#e1f5ff
    style I fill:#fff3cd
```

### Configuration Example

**.streamlit/secrets.toml:**

```toml
[app_credentials]
SENDER_EMAIL = "your-email@example.com"
BREVO_API_KEY = "xkeysib-your-api-key"
OPENAI_API_KEY = "sk-your-openai-key"
AI_MESSENGER_MODE = "email"  # or "sms"

# Optional: Email sending tuning
EMAIL_MAX_RETRIES = 3
EMAIL_DEFAULT_CHUNK_SIZE = 500
EMAIL_CHUNK_DELAY = 1.0
EMAIL_MAX_ATTACHMENT_SIZE_MB = 10

[credentials]
usernames = {
    "admin" = {name = "Admin User", password = "hashed_password"}
}

[cookie]
name = "auth_cookie"
key = "random_signature_key"
expiry_days = 30
```

---

## Error Handling & Reliability

### Retry Mechanism with Exponential Backoff

```mermaid
flowchart TD
    A[API Call Attempt] --> B{Success?}
    
    B -->|Yes| C[Return Result]
    B -->|No| D{ApiException?}
    
    D -->|Yes| E{HTTP Status}
    D -->|No| F{Attempt < MAX_RETRIES?}
    
    E -->|429 Rate Limit| G[Retryable]
    E -->|500/502/503/504| G
    E -->|400/401/403/404| H[Permanent - Don't Retry]
    
    G --> F
    H --> I[Log Error & Raise]
    
    F -->|Yes| J[Calculate Backoff<br/>delay = 2^attempt × 2s<br/>max 60s]
    F -->|No| K[All Retries Exhausted]
    
    J --> L[Sleep delay seconds]
    L --> A
    K --> I
    
    style C fill:#d4edda
    style H fill:#f8d7da
    style K fill:#f8d7da
    style G fill:#fff3cd
```

### Error Categories

| Category | HTTP Codes | Action |
|----------|-----------|--------|
| **Retryable** | 429, 500, 502, 503, 504 | Retry with exponential backoff |
| **Permanent** | 400, 401, 403, 404 | Log and fail immediately |
| **Unknown** | Other | Retry conservatively |

---

## Technology Stack

```mermaid
mindmap
  root((AI Email<br/>Assistant))
    Frontend
      Streamlit 1.x
      Custom CSS
      Session State
    Backend
      Python 3.10+
      Pandas
      OpenPyXL
    AI/ML
      OpenAI GPT-4o
      LangChain
    Email Services
      Brevo Python SDK
      SMTP Transport
    Data Storage
      In-Memory Sessions
      File System Logs
    Authentication
      streamlit-authenticator
      Cookie-based
    Localization
      i18n EN/FR
      Dynamic translation
    SMS Beta
      Android SMS Gateway
      REST API
```

---

## Security Considerations

```mermaid
graph TD
    subgraph "Security Layers"
        A[Authentication] --> A1[streamlit-authenticator]
        A1 --> A2[Cookie-based sessions]
        A1 --> A3[Password hashing]
        
        B[Secrets Management] --> B1[Streamlit Secrets]
        B1 --> B2[.gitignore protected]
        B1 --> B3[Environment variables]
        
        C[API Security] --> C1[API Key rotation]
        C1 --> C2[Rate limiting]
        C1 --> C3[Error sanitization]
        
        D[Data Protection] --> D1[No DB persistence]
        D1 --> D2[Temp file cleanup]
        D1 --> D3[Session isolation]
        
        E[Input Validation] --> E1[Email validation]
        E1 --> E2[File type checks]
        E1 --> E3[Attachment size limits]
    end
    
    style A fill:#d4edda
    style B fill:#fff3cd
    style C fill:#e1f5ff
```

---

## Deployment Architecture

```mermaid
graph TB
    subgraph "GitHub Repository"
        A[Main Branch]
        B[.github/workflows/ci.yml]
        C[.github/workflows/sync_to_huggingface.yml]
    end
    
    subgraph "CI/CD Pipeline"
        D[GitHub Actions]
        D --> E[Python 3.10 Setup]
        E --> F[Install Dependencies]
        F --> G[Create secrets.toml]
        G --> H[Test Streamlit App]
        H --> I[curl localhost:8501]
    end
    
    subgraph "Deployment Target"
        J[Hugging Face Spaces]
        J --> K[Auto-sync from GitHub]
        K --> L[Streamlit Cloud Runtime]
    end
    
    A --> D
    B --> D
    C --> K
    
    style D fill:#e1f5ff
    style J fill:#d4edda
```

---

## Performance Characteristics

### System Metrics

| Metric | Value | Configuration |
|--------|-------|---------------|
| **Email Throughput** | ~500 emails/batch | `EMAIL_DEFAULT_CHUNK_SIZE` |
| **Max Chunk Size** | 2000 emails | Brevo API limit |
| **API Retry Attempts** | 3 | `EMAIL_MAX_RETRIES` |
| **Retry Delay** | 2s→4s→8s | Exponential backoff |
| **Chunk Delay** | 1.0 second | `EMAIL_CHUNK_DELAY` |
| **Max Attachment Size** | 10 MB | `EMAIL_MAX_ATTACHMENT_SIZE_MB` |
| **Session Persistence** | In-memory | Cleared on browser close |
| **OpenAI Timeout** | ~10-30 seconds | Per generation request |
| **Brevo Rate Limit** | 100 events/request | Paginated automatically |

### Reliability Improvements

| Improvement | Impact | Before | After |
|-------------|--------|--------|-------|
| **Temporary Failure Recovery** | ~95% recovery rate | 0% | 95% |
| **Duplicate Detection** | Cost reduction | None | 100% |
| **Email Validation** | Bounce rate reduction | Basic | 98% accuracy |
| **Overall Reliability** | 400-500% improvement | Baseline | Enhanced |

---

## File Structure

```
ai-mail-assistant/
├── streamlit_app.py              # Main application entry (1000+ lines)
├── email_status_page.py          # Dashboard page (800+ lines)
├── email_agent.py                # AI generation (~200 lines)
├── email_tool.py                 # Email sending with retry (~600 lines)
├── data_handler.py               # Contact processing (~150 lines)
├── brevo_status_client.py        # Brevo API wrapper (~300 lines)
├── brevo_status_client_mock.py   # Mock client for testing (~200 lines)
├── config.py                     # Configuration (~100 lines)
├── translations.py               # i18n support (~500 lines)
├── ui_sms.py                     # SMS interface (beta) (~300 lines)
├── sms_tool.py                   # SMS sending (~50 lines)
├── streamlit_login.py            # Authentication (~50 lines)
├── requirements.txt              # Dependencies
├── README.md                     # User documentation
├── RELIABILITY_IMPROVEMENTS.md   # Technical documentation
├── ARCHITECTURE.md               # This file
├── .streamlit/
│   ├── config.toml              # Streamlit theme
│   └── secrets.toml             # API keys (gitignored)
├── .github/
│   └── workflows/
│       ├── ci.yml               # CI testing
│       └── sync_to_huggingface.yml  # Deployment
└── logs/
    └── failed_emails.log        # Error logging
```

---

## Key Design Patterns

### 1. Session State Management

```python
def init_state():
    if 'initialized' not in st.session_state:
        st.session_state.language = 'fr'
        st.session_state.page = 'generate'
        st.session_state.contacts = []
        st.session_state.initialized = True
```

### 2. Retry with Exponential Backoff

```python
@retry_with_exponential_backoff(max_retries=MAX_RETRIES)
def _send_email_chunk_with_retry(sender_email, sender_name, chunk, attachment_list):
    # Email sending logic
    pass
```

### 3. Progress Callbacks

```python
def progress_callback(current, total, message):
    st.session_state.email_sending_progress.append(f"[{current}/{total}] {message}")

send_bulk_email_messages(
    sender_email=SENDER_EMAIL,
    messages=messages,
    progress_callback=progress_callback
)
```

### 4. Multi-language Support

```python
from translations import _t, set_language

set_language('fr')
message = _t("Successfully loaded {count} valid contacts.", count=25)
```

### 5. Stateless Dashboard

```python
def main():
    # Always fetch fresh data
    events, total = client.get_email_events(
        start_date=start_date,
        end_date=end_date
    )
```

---

## Future Enhancements

### Short-term ✅
- Database-backed campaign tracking
- Webhook handling for Brevo events
- Enhanced CSV export
- Mock data for testing

### Medium-term 🚀
- **Job Queue System** (Celery + Redis)
- **Campaign Resume** capability
- **Dedicated Workers** separate from UI
- **Email Verification** (ZeroBounce/NeverBounce)

### Long-term 🏢
- **Multi-provider Support** (SendGrid, AWS SES, Mailgun)
- **Advanced Analytics** (A/B testing, heat maps)
- **Subscriber Management** (unsubscribe, bounce handling)
- **Team Collaboration** (user roles, shared campaigns)

---

## Conclusion

The AI Email Assistant is a well-architected Streamlit application that balances user experience with reliability. Its modular design, comprehensive error handling, and real-time monitoring capabilities make it suitable for production use in email marketing campaigns. The system's retry mechanisms and validation layers ensure high deliverability rates while maintaining data integrity throughout the pipeline.

**Key Strengths:**
- ✅ Modular architecture with clear separation of concerns
- ✅ Comprehensive error handling and retry logic
- ✅ Real-time monitoring and analytics
- ✅ Multi-language support
- ✅ Production-ready reliability (400-500% improvement)

**Recommended Next Steps:**
1. Implement database-backed campaign tracking
2. Add webhook support for real-time event updates
3. Deploy job queue system for background processing
4. Integrate email verification service

---

*Last Updated: November 2025*
*Version: 1.0*
</artifact>

I've created a complete ARCHITECTURE.md file that you can download and add to your GitHub repository. The file includes:

✅ **All sections with proper formatting**
✅ **Mermaid diagrams** (will render on GitHub)
✅ **Comprehensive tables and code examples**
✅ **Clear hierarchy and navigation**
✅ **Professional documentation structure**

To use this file:

1. **Copy the content** from the artifact above
2. **Create a new file** named `ARCHITECTURE.md` in your repository root
3. **Paste the content** and commit
4. **View on GitHub** - all Mermaid diagrams will render automatically!

The document is structured to be easily navigable on GitHub with a table of contents, proper heading hierarchy, and visual diagrams that help understand the system architecture at a glance.