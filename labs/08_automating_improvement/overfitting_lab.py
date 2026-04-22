# %% [markdown]
"""
# Source #3: Overfitting to the Dev Set

**Feel it, then fix it.**

You'll iterate on a prompt, watch the dev score climb, then see the held-out gap.
The dev score going up *feels* like real progress. The held-out gap is the gut punch.

**Key mechanism:** You *see* the test data. You read the examples, understand the patterns,
and encode them into the prompt — including copy-pasting dev examples as few-shot examples.
This is **information leakage**: the data directly shapes the system.

## Setup
- Task: LLM judge scoring customer support responses 1-5 on Correctness
- Dev set: 30 examples (you iterate on these)
- Held-out test set: 100 examples (you touch this ONCE at the end)
- We use synthetic data so the lab runs without external datasets
"""

# %% — Setup
import json
import os
import random
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()
MODEL = "gpt-4.1-mini"

# %% [markdown]
"""
## Step 1: Generate Synthetic Customer Support Data

We create realistic customer support exchanges with known quality levels.
Each example has: a customer query, an agent response, and a ground-truth Correctness score (1-5).
"""

# %% — Generate synthetic data
GENERATE_PROMPT = """Generate a realistic customer support exchange for an e-commerce company.

Return JSON with these fields:
- "query": the customer's message (1-3 sentences)
- "response": the support agent's response (2-5 sentences)
- "true_score": Correctness score 1-5 (how factually correct and complete the response is)
- "reasoning": why this score (1 sentence)

For variety, generate exchanges across this quality spectrum:
- Score 1-2: wrong information, misunderstands the issue, or gives irrelevant answer
- Score 3: partially correct but missing key details
- Score 4: mostly correct with minor gaps
- Score 5: fully correct and complete

Target score: {target_score}

Return ONLY valid JSON, no markdown."""

def generate_examples(n, seed=42):
    """Generate n synthetic customer support examples with varied quality."""
    random.seed(seed)
    examples = []

    # Distribution: some bad, mostly medium, some great
    scores = []
    for _ in range(n):
        r = random.random()
        if r < 0.15:
            scores.append(random.choice([1, 2]))
        elif r < 0.35:
            scores.append(3)
        elif r < 0.70:
            scores.append(4)
        else:
            scores.append(5)

    print(f"Generating {n} examples...")
    for i, target in enumerate(scores):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": GENERATE_PROMPT.format(target_score=target)}],
            temperature=0.9,
            response_format={"type": "json_object"}
        )
        try:
            ex = json.loads(resp.choices[0].message.content)
            ex["id"] = i
            examples.append(ex)
        except json.JSONDecodeError:
            print(f"  Skipped example {i} (bad JSON)")
            continue

        if (i + 1) % 10 == 0:
            print(f"  Generated {i + 1}/{n}")

    print(f"Done. {len(examples)} examples generated.")
    return examples


# Generate dev (30) + held-out test (100) — or load from cache
CACHE_PATH = "overfitting_data_cache.json"

if os.path.exists(CACHE_PATH):
    print(f"Loading cached data from {CACHE_PATH}")
    with open(CACHE_PATH) as f:
        cached = json.load(f)
    dev_set = cached["dev"]
    test_set = cached["test"]
else:
    all_examples = generate_examples(130)
    random.shuffle(all_examples)
    dev_set = all_examples[:30]
    test_set = all_examples[30:]

    # Re-index
    for i, ex in enumerate(dev_set):
        ex["id"] = f"dev_{i}"
    for i, ex in enumerate(test_set):
        ex["id"] = f"test_{i}"

    # Cache to disk
    with open(CACHE_PATH, "w") as f:
        json.dump({"dev": dev_set, "test": test_set}, f, indent=2)
    print(f"Cached data to {CACHE_PATH}")

print(f"Dev set: {len(dev_set)} examples")
print(f"Test set: {len(test_set)} examples")

# %% [markdown]
"""
## Step 2: The Judge Prompt

This is the prompt we'll iterate on. It tells the LLM to score a customer support response
on Correctness (1-5).

**Start with a simple baseline.** We'll improve it step by step.
"""

# %% — Baseline judge prompt (v0)
JUDGE_V0 = """Rate the following customer support response for Correctness on a scale of 1-5.

1 = Completely wrong or irrelevant
2 = Mostly wrong with some correct elements
3 = Partially correct but missing key details
4 = Mostly correct with minor gaps
5 = Fully correct and complete

Customer query: {query}

Agent response: {response}

Return JSON with:
- "score": integer 1-5
- "reasoning": brief explanation (1-2 sentences)

Return ONLY valid JSON."""


