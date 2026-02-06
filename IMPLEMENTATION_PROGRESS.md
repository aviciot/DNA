# DNA Implementation Progress - AI Worker Integration

**Last Updated:** 2026-02-07  
**Current Phase:** Phase 0 - Planning Complete ✅  
**Next Phase:** Phase 1 - Foundation (Starting)

---

## 📋 Implementation Roadmap

### Phase 0: Planning & Design ✅ COMPLETE
**Duration:** 1 day  
**Status:** ✅ Complete (2026-02-07)

**Deliverables:**
- ✅ Architecture document created (ARCHITECTURE.md)
- ✅ Implementation phases defined
- ✅ Technology decisions finalized
- ✅ Database schema designed
- ✅ Service communication patterns documented

**Key Decisions:**
- Redis Streams for task queue (persistent, reliable)
- Redis Pub/Sub for progress updates (real-time, ephemeral)
- AI-Service as separate worker container
- MCP for ChatWidget tool integration
- Multi-LLM support with configurable providers
- Optional reviewer agent (user-triggered)

---

## 🎯 Phase 1: Foundation
**Goal:** Infrastructure ready for AI workers  
**Duration:** 1-2 days  
**Status:** 🔄 In Progress (Milestone 1.1 Complete ✅)

### Milestone 1.1: Redis Integration ✅ COMPLETE
**Status:** ✅ Complete (2026-02-07)  
**Commit:** 5eee76b

**Tasks:**
- [x] Add Redis to docker-compose.yml
  - Image: redis:7-alpine
  - Port: 6379
  - Volume for persistence
  - Health check
- [x] Install Redis client in backend
  - Add `redis` to requirements.txt
  - Create redis_client.py wrapper
- [x] Test Redis connection from backend
  - Publish test message
  - Subscribe to test channel
  - Verify persistence after restart

**Completed Files:**
```
DNA/
├── docker-compose.yml (updated - added dna-redis service)
├── dashboard/backend/
│   ├── requirements.txt (updated - added redis==5.0.1)
│   └── app/
│       ├── config.py (updated - added REDIS_* settings)
│       ├── main.py (updated - Redis startup/shutdown/health)
│       └── redis_client.py (new - async Redis wrapper)
```

**Testing Results:**
```bash
# All services running
✅ dna-redis: Up (healthy) - port 6379
✅ dna-postgres: Up (healthy) - port 5432
✅ dna-auth: Up (healthy) - port 8401
✅ dna-backend: Up (healthy) - port 8400
✅ dna-frontend: Up - port 3003

# Health check
curl http://localhost:8400/health
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected"  ✅
}

# Backend logs
✅ Redis connected to dna-redis:6379
✅ Redis connection initialized
✅ Service started on 0.0.0.0:8400
```

### Milestone 1.2: Database Schema
**Status:** ✅ COMPLETE (2026-02-07, commit d6ead11)

**Tasks:**
- [x] Create migration: `002_ai_tasks.sql`
  - Add `ai_tasks` table (UUID id, task_type, status, progress, llm_provider, result JSONB, cost tracking)
  - Add `llm_providers` table (multi-LLM configuration with costs)
  - Add `template_reviews` table (quality scores and feedback)
  - Add indexes (6 on ai_tasks, 3 on llm_providers, 3 on template_reviews)
- [x] Seed LLM providers
  - Claude Sonnet 4.5 (enabled, default parser & chat)
  - OpenAI GPT-4 Turbo (disabled, default reviewer when enabled)
  - Gemini Pro (disabled, placeholder)
- [x] Dropped old ai_tasks table (conflicting document workflow table)
- [x] Applied migration successfully to database
- [x] Updated rules.md with new table definitions and indexes

**Completed Files:**
```
DNA/
├── db/init/
│   └── 002_ai_tasks.sql (new - 280 lines)
└── rules.md (updated - added Milestone 1.2 tables and indexes)
```

