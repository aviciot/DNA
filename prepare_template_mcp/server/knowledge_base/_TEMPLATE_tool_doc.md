# Tool: [tool_name]

> **Instructions**: Copy this template to `tools/tool_name.md` and customize all sections

## 📋 Overview

**Tool Name**: `your_tool_name`  
**Purpose**: [One sentence describing what this tool does]  
**Category**: [Analysis/Data Retrieval/Monitoring/Comparison/etc]

## 🎯 What Does This Tool Do?

[2-3 paragraphs explaining the tool's functionality in detail]

This tool [MAIN PURPOSE]. It provides [KEY OUTPUTS] by [HOW IT WORKS].

Use this tool when [PRIMARY USE CASE]. It's particularly valuable for [SPECIFIC SCENARIO].

## 📥 Input Parameters

### Required Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `param1` | `str` | [Description] | `"example_value"` |
| `param2` | `int` | [Description] | `100` |

### Optional Parameters

| Parameter | Type | Default | Description | Example |
|-----------|------|---------|-------------|---------|
| `param3` | `str` | `"default"` | [Description] | `"custom_value"` |
| `param4` | `bool` | `True` | [Description] | `False` |

## 📤 Output Structure

The tool returns a dictionary with the following structure:

```json
{
  "status": "success|error",
  "data": {
    "key_metric_1": "value",
    "key_metric_2": 123,
    "details": [
      {
        "item": "example",
        "value": "data"
      }
    ]
  },
  "metadata": {
    "execution_time_ms": 145,
    "timestamp": "2026-01-06T14:00:00Z"
  }
}
```

### Key Output Fields

| Field | Type | Description |
|-------|------|-------------|
| `data.key_metric_1` | `str` | [What this contains] |
| `data.key_metric_2` | `int` | [What this represents] |
| `data.details` | `list` | [What's in the list] |

## 🚀 Usage Examples

### Example 1: Basic Usage

```python
# Scenario: [Common use case]
result = your_tool_name(
    param1="production_db",
    param2=100
)

# What to look for:
# - Check result['data']['key_metric_1'] for [INFORMATION]
# - Review result['data']['details'] for [SPECIFIC DATA]
```

**Expected Output**:
```json
{
  "status": "success",
  "data": {
    "key_metric_1": "sample_data",
    "details": [...]
  }
}
```

### Example 2: Advanced Usage

```python
# Scenario: [More complex use case]
result = your_tool_name(
    param1="production_db",
    param2=100,
    param3="custom_filter"
)

# How to interpret:
# 1. First check [FIELD X]
# 2. Then review [FIELD Y]
# 3. If [CONDITION], do [ACTION]
```

### Example 3: Error Handling

```python
# Scenario: Handle potential errors
result = your_tool_name(param1="invalid_value")

if result['status'] == 'error':
    # Common errors:
    # - "Not found" → [CAUSE AND FIX]
    # - "Access denied" → [CAUSE AND FIX]
    # - "Timeout" → [CAUSE AND FIX]
    print(f"Error: {result.get('error')}")
```

## 🔄 Common Workflows

### Workflow 1: [Common Task Name]

**Scenario**: User needs to [GOAL]

**Steps**:
1. Call `your_tool_name(param1='...')`
2. Review `result['data']['key_metric_1']`
3. If [CONDITION], call `another_tool()`
4. Present findings: [WHAT TO TELL USER]

**Example Conversation**:
```
User: "I need to check X"
LLM: Calls your_tool_name(param1='user_value')
LLM: "Based on the analysis, [INTERPRETATION]"
```

### Workflow 2: [Another Common Task]

**Scenario**: User reports [PROBLEM]

**Steps**:
1. Call `your_tool_name(param1='...', param2=...)`
2. Look for [INDICATOR 1] in the output
3. If present, [ACTION]
4. Otherwise, [ALTERNATIVE ACTION]

## ⚠️ Important Notes

### Performance Considerations
- **Response Time**: Typically [X-Y seconds]
- **Rate Limits**: [IF ANY]
- **Resource Usage**: [MEMORY/CPU NOTES]

### Known Limitations
1. **[Limitation 1]**: [Description and workaround]
2. **[Limitation 2]**: [Description and workaround]

### Best Practices
- ✅ **DO**: [Recommendation 1]
- ✅ **DO**: [Recommendation 2]
- ❌ **DON'T**: [Anti-pattern 1]
- ❌ **DON'T**: [Anti-pattern 2]

## 🐛 Troubleshooting

### Error: "[Common Error Message]"

**Cause**: [Why this happens]

**Solution**:
```python
# Fix approach
your_tool_name(
    param1="corrected_value",  # Changed from incorrect_value
    param2=proper_setting
)
```

### Error: "[Another Common Error]"

**Cause**: [Why this happens]

**Solution**: [Step-by-step fix]

## 🔗 Related Tools

- **[related_tool_1](related_tool_1.md)** - Use this to [WHEN]
- **[related_tool_2](related_tool_2.md)** - Combine with this for [SCENARIO]

## 📊 Real-World Example

**Scenario**: [Realistic business problem]

```python
# User asks: "[User question]"

# Step 1: Gather initial data
result = your_tool_name(
    param1="production",
    param2=100
)

# Step 2: Analyze results
if result['data']['key_metric_1'] > threshold:
    # Found the issue!
    explanation = f"The problem is {result['data']['details'][0]}"
else:
    # Need more investigation
    result = another_tool(follow_up_param)

# Step 3: Present findings
print(f"Analysis complete: {explanation}")
```

**Output Interpretation**:
- If `key_metric_1` is high → [WHAT IT MEANS]
- If `details` list is empty → [WHAT IT MEANS]
- If `status` is error → [WHAT TO DO]

## 📚 See Also

- [Overview](../overview.md) - Full MCP capabilities
- [Workflows](../workflows.md) - Step-by-step guides
- [Troubleshooting](../troubleshooting.md) - Common issues
