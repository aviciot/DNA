# DNA System Architecture - AI Worker Integration

**Last Updated:** 2026-02-07  
**Status:** Phase 1 - Planning & Design Complete

---

## 🎯 System Overview

DNA is an ISO certification management system with intelligent template parsing and document generation powered by multiple AI agents working asynchronously.

### Core Philosophy
- **Modular:** Separate services for API, AI processing, and authentication
- **Async-First:** Heavy AI tasks run in background workers
- **Real-time:** WebSocket + Redis Pub/Sub for live progress updates
- **Multi-LLM:** Configurable AI providers (Claude, OpenAI, Gemini)
- **MCP-Enhanced:** ChatWidget uses Model Context Protocol for system interaction

---

## 🏗️ High-Level Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                          FRONTEND LAYER                            │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  Dashboard  │  │  ChatWidget  │  │  Template Upload Form    │  │
│  │  (Next.js)  │  │  (MCP-based) │  │  (with progress bar)     │  │
│  └─────────────┘  └──────────────┘  └──────────────────────────┘  │
│         │  HTTP           │  WebSocket            │  HTTP          │
└─────────┼─────────────────┼───────────────────────┼────────────────┘
          │                 │                       │
          ▼                 ▼                       ▼
┌────────────────────────────────────────────────────────────────────┐
│                         BACKEND LAYER                              │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │           DNA-BACKEND (FastAPI)                              │ │
│  │  • REST API endpoints (CRUD operations)                      │ │
│  │  • WebSocket server (chat + progress updates)               │ │
│  │  • MCP Server (tools for ChatWidget)                        │ │
│  │  • Authentication middleware                                 │ │
│  │  • File upload handling                                     │ │
│  │  • Redis Stream publisher (for async tasks)                │ │
│  │  • Redis Pub/Sub subscriber (for progress updates)         │ │
│  └──────────────────────────────────────────────────────────────┘ │
│         │               │               │                          │
│         │ PostgreSQL    │ Redis Stream  │ Redis Pub/Sub            │
│         ▼               ▼               ▼                          │
└─────────┬───────────────┬───────────────┬──────────────────────────┘
          │               │               │
    ┌─────▼─────┐   ┌────▼────┐    ┌────▼─────┐
    │ DNA-AUTH  │   │  REDIS  │    │POSTGRES  │
    │ (FastAPI) │   │         │    │          │
    │ Port 8401 │   │Port 6379│    │Port 5432 │
    └───────────┘   └────┬────┘    └────┬─────┘
                         │              │
                         │ Streams      │ Read/Write
                         │ Pub/Sub      │
                         ▼              ▼
┌────────────────────────────────────────────────────────────────────┐
│                       AI WORKER LAYER                              │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │           DNA-AI-SERVICE (Python Worker)                     │ │
│  │                                                              │ │
│  │  ┌─────────────────────────────────────────────────────┐   │ │
│  │  │  Stream Consumer                                    │   │ │
│  │  │  • Listens to Redis Streams                         │   │ │
│  │  │  • Consumes tasks: template:parse, template:review  │   │ │
│  │  │  • Acknowledges (XACK) when complete                │   │ │
│  │  └─────────────────────────────────────────────────────┘   │ │
│  │                                                              │ │
│  │  ┌─────────────────────────────────────────────────────┐   │ │
│  │  │  LLM Provider Manager                               │   │ │
│  │  │  • Claude SDK (Anthropic)                           │   │ │
│  │  │  • OpenAI SDK (GPT-4, GPT-4o)                      │   │ │
│  │  │  • Gemini SDK (Google)                             │   │ │
│  │  │  • Dynamic provider switching                       │   │ │
│  │  │  • Cost tracking per operation                      │   │ │
│  │  └─────────────────────────────────────────────────────┘   │ │
│  │                                                              │ │
│  │  ┌─────────────────────────────────────────────────────┐   │ │
│  │  │  AI Agents                                          │   │ │
│  │  │  • Parser Agent (Word doc → structured template)   │   │ │
│  │  │  • Reviewer Agent (quality validation)             │   │ │
│  │  │  • Generator Agent (template + data → document)    │   │ │
│  │  └─────────────────────────────────────────────────────┘   │ │
│  │                                                              │ │
│  │  ┌─────────────────────────────────────────────────────┐   │ │
│  │  │  Progress Publisher                                 │   │ │
│  │  │  • Publishes to Redis Pub/Sub                       │   │ │
│  │  │  • Sends: percentage, current step, ETA             │   │ │
│  │  └─────────────────────────────────────────────────────┘   │ │
│  └──────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Data Flow Patterns

