# %% [markdown]
# # Prompt Iteration Loop
#
# A step-by-step walkthrough of the extract → judge → improve → re-test cycle.
#
# **The loop:**
# 1. **Extract** — run a prompt template on a dataset of support requests
# 2. **Judge** — assess each extraction for completeness, accuracy, and quality
# 3. **Analyze** — look at failure patterns and best practices
# 4. **Improve** — generate prompt variations that address the failures
# 5. **Re-test** — run the best variation and compare scores
#
# We'll do this interactively so you can inspect every intermediate result.

# %%
import json
import os
import re
import random
from pathlib import Path
from collections import Counter

from dotenv import load_dotenv
from jinja2 import Template
from openai import OpenAI

load_dotenv()

# ── Configuration ────────────────────────────────────────────────
MODEL = "gpt-4.1-mini"
IMPROVE_MODEL = "gpt-5.2"  # stronger model for the creative improve step
BATCH_SIZE = 30
DATASET_SIZE = 50  # keep small for fast iteration; increase for reliable scores

# ── Paths ────────────────────────────────────────────────────────
DATASET_PATH = Path("datasets/bitext_customer_support/sample.json")
EXTRACT_TMPL_PATH = Path("prompt_templates/extract_v1.j2")
BATCH_EXTRACT_TMPL_PATH = Path("prompt_templates/batch_extract.j2")
JUDGE_TMPL_PATH = Path("prompt_templates/judge_extraction.j2")
IMPROVE_SYSTEM_PATH = Path("prompt_templates/improve_prompt_system.j2")
IMPROVE_USER_TMPL_PATH = Path("prompt_templates/improve_prompt_user.j2")
BEST_PRACTICES_PATH = Path("best_practices.yaml")
OUTPUT_TMPL_PATH = Path("prompt_templates/extract_v2.j2")

# ── Client ───────────────────────────────────────────────────────
client = OpenAI()

print(f"Model: {MODEL}")
print(f"API key: {'ok' if os.environ.get('OPENAI_API_KEY') else 'MISSING'}")

# %% [markdown]
# ## 0. Load dataset and baseline prompt
#
# We'll use the **Bitext** dataset (short, labeled requests) so we can evaluate with both LLM-as-judge and ground-truth intent matching.
#
# We start with a small subset (50 items) to keep iteration fast and cheap.

# %%
dataset = json.loads(DATASET_PATH.read_text())[:DATASET_SIZE]
extract_tmpl_source = EXTRACT_TMPL_PATH.read_text()

print(f"{len(dataset)} items loaded from {DATASET_PATH}")
print(f"\n--- {EXTRACT_TMPL_PATH} ---")
print(extract_tmpl_source)

# %% [markdown]
# ## Step 1: Extract
#
# The template has one variable: `{{request}}`. Jinja2 replaces it with the actual customer text.

# %%
# Render the template for one item
rendered = Template(extract_tmpl_source).render(request=dataset[0]["text"])
print(rendered)

# %%
# Send it to the LLM
response = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": rendered}],
    temperature=0,
    response_format={"type": "json_object"},
)

print(response.choices[0].message.content)

# %% [markdown]
# ### From one item to a batch
#
# One API call per item is slow and expensive. Instead we send a **batch prompt**: the extraction
# template plus multiple items in one request. The LLM applies the template to each item and
# returns a JSON array of results.
#
# The batch prompt has a different structure from the single-item prompt — let's look at it.

# %%
# Load the batch extraction template — a single prompt that handles multiple items at once.
batch_extract_tmpl_source = BATCH_EXTRACT_TMPL_PATH.read_text()
print(f"--- {BATCH_EXTRACT_TMPL_PATH} ---")
print(batch_extract_tmpl_source)

# %%
# Render the batch prompt for 5 items so we can see what's actually sent
mini_batch = dataset[:5]
mini_payload = [{"id": it["id"], "request": it["text"]} for it in mini_batch]
mini_batch_by_id = {it["id"]: it for it in mini_batch}

rendered_batch = Template(batch_extract_tmpl_source).render(
    customer_support_requests=json.dumps(mini_payload, indent=2),
)

print("--- RENDERED BATCH PROMPT (first 1200 chars) ---")
print(rendered_batch[:1200])
print("..." if len(rendered_batch) > 1200 else "")