def run_judge(prompt_template, examples, label=""):
    """Run the judge prompt on a set of examples. Returns scores + agreement stats."""
    results = []
    start = time.time()

    for ex in examples:
        prompt = prompt_template.format(query=ex["query"], response=ex["response"])
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        try:
            parsed = json.loads(resp.choices[0].message.content)
            judge_score = int(parsed.get("score", 0))
        except (json.JSONDecodeError, ValueError):
            judge_score = 0

        results.append({
            "id": ex["id"],
            "true_score": ex["true_score"],
            "judge_score": judge_score,
            "exact_match": judge_score == ex["true_score"],
            "within_1": abs(judge_score - ex["true_score"]) <= 1,
        })

    elapsed = time.time() - start

    exact = sum(r["exact_match"] for r in results) / len(results) * 100
    within1 = sum(r["within_1"] for r in results) / len(results) * 100
    mae = sum(abs(r["judge_score"] - r["true_score"]) for r in results) / len(results)

    print(f"\n{'='*50}")
    print(f"  {label}")
    print(f"  n={len(results)}  |  {elapsed:.1f}s")
    print(f"  Exact match:  {exact:.1f}%")
    print(f"  Within ±1:    {within1:.1f}%")
    print(f"  MAE:          {mae:.2f}")
    print(f"{'='*50}")

    return {"results": results, "exact": exact, "within1": within1, "mae": mae, "elapsed": elapsed}


# %% — Run baseline on dev set
print("Running baseline judge (v0) on DEV set...")
v0_dev = run_judge(JUDGE_V0, dev_set, label="v0 — Baseline (DEV)")

# %% [markdown]
"""
## Step 3: Iterate on the Prompt

Now you play the role of the prompt engineer. You'll look at the dev set errors,
understand the patterns, and improve the prompt.

**This is where overfitting happens.** Each iteration, you encode more dev-set-specific
knowledge into the prompt. The dev score climbs. But does it generalize?
"""

# %% — v1: Add rubric details (informed by dev set errors)
# Look at some dev errors first
print("Dev set errors (v0):")
for r in v0_dev["results"]:
    if not r["exact_match"]:
        ex = next(e for e in dev_set if e["id"] == r["id"])
        print(f"  [{r['id']}] True={r['true_score']} Judge={r['judge_score']}  "
              f"Query: {ex['query'][:60]}...")

# %% — v1: More detailed rubric
JUDGE_V1 = """You are an expert evaluator for customer support quality.

Rate the following customer support response for **Correctness** on a scale of 1-5.

## Rubric
- **1 (Wrong):** The response contains factually incorrect information, misidentifies the
  customer's issue, or provides an irrelevant answer. The customer would be misled.
- **2 (Mostly wrong):** The response addresses the topic but contains significant errors
  or misunderstandings. Some elements may be correct but the overall answer is unreliable.
- **3 (Partially correct):** The response gets the general idea right but is missing key
  details, caveats, or steps. The customer would need to follow up for a complete answer.
- **4 (Mostly correct):** The response is accurate on all major points with only minor
  gaps or imprecisions. The customer could act on this information successfully.
- **5 (Fully correct):** The response is factually accurate, complete, and directly
  addresses the customer's specific question. No follow-up needed.

## Important
- Focus on factual correctness, not tone or politeness.
- A response that is polite but wrong should score low.
- A response that is brusque but accurate should score high on Correctness.

## Exchange
Customer: {query}
Agent: {response}

Return JSON with "score" (integer 1-5) and "reasoning" (1-2 sentences).
Return ONLY valid JSON."""

print("Running improved judge (v1) on DEV set...")
v1_dev = run_judge(JUDGE_V1, dev_set, label="v1 — Detailed Rubric (DEV)")

# %% — v2: Add few-shot examples FROM the dev set (the overfitting move)
# Pick 3 examples the judge got wrong and add them as calibration examples
errors_v1 = [(r, next(e for e in dev_set if e["id"] == r["id"]))
             for r in v1_dev["results"] if not r["exact_match"]]

# Pick diverse errors (one too-high, one too-low, one correct example)
fewshot_examples = []
for r, ex in errors_v1[:3]:
    fewshot_examples.append({
        "query": ex["query"],
        "response": ex["response"],
        "score": ex["true_score"],
        "reasoning": f"Ground truth score is {ex['true_score']}."
    })