**Testing Results:**
```bash
# Tables created successfully
\dt dna_app.ai_tasks        ✅ UUID pk, 19 columns, proper constraints
\dt dna_app.llm_providers   ✅ UUID pk, 12 columns, default flags
\dt dna_app.template_reviews ✅ UUID pk, 11 columns, score constraints

# Indexes created (12 total)
ai_tasks: 7 indexes (status, type, related, created_by, created_at, provider, pk)
llm_providers: 4 indexes (name, enabled, default_parser, pk)
template_reviews: 4 indexes (template_id, task_id, created_at, pk)

# LLM providers seeded
SELECT * FROM dna_app.llm_providers;
  name  | display_name      | model                      | enabled | defaults
--------+-------------------+----------------------------+---------+-----------------
 claude | Claude Sonnet 4.5 | claude-sonnet-4-5-20250929 | true    | parser, chat
 openai | GPT-4 Turbo       | gpt-4-turbo-preview        | false   | reviewer
 gemini | Gemini Pro        | gemini-pro                 | false   | none
```

---

### Milestone 1.3: Task Management API
**Tasks:**
- [ ] Create `app/services/task_service.py`
  - `create_task()` - Create task in DB + publish to Redis Stream
  - `update_task_status()` - Update task status
  - `get_task()` - Fetch task by ID
  - `publish_progress()` - Publish to Redis Pub/Sub
- [ ] Create `app/routes/tasks.py`
  - GET `/api/tasks/{task_id}` - Get task status
  - GET `/api/tasks` - List user's tasks
  - POST `/api/tasks/{task_id}/cancel` - Cancel running task
- [ ] Update templates.py upload endpoint
  - Create task record
  - Publish to `template:parse` stream
  - Return task_id immediately (HTTP 202)

**Expected Files:**
```
DNA/
├── dashboard/backend/app/
│   ├── services/
│   │   └── task_service.py (new)
│   └── routes/
│       └── tasks.py (new)
│       └── templates.py (updated)
```

**API Testing:**
```bash
# Upload template
curl -X POST http://localhost:8400/api/templates/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.docx"

# Response
{
  "task_id": "uuid",
  "status": "pending",
  "message": "Template upload queued for processing"
}

# Check task status
curl http://localhost:8400/api/tasks/{task_id}

# Response
{
  "task_id": "uuid",
  "status": "pending",
  "progress": 0,
  "current_step": null
}
```

---

### Milestone 1.4: Progress WebSocket
**Tasks:**
- [ ] Create `app/websocket_relay.py`
  - WebSocket endpoint: `/ws/tasks/{task_id}`
  - Subscribe to Redis Pub/Sub: `progress:task:{task_id}`
  - Forward messages to WebSocket client
  - Handle reconnection
- [ ] Update main.py to register WebSocket route
- [ ] Test with Redis CLI publishing progress

**Expected Files:**
```
DNA/
├── dashboard/backend/app/
│   ├── websocket_relay.py (new)
│   └── main.py (updated)
```

**Testing:**
```javascript
// Frontend test
const ws = new WebSocket('ws://localhost:8400/ws/tasks/123');
ws.onmessage = (event) => {
  console.log(JSON.parse(event.data));
  // {progress: 50, current_step: "Processing..."}
};
```

```bash
# Simulate progress with Redis CLI
redis-cli PUBLISH progress:task:123 '{"progress": 50, "current_step": "Processing..."}'
# WebSocket should receive message
```

---

### Phase 1 Success Criteria ✅
- [x] Redis running and accessible from backend
- [x] Database has ai_tasks, llm_providers tables
- [ ] Backend can publish to Redis Stream
- [ ] Backend can subscribe to Redis Pub/Sub
- [ ] Task API endpoints respond correctly
- [ ] WebSocket receives messages from Redis
- [ ] Template upload creates task and publishes to stream

**Phase 1 Complete When:**  
User uploads template → Task created → Stream message published → WebSocket connected (even if no worker yet)

**Current Progress:** 50% complete (2 of 4 milestones done)

---

## 🤖 Phase 2: AI Worker - Parser Agent
**Goal:** Upload Word doc → Worker parses → Template saved  
**Duration:** 2-3 days  
**Status:** ⏳ Pending Phase 1

### Milestone 2.1: AI Service Setup
**Tasks:**
- [ ] Create `ai-service/` folder structure
  ```
  ai-service/
  ├── Dockerfile
  ├── requirements.txt
  ├── main.py
  ├── config.py
  ├── redis_client.py
  ├── db_client.py
  └── agents/
      └── __init__.py
  ```
