# Sources of Uncertainty — Design Notes

Unified setup: an AI system evaluated by an LLM judge scoring outputs 1–5 on a scorecard of 4 metrics: **Correctness, Helpfulness, Tone, Completeness**.

Pedagogy: **feel it, then fix it** — each source starts with a visceral moment (trap or exploration) where students see how they'd get fooled, then introduces the tool/method to handle it.

Format: mix per source (HTML playground, slides, notebook — whatever fits best).

Domain: AI system evaluation throughout.

**Every source must answer two key questions:**
1. **How do we solve or mitigate this?** — What's the practical remedy?
2. **Does more data help?** — And if so, how much? If not, why not?

---

## 1. Sampling noise (assuming samples are iid)

**Format:** HTML playground

**Feel it:** Students set true scores (defaults: Correctness 3.8, Helpfulness 4.1, Tone 4.3, Completeness 3.6) and pick sample size. Click "Run evaluation" repeatedly — watch the 4-metric scorecard wobble wildly at small n. Commitment twist: "Based on this measurement, would you ship?" → reveal the true value was below threshold.

**Fix it:**
1. Binarize scores (≥4 = "good"), show Beta posteriors — Beta(successes+1, failures+1). At n=10 the beta is wide, at n=500 it's a spike.
2. Bootstrap on the raw 1–5 scores (no binarization) — show bootstrap distribution of the mean per metric.
3. Confidence intervals as summary of both approaches.

**Key parameters:** true scores per metric, sample size (10–5000), confidence level (90/95/99%), number of repeated evaluations.

**Score generation:** discretized beta distribution (realistic skew, not symmetric).

**How do we solve/mitigate?**
- Report confidence intervals, never bare point estimates.
- Use beta posteriors (on binarized scores) or bootstrap (on raw scores) to quantify the uncertainty.
- Choose sample size *before* the experiment based on the precision you need (sample size planning).

**Does more data help?** Yes — this is the one source where more data is a clean fix. Variance of the mean shrinks as 1/n. The beta posterior tightens, the bootstrap distribution narrows. The playground should make this viscerally obvious: drag n from 30 to 300 and watch the uncertainty collapse.

---

## 2. Sampling bias

**Format:** HTML playground

**Core idea:** your evaluation sample has a different distribution than production along some dimension. Language is the featured example, but framed as one instance of a general problem — bias can lurk on any axis (complexity, domain, user type, synthetic vs real, etc.).

**Scenarios:**
- Synthetic data (clean, well-structured) vs real user queries (messy, ambiguous).
- Multilingual: test set might include other languages but in wrong proportions (e.g., 5% Italian in test vs 15% in production).

**Feel it (trick-then-reveal):** Show biased scorecard → ask "ship?" → reveal production-distribution scorecard. Dramatic gap.

**Explore:** Sliders for sample mix vs production mix across segments. Scorecard updates live. Students see that even small proportion mismatches create misleading aggregates.

**Fix it:** Per-segment breakdown (scorecard per segment side by side). Stratified sampling — sample proportionally to production mix.

**Key message:** Language is one axis of many. Always ask: "does my test set look like production?"

**How do we solve/mitigate?**
- Know your production distribution. Instrument it, measure it, don't assume it.
- Stratified sampling: sample proportionally to production mix across known segments.
- Per-segment reporting: always break the scorecard down by segment, never trust only the aggregate.
- When possible, validate on real production data, not just curated/synthetic test sets.

**Does more data help?** Not on its own — more biased data is still biased. If you collect 10,000 synthetic English queries, your estimate gets very precise... for the wrong population. More data helps *only if* it's representative. The fix is in the sampling design, not the sample size.

---

## 3. Noisy judges / ground truth — DEFERRED, TREATED AS A CROSS-CUTTING LAYER

Judges (LLM or human) are not just one source of uncertainty — they are a **multiplier layer** through which all other sources pass. Every measurement goes through the judge, so judge problems compound with every other source.

