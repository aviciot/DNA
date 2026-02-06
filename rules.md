# DNA ISO Certification Dashboard - Architecture & Rules

**Last Updated:** 2026-02-07 (AI Worker architecture planned, Redis + AI-Service to be added)

## 🎯 Overview
DNA is a modern SPA dashboard for managing ISO certification workflows with AI-assisted document completion, intelligent template parsing via async workers, and real-time progress tracking.

**Current Status:** 🔄 Phase 1 Starting - Adding Redis + AI Worker infrastructure  
**See Also:** [ARCHITECTURE.md](ARCHITECTURE.md) for detailed AI worker design, [IMPLEMENTATION_PROGRESS.md](IMPLEMENTATION_PROGRESS.md) for phase tracking

---

## 🏗️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      DNA System Architecture                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────┐      ┌──────────────┐   ┌──────────────┐         │
│  │   Frontend   │◄────►│   Backend    │◄─►│ Auth Service │         │
│  │   (Next.js)  │  WS  │  (FastAPI)   │   │  (FastAPI)   │         │
│  │   Port 3003  │      │  Port 8400   │   │  Port 8401   │         │
│  └──────┬───────┘      └───────┬──────┘   └──────────────┘         │
│         │                      │                   │                 │
│         │ Progress WebSocket   │ Redis Streams    │                 │
│         │                      │ Redis Pub/Sub    │                 │
│         │                      ▼                   │                 │
│         │               ┌────────────┐             │                 │
│         │               │   Redis    │             │                 │
│         │               │ Port 6379  │             │                 │
│         │               └─────┬──────┘             │                 │
│         │                     │ Task Queue         │                 │
│         │                     │ (Streams)          │                 │
│         │                     ▼                    │                 │
│         │            ┌──────────────────┐          │                 │
│         │            │  AI-Service      │          │                 │
│         │            │  (Worker)        │          │                 │
│         │            │  • Parser Agent  │          │                 │
│         │            │  • Reviewer      │          │                 │
│         │            └────────┬─────────┘          │                 │
│         │                     │                    │                 │
│         └─────────────────────┼────────────────────┘                 │
│                               │                                      │
│                        ┌──────▼──────┐                               │
│                        │  PostgreSQL  │                               │
│                        │  Port 5432   │                               │
│                        │              │                               │
│                        │  Schemas:    │                               │
│                        │  - auth      │                               │
│                        │  - dna_app   │                               │
│                        │  - customer  │                               │
│                        └──────────────┘                               │
│                                                                       │
│  AI Integration: Multi-LLM (Claude, OpenAI, Gemini)                  │
│  Task Queue: Redis Streams (persistent, reliable)                    │
│  Progress: Redis Pub/Sub → WebSocket (real-time)                     │
│  Chat: MCP-enabled (tools for system interaction)                    │
│  User Roles: admin (full access), viewer (limited)                   │
│  Security: JWT tokens, session store, secure cookies                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔐 Security Architecture

### Authentication Flow
1. User submits credentials to `/api/v1/auth/login` (auth_service)
2. Auth service validates against `auth.users` table
3. Returns JWT access token + refresh token
4. Frontend stores in httpOnly cookies + localStorage (access token)
5. All requests include `Authorization: Bearer <token>` header
6. Backend validates token with auth_service on each request

### Session Management
- Access token: 30 minutes expiry
- Refresh token: 7 days expiry
- Session store in PostgreSQL `auth.sessions`
- Automatic token rotation on refresh

### Role-Based Access Control (RBAC)
- **admin**: Full dashboard access, template management, AI config, chat
- **viewer**: Read-only access to customer tracking, limited tabs

### Security Headers
- CORS: Restricted origins (no wildcard in production)
- CSP: Content Security Policy enabled
- HSTS: HTTP Strict Transport Security
- X-Frame-Options: DENY
- X-Content-Type-Options: nosniff

---

## 📊 Database Schema