- [ ] Add to docker-compose.yml
  - Service: dna-ai-service
  - Depends on: redis, postgres
  - Environment variables
- [ ] Create requirements.txt
  - anthropic
  - python-docx
  - redis
  - asyncpg
  - pydantic

**Testing:**
```bash
docker-compose build dna-ai-service
docker-compose up dna-ai-service
# Should start without errors
```

---

### Milestone 2.2: Stream Consumer
**Tasks:**
- [ ] Create `stream_consumer.py`
  - Connect to Redis
  - Create consumer group: `parser-workers`
  - XREADGROUP from `template:parse`
  - Process messages in infinite loop
  - XACK after processing
  - Error handling & retry logic
- [ ] Integrate into main.py
  - Start consumer in background task
  - Graceful shutdown on SIGTERM
- [ ] Test with manual stream message

**Expected Files:**
```
ai-service/
├── stream_consumer.py (new)
├── main.py (updated)
```

**Testing:**
```bash
# Add message to stream manually
redis-cli XADD template:parse * task_id 123 template_id 456 file_path "/test.docx"

# Check worker logs
docker-compose logs dna-ai-service
# Should show: "Received task: 123"
```

---

### Milestone 2.3: Parser Agent Implementation
**Tasks:**
- [ ] Create `agents/parser.py`
  - Class `TemplateParserAgent`
  - Method: `parse_word_document(file_path, custom_rules)`
  - Read Word doc with python-docx
  - Construct Claude prompt with document content
  - Call Claude API with streaming
  - Parse Claude response into structured JSON
  - Return template structure
- [ ] Create prompt template
  - System prompt for template parsing
  - Few-shot examples
  - Custom rules injection
  - Output format specification (JSON schema)
- [ ] Test with sample ISO document

**Expected Files:**
```
ai-service/
├── agents/
│   ├── parser.py (new)
│   └── prompts/
│       └── template_parser.txt (new)
```

**Prompt Structure:**
```
System: You are an expert at analyzing ISO certification templates...

Parse the following Word document and extract:
1. Document sections with hierarchy
2. Fillable fields with types (text, date, number, etc.)
3. Field constraints (required, max length, etc.)
4. Section descriptions

Custom Rules:
{custom_rules}

Document Content:
{document_text}

Output as JSON:
{
  "sections": [...],
  "fields": [...],
  "metadata": {...}
}
```

---

### Milestone 2.4: Progress Publishing
**Tasks:**
- [ ] Create `progress_publisher.py`
  - Method: `publish_progress(task_id, progress, step)`
  - Publishes to Redis Pub/Sub: `progress:task:{task_id}`
  - Includes timestamp, ETA calculation
- [ ] Integrate into parser agent
  - 10% - Document loaded
  - 30% - Sending to Claude
  - 50% - Parsing response
  - 75% - Validating structure
  - 100% - Complete
- [ ] Update task status in database
  - Start: status = "processing"
  - Progress: update progress field
  - Complete: status = "completed", save result
  - Error: status = "failed", save error

**Expected Files:**
```
ai-service/
├── progress_publisher.py (new)
├── agents/parser.py (updated)
```

**Flow:**
```python
# In parser agent
await progress.publish(task_id, 10, "Loading Word document...")
doc = load_document(file_path)

await progress.publish(task_id, 30, "Analyzing document structure...")
template = await claude.parse(doc)

await progress.publish(task_id, 75, "Validating template...")
validated = validate(template)

await progress.publish(task_id, 100, "Complete!")
await db.save_template(validated)
```

---

### Milestone 2.5: End-to-End Integration
**Tasks:**
- [ ] Upload real ISO certification Word doc
- [ ] Verify task created in database
- [ ] Verify message in Redis Stream
- [ ] Verify worker picks up task
- [ ] Verify progress updates appear in WebSocket
- [ ] Verify parsed template saved to PostgreSQL
- [ ] Verify task marked as completed
- [ ] Frontend polls task status until complete
- [ ] Frontend displays parsed template

**Testing Checklist:**
- [ ] Upload 1-page document → Parses in <30s
- [ ] Upload 50-page document → Parses in <2min
- [ ] Worker restart mid-task → Task resumes (XPENDING)
- [ ] Redis restart → Task persists, worker reconnects
- [ ] Invalid document → Task fails gracefully with error
- [ ] Multiple simultaneous uploads → All process correctly

