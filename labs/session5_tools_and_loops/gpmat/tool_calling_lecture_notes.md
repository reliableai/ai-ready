# Tool Calling: Lecture Notes, Reading, and Code Examples

Prepared for an AI Design class  
Date: March 16, 2026

## What this handout is for

This lesson is designed to help students understand that **tool calling is not only an output format problem**. It is also a **control problem**:

1. How does the model request a tool?
2. How does the system decide whether to call another tool or stop?

The notes below cover both:
- **provider-native / specialized tool-calling APIs**,
- **tool calling "by hand"** with your own prompt-and-parser protocol,
- and the **interaction loop** using a running example with:
  - `explore_data`
  - `cluster_data`
  - `classify_data`

---

## Suggested learning objectives

By the end of the lesson, students should be able to:

- explain what tool calling is and why LLM systems use it,
- distinguish between **provider-native tool calling** and **hand-rolled tool calling**,
- explain the **observe -> decide -> act -> observe** loop,
- identify when a system should call another tool versus when it is done,
- design tool descriptions with useful inputs, outputs, and preconditions,
- analyze a multi-tool workflow using exploration, clustering, and classification.

---

## Suggested 75–90 minute class plan

### Part 1 — Motivation (10 min)
Why use tools at all?

- LLMs are good at language and flexible planning.
- They are not always reliable for:
  - exact computation,
  - accessing current or private data,
  - deterministic actions,
  - structured database operations.

Tool calling lets the model **delegate** parts of a task to systems that are better suited for them.

### Part 2 — Vocabulary and mental model (10 min)

Key terms:

- **Tool**: any external capability the model can invoke.
- **Function tool**: a tool with a structured schema, often JSON-schema-like.
- **Built-in tool**: a tool the provider executes for you, such as web search or file search.
- **Client-side tool**: a tool your application executes after the model requests it.
- **Server-side tool**: a tool the provider executes on its own infrastructure.
- **Observation**: the result returned by a tool.
- **Controller**: the part of the system that decides what happens next.
- **Loop / orchestration loop**: the repeated cycle of model decision, tool execution, and result integration.
- **Termination condition**: the rule for deciding the system is done.

### Part 3 — Two implementation styles (15–20 min)

1. **Specialized tool-calling APIs**
2. **Tool calling by hand**

### Part 4 — The interaction loop (15 min)

After every tool result, the system must answer:

- Is the user’s original question already answered?
- Is another tool needed?
- Would another tool materially improve the answer?

### Part 5 — Running example: data analyst agent (15–20 min)

Three tools:
- `explore_data`
- `cluster_data`
- `classify_data`

### Part 6 — Code walkthrough or live demo (10–15 min)

Use either:
- the **manual JSON protocol** example, or
- the **provider-native function calling** example.

---

## 1. What tool calling is

Tool calling is a pattern where the model can request an external capability instead of answering purely from text.

A minimal cycle looks like this:

1. The user asks a question.
2. The model decides a tool is useful.
3. The application executes the tool.
4. The tool result is returned to the model.
5. The model either:
   - gives a final answer, or
   - asks for another tool.

This is the core idea behind modern agentic systems.

---

## 2. Specialized APIs vs tool calling by hand

## 2.1 Specialized / provider-native tool calling

With a provider-native API, the model does not have to "fake" tool calls in plain text.  
Instead, the provider gives you a structured interface for declaring tools and receiving tool-call objects.

### What these APIs usually provide

- tool schemas,
- validation-friendly argument structures,
- typed tool call outputs,
- support for multiple tool calls,
- integration with built-in tools,
- fewer parsing failures than plain text protocols.

### What they do **not** solve automatically

They do **not** solve the full agent design problem:

- Which tool should be called first?
- Should the system call another tool?
- When should the loop stop?
- How should failures and retries work?
- How should ambiguous user requests be decomposed?