# %%
def parse_batch_extract_response(text):
    """Normalize batch extraction responses across prompt-schema revisions."""
    payload = json.loads(text)
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raw_items = payload.get("extractions")
    if not isinstance(raw_items, list):
        raise ValueError("Batch extraction response must include an 'items' or 'extractions' list.")

    normalized = []
    for entry in raw_items:
        item_id = entry.get("id")
        # Support multiple output schemas:
        #   standard:      {"output": {...}}  or  {"extracted_items": {...}}
        #   self-critique:  {"answer": {...}, "critique": "...", "revised_answer": {...}}
        output = entry.get("revised_answer")  # self-critique schema (use final answer)
        if output is None:
            output = entry.get("output")
        if output is None:
            output = entry.get("extracted_items")
        if not isinstance(item_id, str):
            raise ValueError("Each batch extraction item must include a string 'id'.")
        if not isinstance(output, dict):
            raise ValueError(f"Batch extraction item '{item_id}' must include an object output.")
        normalized.append({"id": item_id, "output": output})
    return normalized

# %%
# Run the batch on 5 items so we can inspect the full input/output
resp = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": rendered_batch}],
    temperature=0,
    response_format={"type": "json_object"},
)

batch_result = parse_batch_extract_response(resp.choices[0].message.content)
for item in batch_result:
    print(f"\n[{item['id']}]")
    original_item = mini_batch_by_id.get(item["id"])
    if original_item is not None:
        print("original dataset item:")
        print(json.dumps(original_item, indent=2))
    print("extracted output:")
    print(json.dumps(item["output"], indent=2))

# %% [markdown]
# ### Run extraction on all 50 items
#
# Same batch prompt, now on the full dataset. We use `BATCH_SIZE=30` to stay within
# context limits while keeping the number of API calls low.

# %%
def run_extraction(batch_tmpl_source, items):
    """Extract from items in batches using a batch extraction template.

    The template must accept {{customer_support_requests}} (JSON array of items).
    Returns list of dicts with llm_response.
    """
    results = []
    for i in range(0, len(items), BATCH_SIZE):
        batch = items[i : i + BATCH_SIZE]
        batch_payload = [{"id": it["id"], "request": it["text"]} for it in batch]

        rendered = Template(batch_tmpl_source).render(
            customer_support_requests=json.dumps(batch_payload, indent=2),
        )
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": rendered}],
            temperature=0,
            response_format={"type": "json_object"},
        )

        outputs = {e["id"]: e["output"] for e in parse_batch_extract_response(resp.choices[0].message.content)}
        for it in batch:
            results.append({**it, "rendered_prompt": rendered,
                            "llm_response": json.dumps(outputs.get(it["id"], {}), indent=2)})
    return results

extractions_v1 = run_extraction(batch_extract_tmpl_source, dataset)
print(f"Extracted {len(extractions_v1)} items")

for item in extractions_v1[:3]:
    parsed = json.loads(item["llm_response"])
    print(f"\n[{item['id']}] {item['text'][:80]}")
    print(f"  intent:   {parsed.get('intent')}")
    print(f"  symptoms: {parsed.get('symptoms', [])[:3]}")

# %% [markdown]
# ## Step 2: Judge
#
# A separate LLM call rates each extraction 1-5. The judge sees the rendered prompt and the response, but not the extraction template's instructions.

# %%
# The judge prompt — loaded from a Jinja2 template
judge_tmpl = JUDGE_TMPL_PATH.read_text()
print(judge_tmpl[:600])
print("...")

# %%
JUDGE_SYSTEM = """You are a quality judge for an information-extraction pipeline.
You receive the full rendered prompt sent to an LLM, and the LLM's response.
Judge whether the response is a good extraction for the request in that prompt.

Rate 1-5: 5=complete and accurate, 4=minor issue, 3=one material issue, 2=multiple issues, 1=unusable.
Respond in JSON: {"items": [{"id": "...", "motivation": "...", "rating": N}, ...]}"""

def run_judge(extractions):
    """Judge extractions in batches. Returns list of dicts with rating + motivation."""
    results = []
    for i in range(0, len(extractions), BATCH_SIZE):
        batch = extractions[i : i + BATCH_SIZE]
        batch_payload = [{"id": it["id"], "rendered_prompt": it["rendered_prompt"],
                          "llm_response": it["llm_response"]} for it in batch]

        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": json.dumps(batch_payload, indent=2)},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )

        j_by_id = {e["id"]: e for e in json.loads(resp.choices[0].message.content)["items"]}
        for it in batch:
            j = j_by_id.get(it["id"], {"motivation": "missing", "rating": None})
            results.append({"id": it["id"], "rating": j.get("rating"), "motivation": j.get("motivation")})
    return results

def mean_rating(results):
    ratings = [r["rating"] for r in results if isinstance(r.get("rating"), (int, float))]
    return sum(ratings) / len(ratings) if ratings else 0.0

judge_v1 = run_judge(extractions_v1)
print(f"Judge average: {mean_rating(judge_v1):.2f} / 5.00\n")

for rating in sorted(set(r["rating"] for r in judge_v1 if r["rating"])):
    n = sum(1 for r in judge_v1 if r["rating"] == rating)
    print(f"  Rating {rating}: {n:3d} {'█' * n}")