---

### Phase 2 Success Criteria ✅
- [ ] AI-Service container running
- [ ] Worker consumes from Redis Stream
- [ ] Parser agent successfully parses Word documents
- [ ] Progress updates stream to frontend in real-time
- [ ] Parsed templates saved to PostgreSQL
- [ ] Error handling works (invalid docs, API failures)
- [ ] System recovers from worker/Redis restarts

**Demo:** Upload ISO certification Word doc → See progress bar → View parsed template with sections and fields

---

## 🎨 Phase 3: Frontend Progress UI
**Goal:** User sees live parsing progress  
**Duration:** 1 day  
**Status:** ⏳ Pending Phase 2

### Milestone 3.1: Upload Progress Component
**Tasks:**
- [ ] Create `components/TemplateUploadProgress.tsx`
  - Progress bar (0-100%)
  - Current step text
  - Estimated time remaining
  - Cancel button
  - Success/error states
- [ ] WebSocket hook: `useTaskProgress(taskId)`
  - Connects to `/ws/tasks/{task_id}`
  - Updates progress state
  - Handles reconnection
  - Closes on completion

**Expected Files:**
```
dashboard/frontend/src/
├── components/
│   └── TemplateUploadProgress.tsx (new)
├── hooks/
│   └── useTaskProgress.ts (new)
```

**Component Usage:**
```tsx
<TemplateUploadProgress taskId={taskId} />
```

---

### Milestone 3.2: Task Status Polling
**Tasks:**
- [ ] Update template upload flow
  - On upload success: Store task_id
  - Show progress component
  - Poll `/api/tasks/{task_id}` as fallback
  - On completion: Navigate to template view
- [ ] Add notifications
  - Success toast: "Template parsed successfully!"
  - Error toast: "Failed to parse template"
  - Clickable: Navigate to template or task details

**User Flow:**
1. Click "Upload Template"
2. Select Word file
3. File uploads (shows upload progress)
4. Backend returns task_id
5. Modal shows parsing progress
6. Progress bar updates in real-time
7. On complete: Redirect to template editor
8. Toast: "Template ABC-123 is ready!"

---

### Milestone 3.3: Task History View
**Tasks:**
- [ ] Create page: `/tasks`
  - List all user's tasks
  - Filters: Status (all, pending, processing, completed, failed)
  - Search by template name
  - Sort by date
- [ ] Task detail view
  - Full task information
  - Progress history
  - Error details if failed
  - Link to template if completed
  - Retry button for failed tasks

**Expected Files:**
```
dashboard/frontend/src/app/
└── tasks/
    └── page.tsx (new)
```

---

### Phase 3 Success Criteria ✅
- [ ] Upload shows real-time progress
- [ ] Progress bar updates smoothly
- [ ] Step descriptions are clear
- [ ] Completion notification works
- [ ] Task history page accessible
- [ ] Can retry failed tasks

**Demo:** Upload template → Live progress bar → Redirect to template editor → See parsed structure

---

## 🧠 Phase 4: MCP Integration
**Goal:** ChatWidget can interact with templates  
**Duration:** 2-3 days  
**Status:** ⏳ Pending Phase 3

### Milestone 4.1: MCP Server Setup
**Tasks:**
- [ ] Install MCP SDK in backend
  - Add `mcp` to requirements.txt
- [ ] Create `app/mcp_server.py`
  - Initialize MCP server
  - Register tools
  - Connect to FastAPI WebSocket
- [ ] Update chat.py WebSocket endpoint
  - Pass MCP server to Claude
  - Handle tool calls
  - Stream tool results

**Expected Files:**
```
dashboard/backend/app/
├── mcp_server.py (new)
└── chat.py (updated)
```

---

### Milestone 4.2: MCP Tools Implementation
**Tasks:**
- [ ] Tool: `get_template_status`
  - Query `ai_tasks` table by template_id
  - Return status, progress, error
- [ ] Tool: `list_templates`
  - Query `certification_templates` table
  - Filter by customer, status
  - Return array of templates
- [ ] Tool: `get_template_content`
  - Fetch full template JSON from DB
  - Return structured content
