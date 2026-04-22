# L11 · Complex Systems I — Council of Agents and Other Agentic Patterns — Slide Notes

A slide-by-slide draft (one concept per slide). Iterate here before promoting to the HTML lecture page / deck.

Target: ~35 slides across 4 sections + opener + closer (including 3–4 demo interludes). Palette: Ocean Gradient (carry over from L10).

Each slide entry has: **title**, **content bullets**, optional **visual / code**, optional **speaker-note one-liner**.

Interlude slides mark where the lecture pauses for a demo (5–12 min each). Short in-class drills (IC-1 … IC-N) stay inline as "→ pause for IC-N" notes on their parent slide.

Scope note: this lecture introduces the **council** as the featured, worked-out pattern, then tours the other common orchestration patterns at a lighter altitude. The deep-dive on "how to build these well" lives in Complex Systems II (abstractions) and III (reliable architectures).

---

## Opener (3 slides)

### Slide 1 — Title

- **L11 · Complex Systems I — Council of Agents and Other Agentic Patterns**
- Week 6 · AI Design 2026
- Subtitle: *Last week you built an agent. This week you build twelve.*

### Slide 2 — Why today's lecture exists

- Until now: one agent, one loop, one answer. That's the atom.
- Real systems are **molecules** — many agents, each doing less, wired into a shape.
- Today's question: *what shapes are there, and which one should I reach for?*
- Two honest framings we'll keep coming back to:
  - **Lateral** composition: many perspectives on the **same** task (councils).
  - **Vertical** composition: one task broken into **different** sub-tasks (pipelines / hierarchies / routers).
- Speaker note: councils are the featured pattern because they're the **simplest thing that is not a single agent** — everything else in the taxonomy assumes you've internalized what a council is doing.

### Slide 3 — Roadmap: the pattern landscape

- **Visual:** a 2×2 grid.
  - X-axis: *same task* ↔ *different sub-tasks*
  - Y-axis: *one call* ↔ *many calls*
