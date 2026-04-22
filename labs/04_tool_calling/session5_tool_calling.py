# %% [markdown]
# # Session 5: Tool Calling
#
# How do LLMs interact with external capabilities? Through **tool calling** — the model decides *which* function to invoke and *what arguments* to pass, then your code executes it and feeds the result back.
#
# **Key insight:** Tool calling is not just an output format problem. It is a **control problem** — the system must decide when to call a tool, which tool, and when to stop.
#
# ### Sections
#
# 0. Setup
# 1. The Dataset & Our Tools
# 2. Built-in Tools (Provider-Managed)
# 3. Tool Calling Without API Support (DIY)
# 4. Registering Custom Tools — API Tool Calling
# 5. Tool Calling By Hand — Stress Test
# 6. The Multi-Tool Loop
# 7. When to Stop (The Control Problem)
# 8. Stopping for User Input
# 9. Tool Naming & Documentation Matter
#
# Run cells in order.

# %% [markdown]
# ## 0. Setup

# %%
import os
import json
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("OPENAI_API_KEY not found. Add it to .env")

client = OpenAI()
MODEL = "gpt-4.1-mini"
MODEL_STRONG = "gpt-5.2"
print(f"Client ready — default model: {MODEL}")

# %% [markdown]
# ## 1. The Dataset & Our Tools
#
# We'll build a **data analyst assistant** with three tools that analyze a customer dataset:
#
# | Tool | Purpose | Precondition |
# |------|---------|-------------|
# | `explore_data` | Inspect schema, missing values, candidate targets | None — safe first step |
# | `cluster_data` | Discover natural customer segments (unsupervised) | Needs numeric column names |
# | `classify_data` | Predict a label like churn (supervised) | Needs a valid target column |
#
# These tools have **natural dependencies** — you typically need to explore before you can cluster or classify. This is what makes tool calling interesting: the model must reason about *which tool to call next*.

# %%
from data_tools import (
    make_customer_data, init, explore_data, cluster_data, classify_data,
    TOOL_SCHEMAS, TOOLS,
)

df = make_customer_data()
init(df)
print(f"Dataset: {df.shape[0]} rows × {df.shape[1]} columns\n")
df.head(10)

# %%
# These are just Python functions — call them directly
result = explore_data(sample_rows=3)
print(json.dumps(result, indent=2))

# %%
# Cluster: discover segments
clusters = cluster_data(
    feature_columns=["age", "income", "monthly_spend", "visits_per_month", "support_tickets"],
    k=3,
)
print("=== Clustering ===")
print(json.dumps(clusters, indent=2))

# Classify: predict churn for a specific customer
classification = classify_data(
    target="churned",
    feature_columns=["age", "income", "monthly_spend", "visits_per_month", "support_tickets", "region"],
    new_row={
        "age": 29, "income": 42000, "monthly_spend": 180,
        "visits_per_month": 4, "support_tickets": 3, "region": "south",
    },
)
print("\n=== Classification ===")
print(json.dumps(classification, indent=2))

# %% [markdown]
# ## 2. Built-in Tools (Provider-Managed)
#
# LLM providers offer **ready-made tools** that the model can call and the provider executes on its infrastructure:
#
# | Provider | Built-in tools |
# |----------|---------------|
# | OpenAI | `web_search`, `code_interpreter`, `file_search` |
# | Anthropic | `computer_use`, `text_editor`, `bash` |
#
# With built-in tools, you write **zero tool code** — the provider handles everything. The model just decides when to use them.
#
# This uses OpenAI's **Responses API**, which supports both built-in and custom tools.

# %%
# Built-in tool: the provider executes it for you
# Uses the Responses API (different from Chat Completions used in earlier labs)
question = "What is the population of Trento, Italy, and whats the weather there?"

