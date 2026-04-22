# AI Design — Course Projects

University of Trento — 2026

*DRAFT — Working Document*

---

This document outlines four project directions for the course. Each project asks you to design and build an AI-powered system where LLMs act as core components—making decisions, using tools, and managing state—rather than being used as simple text generators.

The descriptions below are intentionally high-level. They define the problem space and a few baseline capabilities; you are expected to shape the specific features, architecture, and evaluation approach for your project. Creativity and thoughtful design choices matter as much as technical execution.

**A note on emphasis.** In this course, building the system is only part of the work. Knowing whether your system works—and being honest about what you know and don't know—is equally important, and arguably harder. Read the evaluation sections carefully. They are not an afterthought.

---

## Project Overview

| Project | Core Idea | Key Challenge |
|---------|-----------|---------------|
| AI-Powered Course Hub | A knowledge management platform where students and professors share materials, ask/answer questions, and AI assists with auto-answers, catch-up summaries, and assignment pre-checks | Answer quality and knowing when to defer to humans; relevance ranking across heterogeneous content; evaluating AI contributions vs. human ones |
| Social Network for Agents (and Humans) | A social platform where AI agents replicate human personas and interact with each other | Persona consistency; emergent social dynamics; meaningful (not trivial) interactions |
| Conversational Clustering | An AI agent that iteratively clusters data through dialogue with a human | Reconciling contradictory feedback; evaluating without ground truth; deciding what to ask and when |

---

## Project 1: AI-Powered Course Hub

### Motivation

Every course generates a growing pile of knowledge: lecture slides, announcements, Q&A threads, reading lists, assignment specs, student notes. This information lives in scattered places—LMS pages, email threads, chat channels, shared drives—and nobody has a complete picture. Students who miss a class struggle to catch up. Questions get asked and re-asked. Professors repeat themselves across channels.

What if a single platform could organize all of this, and an AI layer could make it *useful*—answering questions from course materials, summarizing what happened last week, flagging common misconceptions, and pre-checking assignments before submission?

### Baseline Capabilities

At a minimum, the system should be able to:

- Let professors and students **upload and link to materials**: slides, readings, code, notes, external resources.
- Support a **Q&A board** where anyone can post questions, answer them, and upvote useful responses.
- Let professors **post announcements** and organize materials by topic or week.
- Provide **AI-powered features** that participate alongside humans:
  - Auto-answer questions using course materials as context (with source citations).
  - Generate **catch-up summaries**: "What happened in Week 3?" drawing from slides, announcements, and Q&A activity.
  - **Pre-check assignments** against stated requirements before students submit (e.g., "Your report is missing the evaluation section mentioned in the rubric").
  - **Smart search** across all content types: find the slide that explains X, the Q&A thread about Y, the announcement about Z.

### Design Considerations

Some questions to think about as you shape the project (you do not need to address all of them):

- When should the AI answer a question directly vs. surface existing human answers vs. flag it for a professor?
- How do you handle questions the AI shouldn't answer (e.g., exam content, grading disputes)?
- How do you keep AI answers grounded in actual course materials rather than general knowledge?
- How does the system handle contradictions between materials (e.g., a slide says one thing, a Q&A answer says another)?
- What's the right UX for AI contributions—should they look different from human posts? Should they be editable?
- How do you handle the cold-start problem at the beginning of a course when there's little content?

**Where KDD techniques apply.** Embedding-based retrieval is the backbone: you need to match questions to relevant materials across slides, Q&A posts, and announcements. Clustering questions reveals common pain points and potential gaps in materials. Upvote patterns give you a signal about content quality—but it's a noisy, biased signal (popular doesn't mean correct). When the AI pre-checks an assignment, it's making a classification decision (requirement met/not met) with uncertain confidence—how do you calibrate that? Ranking and recommendation techniques apply to surfacing the most relevant materials for a given context.

### Things Worth Measuring

Your evaluation should serve the three grading pillars — design alternatives, honest experiments, clear communication. Here are starting points for this project:

