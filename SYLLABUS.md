# AI-Ready Engineers — Syllabus

> AI-Ready Engineers is dedicated to engineers and practitioners who want to be ready to build complex systems with AI — and for AI. It lays the foundations for building reliable systems efficiently, and for mastering the evaluation and improvement process that keeps them reliable as they grow.

**Format:** 16 sessions, organized in 4 skillsets, with an optional 3-chapter deep dive on uncertainty foundations for students without a stats background.

**Convention:** each session has a page (HTML, serves as the in-class walkthrough) and a master Jupyter notebook alongside it in the same folder. Supporting `.py` scripts, exercises, solutions, and slides live in the same folder.

---

## Learning Objectives

By the end of this course, you will:

1. **Understand how AI works and how to build AI-powered applications**. From hello world to mastering the development of AI agents with context, memory, tools.
2. **Build Effective, Reliable AI Systems at Scale.** Go beyond PoCs and small systems. Manage complexity. Build for reliability, consistency, manageability. Build observability, cost controls, and incident-ready guardrails.
3. **Identify and Master the Key Abstractions.**  Learn which are the fundamental abstractions you need to manage the complexity of a distributed, large scale probabilistic system. Understand which engineering principles carry forward from traditional software and which are the new abstractions we need.
4. **Use AI to Build AI, and iterate towards success.**  Master the science of monitoring, analysis, and estimation. Stand up an evaluation harness you can run in CI. Leverage AI for development, evaluation, and system management. Understand what this unlocks and where the limits are.

---

## Skillset 1 — Building AI Agents

---

### S1 — Hello AI World

**Page:** `[labs/01_hello_world/hello_world_3.0.html](labs/01_hello_world/hello_world_3.0.html)`
**Tagline:** Connecting to AI via API: chat, streaming, voice, and image.

**Learning objectives**

- *Differences between non-AI software, ML based software and gen AI*
- *Understand what are the different roles AI can play in software engineering*
- *Create an "hello world" AI-powered application*
- *Create an "hello world' application where AI is the user*
- *Create an "hello world" application using AI*

**Slides**

- `[session1_intro_with_and_for_ai.pdf](labs/01_hello_world/session1_intro_with_and_for_ai.pdf)` — Roles of AI in Software

**Resources**

- Python scripts: `[1_chat.py](labs/01_hello_world/1_chat.py)`, `[2_streaming.py](labs/01_hello_world/2_streaming.py)`, `[3_voice.py](labs/01_hello_world/3_voice.py)`, `[4_image.py](labs/01_hello_world/4_image.py)`
- `[history-of-evals.md](labs/01_hello_world/history-of-evals.md)`

**Labs**

- Master notebook: `[01_hello_ai_world.ipynb](labs/01_hello_world/01_hello_ai_world.ipynb)`
- Setup instructions: `[SETUP.md](SETUP.md)` — clone, install `uv`, configure API keys, install Ollama for the homework

---

### S2 — Gen AI Basics: How LLMs Work

**Page:** *TBD*
**Folder:** `[labs/01b_llm_basics/](labs/01b_llm_basics/)` (to be populated)
**Tagline:** How an LLM is built, tokens and context, fine-tuned vs bare models, the mental model engineers need to build on top.

**Learning objectives**

- Explain how an LLM is built (pre-training vs. post-training) and what distinguishes base models from instruction-tuned and "reasoning" variants
- Understand tokens and context windows — and why *effective* context is typically smaller than the nominal window
- Know the practical implications for engineers building on top: latency, cost, reliability, and model-choice tradeoffs

**Slides**

- *TBD*

**Resources**

