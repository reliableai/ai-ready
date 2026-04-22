# %% [markdown]
"""
# Source #8: Prompt Brittleness & the Illusion of "Same Metric"

**Same name. Same 1–5 scale. Same few-shot examples. Different rubric wording — big score swings.**

The usual framing of brittleness talks about punctuation and delimiters. On modern
models those perturbations barely move the needle (try it: `v1 Reversed examples` is
included as a control). The *real* brittleness is more insidious:

> Two rubrics with the same name, same scale, and what looks like synonymous wording
> are actually **different instruments**. The model follows each faithfully — and
> gives you different scores.

If you didn't realize you swapped the instrument, you'll think the model got worse
(or better) between iterations when nothing about the model actually changed.

## What we'll do
1. Start with a baseline Correctness (1–5) judge prompt
2. Apply "nuanced" rewordings that a PM would approve in review:
   - Narrower word (Correctness → Accuracy)
   - Strict vs lenient framing
   - Customer-perspective framing
   - Grade-like scale ("exceeds expectations")
   - Midpoint shift (3 = "partial" vs 3 = "acceptable baseline")
3. Run each variant on the same 20 examples at temp=0
4. Watch the mean score slide up and down — same name, different metric
"""

# %% — Setup
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()
MODEL = "gpt-4.1-mini"
CACHE_PATH = Path(__file__).parent / "brittleness_data_cache.json"

# %% [markdown]
"""
## Step 1: Load (or generate) the eval set

20 customer-support exchanges with ground-truth scores across 1–5. Cached so
re-runs are deterministic.
"""

# %% — Generate or load eval data
GENERATE_PROMPT = """Generate a realistic customer support exchange for an e-commerce company.
Return JSON with:
- "query": customer message (1-3 sentences)
- "response": agent response (2-4 sentences)
- "true_score": Correctness score 1-5
- "reasoning": why this score (1 sentence)

Target quality level: {target_score}
Return ONLY valid JSON."""


def generate_eval_data(n=20):
    import random
    random.seed(123)
    examples = []
    targets = [random.choice([1, 2, 3, 3, 4, 4, 4, 5, 5]) for _ in range(n)]

    print(f"Generating {n} evaluation examples...")
    for i, target in enumerate(targets):
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
            continue
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{n}")
    return examples


if CACHE_PATH.exists():
    print(f"Loading cached data from {CACHE_PATH.name}")
    eval_data = json.loads(CACHE_PATH.read_text())
else:
    eval_data = generate_eval_data(20)
    CACHE_PATH.write_text(json.dumps(eval_data, indent=2))
    print(f"Cached {len(eval_data)} examples")

print(f"Eval set: {len(eval_data)} examples")

# %% [markdown]
"""
## Step 2: Shared few-shot calibration examples

All variants use the **same** 3 calibration examples. The only thing we vary is
the rubric wording.
"""

# %% — Few-shot examples (fixed across all variants)
FEWSHOT = [
    {
        "query": "Can I return this item after 45 days?",
        "response": "Our return policy allows returns within 30 days of purchase. "
                    "Unfortunately, after 45 days we cannot process a return, but I "
                    "can help you with an exchange or store credit.",
        "score": 4,
        "reasoning": "Correct policy, offers alternatives, minor gap on exceptions."
    },
    {
        "query": "Is this laptop compatible with Linux?",
        "response": "Yes! This model ships with Windows but has full Linux compatibility. "
                    "Ubuntu and Fedora are officially supported, and the WiFi and Bluetooth "
                    "drivers work out of the box.",
        "score": 5,
        "reasoning": "Fully correct, specific, addresses the exact question."
    },
    {
        "query": "Where is my order? I ordered it last week.",
        "response": "I apologize for the inconvenience! Let me look into that. Our "
                    "delivery team is working hard to get your order to you as soon "
                    "as possible.",
        "score": 2,
        "reasoning": "Doesn't actually check the order status or provide tracking. Vague deflection."
    },
]


def fewshot_block(examples, delimiter="---"):
    return "\n\n".join(
        f"{delimiter}\nCustomer: {fs['query']}\nAgent: {fs['response']}\n"
        f"Score: {fs['score']}\nReasoning: {fs['reasoning']}"
        for fs in examples
    )


