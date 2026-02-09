# AI Service - Quick Reference Card

## 📁 File Structure

```
ai-service/
├── agents/
│   ├── __init__.py          → Exports: BaseAgent, TemplateAgent
│   ├── base_agent.py        → Foundation class (extend this!)
│   ├── template.py          → Parse & edit templates
│   ├── parser.py            → DEPRECATED (old code)
│   └── README.md            → Full architecture guide
├── llm_client.py            → Rate-limited Claude client
├── telemetry.py             → Structured logging
├── stream_consumer.py       → Redis stream processor
├── db_client.py             → PostgreSQL client
├── config.py                → Environment config
└── POLISH_COMPLETE.md       → What we just built
```

## 🚀 Quick Start

### Add New Agent (5 steps)

```python
# 1. Create file: agents/my_agent.py
from agents.base_agent import BaseAgent

class MyAgent(BaseAgent):
    @property
    def agent_name(self) -> str:
        return "MyAgent"

    async def do_task(self, data, trace_id, task_id):
        result = await self._call_llm(
            prompt=f"Process: {data}",
            trace_id=trace_id,
            task_id=task_id,
            call_purpose="my_task"
        )
        return result

# 2. Register: agents/__init__.py
from .my_agent import MyAgent
__all__ = ['BaseAgent', 'TemplateAgent', 'MyAgent']

# 3. Initialize: stream_consumer.py __init__
self.my_agent = MyAgent(api_key=..., model=...)

# 4. Add stream: stream_consumer.py _create_consumer_groups
("my:stream", "my-workers")

# 5. Add handler: stream_consumer.py consume_forever
await self._consume_stream("my:stream", "my-workers", self._handle_my_task)
```

## 🔌 Using BaseAgent

### Call LLM (with rate limiting + telemetry)
```python
result = await self._call_llm(
    prompt="Your prompt here",
    system_prompt="Optional system instructions",
    temperature=0.7,
    trace_id=trace_id,
    task_id=task_id,
    call_purpose="descriptive_name"
)
# Returns: {"content": "...", "usage": {...}, "cost_usd": 0.05, ...}
```

### Extract JSON
```python
json_str = self._extract_json(result["content"])
data = json.loads(json_str)
```

### Track Operations
```python
# Start
await self._start_operation(
    operation_name="User-friendly name",
    trace_id=trace_id,
    task_id=task_id
)

# Complete
await self._complete_operation(
    operation_name="User-friendly name",
    trace_id=trace_id,
    task_id=task_id,
    duration_seconds=10,
    result_field=value  # Any result data
)

# Fail
await self._fail_operation(
    operation_name="User-friendly name",
    trace_id=trace_id,
    task_id=task_id,
    error="What went wrong",
    error_type="category"
)
```

## 📊 Telemetry Events

### Structure
```json
{
  "event_id": "uuid",
  "timestamp": "2025-01-15T10:30:00Z",
  "event_type": "operation.started",
  "service": "dna-ai-service",
  "trace_id": "trace-uuid",
  "task_id": "task-uuid",
  "user_id": "user-uuid",
  "data": {...},
  "metadata": {...}
}
```

### Event Types
- `operation.started` → Task begins
- `operation.completed` → Task succeeds
- `operation.failed` → Task fails
- `agent.started` → Agent begins work
- `agent.completed` → Agent finishes
- `agent.failed` → Agent error
- `llm.request` → LLM call starts
- `llm.response` → LLM call completes

## 🛡️ Error Handling

### Raise User-Friendly Errors
```python
# ✅ GOOD - Clear, actionable
raise ValueError(
    "Document appears to be corrupted.\n"
    "Please try:\n"
    "1. Open in Microsoft Word and re-save\n"
    "2. Convert to .docx format\n"
    "3. Create new document and copy content"
)

# ❌ BAD - Technical jargon
raise Exception("zipfile.BadZipFile at offset 0x4A2F")
```

### Handle Common Errors
```python
try:
    # Your code
    pass
except FileNotFoundError:
    # File doesn't exist - tell user where to find it
    pass
except ValueError:
    # Validation failed - tell user how to fix
    pass
except RuntimeError:
    # Config/setup issue - tell user to contact admin
    pass
except Exception as e:
    # Unexpected - log details but give user simple message
    logger.error(f"Unexpected error: {e}")
    raise RuntimeError("An unexpected error occurred. Please try again.")
```

## 🔒 Rate Limiting

### How It Works
```python
# Global semaphore (shared across ALL agents)
LLMClient._semaphore = asyncio.Semaphore(2)  # Max 2 concurrent calls

# When agent calls LLM:
async with LLMClient._semaphore:  # Waits if 2 calls already running
    response = await client.messages.create(...)
# Releases slot when done
```