- **Answer groundedness**: is the AI citing actual course materials, or hallucinating from general knowledge?
- **When to stay quiet**: what's the cost of a wrong AI answer vs. the cost of silence?
- **Pre-check precision/recall**: false positives erode trust, false negatives defeat the purpose — estimate both rates
- **Catch-up summary accuracy**: can a student who reads only the summary participate in the next class?
- **Search relevance**: does smart search surface the right content across slides, Q&A, and announcements?

---

## Project 2: Social Network for Agents (and Humans)

### Motivation

What happens when AI agents don't just assist humans, but interact with each other as social entities? This project explores multi-agent social dynamics by building a platform where agents replicate human personas and engage in conversations, form opinions, and react to each other—a kind of social network populated by AI.

### Baseline Capabilities

At a minimum, the system should be able to:

- Create agent personas based on some form of input (descriptions, profiles, example texts, etc.).
- Let agents interact: post messages, comment, reply, have conversations.
- Maintain persona consistency across interactions (an agent should "sound like" the same person over time).
- Support some form of social dynamics: agents can react to each other's posts, form threads, take sides in discussions.

### Design Considerations

Some questions to think about:

- How do you define and maintain a persona? What makes an agent behave consistently?
- How do you prevent conversations from becoming shallow or repetitive?
- What social mechanics matter? Posting? Reacting? Private messages? Group dynamics?
- Can agents form opinions that evolve over time based on interactions?

**Where KDD techniques apply.** Mode collapse detection is a clustering and diversity problem. Embed agent outputs and measure cluster separation—if all agents map to the same region of embedding space, they've collapsed regardless of how different they *read* on the surface. The interaction network itself is a graph: who talks to whom, who responds to whom, which topics attract clusters of agents. Graph metrics (degree distribution, community structure, betweenness centrality of topics) can reveal whether your social dynamics are rich or degenerate. Cosine similarity distributions across agent outputs give you a quantitative handle on diversity that goes beyond "they seem different to me."

### Things Worth Measuring

Your evaluation should serve the three grading pillars — design alternatives, honest experiments, clear communication. Here are starting points for this project:

- **Persona consistency**: can readers match posts to personas above chance? (clear null hypothesis)
- **Mode collapse detection**: embed agent outputs and measure cluster separation — do all agents sound the same?
- **Interaction quality**: operationalize "meaningful" — disagreement? persuasion? depth? — then measure it, even roughly
- **Diversity of expression**: cosine similarity distributions across agents reveal whether diversity is real or surface-level
- **Vibe eval vs. real eval**: "4 of 6 raters found it substantive" beats "this seems cool" — quantify the noise

---

## Project 3: Conversational Clustering

### Motivation

Clustering is one of the most common tasks in data analysis—and one of the least well-defined. Ask three people to group the same dataset and you'll get three different answers, each defensible. Traditional clustering algorithms (K-means, DBSCAN) require you to commit to a distance metric, a number of clusters, and a definition of "good grouping" before you start. But in practice, people often don't know what grouping they want until they see one—and then they want to change it.

What if clustering were a conversation? An AI agent that proposes an initial grouping, explains it, and then iteratively refines it based on human feedback—at the level of individual points ("x should be in cluster B"), clusters ("merge A and B"), or the whole structure ("too many clusters, and you're ignoring the time dimension"). The human doesn't need to specify a distance metric or a value of K. They just react to what they see, and the system adapts.

### Baseline Capabilities

At a minimum, the system should be able to:

- Ingest a dataset and produce an initial clustering with natural language descriptions of each cluster.
- Support a conversational loop: the user gives feedback, the system re-clusters (or adjusts), and presents the updated result.
- Handle feedback at multiple levels: global ("too many clusters"), cluster-level ("split this one"), and point-level ("this item is in the wrong group").
- Produce soft assignments—a point can belong partially to multiple clusters—and communicate uncertainty ("this point is on the boundary between A and B").
- Maintain a coherent state across turns: remember what the user said earlier, even if later feedback partially contradicts it.

### Design Considerations

Some questions to think about:

- What representation do you cluster over? Raw features? Embeddings? Does the user get to influence this?
- How does the system decide what to ask the user? Showing every intermediate state is overwhelming. Can it identify the most informative question to ask next?
- How do you reconcile contradictory feedback? The user said "merge A and B" three turns ago but now says "A and B are too different." Which instruction wins? How do you handle preference drift?
- Can the system explain its decisions? "I put x in cluster A because..." is much more useful than silently re-assigning points.
- What happens with hierarchy? Can the user drill into a cluster and ask for sub-clusters? Can they zoom out and ask for a coarser grouping?

**Where KDD techniques apply.** This project lives at the intersection of AI agents and core KDD methods. The clustering itself requires choosing and implementing algorithms (K-means, DBSCAN, hierarchical methods), distance metrics (Euclidean, cosine, Jaccard—and the choice matters), and embeddings to represent items in a space where distance is meaningful. Soft clustering maps naturally to probability distributions over assignments. The conversational aspect requires the agent to reason about which points are most uncertain (highest entropy in their cluster assignment) and prioritize those for user feedback—an active learning problem. Graph representations can capture cluster hierarchies and point-cluster relationships. And the entire evaluation challenge is a KDD problem: how do you measure the quality of a clustering when there is no ground truth, only an oracle with evolving preferences?

### Things Worth Measuring

Your evaluation should serve the three grading pillars — design alternatives, honest experiments, clear communication. Here are starting points for this project:

- **Convergence rate**: does feedback become less corrective over turns? (but is that convergence or fatigue?)
- **Conversational efficiency**: turns to reach a satisfactory clustering — not all turns are equal
- **Contradiction handling**: inject synthetic contradictions and measure whether the system notices
- **Clustering quality without ground truth**: silhouette scores, user satisfaction ratings, soft assignment calibration
- **User study design**: within-subject comparisons maximize signal per participant — plan for wide confidence intervals

---

## Evaluation: The Hard Part

> *"Any measurement, without knowledge of the uncertainty, is meaningless."*
> — Walter Lewin, MIT

Evaluation is not a section you bolt onto the end of your project. It's the core intellectual challenge, and it accounts for a significant portion of your grade. In this course we argue that **better eval beats better dev**—that investing in understanding what your system actually does is more valuable than tweaking it blindly. The projects are designed to make you experience this firsthand.

**A note on tools.** Many of the evaluation challenges below are KDD problems in disguise. Confidence intervals, bootstrapping, hypothesis testing, embedding-based similarity, clustering metrics, graph analysis—these are not optional extras. They are the right tools for answering "how good is my system?" with honest uncertainty bounds. If you find yourself reporting a single number without a range, you're probably missing a tool you already know how to use.

### What "Eval" Actually Means

When you evaluate your system, you are not running a test suite. You are **estimating the distribution of a random variable**—the value your system generates, execution by execution.