FEWSHOT_BLOCK = fewshot_block(FEWSHOT)

# %% [markdown]
"""
## Step 3: Define the variants

**v0 Baseline** — the reference rubric.

**v1 Reversed examples** is a control: a *presentation* perturbation (same semantics,
different order). We expect it to barely move the score. If a semantic perturbation
moves the score much more than v1 does, that's the teaching moment.

**v2–v7** are the real payload: nuanced metric-semantics shifts. To a human skimming
the diff they all look like "still Correctness, 1–5 — same thing." To the model they
are different instruments.
"""

# %% — Variant definitions

V0_BASELINE = f"""Rate the following customer support response for Correctness (1-5).

## Rubric
1 = Wrong or irrelevant
2 = Mostly wrong
3 = Partially correct, missing key details
4 = Mostly correct, minor gaps
5 = Fully correct and complete

## Examples
{FEWSHOT_BLOCK}

---
Customer: {{query}}
Agent: {{response}}

Return JSON with "score" (1-5) and "reasoning" (1-2 sentences). Return ONLY valid JSON."""


V1_REVERSED = f"""Rate the following customer support response for Correctness (1-5).

## Rubric
1 = Wrong or irrelevant
2 = Mostly wrong
3 = Partially correct, missing key details
4 = Mostly correct, minor gaps
5 = Fully correct and complete

## Examples
{fewshot_block(list(reversed(FEWSHOT)))}

---
Customer: {{query}}
Agent: {{response}}

Return JSON with "score" (1-5) and "reasoning" (1-2 sentences). Return ONLY valid JSON."""


# v2: Correctness → Accuracy. Accuracy is narrower — excludes completeness.
V2_ACCURACY = f"""Rate the following customer support response for Accuracy (1-5).

## Rubric
1 = Inaccurate
2 = Mostly inaccurate
3 = Partially accurate
4 = Mostly accurate
5 = Fully accurate

## Examples
{FEWSHOT_BLOCK}

---
Customer: {{query}}
Agent: {{response}}

Return JSON with "score" (1-5) and "reasoning" (1-2 sentences). Return ONLY valid JSON."""


# v3: Strict framing. Everything else identical.
V3_STRICT = f"""Rate the following customer support response for Correctness (1-5).

**Score strictly.** Reserve 5 only for responses that are fully correct, complete,
and leave nothing ambiguous. Any missing detail, caveat, or step caps the score at 4.
When in doubt, score lower — the customer deserves an accurate bar.

## Rubric
1 = Wrong or irrelevant
2 = Mostly wrong
3 = Partially correct, missing key details
4 = Mostly correct, minor gaps
5 = Fully correct and complete

## Examples
{FEWSHOT_BLOCK}

---
Customer: {{query}}
Agent: {{response}}

Return JSON with "score" (1-5) and "reasoning" (1-2 sentences). Return ONLY valid JSON."""


# v4: Lenient framing. Everything else identical.
V4_LENIENT = f"""Rate the following customer support response for Correctness (1-5).

**Score generously.** Support agents are trying their best under time pressure. Reward
responses that make a genuine effort to address the customer. A helpful-but-incomplete
answer should not be penalized harshly — partial credit is appropriate.

## Rubric
1 = Wrong or irrelevant
2 = Mostly wrong
3 = Partially correct, missing key details
4 = Mostly correct, minor gaps
5 = Fully correct and complete

## Examples
{FEWSHOT_BLOCK}

---
Customer: {{query}}
Agent: {{response}}

Return JSON with "score" (1-5) and "reasoning" (1-2 sentences). Return ONLY valid JSON."""


# v5: Customer perspective framing.
V5_CUSTOMER_PERSPECTIVE = f"""Rate this customer support exchange from the customer's
perspective. On a 1-5 scale, how satisfied would the customer be with this response?
Would they feel their concern was resolved?

## Rubric
1 = Very unsatisfied — the response did not help at all
2 = Unsatisfied — the response missed the point
3 = Neutral — the response was acceptable but underwhelming
4 = Satisfied — the response resolved the concern well
5 = Very satisfied — the response was everything the customer could ask for

## Examples
{FEWSHOT_BLOCK}

---
Customer: {{query}}
Agent: {{response}}

Return JSON with "score" (1-5) and "reasoning" (1-2 sentences). Return ONLY valid JSON."""


