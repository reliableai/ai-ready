# Chat Panel Design: "Discuss with AI"

## Overview

A sidebar chat panel that allows readers to discuss the article content with an AI assistant. The AI has context about the article and can answer questions, explain concepts, and help readers apply the ideas to their own situations.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Article Content                    │  Chat Panel (collapsible)
│                                     │  ┌─────────────────────┐
│  [Entry Point Button]               │  │ Discuss with AI     │
│                                     │  ├─────────────────────┤
│  Section content...                 │  │ [conversation]      │
│                                     │  │                     │
│  [Entry Point Button]               │  │                     │
│                                     │  ├─────────────────────┤
│                                     │  │ [input] [send]      │
│                                     │  └─────────────────────┘
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Chat Panel (Sidebar)
- **Position**: Fixed right sidebar, collapsible
- **Toggle**: Button in corner or triggered by entry points
- **State**: Persists across page navigation (localStorage)

### 2. Entry Points
Clickable buttons/links scattered through the article that:
- Open the chat panel (if closed)
- Pre-fill or send a specific question
- Highlight which section the question relates to

### 3. Backend/API
- **Option A**: Direct OpenAI API call from client (requires exposed key - not ideal for public)
- **Option B**: Proxy backend that holds API key and manages sessions
- **Option C**: Use OpenAI Assistants API with thread management

**Recommended**: Option B or C for production; Option A acceptable for internal/teaching use.

### 4. Context Management
- System prompt includes article summary and key concepts
- Conversation history stored per user (localStorage or backend)
- Each user gets isolated conversation context

---

## Entry Points

### Global Entry Points (appear in sidebar or header)
| ID | Label | Prompt |
|----|-------|--------|
| `global-summary` | "Summarize key takeaways" | "What are the 3-5 most important takeaways from this article series?" |
| `global-apply` | "How does this apply to me?" | "I work on AI systems. How should I apply these ideas to my evaluation process?" |
| `global-checklist` | "Give me a checklist" | "Create a practical checklist I can use when reviewing AI evaluation results." |
| `global-skeptic` | "Play devil's advocate" | "What are the strongest counterarguments to the claims in this article?" |

### Part 1: A Structural Flaw in Judgment
| ID | Section | Label | Prompt |
|----|---------|-------|--------|
| `p1-89` | Intro | "Why is 89% misleading?" | "The article says '89% accuracy' might be meaningless. Can you explain why with a concrete example?" |
| `p1-three-facets` | Three Facets | "Explain the three facets" | "What are the three facets of the problem (visibility, culture, action) and how do they interact?" |
| `p1-random-target` | Iterating | "Random target?" | "What does 'iterating toward a random target' mean? How would I know if my team is doing this?" |

### Part 2: The Cost of Ignorance
| ID | Section | Label | Prompt |
|----|---------|-------|--------|
| `p2-value-dist` | Shape of Value | "Explain value distributions" | "Help me understand why value is a distribution, not a single number. Use a real-world example." |
| `p2-bias-noise` | Bias vs Noise | "Bias vs noise?" | "What's the difference between bias and noise in evaluation? Which is worse?" |
| `p2-cost` | Cost of Errors | "Calculate my cost" | "Help me estimate the cost of evaluation errors for my specific situation. What information do you need?" |

### Part 3: Better Evals Beats Better Dev
| ID | Section | Label | Prompt |
|----|---------|-------|--------|
| `p3-mxc` | M×C Matrix | "Explain M×C matrix" | "Walk me through the M×C matrix concept. How would I build one for my organization?" |
| `p3-uncertainty-variability` | Uncertainty vs Variability | "Uncertainty vs variability?" | "I'm confused about uncertainty vs variability. Can you give me a concrete example of each?" |
| `p3-better-eval` | Better Eval | "Why eval > engineering?" | "The article claims investing in eval is more valuable than investing in engineering. Convince me." |
| `p3-scorecard` | Scorecard | "Design a scorecard" | "Help me design a scorecard for my AI agent. What dimensions should I include?" |