# If we don't have 3 errors, pad with correct ones
if len(fewshot_examples) < 3:
    correct = [(r, next(e for e in dev_set if e["id"] == r["id"]))
               for r in v1_dev["results"] if r["exact_match"]]
    for r, ex in correct[:3 - len(fewshot_examples)]:
        fewshot_examples.append({
            "query": ex["query"],
            "response": ex["response"],
            "score": ex["true_score"],
            "reasoning": f"Ground truth score is {ex['true_score']}."
        })

fewshot_block = "\n\n".join([
    f"### Example {i+1}\nCustomer: {fs['query']}\nAgent: {fs['response']}\nScore: {fs['score']}\nReasoning: {fs['reasoning']}"
    for i, fs in enumerate(fewshot_examples)
])

JUDGE_V2 = f"""You are an expert evaluator for customer support quality.

Rate the following customer support response for **Correctness** on a scale of 1-5.

## Rubric
- **1 (Wrong):** Factually incorrect, misidentifies the issue, or irrelevant answer.
- **2 (Mostly wrong):** Addresses the topic but significant errors. Unreliable overall.
- **3 (Partially correct):** General idea right but missing key details. Needs follow-up.
- **4 (Mostly correct):** Accurate on major points, minor gaps. Actionable.
- **5 (Fully correct):** Accurate, complete, directly addresses the question. No follow-up needed.

## Calibration Examples (to set your scale)
{fewshot_block}

## Important
- Focus on factual correctness, not tone or politeness.
- Calibrate your scores to match the examples above.

## Exchange to Rate
Customer: {{query}}
Agent: {{response}}

Return JSON with "score" (integer 1-5) and "reasoning" (1-2 sentences).
Return ONLY valid JSON."""

print("Running v2 (with dev-set few-shot examples) on DEV set...")
v2_dev = run_judge(JUDGE_V2, dev_set, label="v2 — Few-shot from Dev Set (DEV)")

# %% [markdown]
"""
## Step 4: Even more overfitting — add MORE dev examples

The dev score keeps going up. We're encoding more and more dev-set-specific knowledge.
This is the most dramatic form of overfitting: literally using dev examples as few-shot
calibration. It works perfectly on dev — but does it generalize?
"""

# %% — v3: Add more few-shot examples + edge-case rules from dev errors
# Grab more examples that v2 still gets wrong
errors_v2 = [(r, next(e for e in dev_set if e["id"] == r["id"]))
             for r in v2_dev["results"] if not r["exact_match"]]

additional_examples = []
for r, ex in errors_v2[:3]:
    additional_examples.append({
        "query": ex["query"],
        "response": ex["response"],
        "score": ex["true_score"],
        "reasoning": f"This is a {ex['true_score']} because the response "
                     f"{'addresses' if ex['true_score'] >= 3 else 'fails to address'} "
                     f"the customer's core issue."
    })

all_fewshot = fewshot_examples + additional_examples
fewshot_block_v3 = "\n\n".join([
    f"### Example {i+1}\nCustomer: {fs['query']}\nAgent: {fs['response']}\nScore: {fs['score']}\nReasoning: {fs['reasoning']}"
    for i, fs in enumerate(all_fewshot)
])

JUDGE_V3 = f"""You are an expert evaluator for customer support quality.

Rate the following customer support response for **Correctness** on a scale of 1-5.

## Detailed Rubric
- **1 (Wrong):** Factually incorrect, misidentifies the issue, or irrelevant answer.
  Example patterns: gives wrong return policy, confuses products, addresses wrong issue.
- **2 (Mostly wrong):** Addresses the topic but significant errors. Unreliable overall.
  Example patterns: mentions the right product but gives wrong specs or timelines.
- **3 (Partially correct):** General idea right but missing key details. Needs follow-up.
  Example patterns: correct category but skips important caveats or conditions.
- **4 (Mostly correct):** Accurate on major points, minor gaps. Actionable.
  Example patterns: right answer but could mention an additional option or exception.
- **5 (Fully correct):** Accurate, complete, directly addresses the question. No follow-up needed.

## Calibration Examples
{fewshot_block_v3}

## Scoring Rules
- Focus on factual correctness, not tone or politeness.
- If the response gives a correct general answer but misses a specific detail the customer
  asked about, cap at 3.
- If the response mentions a policy or timeline, verify it's consistent with the context.
- Calibrate strictly to the examples above.

## Exchange to Rate
Customer: {{query}}
Agent: {{response}}

Return JSON with "score" (integer 1-5) and "reasoning" (1-2 sentences).
Return ONLY valid JSON."""