Each time your system runs, it produces an outcome. That outcome might be positive (found a real gap, gave a useful review, generated an interesting conversation, converged on a useful clustering) or negative (false alarm, useless feedback, shallow exchange, wasted the user's time with bad questions). The distribution of those outcomes is what matters. Your job is to form a *belief* about that distribution—and to be honest about how uncertain that belief is.

If someone asks "how good is your system?" and you say "85%," we will ask: *what is the range you would sign your name to?*

### What Does Testing Actually Look Like?

In Software 1.0, testing is clear: you write a function, you write a test, the test passes or fails. There's a spec, there's a right answer, the computer checks it. In Software 3.0—our world—almost none of this holds. The outputs are open-ended. The "right answer" is often a matter of judgment. And the system can give different answers to the same input depending on the day.

So what do you actually do?

**The ground truth problem.** For some things, ground truth exists. If your KB system says "Document A and Document B contradict each other," you can check—do they? If your review system says "this paragraph has a factual error," you can verify. These are the easy cases, and you should absolutely test them. But most of what your system produces doesn't have a single correct answer. What's the "right" review of a paper? What's the "correct" KB fix? What makes a social interaction "meaningful"? For these, ground truth is not a dataset you curate—it's a judgment you make, and that judgment is noisy.

Be very careful with golden datasets. They are useful as a starting point—but if you develop your system by looking at the golden set, then evaluate on the same golden set, you've collapsed development and testing into a single loop. Your test score will be optimistic, and you won't know by how much. If you use a golden set, at minimum keep a held-out portion you never look at during development. Better yet, evaluate on data you didn't curate yourself.

**When there's no right answer, you need a judge.** For open-ended outputs, you need something—a human, an LLM, a rubric—to look at the ⟨input, output⟩ pair and decide: is this good? This is where things get interesting and dangerous.

*Humans as judges* are the gold standard in principle, but noisy in practice. Two humans will often disagree. If you use a 3-person panel and true quality is 80%, there's a meaningful chance the panel majority will say "bad." That's not a failure of the panel; it's the reality of subjective judgment. You need multiple raters to estimate this noise, and you need to report inter-rater agreement.

*LLMs as judges* are scalable and consistent within a run, but they bring their own biases. They tend to favor verbose, well-structured outputs regardless of substance. They are sensitive to the judge prompt—small wording changes can flip 20% of borderline cases. And they may share systematic biases with the system being evaluated (especially if both use the same underlying model). Use LLM judges, but calibrate them: compare LLM judgments to human judgments on a sample, and report how well they agree.

*Rubrics* define what "good" means, but the mapping from rubric to number is a design decision that can change your results. If your rubric says 1 = bad, 2 = okay, 3 = good, and you average to get a score—you've assumed the distance between "bad" and "okay" equals the distance between "okay" and "good." That's probably wrong. Different reasonable mappings can produce different rankings between systems. Show this sensitivity, or at minimum acknowledge it.

**What to test, concretely.** Think about your system's outputs along multiple dimensions and design separate evaluations for each. For example:

- *Functional correctness*: Did the system do what it was supposed to? (Gap detection → is the gap real? Review → does the comment match the text it references? Persona → is the response in-character?)
- *Quality/usefulness*: Is the output actually helpful? (Is the KB fix factually sound? Is the review actionable? Is the conversation interesting?)
- *Failure modes*: What does the system do when it goes wrong? (Does it hallucinate? Does it repeat itself? Does it fail silently?)
- *Behavioral consistency*: Does the system behave similarly on similar inputs? Does it degrade gracefully on hard cases?

You don't need a single metric that collapses all of these into one number. In fact, you shouldn't—because that collapse hides the interesting information. A scorecard with multiple dimensions tells you *where* the system is strong and weak. A single number tells you nothing about where to improve.

### What Do You Show the Boss?

At some point, someone will want a number. A dashboard. A slide. This is inevitable and it's fine—but *how* you present matters enormously. What you show shapes what decisions get made.

**The wrong way.** A table with green/yellow/red cells and point estimates:

| Metric | Score | Status |
|--------|-------|--------|
| Accuracy | 87% | ✅ |
| Completeness | 79% | ⚠️ |
| Relevance | 91% | ✅ |

This looks decisive. It's also almost certainly misleading. It hides every source of uncertainty, invites no questions, and creates the illusion that you know more than you do.

**A better way.** The same information, presented honestly:

| Metric | Estimate | Range | Based on | Notes |
|--------|----------|-------|----------|-------|
| Accuracy | 87% | 78–93% | 90 examples, LLM judge | Judge prompt sensitivity: ±6 pts across 3 prompt variants |
| Completeness | 79% | 68–88% | 90 examples, LLM judge | Test set skews toward simple cases; production may be lower |
| Relevance | 91% | 84–96% | 90 examples, LLM judge | High agreement across judge variants; most confident metric |

This table says less with false precision and more with honest information. It invites the right questions: "Can we narrow the accuracy range?" "What would it take to test on harder cases?" "Why is completeness uncertain?" These are exactly the questions that lead to better systems.

**Business assertions.** Beyond metrics, think about what you *expect* your system to do in operational terms—and state those expectations explicitly:

- "I expect our KB system to flag 10–30 gaps per 100 documents, not 2 and not 200."
- "I expect at least 60% of generated reviews to contain at least one actionable suggestion."
- "I expect agent personas to be distinguishable by a blind rater at least 70% of the time."
- "I expect users to need fewer corrective turns over the course of a clustering session—say, 50% fewer corrections in the last 5 turns than in the first 5."

These are business assertions—they express your beliefs about how the system should behave. When reality deviates, you learn something. When it matches, you gain confidence. Either way, you've made your expectations explicit, which is the precondition for any serious evaluation.

**What a good project presentation looks like.** When you present your project, we want to see:

1. *What you measured and how* — your metrics, your judge, your rubric, your test data.
2. *What the results are, with uncertainty* — ranges, not just point estimates. Spread across judge variants if applicable.
3. *What you're confident about and what you're not* — which metrics are stable, which are noisy, where your test set is weak.
4. *What you would do with more time* — how would you reduce the uncertainty? What data would you collect? What experiments would you run?

This is what it means to stand behind your numbers. Not to claim they're right—but to know how wrong they might be, and to be able to say so.

### The Three Problems You Will Face

Every project will encounter three interrelated challenges:

**The visibility problem.** Uncertainty exists in your measurements, but nothing in your pipeline surfaces it. Your evaluation gives you a number—say, 82%. That number feels solid. It isn't. With 100 test cases at 82% accuracy, sampling alone gives you a 95% confidence interval roughly 16 points wide—74% to 90%. And that's the *optimistic* case, because it assumes the only source of error is sample size. It never is.

**The culture problem.** You will be tempted to report your best number without qualification. It looks stronger. It's easier to present. This is exactly the instinct that leads organizations to make bad decisions on AI products. We are asking you to resist it. Report what you know *and* what you don't know. A range is more informative than a point estimate. "I don't know" is a valid and valuable answer, as long as you can explain *why* you don't know and *what it would take* to find out.

**The action problem.** Even when you see the uncertainty, you may not know what to do about it. Should you collect more data? Use a better judge? Change the metric? Run a paired comparison? Part of the project is learning to make these decisions. We don't expect you to eliminate uncertainty—we expect you to manage it.

### Sources of Error You Must Consider

Not all of these will apply to your project, but you should think about which ones do:

**Small test sets.** If you're evaluating on 50 or 100 examples, your confidence intervals are wide. Know how wide.

**Multiple hypothesis testing (the "winner's bonus").** If you tried many variants and report the best score, that score is systematically optimistic. The expected inflation grows with the number of variants and the noise in your measurement. With 10 variants and σ ≈ 4 points, the best-looking score is inflated by about 6 points on average—even if none of the variants are truly better than the baseline.

**Developer-induced overfit.** If you developed your system by looking at the same examples you're evaluating on, you've tuned to those examples—consciously or not. A test accuracy of 88% might translate to production accuracy of 65–78%. The test score alone cannot tell you which.

**LLM judge noise and prompt sensitivity.** If you're using an LLM to judge quality, that judge is noisy. Small changes in the judge prompt can move scores by 10–20+ points. This isn't a minor implementation detail—it's a fundamental source of uncertainty. Run your evaluation with at least two or three reasonable judge prompt variants and report the spread.

**Rubric mapping artifacts.** How you convert qualitative judgments to numbers matters more than you think. Three systems with identical average scores can have radically different behavior (one consistent, one bimodal, one mediocre-but-safe). Show the distribution, not just the mean.

**Subjectivity.** For many of the qualities you'll measure—"usefulness," "meaningfulness," "correctness" of open-ended outputs—reasonable people will disagree. That disagreement is not a bug in your evaluation; it's a feature of the domain. Measure it. Report it. Don't hide it behind a single number.

### What Good Evaluation Looks Like

We're not asking for perfection. We're asking for honesty and rigor. Here is what separates a strong evaluation from a weak one:

| Weak | Strong |
|------|--------|
| "Accuracy is 84%" | "We estimate accuracy between 75% and 90%, based on 80 examples. Our test set over-represents simple cases." |
| "We improved from 78% to 85%" | "The best of our 8 variants scored 85%, but with σ ≈ 5 pts the winner's bonus alone accounts for ~5 points. We cannot confidently say this variant is better than the baseline." |
| "We used GPT-4 as a judge" | "We ran three judge prompt variants. Scores ranged from 71% to 86%. The spread tells us our measurement instrument is noisy." |
| "Our system works well" | "Our system works well on the types of inputs in our test set. We have not tested on [X, Y, Z] and we suspect performance would be lower there." |

The left column gets you a number. The right column gets you *knowledge*—and knowledge is what lets you make good decisions about your system.

### Why This Matters

If you have reliable eval, improving your system is almost mechanical—you know the gradient, you know where to focus, you can tell whether each change helped. AI can even do the improving for you, if the eval is trustworthy.

If you don't have reliable eval, every iteration is a coin flip. You're optimizing in the dark.

The teams that invest in eval will compound improvements. The teams that don't will spin—whether they have 2 people or 20.

### Scope

These projects are meant to be ambitious but achievable within the course timeline. Start with the baseline capabilities and expand from there. A well-executed simple version beats a broken complex one.

The same applies to evaluation: a small, honest evaluation that acknowledges its limits is worth more than an elaborate one that hides its uncertainty.

### Working Process

**We expect visible, steady progress every week.** Your project repository on GitHub is your primary artifact — not just for the final deliverable, but for the entire development process.

Concretely:

- Commit and push work **at least weekly**. We will check commit history.
- Weeks with no GitHub activity will be noticed and will count against you. If you're stuck, commit what you have — a failing experiment, a write-up of what you tried, updated evaluation notes. Silence is worse than a dead end.
- Use commits to show your thinking, not just your code. Meaningful commit messages, updated docs, and evaluation logs all count as progress.
- This is not about volume — a week with three thoughtful commits that show you wrestled with a design decision is better than a week with fifty auto-generated files.
- **Use GitHub Issues to track your work.** Break your project into concrete tasks and create issues for them. Reference issues in your commits (e.g., `fixes #3`). Close them as you go. This is how we see not just what you did, but what you planned to do — and how your plan evolved. Aim for roughly 3–5 active issues per week. An issue stuck "in progress" for three weeks with no linked commits tells a story too.

Why? Because real engineering work is incremental. A project that materializes fully formed in the last week tells us nothing about how you think, how you debug, or how you respond to problems — and it's usually worse than one that was built and tested iteratively.

### Testing

AI projects have two kinds of tests. You need both.

**Deterministic tests** cover the parts of your system that have right answers: data ingestion, parsing, tool execution, state management, API wrappers. These are standard unit and integration tests. If your system extracts facts from documents, test the extractor. If it calls tools, test that the tools do what they claim. If it builds a knowledge graph, test that edges are created correctly. These tests should be fast, free, and deterministic.

**Eval suite** covers LLM outputs — the parts that don't have a single right answer. These run your system on your golden dataset and score the results (via LLM judge, rubric, or heuristic). They won't pass/fail cleanly — they produce scores and distributions. That's fine. They should still be automated and runnable, not something you do by hand in a notebook and eyeball.

Concretely:

- Use `pytest`. Your entire deterministic test suite should run with a single command: `uv run pytest`.
- Set up **GitHub Actions** to run deterministic tests on every push. A broken push should be visible immediately — to you and to us.
- The eval suite can be a separate command (e.g., `uv run pytest tests/eval/ --slow`) since it calls LLMs and costs money. But it must be scripted and reproducible, not manual.
- **Write tests as you build, not after.** If you add a tool, add a test for it in the same commit. If you add a new evaluation metric, add a test that runs it on a small sample. Tests that arrive in a single bulk commit at the end are worth less than tests that grew alongside the code.

Why? Because untested code is code you don't understand. You may think your document parser handles edge cases — but until there's a test that feeds it a malformed document, you're guessing. And in AI systems, where the LLM parts are inherently unpredictable, the least you can do is make sure the deterministic parts actually work.

---

*This is a living document. Ideas, scope, and details will evolve as we discuss them.*