extractions_by_id = {item["id"]: item for item in extractions_v1}
EXAMPLES_PER_RATING = 2

print("\n--- Example individual assessments ---")
for rating in sorted(set(r["rating"] for r in judge_v1 if r["rating"])):
    print(f"\nRating {rating} examples:")
    examples = [r for r in judge_v1 if r["rating"] == rating][:EXAMPLES_PER_RATING]
    for assessment in examples:
        item = extractions_by_id[assessment["id"]]
        try:
            llm_response_pretty = json.dumps(json.loads(item["llm_response"]), indent=2)
        except json.JSONDecodeError:
            llm_response_pretty = item["llm_response"]

        print(f"\n[{assessment['id']}] rating={assessment['rating']}")
        print(f"text: {item['text']}")
        print("llm response:")
        print(llm_response_pretty)
        print(f"judge motivation: {assessment['motivation']}")

# %%
# Ground-truth check (free — no LLM calls)
def normalize(s):
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s.lower()).split())

gt_v1 = []
for item in extractions_v1:
    expected = item["ground_truth_intent"]
    try:
        predicted = json.loads(item["llm_response"]).get("intent", "").strip()
        gt_v1.append({"id": item["id"], "match": normalize(predicted) == normalize(expected),
                       "predicted": predicted, "expected": expected})
    except Exception:
        gt_v1.append({"id": item["id"], "match": False, "predicted": None, "expected": expected})

n_correct = sum(1 for r in gt_v1 if r["match"])
print(f"Intent accuracy: {n_correct}/{len(gt_v1)} = {n_correct/len(gt_v1):.0%}")

for r in [r for r in gt_v1 if not r["match"]][:5]:
    print(f"  [{r['id']}] predicted: {str(r['predicted']):30s} expected: {r['expected']}")

# %% [markdown]
# ## Step 3: Analyze failures

# %%
# Look at worst extractions
low = [r for r in judge_v1 if (r.get("rating") or 0) <= 3]
print(f"{len(low)} items rated ≤ 3\n")

for r in low[:5]:
    item = next(e for e in extractions_v1 if e["id"] == r["id"])
    motivation = (r.get("motivation") or "missing")[:200]
    print(f"[{r['id']}] rating={r['rating']}")
    print(f"  Text:       {item['text'][:100]}")
    print(f"  Motivation: {motivation}")
    print()

# %%
best_practices = BEST_PRACTICES_PATH.read_text()
print(best_practices)

# %% [markdown]
# ## Step 4: Improve — generate prompt variations
#
# We feed the current prompt, judge motivations, and best practices to the LLM and ask for 5 improved prompt variations.

# %%
# Load system prompt (static) and render user prompt (has variables)
improve_system = IMPROVE_SYSTEM_PATH.read_text()

motivations = [r["motivation"] for r in judge_v1 if r.get("motivation")]
if len(motivations) > 100:
    motivations = random.Random(42).sample(motivations, 100)

improve_user = Template(IMPROVE_USER_TMPL_PATH.read_text()).render(
    current_prompt=batch_extract_tmpl_source,
    best_practices_yaml=best_practices,
    avg_rating=f"{mean_rating(judge_v1):.2f}",
    n_items=len(judge_v1),
    rationales=motivations,
)

print(f"System ({len(improve_system)} chars):\n{improve_system[:300]}...\n")
print(f"User ({len(improve_user)} chars):\n{improve_user[:300]}...")

# %%
# Call a stronger model for the creative improve step
resp = client.chat.completions.create(
    model=IMPROVE_MODEL,
    messages=[
        {"role": "system", "content": improve_system},
        {"role": "user", "content": improve_user},
    ],
    temperature=0,
    response_format={"type": "json_object"},
)

improvement = json.loads(resp.choices[0].message.content)
print(f"Analysis:\n{improvement['analysis']}\n")

for i, var in enumerate(improvement["variations"]):
    print(f"  [{i+1}] {var.get('approach_name', '?')}: {var.get('rationale', '')[:120]}")

# %%
# Inspect the full text of each generated variation
for i, var in enumerate(improvement["variations"]):
    print(f"{'='*60}")
    print(f"VARIATION {i+1}: {var.get('approach_name', 'unnamed')}")
    print(f"{'='*60}")
    print(var["prompt_template"])
    print()

# %% [markdown]
# ## Step 5: Re-test — evaluate all variations
#
# Now we run each variation on the same dataset and compare scores. This is the core of the iteration loop — we measure whether our changes actually helped.

# %%
# Test each variation: extract → judge → ground-truth
variation_scores = {}