print("Running v3 (heavy few-shot + rules from dev) on DEV set...")
v3_dev = run_judge(JUDGE_V3, dev_set, label="v3 — Heavy Few-shot + Rules (DEV)")

# %% [markdown]
"""
## Step 5: THE REVEAL — Run on Held-Out Test Set

Now the moment of truth. We take our best prompt (v3, which was heavily tuned to the dev set)
and run it on the 100-example test set that we've never touched.

**Prediction:** Dev score climbed steadily. Test score... didn't keep up.
"""

# %% — Run all versions on test set
print("=" * 60)
print("  HELD-OUT TEST SET — THE MOMENT OF TRUTH")
print("=" * 60)

print("\nRunning v0 (baseline) on TEST set...")
v0_test = run_judge(JUDGE_V0, test_set, label="v0 — Baseline (TEST)")

print("\nRunning v1 (detailed rubric) on TEST set...")
v1_test = run_judge(JUDGE_V1, test_set, label="v1 — Detailed Rubric (TEST)")

print("\nRunning v2 (few-shot from dev) on TEST set...")
v2_test = run_judge(JUDGE_V2, test_set, label="v2 — Few-shot from Dev (TEST)")

print("\nRunning v3 (heavy tuning) on TEST set...")
v3_test = run_judge(JUDGE_V3, test_set, label="v3 — Heavy Tuning (TEST)")

# %% — Summary: the overfitting trajectory
print("\n" + "=" * 70)
print("  OVERFITTING TRAJECTORY")
print("=" * 70)
print(f"{'Version':<30} {'DEV Exact%':>12} {'TEST Exact%':>12} {'Gap':>8}")
print("-" * 70)

versions = [
    ("v0 — Baseline",         v0_dev, v0_test),
    ("v1 — Detailed Rubric",  v1_dev, v1_test),
    ("v2 — Few-shot (dev)",   v2_dev, v2_test),
    ("v3 — Heavy Tuning",     v3_dev, v3_test),
]

for name, dev, test in versions:
    gap = dev["exact"] - test["exact"]
    marker = " ← GAP!" if gap > 5 else ""
    print(f"  {name:<28} {dev['exact']:>10.1f}% {test['exact']:>10.1f}% {gap:>+7.1f}{marker}")

print("-" * 70)
print("\n  The gap between dev and test is the overfitting.")
print("  Dev score went up because you encoded dev-set patterns into the prompt.")
print("  Test score plateaued (or dropped) because those patterns don't generalize.")

# %% [markdown]
"""
## Step 6: Discussion

### When did the dev score stop being trustworthy?

Look at the trajectory above. Dev climbed steadily (~+23pt total). Test barely moved
(~+9pt total). The **gap** grew from baseline noise to a big, obvious number.

Per stage (typical run):
- **v0 → v1** (more detailed rubric): Dev up a few points, test essentially flat
  (sometimes slightly down). We *think* we're making progress. We're not really —
  the change is within sampling noise at this dev size (n=30).
- **v1 → v2** (few-shot examples copy-pasted from dev): Dev jumps ~10pt, test also
  rises. Most of that gain is genuine — showing the judge calibration examples
  helps in general. But a small premium on dev is pure memorization.
- **v2 → v3** (more few-shot + rules derived from dev errors): Dev jumps another
  ~10pt. Test barely moves. **This is the textbook overfit.** We're encoding
  dev-specific patterns that don't generalize.

### The v0 baseline already has a gap

Even v0 shows a dev/test gap of several points. That's not overfitting — it's
**sampling noise** from a 30-item dev set. Students should internalize: a small
dev set has noisy scores, so early "improvements" below ~5pt may be meaningless.
A larger dev set shrinks this baseline gap but doesn't eliminate overfitting with
enough iterations.

### The fix

1. **Strict held-out test set** — you touch it ONCE, at the end.
2. **Track how many iterations** — the more you iterate, the more you should
   discount the dev improvement.
3. **Larger dev sets** are harder to overfit (but not impossible).
4. **Cross-validation** on the dev set as a middle ground.

### Does more data help?

Partially. A larger dev set is harder to overfit, so the gap shrinks.
But with enough iterations you'll overfit any finite set.
The real fix is **process discipline** (held-out test set), not just more data.
More data buys you time, not safety.
"""
