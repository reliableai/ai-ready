# Chat Completions API vs Responses API

A technical guide for understanding OpenAI's two primary generation APIs—their abstractions, trade-offs, and when to use each.

> **Course context:** This document is part of a course on AI Systems. MCP (Model Context Protocol) is introduced here but covered in depth in a later module.

---

## Table of Contents

1. [Conceptual Framing](#1-conceptual-framing)
2. [The Core Difference: Output Models](#2-the-core-difference-output-models)
3. [State Management](#3-state-management)
4. [Tool Calling](#4-tool-calling)
5. [What Responses API Does NOT Provide](#5-what-responses-api-does-not-provide)
6. [Vendor and Platform Support](#6-vendor-and-platform-support)
7. [Migration Guide](#7-migration-guide)
8. [Summary and Recommendations](#8-summary-and-recommendations)

---

## 1. Conceptual Framing

### Chat Completions API

A **stateless completion API with a chat-shaped interface**.

Despite the name, Chat Completions does not manage conversations. It accepts a list of messages and returns a completion. The "chat" is purely a formatting convention—you provide message history, you get a message back. There is no memory, no state, no threading.

```python
# Chat Completions: stateless, message-shaped
from openai import OpenAI
client = OpenAI()

# You must send the entire conversation history every time
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is 2+2?"},
    {"role": "assistant", "content": "4"},
    {"role": "user", "content": "Multiply that by 3"}  # You provide context
]

response = client.chat.completions.create(
    model="gpt-4o",
    messages=messages
)

# Output is a message
print(response.choices[0].message.content)
```

**Characteristics:**
- Stateless: entire history resent on every call
- Message-oriented: input and output are both "messages"
- Tools and structure layered on top of a chat metaphor
- De facto industry standard (supported by most vendors)

### Responses API

A **systems-first generation API with optional state management**.

The Responses API treats generation as producing **typed output items**, not messages. It's designed for agents, tools, workflows, and multi-step reasoning—where you need to branch on *what the model did*, not parse *what it said*.

```python
# Responses API: typed outputs, optional state
from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-5",
    instructions="You are a helpful assistant.",  # Separate from input
    input="What is 2+2?"
)

# Output is an array of typed items
for item in response.output:
    print(f"Type: {item.type}")
    # Could be: message, function_call, reasoning, image, refusal, etc.

# Convenience helper for text
print(response.output_text)
```

**Characteristics:**
- Stateful-capable: `previous_response_id` or Conversations API
- Output-oriented: typed items, not just messages
- First-class tool calling, reasoning tokens, multimodal
- OpenAI-specific (limited vendor support)

### The Key Shift

> **Chat Completions** is a *stateless API* with a *chat-shaped interface*.  
> **Responses** is a *systems API* with *optional conversation infrastructure*.

Neither "optimizes for conversation" in the sense of remembering anything automatically. But Responses provides explicit mechanisms for state, while Chat Completions leaves state entirely to you.

---

## 2. The Core Difference: Output Models

This is the fundamental architectural distinction.

### Chat Completions: Messages In, Message Out

Output is a single message with content that may encode multiple intents:

```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Weather in Paris?"}],
    tools=[weather_tool]
)

message = response.choices[0].message

# The message may contain:
# - text content (message.content)
# - tool calls (message.tool_calls)
# - both, or neither

# You must check and parse:
if message.tool_calls:
    for tc in message.tool_calls:
        # Tool call info is nested
        name = tc.function.name
        args = tc.function.arguments  # JSON string
elif message.content:
    # Text response
    print(message.content)
```

The message object glues together multiple concerns. Your code must inspect and parse.

### Responses API: Input In, Typed Items Out

Output is an **array of typed items**, each representing a distinct model action:

```python
response = client.responses.create(
    model="gpt-5",
    input="Weather in Paris?",
    tools=[weather_tool]
)

# Output is explicitly typed
for item in response.output:
    if item.type == "function_call":
        # Tool call with direct properties
        print(f"Call: {item.name}({item.arguments})")
        print(f"Correlation ID: {item.call_id}")
    
    elif item.type == "message":
        # Text response
        print(f"Text: {item.content[0].text}")
    
    elif item.type == "reasoning":
        # Model's reasoning (for reasoning models)
        print(f"Reasoning: {item.summary}")
    
    elif item.type == "refusal":
        # Model declined to respond
        print(f"Refused: {item.refusal}")
```

**Item types include:**
- `message` — text response
- `function_call` — tool invocation request
- `function_call_output` — result of a tool call (in input)
- `reasoning` — chain-of-thought (for o1, o3, etc.)
- `image` — generated image
- `refusal` — model declined

This allows application code to branch on **intent**, not text parsing.

---

## 3. State Management

Both APIs are stateless by default. The difference is what mechanisms they provide for state.

### 3.1 Chat Completions: Manual State Only

You manage conversation history yourself. Every request must include the full context.

```python
from openai import OpenAI
client = OpenAI()

# You maintain this
history = [
    {"role": "system", "content": "You are a helpful assistant."}
]

def chat(user_message: str) -> str:
    history.append({"role": "user", "content": user_message})
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=history  # Send everything
    )
    
    assistant_message = response.choices[0].message.content
    history.append({"role": "assistant", "content": assistant_message})
    
    return assistant_message

# Usage
print(chat("My name is Alice."))
print(chat("What's my name?"))  # Works because history includes prior turns
```

**Properties:**
- Full control over what's included
- Must serialize/store history yourself
- Token costs grow with conversation length
- No built-in branching or forking

### 3.2 Responses API: Three Tiers of State

Responses provides explicit, controllable state mechanisms.

#### Tier 1: Manual State (Same as Chat Completions)

```python
# You can still manage state manually
history = [{"role": "user", "content": "My name is Alice."}]

r1 = client.responses.create(
    model="gpt-5",
    input=history,
    store=False  # Don't store on OpenAI
)

# Extend history with model output
history.extend([
    {"role": item.role, "content": item.content}
    for item in r1.output
    if item.type == "message"
])

# Continue
history.append({"role": "user", "content": "What's my name?"})
r2 = client.responses.create(model="gpt-5", input=history, store=False)
```

Use when: stateless deployments, full control, privacy requirements.

#### Tier 2: Lightweight Threading with `previous_response_id`

```python
# First turn
r1 = client.responses.create(
    model="gpt-5",
    input="My name is Alice.",
    store=True  # Required for chaining
)

# Second turn: reference previous response
r2 = client.responses.create(
    model="gpt-5",
    input="What's my name?",
    previous_response_id=r1.id  # OpenAI maintains context
)

print(r2.output_text)  # "Your name is Alice."
```

**Properties:**
- No manual history management
- Responses stored on OpenAI (controlled by `store` parameter)
- Can retrieve any response: `client.responses.retrieve(response_id=r1.id)`
- Supports forking (branch from any point)

**Forking example:**

```python
# Branch from r1, ignoring r2
r3 = client.responses.create(
    model="gpt-5",
    input="Actually, my name is Bob.",
    previous_response_id=r1.id  # Fork from r1
)
# r3 doesn't know about r2
```

Use when: multi-turn interactions, prototyping, forking needed.

#### Tier 3: Durable State with Conversations API

```python
# Create a durable conversation object
conv = client.conversations.create(
    metadata={"user_id": "alice", "session": "onboarding"}
)

# First turn
r1 = client.responses.create(
    model="gpt-5",
    conversation=conv.id,  # Attach to conversation
    input="My name is Alice. I prefer bullet points."
)

# Later (even in a different session/process)
r2 = client.responses.create(
    model="gpt-5",
    conversation=conv.id,
    input="Summarize the benefits of exercise."
)
# Model remembers preferences from r1

# Inspect conversation contents
items = client.conversations.items.list(conversation_id=conv.id)
for item in items.data:
    print(f"{item.type}: {item.content}")
```

**Conversations API features:**
- Durable object with unique ID (`conv_xxx`)
- Persists across sessions, devices, jobs
- Stores all items: messages, tool calls, tool outputs, reasoning
- Metadata support (16 key-value pairs)
- Items can be added/retrieved/listed independently
- Suitable for agents spanning sessions

Use when: long-running agents, cross-session persistence, audit trails.

#### Context Compaction for Long Conversations

For very long conversations, use the `/responses/compact` endpoint:

```python
# When context grows large, compact it
compacted = client.responses.compact(
    model="gpt-5",
    input=long_conversation_history,
    instructions="You are a helpful assistant."
)

# Use compacted context for next turn
response = client.responses.create(
    model="gpt-5",
    input=compacted.output  # Compressed context
)
```

**How compaction works:**
- User messages kept verbatim
- Assistant messages, tool calls, tool results replaced with encrypted summary
- Preserves model's latent understanding
- ZDR (Zero Data Retention) compatible

### 3.3 State Comparison Table

| Mechanism | API | Persistence | Control | Use Case |
|-----------|-----|-------------|---------|----------|
| Manual history | Both | You manage | Full | Stateless deploys, privacy |
| `previous_response_id` | Responses | OpenAI stores | Medium | Multi-turn, prototyping |
| Conversations API | Responses | Durable object | Medium | Agents, cross-session |
| Compaction | Responses | Stateless | Full | Long conversations |

---

## 4. Tool Calling

### 4.1 Structural Differences

**Chat Completions: Externally-tagged, nested schema**

```python
# Chat Completions tool definition
# Note the nested "function" wrapper
tools = [{
    "type": "function",
    "function": {                              # <-- Nested
        "name": "get_weather",
        "description": "Get weather for a city",
        "strict": False,                       # Non-strict by default
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string"}
            },
            "required": ["location"]
        }
    }
}]
```

**Responses API: Internally-tagged, flat schema**

```python
# Responses API tool definition
# Flat structure, no wrapper
tools = [{
    "type": "function",
    "name": "get_weather",                     # <-- Direct
    "description": "Get weather for a city",
    # Strict by default in Responses API
    "parameters": {
        "type": "object",
        "properties": {
            "location": {"type": "string"}
        },
        "required": ["location"],
        "additionalProperties": False          # Required for strict mode
    }
}]
```

### 4.2 Strict Mode

| API | Default | Behavior |
|-----|---------|----------|
| Chat Completions | `strict: false` | Model may return extra fields or wrong types |
| Responses API | `strict: true` | Guaranteed schema conformance |

**For strict mode to work:**
- All fields must be in `required`
- Must include `"additionalProperties": false`

```python
# Strict mode guarantees this schema is followed exactly
"parameters": {
    "type": "object",
    "properties": {
        "location": {"type": "string"},
        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
    },
    "required": ["location", "unit"],      # All fields required
    "additionalProperties": False           # No extra fields
}
```

### 4.3 Response Structure

**Chat Completions: Tool calls nested in message**

```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Weather in Paris?"}],
    tools=tools
)

message = response.choices[0].message

if message.tool_calls:
    for tc in message.tool_calls:
        # Nested access pattern
        call_id = tc.id
        function_name = tc.function.name        # Under .function
        arguments = tc.function.arguments       # JSON string
```

**Responses API: Tool calls as distinct output items**

```python
response = client.responses.create(
    model="gpt-5",
    input="Weather in Paris?",
    tools=tools
)

for item in response.output:
    if item.type == "function_call":
        # Direct access pattern
        call_id = item.call_id                  # Different field name
        function_name = item.name               # Direct property
        arguments = item.arguments              # JSON string
```

### 4.4 Field Name Mapping

| Concept | Chat Completions | Responses API |
|---------|------------------|---------------|
| Call identifier | `tc.id` | `item.call_id` |
| Function name | `tc.function.name` | `item.name` |
| Arguments | `tc.function.arguments` | `item.arguments` |
| Result type | `{"role": "tool", ...}` | `{"type": "function_call_output", ...}` |

### 4.5 Complete Tool Calling Flow

#### Chat Completions

```python
import json
from openai import OpenAI

client = OpenAI()

def get_weather(location: str) -> dict:
    """Your actual function"""
    return {"temp_c": 18, "condition": "sunny"}

tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get weather for a city",
        "parameters": {
            "type": "object",
            "properties": {"location": {"type": "string"}},
            "required": ["location"]
        }
    }
}]

# Step 1: Initial request
messages = [{"role": "user", "content": "Weather in Zurich?"}]
response = client.chat.completions.create(
    model="gpt-4o",
    messages=messages,
    tools=tools
)

# Step 2: Check for tool calls
assistant_message = response.choices[0].message

if assistant_message.tool_calls:
    # Add assistant message to history (includes tool_calls)
    messages.append(assistant_message.model_dump())
    
    # Step 3: Execute tools and add results
    for tc in assistant_message.tool_calls:
        args = json.loads(tc.function.arguments)
        result = get_weather(**args)
        
        messages.append({
            "role": "tool",                    # Special role
            "tool_call_id": tc.id,             # Must match
            "content": json.dumps(result)
        })
    
    # Step 4: Get final response
    final = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=tools
    )
    print(final.choices[0].message.content)
```

#### Responses API

```python
import json
from openai import OpenAI

client = OpenAI()

def get_weather(location: str) -> dict:
    return {"temp_c": 18, "condition": "sunny"}

tools = [{
    "type": "function",
    "name": "get_weather",
    "description": "Get weather for a city",
    "parameters": {
        "type": "object",
        "properties": {"location": {"type": "string"}},
        "required": ["location"],
        "additionalProperties": False
    }
}]

# Step 1: Initial request
response = client.responses.create(
    model="gpt-5",
    input="Weather in Zurich?",
    tools=tools,
    store=True
)

# Step 2: Find function calls
function_calls = [item for item in response.output if item.type == "function_call"]

if function_calls:
    # Step 3: Execute tools and collect outputs
    tool_outputs = []
    for fc in function_calls:
        args = json.loads(fc.arguments)
        result = get_weather(**args)
        
        tool_outputs.append({
            "type": "function_call_output",    # Specific type
            "call_id": fc.call_id,             # Correlation
            "output": json.dumps(result)
        })
    
    # Step 4: Get final response (state managed via previous_response_id)
    final = client.responses.create(
        model="gpt-5",
        input=tool_outputs,
        previous_response_id=response.id,
        store=True
    )
    print(final.output_text)
```

### 4.6 Built-in Tools (Responses API Only)

Chat Completions has no built-in tools. Responses API provides:

```python
# Web search
response = client.responses.create(
    model="gpt-5",
    tools=[{"type": "web_search"}],
    input="What happened in tech news today?"
)

# File search (RAG over vector stores)
response = client.responses.create(
    model="gpt-5",
    tools=[{
        "type": "file_search",
        "vector_store_ids": ["vs_abc123"]
    }],
    input="What does our policy say about remote work?"
)

# Code interpreter (sandboxed Python execution)
response = client.responses.create(
    model="gpt-5",
    tools=[{"type": "code_interpreter"}],
    input="Calculate the standard deviation of [1, 2, 3, 4, 5]"
)

# MCP servers (covered in a later module)
response = client.responses.create(
    model="gpt-5",
    tools=[{
        "type": "mcp",
        "server_label": "my_server",
        "server_url": "https://my-mcp-server.com/sse",
        "require_approval": "never"
    }],
    input="Query my database"
)
```

Built-in tools execute within OpenAI's infrastructure—you don't orchestrate them.

### 4.7 Agentic Loops

**Chat Completions: You orchestrate everything**

```python
def run_agent(user_input: str, tools: list, max_turns: int = 10) -> str:
    """Agentic loop for Chat Completions"""
    messages = [{"role": "user", "content": user_input}]
    
    for _ in range(max_turns):
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools
        )
        
        msg = response.choices[0].message
        messages.append(msg.model_dump())
        
        if not msg.tool_calls:
            return msg.content  # Done
        
        # Execute tools
        for tc in msg.tool_calls:
            result = execute_tool(tc.function.name, tc.function.arguments)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result
            })
    
    raise Exception("Max turns exceeded")
```

**Responses API: Server-side execution for built-in tools**

```python
# For built-in tools, OpenAI runs the loop internally
response = client.responses.create(
    model="gpt-5",
    tools=[
        {"type": "web_search"},
        {"type": "code_interpreter"}
    ],
    input="Search for NVIDIA's stock price and calculate its 30-day moving average"
)

# Single call—OpenAI executed both tools and returned final answer
print(response.output_text)
```

For custom functions, you still orchestrate the loop, but state is simpler.

---

## 5. What Responses API Does NOT Provide

Understanding what the API *doesn't* do is critical for building robust systems.

| Capability | Provided? | Where it belongs |
|------------|-----------|------------------|
| Automatic long-term memory | ❌ | Your application / vector stores |
| Observability / tracing | ❌ | Middleware, logging infrastructure |
| Retry / idempotency | ❌ | Your application / queue system |
| Tool execution guarantees | ❌ | Your code / MCP servers |
| Security policy enforcement | ❌ | Middleware, gateway |
| Rate limiting | ❌ | Your application |
| Cost controls | ❌ | Your application / OpenAI dashboard |

**The Responses API defines the wire format.**

Behavior, policy, observability, and reliability belong in:
- **Your application code**
- **Agent runtimes** (LangChain, CrewAI, OpenAI Agents SDK)
- **MCP servers** (for tool policy and discovery)
- **Middleware and gateways**

This separation of concerns is intentional and aligns with MCP-style architectures (covered in a later module).

---

## 6. Vendor and Platform Support

### Chat Completions: Industry Standard

The Chat Completions API format has become the de facto standard. Nearly everyone supports it.

| Provider | Support | Notes |
|----------|---------|-------|
| **OpenAI** | ✅ Full | Native |
| **OpenRouter** | ✅ Full | 400+ models, drop-in replacement |
| **Anthropic** | ⚠️ Beta | Compatibility layer, not for production |
| **Google Gemini** | ✅ Full | OpenAI-compatible endpoint |
| **Azure OpenAI** | ✅ Full | Native |
| **Mistral AI** | ✅ Full | Native OpenAI-compatible |
| **Together AI** | ✅ Full | OpenAI-compatible |
| **Groq** | ✅ Full | OpenAI-compatible |
| **Fireworks** | ✅ Full | OpenAI-compatible |
| **DeepSeek** | ✅ Full | OpenAI-compatible |

**Code portability example:**

```python
from openai import OpenAI

# Same code works with different providers—just change base_url

# OpenAI
client = OpenAI()

# OpenRouter (400+ models)
client = OpenAI(
    api_key="your-openrouter-key",
    base_url="https://openrouter.ai/api/v1"
)

# Anthropic (beta compatibility)
client = OpenAI(
    api_key="your-anthropic-key",
    base_url="https://api.anthropic.com/v1/"
)

# Same call works everywhere
response = client.chat.completions.create(
    model="gpt-4o",  # or "anthropic/claude-3.5-sonnet", etc.
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### Responses API: OpenAI-Specific

| Provider | Support | Notes |
|----------|---------|-------|
| **OpenAI** | ✅ Full | Native, recommended for new projects |
| **OpenRouter** | ⚠️ Beta | Stateless only, no built-in tools |
| **Others** | ❌ No | Not supported |

**OpenRouter's Responses API limitations:**
- No server-side state (`previous_response_id` doesn't persist on OpenRouter)
- No built-in tools (web_search, file_search, etc.)
- No MCP support
- Essentially a schema translation layer

### Anthropic Compatibility Notes

Anthropic's OpenAI SDK compatibility is **beta and not for production**:

```python
# Anthropic via OpenAI SDK (beta)
client = OpenAI(
    api_key="your-anthropic-key",
    base_url="https://api.anthropic.com/v1/"
)

response = client.chat.completions.create(
    model="claude-sonnet-4-5",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

**Limitations:**
- No prompt caching
- No PDF processing
- No extended thinking output
- No citations
- Strict mode not guaranteed
- System messages concatenated differently

Use Anthropic's native SDK for production.

### Vendor Support Summary

| Scenario | Recommendation |
|----------|---------------|
| Multi-vendor flexibility required | Chat Completions |
| OpenAI-only, maximum features | Responses API |
| Production multi-vendor | Chat Completions |
| Prototyping with latest features | Responses API |

---

## 7. Migration Guide

### Checklist: Chat Completions → Responses API

| Step | Change |
|------|--------|
| 1 | Endpoint: `.chat.completions.create()` → `.responses.create()` |
| 2 | Input: `messages=[...]` → `input=[...]` or `input="..."` |
| 3 | Output: `response.choices[0].message` → `response.output` / `response.output_text` |
| 4 | Tool schema: Remove nested `function` wrapper |
| 5 | Tool schema: Add `"additionalProperties": false` |
| 6 | Tool call ID: `tc.id` → `item.call_id` |
| 7 | Tool call name: `tc.function.name` → `item.name` |
| 8 | Tool result: `{"role": "tool", ...}` → `{"type": "function_call_output", ...}` |
| 9 | Consider: Use `previous_response_id` for state |
| 10 | Consider: Replace custom tools with built-in tools |

### Schema Migration

```python
# BEFORE: Chat Completions
chat_completions_tool = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get weather",
        "parameters": {
            "type": "object",
            "properties": {"location": {"type": "string"}},
            "required": ["location"]
        }
    }
}

# AFTER: Responses API
responses_tool = {
    "type": "function",
    "name": "get_weather",
    "description": "Get weather",
    "parameters": {
        "type": "object",
        "properties": {"location": {"type": "string"}},
        "required": ["location"],
        "additionalProperties": False  # Add this
    }
}
```

### Tool Result Migration

```python
# BEFORE: Chat Completions
tool_result_message = {
    "role": "tool",
    "tool_call_id": "call_abc123",
    "content": '{"temp": 18}'
}

# AFTER: Responses API
tool_result_item = {
    "type": "function_call_output",
    "call_id": "fc_xyz789",
    "output": '{"temp": 18}'
}
```

---

## 8. Summary and Recommendations

### Conceptual Summary

| Aspect | Chat Completions | Responses API |
|--------|------------------|---------------|
| Core abstraction | Messages | Typed output items |
| State model | Stateless (you manage) | Stateless by default, optional persistence |
| Tool calling | Layered on messages | First-class items |
| Strict schemas | Opt-in | Default |
| Built-in tools | None | web_search, file_search, code_interpreter, MCP |
| Vendor support | Industry standard | OpenAI-specific |
| Best for | Portability, simple completions | Agents, workflows, tool-heavy systems |

### When to Use Chat Completions

✅ You need **multi-vendor support** (switch between OpenAI, Anthropic, etc.)  
✅ You're building **stateless services** (Lambda, serverless)  
✅ You have **existing code** that works well  
✅ You're using **fine-tuned models** (behavior may differ across APIs)  
✅ You want **maximum portability** and **no vendor lock-in**

### When to Use Responses API

✅ You're building **OpenAI-only** and want latest features  
✅ You need **built-in tools** (web search, file search, code interpreter)  
✅ You're using **reasoning models** (GPT-5, o3, o4-mini) and want best performance  
✅ You need **MCP integration** (only option)  
✅ You want **server-managed conversation state**  
✅ You're building **agentic workflows** with multiple tools

### Decision Matrix

| Scenario | Recommendation |
|----------|---------------|
| Multi-vendor required | Chat Completions |
| Simple text generation | Either (Responses for new) |
| Tool calling, single vendor | Responses API |
| Need web search / file search | Responses API |
| MCP integration | Responses API |
| Serverless / stateless | Chat Completions |
| Long conversations with branching | Responses API |
| Maximum reasoning performance | Responses API |

### Final Takeaway

> **Chat Completions** is a stateless API with a chat-shaped interface. It's simple, portable, and the industry standard.
>
> **Responses** is a systems API with typed outputs and optional state. It's powerful, agentic, and OpenAI-specific.

Choose based on your constraints: portability vs. features.

---

## References

- [OpenAI: Responses vs Chat Completions](https://platform.openai.com/docs/guides/responses-vs-chat-completions)
- [OpenAI: Migration Guide](https://platform.openai.com/docs/guides/migrate-to-responses)
- [OpenAI: Conversation State](https://platform.openai.com/docs/guides/conversation-state)
- [OpenAI: Function Calling](https://platform.openai.com/docs/guides/function-calling)
- [OpenAI: Tools Guide](https://platform.openai.com/docs/guides/tools)
- [OpenRouter Documentation](https://openrouter.ai/docs/api/reference/overview)
- [Anthropic: OpenAI SDK Compatibility](https://docs.anthropic.com/en/api/openai-sdk)
