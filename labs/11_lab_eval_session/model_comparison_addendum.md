# L10 Addendum: Model Comparison (Bonus)

> *"Which model is best?" is the wrong question. The right question is: "Best at what, for whom, at what cost?"*

---

## Overview

This bonus extension adds a **model comparison** dimension to the blog-ification lab. Instead of just evaluating outputs, you'll compare outputs from different models on the same task.

This teaches a critical production skill: **model selection is an evaluation problem.**

---

## Instructions

If you finish Parts 1-4 early, try this:

### 1. Generate with a Second Model

Re-run your agent on **one article** using a different model. Suggested pairs:

| If you used... | Try comparing with... |
|----------------|----------------------|
| `gpt-4.1-mini` | `gpt-4.1` |
| `gpt-4.1` | `claude-sonnet-4-20250514` |
| Any frontier model | `gpt-4.1-nano` or `gemini-2.0-flash` |

Keep your prompt identical. Only change the model.

### 2. Rate Both Outputs

Apply your rubric to both outputs. Record:
- Scores on each dimension
- Which you'd ship to a real blog
- Your confidence in the comparison

### 3. Reflect

- Did the "better" model win on all dimensions, or just some?
- How much quality do you lose with the cheaper model?
- Would your rubric need to change for a different use case?

---

## Cost Context

Ground your comparison with real numbers:

| Model | Approximate Cost (per 1M tokens) | Relative Speed |
|-------|----------------------------------|----------------|
| `gpt-4.1-nano` | ~$0.10 | Fastest |
| `gpt-4.1-mini` | ~$0.40 | Fast |
| `gpt-4.1` | ~$2.00 | Medium |
| `claude-sonnet-4` | ~$3.00 | Medium |
| `claude-opus-4` | ~$15.00 | Slower |

*Prices approximate and subject to change.*

For a blog-ification task processing 100 articles/day:
- Cheapest option: ~$0.50/day
- Most expensive: ~$75/day

**Question**: At what quality difference does a 150x cost increase become worth it?

---

## Bonus Reflection Questions

Add these to your Lab 10b reflection:

1. Was the quality difference between models obvious? Or did it depend on which dimension you weighted?
2. How many samples would you need to be 95% confident that Model A is better than Model B?
3. When might you intentionally choose the "worse" model?

---

## The Punchline

Often the **rating noise exceeds the model difference**. If your ratings vary by ±1.5 points on a 10-point scale, and the expensive model only beats the cheap model by 0.8 points... can you actually conclude it's better?

Model selection isn't about finding the "best" model. It's about finding the model that's good enough for your use case, your budget, and your confidence threshold.