# v6: Grade-like scale (exceeds expectations).
V6_GRADE_SCALE = f"""Rate the following customer support response for Correctness (1-5).

## Scale
1 = Unacceptable — would fail QA review
2 = Below expectations — needs rework
3 = Meets basic expectations — acceptable but not impressive
4 = Above expectations — good work
5 = Exceeds expectations — exceptional

## Examples
{FEWSHOT_BLOCK}

---
Customer: {{query}}
Agent: {{response}}

Return JSON with "score" (1-5) and "reasoning" (1-2 sentences). Return ONLY valid JSON."""


# v7: Midpoint shift — "3 = acceptable baseline" instead of "3 = partial".
V7_MIDPOINT_SHIFT = f"""Rate the following customer support response for Correctness (1-5).

## Rubric
1 = Unusable — contains serious errors
2 = Needs major work — significant issues
3 = Acceptable baseline — solves the core issue
4 = Above baseline — solid, well-rounded
5 = Excellent — clearly outstanding

## Examples
{FEWSHOT_BLOCK}

---
Customer: {{query}}
Agent: {{response}}

Return JSON with "score" (1-5) and "reasoning" (1-2 sentences). Return ONLY valid JSON."""


VARIANTS = [
    ("v0 Baseline",              V0_BASELINE,             "reference"),
    ("v1 Reversed examples",     V1_REVERSED,             "presentation"),
    ("v2 Correctness→Accuracy",  V2_ACCURACY,             "semantic"),
    ("v3 Strict framing",        V3_STRICT,               "semantic"),
    ("v4 Lenient framing",       V4_LENIENT,              "semantic"),
    ("v5 Customer perspective",  V5_CUSTOMER_PERSPECTIVE, "semantic"),
    ("v6 Grade-like scale",      V6_GRADE_SCALE,          "semantic"),
    ("v7 Midpoint shift",        V7_MIDPOINT_SHIFT,       "semantic"),
]

print(f"Prepared {len(VARIANTS)} variants:")
for name, _, kind in VARIANTS:
    print(f"  [{kind:<12}] {name}")

# %% [markdown]
"""
## Step 4: Run all variants on the same data

Same 20 examples. Same model. `temperature=0`. Only the rubric wording changes.
"""


# %% — Run
def run_variant(name, prompt_template, data):
    results = []
    for ex in data:
        prompt = prompt_template.format(query=ex["query"], response=ex["response"])
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        try:
            parsed = json.loads(resp.choices[0].message.content)
            score = int(parsed.get("score", 0))
        except (json.JSONDecodeError, ValueError):
            score = 0
        results.append({
            "id": ex["id"],
            "true": ex["true_score"],
            "judge": score,
            "exact": score == ex["true_score"],
            "within1": abs(score - ex["true_score"]) <= 1,
        })

    exact = sum(r["exact"] for r in results) / len(results) * 100
    within1 = sum(r["within1"] for r in results) / len(results) * 100
    mae = sum(abs(r["judge"] - r["true"]) for r in results) / len(results)
    mean_score = sum(r["judge"] for r in results) / len(results)
    return {"name": name, "exact": exact, "within1": within1, "mae": mae,
            "mean_score": mean_score, "results": results}


all_results = []
for name, template, kind in VARIANTS:
    print(f"\nRunning: {name}...")
    start = time.time()
    res = run_variant(name, template, eval_data)
    res["elapsed"] = time.time() - start
    res["kind"] = kind
    all_results.append(res)
    print(f"  Exact={res['exact']:.1f}%  Within1={res['within1']:.1f}%  "
          f"MAE={res['mae']:.2f}  MeanScore={res['mean_score']:.2f}  ({res['elapsed']:.1f}s)")