# 1) Current call (often shows citation refs like [ref_2003])
req = {
    "model": MODEL,
    # "tools": [{"type": "web_search_preview"}],
    "input": question,
}
resp = client.responses.create(**req)
print("\n=== Responses API + web_search_preview (default model) ===")
print("Request:")
print(json.dumps(req, indent=2))
print("Response:")
print(f"  id:    {getattr(resp, 'id', None)}")
print(f"  model: {getattr(resp, 'model', None)}")
print("\nOutput text:")
print(getattr(resp, "output_text", ""))

# %%
# 2) Same call, stronger model
req = {
    "model": MODEL_STRONG,
    # "tools": [{"type": "web_search_preview"}],
    "input": question,
}
resp = client.responses.create(**req)
print("\n=== Responses API + web_search_preview (strong model) ===")
print("Request:")
print(json.dumps(req, indent=2))
print("Response:")
print(f"  id:    {getattr(resp, 'id', None)}")
print(f"  model: {getattr(resp, 'model', None)}")
print("\nOutput text:")
print(getattr(resp, "output_text", ""))

# %%
# 3) Correct tool API: use the non-preview web search tool
req = {
    "model": MODEL_STRONG,
    "tools": [{"type": "web_search"}],
    "input": question,
}
print("\n=== Responses API + web_search (strong model) ===")
print("Request:")
print(json.dumps(req, indent=2))
try:
    resp = client.responses.create(**req)
    print("Response:")
    print(f"  id:    {getattr(resp, 'id', None)}")
    print(f"  model: {getattr(resp, 'model', None)}")
    print("\nOutput text:")
    print(getattr(resp, "output_text", ""))
except Exception as e:
    print("This tool config failed in this environment:")
    print(type(e).__name__, e)

# %% [markdown]
# Built-in tools are convenient but limited to what the provider offers. For domain-specific work — like analyzing *our* customer dataset — we need to register **our own functions** as tools.
#
# The rest of this lab uses the **Chat Completions API** (consistent with earlier labs) to build custom tool calling.

# %% [markdown]
# ## 3. Tool Calling Without API Support (DIY)
#
# Before providers added tool-calling primitives, the only option was:
# 1. Describe available tools in the **system prompt**
# 2. Ask the model to reply with **JSON** when it wants to call a tool
# 3. **Parse** the JSON yourself, execute the function, feed the result back
#
# Let's try this — it reveals the mechanism clearly.

# %%
from pathlib import Path
from jinja2 import Template

tool_list = json.dumps([s["function"] for s in TOOL_SCHEMAS], indent=2)
diy_prompt_text = Path("prompt_templates/tool_diy.j2").read_text()
template = Template(diy_prompt_text)

# %%
user_query = "What kind of data is in this dataset? Is any prediction possible?"

prompt = template.render(tool_list=tool_list, user_message=user_query)
print(prompt)

# %%
response = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": prompt}],
    temperature=0,
)

raw = response.choices[0].message.content
print(f"Raw model output:\n{raw}")

# %%
# Try to parse the structured reply
parsed = json.loads(raw)
print(f"Parsed: {json.dumps(parsed, indent=2)}")
print(f"\nReasoning: {parsed['reasoning']}")

if parsed["type"] == "tool_call":
    print(f"Action:    tool_call → {parsed['tool']}({parsed['args']})")

    fn = TOOLS[parsed["tool"]]
    result = fn(**parsed["args"])
    result_json = json.dumps(result)
    print(f"Result:    {result_json[:200]}...")


    # Feed result back so the model can answer
    prompt2 = template.render(tool_list=tool_list, user_message=user_query)
    response2 = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "user", "content": prompt2},
            {"role": "assistant", "content": raw},
            {"role": "user", "content": f"Tool result:\n{result_json}"},
        ],
        temperature=0,
    )
    print(f"\nAnswer:\n{response2.choices[0].message.content}")
else:
    print(f"Action:    answer")
    print(f"\nDirect answer:\n{parsed['content']}")

# %% [markdown]
# This works for simple cases, but it's **fragile**. The model might:
# - Wrap JSON in ` ```json ``` ` code blocks
# - Add conversational text before/after the JSON
# - Use different field names (`"function"` instead of `"tool"`)
# - Invent a format for multiple tool calls
##
# Provider APIs solve this with a **structured tool-calling protocol**: the model returns tool calls as structured objects, not text you have to parse.