### Part 4: Sources of Bias and Uncertainty
| ID | Section | Label | Prompt |
|----|---------|-------|--------|
| `p4-sample-size` | Sample Size | "How many samples?" | "How many test samples do I need for reliable evaluation? Help me calculate for my case." |
| `p4-multiple-hypothesis` | Multiple Hypothesis | "Best-of-K problem" | "Explain the multiple hypothesis testing problem. I run 10 prompt variants - how inflated are my results?" |
| `p4-overfit` | Developer Overfit | "Am I overfitting?" | "How do I know if my team is overfitting to the test set? What are the warning signs?" |
| `p4-judge` | LLM Judges | "Judge reliability?" | "How reliable are LLM judges? What can I do to improve judge consistency?" |
| `p4-rubric` | Rubric Mapping | "Rubric problems" | "Explain why rubric mapping is problematic. How should I design my scoring rubric?" |

### Part 5: What To Do
| ID | Section | Label | Prompt |
|----|---------|-------|--------|
| `p5-mandates` | Mandates | "Mandates don't work?" | "Why do evaluation mandates fail? What should leadership do instead?" |
| `p5-raci` | Accountability | "Who's accountable?" | "Help me set up clear accountability for evaluation quality in my organization." |
| `p5-reduce` | Reduce Uncertainty | "How to reduce uncertainty?" | "What are the most practical ways to reduce evaluation uncertainty?" |
| `p5-culture` | Culture | "Change the culture" | "How do I change my organization's culture around evaluation uncertainty?" |
| `p5-questions` | Questions to Ask | "Questions to ask" | "Give me the specific questions I should ask in my next evaluation review meeting." |

---

## System Prompt (for AI context)

```
You are an AI assistant helping readers understand and apply concepts from the article series "Iterating in the Dark: Organizational Blindness in AI Evaluations" by Fabio Casati.

Key concepts from the series:
1. Evaluation metrics (like "89% accuracy") often hide significant uncertainty
2. Three facets of the problem: visibility (people don't see uncertainty), culture (organizations don't ask), action (people don't know what to do)
3. Value is a random variable with a distribution, not a single number
4. Uncertainty (reducible via better measurement) vs Variability (real-world differences)
5. Better eval enables better decisions AND better directed improvement
6. Sources of error: small samples, multiple hypothesis testing, developer overfit, eval/production mismatch, rubric mapping, noisy judges, prompt sensitivity
7. Solutions: make uncertainty visible, ask the right questions, clear accountability

Your role:
- Explain concepts from the article clearly with concrete examples
- Help readers apply ideas to their specific situations
- Be direct and practical, not academic
- If asked about something not in the article, say so and offer your best understanding
- Encourage critical thinking - don't just validate what readers want to hear

Current article context: {ARTICLE_SECTION}
```

---

## Implementation Plan

### Phase 1: Static Prototype
- [ ] Add CSS for sidebar panel layout
- [ ] Add HTML structure for chat panel
- [ ] Add entry point buttons to one article (Part 3)
- [ ] JavaScript for panel toggle and entry point clicks

### Phase 2: Basic Chat
- [ ] Connect to OpenAI API (direct call for prototype)
- [ ] Basic conversation flow (send message, display response)
- [ ] Store conversation in localStorage

### Phase 3: Context & Polish
- [ ] System prompt with article context
- [ ] Section-aware context (know which part user is reading)
- [ ] Conversation persistence across sessions
- [ ] Mobile-responsive design

### Phase 4: Production
- [ ] Backend proxy for API key security
- [ ] User session management
- [ ] Rate limiting
- [ ] Analytics (which entry points are used)

---

## File Structure

```
optimizing-in-the-dark/
├── chat-panel.css          # Sidebar styles
├── chat-panel.js           # Chat logic and API calls
├── entry-points.json       # Entry point definitions
└── parts use <script src="chat-panel.js">
```

---

## Open Questions

1. **API Key security**: For teaching use, is client-side API key acceptable? Or need backend?
2. **Model**: GPT-4o-mini for cost? GPT-4o for quality?
3. **Conversation limits**: Max messages per session? Token limits?
4. **Analytics**: Track which entry points are clicked? Store anonymized conversations for improvement?