- Placements:
  - Many calls · same task → **Council / ensemble** (today's focus)
  - Many calls · different sub-tasks → **Pipeline, router, hierarchy**
  - One call · same task → plain agent (last week)
  - One call · different sub-tasks → doesn't exist
- "We'll fill this in over the lecture; by the end, every pattern has a cell and a reason you'd reach for it."

---

## Section 01 · Positioning: when one agent is not enough (4 slides)

### Slide 4 — The failure modes of a single agent

- Three failure modes a single agent cannot fix by trying harder:
  - **Overconfident wrong.** No internal signal that the answer is shaky.
  - **Mode collapse.** Only one plausible framing makes it into the output.
  - **Out-of-depth.** The task needs a planner *and* an executor *and* a critic; one prompt can't hold all three.
- Adding more tokens, more examples, or more tools doesn't address any of these.
- Thesis: *some failures are shaped like "you needed a second opinion" — no amount of prompting gets you one from inside the same call.*

### Slide 5 — Lateral vs vertical composition

- **Lateral (council / ensemble):** keep the task whole, **multiply perspectives** on it. Output = aggregation of opinions about the answer.
- **Vertical (pipeline / hierarchy / router):** **decompose** the task, each agent handles a sub-task. Output = assembly of sub-answers.
- These are not competing — they **compose**. A single sub-task inside a pipeline can itself be a council.
- **Visual:** two arrow diagrams side by side — lateral = fan-out-fan-in; vertical = chain / tree.
- Speaker note: the rest of the lecture tours lateral first (councils, deeply), then vertical (other patterns, at a tour altitude).

### Slide 6 — What "diversity" means, precisely

- A council with N identical agents is one agent running N times. The currency is **how the agents differ**.
- Sources of diversity, roughly in order of cheapness:
  - **Temperature** — same model, same prompt, sample N.
  - **Prompt / persona** — different framings of the same role.
  - **Model family** — GPT · Claude · Gemini · open-weights.
  - **Context / data** — different retrieved passages, different tools available.
  - **Fine-tune** — different training signal.
- Speaker note: this list is the backbone for the *council design* segment. Every council decision is "which of these levers am I pulling, and am I paying for diversity I'm not actually getting?"

### Slide 7 — The "lateral" hooks — four motivations, one pattern family

- Four ways students already think about councils; we'll teach each:
  - **Wisdom of crowds** → self-consistency / majority vote.
  - **Jury deliberation** → role-based panel + moderator.
  - **Engineer's reliability hack** → multi-model ensemble + judge LLM.
  - **Diversity is the product** → debate / adversarial pairs; the transcript *is* the output.
- Teaching beat: we'll ground each hook with the same running example so the contrasts are visceral, not theoretical.

---

## Section 02 · The council, in depth (14 slides)

### Slide 8 — Running example: the Research Synthesis Council

- **Task:** summarize and critique the state of the art on a topic students care about.
- **Why this task:** semi-objective (some factual claims, some contested judgment calls) — lets us teach all four hooks without switching examples.
- **The Panel (personas):**
  - **Dr. Methods** — experimental design, confounds, ablations.
  - **Prof. Prior** — literature memory; situates new work against the last decade.
  - **The Skeptic** — overclaiming, cherry-picked benchmarks, reproducibility.
  - **The Builder** — external validity; "does this work outside the benchmark?"
  - **The Synthesizer (Moderator)** — integrates into a verdict; preserves dissent.
- Task variants (escalating difficulty): summarize · review one paper · compare three papers · propose next directions.

### Slide 9 — Hook A — Self-consistency (wisdom of crowds for LLMs)

- Same model, same prompt, **temperature > 0**, sample N times. Pick the modal answer (or average the numeric score).
- Why it works: LLM errors are partially independent; the true answer has a basin of attraction that random sampling finds more than any single mistake.
- **Code sketch:**
  ```python
  samples = [llm(prompt, temperature=0.7) for _ in range(N)]
  answer = majority_vote([parse(s) for s in samples])
  ```
- When it wins: short, parseable answers with a ground truth (numeric scores, classifications, code with tests).
- When it loses: free-form text, where "modal" is ill-defined — you end up needing a judge LLM to aggregate, which is Hook C.

### Slide 10 — INTERLUDE · Demo A · Self-consistency curve

- Open `labs/10_complex_systems/1_councils/demos/` and run the paper-review script.
- Budget: ~8 minutes.
- What students see: score distribution for N=1 vs N=5 vs N=20 on Task 2 (paper review with numeric score). The variance-collapse plot *is* the lesson.
- Teaching beat: students guess where the curve flattens *before* the reveal, then check.
- → **pause for IC-1** (2 min): *At what N would you stop paying?*

### Slide 11 — Hook B — Role-based panel with a moderator

- Different **personas** instantiated from the same base model: Dr. Methods, Prof. Prior, The Skeptic, The Builder.
- A **moderator** agent runs the deliberation and writes the verdict.
- If the panel cannot agree within K rounds, escalate to a human.
- **Visual:** a panel UI — four transcripts on the left, one synthesized verdict on the right.
- Great for decisions that are **qualitative and contested**, not purely factual.
- Reference: 12 Angry Men, but the jurors are prompts.

### Slide 12 — Aggregation is a design choice, not a default

- Ways to turn N answers into one answer:
  - **Majority vote** — cheap, works on parseable answers.
  - **Weighted vote** — by calibrated confidence or track-record on held-out data.
  - **Judge LLM** — another model synthesizes; must be *different* from panel for honesty.
  - **Rank aggregation** — each agent ranks candidates; Borda / Condorcet on the ranks.
  - **Preserve disagreement** — no single answer; present the dissent record.
- Speaker note: "every council has a hidden aggregator. Even 'pick the first one that answers' is an aggregation rule. Make it explicit."

### Slide 13 — The receipts panel (and why it matters)

- **Always show:** the per-agent transcripts **alongside** the synthesized verdict.
- The gap between transcript and verdict is where the richest signal lives — and exactly what a single-agent answer would have hidden.
- Claims in the verdict that don't trace to any transcript are **flagged**: where did that come from?
- Teaching beat: a single-agent answer is a verdict with no receipts. Once you see the receipts panel, going back feels like losing information.

### Slide 14 — Hook C — Multi-model ensemble + judge LLM

- Run GPT, Claude, Gemini, an open-weights model in parallel on the same input. A judge LLM (ideally a different family) synthesizes.
- The engineer-brain favorite: when fine-tuning is expensive and eval is shaky, **diversity across model families** is often the cheapest robustness you can buy.
- **Visual:** a real benchmark where GPT's error and Claude's error are uncorrelated — the ensemble eats both.
- Gotcha: if three frontier models were trained partly on each other's outputs, the ensemble is a single giant model in a trench coat.

### Slide 15 — Hook D — Debate / adversarial pairs

- Proponent vs Skeptic, moderated. The value is **not** in the winner — it's in the **record of disagreement**.
- Use when the honest answer is *"the experts disagree, and here's why"* rather than a confident synthesis.
- Bridge to Complex Systems III (*when NOT to use agents*): sometimes a single-agent confident answer is worse than a two-agent honest disagreement.

### Slide 16 — INTERLUDE · Demo B · Blind taste test

- Open the panel demo and run Task 1 (state-of-the-art summary) twice: single agent vs council.
- Budget: ~10 minutes.
- Students rate both **blind** on coverage / accuracy / calibration / usefulness **before** the reveal.
- Teaching beat: they discover where councils help and where they don't, rather than being told. Their blind ratings become a live dataset the rest of the lecture cites.
- → **pause for IC-2** (3 min): *Pick one criterion where the council helps, one where it doesn't — and explain why.*

### Slide 17 — When councils fail

- **Mode collapse.** All models trained on each other's outputs — "diversity" evaporates.
- **Correlated errors.** Same prompt, same model, same temperature ≠ genuine diversity.
- **Sycophancy cascades.** Each agent sees prior answers and drifts toward them.
- **Cost blowup.** 5× tokens. 3× latency. Only worth it for tasks where the council *actually* buys something.
- **Hidden dissent.** A synthesized verdict can be *less* informative than the raw transcript — and you'd never know.

### Slide 18 — Councils are for calibration, not just accuracy

- The cheapest honest confidence estimate from LLMs that refuse to give honest ones is to **ask N and look at the spread**.
- If all N agree → you have real confidence evidence.
- If the spread is wide → you have honest "I don't know" evidence, which is often the **more useful** answer.
- Speaker note: this is the one takeaway even skeptical students usually accept. It's also the cheapest to demo.

### Slide 19 — Eval for councils (callback to Lab 7)

- How do you eval a thing that produces *disagreement*?
- Metrics, in addition to the accuracy metrics from Lab 7:
  - **Calibrated diversity** — does the spread correlate with ground-truth uncertainty?
  - **Dissent preservation** — does the verdict carry the signal the transcripts contain?
  - **Cost-adjusted win rate** — beats single-agent at **the same budget**?
- Speaker note: if you only eval final accuracy, you'll keep building councils that look like single agents and cost 5×.

### Slide 20 — Council design recipe (one slide)

- A working council, minimal version:
  1. Pick the **source of diversity** (temperature · prompt · model · data) — see Slide 6.
  2. Pick the **aggregator** (vote · judge · preserve disagreement) — see Slide 12.
  3. Always surface the **receipts panel** alongside the verdict — Slide 13.
  4. Eval against a single-agent baseline at **the same cost budget**.
- The failure mode of most councils in the wild is skipping step 4.

### Slide 21 — Councils are not complex systems

- A council is a **primitive** you'll compose into complex systems, not a complex system itself.
- Parallel deliberation (lateral) ≠ decomposition (vertical).
- Next section: the vertical patterns. The point is to have both in your toolkit and stop reaching for the first one you learned.

---

## Section 03 · Other orchestration patterns, at altitude (10 slides)

### Slide 22 — The pattern tour

- We'll introduce each pattern with the same four fields:
  - **Shape** — diagram
  - **When to reach for it** — one sentence
  - **Failure mode** — the classic mistake
  - **Example task**
- Deeper treatments live in Complex Systems II (abstractions) and III (reliable architectures); today is about having the vocabulary.

### Slide 23 — Pattern: Pipeline (sequential chain)

- **Shape:** A → B → C. Each stage consumes the previous stage's output.
- **When:** the task genuinely decomposes into ordered steps (extract → transform → summarize).
- **Failure mode:** error propagation. A bad step-1 output poisons everything downstream; no later stage can recover.
- **Example:** ingest a PDF → extract structured fields → validate → write to DB.
- Speaker note: pipelines are the pattern SaaS engineers already know; LLM pipelines inherit *all* their failure modes plus new ones (silent content drift).

### Slide 24 — Pattern: Router / dispatch

- **Shape:** classifier → one of N specialist agents.
- **When:** inputs fall into clearly separable categories, each with a specialist prompt/model/tool set.
- **Failure mode:** the classifier itself. "Router quality" becomes the bottleneck, and it's usually an LLM doing a job a cheap heuristic could do.
- **Example:** a support bot routing billing questions, technical questions, and cancellations to different flows.
- Speaker note: if your router is an LLM, measure it like one — confusion matrix on held-out traffic.

### Slide 25 — Pattern: Hierarchical / orchestrator-worker

- **Shape:** one orchestrator agent decomposes a task and dispatches sub-tasks to workers, then assembles.
- **When:** tasks where the decomposition itself is the hard part — "research this topic" ≠ fixed pipeline.
- **Failure mode:** orchestrator hallucinates a plan that sounds plausible but is wrong, and the workers execute it faithfully.
- **Example:** a research agent that plans "search → read → summarize → cite" but adapts per query.
- Worth noting: **a hierarchy can contain a council** at any node (e.g., the critic step is a 3-agent council).

### Slide 26 — Pattern: Plan-then-execute

- **Shape:** Planner agent writes a plan → Executor agent runs it step by step (with tools).
- **When:** you want plan-quality reviewable *before* any expensive / irreversible action runs.
- **Failure mode:** the plan is fine; the executor deviates under pressure (tool errors, unexpected content) and re-plans ad-hoc without surfacing it.
- **Example:** "book me a flight" where the plan ("search, compare, choose, pay") gets human approval before the pay step.
- Connection: this pattern is where **checkpoints** and **human-in-the-loop** fit most naturally — Complex Systems III will make that explicit.

### Slide 27 — Pattern: Self-refine / critic loop

- **Shape:** Generator → Critic → Generator (repeat until Critic approves or budget hit).
- **When:** the critic is cheaper than the generator, *or* the task has a clear correctness signal (unit tests, schema validation, style rules).
- **Failure mode:** the critic and generator collude (same model, same prompt bias) — infinite approval.
- **Example:** code generation with a test runner as the critic. Refinement works because the test is *not* an LLM.
- Teaching beat: a critic that agrees with everything is a critic that isn't working — the same lesson as "remove the Skeptic from your council and nothing changes."

### Slide 28 — Pattern: Map-reduce / parallel fan-out

- **Shape:** split input into N chunks → process each in parallel → reduce.
- **When:** the work is embarrassingly parallel on sub-inputs (per-document, per-record, per-user).
- **Failure mode:** the reduce step quietly becomes the whole task — you spent N calls to feed one giant synthesis call that does all the reasoning.
- **Example:** summarize a 500-page document by chunking → per-chunk summary → final synthesis.
- Note: this is vertical (different sub-tasks) even though it looks lateral — each worker sees different data.

### Slide 29 — Pattern: Agent loop with tools (the "agent" from last week)

- **Shape:** LLM ↔ tool calls, in a loop, until the model decides it's done.
- **When:** the task requires interacting with external systems (search, code execution, APIs) and the steps can't be listed up front.
- **Failure mode:** loops that don't terminate, or that wander away from the goal after 10+ tool calls.
- Why it's in this list: it is the *building block* for most of the patterns above. Every node in a hierarchy is usually an agent loop.

### Slide 30 — Choosing between patterns

- **Visual:** a decision tree.
  - Same task, many opinions? → Council
  - Different sub-tasks, known order? → Pipeline
  - Different sub-tasks, unknown order? → Hierarchical / plan-then-execute
  - Categorized inputs? → Router
  - Clear correctness signal? → Self-refine
  - Embarrassingly parallel data? → Map-reduce
  - External systems required? → Agent loop (inside any of the above)
- Speaker note: the most common production architecture is a *composition*: router → hierarchical → (council at the critic node) → pipeline to write. None of these patterns are rivals.

### Slide 31 — INTERLUDE · Demo C · One task, three patterns

- Budget: ~10 minutes.
- Same task (review a paper) implemented three ways:
  1. Single agent (baseline).
  2. Council (Hook B from Section 02).
  3. Plan-then-execute with a self-refine critic.
- What students see: the outputs side-by-side, cost, latency, and the **receipts** for each.
- Teaching beat: which pattern fits which version of the task? None dominates; each has a regime.
- → **pause for IC-3** (3 min): *Name a task where pattern 3 obviously beats pattern 2, and one where it obviously doesn't.*

---

## Section 04 · Cost, tradeoffs, and "when NOT to use agents" (3 slides)

### Slide 32 — The three axes: quality · cost · latency

- Every orchestration pattern moves you on all three.
- Councils: +quality, ++cost, +latency.
- Pipelines: neutral quality per-step, +cost, ++latency (serial).
- Hierarchies / self-refine: +quality, ++cost, ++latency.
- Router: ≈ cost of its best branch + router overhead, latency dominated by the branch.
- Rule of thumb: if you can't state the **cost-adjusted** quality gain, you can't justify the pattern.

### Slide 33 — When not to reach for any of these

- Sometimes the right answer is "don't use an agent."
- Signs: the task is deterministic, the rules are writable, a heuristic/classifier beats the LLM on held-out data, or the cost of a wrong answer is high and the task doesn't need language.
- Foreshadow: Complex Systems III will dedicate a full section to *when a regex, a SQL query, or a classifier is the right tool*.
- Speaker note: the maturity move is being able to recommend "don't build this as an agent" in a room that expects you to.

### Slide 34 — Key takeaways (the non-negotiables)

- **T1.** Councils are lateral; pipelines / hierarchies / routers are vertical. Most real systems compose both.
- **T2.** A council with no diversity is one agent paying for N. Name your source of diversity.
- **T3.** Every council has a hidden aggregator. Make it explicit.
- **T4.** Councils are for calibration as much as accuracy — the spread is data.
- **T5.** The pattern you know is not the pattern you need. Learn the taxonomy; choose on the merits.
- **T6.** If you can't state the cost-adjusted quality gain, you can't justify the pattern.

---

## Closer (2 slides)

### Slide 35 — Bridge to Complex Systems II

- Today: *what shapes are there?*
- Next: *what abstractions let me build these shapes without the code rotting?*
- Preview: messages, tools, state, checkpoints, handoffs — the vocabulary the frameworks share.

### Slide 36 — One-line summary

- *A council is the smallest thing that is more than one agent — and the patterns in Section 03 are what you reach for when lateral isn't enough.*

---

## Open questions before promoting to deck / HTML page

1. Does the Research Synthesis Council stay as the running example, or do we swap for something closer to the students' own projects?
2. How much code lives in the slides vs the companion notebook? (Monitoring lecture put almost all code in demos/exercises — follow that.)
3. Demo A, B, C — do we build all three before Week 6, or ship with A+B and leave C as exercise?
4. Do we foreshadow the "when NOT to use agents" section from Complex Systems III, or keep it a clean cliffhanger at the end of today?
5. Aggregator taxonomy on Slide 12 — complete, or too much for one slide? Candidate to split if it's cramped in the live deck.