### Pattern 1: Template Upload & Parsing (Async)

```
1. User uploads Word document
   ├─► Frontend: POST /api/templates/upload
   │
2. Backend receives file
   ├─► Saves file to disk/S3
   ├─► Creates task record in PostgreSQL (status: pending)
   ├─► Publishes to Redis Stream: "template:parse"
   │   Message: {task_id, template_id, file_path, llm_config, rules}
   ├─► Returns HTTP 202 Accepted {task_id, status: "pending"}
   │
3. Frontend receives task_id
   ├─► Opens WebSocket connection
   ├─► Subscribes to progress: /ws/tasks/{task_id}
   │
4. AI-Service picks up task
   ├─► XREAD from Redis Stream "template:parse"
   ├─► Updates DB: status = "processing"
   ├─► Publishes progress: "10% - Loading document..."
   │
5. Parser Agent processes
   ├─► Reads Word doc with python-docx
   ├─► Calls Claude API with parsing prompt
   ├─► Publishes progress: "50% - Extracting sections..."
   ├─► Publishes progress: "75% - Identifying fields..."
   │
6. AI-Service saves result
   ├─► Saves parsed template to PostgreSQL
   ├─► Updates DB: status = "completed", progress = 100%
   ├─► XACK to Redis Stream (task acknowledged)
   ├─► Publishes completion: "100% - Complete!"
   │
7. Backend WebSocket relays
   ├─► Forwards progress to Frontend
   ├─► Frontend shows progress bar updating
   ├─► On completion: Shows success + link to template
```

### Pattern 2: ChatWidget Interaction (Sync via MCP)

```
1. User types in ChatWidget
   ├─► "Show me the status of template ABC-123"
   │
2. Frontend sends to Backend WebSocket
   ├─► WS message: {type: "user_message", content: "..."}
   │
3. Backend MCP Server
   ├─► Claude receives message
   ├─► Claude decides to use MCP tool: get_template_status()
   ├─► MCP tool queries PostgreSQL
   ├─► Returns: {status: "completed", progress: 100%, fields: 42}
   │
4. Claude formats response
   ├─► "Template ABC-123 is fully parsed with 42 fields!"
   ├─► Streams response back via WebSocket
   │
5. Frontend displays in ChatWidget
   ├─► Markdown rendered with syntax highlighting
```

### Pattern 3: Optional Review (User-Triggered)

```
1. User clicks "Review Template" button
   ├─► Frontend: POST /api/templates/{id}/review
   │
2. Backend creates review task
   ├─► Creates task record (status: pending)
   ├─► Publishes to Redis Stream: "template:review"
   │   Message: {task_id, template_id, reviewer_llm: "gpt-4"}
   ├─► Returns HTTP 202 Accepted {task_id}
   │
3. AI-Service Reviewer Agent
   ├─► Picks up from "template:review" stream
   ├─► Uses GPT-4 (different LLM than parser)
   ├─► Validates: completeness, field types, ISO compliance
   ├─► Publishes progress: "Reviewing section 1 of 5..."
   │
4. Review saves feedback
   ├─► Saves review to PostgreSQL:
   │   - Overall score (0-100)
   │   - Missing fields list
   │   - Suggestions array
   │   - Compliance issues
   ├─► Updates status: "completed"
   ├─► XACK acknowledgment
   │
5. Use sees review results
   ├─► Toast notification: "Review complete!"
   ├─► Opens review panel with suggestions
   ├─► User can apply fixes or ignore
```

---

## 🔌 Service Communication

### Backend ↔ PostgreSQL
- **Protocol:** TCP/IP (asyncpg)
- **Connection:** Connection pool (10-20 connections)
- **Schemas:** `auth`, `dna_app`, `customer`
- **Access:** Read/Write for CRUD operations

### Backend ↔ Redis
- **Protocol:** RESP3 (Redis Serialization Protocol)
- **Library:** `redis-py` with asyncio support
- **Usage:**
  - **Streams:** Task queue (template:parse, template:review)
  - **Pub/Sub:** Progress updates (progress:task-{id})

### Backend ↔ Auth Service
- **Protocol:** HTTP REST
- **Endpoints:** Token validation, user info
- **Pattern:** Service-to-service auth with shared secret

### AI-Service ↔ Redis
- **Streams:** Consumer with consumer group
- **Pub/Sub:** Publisher for progress
- **Persistence:** Streams persist tasks across restarts

### AI-Service ↔ PostgreSQL
- **Access:** Read-only for config, Read/Write for results
- **Usage:** Fetch LLM config, save parsed templates

