# L10 · Monitoring, Observability and Reporting — Lab

Companion to the L10 lecture (Week 5, AI Design 2026). Seven demos
and seven exercises covering the full monitoring stack, from a single
`print()` statement up through multi-agent OTel traces and offline
A/B analysis with confidence intervals.

## Structure

```
labs/09_monitoring/
├── demos/
│   ├── 1_basic_logging/                ← Slides 5–6   — print → log → structured log
│   ├── 2_central_log_dashboard/        ← Slides 9–10  — flat rows + 4-panel dashboard
│   ├── 3_classical_ml_dashboard/       ← Slides 14–16 — classical-ML training + drift
│   ├── 4_llm_calls/                    ← Slides 18–22 — LLM calls, outcomes, guardrails
│   ├── 5_otel_traces/                  ← Slides 24–26 — OTel spans + waterfall viewer
│   ├── 6_multi_agent/                  ← Slides 29–32 — orchestrator + sub-agents
│   └── 7_ab_analysis/                  ← Slides 37–38 — A/B with 95% CIs
└── exercises/
    ├── lx1_logging/                    ← pairs with Demo 1
    ├── lx2_leading_indicator/          ← pairs with Demo 2
    ├── lx3_ci_drift_gate/              ← pairs with Demo 3
    ├── lx4_safety_category/            ← pairs with Demo 4
    ├── lx5_instrument_rag/             ← pairs with Demo 5
    ├── lx6_diagnose_multi_agent/       ← pairs with Demo 6
    └── lx7_ab_decision/                ← pairs with Demo 7

(Reference solutions live in `solutions/lxN_*/` — don't peek until
you've tried the exercise.)
```

Every demo folder has its own `README.md` with slide pairings,
teaching beats, and reading-the-data snippets. Every exercise folder
has a `README.md` with success criteria, hints, and common pitfalls.

## Install

The labs are deliberately stdlib-heavy. Everything below is enough
for the whole set:

```bash
pip install numpy scikit-learn
# Dashboards use Chart.js from a CDN — no local JS install needed.
```

No API keys. No OpenTelemetry SDK. Every demo seeds a deterministic
RNG and a frozen `NOW = 2026-04-27T18:00`, so the outputs are
byte-stable across machines.

> **Legacy notebook only:** `monitoring_lab.py` and
> `monitoring_lab.ipynb` are kept for backward compatibility and
> import `pydantic` and `opentelemetry`. If you actually want to run
> them, `pip install pydantic opentelemetry-api opentelemetry-sdk`.
> The current `demos/` + `exercises/` layout does not need either.

## Running a demo

Each demo is self-contained. Example — Demo 4 (LLM calls):

```bash
cd demos/4_llm_calls
python gen_calls.py         # writes llm_calls.ndjson + calls.js
open dashboard.html          # dashboard with guardrail + cost panels
open log_viewer.html         # flat row table, filterable
```

The pattern is the same for Demos 2, 3, 5, 6, 7 — a Python script
that writes NDJSON plus a `.js` wrapper; one or two HTML files that
visualise the data.

## The three stages

The lecture frames monitoring in three stages; the lab follows that
structure:

- **Stage A — Flat call rows** (Demos 1–4, LX-1–4). One row per
  request. Good for outcomes, cost, latency, guardrail trips.
  Teaches what you get for free, and what gets painful when you
  need parent-child causality.
- **Stage B — Distributed traces** (Demos 5–6, LX-5–6). One span
  per operation, parent-child via `trace_id` / `span_id`.
  Enough to reason about multi-step agents, retrieval timeouts,
  and multi-agent failure modes like role confusion or planner
  loops.
- **Stage C — Offline analysis** (Demo 7, LX-7). The data from
  Stages A+B, but used to answer "should we ship this change?"
  Confidence intervals, decision memos, evidence vs. vibes.

## Running the exercises

Each exercise has a `starter.py` or `starter.html` with clear TODO
markers and a self-grading path where possible. Success criteria
are listed at the top of each README. Example:

```bash
cd exercises/lx4_safety_category
python starter.py            # fails at NotImplementedError
# ...edit starter.py...
python starter.py            # should print outcome counts
open dashboard.html          # should show your new bucket
```

The reference solutions live alongside under `solutions/lxN_*/`.
If you peek first, you've robbed yourself of the learning; if you
peek after, they're well-commented and show a few variants that
students ship.

## The slide deck and the notebook

**Canonical lecture deck:**

- `monitoring_slides.html` — the lecture itself. Plain HTML, no
  framework. Open in a browser and scroll; the sidebar is the ToC.
- `slides_outline.md` — the source of truth for slide content. Edit
  here, regenerate the HTML.

**Planning / instructor notes:**

- `outline.md` — high-level lecture plan.
- `demos_plan.md` — per-demo design notes.
- `exercises.md` / `solutions.md` — exercise specs and reference
  answers, separate from the student-facing `exercises/` folder.

**Legacy (kept for backward compatibility, not required):**

- `monitoring.html` — earlier HTML deck, superseded by
  `monitoring_slides.html`.
- `monitoring_slides.pptx` — earlier PowerPoint export, also
  superseded.
- `monitoring_lab.ipynb` / `monitoring_lab.py` — earlier
  single-notebook version. See the "Legacy notebook only" note in
  the **Install** section above for its extra requirements.
- `trace_viewer.py` — stdlib-only span-tree renderer. The
  `trace_viewer.html` files inside Demos 5/6 and LX-5/LX-6
  supersede it.

**Other:**

- `weekly_report_demo.py` / `weekly_report.png` — matplotlib
  "anatomy of a weekly report" teaching artifact.

## Order to work through

Reading order for a student with ~8 hours:

1. Demo 1 → LX-1                   (30 min)
2. Demo 2 → LX-2                   (45 min)
3. Demo 3 → LX-3                   (60 min)
4. Demo 4 → LX-4                   (90 min)
5. Demo 5 → LX-5                   (60 min)
6. Demo 6 → LX-6                   (60 min)
7. Demo 7 → LX-7                   (60 min)

Skipping around works too — every demo+exercise pair is independent
of the others. The only hard dependency is that LX-5 reuses the
viewer from Demo 5, LX-6 reuses Demo 6, and LX-7 reuses the Demo 7
statistical helpers.

## Determinism and re-running

Every generator is seeded:

  - Demos 2, 3, 4   → seed=42
  - Demo 5          → seed=7
  - Demo 6          → seed=19
  - Demo 7          → seed=77
  - LX-6 generator  → seed=101
  - LX-7 generator  → seed=202

Frozen `NOW = 2026-04-27T18:00` on every run. Re-running produces
byte-identical NDJSON, which is why the self-grading blocks in the
exercises can assert exact row counts.