# %% [markdown]
# ## 4. Registering Custom Tools — API Tool Calling
#
# Same idea, but now the API handles the structure. We register **tool schemas** and the model returns typed `tool_calls` objects instead of raw JSON text.
#
# The single-call round trip:
# 1. Send tool **schemas** + user message
# 2. Model returns a `tool_calls` object (structured, not text)
# 3. Your code **executes** the function
# 4. Send the result back as a `tool` message
# 5. Model produces the **final text answer**

# %%
# The schemas tell the model what tools exist and what arguments they accept
print(f"{len(TOOL_SCHEMAS)} tool schemas:\n")
for schema in TOOL_SCHEMAS:
    fn = schema["function"]
    print(f"  {fn['name']}")
    print(f"    {fn['description'][:80]}...")
    print(f"    params: {list(fn['parameters']['properties'].keys())}\n")

# %%
# Ask a question that needs one tool call
user_query = "What kind of data is in this dataset? Is churn prediction possible?"
print(f"User: {user_query}\n")

# Step 1: send query + tool schemas
response = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": user_query}],
    tools=TOOL_SCHEMAS,
    tool_choice="auto",
)

msg = response.choices[0].message

print(f"Role:         {msg.role}")
print(f"Content:      {msg.content}")
print(f"Tool calls:   {len(msg.tool_calls or [])} call(s)")
if msg.tool_calls:
    for tc in msg.tool_calls:
        print(f"  → {tc.function.name}({tc.function.arguments})")

# %%
# Step 2: model wants to call a tool
if msg.tool_calls:
    tc = msg.tool_calls[0]
    print(f"Model calls: {tc.function.name}({tc.function.arguments})")

    # Step 3: execute the tool
    args = json.loads(tc.function.arguments)
    result = json.dumps(TOOLS[tc.function.name](**args))
    print(f"Result: {result[:200]}...\n")

    # Step 4: send the result back
    response2 = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "user", "content": user_query},
            msg,
            {"role": "tool", "tool_call_id": tc.id, "content": result},
        ],
        tools=TOOL_SCHEMAS,
    )

    # Step 5: model answers in natural language
    print(f"Answer:\n{response2.choices[0].message.content}")
else:
    print(f"Model answered directly: {msg.content}")

# %% [markdown]
# ## 5. Stress Test — How Reliable Is DIY Tool Calling?
#
# Section 3 worked for one query at `temperature=0`. But how robust is it?
# Let's throw several queries at the DIY approach with `temperature=0.7` and see how often parsing succeeds.
#
# We also need a **forgiving parser** — models often wrap JSON in code blocks or add extra text.

# %%
def parse_tool_call(text):
    """Try to extract a JSON tool call from model output."""
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    if "```" in text:
        try:
            start = text.index("```") + 3
            if text[start:].startswith("json"):
                start += 4
            end = text.index("```", start)
            return json.loads(text[start:end].strip())
        except (json.JSONDecodeError, ValueError):
            pass
    return None

# %%
# Stress test: how often does manual parsing succeed?
test_queries = [
    "What kind of data is this?",
    "Are there natural customer segments?",
    "Will a young low-income customer with many support tickets churn?",
    "Explore the data and then find clusters.",
    "Compare clustering with 2 vs 4 groups.",
]

for model_name in [MODEL, MODEL_STRONG]:
    print(f"\n{'='*50}")
    print(f"Model: {model_name}, temperature=0.7")
    print(f"{'='*50}")
    ok, fail = 0, 0
    for q in test_queries:
        prompt = template.render(tool_list=tool_list, user_message=q)
        r = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        raw = r.choices[0].message.content
        parsed = parse_tool_call(raw)
        if parsed and parsed.get("type") == "tool_call":
            ok += 1
            print(f"  [OK]   {q[:45]}")
        else:
            fail += 1
            print(f"  [FAIL] {q[:45]}")
            print(f"         → {raw[:100]}")
    print(f"  Score: {ok}/{ok + fail}")

