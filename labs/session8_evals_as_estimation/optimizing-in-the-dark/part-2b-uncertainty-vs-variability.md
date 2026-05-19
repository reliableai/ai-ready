# Uncertainty vs Variability

Part 2b of *Iterating in the Dark:
Organizational Blindness in AI Evaluations*

*When you see a range, what does it mean?*

← [Part 2: The Cost of Ignorance](./part-2-cost-of-ignorance.md) | [Series Index](./index.md)

---

> **Orientation.** This section introduces a distinction used throughout the rest of the series: *variability* describes real differences in the world, while *uncertainty* describes limits in our measurement of a metric. Confusing the two leads to systematic evaluation errors.

---

## The M×C Matrix: What You're Actually Optimizing

You have **M agents** (Incident Auto-Resolution, Incident Summarization, Knowledge Base Deduplication, Document Classification, ...) and you are considering deploying them across **C customers** (Customer A, Customer B, Customer C, ...) - or C domains, or C regions - whatever. Each cell in this matrix has a *value distribution*: V<sub>m,c</sub> - in other words, *each of these cell is a random variable*.

<figure class="mxc-matrix">
<!-- MxC Matrix visualization will go here -->
</figure>

<!-- **What's in each cell?** A distribution of value. Not a single number—a random variable. For Incident Auto-Resolution at Customer A, sometimes it saves 15 minutes, sometimes 5, sometimes it makes things worse and costs 10 minutes. The distribution captures this reality. -->

**The aggregates matter too:**
You can also consider what happens at the row and column level, that is, the value of one agent (across customers) of the value for a customer that implements some - or all - of the agents. Those are random variables, too.
And you can think about statistics such asL

- **Row totals**: E[V<sub>m,*</sub>] = expected value of agent m across all customers, or, P(E[V<sub>m,*</sub>>0) = probability that a customer will see a positive value from agent m.
- **Column totals**: E[V<sub>*,c</sub>] = expected value for customer c across all agents, or, P(E[V<sub>*,c</sub>>0) = probability that a customer will see a positive value from the agents.
- **Overall total**: E[V] across all customers and agents.

Each cell is *unknown*. We have *beliefs* about it, with varying degrees of uncertainty. 
It is very common to be uncertain about these distributions.

What is important is 1. to be aware of what we are talking about when we are discussing a metric (which cell in this figure?) and 2. be aware that we are talking about estimation of random variables (sorry to keep insisting on this....)

---

When you see distributions or "bars" around a value, you need to be sure you understand what they represent. And you want to make sure the presenter knows what they represent.

If somebody says *"We expect our incident resolution agent to have a value/cost savings of $12 per run, plus or minus $4,"* **you MUST ask what they mean**.

| What they might mean | Interpretation | Can we reduce it? |
|---------------------|----------------|-------------------|
| **Uncertainty** | "We believe the average is somewhere between $8 and $16, but we're not sure which" | **YES** — better measurement narrows the range |
| **Variability** | "We're confident the average is $12, but some customers will be around $8, some other custiomers will see $16" | **NO** — this is real-world difference, not measurement error |

This distinction is fundamental: **Uncertainty** is about our *knowledge*. It reflects the fact that we haven't measured enough, or our measurements are noisy, or our judges are inconsistent. Uncertainty can be reduced by:
- Larger test sets
- Better sampling
- More consistent evaluation criteria
- Multiple judges with adjudication

**Variability** is about different target customers or domains. It reflects the fact that different deployments of the same agent will have different data quality, different languages, different processes. Variability across customers (the fact that E[V<sub>m,c1</sub>] ≠ E[V<sub>m,c2</sub>]) cannot be reduced via better measurement. It can only be addressed via:
- More adaptive agent implementations
- Selective deployment (only deploy where E[V] > 0)
- Better matching of agents to customer characteristics

<!-- **The questions you must ask:**
1. "Is that uncertainty or variability?"
2. "Does the presenter even know what they mean?"

When someone presents a range and can't answer these questions, the number is not just uncertain—it's *uninterpretable*.
 -->


<!-- ## One Agent, Many Customers

So far in Part 2 we discussed M agents for one customer. But there's another dimension: deploying one agent across N customers.

This introduces a different kind of uncertainty — one that better measurement can *reveal* but cannot *reduce*.

You have one agent — say, Incident Auto-Resolution — and 10 customers considering deployment. You've evaluated thoroughly and you're confident: E[V] = +8, range [+5, +11].

Should you deploy to all 10 customers?

Your evaluation was done on some dataset — maybe a mix of data from several customers, maybe synthetic data, maybe data from your most engaged pilot customer.

But each customer's data is different:
- Customer A has clean, well-structured tickets with consistent formatting
- Customer B has messy tickets with lots of jargon and abbreviations
- Customer C has tickets in multiple languages
- Customer D has a ticket system that truncates long descriptions

The agent might perform very differently across these environments. Your confident E[V] = +8 might actually be:

| Customer | True E[V] |
|----------|-----------|
| A | +15 |
| B | +2 |
| C | −5 |
| D | +12 |
| E | +8 |
| F | −3 |
| G | +10 |
| H | +6 |
| I | +1 |
| J | −8 |

Your aggregate evaluation gave you confidence, but the reality is: 3 out of 10 customers would be harmed.

--- -->

**This uncertainty is different**

With measurement uncertainty, better evaluation narrows your range. You become more confident about the true E[V].

With cross-customer variability:
- Better measurement makes you *more confident about the variance* — you learn precisely how much performance differs across customers
- But better measurement *doesn't reduce* the variance — it's real variability in the world, not measurement error

If you evaluate on Customer C's data, you don't make the agent work better for Customer C. You just learn that it doesn't work well there.

---

**What can you do to address variability?**

1. **Improve the system:** Make the agent more robust to different data distributions. This actually reduces the variance.

2. **Deploy selectively:** Learn which customers (or which data characteristics) predict success, and only deploy where you expect E[V] > 0.

3. **Set expectations:** If you deploy broadly, communicate that results will vary. Some customers will see great results; some won't.

The key point: this is not a measurement problem. It's a real-world variability problem. Recognizing the difference matters for deciding where to invest effort.
So we will not be focusing on this variability.

HOWEVER - remember that if you make changes and improve the agent for a customer, this does not mean other customers will see improvements - you may actually make things worse overall. It's obvious, but my experience is that this is part of the many obvious things that need to be said.

---

*Next: [Part 3: Better "Evals" Beats Better Dev](./part-3-value-of-better-measurement.md) — The value of knowing what you're measuring*

