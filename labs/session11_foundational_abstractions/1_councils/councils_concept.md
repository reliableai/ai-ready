# Councils of Agents — Concept Doc

*Lesson 12 · Week 6 · brainstorm / outline (not a final lecture page)*

> Last week you built **an** agent.
> This week you build **twelve**. And you let them argue.
> Next week you'll learn when that was a terrible idea.

---

## 1. The Big Idea (and why it sits *between* single agents and complex systems)

A **complex system** (next week's lecture) decomposes a hard task into smaller sub-tasks, each handled by a specialized module wired in a pipeline. It's **vertical** — divide et impera.

A **council** keeps the task *whole* but multiplies **perspectives** on it. It's **lateral** — gather et synthetize. The output of a council is not a decomposition of the answer, it's an **aggregation of opinions about the answer**.

That's why councils are the natural stepping-stone beyond "one smart agent" and before "a full orchestrated architecture":

- They are the **simplest pattern that is not a single agent**.
- They produce something genuinely new: **calibrated disagreement**.
- They expose the core design questions of multi-agent systems (diversity, aggregation, cost, evaluation) in a minimal setting.

A council is more than the sum of its parts when the parts **disagree in useful ways**. It's less than the sum of its parts when they all fail in the same way — a point we will hammer.

---

## 2. Four Hooks, Four Patterns, One Lecture

Each "hook" (motivation) lands students in a different pattern. We teach all four, using the same running example so the contrasts are visceral.

### Hook A — *Wisdom of Crowds (for LLMs)*
**Pattern: Self-consistency / majority vote**
Same model, same prompt, temperature > 0, sample N times. Pick the modal answer.
The "hello world" of councils. It works because LLM errors are partially independent — if the true answer has a basin of attraction, random sampling finds it more than any single mistake.

*Teaching beat:* show the Galton ox plot, then show a plot of accuracy vs N samples. The curve is the lecture.

### Hook B — *The Jury / Deliberation Metaphor*
**Pattern: Role-based panel with a moderator (+ human escalation on disagreement)**
Different personas instantiated from the same base model: traditionalist, contrarian, skeptic, domain expert. A moderator agent runs the deliberation and writes the verdict. If the panel can't agree within K rounds, escalate to a human.

*Teaching beat:* 12 Angry Men, but the jurors are prompts. Great for decisions that are **qualitative and contested**, not factual.

### Hook C — *Ensembles as a Cheap Reliability Hack*
**Pattern: Multi-model ensemble + judge LLM**
Run GPT, Claude, Gemini, and an open model in parallel on the same input. A judge LLM (ideally a different family) synthesizes. This is the engineer-brain favorite: when fine-tuning is expensive and eval is shaky, diversity across **model families** is often the cheapest robustness you can buy.

*Teaching beat:* show a real benchmark where GPT's error and Claude's error are uncorrelated — the ensemble eats both.

### Hook D — *Diversity as the Real Product*
**Pattern: Debate / adversarial pairs**
Proponent vs Skeptic, moderated. The value is **not** in the winner — it's in the **record of disagreement**. This is the hook that bridges to next week's "when NOT to use agents": sometimes the honest answer is "the experts disagree, and here's why", not a confident synthesis.

*Teaching beat:* a debate transcript where the dissent is more informative than the verdict. Students read it and realize that a single-agent answer would have hidden the richest signal.

---

## 3. Running Example: **The Research Synthesis Council** 🔬

A council of reviewer-agents tasked with summarizing and critiquing the state of the art on a topic the students actually care about. This is a task every student already does — poorly, late at night, with a single LLM tab open — which is exactly why they can *feel* when a council gives them something better.

The task is semi-objective: there are factually right and wrong statements about the literature, *and* there are contested judgment calls. That mix is what lets us teach all four hooks without switching examples.

**The Panel (personas):**
- **Dr. Methods** — experimental design, sample sizes, confounds, ablations. Will flag "they didn't report variance across seeds."
- **Prof. Prior** — deep literature memory. Situates new work against the prior decade. Will say "this is just X (2019) with a new acronym."
- **The Skeptic** — hunts overclaiming, cherry-picked benchmarks, missing baselines. Reproducibility hawk.
- **The Builder** — external validity. "Does this actually work outside the benchmark? At production cost? With noisy data?"
- **The Synthesizer (Moderator)** — integrates the four voices into a verdict. Writes the summary. Preserves dissent rather than erasing it.

**Task variants (escalating difficulty):**
1. **Summarize the state of the art** on a topic (free-form; great for diversity-collapse demos and blind taste tests).
2. **Critical review of a single recent paper** (structured output — strengths, weaknesses, open questions, numeric score — clean for majority vote, variance plots, and calibration).
3. **Compare three papers on the same topic** (relational reasoning; councils tend to shine here because personas disagree on *which* paper is best).
4. **Propose next research directions** (generative decision task — where a council is most likely to *under*-perform a single sharp agent, which is exactly the lesson we want to end on).

We reuse the same four tasks across all four patterns, so students see the same inputs producing different council behaviors. That's the lesson.

**The meta-joke option:** one of the topics the council reviews is "councils of LLM agents." Students watch a council review the literature on councils. If it converges to premature consensus, the lecture writes itself.

---

## 4. Lecture Arc (suggested)

| # | Segment | Time | Beat |
|---|---------|------|------|
| 1 | The cold open | 5 min | "You ask one LLM to summarize the state of the art on topic X. It sounds confident. Here's what it got wrong. Now we ask twelve." |
| 2 | Vertical vs lateral composition | 8 min | Positioning councils between single agents and complex systems. One slide with two arrows. |
| 3 | Hook A + self-consistency live demo | 12 min | Task 2 (paper review with numeric score), N=1 vs N=20. Variance collapse plot *and* a blind taste test: students rate a single-agent review vs a self-consistency one. |
| 4 | Hook B + role-based panel demo | 12 min | Meet Dr. Methods, Prof. Prior, the Skeptic, the Builder. Run Task 1. Receipts UI on screen — per-persona transcripts next to synthesized verdict. |
| 5 | Hook C + multi-model ensemble | 10 min | Same personas across GPT/Claude/Gemini/open. Judge synthesizes. Compare to the same-model panel from segment 4 — does cross-family diversity buy anything? |
| 6 | Hook D + debate demo | 10 min | Prof. Prior vs The Builder debating a recent flashy result. The transcript of disagreement *is* the output. |
| 7 | Aggregation mechanics | 8 min | Majority vote, weighted by calibrated confidence, judge-LLM, rank aggregation. |
| 8 | When councils fail | 8 min | Mode collapse (all models trained on each other), correlated errors, sycophancy cascades, cost blowup, latency tax. |
| 9 | Eval for councils (callback to Lab 7) | 7 min | How do you eval a thing that produces *disagreement*? Metrics: accuracy *and* calibrated diversity. |
| 10 | Bridge to next week | 5 min | "Next week: when to *stop* adding agents." |

Total: ~85 min.

---

## 5. The Concepts Students Must Leave With

These are the *non-negotiable* takeaways. The rest is entertainment.

**C1. Diversity is the currency.** Aggregating correlated agents gives you nothing but a bigger bill. Sources of diversity, in rough order of cheapness: temperature, prompt, persona, model family, data/context, fine-tune.

**C2. Aggregation is a design choice, not a default.** Majority vote, weighted vote, judge-LLM, and rank aggregation all produce different answers from the same panel. Pick one with your eyes open.

**C3. Councils are for calibration, not just accuracy.** The cheapest way to get a confidence estimate from LLMs that refuse to give honest ones is to ask N of them and look at the spread.

**C4. Every council has a hidden aggregator.** Even "pick the first one that answers" is an aggregation rule. Make it explicit.

**C5. Councils can hide dissent.** A single synthesized verdict can be *less* informative than the raw transcript. Sometimes the right UI is the transcript.

**C6. Councils are not complex systems.** They are a *primitive* you'll compose into complex systems next week. Don't conflate parallel deliberation with decomposition.

---

## 6. Pedagogical Design: Making the Difference Visible

Students don't believe a pattern until they *see* its effect. This lecture is built around three comparison mechanics that let students experience the delta, not just hear about it. Every exercise in Section 7 feeds one of these.

**M1 · The Blind Taste Test.** For each task, we produce two outputs — one from a single strong agent, one from a council — and hand them to students unlabeled. They rate them on a shared rubric (coverage, accuracy, calibration, usefulness) *before* we reveal which was which. They discover where councils help and where they don't, rather than being told. Bonus: collect the class's blind ratings as a live dataset the lecture can cite against itself.

**M2 · The Receipts Panel.** The notebook always displays the council verdict alongside the raw transcripts from each persona. Students see *what the synthesizer kept* and *what it dropped*. The gap between transcript and verdict is often where the most interesting disagreement lives — and is exactly what a single-agent answer would have hidden. Claims in the verdict that trace to no transcript are flagged: *where did that come from?*

**M3 · The Ablation Slider.** A small notebook widget that lets students remove one persona at a time and regenerate. They feel, in real time, what each voice was contributing. When removing the Skeptic doesn't change the verdict, the Skeptic wasn't doing its job — and that's a teachable moment, not a bug.

The design principle: **never state a property of councils that students can't reproduce and check within ten minutes.**

---

## 7. In-Class / Lab Exercises (sketches for later)

- **E1 · Variance collapse, visible.** Self-consistency on Task 2 (paper review with numeric score). Plot score distribution for N=1 vs N=20. Students guess where the curve flattens *before* they see it, then check.
- **E2 · The blind taste test (M1).** For Task 1 (state-of-the-art summary), produce single-agent and council outputs. Students rate blind on a four-criterion rubric, then we reveal. The class's preferences become a shared data point for the rest of the semester.
- **E3 · The contrarian test.** Add the Skeptic to a working majority-vote council on Task 3 (comparing papers). Measure: how often does the Skeptic change the verdict? How often was that change right? What does it look like when the Skeptic is wrong?
- **E4 · Judge vs vote.** Same panel, two aggregators. Where do they disagree? Which is better calibrated against a gold rubric (or against human ratings from E2)?
- **E5 · Ablation slider (M3).** Drop one persona at a time. For each drop, characterize in one sentence what the verdict lost. This makes takeaway C1 tangible: "diversity is the currency."
- **E6 · The receipts UI (M2).** Build the side-by-side view: per-persona transcripts on the left, synthesized verdict on the right. Highlight claims in the verdict that are *not* traceable to any transcript. Where did those come from — wisdom, or hallucination of the synthesizer?
- **E7 · The honest failure.** Find a topic or task where the council is *worse* than a single sharp agent (Task 4 — "propose next research directions" — is a likely candidate). Explain why. This is the seed of the next-week lecture.

---

## 8. Provocations / Discussion Questions

- If three frontier models were trained partly on each other's outputs, is a three-model ensemble really diverse — or is it a single giant model in a trench coat?
- A council takes 5× the tokens and 3× the latency of a single agent. Name three tasks where that's obviously worth it, and three where it's obviously not.
- A jury of humans has *secret ballots* to reduce conformity. Should an LLM council?
- If a council always converges on an answer, is that wisdom or failure of diversity?
- Is "judge-LLM" just a single agent wearing the council as a costume?

---

## 9. Open Design Questions for *this* Lecture

Things to decide before we promote this to a full lecture page / notebook / deck:

1. **The topic pool.** The blind taste test only works if students can verify ground truth on the topic. Options: (a) a curated pool of ~10 sub-topics from the course itself — RAG, eval methodology, agentic memory, self-consistency — where we have gold reviews; (b) let students pick from their own project areas; (c) a mix. I lean (a) for the in-class demo and (c) for the assignment.
2. **The gold standard problem.** To eval councils honestly we need reference reviews. Do we hand-write 10–20 rubric-scored gold reviews of recent papers, or do we use the class's blind ratings from E2 as a rolling soft gold?
3. **One vendor or multi-vendor in the notebook?** Multi-vendor is pedagogically honest but operationally annoying (keys, rate limits, cost). Fallback: persona prompts on one model for most demos, true multi-vendor only in segment 5 where it's the whole point.
4. **How much do we foreshadow Lesson 13?** The "beyond a complex system" framing is powerful but can confuse. Drop a single slide, or weave it throughout?
5. **Assessment hook.** Three candidates: (a) "build a self-consistency council and plot the curve," (b) "build a panel that beats a single-agent baseline on Task 2 given the gold rubric," (c) "find a task where a council is *worse* than a single agent and explain why." I'm partial to (c) — it tests C6 and teaches humility.
6. **Does the council cite?** For a research-review task, citations are the honest currency. Do we require each persona to ground claims in retrieved passages, or keep it closed-book for v1 and push retrieval into the complex-systems lecture?

---

## 10. One-Line Summary (for the syllabus / preview)

*A council is the smallest thing that is more than one agent — and the simplest place to learn why diversity, aggregation, and disagreement are the real levers of multi-agent design.*
