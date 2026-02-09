# DNA AI Agents

Professional-grade AI agents for document processing, template management, and content generation.

## Architecture

### 🏗️ Foundation: BaseAgent

All agents extend `BaseAgent`, which provides:

- **Rate-Limited LLM Calls**: Global semaphore prevents API rate limits (max 2 concurrent calls)
- **Integrated Telemetry**: Automatic logging of operations, LLM calls, costs, and performance
- **Stateless Design**: Thread-safe, no shared state between requests
- **Error Handling**: User-friendly error messages with graceful degradation
- **Cost Tracking**: Automatic token counting and cost calculation

**Location:** `agents/base_agent.py`

### 🤖 Available Agents

#### 1. TemplateAgent

**Purpose:** Parse and edit Word document templates for ISO certification.

**Capabilities:**
- `parse_document()`: Extract structure, sections, and fields from Word docs
- `edit_template()`: Modify templates using natural language instructions
- `validate_template()`: Check template validity and compliance

**Features:**
- File validation (format, size, corruption detection)
- Hierarchical section extraction
- Field type detection (text, date, dropdown, etc.)
- ISO standard compliance checking
- Metadata enrichment (completion estimates, field counts)

**Location:** `agents/template.py`

**Usage:**
```python
from agents.template import TemplateAgent

agent = TemplateAgent(
    api_key="your-api-key",
    model="claude-sonnet-4-5-20250929"
)

# Parse a Word document
template = await agent.parse_document(
    file_path="/path/to/document.docx",
    iso_standard="ISO 9001:2015",
    trace_id="trace-123",
    task_id="task-456"
)

# Edit the template
edited = await agent.edit_template(
    template=template,
    instructions="Add a new field 'Employee ID' to the Company Info section",
    trace_id="trace-123",
    task_id="task-789"
)
```

#### 2. ReviewerAgent (TODO: Milestone 2.3)

**Purpose:** Review templates, documents, and content for quality and compliance.

**Planned Capabilities:**
- Review template completeness
- Check ISO compliance
- Validate field definitions
- Suggest improvements

**Location:** `agents/reviewer.py` (not yet implemented)

#### 3. WriterAgent (TODO: Future)

**Purpose:** Generate and modify document content.

**Planned Capabilities:**
- Generate document sections
- Fill templates with data
- Create compliance documentation
- Content refinement

**Location:** `agents/writer.py` (not yet implemented)

## How to Create a New Agent

### Step 1: Create Agent File

```python
# agents/my_agent.py
from agents.base_agent import BaseAgent

class MyAgent(BaseAgent):
    """My specialized agent description."""

    @property
    def agent_name(self) -> str:
        """Agent name for logging/telemetry."""
        return "MyAgent"

    async def do_something(
        self,
        input_data: str,
        trace_id: Optional[str] = None,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Do something with the input.

        Args:
            input_data: Input to process
            trace_id: Optional trace ID for telemetry
            task_id: Optional task ID for telemetry

        Returns:
            Processing result
        """
        # Start operation tracking
        if trace_id:
            await self._start_operation(
                operation_name="Do Something",
                trace_id=trace_id,
                task_id=task_id
            )

        start_time = time.time()

        try:
            # Call LLM with automatic rate limiting and telemetry
            result = await self._call_llm(
                prompt=f"Process this: {input_data}",
                trace_id=trace_id,
                task_id=task_id,
                call_purpose="processing"
            )

            # Complete operation tracking
            duration = int(time.time() - start_time)
            if trace_id:
                await self._complete_operation(
                    operation_name="Do Something",
                    trace_id=trace_id,
                    task_id=task_id,
                    duration_seconds=duration
                )

            return result

        except Exception as e:
            # Fail operation tracking
            if trace_id:
                await self._fail_operation(
                    operation_name="Do Something",
                    trace_id=trace_id,
                    task_id=task_id,
                    error=str(e)
                )
            raise
```

### Step 2: Register in `__init__.py`

```python
# agents/__init__.py
from .my_agent import MyAgent

__all__ = [
    'BaseAgent',
    'TemplateAgent',
    'MyAgent'  # Add your agent
]
```

### Step 3: Add to Stream Consumer

```python
# stream_consumer.py
from agents.my_agent import MyAgent

class StreamConsumer:
    def __init__(self):
        self.my_agent = MyAgent(...)  # Initialize

    async def _create_consumer_groups(self):
        streams = [
            # ... existing streams
            ("my_stream", "my-workers")  # Add your stream
        ]

    async def consume_forever(self):
        # Listen to your stream
        await self._consume_stream(
            stream_name="my_stream",
            group_name="my-workers",
            handler=self._handle_my_task
        )

    async def _handle_my_task(self, data: Dict[str, Any]):
        # Process tasks from your stream
        result = await self.my_agent.do_something(...)
```

## Telemetry & Logging

All agents automatically log structured events:

### Operation Events
```json
{
  "event_type": "operation.started",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_id": "task-123",
  "operation_name": "Parse Template: iso9001.docx"
}
```

### LLM Events
```json
{
  "event_type": "llm.response",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_id": "task-123",
  "duration_ms": 2341,
  "input_tokens": 1234,
  "output_tokens": 567,
  "cost_usd": 0.0123
}
```