- [ ] Tool: `update_template_field`
  - Update specific field in template
  - Save to database
  - Return success confirmation
- [ ] Tool: `trigger_template_review`
  - Create review task
  - Publish to Redis Stream
  - Return task_id

**Expected Files:**
```
dashboard/backend/app/
└── mcp_tools/
    ├── __init__.py (new)
    ├── template_tools.py (new)
    └── task_tools.py (new)
```

---

### Milestone 4.3: ChatWidget Enhancement
**Tasks:**
- [ ] Update ChatWidget to use MCP-enabled endpoint
- [ ] Handle tool call responses
  - Show "Checking template status..."
  - Display tool results in chat
- [ ] Add quick actions
  - "Check upload status"
  - "List my templates"
  - "Review this template"
- [ ] Test conversational flows
  - "What's the status of template ABC?"
  - "Change company name to Acme Corp"
  - "Review my template for errors"

**Testing Scenarios:**
```
User: "Show me template ABC-123"
Claude: [Uses get_template_content tool]
Claude: "Here's template ABC-123: ISO 9001 Quality Management..."

User: "Is it done parsing?"
Claude: [Uses get_template_status tool]
Claude: "It's 75% complete, currently parsing section 4 of 12."

User: "Review it when done"
Claude: [Uses trigger_template_review tool]
Claude: "I'll start a review when parsing completes. Task ID: XYZ"
```

---

### Phase 4 Success Criteria ✅
- [ ] MCP server integrated with chat WebSocket
- [ ] All 5 tools working correctly
- [ ] ChatWidget can query template status
- [ ] ChatWidget can trigger reviews
- [ ] ChatWidget can update template fields
- [ ] Tool calls stream results smoothly

**Demo:** Chat with AI about uploaded template → AI uses tools to fetch data → AI triggers review

---

## 🔍 Phase 5: Optional Reviewer Agent
**Goal:** User triggers review → Different LLM validates template  
**Duration:** 2 days  
**Status:** ⏳ Pending Phase 4

### Milestone 5.1: Reviewer Agent
**Tasks:**
- [ ] Create `agents/reviewer.py`
  - Class `TemplateReviewerAgent`
  - Method: `review_template(template, cert_standard)`
  - Use GPT-4 (different from parser)
  - Check: completeness, field types, ISO compliance
  - Return: score, missing fields, suggestions
- [ ] Create reviewer prompt
  - ISO standard requirements
  - Field validation rules
  - Completeness criteria
- [ ] Add to stream consumer
  - Listen to `template:review` stream
  - Process with reviewer agent
  - Save to `template_reviews` table

**Expected Files:**
```
ai-service/
└── agents/
    ├── reviewer.py (new)
    └── prompts/
        └── template_reviewer.txt (new)
```

---

### Milestone 5.2: Review UI
**Tasks:**
- [ ] Add "Review Template" button to template editor
- [ ] Create review result panel
  - Overall score badge
  - Completeness score
  - Compliance score
  - Missing fields list
  - Suggestions with apply buttons
- [ ] Apply suggestion action
  - One-click to apply each suggestion
  - Updates template field
  - Marks suggestion as applied

**Expected Files:**
```
dashboard/frontend/src/
└── components/
    ├── TemplateReviewButton.tsx (new)
    └── ReviewResultsPanel.tsx (new)
```

**Review Result Example:**
```
Overall Score: 85/100 ✅

Completeness: 90/100
- Missing 2 required fields

Compliance: 80/100
- Section 4.3 needs more detail

Suggestions:
✓ Add "Quality Policy" field (applied)
⚠ "Management Review" should be date type
⚠ Add "Risk Assessment" section
```

---

### Milestone 5.3: Multi-LLM Configuration
**Tasks:**
- [ ] LLM factory pattern in ai-service
  - `llm_factory.py`
  - Support: Claude, OpenAI, Gemini
  - Load config from `llm_providers` table
- [ ] Admin UI for LLM configuration
  - List providers
  - Enable/disable providers
  - Set default parser/reviewer
  - Test connection button
- [ ] Cost tracking
  - Calculate tokens used
  - Save cost to `ai_tasks.cost_usd`
  - Display in admin dashboard