**Judge-specific issues to cover (as a separate section or lecture segment):**
- **Noise:** same judge, same output, different score each time (source #1 amplified)
- **Bias:** judge systematically generous/harsh on certain metrics or domains (source #2 amplified)
- **Brittleness:** small changes in judge prompt → different scores (source #9 amplified)
- **LLM evolution:** judge model gets updated, scores shift (source #10 amplified)
- **Subjectivity in human judges:** different humans have different standards — what's a "4" to one person is a "3" to another
- **Calibration drift:** judges (human or LLM) shift standards over time, or across different sessions
- **Inter-judge disagreement:** two judges (human or LLM) disagree — who's right?

**Key pedagogical point:** every source of uncertainty we cover (sampling noise, bias, overfitting, etc.) applies *again* at the judge level. The judge is itself a system being measured, and it has all the same problems.

**Plan:** cover the 10 sources first using "ideal judge" assumption, then dedicate a section to showing how a real judge re-introduces all of them as an extra layer of uncertainty.

---

## 3. Overfitting

**Format:** Real lab (Python notebook with live LLM calls). Cache results for later replay/slides.

**Pedagogy:** Instructor (Fabio) iterates on prompts live in front of students, showing reasoning at each step. Students watch the dev score climb, then see the held-out reveal.

**Key mechanism:** You *see* the test data. You read the examples, understand the patterns, and encode them into the prompt — including copy-pasting dev examples as few-shot examples in the prompt. This is information leakage: the data directly shapes the system. (Contrast with #4 Multiple Hypothesis Testing, where you never see the test data but still get biased results from selection.)

**Demo idea — the most dramatic form of overfitting:** Take dev examples that the system gets wrong, and literally add them as few-shot examples in the prompt. Dev score jumps. But those specific examples don't generalize — the held-out score barely moves or even drops.

**Two tasks, same overfitting lesson:**

### Task B1 — Judge calibration (classification-flavored)
- **Dataset:** Prometheus / FeedbackBench (https://arxiv.org/abs/2310.08491)
  - 1-5 scale ratings with custom rubrics, purpose-built for judge evaluation
  - Sample 50 examples for dev, 200 for held-out test
- **What students see:** Tune an LLM judge prompt to score chatbot responses 1-5 on Correctness, calibrating against human labels. Each iteration: tweak rubric, add examples, clarify edge cases → re-run on dev → watch agreement go up.
- **The overfitting:** After 10-15 iterations, dev agreement is high. Held-out test: much lower. The rubric was tuned to specific dev-set patterns.

### Task B2 — Structured summarization (open-ended)
- **Dataset:** TWEETSUMM (https://github.com/guyfe/Tweetsumm)
  - ~6,500 Twitter customer support conversations with extractive + abstractive summaries
  - Real messy data, relatable domain
  - Sample 50 for dev, 200 for held-out test
- **Structured extraction fields:** main issue, customer sentiment, resolution status, what the resolution was
- **What students see:** Tune a prompt to extract these fields from support threads. Each iteration: add formatting instructions, examples, edge-case rules → re-run on dev → score improves.
- **The overfitting:** Rules tuned to specific complaint types in dev set don't generalize. E.g., "if they mention 'refund', resolution = refund request" works on dev but misclassifies on test.
- **Evaluation of B2:** LLM-as-judge compares extracted fields to ground truth (match/partial/miss per field). This itself foreshadows the judges-as-cross-cutting-layer theme.

### Lab flow
1. Start with baseline prompt, evaluate on dev set (50 examples, real LLM calls).
2. Iterate 10-15 times: edit prompt → run on dev → see scorecard improve.
3. Show trajectory chart: dev score vs iteration number (going up).
4. Hit "Evaluate on held-out test set" (200 examples) → see the gap.
5. Overlay test score on trajectory chart: went up at first (real improvements), then plateaued while dev kept climbing.
6. Class discussion: when did the dev score stop being trustworthy?

### Feel it → fix it
- **Feel it:** The dev score going up feels like real progress. The held-out gap is the gut punch.
- **Fix it:** Train/dev/test split discipline. The dev set is for selection, the test set gives the honest number. The more iterations, the less you should trust the dev number.

**How do we solve/mitigate?**
- Strict held-out test set that you only touch once.
- Larger dev sets are harder to overfit (but not impossible).
- Track how many iterations you've done — the more you iterate, the more you should discount the dev improvement.
- Cross-validation on the dev set as a middle ground.

**Does more data help?** Partially. A larger dev set is harder to overfit, so the gap shrinks. But with enough iterations you'll overfit any finite set. The real fix is process discipline (held-out test set), not just more data. More data buys you time, not safety.

---

## 4. Multiple hypothesis testing

**Format:** HTML playground

**Key distinction from #3:** In overfitting, you *see* the data and it shapes your system (information leakage). In MHT, you **never look at the test data** — you design N prompt variants independently, then evaluate all N on the same held-out test set and pick the winner. You were disciplined, you didn't peek. But selecting the best of N on the same dataset still biases the winner's score upward. This is **selection bias**, not information leakage.

**Scenario:** You design 10 prompt variants for your customer support bot. Each variant was crafted from different design principles — not by looking at test data. You evaluate all 10 on the same 100-query test set. Variant #7 scores Correctness 4.3, best of the bunch. You ship it.

**Feel it (explore):**
The playground generates N variants that are all *identical in true quality* (or very close). Sampling noise means each gets a slightly different score on the test set. The "winner" is just the luckiest. Students:
1. Run the tournament — see a clear "winner" emerge with a convincing lead.
2. Repeat many times — see different winners each time. The "best system" is a different one every run.
3. **Key visual #1 — The bad decision:** Show that the tournament winner, when evaluated on fresh data, often performs *worse* than variants you discarded. You didn't just get a biased number — you shipped the wrong system.
4. **Key visual #2 — Bias scales with N:** Chart with X-axis = number of variants tested, Y-axis = gap between winner's test score and its true score. At N=2 the gap is small. At N=50 it's dramatic. The more thorough your search, the more you fool yourself.
5. **Key visual #3 — The 4-metric trap:** Show the full scorecard across all variants. With 4 metrics × 10 variants = 40 numbers, some variant will look spectacular on some metric by pure chance. You might pick a variant because it "won on Correctness AND Tone" — but it won on nothing.
6. **Key visual #4 — The control comparison:** Side-by-side: same tournament but with a fresh test set for the final evaluation of the winner. The inflated score vs the honest score. The gap is the selection bias, made visible.

**The trap twist:** Ask students: "You tested 20 prompt variants. Variant #14 scores 4.3 on Correctness — 0.5 points above the average variant. Ship it?" They commit. Then reveal: all variants had true Correctness of 3.8. The 4.3 was pure noise amplified by selection.

**Fix it:**
- Bonferroni / Holm-Bonferroni correction on the comparisons.
- Better: use the test set only for the *final* winner, selected on a separate validation set (two-stage evaluation).
- Report the adjusted confidence interval for the "best-of-N" winner, not the raw score.
- Pre-register which variant you're testing (when possible) to avoid post-hoc selection.

**How do we solve/mitigate?**
- Two-stage evaluation: use one dataset to select the winner, a fresh dataset to measure the winner's true performance.
- Statistical corrections (Bonferroni, Holm) if you must use the same dataset.
- Be honest about how many variants you tried — report N alongside the winner's score.
- Pre-registration: decide what you're testing before you see results.

**Does more data help?** Yes and no. More data shrinks the per-variant noise, so the selection bias gets smaller. But it never goes to zero as long as you're selecting best-of-N. And more data can make the problem *feel* worse: tighter CIs make small noise look "significant," so you're more confident in a biased pick. The real fix is process (two-stage evaluation, corrections), not just more data.

---

## 5. Variance across domains/customers

**Format:** HTML playground

**Core idea:** Variance across domains/customers is a property of the world, not a measurement problem. Your system genuinely performs differently for different people, topics, or domains. The aggregate scorecard hides this. No amount of better measurement fixes it — only improving the system (making it more adaptive) can reduce the variance.

**Scenario:** AI assistant sold to three enterprise clients. Internal aggregate scorecard says Correctness 4.0. But:
- Client A (finance-heavy queries): experiences 4.5 → happy
- Client B (medical-heavy queries): experiences 3.3 → churns
- Client C (mixed): experiences 3.9 → confused why it's not as good as promised

**Feel it (explore):**
1. Students see the aggregate scorecard. Looks solid.
2. They "deploy" to each client — playground reveals per-client scores based on each client's query mix. The variance is shocking.
3. Sliders to change client query mixes → watch client-level scores diverge wildly from the same aggregate.
4. **Simpson's paradox demo:** System A beats System B in aggregate (4.0 vs 3.9). But B beats A in *every single segment* (finance: B 4.5 vs A 4.4, medical: B 3.4 vs A 3.2, legal: B 3.9 vs A 3.7). A wins the aggregate only because it was tested on an easier mix. You'd pick the wrong system.

**Connection to #2 (sampling bias):** #2 is about your *test set* having the wrong mix. #5 is about *reality itself* being heterogeneous and the aggregate being a lossy summary. Even with a perfectly representative test set, the aggregate hides that some segments are failing.

**Fix it:**
- Always report per-segment scores, not only the aggregate.
- Weight the aggregate by production or customer-specific traffic mix.
- Define minimum acceptable performance per segment — a system that's 4.5 on finance but 2.0 on medical is not a "3.5 system," it's a broken system.
- SLAs per segment / per customer.

**How do we solve/mitigate?**
- Stratified reporting as standard practice.
- Per-segment SLAs and monitoring.
- **Crucially: improve the system itself.** Make it more adaptive to different domains (domain-specific prompts, routing, fine-tuning). The variance is real — it reflects actual system weakness, not a measurement artifact.

**Does more data help?** No. More data gives you a tighter estimate of each segment's score, but doesn't reduce the variance between segments. The variance is a property of the world: your system handles finance well and medical poorly. You can *measure* that more precisely with more data, but the gap doesn't shrink. Only system improvements (better medical handling) reduce the variance. This is fundamentally different from sources #1–4.

---

## 6. Choice of metric

**Format:** HTML playground or slides with worked example

**Core idea:** The metric is a design decision that encodes your values, not a statistical fact. The same system, same data, same judge — but different metrics tell contradictory stories. There is no "correct" metric to discover. You must decide what matters *before* you measure.

**Scenario:** System A vs System B, same 200 queries, same judge.
- Mean Correctness: A 4.1 vs B 3.9 → A wins
- Median Correctness: A 4 vs B 4 → tie
- % scoring ≥4 (binarized): A 62% vs B 68% → B wins
- 5th percentile (worst-case): A 1.8 vs B 2.5 → B wins (A has a worse tail)

A has a higher average but B is more consistent and has fewer disasters. Which is "better"?

**Feel it (trick-then-reveal):**
1. Show students only the mean. "A wins, ship A." They commit.
2. Toggle to median — tie.
3. Toggle to ≥4 rate — B wins.
4. Toggle to 5th percentile — B wins clearly.
5. The "winner" changes with each tab click. The data didn't change. The question changed.

**Expand to the 4-metric scorecard:** System A wins on Correctness and Tone, System B wins on Helpfulness and Completeness. Now what? Which metrics matter more? That's not in the data — it's a product decision.

**Fix it:**
- Pre-commit to a primary metric and a specific aggregation (mean, threshold, percentile) *before* running the evaluation.
- Understand the tradeoffs: mean rewards high highs, threshold rate rewards consistency, worst-case protects against disasters.
- Use a hierarchy: primary metric decides the winner, secondary metrics are guardrails (must stay above a floor).
- The metric choice is part of the system design, not an afterthought.

**How do we solve/mitigate?**
- Pre-registration of the primary metric and success criteria.
- Metric hierarchy: one primary, others as guardrails.
- Document *why* you chose the metric — what user outcome does it proxy for?
- Revisit the metric choice when the product context changes.

**Does more data help?** No. More data makes each metric more precise, but doesn't resolve the disagreement between metrics. That's a design question, not a data question.

---

## 7. Temporal drift

**Format:** Slides with worked example + optional HTML time-series visualization

**Core idea:** Your evaluation is a snapshot, not a guarantee. The number has an expiration date, and you don't know what it is. The world changes — user behavior, topics, expectations, regulations — and your system degrades without any code change.

**Scenario:** Customer support bot evaluated monthly.
- January: Correctness 4.2 → great, ship it.
- February: 4.1 → fine.
- March: 3.8 → hmm.
- April: 3.5 → panic.
What happened? New product launch → flood of queries about features the system was never designed for. Or: users shifted to a more casual tone and the system's formal style now reads as "unhelpful."

**Feel it (explore):**
Time-series chart of monthly scorecards. The slow degradation is obvious in hindsight but invisible without continuous monitoring. Playground lets students simulate different drift rates and see how long before the system crosses the "unacceptable" threshold. Key question: "If you only evaluated once in January, when would you have noticed?"

**Key insight:** Your January evaluation tells you about January. It says nothing about April.

**Fix it:**
- Continuous monitoring, not one-off evaluations.
- Drift detection: alert when scores drop below a threshold or change by more than X over a rolling window.
- Periodic re-evaluation on fresh production data.
- Version everything (data, prompts, models) so you can diagnose *what* drifted.

**How do we solve/mitigate?**
- Build monitoring into the system from day one.
- Set up automated periodic evaluation on sampled production data.
- Track leading indicators (query distribution shift, topic mix changes) that predict score drops before they happen.

**Does more data help?** No — more data from January tells you January's score more precisely. It says nothing about April. The fix is *fresh* data over time, not more old data.

---

## 8. Prompt brittleness & sensitivity

**Format:** Live demo (notebook with real LLM calls, cached for replay in slides)

**Core idea:** Your system's performance depends on exact prompt wording in ways that are unpredictable and disproportionate. "Trivial" edits — reordering examples, changing punctuation, rephrasing instructions — can swing scores by 20-40+ points. This means your evaluation result is conditional on the *exact* prompt, not the intent behind it.

**Prep work:** Fabio runs a notebook beforehand that takes a task (e.g., judge calibration from #3), defines a baseline prompt, then systematically applies "trivial" perturbations and records the score after each. Concrete before/after examples to show in class.

**Documented examples to show (with references):**

1. **Reordering few-shot examples:** Same examples, different order → accuracy swings from 54% to 93%.
   - Zhao et al., "Calibrate Before Use" (2021) — https://arxiv.org/abs/2102.09690

2. **Single delimiter character change:** Changing the character separating examples → ±23% accuracy. Can manipulate model rankings to put any model in the lead.
   - "A single character can make or break your LLM evals" (2024) — https://arxiv.org/abs/2510.05152

3. **Punctuation / whitespace only:** Llama-2-70B-chat ranges from 9.4% to 54.9% (6x swing) from formatting variations alone.
   - "When Punctuation Matters" (2024) — https://arxiv.org/abs/2508.11383

4. **Answer option ordering:** In multiple choice, models prefer certain positions (A/B/C/D) regardless of content.
   - Zheng et al., ICLR 2024 Spotlight — https://arxiv.org/abs/2309.03882

5. **Production incident:** Changing "Output strictly valid JSON" to "Always respond using clean, parseable JSON" silently broke downstream parsers.
   - Deepchecks production analysis — https://deepchecks.com/llm-production-challenges-prompt-update-incidents/

6. **Up to 76 accuracy points difference** from small formatting changes in few-shot settings.
   - "Quantifying Language Models' Sensitivity to Spurious Features" (2023) — https://arxiv.org/abs/2310.11324

**Feel it (live demo):**
Show students a working prompt. Make a series of "trivial" edits — ones everyone would agree are semantically equivalent. After each edit, show the scorecard. Scores bounce around far more than anyone expects. Key moment: reorder two few-shot examples, watch accuracy drop 15 points.

**Key insight:** Prompt engineering is not robust engineering. Your evaluation is conditional on exact wording. This is a property of the model, not the measurement.

**Fix it:**
- Sensitivity testing: before shipping, try N rephrasings and measure the variance in scores.
- Report score as a range (best/worst across rephrasings), not a single number.
- Prefer prompts where small perturbations cause small score changes (robustness as a selection criterion).
- Pin prompt versions exactly — treat any edit as a new deployment requiring re-evaluation.

**How do we solve/mitigate?**
- Systematic perturbation testing as part of the evaluation pipeline.
- Robustness score: how stable is performance across N rephrasings?
- Version control for prompts, with mandatory re-evaluation on any change.
- Design prompts for robustness, not just peak performance.

**Does more data help?** No — more data makes the score for each prompt variant more precise, but doesn't reduce the sensitivity between variants. The brittleness is a property of the model, not the measurement.

---

## 9. LLM evolution (model updates you don't control)

**Format:** Slides with documented real-world examples

**Core idea:** You don't own your model. The provider can update the weights behind the same API endpoint without warning. Your prompt, your test set, your code — nothing changed. But scores shift. This is unique to AI systems: traditional software doesn't change behavior when you don't touch the code.

**Scenario:** Customer support bot scored Correctness 4.2 on March 1. On April 15 — same prompt, same test set — Correctness 3.7. You didn't touch anything. The model behind the API was updated.

**Key documented example:**
- Chen et al., "How Is ChatGPT's Behavior Changing over Time?" (2023): GPT-4 went from 97.6% to 2.4% on a specific task (identifying prime numbers) between March and June 2023. Same prompt, same task, catastrophic regression.
  - https://arxiv.org/abs/2307.09009

**Also relevant:**
- Model deprecation forcing migration (e.g., `gpt-4-0613` → `gpt-4o`): subtle behavior changes your tests don't catch.
- Deepchecks finding: 22.9% of model updates cause prompt regressions, with some regressing >20%.

**Feel it:**
Show the Chen et al. chart — 97.6% to 2.4%. Let that sink in. Then ask: "How would you have caught this if you weren't re-running evals every week?"

**Key insight:** Your evaluation has an expiration date tied not just to the world changing (#7 temporal drift) but to the *model itself* changing under you. You have two sources of drift: the world and the model.

**Fix it:**
- Pin model versions (use dated snapshots like `gpt-4-0613`, not `gpt-4`).
- Automated regression tests on a schedule — catch degradation early.
- Maintain a fallback: if the new version regresses, roll back to the pinned version.
- Treat every model version change as a new deployment requiring full re-evaluation.
- Monitor provider changelogs / deprecation notices.

**How do we solve/mitigate?**
- Version pinning as default policy.
- Scheduled automated evaluation (daily/weekly) on a fixed benchmark set.
- Alerts when scores drop below threshold or shift beyond a tolerance.
- Multi-provider strategy: if one provider regresses, you can switch.

**Does more data help?** No. More data tells you more precisely what *this* version does on *this* date. When the version changes, your measurements are stale. The fix is continuous monitoring and version discipline, not more data.

---

## Cross-cutting layer: Judges (LLM and human)

**Format:** Mix — HTML playground for noise/bias impact, slides with real examples for subjectivity, live demo for brittleness.

**Why this is a separate layer, not just another source:**
Every single measurement in sources #1–9 assumed a perfect judge: you ask "is this output correct?" and get the right answer. In reality, the judge is itself an imperfect system. Every uncertainty source applies *again* at the judge level, and the errors **compound** — judge uncertainty multiplies with all the other uncertainties, it doesn't just add to them.

**The compounding effect — making it visceral:**
Walk students through the math/intuition:
- You have sampling noise (#1): your measured score is ±0.3 due to finite samples.
- Your judge is noisy: each individual score is ±1 point on the 1–5 scale.
- Combined: your confidence interval isn't ±0.3 anymore — it's much wider because each data point is itself uncertain.
- Show side by side: same experiment with a perfect judge (tight CI) vs a noisy judge (wide CI). The noisy judge doesn't just add a little fuzz — it can double or triple your uncertainty.

---

### Judge issue A: Noise (same judge, same input, different score)

**Mirrors source #1 (sampling noise), but at the item level.**

**Demo:** Take 50 chatbot outputs. Run the same LLM judge on each output 5 times. Show:
1. **Scatter plot:** Score from Run 1 vs Score from Run 2 for each item. Lots of off-diagonal points.
2. **Per-item variance:** Some items get consistent scores (always 4), others bounce between 2 and 5. The judge simply doesn't know.
3. **Agreement metric:** % exact match across runs, Cohen's kappa. Students see it's lower than they'd expect (often 60-70%).
4. **Impact on the scorecard:** Run the full evaluation 10 times (same outputs, same judge, re-judging each time). The scorecard wobbles — not because of different samples (#1), but because the *judge gives different answers each time*.

**Key visual:** Overlay the confidence interval from sampling noise alone (assuming perfect judge) vs the confidence interval including judge noise. The gap between the two is the cost of imperfect measurement.

**Fix:** Multiple judgings per item (average k runs, noise shrinks by √k). Better rubrics reduce noise at the source. More capable judge models tend to be more consistent.

---

### Judge issue B: Bias (systematically generous or harsh)

**Mirrors source #2 (sampling bias), but in the measurement instrument.**

**Demo:** Compare two judges on the same outputs:
1. Judge A (generous): averages 4.2 across outputs. Judge B (harsh): averages 3.4. Same outputs.
2. More subtle: Judge A is generous on Tone (always gives 4-5) but harsh on Correctness. Judge B is the opposite. The scorecard *shape* changes depending on which judge you use.
3. Domain-specific bias: judge is well-calibrated on English but systematically harsh on Italian responses (mirrors #2 and #5 at the judge level).

**Key insight:** If your judge is biased, more data doesn't help — you get a very precise wrong answer. This is exactly #2 (sampling bias) applied to the measurement instrument.

**Show the compounding:** Your test set is biased (#2) AND your judge is biased. The biases can cancel (lucky) or reinforce (disaster). Students see that stacking two biased components makes the outcome unpredictable.

---

### Judge issue C: Subjectivity and inter-judge disagreement

**This is unique to the judges layer — no parallel in #1–9.**

**The core problem:** Some things are genuinely subjective. "Is this response helpful?" — reasonable experts disagree. There isn't a ground truth to converge to. The disagreement isn't noise or bias — it's a fundamental property of the task.

**Demo (slides with real data):**
1. Take 20 chatbot outputs. Have 5 human experts independently score them 1-5 on Helpfulness.
2. Show the raw scores: for some outputs, experts agree (all give 4-5). For others, scores range from 2 to 5. The variance is enormous.
3. Key question: if the experts disagree, what is the "right" score? There isn't one. Your ground truth is a social construction, not a fact.
4. Now show: the LLM judge picks one score. Which expert does it agree with? Different experts. It's not "right" or "wrong" — it adopted one subjective standard.

**Inter-judge disagreement matrix:** Show a heatmap of judge-vs-judge agreement (human A vs human B, human A vs LLM judge, LLM judge vs itself). Students see that human-human agreement is often *lower* than human-LLM agreement. This challenges the assumption that human = ground truth.

**Key insight:** When the task is subjective, the concept of "accuracy" for a judge breaks down. You can't calibrate against ground truth because ground truth doesn't exist. You can only measure consistency and agreement.

**Impact on evaluation:** If your "ground truth" labels were produced by one subjective human, and your LLM judge disagrees, it might be the human who was arbitrary. Your entire evaluation pipeline rests on a foundation of opinions.

---

### Judge issue D: Calibration drift

**Mirrors source #7 (temporal drift), but in the judge.**

**The problem:** A human judge scores the first 50 items strictly (fresh, attentive). By item 200, they've drifted — more lenient, or more fatigued and random. LLM judges can drift too: if you change the preceding context, or if the order of items matters (primacy/recency effects).

**Demo:** Show judge scores over time within a single session. Plot average score per batch of 20 items. Reveal: the judge got more generous over time. The items weren't getting better — the judge's standards shifted.

**Fix:** Randomize item order. Insert calibration anchors (items with known scores, periodically re-judged). Monitor judge consistency across batches.

---

### Judge issue E: Brittleness (mirrors #8 at the judge level)

**The problem:** Your LLM judge prompt says "Score 1-5 on Correctness." You rephrase to "Rate the factual accuracy from 1 (poor) to 5 (excellent)." Scores shift. Same outputs, same model, different prompt wording for the judge.

**Demo (live or pre-cached):** Same 50 outputs judged with 5 different phrasings of the judge prompt. Show the scorecard for each phrasing. The "best system" changes depending on how you asked the judge.

**Compounding with #8:** Your system prompt is brittle (#8) AND your judge prompt is brittle. Small changes on either side cause score swings — and the swings can reinforce or cancel unpredictably.

---

### Judge issue F: LLM judge evolution (mirrors #9)

**The problem:** Your LLM judge is `gpt-4o`. The provider updates it. Your judge now scores differently. Your system didn't change, your prompt didn't change, but your evaluation results shifted because the *measurement instrument* was silently updated.

**Demo:** Show the same outputs scored by `gpt-4-0613` vs `gpt-4o` vs `gpt-4o-mini`. Different scores, different winners. The model you use as a judge is itself a variable.

---

### The compounding story — tying it all together

**This is the capstone demo.** Show a single evaluation scenario with multiple uncertainty sources stacked:

1. Start with source #1 only (sampling noise, perfect judge): CI is ±0.2
2. Add judge noise: CI widens to ±0.4
3. Add judge bias: the center of the CI shifts
4. Add judge subjectivity: now there isn't even a single "true" value
5. Add judge brittleness: the CI depends on which judge prompt you used
6. Add model evolution: the CI depends on which judge model version you ran

Each layer makes the picture fuzzier. By the end, students see that a confident-sounding scorecard ("Correctness: 4.1") is really "somewhere between 3.2 and 4.8 depending on who's judging, how they're asked, and which model version ran today."

**Key takeaway:** The scorecard is not a measurement of your system. It's a measurement of your system *as seen by this judge, with this prompt, on this data, at this moment*. Every one of those qualifiers hides uncertainty.

**Does more data help?** Only for the sampling noise component. Judge noise is reduced by multiple judgings per item. Judge bias, subjectivity, brittleness, and model evolution are *not* fixed by more data — they require better judges, better rubrics, multi-judge panels, version pinning, and humility about what your numbers mean.

---
---

## CAPSTONE: Uncertainty compounds — it does not cancel out

**This is the single most important message of the entire lecture.**

Students might assume uncertainties cancel: "the judge is sometimes too harsh, sometimes too generous, so it averages out." Or: "some sources push the score up, others down, so the net effect is small." This is wrong. Uncertainty grows when you stack sources. It never shrinks.

### Why compounding, not cancellation?

**The variance addition law:** Even when sources are independent, variances *add*. They never subtract. If sampling noise contributes σ₁², judge noise contributes σ₂², and prompt sensitivity contributes σ₃², the total variance is at least σ₁² + σ₂² + σ₃². The standard deviation (width of your uncertainty) is √(σ₁² + σ₂² + σ₃²) — always larger than any individual source. No source can make another source's uncertainty smaller.

When sources are *correlated* — and they often are (e.g., biased test set + biased judge both favoring easy queries) — it's even worse. Correlated biases reinforce, they don't cancel.

And biases (systematic errors) don't cancel at all — they shift your answer in one direction, and stacking two biases shifts it further, not back.

### Demo 1: The stacking visualization (HTML playground)

Start with the ideal case. Add one source of uncertainty at a time. Students watch the confidence interval grow and shift:

| What's included | Reported score | True uncertainty |
|---|---|---|
| Perfect judge, infinite data, no bias | 4.10 | exact |
| + Sampling noise (n=100) | 4.10 ± 0.15 | CI from finite sample |
| + Judge noise (70% self-agreement) | 4.10 ± 0.35 | each data point is itself uncertain |
| + Judge bias (systematically +0.3) | 4.40 ± 0.35 | shifted — center is wrong |
| + Sampling bias (wrong population mix) | 4.40 ± 0.35, but true value is 3.70 | CI doesn't even contain the truth |
| + Prompt brittleness (±0.3 across rephrasings) | 3.4 – 4.8 depending on which prompt | not a single number anymore |
| + Model evolution (judge updated) | ??? | measurement instrument changed |

Key visual: an animated bar chart where the "Correctness: 4.1" bar starts crisp and narrow, then gets wider, then shifts, then gets fuzzy, then splits into multiple possible values. By the end, the single number is an illusion.

### Demo 2: The simulation (HTML playground or notebook)

Actually simulate it. Generate 1000 evaluation runs, each time randomly drawing:
- A random sample of n items (sampling noise, #1)
- Each item scored by a noisy judge (judge noise, adds per-item variance)
- Judge has a systematic bias (shifts the mean)
- A slight prompt perturbation (adds between-run variance from #8)
- Optionally: a biased sample mix (shifts population, #2)

Plot three distributions:
1. **Sampling noise only** (perfect judge): tight bell curve centered on truth
2. **Sampling noise + judge noise**: wider bell curve, still centered
3. **All sources**: wide, shifted, possibly multimodal

Overlay the "true" value. In case 1 it's at the center. In case 3 it might be outside the distribution entirely. The scorecard said 4.1, the truth is 3.7, and no amount of staring at the scorecard tells you that.

### Demo 3: The "how many things can go wrong at once" table

Show a concrete scenario with numbers:

> You evaluate a customer support bot. n=100, LLM judge, 4 metrics.
>
> - Sampling noise: ±0.15 per metric (from #1)
> - Your test set is 80% English but production is 60% English: true Correctness is 0.4 lower than measured (from #2)
> - You tried 5 prompt variants and picked the best: winner is ~0.2 inflated (from #4)
> - Your judge agrees with itself 65% of the time: effective uncertainty per metric is ±0.30 (from judges A)
> - Your judge is systematically generous on Tone by +0.3 (from judges B)
>
> Your scorecard says: Correctness 4.1, Helpfulness 4.0, Tone 4.4, Completeness 3.8
>
> Reality (best estimate): Correctness ~3.5, Helpfulness ~3.7, Tone ~3.9, Completeness ~3.5
>
> The scorecard was wrong on every metric, in the same direction. You thought you were great, you're actually mediocre. And this is *before* considering temporal drift, model updates, or prompt brittleness.

### The anti-intuition students need to develop

| Intuition (wrong) | Reality |
|---|---|
| "Errors cancel out" | Variances add, biases compound |
| "More data fixes everything" | Only fixes #1. Doesn't fix bias, judges, brittleness, drift |
| "If the number looks precise, it is precise" | Precision ≠ accuracy. A very precise wrong number is worse than a vague right one |
| "We measured 4.1, so it's approximately 4.1" | 4.1 is the output of a specific judge, prompt, sample, model version, at one point in time. Change any one and the number changes |

### Key takeaway (for the final slide)

*"The scorecard is not a measurement of your system. It's a measurement of your system, as seen by this judge, with this prompt, on this data, at this moment in time. Every one of those qualifiers hides uncertainty. And the uncertainties do not cancel — they compound."*

### Format

HTML playground for Demos 1 and 2 (interactive stacking + simulation). Demo 3 as a worked example in slides. The anti-intuition table as a summary slide.

### Does more data help?

Only partially. More data reduces sampling noise (#1) and lets you estimate per-segment scores (#5) more precisely. But it does nothing for: judge bias, judge subjectivity, prompt brittleness, model evolution, sampling bias (if the extra data comes from the same biased source), or metric choice. Students should leave with the understanding that "collect more data" is the answer to exactly one of the ten sources, and is irrelevant or insufficient for the other nine.
