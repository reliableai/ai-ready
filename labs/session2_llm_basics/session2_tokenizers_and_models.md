# Session 2 Lab — Tokenizers and Base vs. Aligned Models

**Goal:** build intuition for two things most mental models of LLMs get wrong — **how text becomes tokens** and **what "aligned" actually changes**.

**Format:** in-class, ~25 minutes. No right answers. The point is to *feel* it and discuss.

**Tools:**
- Tokenizer exploration → [tiktokenizer.vercel.app](https://tiktokenizer.vercel.app/)
- Base vs. aligned models → [app.hyperbolic.ai](https://app.hyperbolic.ai/)

Bring your laptop, jot down anything surprising, and we'll compare notes as a group.

---

## Part 1 — Tokenizers (~12 min)

Open [tiktokenizer.vercel.app](https://tiktokenizer.vercel.app/) and start with `gpt-4o` (or the latest GPT tokenizer shown). For each exercise, paste the input, look at the token count, look at the colored segmentation.

### 1.1 Numbers: long vs. short

Try:

- `42`
- `1234`
- `1000000000`
- `1,000,000,000`
- `3.14159265358979`
- `2026-04-22` (a date)
- `123456789012345` (15 digits, no separators)

**Discuss:** Do numbers stay intact or get split? Where do the splits land? Does punctuation help or hurt? What does this mean when an LLM is asked to do arithmetic?

### 1.2 Different languages / scripts

Paste the same sentence in several languages:

- English: `The quick brown fox jumps over the lazy dog.`
- Italian: `La veloce volpe marrone salta sopra il cane pigro.`
- German: `Der schnelle braune Fuchs springt über den faulen Hund.`
- Chinese: `敏捷的棕色狐狸跳过了那只懒狗。`
- Japanese: `素早い茶色のキツネは怠け者の犬を飛び越える。`
- Arabic: `الثعلب البني السريع يقفز فوق الكلب الكسول.`
- Swahili: `Mbweha wa rangi ya kahawia anaruka juu ya mbwa mvivu.`

**Discuss:** Same meaning, roughly the same length — same number of tokens? Which languages are most "expensive"? What does this imply for cost, context, and model quality across languages?

### 1.3 Code vs. prose vs. JSON

Paste each, note the token count:

```python
def hello(name: str) -> str:
    return f"Hello, {name}!"
```

```json
{"name": "Alice", "age": 30, "friends": ["Bob", "Carol"]}
```

> Alice is a 30-year-old developer who enjoys writing Python. Her closest friends are Bob and Carol, both of whom are also engineers.

**Discuss:** Which form uses the fewest tokens for the same information? Where does token cost come from in code — keywords, punctuation, indentation? When is JSON's token expense worth it? When isn't it?

### 1.4 Adversarial / degenerate inputs

Try:

- `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` (48 a's)
- `the the the the the the the the the the the the`
- ` SolidGoldMagikarp` (leading space — a famously weird "glitch token")
- A zero-width character between letters: copy `a‍b‍c‍d` (there are invisible ZWJ chars between letters)

**Discuss:** Do repeated sequences compress into fewer tokens or not? What happens at strange boundaries? What could an attacker do by crafting inputs around tokenizer quirks?

### Bonus — if time permits

- **1.5 Emoji and Unicode.** Try `👋🌍`, `🇮🇹🇯🇵🇫🇷` (flag emojis), and the same accented letter in precomposed vs. combining form (`é` vs. `é`). Do visually-identical strings tokenize the same way?
- **1.6 Compare tokenizers.** Take one of the paragraphs above and run it through `gpt-4o`, `claude-3-5-sonnet`, and `llama-3`. How different are the token counts? What would you measure if you had to pick a tokenizer for a cost-sensitive production app?

---

## Part 2 — Base vs. Aligned Models (~12 min)

Open [app.hyperbolic.ai](https://app.hyperbolic.ai/). Find a base model (e.g. `Meta-Llama-3.1-70B`) and its aligned counterpart (`Meta-Llama-3.1-70B-Instruct`). Run the same input through both and compare behaviour.

### 2.1 Completion-style prompt

Paste exactly — no instruction, no punctuation:

> The capital of France is

**Discuss:** What does the base model produce? Where does it stop? How does the aligned model's behaviour differ on *the same exact input*?

### 2.2 Open-ended prompt (rambling territory)

> Once upon a time in a small village

**Discuss:** Which model stays on task longer? Which one spirals, repeats, or drifts? Does the aligned model add "I can write a short story for you…" preamble?

### 2.3 Instruction the base model wasn't trained on

> Translate the following sentence to pirate English: "I would like a cup of tea, please."

**Discuss:** Can the base model even follow instructions? How does it interpret this input — as a task, or as text to continue? Does the aligned model comply directly?

### 2.4 Contrastive / under-specified

> List three reasons why

**Discuss:** Base: where does it go? Does it pick a topic at random? Aligned: does it ask for clarification, pick something, or refuse?

### Bonus — if time permits

- **2.5 Question vs. statement.** Ask "What is the capital of France?" to both. Does the base model answer, or does it generate more questions?
- **2.6 Style/tone prompts.** "Write a short story about two friends discussing their favourite cheeses." Compare preamble, length, structure, and tone.

---

## Closing discussion

Bring one answer (or one question) to each of these:

1. What's the **single most surprising thing** you saw during the tokenizer exercises?
2. How would you explain "why LLMs struggle with arithmetic" using only what you saw in Part 1?
3. In one sentence, how would you describe **alignment** to someone who's never used an LLM?
4. When would you **prefer** a base model over an aligned one? (There are real answers.)
5. What's one thing you saw today that will change how you design a prompt, a tool, or an agent?

---

**Wrap-up thought.** The goal wasn't to test tokenizers or models. It was to show you that what the model *sees* is different from what you write, and that alignment is a deliberate post-training step that reshapes output in specific, predictable ways. Both are **design choices** — and you now have opinions about them.
