# A Brief History of Evals

*From deterministic tests to probabilistic judgments: how our eval muscles got weaker*

---

To understand how we got to the current state of eval and how we think about eval, we need to trace the recent history of software development. To do so, I will borrow—and slightly modify—[Andrej Karpathy's definition of Software 1.0, 2.0 and 3.0](https://www.youtube.com/watch?v=LCEmiRjPEtQ). I will reinterpret the definitions slightly to adapt them to the present discussion.

**Software 1.0** is "traditional" software written by humans, executed by computers.

**Software 2.0** is ML Models—typically models learned from data.

**Software 3.0** is Gen AI Applications, such as AI agents or other applications where the main functionality is powered by LLMs. The program here is at least in part in natural language (prompts).

I am interested in studying quality and eval in these types of software applications based on the following four dimensions:

1. **What constitutes progress**, and what counts as an iteration or sprint—what does it mean to move forward in Software 1.0 vs 2.0 vs 3.0?

2. **How we define and measure quality**—which metrics we use, how we aggregate them, and how we decide that something is "good enough" to ship. And specifically, which are the dimensions of variability and how we approach uncertainty.

3. **Who achieves and measures progress**—which personas are actually building, evaluating, and signing off on quality (dev engineers, QA, data scientists, PMs, process owners, "prompt engineers", etc.).

4. **Which engineering processes and practices teams follow**—from repo management and reviews to experimentation workflows, eval pipelines, and decision rituals.

![](./images/image7.png)

In the rest of this section I'll use these lenses to contrast Software 1.0, 2.0, and 3.0 and show how our eval muscles get progressively weaker as we move from deterministic code to open-ended gen AI applications.

---

## The Evolution at a Glance

Before diving into each software "era" in turn, here's a single view comparing them along the four dimensions:

| Dimension | Software 1.0 (Traditional) | Software 2.0 (ML Models) | Software 3.0 (Gen AI) |
|-----------|---------------------------|-------------------------|----------------------|
| **What constitutes progress / an iteration?** | Shipping new features and fixing bugs. Each sprint delivers code changes against a spec. | Improving model quality and latency on a well-defined prediction task (e.g., better accuracy, lower error). | Improving end-to-end agent or service quality and latency on complex, open-ended tasks (often loosely specified). |
| **How we define and measure quality** | Feature completeness, pass/fail test suites, number and severity of defects, SLIs/SLOs. | Statistical metrics: accuracy, precision/recall/F1, ROC–AUC, calibration, plus some business KPIs. Still somewhat arbitrary in how they are combined. | Composite scorecards mixing task success, "technical accuracy," safety, UX, latency, cost, etc. Often judged by humans or LLMs and aggregated in opaque ways. Definitions are unstable and under-specified. |
| **Who achieves and measures progress** | Dev engineers build; QA/test engineers and sometimes SREs own validation and sign-off. | Data scientists/ML engineers develop and evaluate; PMs or process owners help define metrics and thresholds. | Software engineers, PMs, process owners, "prompt/agent designers" all modify behavior. Evaluation is done by a combination of teams sometimes with unclear ownership. |
| **Engineering processes and practices** | Mature practices: version control, code review, CI/CD, test strategies, acceptance testing, change management. Clear RACI. Behavior is expected to be predictable, with no surprises. | Mix of software practices and ad hoc experiment pipelines. Model and data versioning are brittle. A/B tests and offline evals are common. RACI exists but is still evolving. | Inconsistent and emergent practices. Prompt and workflow changes can bypass normal review. Eval pipelines and data management are ad hoc; documentation is patchy. RACI is unclear and ownership blurred between the model provider, platform, and application team. |

---

## Software 1.0: Clear Processes, Predictable Outcomes

In "Software 1.0" the gap between what we *measure* and what we *ship* is relatively well understood. Processes are fairly predictable, work follows design, review, and approval cycles.

### What constitutes progress / an iteration

In traditional software, progress is measured in terms of new features and closed defects. A sprint is successful if user stories moved to *Done* and the regression suite stays green. When something breaks, we can usually point at a line of code, a diff, a missing if-statement. There's a stack trace. There's a bug ID. There's maybe also a person on the hook.

### How we define and measure quality

Evaluation, in this world, is just an extension of **specification**: someone writes down what the system should do (a spec, a user story, acceptance criteria); we encode that into test cases; the system either passes or fails those tests.

Quality is measured in artifacts we've collectively learned to trust: percentage of tests passing, number and severity of open defects, performance, security, and so on.

This approach is not perfect: tests don't cover everything, users do weird things, and there are always unknown unknowns. But when a release has 5 critical bugs open, everyone in the room has an intuition for what that means.

*There is a shared understanding between the numbers we report and the real risk we are taking.*

This is important, because it sets up a mental model that many teams still apply to AI systems: In Software 1.0 if our tests are good, a "green build" really is a strong signal.

### Who achieves and measures progress

The organizational structure reinforces this clarity:

- **Dev engineers** write code and fix bugs.
- **QA/test engineers** own regression suites and sign-off.
- Sometimes **SREs** own production SLIs/SLOs and error budgets.

### Engineering processes and practices

The engineering practices around this are mature: code review, CI/CD, version control, staging environments, change requests. Almost everything that changes behavior goes through a visible artifact and an approval cycle—a pull request, a test plan, a deployment pipeline.

We've spent decades building this muscle. We know how to test deterministic systems, we know how to gate releases, and we know how to have arguments about risk in terms everyone recognizes.

There is also a clear *RACI* around quality. Someone is explicitly accountable for saying "yes, we're good enough" and for stopping a release when the signals look wrong.

---

## Software 2.0: Statistical Signals on Shifting Ground

With Software 2.0, we move from deterministic code to ML models trained from data. Let's take the example of a model that predicts the intent or type of an HR-related customer support request. Let's assume the model is trained for ACME Inc, on ACME data.

### What constitutes progress / an iteration

In Software 2.0, "progress" is usually defined as: the model got better on some metric, for some dataset.

An iteration might mean:

- trying a new model architecture,
- adding features or signals,
- tuning hyperparameters or the loss function,
- collecting more data or labels.

If the offline metric goes up—accuracy from 82% to 86%, or AUC from 0.91 to 0.94—we call that an improvement. A sprint "went well" if the new model version beats the baseline on the validation set and doesn't blow up latency.

This is more fragile than Software 1.0, but *if* we have identified good metrics, if the dataset is "representative enough" and "large enough", if we are careful to avoid overly reusing the test set and generally follow established "best practices", then we are not in a bad place. Still, the relationship between that improvement and what happens in production is less certain—especially when data drifts over time.

### How we define and measure quality

In principle, Software 2.0 is where we should shine: machine learning is built on statistics, the science is well established, we often have lots of data. And, it's the right data—as we train on customer's records.

In practice, we have many knobs to turn in our eval. As a simple example, consider two models that predict the users' intent in HR customer support requests.

One model might be broadly okay but occasionally wrong on important requests—those that we really want to get right—while the other may be worse overall but better on important requests. Yet another model might abstain more often ("I don't know"), but be rock-solid when it does predict. Depending on whether you value *coverage* or *safety*, the "better" model changes.

![](./images/image8.png)

![](./images/image9.png)

The problem extends beyond classifiers. Even for well-established functions such as search, people debate whether precision@K or recall@K is more suitable, how much to weigh the position of the link clicked... and this is of course before gen AI turned the table and added the possibility of having a direct answer to the search question rather than proposing links.

### Who achieves and measures progress

An important factor in handling evaluations well is that both the progression and the assessment often involved *experts in the science of experimentation*.

- **Data scientists/ML engineers** now own a big part of both development and evaluation. They choose metrics, design experiments, and prepare the famous "model card" or scorecard.
- **PMs and process owners** may help define what "good" means (e.g., trade-offs between false positives and false negatives, or latency vs accuracy), but often defer to the data scientists on the details.
- Traditional **QA** plays a somewhat different role, getting involved mainly at the API or integration level.

### Engineering processes and practices

On the process side, Software 2.0 is a hit and miss, and very much depends on the specific platform.

Vendors often reuse some Software 1.0 practices, such as version control, experiment tracking, model registries, and sometimes feature stores, offline/online evaluation pipelines. A lot still happens in notebooks, ad hoc scripts, and one-off dashboards, often lost in experimentations.

Two important consequences for evaluation:

1. **Versioning is brittle.** It's surprisingly easy to lose track of which data snapshot, label set, and code version produced a given metric. Reproducing an eval six months later can be non-trivial.

2. **Many decisions remain implicit.** Sampling strategies, label guidelines, exclusion criteria, and metric definitions often live in someone's head, or in a half-finished Confluence page. They rarely make it into the slide where we show "Accuracy: 86%."

**Sources of variability**: Even in Software 2.0, before we get anywhere near gen AI, we already have multiple hidden sources of variability:

- variability from the data we sampled,
- variability from how the labels were produced (and by whom),
- variability from the choice and aggregation of metrics,
- variability from how many times we tested different variants on the same dataset,
- bias resulting from multiple hypotheses testing on the same test set, and some degree of overfitting.

Most teams have an intuitive sense that "eval is hard"—but few have a concrete picture of how many dimensions of randomness and bias they're juggling.

At the same time, Software 2.0 still has important anchors:

- Tasks are usually **well-defined** (classification, regression, ranking).
- We often have **explicit ground truth labels** for at least some of the data.
- We have large datasets that are representative of what the model will see in production.

---

# Software 3.0: Gen AI Applications and the Risk of Organizational Blindness

## A Running Example: The Legal Proceedings Summarizer

To make the challenges of Software 3.0 concrete, let's follow a single example: an AI-powered system that summarizes legal proceedings.

A user provides a legal docket—complaints, motions, rulings, settlement documents—and the system produces a concise summary:

> *"2005 class action settlement resulted in Ford paying $8.55m to redesign its selection process for apprenticeship programs to address the previous process's disparate impact on Black applicants."*

![](./images/image10.png)

In simple cases the agent will just do a summary. In more sophisticated implementations it will connect to a variety of tools to fetch related contextual information to provide a more informed summary. We build it, run our evaluation based on company-provided guidelines for metrics, eval metrics, and eval tools, rely on a carefully curated set of 50 or 100 "ground truth" examples, and get a scorecard:

| Metric | Score |
|--------|-------|
| Technical Accuracy | 89% |
| Calling Correctness | 29% |
| Completeness | 84% |
| Overall Estimated Customer Value | 87% |

Let's make a big leap of faith and assume these metrics are the ones that matter, as the problem is complex enough even with this assumption. **How reliable are these numbers? Should we ask this question? And how should we act based on the answer?**

---

## Context: A Perfect Storm

Understanding organizations' approach and response to Gen AI eval requires a reflection on the rapidity and scale of gen AI adoption—a pace unprecedented in software history.

According to McKinsey's 2025 survey, 88% of organizations now report using AI in at least one business function. The use of generative AI specifically has jumped from near-zero to 65% adoption in just two years. And this isn't experimentation anymore—38% of organizations report they are scaling or have fully scaled AI deployment across their enterprise.

![](./images/image11.png)

These numbers represent thousands of AI-powered features, agents, and services being built and shipped every quarter.

Several factors converge to create this situation:

1. **Gen AI is genuinely good.**

2. **It applies to high-value use cases.**

3. **It's easy to use.** Almost anyone who can write a sentence can write a prompt. A product manager can prototype an AI feature in an afternoon. A business analyst can build a working demo without writing code. The barrier to entry has collapsed. *Hint: this is a double-edge sword.*

4. **CEOs have watched their kids use GPT** to write essays, plan trips, debug homework problems. It works. It's impressive. It's *easy*. This creates a reference point: if a teenager can get useful results in minutes, surely a well-resourced engineering team can build reliable AI applications?

This reference point shapes expectations. If gen AI is this capable and this easy, then adoption should be fast, results should be good, and failures are hard to accept. "We're struggling with our AI project" sounds like an excuse when the CEO's kids built something useful over the weekend.

This creates a perfect storm for evaluation:

- High pressure to ship (the technology works, competitors are moving, executives expect results)
- High confidence in outcomes (everyone has seen it work)
- Low appreciation for the difficulty of verification (the hard part is invisible)
- Many people building, few people equipped to evaluate

The asymmetry is stark: **the barrier to *building* gen AI applications has dropped dramatically, while the difficulty of *evaluating* whether they actually work has not dropped at all.** If anything, it has increased.

---

## What Constitutes Progress? What's an Iteration?

In Software 3.0, progress generally means improving on the metrics we think are important. Iterations may include:

- Revise the prompt
- Switch to a different model
- Add or remove tools the agent can access
- Modify the orchestration logic
- Update the retrieval system
- Adjust the guardrails

Each of these is an iteration. Each could affect quality. Notice that since modifications are "easy", we do tend to create a large set of variations—especially in terms of prompt.

---

## Who Achieves and Measures Progress?

In Software 3.0, the set of people that builds and evals applications expands greatly. Both PMs and engineers contribute to both dev and eval.

Most importantly, many people *feel qualified to evaluate*, even though evals are far from trivial and include *many moving parts, controlled by different persons—even different teams.*

We may have a team of linguists generating ground truth labels, based on guidelines defined by data scientists, working over a synthetic dataset generated by another team, using a dataset generation tool crafted by yet another team. Eval can be done using a metric and a prompt recommended by yet another team... and this is a very partial list (more to come later).

There is also an ecosystem of roles and teams that provide guidance and tools to support evaluations in some shape or form.

---

## How We Define and Measure Quality

This is the heart of the problem. Let's see different approaches and reflect on them.

### First idea: Vibe evals

In the "beginning", at the onset of GPT 3.5, quality was often assessed by companies using "vibe evals". This was popular until two things happened:

First, teams started **"overfitting to the CTO"**. You had the CTO doing vibe evals, teams logging the CTO test prompts, and adding those tests (with the answers believed to be what the CTO expected) as examples (in-context learning). This generated a manifest difference between expected and actual quality in prod.

Second, PMs generally started requesting that eval become more systematic.

This does not mean that vibe eval has been abandoned: I believe it is the primary method of eval by developers when iterating over a solution, even today, mainly to pick the version that undergoes a more "structured" evaluation.

### Next idea: metrics and golden datasets

The approach: define metrics (e.g., technical accuracy, completeness, correctness), hand-curate a dataset of test cases with ground truth, measure systematically. This produces scorecards. Numbers. Dashboards. It feels rigorous.

**But let's look at what these numbers actually tell us—and what they don't.**

To "demonstrate" that:

1. there is a large uncertainty in evals, and
2. this is more than we think,

I'll proceed with detailed examples in a later discussion. I will also show which solutions do not work (and can, in fact, backfire), and why. Then, we'll see if we can instead try to make some progress.

---

**Tags:** `AI` `Machine Learning` `Evaluation` `MLOps` `AI Engineering`