# %% — Summary table
print("\n" + "=" * 82)
print("  METRIC-SEMANTICS BRITTLENESS — same data, same model, different rubric wording")
print("=" * 82)
print(f"  {'Variant':<28} {'Kind':<13} {'Exact%':>8} {'±1%':>7} {'MAE':>6} {'Mean':>6}")
print("-" * 82)

mean_scores = [r["mean_score"] for r in all_results]
exact_scores = [r["exact"] for r in all_results]
baseline_mean = all_results[0]["mean_score"]

for r in all_results:
    delta = r["mean_score"] - baseline_mean
    tag = f"  Δmean={delta:+.2f}"
    print(f"  {r['name']:<28} {r['kind']:<13} {r['exact']:>7.1f}% "
          f"{r['within1']:>6.1f}% {r['mae']:>5.2f} {r['mean_score']:>5.2f}{tag}")

print("-" * 82)
mean_swing = max(mean_scores) - min(mean_scores)
exact_swing = max(exact_scores) - min(exact_scores)
print(f"\n  Mean-score swing:   {mean_swing:.2f} points (on a 1–5 scale)")
print(f"  Exact-match swing:  {exact_swing:.1f} percentage points")
print(f"  Baseline mean score: {baseline_mean:.2f}")

# %% [markdown]
"""
## Step 5: Per-example score distribution across variants

For each example, how much did the judge score move across the 8 rubric wordings?
If the metric were truly the same, the spread should be 0.
"""

# %% — Per-example variance
print("\n" + "=" * 82)
print("  PER-EXAMPLE SCORE SPREAD ACROSS VARIANTS")
print("=" * 82)
print(f"  {'ID':>4} {'True':>5}  {'v0':>3} {'v1':>3} {'v2':>3} {'v3':>3} "
      f"{'v4':>3} {'v5':>3} {'v6':>3} {'v7':>3}  {'Range':>6} {'StdDev':>7}")
print("-" * 82)

high_disagree = 0
for i, ex in enumerate(eval_data):
    scores = [r["results"][i]["judge"] for r in all_results]
    score_range = max(scores) - min(scores)
    mean_s = sum(scores) / len(scores)
    std_s = (sum((s - mean_s) ** 2 for s in scores) / len(scores)) ** 0.5
    flag = " ⚠" if score_range >= 2 else ""
    if score_range >= 2:
        high_disagree += 1
    cells = " ".join(f"{s:>3d}" for s in scores)
    print(f"  {ex['id']:>4} {ex['true_score']:>5}  {cells}  {score_range:>6} {std_s:>7.2f}{flag}")

print(f"\n  {high_disagree}/{len(eval_data)} examples have a score range ≥ 2 across the 8 variants")

# %% [markdown]
"""
## Step 6: Takeaways

### What just happened?

Every variant was still called "1–5 Correctness" (or a close synonym). A PM
reviewing the diff between v0 and v7 would say "same rubric — different words."
The model disagreed.

### The big idea

**A rubric is an instrument.** Its wording is the calibration. "Rate for Correctness"
and "Rate for Accuracy" and "Rate from the customer's perspective" are not three
different phrasings of one instrument — they are three instruments measuring three
slightly different things. The model is doing the right thing by following each one
faithfully; the *bug is on our side*, in assuming they were interchangeable.

### How to spot this in practice

1. **If you changed the rubric, you changed the metric.** Re-baseline before comparing.
2. **Pin your rubric exactly.** Store it in version control. Any edit = a new version
   of the metric, not a minor tweak.
3. **Sensitivity-test the rubric, not just the prompt.** Generate N paraphrases of
   your rubric and measure score spread *before* shipping.
4. **Prefer a rubric where mean score is stable across paraphrases.** If a simple
   rewrite moves the mean by ≥ 0.3 points on a 1–5 scale, your rubric is fragile —
   tighten the wording until the mean stops moving.

### Contrast with the presentation control

v1 (reversed few-shot examples) is the "classic" brittleness perturbation: same
semantics, different order. On a robust modern model like `gpt-4.1-mini` the effect
is small. The semantic perturbations (v2–v7) move the mean score far more, because
they *actually change what is being measured*.

The takeaway isn't "modern models are brittle to delimiters." It's "modern models
are exquisitely sensitive to what you ask — so be careful what you ask."
"""
