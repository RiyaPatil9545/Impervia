# Impervia — Privacy-Aware Academic Assistant Backend

**Impervia** is a privacy-aware academic assistant backend designed to protect students' personal information and emotional disclosures before their academic inquiries reach an AI model.

The system enforces data minimization, context awareness, and user consent through an in-memory Privacy Handler pipeline that inspects, sanitizes, separates, or redirects user messages before storage or downstream processing.

---

## 1. System Architecture & Privacy Pipeline

```
User Input
    │
    ▼
Text Preprocessing (NFKC normalization, control character stripping)
    │
    ▼
Privacy Detection Layer
 ├── PII Detection (Emails, Phone numbers, Student IDs, National IDs, Cards, Names, IPs)
 ├── Sensitive Content Detection (Emotional distress, Crisis, Medical, Financial)
 └── Academic Relevance Detection (Subject vocabulary, Intent scoring, Query extraction)
    │
    ▼
Risk Assessment & Decision Engine
 ├── Pass Through ──► Safe academic input preserved unchanged
 ├── Sanitize     ──► In-place PII masking with [REDACTED_*] tokens
 ├── Separate     ──► Academic question extracted; sensitive portion isolated
 └── Redirect     ──► Crisis guidance or privacy notice returned; no forward
    │
    ▼
Storage Policy Enforcement (In-Memory Decision)
 ├── save_chat_history == False        ──► 0 message rows persisted; message_id=NULL in analysis
 ├── save_chat_history == True         ──► ONLY sanitized text stored (DB CHECK constraint enforced)
 └── allow_aggregate_analytics == True ──► Daily metrics incremented atomically (strictly anonymous)
```

---

## 2. Technology Stack

- **Framework**: FastAPI (Asynchronous REST API, OpenAPI/Swagger)
- **Database**: PostgreSQL (Hosted on Aiven) with 12 existing tables
- **ORM**: SQLAlchemy 2.0 (Declarative models, type-annotated Mapped attributes)
- **Driver**: Psycopg 3 (`postgresql+psycopg`)
- **Authentication**: JWT (`PyJWT`) with Argon2 password hashing (`pwdlib[argon2]`)
- **Validation**: Pydantic v2 & Pydantic Settings
- **Testing**: Pytest with Pytest-Cov

---

## 3. Database Schema Alignment

The backend maps strictly to the 12 existing Aiven PostgreSQL tables:

1. `users` — User credentials with Argon2 password hashes.
2. `user_privacy_settings` — Consent flags (`save_chat_history`, `allow_aggregate_analytics`, `warn_before_high_risk`, `retention_days`).
3. `chat_sessions` — User conversation sessions.
4. `chat_messages` — Stored conversation turns (enforces `chk_message_role_status` where user messages MUST be `sanitized_text`).
5. `privacy_analyses` — Identifiable analysis records with `message_id` (NULL when history is disabled).
6. `privacy_findings` — Category, occurrence count, action taken, and confidence (never stores raw detected text).
7. `privacy_audit_logs` — Operational audit trails (metadata only, prompts/tokens stripped).
8. `privacy_daily_metrics` — Aggregate anonymous counts updated via atomic upserts (`chk_metrics_risk_total`, `chk_metrics_path_total`).
9. `academic_responses` — Metadata for future Academic LLM integration.
10. `knowledge_sources` — Academic knowledge resource metadata for future RAG.
11. `knowledge_chunks` — Chunk references for pgvector/Qdrant.
12. `response_sources` — Linkages between generated responses and retrieved chunks.

---

## 4. Installation & Setup

### Prerequisites
- Python 3.11+
- Virtual environment (already established in `.venv`)

### Configuration
Copy the template configuration and fill in your credentials:

```powershell
cp .env.example .env
```

Ensure your `.env` contains:
```ini
APP_NAME=Impervia
DEBUG=false
SECRET_KEY=your-secure-jwt-secret-key-at-least-32-chars
DB_HOST=your-aiven-host.aivencloud.com
DB_PORT=5432
DB_NAME=defaultdb
DB_USER=avnadmin
DB_PASSWORD=your_password
DB_SSLMODE=require
```

---

## 5. Running the Backend

Activate your virtual environment and start the Uvicorn server:

```powershell
# From the backend directory
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive API documentation will be available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/api/v1/health

---

## 6. Running the Test Suite

Execute the full automated test suite with coverage:

```powershell
# Run all tests
pytest -v

# Run with test coverage
pytest --cov=app --cov-report=term-missing
```

---

## 7. API Endpoints Overview

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/v1/health` | Service and database connectivity health check | No |
| `POST` | `/api/v1/auth/register` | Register new user with default privacy settings | No |
| `POST` | `/api/v1/auth/login` | Login and receive Bearer JWT token | No |
| `GET` | `/api/v1/auth/me` | Current user profile and privacy preferences | Yes |
| `DELETE`| `/api/v1/auth/account` | Permanent account deletion & cascading cleanup | Yes |
| `GET` | `/api/v1/settings` | Get privacy settings | Yes |
| `PUT` | `/api/v1/settings` | Update privacy settings and consent | Yes |
| `POST` | `/api/v1/settings/purge-history`| Purge chat messages by retention period or all | Yes |
| `POST` | `/api/v1/privacy/analyze` | Direct text analysis via Privacy Pipeline | Optional |
| `GET` | `/api/v1/privacy/analyses` | List past privacy analyses for user | Yes |
| `GET` | `/api/v1/privacy/analyses/{id}` | Get specific analysis with structured findings | Yes |
| `POST` | `/api/v1/chat/sessions` | Create a new chat session | Yes |
| `GET` | `/api/v1/chat/sessions` | List user's chat sessions | Yes |
| `GET` | `/api/v1/chat/sessions/{id}` | Get session details and messages | Yes |
| `DELETE`| `/api/v1/chat/sessions/{id}` | Delete a chat session | Yes |
| `POST` | `/api/v1/chat/process` | Full privacy-preserving academic query interaction | Yes |
| `GET` | `/api/v1/analytics/daily` | Anonymous aggregate daily metrics | Yes |
| `GET` | `/api/v1/analytics/summary` | Anonymous aggregate summary statistics | Yes |

---

## 8. Offline Model Retraining

To evaluate or retrain the privacy detection engine on synthetic benchmarks:

```powershell
python scripts/train_privacy_model.py --dataset data/synthetic_benchmark.jsonl
```
*Note: Impervia strictly prohibits training on live student conversations. All training operates solely on synthetic, certified benchmark files.*