# %% [markdown]
# **Common failures** with the manual approach:
# - Model wraps JSON in ` ```json ``` ` code blocks
# - Model adds conversational text before/after the JSON
# - Model uses different field names (`"function"` instead of `"tool"`)
# - Model tries to call multiple tools but invents a format
# - Model hallucinates tool names that don't exist
#
# | Approach | Strengths | Weaknesses |
# |----------|-----------|------------|
# | Manual JSON | Transparent, provider-agnostic | Brittle, needs repair code |
# | API tool calling | Reliable structure, multi-tool support | Tied to provider conventions |
#
# **Takeaway:** Manual parsing works for teaching. API tool calling is what you use in production.

# %% [markdown]
# ## 6. The Multi-Tool Loop
#
# Real questions often need **multiple tool calls** before the model can answer:
#
# ```
# while has_budget:
#     response = LLM(messages, tools)
#     if response has tool_calls:
#         execute each tool, append results
#     else:
#         return response.text  # model decided it's done
# ```
#
# Two critical design choices:
# 1. **Max iterations** — prevent infinite loops
# 2. **The model decides when to stop** — it produces text (not a tool call) when it has enough info

# %%
system_prompt_text = Path("prompt_templates/tool_system.j2").read_text()
system_template = Template(system_prompt_text)
system_prompt = system_template.render(tool_list=tool_list, clarification_mode=False)

