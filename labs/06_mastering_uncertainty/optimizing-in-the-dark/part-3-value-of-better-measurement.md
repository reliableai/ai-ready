# Better "Evals" Beats Better Dev

Part 3 of *Iterating in the Dark:
Organizational Blindness in AI Evaluations*

*The value of knowing what you're measuring*

← [Part 2b: Uncertainty vs Variability](./part-2b-uncertainty-vs-variability.md) | [Series Index](./index.md)

---

## Executive Summary

> **Better eval improves customer value even if you never touch the system.**
>
> Through better deployment decisions alone—deploying what works, holding what's uncertain, avoiding what harms—you realize more value from the systems you already have.

> **If you have a team of 10 people working on AI, put 8 on evals and 2 on engineering, not the other way around.**
>
> The 2 engineers can iterate fast—AI helps them write code, test variants, try new approaches. But without reliable measurement, the engineers have no idea if their iterations are improvements. They're spinning. With reliable measures, AI can likely do the improvement by itself.

---

## Two Ways to Improve Quality

You're pouring engineering effort into making your agents better. More prompt tuning. More fine-tuning. More RAG improvements. More guardrails.

**STOP.** Do not work on dev before you have a good eval in place. 


Consider this: *when you change from Prompt 1 to Prompt 2, do you actually know which one is better?*
Not "which one scored higher on your eval." Do you know which one is *actually* better? With enough confidence to ship it?

Because that is the minimum bar: you must be able to reliably detect *directional*, meaningful improvement. If you can't confidently say "Prompt 2 is better than Prompt 1," then every iteration is a coin flip. You're not engineering. You are working at random hoping to get to a state where you can make a nice presentation to execs.

Ideally, you'd also know the *absolute* value—how much is this system worth to customers? But that is hard and may come over time. At bare minimum, you need *relative* comparison. Without that, you cannot iterate. You're optimizing in the dark.
And when you make your relative comparisons - there too you need to be aware of the uncertainty - even if it means being aware that you are no clue about it.

Now, there are two ways to improve quality and customer value:

1. **Better agents** — improve the system itself
2. **Better "eval"** — improve your knowledge of the system

Most companies focus exclusively on (1) and are not even aware that you can improve customer value just by having better evals. 
Path 1 - better systems - is almost trivial with AI—*if* you have reliable evals. 
But without reliable measurement, you don't even know if your dev cycles are going in the right direction.

---

## Better Eval Leads to Better Quality (Even Without Touching the System)

**Better eval improves realized customer value even if you never touch the agent itself.**

How? Through better *deployment decisions*.

Think about your current portfolio. You have agents in production. You have agents you held back. *How confident are you that you got those decisions right?*

If your eval has high uncertainty, some of your deployed agents are probably hurting customers. And some of your held agents are probably valuable. You just can't tell which.

Even without improving the agent, better eval lets you:
1. **Deploy where E[V] > 0 with confidence** — more good deploys
2. **Avoid deploying where E[V] < 0** — fewer harmful deploys
3. **Hold where uncertain until you know more** — avoid premature decisions

### A Worked Example

Suppose you have 10 agents and current eval quality. With your current measurements, you decide to deploy 8 of them.

**Reality (which you discover later):**
- 6 of the 8 deployed agents are genuinely valuable (✓)
- 2 of the 8 deployed agents are actually harmful (✗)
- 1 of the 2 held agents was actually valuable (missed opportunity)
- 1 of the 2 held agents was correctly held (✓)

Now suppose you invest in better eval. With improved measurement:
- You correctly identify and avoid the 2 harmful deploys
- You hold 1 uncertain agent for more data (turns out to be good, but you defer the decision)
- You deploy 1 agent that was being held back (turns out to be valuable)

**Let's quantify:**

| Outcome | Before (Poor Eval) | After (Better Eval) |
|---------|-------------------|---------------------|
| Good deploys | 6 × $10 = $60 | 7 × $10 = $70 |
| Harmful deploys | 2 × -$50 = -$100 | 0 × -$50 = $0 |
| Held (good) | 1 × $0 = $0 | 1 × $0 = $0 |
| Held (bad) | 1 × $0 = $0 | 1 × $0 = $0 |
| **Net value** | **-$40** | **+$70** |

The $110 improvement came entirely from better *decisions*, not better *agents*. The agents didn't change at all.

**Notice the asymmetry:** harmful deploys cost 5× more than the value of good deploys. This is typical in enterprise settings where trust, once lost, is hard to regain. This asymmetry makes the value of better eval even higher—avoiding one harmful deploy is worth more than making five good ones.

---

## The Value of Reducing Uncertainty

In Part 2, we saw the value of *awareness*—knowing that uncertainty exists. But what happens when you invest in *reducing* that uncertainty?

**Continuing the example from Part 2:**

You held agents B, D, and G because their uncertainty was too high. Now you invest in better evaluation—more test cases, better judges, more representative data.

The systems don't change. But your knowledge improves:

| Agent | Before | After better measurement | True E[V] | Decision |
|-------|--------|--------------------------|-----------|----------|
| B | +3 [−8, +14] | −2 [−5, +1] | −4 | Don't deploy ✓ |
| D | +6 [−15, +27] | +9 [+6, +12] | +8 | Deploy ✓ |
| G | +1 [−12, +14] | −4 [−7, −1] | −6 | Don't deploy ✓ |

With better measurement:
- **Agent B:** The range narrowed and shifted. You now see it's likely negative. You confirm the hold—correct decision.
- **Agent D:** The range narrowed dramatically. You now see it's confidently positive. You can deploy—you've unlocked value that was always there.
- **Agent G:** The range narrowed and you see it's clearly negative. You confirm the hold—correct decision.

**What reducing uncertainty gives you:**

1. **Confident deploys:** Agent D was a good system all along. You just didn't know it. Better measurement gave you the confidence to ship.

2. **Confident rejects:** Agents B and G were bad systems. Better measurement confirmed you should hold back, and now you can stop investigating them.

3. **No wasted effort:** Without better measurement, you might have kept investigating all three forever—or eventually deployed them out of impatience.

The system didn't improve. Your *knowledge* improved. And that knowledge has direct business value: you shipped a good agent you were holding back, and you stopped wasting effort on bad ones.

**The investment case for better measurement:**

Traditional framing: "We need better evals to improve our systems."

Better framing: "We need better evals to *know which systems are already good enough to ship*—and which ones aren't worth further investment."

Reducing uncertainty doesn't just help you improve. It helps you *decide*—faster, with more confidence, and with fewer mistakes.

---

*Next: [Part 3b: From Value to Scorecards](./part-3b-from-value-to-scorecard.md) — Knowing where to improve*


