# Lesson 2: Instructor Planning Guide

## Stateless & Stateful Agents
*Conversation history, cost and latency tradeoffs*

**Duration:** 90 minutes  
**Prerequisites:** Lesson 1 (Hello Software 3.0)  
**Prepares for:** Lesson 3 (Tools & The Agentic Loop)

---

## 1. Lesson Arc

| Time | Section | Focus |
|------|---------|-------|
| 0-10 min | Intro | Motivation: why state matters |
| 10-25 min | Stateless Agent | Live demo, observe the forgetting |
| 25-45 min | Stateful Agent | Add history, measure growth |
| 45-60 min | Cost & Latency | Analyze quadratic scaling |
| 60-80 min | Memory Systems | Implement window + summary |
| 80-90 min | Wrap-up | APIs, exercises, preview L3 |

---

## 2. Key Demonstrations

### Demo 1: The Forgetting (5 min)
Run `1_stateless_agent.py`:
```
You: My name is Alice.
Assistant: Nice to meet you, Alice!

You: What's my name?
Assistant: I don't have that information...
```
**Point:** Each turn is independent. The model literally cannot remember.

### Demo 2: The Remembering (5 min)
Run `2_stateful_agent.py` with the same conversation.
```
You: My name is Alice.
You: What's my name?
Assistant: Your name is Alice!
```
**Point:** History enables continuity—but at what cost?

### Demo 3: Watch It Grow (10 min)
Modify `2_stateful_agent.py` to print:
```python
print(f"Input tokens: {response.usage.prompt_tokens}")
print(f"Output tokens: {response.usage.completion_tokens}")
```
Have a 15-turn conversation. Track the numbers.

**Expected observation:**
- Turn 1: ~100 input tokens
- Turn 5: ~800 input tokens  
- Turn 10: ~2000 input tokens
- Turn 15: ~3500 input tokens

Draw a quick graph on the board. Ask: "Is this linear?"

### Demo 4: Memory in Action (15 min)
Run `3_agent_with_memory.py`:
1. Have a 10-turn conversation establishing facts
2. Continue until memory summary is triggered
3. Show the debug output with memory contents
4. Ask about early facts—does it still know?

**Discussion:** What got lost? What was preserved?

---

## 3. Discussion Questions

### After stateless demo:
- "In what situations is stateless actually better?"
- "What assumptions from Software 1.0 break when state is your problem?"

### After cost analysis:
- "At what point does full history become unacceptable? 50 turns? 100? 500?"
- "If you're building a customer service bot that handles 1000 conversations/day, how do you budget for this?"

### After memory demo:
- "Who decides what's important to remember? The model? The developer?"
- "How would you test whether your memory system is working correctly?"
- "What happens if the summarizer makes a mistake? How would you even know?"

### Design question:
- "Imagine you're building a coding assistant. What should it remember? What should it forget?"

---

## 4. Connection to Course Arc

### From Lesson 1:
L1 established that LLM calls are **stateless** and **non-deterministic**. L2 builds on this:
- Stateless → now we manage state ourselves
- Non-deterministic → memory summaries are also non-deterministic (lossy compression)

L1's testing section showed why exact matching fails. L2 shows another reason: **the same input produces different outputs depending on context**.

### To Lesson 3:
L3 introduces **tools**—functions the model can call. The conversation history becomes more complex:
```python
messages = [
    {"role": "user", "content": "What's the weather?"},
    {"role": "assistant", "tool_calls": [{"function": "get_weather", ...}]},
    {"role": "tool", "content": "72°F, sunny"},
    {"role": "assistant", "content": "It's 72°F and sunny!"},
]
```

The same state management challenges apply, but now with tool calls in the mix. L2's patterns (windowing, summarization) become more complex when tools are involved.

**Foreshadowing for L3:**
> "Right now our agents can only talk. What if they could *do* things—search the web, query a database, run code? That's Lesson 3."

---

## 5. Common Student Questions

**Q: Why doesn't the API just remember for us?**
A: Some APIs (Responses API) can, but it creates vendor lock-in. Chat Completions gives you control. Also: who pays for storage? Who decides what to keep?

**Q: How do commercial products (ChatGPT, Claude) handle this?**
A: They use similar strategies internally—windowing, summarization, retrieval. ChatGPT Plus has a memory feature that stores facts between sessions. Anthropic's Claude has project context.

**Q: What about RAG (Retrieval-Augmented Generation)?**
A: Great question—that's an advanced version of what we're doing. Instead of summarizing into prose, you embed conversation turns into a vector database and retrieve relevant ones. We'll touch on this in Skillset 2.

**Q: Is there a "best" window size?**
A: No. It depends on your application. A quick Q&A bot might use 2-3 turns. A coding assistant might need 20+. You tune this based on task requirements and cost constraints.

---

## 6. What Can Go Wrong

### Technical issues:
- API keys not set → check `.env` file
- Rate limits → use OpenRouter or space out demos
- Model responds differently → that's the point! Non-determinism

### Conceptual confusion:
- Students think "stateful" means the API remembers → emphasize: **you** send the state
- Students think memory solves the problem → emphasize: memory is **lossy**

### Time management:
- Cost analysis can expand → keep it tight, reference written materials
- Memory demo takes time to trigger → pre-prepare a conversation transcript

---

## 7. Materials Checklist

- [ ] `1_stateless_agent.py` — working, API key configured
- [ ] `2_stateful_agent.py` — modified to print token counts  
- [ ] `3_agent_with_memory.py` — all three SUMMARY_STYLE options ready
- [ ] Whiteboard/slides for cost growth diagram
- [ ] `chat-completions-vs-responses-api.md` — as reference material

---

## 8. Assessment Hooks

This lesson sets up exam questions around:
- Calculating cost growth (quadratic vs bounded)
- Designing memory strategies for specific use cases
- Tradeoffs between fidelity and efficiency
- API choice rationale (Chat Completions vs Responses)

**Sample exam question:**
> You're building a customer service agent that handles product returns. Conversations average 25 turns. You have a budget of $0.10 per conversation.
> 
> (a) Can you use full history with gpt-4.1-mini? Show your calculation.
> (b) Design a context management strategy that stays within budget.
> (c) What information must the agent remember? What can it forget?

---

## 9. Takeaway Statements

End the lesson with these key points:

1. **"LLMs are stateless. State is your responsibility."**

2. **"Full history doesn't scale. Cost and latency grow quadratically."**

3. **"Memory is lossy compression. You choose what to keep and what to lose."**

4. **"Memory is not a feature—it's a design decision."** (From lesson outline)

---

## 10. Bridge to Next Lesson

Preview Lesson 3:
> "Today we built agents that can *remember*. But they can only *talk*. What if they could take actions—search the web, query a database, send emails?
>
> That's where tools come in. Tools let intelligence escape the prompt.
>
> Next time: the agentic loop."