def tool_loop(user_message, model=MODEL, max_iterations=10):
    """Run a tool-calling loop until the model produces a text answer."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    for i in range(1, max_iterations + 1):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            print(f"  Iteration {i}: FINAL ANSWER")
            return msg.content

        print(f"  Iteration {i}: {len(msg.tool_calls)} tool call(s)")
        messages.append(msg)

        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            print(f"    → {tc.function.name}({json.dumps(args)[:100]})")
            result = json.dumps(TOOLS[tc.function.name](**args))
            print(f"      Result: {result[:120]}...")
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    return "[Max iterations reached]"


print("tool_loop() ready.")

# %%
# Simple: one tool call, then answer
print("=" * 60)
print("Query: What kind of data is this?")
print("=" * 60)

answer = tool_loop("What kind of data is in this dataset? Is churn prediction possible?")
print(f"\nAnswer:\n{answer}")

# %%
# Complex: the model chains multiple tools automatically
print("=" * 60)
print("Query: Segments + churn prediction")
print("=" * 60)

answer = tool_loop(
    "Analyze this customer dataset. Are there natural segments? "
    "Also, predict whether this customer will churn: "
    "age=29, income=42000, monthly_spend=180, visits_per_month=4, "
    "support_tickets=3, region=south."
)
print(f"\nAnswer:\n{answer}")

# %% [markdown]
# ## 7. When to Stop (The Control Problem)
#
# > Specialized APIs solve the **syntax** of tool calling. The hard part is the **control policy**.
#
# After each tool result, continue only if **all three** are true:
# 1. Some part of the original goal is still **unresolved**
# 2. Another available tool can **resolve** it
# 3. The next tool call is **necessary**, not merely interesting
#
# ### Common failure modes
# - **Tool obsession**: calling tools because they exist, not because they're needed
# - **Skipping preconditions**: classifying before checking that a label exists
# - **Looping without gain**: repeating nearly identical calls
# - **No termination**: never deciding the answer is good enough
#
# Different queries should lead to **different tool sequences**:

# %%
# Different queries → different tool traces
queries = [
    ("Exploration only",
     "What kind of data is in this file? Is churn prediction even possible?"),
    ("Segmentation",
     "Are there natural customer segments in this dataset?"),
    ("Classification",
     "Will a customer with age=29, income=42k, spend=180, visits=4, tickets=3, region=south churn?"),
    ("Compound request",
     "Find customer segments AND predict churn for: age=29, income=42k, spend=180, visits=4, tickets=3, region=south."),
]

for label, q in queries:
    print(f"\n{'='*60}")
    print(f"[{label}] {q[:70]}...")
    print(f"{'='*60}")
    answer = tool_loop(q)
    print(f"\nAnswer: {answer[:200]}{'...' if len(answer) > 200 else ''}")

# %%
# What happens when preconditions aren't met?
# Remove the churned column — classification should fail gracefully
init(df.drop(columns=["churned"]))

print("=== Dataset WITHOUT a target label ===")
print("Query: Will this customer churn?\n")

answer = tool_loop("Will a customer with age=29, income=42k churn?")
print(f"\nAnswer:\n{answer}")

# Restore the full dataset
init(df)

# %%
# Model comparison: how do different models handle the same compound query?
compound_q = (
    "Find customer segments AND predict churn for: "
    "age=29, income=42k, spend=180, visits=4, tickets=3, region=south."
)

for model_name in [MODEL, MODEL_STRONG]:
    print(f"\n{'='*60}")
    print(f"Model: {model_name}")
    print(f"{'='*60}")
    answer = tool_loop(compound_q, model=model_name)
    print(f"\nAnswer: {answer[:300]}{'...' if len(answer) > 300 else ''}")

# %% [markdown]
# ## 8. Stopping for User Input
#
# What if the model doesn't have enough information to decide which tool to call?
#
# Instead of guessing, it can **ask the user for clarification**. This is just a system prompt instruction — the model chooses to produce text (a question) instead of a tool call.
#
# The model has three options at each step:
# 1. **Call a tool** — if it knows which tool and has all parameters
# 2. **Ask a question** — if information is missing or ambiguous
# 3. **Answer directly** — if it already has enough information

# %%
# Without clarification instructions — model guesses
system_no_clarify = system_template.render(tool_list=tool_list, clarification_mode=False)

vague_queries = [
    "Find some clusters.",
    "Predict something.",
    "Analyze the data.",
]

print("=== WITHOUT clarification instructions ===")
for q in vague_queries:
    print(f"\nUser: {q}")
    r = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_no_clarify},
            {"role": "user", "content": q},
        ],
        tools=TOOL_SCHEMAS,
        tool_choice="auto",
    )
    msg = r.choices[0].message
    if msg.tool_calls:
        tc = msg.tool_calls[0]
        print(f"  → GUESSED: {tc.function.name}({tc.function.arguments})")
    else:
        print(f"  → Responded: {msg.content[:150]}")

# %%
# With clarification instructions — model asks instead of guessing
system_with_clarify = system_template.render(tool_list=tool_list, clarification_mode=True)

print("=== WITH clarification instructions ===")
for q in vague_queries:
    print(f"\nUser: {q}")
    r = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_with_clarify},
            {"role": "user", "content": q},
        ],
        tools=TOOL_SCHEMAS,
        tool_choice="auto",
    )
    msg = r.choices[0].message
    if msg.tool_calls:
        tc = msg.tool_calls[0]
        print(f"  → GUESSED: {tc.function.name}({tc.function.arguments})")
    else:
        print(f"  → ASKED: {msg.content[:200]}")

# %%
# Full conversation: vague → clarify → user answers → tool calls → answer
print("=" * 60)
print("Full clarification conversation")
print("=" * 60)

messages = [
    {"role": "system", "content": system_with_clarify},
    {"role": "user", "content": "Predict something for a customer."},
]

# Turn 1: model asks for details
r1 = client.chat.completions.create(
    model=MODEL, messages=messages, tools=TOOL_SCHEMAS, tool_choice="auto",
)
msg1 = r1.choices[0].message
print(f"\nUser: Predict something for a customer.")
print(f"Assistant: {msg1.content}")

# Turn 2: user provides the missing info
messages.append(msg1)
messages.append({
    "role": "user",
    "content": (
        "Predict churn. The customer is age=29, income=42000, "
        "spend=180, visits=4, tickets=3, region=south."
    ),
})
print(f"\nUser: Predict churn. Customer: age=29, income=42k, ...")

# Continue with tool loop from here
while True:
    r = client.chat.completions.create(
        model=MODEL, messages=messages, tools=TOOL_SCHEMAS, tool_choice="auto",
    )
    msg = r.choices[0].message

    if not msg.tool_calls:
        print(f"\nAssistant: {msg.content}")
        break

    messages.append(msg)
    for tc in msg.tool_calls:
        args = json.loads(tc.function.arguments)
        print(f"  → Calls: {tc.function.name}({json.dumps(args)[:80]})")
        result = json.dumps(TOOLS[tc.function.name](**args))
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

# %% [markdown]
# **Key insight:** Asking back is itself a "tool" — the model's ability to produce text is its most flexible capability. A tool call requires exact parameters; a clarification question can handle any ambiguity.

# %% [markdown]
# ## 9. Tool Naming & Documentation Matter
#
# The model picks tools based on their **name**, **description**, and **parameter names**. What happens when these are bad?
#
# `data_tools_bad.py` has the same three functions and same logic, but:
# - Vague names: `run_check`, `process_data`, `get_result`
# - Minimal descriptions: *"Checks the data."*, *"Processes the data."*, *"Gets the result."*
# - Cryptic parameters: `n`, `cols`, `num`, `col`, `row`

# %%
import data_tools_bad

data_tools_bad.init(df)
bad_schemas = data_tools_bad.TOOL_SCHEMAS

# Compare schemas side by side
print("=== GOOD schema (explore_data) ===")
print(json.dumps(TOOL_SCHEMAS[0], indent=2))
print("\n=== BAD schema (run_check) ===")
print(json.dumps(bad_schemas[0], indent=2))

# Test both on the same queries
test_queries = [
    "What columns does this dataset have?",
    "Are there natural customer groups?",
    "Will this customer churn? age=29, income=42000",
]
expected_good = ["explore_data", "cluster_data", "classify_data"]
expected_bad = ["run_check", "process_data", "get_result"]

for label, schemas, expected in [
    ("GOOD tools", TOOL_SCHEMAS, expected_good),
    ("BAD tools", bad_schemas, expected_bad),
]:
    print(f"\n{'='*50}")
    print(f"{label}")
    print(f"{'='*50}")
    correct = 0
    for q, exp in zip(test_queries, expected):
        r = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": q}],
            tools=schemas,
            tool_choice="auto",
        )
        msg = r.choices[0].message
        if msg.tool_calls:
            called = msg.tool_calls[0].function.name
            ok = called == exp
            correct += ok
            print(f"  [{'OK' if ok else 'WRONG'}] {q[:45]}")
            print(f"         Called: {called}, Expected: {exp}")
        else:
            print(f"  [MISS] {q[:45]} — no tool called")
    print(f"  Score: {correct}/{len(test_queries)}")

# %% [markdown]
# ### Best practices for tool definitions
#
# | Practice | Why |
# |----------|-----|
# | **Descriptive function names** | `explore_data` vs `run_check` — model matches intent to name |
# | **Parameter names that explain themselves** | `feature_columns` vs `cols` — model maps user concepts to params |
# | **Rich descriptions with preconditions** | *"Call explore_data first if unsure"* guides the tool sequence |
# | **Type constraints** | `k: integer (2-10)` prevents invalid values |
# | **Consistent naming patterns** | If tools follow a convention, the model learns it |

# %% [markdown]
# ## Takeaways
#
# 1. **Tool calling turns an LLM into a controller** of external capabilities
# 2. **Provider APIs** give you reliable structure (no more parsing JSON from text)
# 3. **The real challenge is the loop**: when to call another tool, when to stop, when to ask the user
# 4. **Preconditions matter**: explore first, then decide which tools are valid
# 5. **Good tool names and descriptions** directly impact model accuracy
# 6. **Asking for clarification** is itself a powerful capability — the model's most flexible "tool"
#
# > The key design challenge is not how to call tools, but how to decide when the job is finished.
