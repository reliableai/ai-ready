# Auto-Improvement Loop: Design & Purpose

## What we're building

A closed-loop system for **automatically improving LLM prompts** based on
structured feedback. The loop has three stages:

```
  ┌─────────────┐       ┌─────────────┐       ┌──────────────────┐
  │  1. Extract  │──────▶│  2. Judge    │──────▶│  3. Improve      │
  │  (run prompt │       │  (rate each  │       │  (analyze failure │
  │   on data)   │       │   output)    │       │   patterns, gen   │
  └─────────────┘       └─────────────┘       │   5 variations)   │
        ▲                                       └────────┬─────────┘
        │                                                │
        └────────────────────────────────────────────────┘
                     pick best variation, repeat
```

## Why this matters

Prompt engineering is typically ad-hoc: tweak, eyeball, repeat. This system
makes it **systematic and auditable**:

- **Judge** provides consistent, explainable ratings — not gut feel.
- **Improvement prompt** looks for **patterns** in failures, not individual fixes.
  This avoids overfitting to specific examples.
- **Multiple variations** explore different strategies (few-shot, chain-of-thought,
  negative instructions, restructuring). We test them all, not just one guess.
- **Full history** — every version, its rationale, its ratings — is preserved.
  You can trace *why* each change was made and whether it helped.

## The pieces

### Dataset (`datasets/sample_dataset.json`)

Each item represents one iteration of a prompt with an LLM:
- `id` — unique identifier
- `prompt_version` — which prompt template produced this (v1, v2, v3a, ...)
- `rendered_prompt` — the full prompt as sent to the LLM
- `llm_response` — what the LLM returned

The same input cases appear across versions so we can compare apples to apples.

### Judge prompt (`prompts/judge_extraction.md`)

Evaluates each extraction on four criteria:
1. **Completeness** — did it capture all facts?
2. **Accuracy** — is everything faithful to the input?
3. **Intent precision** — actionable but not too narrow?
4. **Symptom atomicity** — one fact per entry, no interpretation?

Output: `motivation` (reasoning first) then `rating` (1-5). Motivation-first
forces the judge to reason before scoring, which improves rating consistency.

Script: `run_judge.py`

### Improvement prompt (`prompts/improve_prompt.md`)

Takes as input:
1. The current prompt template (with `{{request}}` placeholder)
2. A best practices catalog (`best_practices.yaml`) — techniques to consider
3. Average rating from the judge
4. Up to 100 sampled judge rationales

The prompt asks the LLM to:
1. Find **patterns** in the rationales (systemic issues, not one-offs)
2. Select relevant best practices that address those patterns
3. Propose **5 variations**, each with a different improvement strategy

Each variation includes: what it changes, why, and the full new prompt template.

Script: `run_improve.py`

### Best practices catalog (`best_practices.yaml`)

A curated set of techniques: explicit schemas, role assignment, few-shot
examples, negative instructions, chain-of-thought, etc. The improvement prompt
treats these as a menu — it selects what's relevant, not a checklist to apply
blindly.

## The workflow

```bash
# 1. Run your prompt on a dataset (you do this, or script it)
#    → produces datasets/sample_dataset.json with rendered_prompt + llm_response

# 2. Judge the outputs
python run_judge.py --dataset datasets/sample_dataset.json --output judged_results.json

# 3. Generate improved variations
python run_improve.py \
    --prompt-template prompt_templates/extract_v1.j2 \
    --judged-results judged_results.json \
    --best-practices best_practices.yaml \
    --prompt-version v1 \
    --output improvements.json

# 4. Pick a variation (or test all of them), run on the same data, judge again
#    Compare ratings across versions.
```

## Design decisions

**Why 5 variations, not 1?** A single "improved" prompt hides the design space.
With 5 variations using different strategies, students see that prompt improvement
is about exploring trade-offs (verbosity vs. cost, examples vs. instructions,
structured reasoning vs. direct output).

**Why motivation before rating?** Forcing the judge to articulate reasoning
before assigning a number produces more calibrated, consistent scores. It's the
same principle as chain-of-thought — the reasoning anchors the conclusion.

**Why sample rationales, not aggregate stats?** The improvement prompt needs
to understand *what kind* of errors occur, not just how many. "Intent is vague"
and "symptoms are hallucinated" require very different fixes. Raw rationales
preserve that signal.

**Why a best practices catalog?** Without it, the improvement prompt invents
techniques from scratch each time — sometimes well, sometimes not. The catalog
provides a curated menu of proven techniques, grounding the suggestions.

**Why `{{request}}` placeholder?** The improvement prompt must output prompt
*templates*, not prompts for one specific input. The placeholder makes this
explicit and keeps templates reusable.

## What's next

The natural extensions:
- **Automated full loop**: script that runs extract → judge → improve → re-extract
  → re-judge for N iterations, tracking convergence.
- **Version history file**: append each generation of variations + ratings to a
  ledger so you can trace the full evolution.
- **Prompt tournament**: run all 5 variations on the same dataset, judge them all,
  pick the best, and feed it back into improvement.
