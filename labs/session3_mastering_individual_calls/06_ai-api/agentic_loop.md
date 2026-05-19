# The Tool-Calling Loop and Its Middleware

*Designing the orchestration layer for AI systems*


## Learning Objectives

By the end of this reading, students should be able to:

- Explain why tool integration in AI systems is an **iterative loop** rather than a single request-response interaction.

- Identify the **new design concerns** introduced by agentic loops: non-deterministic control flow, error accumulation, and decisions under uncertainty.

- Describe the role of **middleware** in mediating between models and tools, including budgets, retries, policies, and stopping conditions.

- Distinguish between concerns that belong to **individual tools** versus the **orchestration layer**.

- Design agentic loops with explicit decisions about what is **delegated to the model** versus **enforced by the system**.


## 1. From request-response to iterative reasoning

TODO


## 2. What the loop looks like

TODO


## 3. New design concerns

TODO
- Control flow is not fully specified
- Errors accumulate across steps
- Decisions under uncertainty


## 4. The role of middleware

TODO
- Budgets (token, time, cost)
- Retry policies
- Stopping conditions
- Policy enforcement


## 5. Tool concerns vs orchestration concerns

TODO


## 6. Designing the boundary

TODO
- What to delegate to the model
- What to enforce in the system


## 7. Patterns and anti-patterns

TODO

