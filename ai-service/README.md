# DNA AI Service - Template Parser Worker

Background worker service that processes ISO certification documents using Claude AI.

## Architecture

```
Redis Stream → Consumer → Parser Agent → Database
      ↓                                      ↓
   Tasks                              Results (JSONB)
      ↓
  Pub/Sub → WebSocket → Frontend
      ↓
  Progress
```

## Components

### Stream Consumer (`stream_consumer.py`)
- Listens to Redis Streams: `template:parse`, `template:review`
- Consumer group: `parser-workers`
- Processes tasks with XREADGROUP
- ACKs on success, retries on failure

### Parser Agent (`agents/parser.py`)
- Reads Word documents with python-docx
- Calls Claude API for structure analysis
- Extracts sections, fields, validation rules
- Returns structured JSON template

### Database Client (`db_client.py`)
- Async PostgreSQL operations
- Task status updates
- Result storage (JSONB)
- LLM provider configuration

### Redis Client (`redis_client.py`)
- Stream operations (read, ack, create groups)
- Pub/Sub operations (publish progress)
- Connection pooling

## Environment Variables

```bash
# Database
DATABASE_HOST=dna-postgres
DATABASE_PORT=5432
DATABASE_NAME=dna
DATABASE_USER=dna_user
DATABASE_PASSWORD=dna_password_dev

# Redis
REDIS_HOST=dna-redis
REDIS_PORT=6379

# Claude API
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-5-20250929

# Worker
WORKER_CONCURRENCY=3
LOG_LEVEL=INFO
MAX_COST_PER_TASK_USD=5.00
```

## Running

### With Docker Compose

```bash
# Build
docker-compose build dna-ai-service

# Start
docker-compose up -d dna-ai-service

# Logs
docker-compose logs -f dna-ai-service

# Restart
docker-compose restart dna-ai-service
```

### Standalone (for development)

```bash
cd ai-service
pip install -r requirements.txt
python main.py
```

## Task Flow

### 1. Task Published to Stream

```python
# Backend publishes to Redis Stream
await redis_client.xadd(
    "template:parse",
    {
        "task_id": "abc-123",
        "template_id": "def-456",
        "file_path": "/app/uploads/document.docx",
        "iso_standard": "ISO 9001:2015",
        "custom_rules": "...",
        "created_by": "user_id"
    }
)
```

### 2. Worker Consumes Task

```python
# Consumer reads from stream
messages = await redis_client.read_stream_group(
    stream_name="template:parse",
    group_name="parser-workers",
    consumer_name="worker-abc123",
    count=1,
    block=5000
)
```

### 3. Parser Processes Document

```python
# Parser agent extracts structure and fields
template = await parser_agent.parse_document(
    file_path="/app/uploads/document.docx",
    custom_rules="...",
    iso_standard="ISO 9001:2015"
)
```

### 4. Progress Published

```python
# Worker publishes progress to Pub/Sub
await redis_client.publish(
    channel=f"progress:task:{task_id}",
    message={
        "task_id": task_id,
        "progress": 60,
        "current_step": "Extracting fields...",
        "timestamp": "2026-02-07T10:00:00Z"
    }
)
```

### 5. Result Saved

```python
# Worker saves result to database
await db_client.save_task_result(
    task_id=task_id,
    result=template,  # Full template JSON
    cost_usd=0.0623,
    tokens_input=3245,
    tokens_output=2156,
    duration_seconds=18
)
```

## Parser Agent Details

### Document Extraction

- Paragraphs with styles and heading levels
- Tables with full data
- Document metadata (title, author, dates)

### Claude Prompting (2-stage)

**Stage 1: Structure Analysis**
```
Input: Document content + metadata
Task: Identify sections, subsections, hierarchy
Output: JSON structure with sections
```

**Stage 2: Field Extraction**
```
Input: Document content + identified sections
Task: Extract all fillable fields with types
Output: JSON fields with validation rules
```

### Output Format