That is why it is useful to teach tool calling as a **controller problem**, not just a syntax problem.

### Current ecosystem notes

- OpenAI’s current guidance for tool calling centers on the **Responses API**. Its tools guide covers built-in tools, function calling, tool search, and remote MCP servers. OpenAI’s docs also note that the older Assistants API has been deprecated and is scheduled to shut down on **August 26, 2026**.  
  Reading: [OpenAI Function Calling Guide](https://developers.openai.com/api/docs/guides/function-calling/), [OpenAI Tools Guide](https://developers.openai.com/api/docs/guides/tools/), [Migrate to the Responses API](https://developers.openai.com/api/docs/guides/migrate-to-responses/), [Assistants Function Calling (deprecation note)](https://developers.openai.com/api/docs/assistants/tools/function-calling/)

- Anthropic documents two broad tool categories: **client tools** that execute on your systems and **server tools** that execute on Anthropic’s infrastructure. Their docs also show a loop where the model emits tool-use requests and your app returns `tool_result` content blocks.  
  Reading: [Anthropic Tool Use Overview](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview), [How to implement tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use)

- The **Model Context Protocol (MCP)** is an open protocol for connecting AI systems to tools and context. The current MCP specification describes JSON-RPC 2.0 communication and the roles of hosts, clients, and servers. OpenAI’s Apps SDK quickstart also explains that ChatGPT apps use MCP to connect an app’s capabilities to ChatGPT.  
  Reading: [MCP Specification](https://modelcontextprotocol.io/specification/2025-11-25), [OpenAI Apps SDK Quickstart](https://developers.openai.com/apps-sdk/quickstart/), [OpenAI MCP guide](https://developers.openai.com/api/docs/mcp/)

## 2.2 Tool calling by hand

Tool calling "by hand" means you define your **own protocol** in the prompt and in your application code.

For example, you may instruct the model:

> Return exactly one JSON object.  
> Either:
> - `{"type":"tool","name":"cluster_data","args":{...}}`
> - or `{"type":"final","answer":"..."}`

Your application then:

1. parses the JSON,
2. validates the request,
3. runs the tool,
4. appends the tool result to history,
5. asks the model again.

### Why teach this version?

Because students can clearly see the mechanism:

- the model is acting like a controller,
- the application is the runtime,
- the protocol is explicit,
- and the stop condition must be designed.

### Trade-offs

| Approach | Strengths | Weaknesses | Good for |
|---|---|---|---|
| Provider-native tool calling | Reliable structure, less parsing overhead, built-in tools | Still needs orchestration logic; tied to provider conventions | Production systems, multi-tool apps |
| Tool calling by hand | Easy to understand, provider-agnostic, transparent | More brittle, more validation code, easier to break | Teaching, experiments, custom runtimes |

---

## 3. The interaction loop

A useful teaching phrase is:

> Specialized APIs mostly solve the **syntax** of tool calling.  
> The hard part is the **control policy**.

A generic interaction loop:

```python
history = []
state = {}

while True:
    decision = controller(user_goal, history, state)

    if decision["type"] == "final":
        return decision["answer"]

    result = run_tool(decision["name"], decision["args"])
    history.append({"tool": decision["name"], "args": decision["args"], "result": result})
```

That code is simple, but the real question is: **what should `controller(...)` do?**

### A practical continue/stop rule

After each tool result, continue only if all three are true:

1. some part of the original user goal is still unresolved,
2. another available tool can resolve it,
3. the next tool call is **necessary**, not merely interesting.

Stop when any of these is true:

- the original question has been answered well enough,
- no available tool can reduce the remaining uncertainty,
- another tool call would not materially change the answer,
- the preconditions for the next tool are not met.

### Important teaching point

Students often assume the system should keep calling tools until it has exhausted all possibilities.

That is usually wrong.

The correct question is not:

> "Can I call another tool?"

It is:

> "Do I need another tool to answer the user’s actual question?"

### Common failure modes

- **Tool obsession**: calling tools because they exist, not because they are needed.
- **Skipping preconditions**: trying classification before checking that a label exists.
- **Looping without gain**: repeating nearly identical calls that do not change the answer.
- **Tool ambiguity**: overlapping tools with unclear boundaries.
- **No termination rule**: the agent never decides it has enough evidence.
- **Bad tool descriptions**: the model cannot tell when a tool is appropriate.

---

## 4. Running example: a data analyst assistant

This example works well in class because the tools naturally represent different kinds of questions.

### Dataset idea

Use a customer table such as:

- `age`
- `income`
- `monthly_spend`
- `visits_per_month`
- `support_tickets`
- `region`
- `churned`

### The three tools

| Tool | Purpose | Typical user question | Preconditions | Output |
|---|---|---|---|---|
| `explore_data` | Inspect schema and data quality | "What kind of data is this?" | Dataset exists | column types, missingness, candidate targets, suggested features |
| `cluster_data` | Discover natural groups | "Are there customer segments?" | Suitable features are known, usually numeric | number of clusters, cluster sizes, profiles, silhouette score |
| `classify_data` | Predict a known label | "Will this customer churn?" | A target label exists and training data is available | metrics, class prediction, confidence, feature importance |

### Why this trio is pedagogically strong

Because the tools have different roles:

- `explore_data` is about **problem framing**,
- `cluster_data` is **unsupervised**,
- `classify_data` is **supervised**.

This makes it easy to discuss tool **preconditions**.

For example:

- clustering does **not** require a label,
- classification **does** require a label,
- exploration is often the right first step when the schema is unknown.

### A good teaching sentence

> Exploration reduces uncertainty about which of the other tools is even valid.

---

## 5. Example tool definitions students can critique

This is not tied to any one provider. It is just a clear specification.

```json
[
  {
    "name": "explore_data",
    "description": "Inspect the dataset schema, missing values, basic column types, and candidate target columns.",
    "inputs": {
      "sample_rows": "optional integer"
    },
    "returns": {
      "n_rows": "integer",
      "columns": "list",
      "numeric_columns": "list",
      "categorical_columns": "list",
      "missing_values": "object",
      "candidate_targets": "list"
    }
  },
  {
    "name": "cluster_data",
    "description": "Run clustering on numeric feature columns to discover natural groups.",
    "inputs": {
      "feature_columns": "list of strings",
      "k": "integer or 'auto'"
    },
    "returns": {
      "k": "integer",
      "cluster_sizes": "object",
      "profiles": "object",
      "silhouette_score": "number"
    }
  },
  {
    "name": "classify_data",
    "description": "Train a supervised classifier to predict a target label and optionally score a new row.",
    "inputs": {
      "target": "string",
      "feature_columns": "list of strings",
      "new_row": "optional object"
    },
    "returns": {
      "metrics": "object",
      "prediction": "optional object",
      "important_features": "list"
    }
  }
]
```

### Questions to ask students

- Is `cluster_data` allowed to infer `k`, or must the user provide it?
- Should `classify_data` refuse to run if the target is missing or non-binary?
- Should `explore_data` return a recommended next tool?
- How much of the tool policy should live in tool descriptions versus the controller prompt?

---

## 6. Example traces: when do we stop?

## Trace A — exploration only

**User**:  
> "What kind of data is in this file, and is churn prediction even possible?"

A good controller should do this:

1. call `explore_data`
2. inspect the result
3. answer the question

### Why stop here?

Because the user did **not** ask for a trained predictor or a churn prediction for a person.
They asked whether prediction is possible.

If `explore_data` reveals a `churned` column, the agent can answer:
- yes, supervised prediction appears possible.

If no label exists, the agent can answer:
- not with supervised classification as currently defined.

Either way, **stop**.

## Trace B — clustering

**User**:  
> "Are there natural customer segments in this dataset?"

A good controller:

1. calls `explore_data` to identify numeric candidate features,
2. calls `cluster_data`,
3. returns a segmentation answer.

### Why this is a good example

Because the system needs at least two steps:
- first determine how to represent the data,
- then perform clustering.

### When to stop

If the question is simply whether segments exist, stop after clustering and explanation.

Do **not** keep exploring endlessly unless:
- the cluster result is ambiguous and another tool would meaningfully help, or
- the user explicitly asked for more detail.

## Trace C — classification

**User**:  
> "Will this new customer churn?"

A good controller:

1. calls `explore_data`,
2. verifies that a target such as `churned` exists,
3. calls `classify_data`,
4. returns the prediction plus model quality.

### Important negative case

If there is no label column:
- the correct answer is not to keep trying tools,
- the correct answer is to stop and explain that classification is not currently supported by the available data.

## Trace D — compound request

**User**:  
> "Analyze this customer dataset. Are there natural segments, and is this new customer likely to churn?"

A good controller:

1. calls `explore_data`,
2. calls `cluster_data`,
3. calls `classify_data`,
4. gives one final answer covering both subgoals.

### Teaching point

This trace shows that the controller should track **multiple unresolved subgoals**.

The loop ends only when both are complete.

---

## 7. Code Example A — local tools on a toy customer dataset

This example is intentionally small and classroom-friendly.  
It shows what the **tools themselves** might look like.

```python
from __future__ import annotations

import numpy as np
import pandas as pd

from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, roc_auc_score, silhouette_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def make_customer_data(n: int = 450, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    segments = rng.choice(
        ["price_sensitive", "routine", "premium"],
        size=n,
        p=[0.35, 0.40, 0.25],
    )

    rows = []
    for seg in segments:
        if seg == "price_sensitive":
            age = rng.normal(28, 6)
            income = rng.normal(45_000, 9_000)
            monthly_spend = rng.normal(220, 70)
            visits_per_month = rng.normal(6, 2)
            support_tickets = rng.poisson(2.2)
        elif seg == "routine":
            age = rng.normal(41, 8)
            income = rng.normal(68_000, 12_000)
            monthly_spend = rng.normal(480, 110)
            visits_per_month = rng.normal(9, 2.5)
            support_tickets = rng.poisson(1.2)
        else:
            age = rng.normal(36, 7)
            income = rng.normal(110_000, 16_000)
            monthly_spend = rng.normal(950, 180)
            visits_per_month = rng.normal(14, 3)
            support_tickets = rng.poisson(0.6)

        region = rng.choice(["north", "south", "east", "west"])

        # Synthetic churn probability:
        # more support tickets, lower spend, and fewer visits increase churn
        logit = (
            -1.6
            + 0.65 * (seg == "price_sensitive")
            + 0.22 * support_tickets
            - 0.0025 * monthly_spend
            - 0.06 * visits_per_month
            + 0.00001 * (50_000 - income)
        )
        p_churn = 1.0 / (1.0 + np.exp(-logit))
        p_churn = float(np.clip(p_churn, 0.02, 0.95))
        churned = int(rng.random() < p_churn)

        rows.append(
            {
                "age": max(18, round(age, 1)),
                "income": max(15_000, round(income, 0)),
                "monthly_spend": max(20, round(monthly_spend, 1)),
                "visits_per_month": max(0, round(visits_per_month, 1)),
                "support_tickets": int(support_tickets),
                "region": region,
                "latent_segment": seg,   # hidden in real life, useful in teaching
                "churned": churned,
            }
        )

    df = pd.DataFrame(rows)

    # Add a little missingness for exploration to notice
    missing_idx = rng.choice(df.index, size=max(5, n // 30), replace=False)
    df.loc[missing_idx[: len(missing_idx)//2], "income"] = np.nan
    df.loc[missing_idx[len(missing_idx)//2 :], "monthly_spend"] = np.nan
    return df


def explore_data(df: pd.DataFrame, sample_rows: int = 5) -> dict:
    numeric_columns = df.select_dtypes(include="number").columns.tolist()
    categorical_columns = df.select_dtypes(exclude="number").columns.tolist()

    candidate_targets = []
    for col in df.columns:
        unique_non_null = df[col].dropna().nunique()
        lower = col.lower()
        if lower in {"label", "target", "class", "outcome", "churned"}:
            candidate_targets.append(col)
        elif unique_non_null <= 5 and col not in {"region", "latent_segment"}:
            candidate_targets.append(col)

    return {
        "n_rows": int(len(df)),
        "columns": df.columns.tolist(),
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "missing_values": df.isna().sum().to_dict(),
        "candidate_targets": candidate_targets,
        "sample": df.head(sample_rows).to_dict(orient="records"),
    }


def cluster_data(df: pd.DataFrame, feature_columns: list[str], k: int = 3) -> dict:
    X = df[feature_columns].copy()
    X = X.select_dtypes(include="number")

    prep = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    X_proc = prep.fit_transform(X)

    model = KMeans(n_clusters=k, n_init=10, random_state=0)
    cluster_labels = model.fit_predict(X_proc)

    with_clusters = df.copy()
    with_clusters["cluster"] = cluster_labels

    profiles = (
        with_clusters.groupby("cluster")[feature_columns]
        .mean(numeric_only=True)
        .round(2)
        .to_dict(orient="index")
    )

    sizes = with_clusters["cluster"].value_counts().sort_index().to_dict()
    score = float(silhouette_score(X_proc, cluster_labels))

    return {
        "k": k,
        "cluster_sizes": sizes,
        "profiles": profiles,
        "silhouette_score": round(score, 3),
    }


def classify_data(
    df: pd.DataFrame,
    target: str,
    feature_columns: list[str],
    new_row: dict | None = None,
) -> dict:
    if target not in df.columns:
        raise ValueError(f"Target column '{target}' not found.")

    y = df[target]
    X = pd.get_dummies(df[feature_columns], drop_first=True)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=0, stratify=y
    )

    model = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("clf", RandomForestClassifier(n_estimators=200, random_state=0)),
        ]
    )
    model.fit(X_train, y_train)

    proba = model.predict_proba(X_test)[:, 1]
    pred = (proba >= 0.5).astype(int)

    result = {
        "metrics": {
            "accuracy": round(float(accuracy_score(y_test, pred)), 3),
            "roc_auc": round(float(roc_auc_score(y_test, proba)), 3),
        }
    }

    clf = model.named_steps["clf"]
    importances = pd.Series(clf.feature_importances_, index=X.columns).sort_values(ascending=False)
    result["important_features"] = importances.head(5).round(4).to_dict()

    if new_row is not None:
        row = pd.DataFrame([new_row])
        row = pd.get_dummies(row, drop_first=True)
        row = row.reindex(columns=X.columns, fill_value=0)
        row_proba = float(model.predict_proba(row)[0, 1])
        row_pred = int(row_proba >= 0.5)
        result["prediction"] = {
            "predicted_class": row_pred,
            "probability_of_positive_class": round(row_proba, 3),
        }

    return result


# Example usage
df = make_customer_data()

print(explore_data(df))

print(
    cluster_data(
        df,
        feature_columns=[
            "age",
            "income",
            "monthly_spend",
            "visits_per_month",
            "support_tickets",
        ],
        k=3,
    )
)

print(
    classify_data(
        df,
        target="churned",
        feature_columns=[
            "age",
            "income",
            "monthly_spend",
            "visits_per_month",
            "support_tickets",
            "region",
        ],
        new_row={
            "age": 29,
            "income": 42000,
            "monthly_spend": 180,
            "visits_per_month": 4,
            "support_tickets": 3,
            "region": "south",
        },
    )
)
```

### What to emphasize in class

The point of this example is **not** that these are the best clustering or classification choices.

The point is that the tools have distinct roles and preconditions:

- `explore_data` discovers what is possible,
- `cluster_data` groups without labels,
- `classify_data` predicts a known label.

---

## 8. Code Example B — tool calling by hand

This version uses a **manual JSON protocol**.  
The model is asked to return one of two things:

- a tool request, or
- a final answer.

This is the simplest way to show students the mechanism.

```python
import json
from openai import OpenAI

client = OpenAI()

TOOLS = {
    "explore_data": lambda args: explore_data(df, **args),
    "cluster_data": lambda args: cluster_data(df, **args),
    "classify_data": lambda args: classify_data(df, **args),
}

CONTROLLER_PROMPT = """
You are the controller for a data-analysis assistant.

You may return exactly one JSON object of one of these forms:

{"type":"tool","name":"explore_data","args":{"sample_rows":5}}
{"type":"tool","name":"cluster_data","args":{"feature_columns":["age","income","monthly_spend","visits_per_month","support_tickets"],"k":3}}
{"type":"tool","name":"classify_data","args":{"target":"churned","feature_columns":["age","income","monthly_spend","visits_per_month","support_tickets","region"],"new_row":{"age":29,"income":42000,"monthly_spend":180,"visits_per_month":4,"support_tickets":3,"region":"south"}}}
{"type":"final","answer":"..."}

Rules:
- If the schema or label availability is unknown, call explore_data first.
- Use cluster_data for segmentation questions.
- Use classify_data only when a suitable target label exists.
- Call at most one tool per turn.
- Stop as soon as the user's original question has been answered well enough.
- Output JSON only and nothing else.
""".strip()


def call_controller(history: list[dict]) -> dict:
    response = client.responses.create(
        model="gpt-5",
        input=[
            {"role": "system", "content": CONTROLLER_PROMPT},
            *history,
        ],
    )
    text = response.output_text.strip()
    return json.loads(text)


history = [
    {
        "role": "user",
        "content": (
            "Analyze this customer dataset. Are there natural segments, "
            "and is this new customer likely to churn?\n"
            "New customer: age=29, income=42000, monthly_spend=180, "
            "visits_per_month=4, support_tickets=3, region=south"
        ),
    }
]

for step in range(8):
    decision = call_controller(history)

    if decision["type"] == "final":
        print("FINAL ANSWER")
        print(decision["answer"])
        break

    tool_name = decision["name"]
    args = decision["args"]

    if tool_name not in TOOLS:
        raise ValueError(f"Unknown tool requested: {tool_name}")

    result = TOOLS[tool_name](args)

    history.append(
        {
            "role": "assistant",
            "content": json.dumps(decision),
        }
    )
    history.append(
        {
            "role": "user",
            "content": f"TOOL_RESULT {tool_name}: {json.dumps(result)}",
        }
    )
else:
    raise RuntimeError("Controller exceeded max steps.")
```

### Why this is useful for teaching

Students can now see the exact separation between:

- **the model’s decision**,
- **the application’s tool execution**,
- **the returned observation**,
- **the stop condition**.

### Weaknesses of the manual approach

- malformed JSON,
- invented tool names,
- missing arguments,
- weaker validation,
- more repair code.

That is exactly why provider-native APIs exist.

---

## 9. Code Example C — provider-native tool calling with the OpenAI Responses API

This version uses the current OpenAI tool-calling pattern from the Responses API documentation.  
The basic loop is:

1. send the user request and tool definitions,
2. receive one or more `function_call` items,
3. execute them in your application,
4. send back `function_call_output`,
5. repeat until the model returns a message instead of more tool calls.

```python
import json
from openai import OpenAI

client = OpenAI()

tools = [
    {
        "type": "function",
        "name": "explore_data",
        "description": "Inspect the dataset schema, missing values, and candidate target columns.",
        "parameters": {
            "type": "object",
            "properties": {
                "sample_rows": {"type": "integer", "minimum": 1, "maximum": 10}
            },
            "required": [],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "cluster_data",
        "description": "Cluster numeric feature columns to discover natural groups.",
        "parameters": {
            "type": "object",
            "properties": {
                "feature_columns": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "k": {"type": "integer", "minimum": 2, "maximum": 10},
            },
            "required": ["feature_columns", "k"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "classify_data",
        "description": "Train a classifier for a target label and optionally score a new row.",
        "parameters": {
            "type": "object",
            "properties": {
                "target": {"type": "string"},
                "feature_columns": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "new_row": {"type": "object"},
            },
            "required": ["target", "feature_columns"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]

tool_map = {
    "explore_data": lambda args: explore_data(df, **args),
    "cluster_data": lambda args: cluster_data(df, **args),
    "classify_data": lambda args: classify_data(df, **args),
}

input_items = [
    {
        "role": "user",
        "content": (
            "Analyze this customer dataset. Are there natural segments, "
            "and is this new customer likely to churn?\n"
            "New customer: age=29, income=42000, monthly_spend=180, "
            "visits_per_month=4, support_tickets=3, region=south"
        ),
    }
]

while True:
    response = client.responses.create(
        model="gpt-5",
        input=input_items,
        tools=tools,
    )

    # Keep the model's output in the conversation state
    input_items += response.output

    function_calls = [item for item in response.output if item.type == "function_call"]

    if not function_calls:
        print("FINAL ANSWER")
        print(response.output_text)
        break

    for call in function_calls:
        args = json.loads(call.arguments)
        result = tool_map[call.name](args)

        input_items.append(
            {
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": json.dumps(result),
            }
        )
```

### What this example demonstrates

- the model is no longer forced to emit fake JSON in plain text,
- tool calls come back as typed response items,
- your application still owns tool execution,
- **you still need the loop**.

### Instructor note

This is the perfect moment to stress:

> Native tool calling gives you better plumbing.  
> It does not eliminate the orchestration problem.

---

## 10. Optional comparison snippet — Anthropic tool use

Anthropic’s docs use a similar concept with different message shapes and terms.  
A simplified sketch:

```python
from anthropic import Anthropic

client = Anthropic()

response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=1024,
    tools=[
        {
            "name": "explore_data",
            "description": "Inspect the dataset schema and candidate target columns.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "sample_rows": {"type": "integer"}
                },
                "required": []
            }
        }
    ],
    messages=[
        {
            "role": "user",
            "content": "What kind of data is in this file, and is churn prediction possible?"
        }
    ],
)

# If Claude decides to use a client tool, the response indicates tool use.
# Your application executes the tool and sends back a tool_result block.
```

### Comparison point for students

Even though the wire format differs across providers, the **conceptual loop** is the same:

- model decides,
- application executes,
- observation returns,
- controller decides whether to continue or stop.

---

## 11. Design principles for good tool calling

### 11.1 Make tool boundaries crisp

Bad:
- `analyze_dataset`

Better:
- `explore_data`
- `cluster_data`
- `classify_data`

Why? Because clear boundaries help the model choose correctly.

### 11.2 Put preconditions in the descriptions

Example:
- "`classify_data` requires a target label column."
- "`cluster_data` expects numeric feature columns."

### 11.3 Prefer tools that return interpretable outputs

For teaching and debugging, tools should return:
- clear metrics,
- summaries,
- compact structured results.

### 11.4 Separate "can do" from "should do"

A tool being available does not mean it should be called.

### 11.5 Always compare to the original user goal

This is the easiest way to avoid endless loops.

---

## 12. Good discussion questions for class

1. Should `explore_data` always be called first?
2. Should the model be allowed to call multiple tools in parallel?
3. Who should choose the clustering features: the model, the user, or the tool?
4. When is it okay to stop with uncertainty?
5. Should a failed tool call be surfaced to the user immediately or hidden behind retries?
6. How much policy belongs in prompts versus application code?

---

## 13. Suggested in-class exercise

Give students three items:

- a user prompt,
- a tool list,
- and one tool result.

Ask them to decide the next move:

- call another tool,
- ask a clarification question,
- or stop.

### Example exercise prompt

**User**:  
> "Will this customer churn?"

**Available tool result from `explore_data`**:
```json
{
  "columns": ["age", "income", "monthly_spend", "visits_per_month", "region"],
  "candidate_targets": []
}
```

Ask students:
- Should the controller call `classify_data`?
- If not, what should the final answer say?

Correct direction:
- do **not** call `classify_data`,
- explain that supervised prediction is not supported because no target label exists.

---

## 14. Reading list

## A. Official docs and standards

### 1. OpenAI Function Calling Guide
Best starting point for current OpenAI function-calling patterns and loop structure.  
<https://developers.openai.com/api/docs/guides/function-calling/>

### 2. OpenAI Tools Guide
Useful for the broader landscape: built-in tools, function calling, tool search, and remote MCP.  
<https://developers.openai.com/api/docs/guides/tools/>

### 3. OpenAI Responses migration guide
Helpful when explaining why newer examples focus on the Responses API and not older endpoints.  
<https://developers.openai.com/api/docs/guides/migrate-to-responses/>

### 4. Anthropic Tool Use Overview
Good provider comparison: client tools, server tools, and the tool-result loop.  
<https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview>

### 5. Model Context Protocol (MCP) specification
Useful when discussing interoperable tool ecosystems beyond a single provider.  
<https://modelcontextprotocol.io/specification/2025-11-25>

### 6. OpenAI Apps SDK Quickstart
Good for showing how tools and UI come together in ChatGPT apps via MCP.  
<https://developers.openai.com/apps-sdk/quickstart/>

## B. Practical guides and cookbooks

### 7. OpenAI Cookbook: Handling Function Calls with Reasoning Models
Excellent for demonstrating why the number of reasoning/tool steps is often unknown in advance.  
<https://developers.openai.com/cookbook/examples/reasoning_function_calls/>

### 8. Anthropic: Building Effective Agents
Readable practitioner guidance on tools, structure, and agent design.  
<https://www.anthropic.com/research/building-effective-agents>

### 9. Anthropic: Writing effective tools for AI agents
Very helpful for discussing tool descriptions and model-facing tool ergonomics.  
<https://www.anthropic.com/engineering/writing-tools-for-agents>

## C. Foundational papers

### 10. MRKL Systems (Karpas et al., 2022)
A classic paper on modular systems that combine language models with symbolic or external modules.  
<https://arxiv.org/abs/2205.00445>

### 11. ReAct (Yao et al., 2022)
Very useful for teaching the interplay of reasoning and acting in a loop.  
<https://arxiv.org/abs/2210.03629>

### 12. Toolformer (Schick et al., 2023)
Important for the idea that models can learn when and how to use tools.  
<https://arxiv.org/abs/2302.04761>

### 13. PAL: Program-Aided Language Models (Gao et al., 2022)
Great reading for the general idea of offloading exact computation to external runtimes.  
<https://arxiv.org/abs/2211.10435>

---

## 15. Slide-friendly takeaways

- Tool calling is not just JSON generation.
- The real design problem is the **interaction loop**.
- Good tools have **clear boundaries** and **clear preconditions**.
- Exploration tools often determine whether other tools are valid.
- A system should call another tool only when it is **necessary** to answer the user’s question.
- "Done" can mean:
  - the answer is complete,
  - or the available tools/data are insufficient and the system can now explain why.

---

## 16. A closing line for the lecture

> Tool calling turns an LLM from a text generator into a controller of external capabilities.  
> The key design challenge is not only how to call tools, but how to decide when the job is finished.

---