### Connection Details
```
Host: localhost (or dna-postgres inside Docker network)
Port: 5432
Database: dna
User: dna_user
Password: dna_password_dev
```

**Connection String (from host):**
```
postgresql://dna_user:dna_password_dev@localhost:5432/dna
```

**Connection String (from containers):**
```
postgresql://dna_user:dna_password_dev@dna-postgres:5432/dna
```

### Schema: `auth`
**Purpose:** User authentication, sessions, roles

**Tables:**
- `users` - User accounts (id, email, password_hash, full_name, role, is_active, last_login, created_at, updated_at)
- `sessions` - Active sessions (id, session_id, user_id, access_token, refresh_token, expires_at, ip_address, user_agent)
- `roles` - Role definitions with granular permissions (id, name, description, permissions JSONB, is_system, created_at, updated_at)

**Key Indexes:**
- `idx_users_email`, `idx_users_role`, `idx_users_is_active`
- `idx_sessions_user_id`, `idx_sessions_session_id`, `idx_sessions_expires_at`

### Schema: `dna_app`
**Purpose:** ISO certification workflow data

**Tables:**
- `iso_templates` - ISO certificate templates (id, name, iso_standard, template_data JSONB, version, is_active, created_by)
- `customers` - Customer information (id, name, email, contact_person, phone, address, status, metadata JSONB)
- `documents` - Generated documents (id, customer_id, template_id, title, document_data JSONB, completion_percentage, status, assigned_to)
- `conversations` - Chat history with Claude (id, conversation_id UUID, user_id, message_role, message_content, metadata JSONB)
- `ai_tasks` - **NEW** Async AI operations tracking (id, task_type, related_id, status, progress, current_step, llm_provider, result JSONB, cost_usd, duration_seconds)
- `llm_providers` - **NEW** AI provider configuration (id, name, model, api_key_env, cost_per_1k_tokens, enabled, is_default_parser)
- `template_reviews` - **NEW** Template quality reviews (id, template_id, task_id, reviewer_llm, overall_score, suggestions JSONB)

**Key Indexes:**
- `idx_documents_customer_id`, `idx_documents_status`, `idx_documents_assigned_to`
- `idx_conversations_user_id`, `idx_conversations_created_at`
- `idx_ai_tasks_status`, `idx_ai_tasks_type`, `idx_ai_tasks_related` **(NEW)**
- `idx_template_reviews_template` **(NEW)**

### Schema: `customer`
**Purpose:** Advanced certification management (intelligent document generation system)

**Tables:**
- `customers` - Customer organizations (id, name, email, phone, address, business_area, notes, created_by)
- `certifications` - ISO standards catalog (id, code, name, description, requirements_count)
- `certification_templates` - Parsed Word templates (id, certification_id, template_structure JSONB, fields_metadata JSONB, document_type, version)
- `customer_certifications` - Customer certification tracking (id, customer_id, certification_id, status, progress_percentage, dates)
- `customer_documents` - AI-generated filled documents (id, customer_certification_id, template_id, filled_data JSONB, completion_percentage, status, version)

**Key Indexes:**
- `idx_customers_email`, `idx_certification_templates_cert_id`
- `idx_customer_certifications_customer`, `idx_customer_documents_cert_id`

**Schema Configuration:**
All schema names are configurable via environment variables:
- `DATABASE_AUTH_SCHEMA` - Default: `auth`
- `DATABASE_APP_SCHEMA` - Default: `dna_app`  
- `DATABASE_CUSTOMER_SCHEMA` - Default: `customer`

**Schema Rules:**
1. ⛔ **NO TABLES IN PUBLIC SCHEMA** - Always use dedicated schemas for proper separation
2. ⛔ **NEVER HARDCODE SCHEMA NAMES** - Always use `settings.DATABASE_*_SCHEMA` variables
3. ✅ All SQL queries must use f-strings: `f"SELECT * FROM {settings.DATABASE_CUSTOMER_SCHEMA}.customers"`
4. ✅ Schema names are set in `app/config.py` and read from environment variables