```json
{
  "template_type": "iso_certification",
  "iso_standard": "ISO 9001:2015",
  "sections": [
    {
      "id": "section_company_info",
      "title": "Company Information",
      "level": 1,
      "has_fields": true,
      "subsections": [...]
    }
  ],
  "fields": [
    {
      "id": "company_name",
      "label": "Company Name",
      "section_id": "section_company_info",
      "type": "text",
      "required": true,
      "max_length": 200,
      "help_text": "Official registered name"
    }
  ],
  "metadata": {
    "total_sections": 8,
    "total_fields": 42,
    "required_fields": 28,
    "completion_estimate_minutes": 35
  }
}
```

## Monitoring

### Health Check

```bash
# Check if worker is running
docker-compose ps dna-ai-service

# Should show: Up (healthy)
```

### Logs

```bash
# Follow logs
docker-compose logs -f dna-ai-service

# Recent activity
docker-compose logs --tail=50 dna-ai-service

# Errors only
docker-compose logs dna-ai-service | grep ERROR
```

### Metrics

```bash
# Task statistics
curl http://localhost:8400/api/tasks/statistics/overview

# Response
{
  "total_tasks": 142,
  "completed": 138,
  "failed": 3,
  "processing": 1,
  "average_duration_seconds": 16.5,
  "total_cost_usd": 8.64,
  "average_cost_usd": 0.061
}
```

## Troubleshooting

### Worker not consuming tasks

**Check consumer groups exist:**
```bash
docker exec -it dna-redis redis-cli XINFO GROUPS template:parse
```

**Check pending messages:**
```bash
docker exec -it dna-redis redis-cli XPENDING template:parse parser-workers
```

### Parser agent not initialized

**Verify API key is set:**
```bash
docker-compose logs dna-ai-service | grep "ANTHROPIC_API_KEY"
```

**Check configuration:**
```bash
docker exec -it dna-ai-service env | grep ANTHROPIC
```

### Task stuck in processing

**Check worker logs:**
```bash
docker-compose logs dna-ai-service | grep "task-id-here"
```

**Check database:**
```sql
SELECT id, status, progress, current_step, error
FROM dna_app.ai_tasks
WHERE id = 'task-id-here';
```

## Cost Optimization

### Current Costs (Claude Sonnet 4.5)

- Input: $3 per 1M tokens
- Output: $15 per 1M tokens
- Typical 20-page doc: ~$0.06

### Optimization Strategies

1. **Cache results:** Don't reparse identical documents
2. **Batch processing:** Process multiple docs in one prompt
3. **Progressive analysis:** Start with structure, only extract fields if needed
4. **Token limits:** Set max_tokens to avoid runaway costs
5. **Model selection:** Use Haiku for simple docs, Sonnet for complex

### Safety Limits

```python
# config.py
MAX_COST_PER_TASK_USD = 5.00  # Abort if cost exceeds $5
```

## Scaling

### Horizontal Scaling

Run multiple workers:

```bash
docker-compose up -d --scale dna-ai-service=3
```

All workers share the same consumer group, so tasks are automatically distributed.

### Vertical Scaling

Increase concurrency per worker:

```bash
# docker-compose.yml
environment:
  - WORKER_CONCURRENCY=10  # Process 10 tasks simultaneously
```

## Development

### Local Development

```bash
cd ai-service

# Install dependencies
pip install -r requirements.txt

# Set environment
export ANTHROPIC_API_KEY=sk-ant-...
export DATABASE_HOST=localhost
export REDIS_HOST=localhost

# Run
python main.py
```

### Testing

```bash
# Integration test
python tests/test_stream_consumer.py

# Manual test
python -c "
import asyncio
import redis.asyncio as redis

async def test():
    r = await redis.from_url('redis://localhost:6379', decode_responses=True)
    await r.xadd('template:parse', {
        'task_id': 'test-123',
        'file_path': '/app/uploads/test.docx'
    })
    await r.aclose()

asyncio.run(test())
"

# Watch logs
docker-compose logs -f dna-ai-service
```

## Dependencies

- **anthropic:** Claude SDK
- **python-docx:** Word document parsing
- **redis:** Stream consumer + Pub/Sub
- **asyncpg:** PostgreSQL async client
- **pydantic:** Data validation

See [requirements.txt](requirements.txt) for versions.