### Frontend ↔ Backend
- **REST:** HTTP/HTTPS (CRUD operations)
- **WebSocket:** Real-time chat + progress
- **Auth:** JWT in Authorization header + WebSocket query param

---

## 🗄️ Database Schema Extensions

### New Tables in `dna_app` Schema

#### `ai_tasks`
Tracks all async AI operations
```sql
CREATE TABLE dna_app.ai_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type VARCHAR(50) NOT NULL,  -- 'template_parse', 'template_review', 'document_generate'
    related_id UUID,                  -- template_id or document_id
    status VARCHAR(50) NOT NULL,      -- 'pending', 'processing', 'completed', 'failed'
    progress INTEGER DEFAULT 0,       -- 0-100
    current_step TEXT,                -- "Parsing section 3 of 12..."
    llm_provider VARCHAR(50),         -- 'claude', 'openai', 'gemini'
    llm_model VARCHAR(100),
    result JSONB,                     -- Parsed template or review feedback
    error TEXT,
    cost_usd DECIMAL(10,4),          -- API cost tracking
    duration_seconds INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_by UUID REFERENCES auth.users(id)
);

CREATE INDEX idx_ai_tasks_status ON dna_app.ai_tasks(status);
CREATE INDEX idx_ai_tasks_type ON dna_app.ai_tasks(task_type);
CREATE INDEX idx_ai_tasks_related ON dna_app.ai_tasks(related_id);
```

#### `llm_providers`
Configure available AI providers
```sql
CREATE TABLE dna_app.llm_providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,     -- 'claude', 'openai', 'gemini'
    display_name VARCHAR(100),            -- 'Claude Sonnet 4.5', 'GPT-4o'
    model VARCHAR(100) NOT NULL,
    api_key_env VARCHAR(100),             -- Which env var: 'ANTHROPIC_API_KEY'
    cost_per_1k_input DECIMAL(10,4),
    cost_per_1k_output DECIMAL(10,4),
    max_tokens INTEGER,
    enabled BOOLEAN DEFAULT true,
    is_default_parser BOOLEAN DEFAULT false,
    is_default_reviewer BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Seed data
INSERT INTO dna_app.llm_providers (name, display_name, model, api_key_env, cost_per_1k_input, cost_per_1k_output, max_tokens, is_default_parser) VALUES
('claude', 'Claude Sonnet 4.5', 'claude-sonnet-4-5-20250929', 'ANTHROPIC_API_KEY', 0.003, 0.015, 4096, true);
```

#### `template_reviews`
Store review feedback
```sql
CREATE TABLE dna_app.template_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL REFERENCES customer.certification_templates(id),
    task_id UUID REFERENCES dna_app.ai_tasks(id),
    reviewer_llm VARCHAR(50),
    overall_score INTEGER,                -- 0-100
    completeness_score INTEGER,
    compliance_score INTEGER,
    missing_fields JSONB,                 -- ["field1", "field2"]
    suggestions JSONB,                    -- [{field, issue, suggestion}]
    compliance_issues JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_template_reviews_template ON dna_app.template_reviews(template_id);
```

---

## 📡 Redis Architecture

### Streams (Reliable Task Queue)

#### Stream: `template:parse`
**Purpose:** Queue for Word document parsing tasks

**Message Format:**
```json
{
  "task_id": "uuid",
  "template_id": "uuid",
  "file_path": "/uploads/template.docx",
  "llm_provider": "claude",
  "custom_rules": "Extract section headers as H1, subsections as H2...",
  "created_by": "user_uuid",
  "priority": "normal"
}
```

**Consumer Group:** `parser-workers`  
**Acknowledgment:** XACK after template saved to DB

#### Stream: `template:review`
**Purpose:** Queue for template quality review

**Message Format:**
```json
{
  "task_id": "uuid",
  "template_id": "uuid",
  "reviewer_llm": "gpt-4",
  "review_mode": "full",  // or "quick"
  "created_by": "user_uuid"
}
```

**Consumer Group:** `reviewer-workers`  
**Acknowledgment:** XACK after review saved

### Pub/Sub (Ephemeral Progress Updates)

#### Channel: `progress:task:{task_id}`
**Purpose:** Real-time progress for specific task

**Message Format:**
```json
{
  "task_id": "uuid",
  "progress": 50,
  "current_step": "Extracting section 3 of 12...",
  "eta_seconds": 15,
  "timestamp": "2026-02-07T10:30:00Z"
}
```

#### Channel: `task:complete:{task_id}`
**Purpose:** Task completion notification

**Message Format:**
```json
{
  "task_id": "uuid",
  "status": "completed",  // or "failed"
  "result": {...},
  "error": null
}
```