for i, var in enumerate(improvement["variations"]):
    name = var.get("approach_name", f"v2_{i+1}")
    var_tmpl_source = var["prompt_template"]
    print(f"Testing {i+1}/{len(improvement['variations'])}: {name}...", end=" ")

    ext = run_extraction(var_tmpl_source, dataset)
    jdg = run_judge(ext)
    n_ok = sum(1 for it in ext
               if normalize(json.loads(it["llm_response"]).get("intent", "")) == normalize(it["ground_truth_intent"]))

    variation_scores[f"v2_{i+1}"] = {
        "name": name, "judge_avg": mean_rating(jdg),
        "gt_accuracy": n_ok / len(ext), "judge_results": jdg, "extractions": ext,
    }
    print(f"judge={mean_rating(jdg):.2f}  accuracy={n_ok/len(ext):.0%}")

print("\nDone!")

# %% [markdown]
# ## Results — compare all versions
#
# Side-by-side comparison of the baseline and all variations.

# %%
# Leaderboard
v1_judge = mean_rating(judge_v1)
v1_acc = sum(1 for r in gt_v1 if r["match"]) / len(gt_v1)

print(f"{'Version':<10s} {'Name':<35s} {'Judge':>6s} {'Accuracy':>9s}")
print("-" * 63)
print(f"{'v1':<10s} {'baseline':<35s} {v1_judge:6.2f} {v1_acc:8.0%}")

ranked = sorted(variation_scores.items(), key=lambda kv: kv[1]["judge_avg"], reverse=True)
for ver, s in ranked:
    print(f"{ver:<10s} {s['name'][:33]:<35s} {s['judge_avg']:6.2f} {s['gt_accuracy']:8.0%}")

best_ver, best = ranked[0]
print(f"\nBest: {best_ver} ({best['name']})")
print(f"  Judge: {best['judge_avg'] - v1_judge:+.2f}  Accuracy: {best['gt_accuracy'] - v1_acc:+.0%}")

# %%
# Rating distributions: baseline vs best
counts_v1 = Counter(r["rating"] for r in judge_v1)
counts_best = Counter(r["rating"] for r in best["judge_results"])

print(f"Rating distribution — v1 vs {best_ver}\n")
for rating in range(1, 6):
    c1, cb = counts_v1.get(rating, 0), counts_best.get(rating, 0)
    print(f"  {rating}:  v1={c1:2d} {'█'*c1:20s}  best={cb:2d} {'█'*cb}")

# %% [markdown]
# ## Deep dive — where did the best variation improve?
#
# Let's look at items where the best variation scored higher than the baseline.

# %%
# Which items improved / regressed?
v1_by_id = {r["id"]: r["rating"] or 0 for r in judge_v1}
best_by_id = {r["id"]: r["rating"] or 0 for r in best["judge_results"]}

improved = [k for k in v1_by_id if best_by_id.get(k, 0) > v1_by_id[k]]
regressed = [k for k in v1_by_id if best_by_id.get(k, 0) < v1_by_id[k]]
print(f"Improved: {len(improved)}  Regressed: {len(regressed)}  Same: {len(v1_by_id) - len(improved) - len(regressed)}")

for item_id in improved[:3]:
    item = next(e for e in extractions_v1 if e["id"] == item_id)
    print(f"\n[{item_id}] {item['text'][:80]}")
    print(f"  v1={v1_by_id[item_id]}  →  best={best_by_id[item_id]}")

# %% [markdown]
# ## Save the winning prompt
#
# Save the best variation as `prompt_templates/extract_v2.j2` for use in the next iteration round or in production.

# %%
# Save the winning variation as a new template
best_idx = int(best_ver.split("_")[1]) - 1
best_prompt = improvement["variations"][best_idx]["prompt_template"]

OUTPUT_TMPL_PATH.write_text(best_prompt)
print(f"Saved {OUTPUT_TMPL_PATH}\n")
print(best_prompt)

 # %% [markdown]
# ## What's next?
#
# You've completed **one iteration** of the loop. To keep improving:
#
# 1. **Run another round** — feed `prompt_templates/extract_v2.j2` back as the baseline and repeat steps 1-5
# 2. **Scale up** — increase the dataset size from 50 to 200+ items for more reliable scores
# 3. **Try a different dataset** — swap Bitext for `tobi_bueck_tickets` or `cfpb_complaints` to see how the prompt generalizes
# 4. **Use split optimization** — see `autotune.py` for tune/selection/test splits that prevent overfitting
#
# ### Cost summary
# With batch_size=30 and 50 items, this notebook made approximately:
# - 2 extract calls (baseline) + 2 judge calls = **4 API calls for evaluation**
# - 1 improve call = **1 API call**
# - 5 variations × (2 extract + 2 judge) = **20 API calls for re-testing**
# - **Total: ~25 API calls** (vs. 350+ without batching)