**Migration Notes:**
- The `customer` schema implements the new intelligent document generation system (Phase 2 feature)
- Templates parse Word docs with Claude AI to extract fillable fields
- Documents can be generated from interviews, free text, or email threads

---

## 🌐 Service Configuration

### Container Naming Convention
All containers prefixed with `dna-`

| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| Frontend | dna-frontend | 3003 | Next.js SPA, user interface |
| Backend | dna-backend | 8400 | FastAPI, WebSocket chat, business logic, MCP server |
| Auth Service | dna-auth | 8401 | FastAPI, JWT authentication, RBAC |
| PostgreSQL | dna-postgres | 5432 | Database for auth + app + customer data |
| Redis | dna-redis | 6379 | Task queue (Streams) + Progress pub/sub |
| AI Service | dna-ai-service | N/A | Background worker (internal only, no exposed port) |

### Port Allocation (8400-8450 range)
- 3003: Frontend (external, changed from 3000 to avoid conflicts)
- 5432: PostgreSQL (database)
- 6379: Redis (task queue + pub/sub)
- 8400: Backend API + WebSocket
- 8401: Auth Service
- 8402-8450: Reserved for future services

### Internal Service Communication
- Backend ↔ Redis: Internal Docker network (`dna-network`)
- AI-Service ↔ Redis: Internal Docker network (consumer)
- AI-Service ↔ PostgreSQL: Internal Docker network (read templates, write results)
- Backend ↔ PostgreSQL: Internal Docker network (CRUD operations)
- Frontend ↔ Backend: External via localhost:8400 (dev) or domain (prod)

---

## 🔌 API Endpoints

### Auth Service (Port 8401)
```
POST   /api/v1/auth/login      - User login (email + password)
POST   /api/v1/auth/logout     - User logout (revoke token)
POST   /api/v1/auth/refresh    - Refresh access token
GET    /api/v1/auth/verify     - Verify token validity
GET    /api/v1/users/me        - Get current user info
GET    /health                 - Health check
GET    /docs                   - OpenAPI documentation
```

**Example Login Request:**
```json
POST http://localhost:8401/api/v1/auth/login
Content-Type: application/json

{
  "email": "admin@dna.local",
  "password": "admin123"
}
```

**Example Login Response:**
```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "eyJhbGci...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Backend (Port 8400)
```
GET    /api/v1/dashboard/stats      - Dashboard statistics (authenticated)
GET    /api/v1/config/admin         - Admin configuration (admin only)
WS     /ws/chat?token=<jwt>         - WebSocket chat with Claude (MCP-enabled)
WS     /ws/tasks/{task_id}          - WebSocket for task progress updates
GET    /api/tasks/{task_id}         - Get task status
GET    /api/tasks                   - List user's tasks
POST   /api/tasks/{task_id}/cancel  - Cancel running task
POST   /api/templates/upload        - Upload template (creates async task)
POST   /api/templates/{id}/review   - Trigger template review (async)
GET    /health                      - Health check
GET    /docs                        - OpenAPI documentation
```

**Example WebSocket Chat:**
```javascript
const token = localStorage.getItem('access_token');
const ws = new WebSocket(`ws://localhost:8400/ws/chat?token=${token}`);

// Send message
ws.send(JSON.stringify({
  content: "Help me with ISO 9001 certification"
}));

// Receive streaming response
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // data.type: "assistant_chunk" | "assistant_complete" | "error"
  console.log(data);
};
```

---

## 🎨 Frontend Architecture

### Technology Stack
- **Framework:** Next.js 14+ (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS v4
- **State Management:** Zustand
- **API Client:** Axios
- **WebSocket:** Native WebSocket API
- **UI Components:** shadcn/ui components

### Page Structure
```
/login          - Login page with DNA branding
/               - Main dashboard (requires auth)
/admin          - Admin configuration (admin only)
```

### Key Features
- Modern, clean UI with DNA branding
- Responsive design (mobile-first)
- Real-time WebSocket chat with Claude
- Draggable chat widget
- Dev mode toggle (admin only)
- Role-based navigation
- Session persistence
- Secure token handling

---

## 🔄 WebSocket Protocol

### Connection
- Endpoint: `ws://localhost:8400/ws/chat`
- Authentication: Query param `?token=<jwt_token>`
- Reconnection: Automatic with exponential backoff

