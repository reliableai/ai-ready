# L10: Putting It All Together

## A Hands-On Evaluation Lab

> "Wherever there is judgment, there is noise—and more of it than you think."  
> — Daniel Kahneman, *Noise: A Flaw in Human Judgment*

---

## Overview

You will build and evaluate a **blog-ification agent** — an LLM-powered system that transforms technical articles into accessible blog posts.

Sounds simple. But here's the catch: **how do you know if your agent is any good?**

By the end of this exercise, you'll discover that:
- Your evaluation criteria are more subjective than you thought
- Your own judgments are noisier than you expected
- "Improving" your system may be an illusion

Welcome to the reality of evaluating AI systems.

---

## Learning Objectives

- Design an LLM-based content transformation agent
- Create an evaluation framework for subjective outputs
- Quantify inter-rater reliability and self-consistency
- Understand uncertainty in evaluation metrics
- Experience the challenges of optimizing against noisy signals

---

## The Task

### Your Agent's Job

Given:
- A **source article** (technical content)
- **Blog guidelines** (style, length, audience)

Produce:
- A **blog post** that makes the content accessible

### Your Job

1. **Build** the blog-ification agent
2. **Generate** blog posts from provided articles
3. **Design** an evaluation framework
4. **Rate** outputs (yours and your peers')
5. **Analyze** the results and reflect

---

## Part 1: Build Your Agent (20 min)

Design a prompt (or prompt chain) that transforms technical articles into blog posts.

Consider:
- Single prompt vs. multi-step (outline → draft → refine)?
- What instructions help the LLM follow guidelines?
- How do you handle long articles?

Use the starter notebook (`notebook.ipynb`) and the provided articles in `articles/`.

**Deliverable**: Your agent prompt(s) saved in the notebook.

---

## Part 2: Generate Blogs (10 min)

Run your agent on **both provided articles** using **Guidelines V1**.

Save your outputs — you'll need them for evaluation.

**Deliverable**: 2 blog posts (one per article).

---

## Part 3: Design Your Evaluation Framework (20 min)

This is where it gets interesting. **You** decide what "good" means.

Design a rubric that answers: *How do I rate a blog post's quality?*

Consider dimensions like:
- **Accuracy**: Does it faithfully represent the source?
- **Accessibility**: Would a non-expert understand it?
- **Engagement**: Would someone want to read it?
- **Guideline compliance**: Does it follow the spec?
- **Completeness**: Are key points covered?

For each dimension:
- Define what you're measuring
- Choose a scale (1-5? 1-10? categorical?)
- Describe what each score level means

**Warning**: There is no "correct" rubric. This is intentional.

**Deliverable**: Your evaluation rubric (in the notebook or separate markdown).

---

## Part 4: Rate Outputs (25 min)

You will rate:
- Your own 2 blog posts
- 4 blog posts from peers (assigned via the submission form)

For each blog:
1. Apply your rubric
2. Assign scores for each dimension
3. Give an overall score (1-10)
4. Note your confidence (high/medium/low)

**Submit your ratings via the Google Form** (link provided by instructor).

💡 *Tip: Rate without looking at who wrote it. Focus on the output.*

---

## Part 5: The Reveal (Lab 10b)

In the next session, we'll analyze the class data together.

Come prepared to be surprised.

---

## Files in This Folder

```
L10/
├── README.md           ← You are here
├── notebook.ipynb      ← Starter code
├── guidelines_v1.md    ← Blog guidelines (version 1)
├── guidelines_v2.md    ← Blog guidelines (version 2) — used later
└── articles/
    ├── article_1.md    ← Source article 1
    └── article_2.md    ← Source article 2
```

---

## Submission Checklist

By end of Lab 10a, submit via Google Form:
- [ ] Your agent prompt(s)
- [ ] Your 2 generated blog posts
- [ ] Your evaluation rubric
- [ ] Your ratings (your blogs + 4 peer blogs)

---

## Hints

**On agent design:**
- Start simple. A single well-crafted prompt often beats a complex chain.
- Test with a short article first.

**On evaluation design:**
- Fewer dimensions rated well > many dimensions rated sloppily
- Write down your rubric *before* you start rating
- Your rubric will feel insufficient. That's the point.

**On rating:**
- Trust your gut on the first pass, then check against your rubric
- Note when you feel uncertain — that's data too

---

## Reflection Questions (for Lab 10b)

Start thinking about these:

1. How much did your ratings vary from your peers' ratings on the same blog?
2. Would you rate your own outputs the same way tomorrow?
3. If you "improved" your agent to score higher on your rubric, would it actually be better?
4. What would it take to be *confident* that System A is better than System B?

---

*"The first principle is that you must not fool yourself—and you are the easiest person to fool."*  
— Richard Feynman