### Configuration
```python
# llm_client.py
LLMClient(
    api_key="...",
    max_concurrent_calls=2,  # ← Change here
    max_retries=3
)
```

## 💰 Cost Tracking

### Pricing (Claude Sonnet 4.5)
- Input: $3.00 per 1M tokens
- Output: $15.00 per 1M tokens

### Calculate Cost
```python
# Automatic in llm_client.py
cost = (input_tokens / 1_000_000 * 3.0) + (output_tokens / 1_000_000 * 15.0)
```

### Track in Logs
```bash
grep "cost_usd" logs.txt | awk '{sum+=$NF} END {print sum}'
```

## 🐛 Debugging

### Enable Debug Logging
```python
# config.py or .env
LOG_LEVEL=DEBUG
```

### View Telemetry
```bash
docker logs dna-ai-service 2>&1 | grep "event_type"
```

### Find Errors
```bash
docker logs dna-ai-service 2>&1 | grep "operation.failed"
```

### Check Rate Limits
```bash
docker logs dna-ai-service 2>&1 | grep "rate limit"
```

### Trace Single Request
```bash
# Get trace_id from API response, then:
docker logs dna-ai-service 2>&1 | grep "trace-uuid-here"
```

## 📋 Common Tasks

### Test Agent Locally
```python
import asyncio
from agents.template import TemplateAgent

async def test():
    agent = TemplateAgent(
        api_key="your-key",
        model="claude-sonnet-4-5-20250929"
    )

    result = await agent.parse_document(
        file_path="/path/to/test.docx",
        iso_standard="ISO 9001:2015",
        trace_id="test-trace",
        task_id="test-task"
    )

    print(result)

asyncio.run(test())
```

### Deploy Changes
```bash
# 1. Build
docker-compose build dna-ai-service

# 2. Restart
docker-compose restart dna-ai-service

# 3. Watch logs
docker-compose logs -f dna-ai-service
```

### Check Health
```bash
# Redis connection
docker exec dna-ai-service python -c "from redis_client import redis_client; import asyncio; asyncio.run(redis_client.connect()); print('OK' if asyncio.run(redis_client.ping()) else 'FAIL')"

# Database connection
docker exec dna-ai-service python -c "from db_client import db_client; import asyncio; asyncio.run(db_client.connect()); print('OK')"

# API key configured
docker exec dna-ai-service python -c "from config import settings; print('OK' if settings.ANTHROPIC_API_KEY else 'MISSING')"
```

### Rollback
```bash
# Revert last commit
git revert HEAD
git push

# Or redeploy previous image
docker-compose down
docker-compose up -d
```

## 🎯 Best Practices

### ✅ DO
- Extend `BaseAgent` for all agents
- Pass `trace_id` and `task_id` everywhere
- Use `_call_llm()` for LLM calls
- Validate inputs before processing
- Provide clear error messages
- Keep agents stateless
- Log important events
- Track costs

### ❌ DON'T
- Call LLM client directly
- Store request data in instance vars
- Skip telemetry calls
- Raise technical errors to users
- Assume files exist/valid
- Use blocking I/O
- Ignore rate limits
- Forget error handling

## 📚 Key Files to Know

| File | Purpose | When to Edit |
|------|---------|--------------|
| `agents/base_agent.py` | Foundation | Rarely (affects all agents) |
| `agents/template.py` | Template logic | Add features |
| `llm_client.py` | Rate limiting | Change limits |
| `stream_consumer.py` | Task routing | Add streams/handlers |
| `telemetry.py` | Logging | Add event types |
| `config.py` | Settings | Add env vars |

## 🚨 Emergency Contacts

### System Down
1. Check logs: `docker logs dna-ai-service`
2. Check Redis: `docker exec dna-redis redis-cli PING`
3. Check DB: `docker exec dna-postgres pg_isready`
4. Restart: `docker-compose restart dna-ai-service`

### High Costs
1. Check queue depth: `redis-cli XLEN template:parse`
2. Check active tasks: `grep "processing" logs.txt | wc -l`
3. Reduce `max_concurrent_calls` in `llm_client.py`
4. Pause consumer: `docker-compose stop dna-ai-service`

### Slow Performance
1. Check queue: Tasks backing up?
2. Check LLM wait time: `grep "llm.response" | awk '{sum+=$duration} END {print sum/NR}'`
3. Increase `max_concurrent_calls` (carefully!)
4. Scale horizontally: Deploy more workers

## 📞 Support

- **Architecture questions**: See `agents/README.md`
- **Deployment issues**: See `POLISH_COMPLETE.md`
- **API docs**: https://docs.anthropic.com/
- **Redis streams**: https://redis.io/docs/data-types/streams/

---

**Last Updated:** 2025-01-15
**Version:** 2.0 (Post-Polish)
**Status:** Production-Ready ✅