### Message Format
```json
{
  "type": "user_message | assistant_message | error | system",
  "content": "message text",
  "timestamp": "ISO 8601",
  "conversation_id": "uuid"
}
```

### Claude Integration
- Model: claude-sonnet-4-5-20250929
- Streaming: Server-sent events via WebSocket
- Context: Maintains conversation history in database

---

## 🐳 Docker Configuration

### Networks
- `dna-network` - Internal service communication

### Volumes
- `dna-postgres-data` - Database persistence
- Service code mounted for development

### Environment Variables
All configuration via `.env` files:
- `DATABASE_URL` - Postgres connection string
- `JWT_SECRET_KEY` - Secret for signing JWT tokens
- `ANTHROPIC_API_KEY` - Claude API key
- `CORS_ORIGINS` - Allowed CORS origins
- Environment-specific: `development`, `production`

---

## 📝 Development Rules

1. **No Hardcoded Values:** 
   - ⛔ **NEVER hardcode database schema names** - Always use `settings.DATABASE_*_SCHEMA` variables
   - ⛔ **NEVER hardcode ports, URLs, secrets** - All config from environment variables  
   - ✅ Example: `f"SELECT * FROM {settings.DATABASE_CUSTOMER_SCHEMA}.customers"`
   
2. **Schema Organization:**
   - ⛔ **NO TABLES IN PUBLIC SCHEMA** - All tables must belong to a dedicated schema
   - ✅ Use: `auth`, `dna_app`, `customer` schemas only
   - ✅ All schema names configurable via `app/config.py`
   
3. **Type Safety:** Full TypeScript on frontend, Pydantic on backend

4. **Error Handling:** Global error boundaries, proper HTTP status codes

5. **Logging:** Structured JSON logging on backend

6. **Testing:** Unit tests for critical paths (auth, API endpoints)

7. **Documentation:** Update this file with every architectural change

8. **Docker-First Development:**
   - ⛔ **NEVER run `npm install` or `pip install` locally**
   - ⛔ **NEVER run package managers outside Docker containers**
   - ✅ All dependencies are managed by Docker containers
   - ✅ Changes to `package.json` or `requirements.txt` require rebuilding container:
     ```bash
     docker-compose build dna-frontend   # for npm dependencies
     docker-compose build dna-backend    # for pip dependencies (FastAPI)
     docker-compose build dna-ai-service # for AI worker dependencies
     docker-compose up -d                # restart with new dependencies
     ```
   - ✅ Missing dependencies are fixed by adding to package.json/requirements.txt and rebuilding
   - 💡 Reason: Docker containers have their own isolated environments; local installs serve no purpose

9. **Architecture Documentation:**
   - ⛔ **NEVER make architectural changes without updating docs**
   - ✅ Update [rules.md](rules.md) for service config, ports, connections
   - ✅ Update [ARCHITECTURE.md](ARCHITECTURE.md) for detailed design patterns
   - ✅ Update [IMPLEMENTATION_PROGRESS.md](IMPLEMENTATION_PROGRESS.md) after every milestone
   - 💡 These docs are the single source of truth - keep them current!

---

## 🚫 What We DON'T Include
- No MCP concepts in backend (MCP is only for ChatWidget tool integration)
- No SSE (WebSocket only)
- No Traefik (direct service communication in Docker network)
- No multi-tenant features (single organization)

---

## 🔴 Redis Configuration

### Connection Details (Internal)
```
Host: dna-redis (Docker network) or localhost (from host)
Port: 6379
Database: 0 (default)
No password in development
```