---

## 🤖 MCP Tools for ChatWidget

### Tool: `get_template_status`
**Purpose:** Query template parsing status  
**Parameters:** `template_id: UUID`  
**Returns:** `{status, progress, fields_count, sections_count}`

### Tool: `list_templates`
**Purpose:** List customer templates  
**Parameters:** `customer_id?: UUID, status?: string`  
**Returns:** `Array<{id, name, status, created_at}>`

### Tool: `get_template_content`
**Purpose:** Fetch parsed template structure  
**Parameters:** `template_id: UUID`  
**Returns:** Full template JSON with all sections/fields

### Tool: `update_template_field`
**Purpose:** Modify template field value  
**Parameters:** `template_id: UUID, field_path: string, value: any`  
**Returns:** `{success, updated_field}`  
**Note:** Simple updates write directly; complex changes may trigger re-parse

### Tool: `trigger_template_review`
**Purpose:** Start template review task  
**Parameters:** `template_id: UUID, reviewer_llm?: string`  
**Returns:** `{task_id, status: "pending"}`

### Tool: `get_task_progress`
**Purpose:** Check AI task status  
**Parameters:** `task_id: UUID`  
**Returns:** `{progress, current_step, eta, status}`

---

## 🔐 Security Considerations

### Redis Security
- No Redis AUTH in development (internal Docker network)
- Production: Redis password + TLS
- Stream ACLs: Workers can only read assigned streams

### AI-Service Security
- Read-only DB access for most operations
- No direct external access (internal service)
- API keys stored in environment variables
- Cost limits per task (prevent runaway costs)

### Worker Isolation
- Separate container from API
- Can restart without affecting user sessions
- Resource limits (CPU/memory) via Docker

---

## 📊 Monitoring & Observability

### Health Checks

#### AI-Service Health
- Endpoint: Internal HTTP `/health`
- Checks:
  - Redis connection
  - PostgreSQL connection
  - LLM provider availability
  - Stream consumer status

#### Task Monitoring
- Query `ai_tasks` table for stuck tasks
- Alert if task in "processing" > 5 minutes
- Dead letter queue for failed tasks

### Metrics to Track
- Tasks processed per hour
- Average task duration
- LLM API costs
- Error rates by task type
- Queue depth (pending tasks)

---

## 🚀 Deployment Configuration

### Environment Variables (AI-Service)

```bash
# Database
DATABASE_HOST=dna-postgres
DATABASE_PORT=5432
DATABASE_NAME=dna
DATABASE_USER=dna_user
DATABASE_PASSWORD=${DATABASE_PASSWORD}
DATABASE_AUTH_SCHEMA=auth
DATABASE_APP_SCHEMA=dna_app
DATABASE_CUSTOMER_SCHEMA=customer

# Redis
REDIS_HOST=dna-redis
REDIS_PORT=6379
REDIS_PASSWORD=${REDIS_PASSWORD}  # Production only

# LLM Providers
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
OPENAI_API_KEY=${OPENAI_API_KEY}
GOOGLE_API_KEY=${GOOGLE_API_KEY}

# Worker Config
WORKER_CONCURRENCY=3              # Max concurrent tasks
WORKER_THREAD_POOL=5              # Thread pool for I/O
LOG_LEVEL=INFO
ENABLE_COST_TRACKING=true
MAX_COST_PER_TASK_USD=5.00       # Prevent runaway costs
```

### Docker Compose Updates

```yaml
services:
  dna-redis:
    image: redis:7-alpine
    container_name: dna-redis
    ports:
      - "6379:6379"
    volumes:
      - dna-redis-data:/data
    networks:
      - dna-network
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3
    restart: unless-stopped

  dna-ai-service:
    build:
      context: ./ai-service
      dockerfile: Dockerfile
    container_name: dna-ai-service
    depends_on:
      - dna-redis
      - dna-postgres
    environment:
      # All env vars listed above
    volumes:
      - ./ai-service:/app
      - ./uploads:/uploads:ro  # Read-only access to uploads
    networks:
      - dna-network
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

---

## 🎯 Design Principles

1. **Async by Default:** Heavy AI operations never block API requests
2. **Fail Gracefully:** Tasks persist in Redis; retry on worker restart
3. **Observable:** All operations tracked in database with timing/cost
4. **Configurable:** Switch LLMs without code changes
5. **User Control:** Optional features (review) are user-triggered
6. **Progressive Enhancement:** MCP adds power to chat without complexity

---

**Next Steps:** See [IMPLEMENTATION_PROGRESS.md](IMPLEMENTATION_PROGRESS.md) for phase-by-phase implementation plan.
