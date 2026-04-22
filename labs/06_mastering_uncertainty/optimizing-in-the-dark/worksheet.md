# AI Evaluation Worksheet

*A thinking tool for rigorous evaluation methodology*

This worksheet helps teams think critically about their AI evaluation approach. For each question, provide an answer and explain **how you know** — the evidence or reasoning behind your answer.

It's okay to answer "I don't know" or "best guess" — but at least you'll know what you don't know.

---

## 1. Experiment Definition & Objectives

| Question | Answer | How do we know? |
|----------|--------|-----------------|
| What is the system under test (SUT) (name & version)? | | |
| Which component/workflow are we evaluating specifically? | | |
| Which properties/qualities are we measuring (list them)? | | |
| Are we testing any hypotheses? State them precisely. | | |
| What test conditions/scenarios are in scope (and out of scope)? | | |
| What business/customer decision will this evaluation inform? | | |
| What is the success threshold/decision rule ("ship/gate")? Why this threshold? | | |
| What assumptions does this experiment rely on? | | |
| Known limitations (what this eval cannot conclude) | | |
| Scope of validity (domains/customers/time periods), if applicable | | |
| Model/prompt/workflow versions and parameters fixed for the run | | |

---

## 2. Datasets

### 2.1 Provenance, Representativeness & Diversity

| Question | Answer | How do we know? |
|----------|--------|-----------------|
| Provenance (sources/customers/time window; customer vs synthetic) | | |
| Is the dataset representative of production scenarios? | | |
| Which diversity dimensions matter for this task (list)? | | |
| Is the dataset diverse enough for the use case? | | |
| For synthetic data (if any): why representative, and how validated? | | |

### 2.2 Size & Sampling

| Question | Answer | How do we know? |
|----------|--------|-----------------|
| What is the dataset size? Why is it sufficient (uncertainty/power)? | | |
| If sampled, which sampling method (random/stratified/other) and why appropriate? | | |

### 2.3 Overfitting & Robustness

| Question | Answer | How do we know? |
|----------|--------|-----------------|
| What concrete steps guard against overfitting to any golden set? | | |

---

## 3. Determining Correctness: Ground Truth & Judges

| Question | Answer | How do we know? |
|----------|--------|-----------------|
| How is ground truth obtained? (human eval, LLM judge, other) | | |
| How accurate/calibrated are judges? Noise/bias assessment? | | |
| Was a clear rubric with unambiguous instructions provided? | | |
| How is subjectivity/disagreement measured and handled? | | |
| Rubric wording sensitivity tested (do small wording changes flip results)? | | |

---

## 4. Metrics & Thresholds

| Question | Answer | How do we know? |
|----------|--------|-----------------|
| Chosen metrics (definitions, units, scales) | | |
| Business mapping: plain-language interpretation of each metric | | |
| Thresholds/traffic-lighting used and rationale (customer-backed vs arbitrary) | | |
| Sensitivity analysis: do rankings change under reasonable coefficient choices? | | |

---

## 5. Execution Workflow & Controls

| Question | Answer | How do we know? |
|----------|--------|-----------------|
| Reproducible run (code, seeds, env, container, data snapshot) | | |
| Randomization/shuffling/blinding implemented and verified | | |
| Logged inputs/outputs/judge decisions with stable IDs | | |
| QA/smoke tests for the evaluation pipeline | | |
| Stop conditions if mid-run checks fail (agreement drop/bug) | | |

---

## 6. Reporting & Decision Communication

### 6.1 Uncertainty & Sample Size

| Question | Answer | How do we know? |
|----------|--------|-----------------|
| Is uncertainty reported (CIs/SE/credible intervals/p-values)? How? | | |
| Are percentages only used for proportions/frequencies? | | |
| Are percentages used only for sufficiently large samples (≈100+)? | | |
| Are charts readable and minimize the risk of misleading conclusions? | | |
| Do charts include uncertainty where appropriate? | | |
| If applicable: what CI width is acceptable for decisions (e.g., ±10 pts)? | | |

### 6.2 Multiple Comparisons & Analysis Plan

| Question | Answer | How do we know? |
|----------|--------|-----------------|
| Count of metrics/slices/hypotheses tested | | |
| Multiple-hypotheses control (e.g., Bonferroni, Benjamini–Hochberg/FDR) | | |
| Pre-registered/written analysis plan exists | | |
| Risk of p-hacking when slicing along diversity dimensions? If so, how addressed? | | |

---

## 7. Conclusions, Limitations, Reproducibility

| Question | Answer | How do we know? |
|----------|--------|-----------------|
| Scope/limitations explicit (where results do/do not apply) | | |
| Pointers to code, datasets, prompts, rubrics, artifacts for replication | | |

---

*This worksheet is part of the [Iterating in the Dark](./index.md) series on AI evaluation methodology.*

**Download:** [worksheet.json](./worksheet.json)