### Agent Events
```json
{
  "event_type": "agent.completed",
  "agent_name": "TemplateAgent",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "duration_seconds": 5,
  "result": {"sections": 8, "fields": 42}
}
```

## Best Practices

### ✅ DO:
- Extend `BaseAgent` for all new agents
- Pass `trace_id` and `task_id` to all methods for telemetry
- Use `_call_llm()` for LLM calls (automatic rate limiting + telemetry)
- Use `_start_operation()`, `_complete_operation()`, `_fail_operation()` for tracking
- Provide clear, user-friendly error messages
- Validate inputs before processing
- Keep agents stateless (no instance variables for request data)

### ❌ DON'T:
- Call LLM client directly (bypasses rate limiting)
- Store request-specific data in instance variables (race conditions)
- Skip telemetry calls (loses visibility)
- Raise cryptic technical errors to users
- Assume files exist or are valid without checking
- Use blocking I/O operations (use async)

## Rate Limiting

**Global semaphore in `llm_client.py`:**
- Max 2 concurrent Claude API calls across ALL agents
- Prevents rate limit errors when multiple tasks run in parallel
- Exponential backoff retry on transient failures (3 attempts)

**How it works:**
```python
# All agents share the same semaphore
async with LLMClient._semaphore:  # Wait for available slot
    response = await client.messages.create(...)  # Make API call
# Slot released, next agent can proceed
```

## Error Handling

All agents provide user-friendly error messages:

### File Errors
```
❌ Document not found: /path/to/file.docx
Please ensure the file was uploaded correctly and the path is valid.
```

### Format Errors
```
❌ Invalid file format: .pdf
Only Microsoft Word documents (.docx, .doc) are supported.
Please convert your document to Word format and try again.
```

### LLM Errors
```
❌ Claude AI rate limit exceeded.
The system is currently processing many requests.
Please wait a few moments and try again.
```

### Validation Errors
```
❌ Document appears to be corrupted or in an unsupported format.
Please try:
1. Opening the document in Microsoft Word and re-saving it
2. Converting the document to .docx format
3. Creating a new document and copying the content
```

## Deployment

### Single Container (Current)

**Container:** `dna-ai-service`

**Agents:** All agents run in same container
- TemplateAgent
- ReviewerAgent (future)
- WriterAgent (future)

**Processing:** Sequential (one task at a time)
- `WORKER_CONCURRENCY=1` in config
- No race conditions
- Shared LLM rate limiting

**Benefits:**
- Simple deployment
- No network overhead
- Shared resource management

### Multi-Container (Future)

When scaling is needed:

**Option 1: Dedicated Agent Containers**
```
dna-template-service  → TemplateAgent only
dna-reviewer-service  → ReviewerAgent only
dna-writer-service    → WriterAgent only
```

**Option 2: Horizontal Scaling**
```
dna-ai-service-1  → All agents (replica 1)
dna-ai-service-2  → All agents (replica 2)
dna-ai-service-3  → All agents (replica 3)
```

**When to split:**
- One agent type dominates workload (90% template parsing)
- Need independent scaling (10 template workers, 2 reviewers)
- Different resource requirements (WriterAgent needs more memory)

## Performance Metrics

Track these metrics to determine when to scale:

- **Queue depth**: Tasks waiting in Redis streams
- **Processing time**: Average time per task
- **LLM wait time**: Time waiting for rate limit slot
- **Error rate**: Failed tasks / total tasks
- **Cost per task**: Average tokens and USD cost

**Example telemetry query:**
```json
{
  "event_type": "agent.completed",
  "agent_name": "TemplateAgent",
  "duration_seconds": {"$gt": 60}  // Find slow tasks
}
```

## Testing

### Unit Tests
```bash
pytest tests/agents/test_template_agent.py
pytest tests/agents/test_base_agent.py
```

### Integration Tests
```bash
pytest tests/integration/test_stream_consumer.py
```

### Manual Testing
```bash
# Start the AI service
docker-compose up dna-ai-service

# Submit a test task (via dashboard API)
curl -X POST http://localhost:8000/api/templates/upload \
  -F "file=@test_document.docx" \
  -F "iso_standard=ISO 9001:2015"

# Watch logs
docker-compose logs -f dna-ai-service
```

## Troubleshooting

### Agent Not Processing Tasks

**Check:**
1. Is `ANTHROPIC_API_KEY` set in `.env`?
2. Is Redis running and accessible?
3. Are consumer groups created?
4. Check logs: `docker-compose logs dna-ai-service`

### Rate Limit Errors

**Solution:**
- Reduce `max_concurrent_calls` in `llm_client.py` (default: 2)
- Increase `WORKER_CONCURRENCY` cautiously (default: 1)
- Add more delay between tasks

### High Costs

**Solution:**
- Reduce document size before parsing
- Use cheaper model for non-critical tasks
- Cache common template patterns
- Batch similar tasks together

## References

- **Anthropic API Docs**: https://docs.anthropic.com/
- **Claude Pricing**: https://www.anthropic.com/pricing
- **Redis Streams**: https://redis.io/docs/data-types/streams/
- **AsyncIO**: https://docs.python.org/3/library/asyncio.html
