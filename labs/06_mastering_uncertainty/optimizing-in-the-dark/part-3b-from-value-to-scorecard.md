# From Value to Scorecards: Enabling Effective Dev Iterations

Part 3b of *Iterating in the Dark:
Organizational Blindness in AI Evaluations*

*Knowing where to improve*

← [Part 3: Better "Evals" Beats Better Dev](./part-3-value-of-better-measurement.md) | [Series Index](./index.md)

---

## From Value to Scorecard: Knowing Where to Improve

So far we've talked about V (value) as a single number. But in practice, value is composed of multiple factors.
Think back to the loss profile from Part 1:

<figure>
<img src="./images/loss_flat.png" alt="Loss profile optimization landscape" />
<figcaption>The loss landscape has many dimensions—each representing a different quality axis</figcaption>
</figure>

This multi-dimensional surface maps to a *scorecard*—a breakdown of value into measurable components:

- **Latency**: How fast does the agent respond?
- **"Precision"**: Does it get provide useful suggestions?
- **Fluency (German)**: How natural is the German output?
- **Fluency (English)**: How natural is the English output?
- **"Recall"**: Does it uncover all relevant suggestions?
- **Safety**: Does it avoid harmful outputs?
- **Cost**: How much does it cost to run?


Each dimension is an axis along which we can improve. And critically, **if we can measure these dimensions reliably, we know where to focus engineering effort**.

This is the second way better eval leads to better quality: not just through better deployment decisions, but through **directed improvement**.

Consider two scenarios:

**Scenario A: Poor scorecard measurement**
- You know the agent is "not great" but not why
- Engineers try random improvements
- Some work, some don't, you're not sure which
- Progress is slow and uncertain

**Scenario B: Good scorecard measurement**
- You know German fluency is at 65%, English at 92%, accuracy at 88%
- Engineers focus specifically on German fluency
- You can measure whether each change helps
- Progress is fast and directed

Conversely, if we cannot measure scorecard metrics properly, we cannot understand where to act. We're flying blind—iterating toward a random target, as we discussed in Part 1.

---
And yes, you guessed it - every dimension, every metric is a random variable, just like our "value".

---

## Finding What Matters: Correlation as a Shortcut

Sometimes it's hard to come up with a good scorecard from first principles. What dimensions actually matter to customers? Is latency more important than fluency? Does accuracy matter more than compliance?
There's an empirical shortcut:

1. **Build a rich scorecard** — many dimensions, even speculative ones
2. **Measure actual value** — ask customers directly, or observe outcomes (adoption, complaints, escalations)--> this is easier than you think, just try
3. **Identify correlations** — which scorecard dimensions predict customer value?
4. **Focus on what matters** — now you know which aspects of the scorecard are useful and which are secondary

**This is extremely powerful.** You don't   necessarily need to know in advance exactly what matters. You can discover it empirically.
And you don't need a lot of data to begin to see patterns. it just takes a study and sit down with some design partners or customers.

For example, you might hypothesize that latency matters a lot. But after measuring, you discover that customers don't complain about latency until it exceeds 5 seconds—below that, they don't notice. Meanwhile, every 10% improvement in German fluency correlates with a 15% increase in adoption among German-speaking users.

Now you know: optimize German fluency, not latency. Without the correlation analysis, you might have spent months shaving milliseconds off response time while the real problem went unaddressed.
You dont need a thousands data points for this - after a few dozens you'll start having a good insight on where to focus.

---

*Next: [Part 4: Sources of Bias and Uncertainty](./part-4-sources-of-error.md) — Where evaluation uncertainty comes from*