**Expected Files:**
```
ai-service/
└── llm_factory.py (new)

dashboard/frontend/src/app/
└── admin/
    └── llm-providers/
        └── page.tsx (new)
```

---

### Phase 5 Success Criteria ✅
- [ ] Review button triggers GPT-4 review
- [ ] Review results displayed clearly
- [ ] Suggestions can be applied
- [ ] Multiple LLM providers work
- [ ] Cost tracking accurate
- [ ] Admin can configure providers

**Demo:** Parse template with Claude → Review with GPT-4 → Apply suggestions → Re-review

---

## 📈 Phase 6: Production Readiness
**Goal:** System ready for real users  
**Duration:** 2-3 days  
**Status:** ⏳ Pending Phase 5

### Tasks:
- [ ] Error handling improvements
  - Retry logic for API failures
  - Dead letter queue for failed tasks
  - Admin alerts for stuck tasks
- [ ] Performance optimization
  - Database query optimization
  - Redis connection pooling
  - Worker concurrency tuning
- [ ] Monitoring & logging
  - Structured logging
  - Cost dashboards
  - Task duration metrics
- [ ] Security hardening
  - Redis AUTH enabled
  - API rate limiting
  - File upload validation
- [ ] Documentation
  - User guide for template upload
  - Admin guide for LLM configuration
  - Troubleshooting guide

---

## 🎯 Current Sprint Focus

### This Week (Phase 1)
**Goal:** Redis + Task infrastructure ready  
**Target:** Complete by 2026-02-08
2026-02-07):**
  - [x] Add Redis to docker-compose ✅
  - [x] Create database migration
  - [x] Test Redis connection ✅
  
- **Day 2 (2026-02-08):**
  - [ ] Create database migration (ai_tasks tables)
  - [ ] Implement task service
  - [ ] Create task API endpoints
  
- **Day 3:**
  - [ ] Setup WebSocket relay
  - [ ] Update template upload endpoint
  - [ ] End-to-end test (without worker)
  - [ ] End-to-end test (without worker)
  - [ ] Update rules.md with new ports/connections

---

## 📊 Progress Tracking

### Completed ✅
- Phase 0: Architecture design (2026-02-07)
- Phase 1.1: Redis Integration (2026-02-07)

### In Progress 🔄
- Phase 1: Foundation (25% complete, Milestone 1.1 done)

### Upcoming ⏳
- Phase 2: AI Worker
- Phase 3: Frontend UI
- Phase 4: MCP Integration
- Phase 5: Reviewer Agent
- Phase 6: Production

### Blocked 🚫
- None currently

---

## 🔄 Update Log

**2026-02-07 (Late Evening):**
- ✅ Milestone 1.2 complete - Database schema for AI tasks
- Created 002_ai_tasks.sql migration (280 lines)
- Added ai_tasks table (UUID pk, track async AI operations)
- Added llm_providers table (multi-LLM configuration)
- Added template_reviews table (quality validation results)
- Created 12 indexes across 3 tables
- Seeded 3 LLM providers (Claude enabled, OpenAI & Gemini disabled)
- Updated rules.md with new tables and indexes
- Tested migration successfully
- Committed and pushed to GitHub (d6ead11)
- **Phase 1 now 50% complete (2/4 milestones)**

**2026-02-07 (Evening):**
- ✅ Milestone 1.1 complete - Redis integration
- Added dna-redis service to docker-compose
- Created async Redis client wrapper with Streams + Pub/Sub support
- Backend connects to Redis on startup
- Health check includes Redis status
- All services healthy and running
- Committed and pushed to GitHub (5eee76b)

**2026-02-07 (Morning):**
- Created implementation plan
- Defined 6 phases with milestones
- Broke down Phase 1 into 4 milestones
- Set current sprint focus

**Next Update:** After Milestone 1.2 completion (Database schema
**Next Update:** After Phase 1.1 completion (Redis integration)

---

## 📝 Notes

### Technical Debt to Address:
- None yet (greenfield development)

### Future Enhancements (Phase 7+):
- Document generator agent (template + data → Word doc)
- Batch template processing
- Template version control
- Audit log for AI operations
- Cost optimization with caching

### Learnings:
- (To be filled as we progress)

---

**Remember:** Update this file after EVERY milestone completion. Keep it current!