**Connection String (from containers):**
```
redis://dna-redis:6379/0
```

**Connection String (from host - testing):**
```
redis://localhost:6379/0
```

### Redis Streams (Task Queue)

#### Stream: `template:parse`
**Purpose:** Queues Word document parsing tasks  
**Consumer Group:** `parser-workers`  
**Message Format:**
```json
{
  "task_id": "uuid",
  "template_id": "uuid",
  "file_path": "/uploads/template.docx",
  "llm_provider": "claude",
  "custom_rules": "...",
  "created_by": "user_uuid"
}
```

#### Stream: `template:review`
**Purpose:** Queues template quality review tasks  
**Consumer Group:** `reviewer-workers`  
**Message Format:**
```json
{
  "task_id": "uuid",
  "template_id": "uuid",
  "reviewer_llm": "gpt-4",
  "created_by": "user_uuid"
}
```

### Redis Pub/Sub (Progress Updates)

#### Channel Pattern: `progress:task:{task_id}`
**Purpose:** Real-time progress updates for specific task  
**Message Format:**
```json
{
  "task_id": "uuid",
  "progress": 50,
  "current_step": "Extracting section 3 of 12...",
  "eta_seconds": 15,
  "timestamp": "ISO 8601"
}
```

#### Channel Pattern: `task:complete:{task_id}`
**Purpose:** Task completion notification  
**Message Format:**
```json
{
  "task_id": "uuid",
  "status": "completed",
  "result": {...}
}
```

---

## 🤖 AI-Service Configuration

### Environment Variables
```bash
# Database (read-only for most operations)
DATABASE_HOST=dna-postgres
DATABASE_PORT=5432
DATABASE_NAME=dna
DATABASE_USER=dna_user
DATABASE_PASSWORD=dna_password_dev
DATABASE_AUTH_SCHEMA=auth
DATABASE_APP_SCHEMA=dna_app
DATABASE_CUSTOMER_SCHEMA=customer

# Redis
REDIS_HOST=dna-redis
REDIS_PORT=6379

# LLM Providers
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
OPENAI_API_KEY=${OPENAI_API_KEY}       # Future
GOOGLE_API_KEY=${GOOGLE_API_KEY}       # Future

# Worker Configuration
WORKER_CONCURRENCY=3                    # Max concurrent tasks
LOG_LEVEL=INFO
ENABLE_COST_TRACKING=true
MAX_COST_PER_TASK_USD=5.00             # Safety limit
```

### No External Ports
AI-Service runs as internal worker only. No HTTP server exposed.  
Communicates only via:
- Redis Streams (incoming tasks)
- Redis Pub/Sub (outgoing progress)
- PostgreSQL (read config, write results)

---

## 📦 Dependencies

### Frontend
- next, react, react-dom
- axios, zustand
- tailwindcss, lucide-react
- typescript

### Backend
- fastapi, uvicorn
- anthropic (Claude SDK)
- asyncpg (Postgres async driver)
- redis (Redis client with asyncio)
- python-jose (JWT)
- passlib (password hashing)
- websockets
- python-docx (for template parsing in backend routes)

### AI-Service (Worker)
- Redis 7+ (Alpine)

---

## 📚 Additional Documentation

For detailed information, see:
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Complete system architecture with data flows, Redis patterns, MCP tools
- **[IMPLEMENTATION_PROGRESS.md](IMPLEMENTATION_PROGRESS.md)** - Phase-by-phase implementation tracking
- **[rules.md](rules.md)** (this file) - Service configuration, ports, development rules

**Update all three files when making architectural changes!**

---

**Note:** This document is the single source of truth for DNA service configuration
- redis (Stream consumer + Pub/Sub publisher)
- asyncpg (Database client)
- pydantic (Data validation)

### Infrastructure
- Docker, docker-compose
- PostgreSQL 16+

---

**Note:** This document is the single source of truth for DNA architecture. Update after every significant change.