- Excalidraw follow-along from Karpathy: [https://drive.google.com/file/d/1EZh5hNDzxMMy05uLhVryk061QYQGTxiN/view](https://drive.google.com/file/d/1EZh5hNDzxMMy05uLhVryk061QYQGTxiN/view)

*The best intro is Andrej Karpathy's videos and materials:*

- [Video: https://www.youtube.com/watch?v=7xTGNNLPyMI&t=1573s](https://www.youtube.com/watch?v=7xTGNNLPyMI&t=1573s)
- Tokenizers: [https://tiktokenizer.vercel.app/](https://tiktokenizer.vercel.app/)
- FineWeb Dataset: [https://huggingface.co/spaces/HuggingFaceFW/blogpost-fineweb-v1](https://huggingface.co/spaces/HuggingFaceFW/blogpost-fineweb-v1)
- Running base models vs aligned: [https://app.hyperbolic.ai/](https://app.hyperbolic.ai/)

**Labs**

- `[session2_tokenizers_and_models.md](labs/01b_llm_basics/session2_tokenizers_and_models.md)` — in-class exploration: tokenizer quirks (numbers, languages, code, adversarial inputs) and base vs. aligned model behaviour on Hyperbolic. Open-ended; invites discussion.

---

### S3 — Mastering Individual AI Calls

**Page:** `[labs/02_standalone_agents/mastering_individual_calls.html](labs/02_standalone_agents/mastering_individual_calls.html)`
**Tagline:** Prompt engineering, structured outputs, best practices for reliable single calls.

**Learning objectives**

- *Build an AI-powered application*
- *Master prompt engineering*
- *Understand how to separate feature of the model from addional bells and whistles offered by individual providers*

**Slides**

- `[session3_v2_mastering_individual_calls.pdf](labs/02_standalone_agents/session3_v2_mastering_individual_calls.pdf)` — Mastering Individual Calls

**Resources**

- `[session3_instructor_guide.md](labs/02_standalone_agents/session3_instructor_guide.md)`
- `[chat-completions-vs-responses-api.md](labs/02_standalone_agents/chat-completions-vs-responses-api.md)`
- `[prompts.md](labs/02_standalone_agents/prompts.md)`
- CLI scripts: `1_stateless_agent.py`, `2_stateful_agent.py`, `3_agent_with_memory.py`, `4_agent_with_long_term_memory.py` in `[labs/02_standalone_agents/](labs/02_standalone_agents/)`

**Labs**

- Master notebook: `[03_mastering_individual_calls.ipynb](labs/02_standalone_agents/03_mastering_individual_calls.ipynb)`
- Topic notebooks: `[session3_singlecall.ipynb](labs/02_standalone_agents/session3_singlecall.ipynb)`, `[session3_stateful.ipynb](labs/02_standalone_agents/session3_stateful.ipynb)`, `[session3_testing.ipynb](labs/02_standalone_agents/session3_testing.ipynb)`, `[session3_testing_and_metrics.ipynb](labs/02_standalone_agents/session3_testing_and_metrics.ipynb)`
- Exercises: `[session3_exercises.ipynb](labs/02_standalone_agents/session3_exercises.ipynb)`
- Answers: `[session3_answers.ipynb](labs/02_standalone_agents/session3_answers.ipynb)`
- Smoke tests: `[labs/tests/test_session3_smoke.py](labs/tests/test_session3_smoke.py)`

---

### S4 — Managing Context and Memory

**Page:** `[labs/03_context/stateless_stateful_agents.html](labs/03_context/stateless_stateful_agents.html)`
**Tagline:** Stateless & stateful agents, conversation history, cost & latency tradeoffs, memory strategies.

**Learning objectives**

- *Understand the distinction between stateless and stateful interactions with AI*
- *Learn how to understand the limit of actual vs effective context for a given tast*
- *Manage state across interactions*
- *How to handle short and long term memory for effective stateful interactions*

**Slides**

- `[session4_stateless_stateful_agents.pptx](labs/03_context/session4_stateless_stateful_agents.pptx)`

**Resources**

- CLI scripts: `1_stateless_agent.py`, `2_stateful_agent.py`, `3_agent_with_memory.py`, `4_agent_with_long_term_memory.py` in `[labs/03_context/](labs/03_context/)`
- `[prompt_templates/](labs/03_context/prompt_templates)`

**Labs**

- Master notebook: `[04_managing_context_and_memory.ipynb](labs/03_context/04_managing_context_and_memory.ipynb)` (Python mirror: `04_managing_context_and_memory.py`)
- Exercises: `[session4_exercises.ipynb](labs/03_context/session4_exercises.ipynb)`
- Solutions: `[session4_solutions.ipynb](labs/03_context/session4_solutions.ipynb)`
- Review-loop tests: `[labs/tests/test_session4_review_loop.py](labs/tests/test_session4_review_loop.py)`

---

### S5 — Tools & Agentic Loops

**Page:** `[labs/04_tool_calling/tool_calling.html](labs/04_tool_calling/tool_calling.html)`
**Tagline:** Tool calling, function schemas, orchestration loops, when to call another tool vs. stop.

**Learning objectives**

- Design clear function schemas and tool descriptions that an LLM can reliably call
- Build an agentic loop: decide when to call a tool, when to call another, and when to stop
- Recognize the failure modes of agentic loops (infinite tools, silent failures, drift) and the control patterns that mitigate them

**Slides**

- `[tool_calling_slides.pptx](labs/04_tool_calling/tool_calling_slides.pptx)`

**Resources**

- Support modules: `[tools.py](labs/04_tool_calling/tools.py)`, `[tools_bad.py](labs/04_tool_calling/tools_bad.py)`, `[data_tools.py](labs/04_tool_calling/data_tools.py)`, `[data_tools_bad.py](labs/04_tool_calling/data_tools_bad.py)`
- `[prompt_templates/](labs/04_tool_calling/prompt_templates)`

**Labs**

- Master notebook: `[05_tools_and_agentic_loops.ipynb](labs/04_tool_calling/05_tools_and_agentic_loops.ipynb)` (Python mirror: `05_tools_and_agentic_loops.py`)
- Exercises: `[session5_exercises.ipynb](labs/04_tool_calling/session5_exercises.ipynb)`
- Solutions: `[session5_solutions.ipynb](labs/04_tool_calling/session5_solutions.ipynb)`

**Safety crosslink:** Tool allow-lists, scoping, and adversarial tool use (tool abuse, destructive-action gating) are covered in depth in **S10 — Safety, Security, and Guardrails**.

---

## Skillset 2 — Mastering Observability, Quality, Security — Before Scaling Up

---

### S6 — Observing and Diagnosing your Agents

**Page:** `[labs/09_monitoring/monitoring.html](labs/09_monitoring/monitoring.html)`
**Tagline:** *TBD*

**Learning objectives**

- *Learn what and how to monitor*
- *Diagnose individual calls, monitor sessions, monitor systems*
- *Understand traces and statistical assertions*

**Slides**

- `[monitoring_slides.html](labs/09_monitoring/monitoring_slides.html)`
- `[monitoring_slides.pptx](labs/09_monitoring/monitoring_slides.pptx)`

**Resources**

- `[README.md](labs/09_monitoring/README.md)`
- `[outline.md](labs/09_monitoring/outline.md)`, `[slides_outline.md](labs/09_monitoring/slides_outline.md)`
- `[demos/](labs/09_monitoring/demos)`, `[exercises/](labs/09_monitoring/exercises)`, `[solutions/](labs/09_monitoring/solutions)`
- `[minimal_agent.py](labs/09_monitoring/minimal_agent.py)`, `[trace_viewer.py](labs/09_monitoring/trace_viewer.py)`, `[weekly_report_demo.py](labs/09_monitoring/weekly_report_demo.py)`
- `[golden_set.json](labs/09_monitoring/golden_set.json)`

**Labs**

- Master notebook: `[06_observing_and_diagnosing.ipynb](labs/09_monitoring/06_observing_and_diagnosing.ipynb)` (Python mirror: `06_observing_and_diagnosing.py`)

---

### S7 — Evals: From Traditional Software, to ML, to Gen AI

**Pages:**

- `[labs/05_eval_fundamentals/datasets.html](labs/05_eval_fundamentals/datasets.html)` — foundations (non-AI and traditional ML)
- `[labs/07_eval/eval_sw3.html](labs/07_eval/eval_sw3.html)` — AI-powered applications (Software 3.0)
**Tagline:** *TBD*

**Learning objectives**

- *Understand why "eval" in AI system is different from eval in non-ai software*
- *Review of eval in software engineering*
- *Understand metrics and measurement for ML models*
- *Learn basic mehods for evaluating unstructured output*

**Slides**

- *TBD*

**Resources**

- From `[labs/05_eval_fundamentals/](labs/05_eval_fundamentals/)`: `[datasets.md](labs/05_eval_fundamentals/datasets.md)`, `[outline.md](labs/05_eval_fundamentals/outline.md)`, `[auto_improvement_design.md](labs/05_eval_fundamentals/auto_improvement_design.md)`, `[best_practices.yaml](labs/05_eval_fundamentals/best_practices.yaml)`; pipeline scripts `[pipeline.py](labs/05_eval_fundamentals/pipeline.py)`, `run_eval_ground_truth.py`, `run_extract.py`, `run_judge.py`, `run_improve.py`, `run_loop.py`, `autotune.py`
- From `[labs/07_eval/](labs/07_eval/)`: `[outline.md](labs/07_eval/outline.md)`, `[auto_improvement_design.md](labs/07_eval/auto_improvement_design.md)`, `[best_practices.yaml](labs/07_eval/best_practices.yaml)`; pipeline scripts `[pipeline.py](labs/07_eval/pipeline.py)`, `run_eval_ground_truth.py`, `run_extract.py`, `run_judge.py`, `run_improve.py`, `run_loop.py`, `autotune.py`, `download_datasets.py`

**Labs**

- Foundations: `[browse_datasets.ipynb](labs/05_eval_fundamentals/browse_datasets.ipynb)`, `[iteration_loop.ipynb](labs/05_eval_fundamentals/iteration_loop.ipynb)`
- AI agents: `[browse_datasets.ipynb](labs/07_eval/browse_datasets.ipynb)`, `[iteration_loop.ipynb](labs/07_eval/iteration_loop.ipynb)`

---

### S8 — Approaching "AI Evals" as Estimation of Random Variables

- `[labs/08_automating_improvement/design_of_experiments.html](labs/08_automating_improvement/design_of_experiments.html)` — Part I: designing experiments, sources of uncertainty
- `[labs/08_automating_improvement/design_of_experiments_2.html](labs/08_automating_improvement/design_of_experiments_2.html)` — Part II: deeper into uncertainty and brittleness
**Tagline:** Apply the uncertainty toolkit to real AI systems — design experiments, quantify what you don't know, report it honestly, and reduce it where it matters.

**Learning objectives**

- Frame an AI eval as an *estimator* of a random variable (the system's true behaviour on a population of inputs) — not a point measurement
- Understand the different sources of uncertainty and how they impact measures in practice
- Recognize common errors and how to make your eval robust and reliable — minimize surprises in production
- Recognize organizational patterns that produce blind spots (incentive misalignment, reporting, metric ownership)

> **No stats background?** Work through the **Mastering Uncertainty Deep Dive (D1–D3)** at the end of Skillset 2 before this session.

**Slides**

- `[labs/08_automating_improvement/slides_p/](labs/08_automating_improvement/slides_p)`

**Resources**

- `[uncertainty_sources_design.md](labs/08_automating_improvement/uncertainty_sources_design.md)`

**Labs**

- Overfitting lab: `[overfitting_lab.ipynb](labs/08_automating_improvement/overfitting_lab.ipynb)` (Python mirror: `overfitting_lab.py`)
- Prompt-brittleness lab: `[prompt_brittleness_lab.ipynb](labs/08_automating_improvement/prompt_brittleness_lab.ipynb)` (Python mirror: `prompt_brittleness_lab.py`)

---



---

### S9 — Reinterpreting Test-Driven Development in the Age of AI

**Page:** *TBD*
**Tagline:** Test-first thinking when the unit under test is stochastic — flipping evals, golden sets, and assertions over distributions into a development discipline.

**Learning objectives**

- Understand how classical TDD (red-green-refactor on deterministic units) needs to be reframed when the unit under test is stochastic
- Apply test-first thinking with evals, golden sets, and assertions over distributions instead of point assertions
- Establish a development feedback loop where the eval is written before the prompt/agent change — and scales with the system

**Slides**

- *TBD*

**Resources**

- *TBD*

**Labs**

- *TBD*

---

### S10 — Safety, Security, and Guardrails

**Page:** *TBD*
**Folder:** `[labs/13_safety/](labs/13_safety/)` (to be populated)
**Tagline:** End-to-end threat model for AI systems — content safety, system security, and operational guardrails that keep agents useful without letting them become liabilities.

**Learning objectives**

- Distinguish the three layers of AI safety: *content safety* (harmful, biased, or dangerously wrong outputs), *system security* (prompt injection, data exfiltration, tool abuse, supply-chain risk), and *operational guardrails* (rate limits, human-in-the-loop gates, blast-radius control, auditability)
- Apply a threat model to an agentic system — what can a malicious input, a compromised tool, or a confused agent do, and which defenses are worth their cost
- Implement practical defenses: input/output filters, tool allow-lists and scoping, sandboxing, approval gates for high-impact actions, anomaly detection and auditing
- Red-team your own system: design attack scenarios, run them, and harden the system against what you find

**Slides**

- *TBD*

**Resources**

- OWASP Top 10 for LLM Applications — canonical threat taxonomy for LLM-powered systems
- Simon Willison's writeups on prompt injection and the "lethal trifecta" (private data + untrusted content + external communication channels)
- Anthropic — Responsible Scaling Policy and agent-safety research
- NIST AI Risk Management Framework (AI RMF) — for regulated/enterprise contexts
- *TBD — red-team scenario playbook and defense pattern catalogue*

**Labs**

- Red-team lab: take the tool-using agent from S5, craft adversarial inputs to exfiltrate data, escalate tool access, or trigger a destructive action — then harden it and re-run the attacks
- Guardrail integration lab: wrap an existing agent with an input filter, a tool allow-list, and an approval gate for high-impact actions; measure the cost (latency, false-positive rate) of each layer
- *TBD — notebooks and exercises*

**Crosslinks:** Builds on **S5** (tool design) and **S6** (observability as a safety primitive). Feeds into **S13** (reliable architectures — architectural realization of these constraints) and **S16** (when AI is the user — the adversary's view of the same interfaces).

---



## Mastering Uncertainty Deep Dive (No stats background required)

### D1 — Probability and Random Variables for AI Evaluations

**Page:** *TBD*  
**Tagline:** "Every measure, without knowledge of its uncertainty, is meaningless" 

**Learning objectives**

- *Probability and Random Variables*
- *Useful random variables for measuring AI systems*
- Adding (and averaging) random variables
- Standard errors and confidence intervals

**Slides**

- `[session9_mastering_uncertainty.pdf](labs/06_mastering_uncertainty/session9_mastering_uncertainty.pdf)`

**Resources**

- Interactive playground: `[AI Evaluation Playgrounds](playground/index.html)` — the full index; each play lets you *feel* a source of uncertainty and see how to *fix* it
- Statistics foundations: `[N Coin Flips / CLT](playground/convolution_of_independent_random_variables.html)`, `[Bootstrap Lab](playground/bootstrap_lab.html)`, `[Distribution Explorer](playground/distribution_explorer.html)`
- Sources of uncertainty (pick through these in class): `[Sampling Noise](playground/sampling_noise.html)`, `[Sampling Bias](playground/sampling_bias.html)`, `[Multiple Hypothesis Testing](playground/multiple_hypothesis_testing.html)`, `[Variance Across Domains](playground/domain_variance.html)`, `[Choice of Metric](playground/metric_choice.html)`, `[Temporal Drift](playground/temporal_drift.html)`, `[LLM Evolution](playground/llm_evolution.html)`, `[Judges & Compounding](playground/judges_and_compounding.html)`
- `[Accuracy Estimator](playground/accuracy_estimator.html)` — Beta-posterior point estimate + credible interval for a pass-rate

**Labs**

- Master notebook: `[09_understanding_uncertainty.ipynb](labs/06_mastering_uncertainty/09_understanding_uncertainty.ipynb)` — overarching, code-first companion to the playground. Four runnable experiments (sampling noise, sampling bias, multiple hypothesis testing, judge compounding) with bootstrap CIs and Beta posteriors. Synthetic data, no API calls — iterate fast.

---

### D2 — Estimating Distributions of AI Systems Quality through Experimentation

**Page:** `[labs/06_mastering_uncertainty/optimizing-in-the-dark/index.html](labs/06_mastering_uncertainty/optimizing-in-the-dark/index.html)`  
**Tagline:** Structural flaws, uncertainty vs. variability confusion, and the cost of ignorance — how well-intentioned eval pipelines go wrong.

**Learning objectives**

- Conditional Probability - the theory behind ML
- Bayes and Beta made easy
- Beta distributions vs standard errors and confidence intervals

**Slides**

- *TBD*

**Resources**

- Parts: `[part-1-structural-flaw.md](labs/06_mastering_uncertainty/optimizing-in-the-dark/part-1-structural-flaw.md)`, `[part-2-cost-of-ignorance.md](labs/06_mastering_uncertainty/optimizing-in-the-dark/part-2-cost-of-ignorance.md)`, `[part-2b-uncertainty-vs-variability.md](labs/06_mastering_uncertainty/optimizing-in-the-dark/part-2b-uncertainty-vs-variability.md)`
- `[glossary.md](labs/06_mastering_uncertainty/optimizing-in-the-dark/glossary.md)`
- `[Optimizing in the Dark.docx](labs/06_mastering_uncertainty/Optimizing%20in%20the%20Dark.docx)`

**Labs**

- *No notebook yet — content is narrative HTML/markdown. TBD whether to add one.*

### D3 — Bootstrapping and Simulations

**Page:** `[labs/06_mastering_uncertainty/optimizing-in-the-dark/index.html](labs/06_mastering_uncertainty/optimizing-in-the-dark/index.html)`  
**Tagline:** Structural flaws, uncertainty vs. variability confusion, and the cost of ignorance — how well-intentioned eval pipelines go wrong.

**Learning objectives**

- A trick to rule them all 
- Statistical significance
- Simulate systems, experiments, and the errors behind experiments to build confidence and robustness

**Slides**

- *TBD*

**Resources**

- Parts: `[part-1-structural-flaw.md](labs/06_mastering_uncertainty/optimizing-in-the-dark/part-1-structural-flaw.md)`, `[part-2-cost-of-ignorance.md](labs/06_mastering_uncertainty/optimizing-in-the-dark/part-2-cost-of-ignorance.md)`, `[part-2b-uncertainty-vs-variability.md](labs/06_mastering_uncertainty/optimizing-in-the-dark/part-2b-uncertainty-vs-variability.md)`
- `[glossary.md](labs/06_mastering_uncertainty/optimizing-in-the-dark/glossary.md)`
- `[Optimizing in the Dark.docx](labs/06_mastering_uncertainty/Optimizing%20in%20the%20Dark.docx)`

**Labs**

- *No notebook yet — content is narrative HTML/markdown. TBD whether to add one.*



## Skillset 3 — Building and Managing Complex Systems

---

### S11 — Foundational Programming Abstractions for Complex Systems

**Pages:**

- `[labs/10_complex_systems/2_abstractions/key_abstractions.html](labs/10_complex_systems/2_abstractions/key_abstractions.html)` — key abstractions
- `[labs/06_ai-api/aoa.html](labs/06_ai-api/aoa.html)` — Abstractions of Agents
- `[labs/06_ai-api/ai_tools_integration.html](labs/06_ai-api/ai_tools_integration.html)` — AI tools integration
- `[labs/06_ai-api/mcp_tutorial.html](labs/06_ai-api/mcp_tutorial.html)` — MCP tutorial
**Tagline:** Foundational programming abstractions for AI systems — agentic loops, autonomy sliders, context/memory, tool integration surfaces, and MCP.

**Learning objectives**

- Complex systems are like grandious, sophisticated, and gradually evolving buildings — learn how the concepts of building blocks, components and compositions, has changed throughout a brief history of software architectures
- Understand which foundational abstractions we want to carry from the past and are still valid today, and what is fundamentally new with AI agents
- Explore hands on the similarities and differences when composing AI-less systems, when the components are AI agents, when the orchestration is driven by AI agents, and finally where AI is present throughout the entire architecture
- Distinguish UI, APIs, agentic interfaces, and agentic systems — and reason about how the contract between caller and callee shifts when the consumer is human, code, or another agent (signature, error semantics, autonomy, retries, observability surface)
- Decide which parts of a system call for *abstractions* (custom, internal, optimized for the problem at hand) versus *standards* (shared protocols like MCP, OpenAPI, OAuth — buying ecosystem leverage at the cost of compliance overhead) — and recognize when picking the wrong one becomes technical debt

**Slides**

- `[aoa.pdf](labs/06_ai-api/aoa.pdf)` / `[aoa.pptx](labs/06_ai-api/aoa.pptx)` / `[aoa-improved.pptx](labs/06_ai-api/aoa-improved.pptx)` — Abstractions of Agents

**Resources**

- Abstractions & interfaces: `[ai_interface.md](labs/06_ai-api/ai_interface.md)`, `[agentic_loop.md](labs/06_ai-api/agentic_loop.md)`, `[autonomy_slider.md](labs/06_ai-api/autonomy_slider.md)`, `[context_memory.md](labs/06_ai-api/context_memory.md)`, `[designing_agentic_systems.md](labs/06_ai-api/designing_agentic_systems.md)`, `[gpt_propsal_for_abstractions.md](labs/06_ai-api/gpt_propsal_for_abstractions.md)`
- Tool calling / MCP: `[ai_tools_integration.md](labs/06_ai-api/ai_tools_integration.md)`, `[mcp_tutorial.md](labs/06_ai-api/mcp_tutorial.md)`, `[mcp_tool_calling_and_ai_integration_surfaces.md](labs/06_ai-api/mcp_tool_calling_and_ai_integration_surfaces.md)`
- AoA variant: `[aoa2.md](labs/06_ai-api/aoa2.md)` / `[aoa2.html](labs/06_ai-api/aoa2.html)`
- `[LECTURE_REVIEW_2026.md](labs/06_ai-api/LECTURE_REVIEW_2026.md)`

**Labs**

- *No notebook yet.*

---

### S12 — Architectural Patterns At Work

**Page:** `[labs/10_complex_systems/1_councils/councils.html](labs/10_complex_systems/1_councils/councils.html)`
**Tagline:** A tour of agentic patterns — ensemble shapes, orchestration shapes, and control/reasoning patterns within a single agent — and how to pick the right shape for the problem.

**Learning objectives**

- Map a concrete AI feature to the right abstractions, so code stays manageable as the system grows
- Identify the foundational abstractions for AI systems — agentic loops, autonomy sliders, context/memory, tool-integration surfaces — and know when to reach for each
- Understand what MCP is, what problem it solves, and how agent-system integration is standardizing
- Map the pattern landscape across three axes: **ensemble** (many agents on the same task), **orchestration** (decompose the task across stages/agents), and **control/reasoning patterns within an agent** (how a single agent reasons and acts)
- Recognize the main patterns in each family — councils / majority vote / debate; pipelines / routers / supervisor-worker; ReAct / plan-and-execute / reflect — and what each buys you (and when it fails: correlated errors, step compounding, loop divergence)
- Reason about the core design questions of multi-agent systems: diversity, aggregation, routing, budget, and evaluation

**Slides**

- `[agentic_patterns.slides.md](labs/10_complex_systems/1_councils/agentic_patterns.slides.md)`

**Resources**

- `[councils_concept.md](labs/10_complex_systems/1_councils/councils_concept.md)`

**Labs**

- *No notebook yet.*

---

### S13 — Driving for Consistent, Predictable Outcomes: Reliable Architectures and Engineering Practices

**Pages:**

- `[labs/10_complex_systems/3_architectures/complex_systems.html](labs/10_complex_systems/3_architectures/complex_systems.html)` — reliable and robust architectures
- `[labs/12_structuring_projects/structuring_projects.html](labs/12_structuring_projects/structuring_projects.html)` — structuring, shipping, multi-version maintenance
**Tagline:** Reliable architectures + shipping into existing products, maintaining large AI systems, multi-version considerations.

**Learning objectives**

- Structuring for Production
- Apply architecture patterns that keep AI systems reliable under real traffic (timeouts, fallbacks, budgets, graceful degradation)
- Structure projects for shipping into existing products and maintaining them across model and prompt versions
- Plan for multi-version considerations — prompts, tools, schemas, datasets — so upgrades don't silently regress behaviour

**Slides**

- *TBD*

**Resources**

- *TBD*

**Labs**

- *No notebook yet.*

**Safety crosslink:** Defensive architecture patterns (approval gates, blast-radius control, circuit-breakers for runaway agents) are the architectural realization of the principles covered earlier in **S10 — Safety, Security, and Guardrails**.

---

## Skillset 4 — Building ++*with*++ AI and ++*for*++ AI — at AI Speed

---

### S14 — Developing at the Speed of AI Without Losing Control

**Page:** `[labs/13_programming_in_english/programming_in_english.html](labs/13_programming_in_english/programming_in_english.html)`
**Tagline:** Without Losing Control (and Mental Health) — using AI to build software, without ceding the engineering judgment that keeps systems sane.

**Learning objectives**

- Use AI to accelerate software development (code generation, review, refactoring) without losing the engineering judgment that keeps systems sane
- Understand why natural language is a lossy specification medium — and what that means for correctness, control, and debuggability
- Establish a sustainable working style for AI-assisted development: when to trust, when to verify, when to step in

**Slides**

- *TBD*

**Resources**

- *Talk by Claude Code team: [https://x.com/codewithimanshu/status/2046415534523306303/video/1?s=46](https://x.com/codewithimanshu/status/2046415534523306303/video/1?s=46)*

**Labs**

- *No notebook yet.*

---

### S15 — Standards, Frameworks, and When to Use Them

**Page:** `[labs/14_frameworks/frameworks.html](labs/14_frameworks/frameworks.html)`
**Tagline:** When and why to use frameworks; LangChain as a case study.

**Learning objectives**

- Explain what frameworks actually provide beyond "less code" — integrations, standard patterns, observability hooks, and ecosystem — and what they don't
- Compare LangChain, LlamaIndex, and LangGraph along three axes (orchestration, data/retrieval, state) and pick an appropriate tool for a given problem
- Apply a decision rule for when a framework is a net positive vs. a net negative — and what the "framework tax" looks like for your system

**Slides**

- *TBD*

**Resources**

- `[outline.md](labs/14_frameworks/outline.md)`
- Agent implementations: `[agent_scratch.py](labs/14_frameworks/agent_scratch.py)`, `[agent_langchain.py](labs/14_frameworks/agent_langchain.py)`, `[agent_langgraph.py](labs/14_frameworks/agent_langgraph.py)`, `[agent_llamaindex.py](labs/14_frameworks/agent_llamaindex.py)`
- Shared tools: `[tools_shared.py](labs/14_frameworks/tools_shared.py)`

**Labs**

- Master notebook: `[15_using_ai_frameworks.ipynb](labs/14_frameworks/15_using_ai_frameworks.ipynb)`

---

### S16 — When AI is the User of Our System

**Page:** *TBD*
**Tagline:** Designing systems for AI consumers — what changes when the user is an agent, not a human: API ergonomics for agents, failure modes unique to agent consumers, and the shift from human-centred to agent-centred system design.

**Learning objectives**

- Recognize how API and UX design shift when the consumer is an AI agent, not a human
- Design tool schemas, error messages, and interfaces that agents can reliably use and recover from
- Anticipate failure modes unique to agent consumers (prompt injection, tool misuse, runaway loops) and design for graceful degradation

**Slides**

- *TBD*

**Resources**

- *TBD*

**Labs**

- *TBD*

**Safety crosslink:** This session covers the *design* side of agent-as-consumer failure modes. The *defense* side — red-teaming, guardrails, and hardening — is covered end-to-end in **S10 — Safety, Security, and Guardrails**.

---

## Orphan content (not yet mapped)

- `[labs/11_lab_eval_session/](labs/11_lab_eval_session)` — eval lab session with `notebook.ipynb`, articles, and guidelines. Candidate for Skillset 2.
- `[labs/representations/](labs/representations)` — `slides.md`. Unclear mapping.

