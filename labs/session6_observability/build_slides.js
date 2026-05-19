// build_slides.js — generates monitoring_slides.pptx
//
// Run:  NODE_PATH=/usr/local/lib/node_modules_global/lib/node_modules \
//       node build_slides.js
//
// Content mirrors labs/09_monitoring/monitoring.html (L10).

const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";   // 13.3" x 7.5"
pres.title  = "L10 — Monitoring, Observability and Reporting";
pres.author = "Fabio Casati";

// -------- Palette: Ocean Gradient (trust / infra feel) --------------------
const C = {
  bg:      "0E1726",    // very dark navy (title/section bg)
  bg2:     "F7F9FC",    // light content bg
  primary: "065A82",    // deep blue
  teal:    "1C7293",    // support
  midnight:"21295C",    // accent / dark
  accent:  "F4A261",    // warm accent for callouts
  danger:  "E76F51",    // regression / warning
  ok:      "2A9D8F",    // green for success
  text:    "1F2A3A",    // body text on light
  textDim: "64748B",    // muted text
  white:   "FFFFFF",
};

const FONT_H = "Calibri";        // headers
const FONT_B = "Calibri";        // body
const FONT_M = "Courier New";    // mono for code (universally available)

// Small helpers ------------------------------------------------------------

function addFooter(slide, number, total) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 7.25, w: 13.3, h: 0.25, fill: { color: C.primary }, line: { color: C.primary },
  });
  slide.addText("L10 · Monitoring, Observability and Reporting", {
    x: 0.4, y: 7.22, w: 10, h: 0.28, fontSize: 10, color: C.white,
    fontFace: FONT_B, margin: 0, valign: "middle",
  });
  slide.addText(`${number} / ${total}`, {
    x: 12.4, y: 7.22, w: 0.6, h: 0.28, fontSize: 10, color: C.white,
    fontFace: FONT_B, align: "right", margin: 0, valign: "middle",
  });
}

function addSectionTag(slide, tag) {
  slide.addText(tag.toUpperCase(), {
    x: 0.6, y: 0.5, w: 12, h: 0.35, fontSize: 12,
    color: C.teal, fontFace: FONT_H, bold: true, charSpacing: 4, margin: 0,
  });
}

function addTitle(slide, title) {
  slide.addText(title, {
    x: 0.6, y: 0.9, w: 12, h: 1.0, fontSize: 36, bold: true,
    color: C.midnight, fontFace: FONT_H, margin: 0,
  });
}

function contentCard(slide, x, y, w, h, header, bullets, opts = {}) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h, fill: { color: C.white },
    line: { color: "E2E8F0", width: 0.75 },
    shadow: { type: "outer", color: "000000", blur: 6, offset: 2, angle: 135, opacity: 0.08 },
  });
  // Left accent bar
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w: 0.08, h, fill: { color: opts.accentColor || C.primary }, line: { color: opts.accentColor || C.primary },
  });
  slide.addText(header, {
    x: x + 0.35, y: y + 0.18, w: w - 0.5, h: 0.5, fontSize: 16, bold: true,
    color: C.midnight, fontFace: FONT_H, margin: 0,
  });
  const runs = bullets.map((b, i) => ({
    text: b,
    options: { bullet: true, breakLine: i < bullets.length - 1 },
  }));
  slide.addText(runs, {
    x: x + 0.35, y: y + 0.75, w: w - 0.55, h: h - 0.9, fontSize: 13,
    color: C.text, fontFace: FONT_B, paraSpaceAfter: 4, valign: "top", margin: 0,
  });
}

function thesisBlock(slide, x, y, w, label, body, color = C.accent) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h: 1.5, fill: { color: C.bg },
    line: { color, width: 1.5 },
  });
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w: 0.12, h: 1.5, fill: { color }, line: { color },
  });
  slide.addText(label.toUpperCase(), {
    x: x + 0.3, y: y + 0.12, w: w - 0.4, h: 0.3,
    fontSize: 10, color, fontFace: FONT_H, bold: true, charSpacing: 3, margin: 0,
  });
  slide.addText(body, {
    x: x + 0.3, y: y + 0.42, w: w - 0.4, h: 1.0,
    fontSize: 14, color: C.white, fontFace: FONT_H, italic: true, margin: 0, valign: "top",
  });
}

// =========================================================================
// Slides
// =========================================================================

const TOTAL = 18;
let n = 0;

// ---- 1. Title ------------------------------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  s.addText("L10 · WEEK 5", {
    x: 0.8, y: 1.6, w: 12, h: 0.4, fontSize: 14, color: C.teal,
    fontFace: FONT_H, bold: true, charSpacing: 6, margin: 0,
  });
  s.addText("Monitoring, Observability\nand Reporting", {
    x: 0.8, y: 2.1, w: 12, h: 2.6, fontSize: 54, bold: true,
    color: C.white, fontFace: FONT_H, margin: 0, paraSpaceAfter: 0,
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.8, y: 4.9, w: 1.2, h: 0.05, fill: { color: C.accent }, line: { color: C.accent },
  });
  s.addText(
    "Runtime checks · Structured logging · Tracing · CI-integrated eval harnesses",
    { x: 0.8, y: 5.1, w: 12, h: 0.5, fontSize: 18, color: C.bg2, fontFace: FONT_H, italic: true, margin: 0 }
  );
  s.addText("Designing Large Scale AI Systems — Spring 2026", {
    x: 0.8, y: 6.8, w: 12, h: 0.3, fontSize: 11, color: C.teal, fontFace: FONT_B, margin: 0,
  });
  n++;
}

// ---- 2. Why this lesson --------------------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.bg2 };
  addSectionTag(s, "00 / Framing");
  addTitle(s, "Evals stop at the CI gate. Production doesn't.");
  s.addText(
    "We spent Phase 2 building tools to know whether our AI system works: "
    + "datasets, rubrics, LLM-as-judge, experiments with uncertainty.\n\n"
    + "Those run before deploy. This lesson is about what happens after — "
    + "when real users touch the system, at 3am, on traffic we did not design for, "
    + "with a model provider that silently changed something under us last Tuesday.",
    { x: 0.6, y: 2.1, w: 8.4, h: 3.0, fontSize: 16, color: C.text, fontFace: FONT_B, margin: 0, paraSpaceAfter: 10 },
  );
  thesisBlock(s, 9.3, 2.2, 3.4,
    "One-line summary",
    "Production is the hardest eval set you will ever have. Instrumentation is how you read it.",
    C.accent);
  addFooter(s, ++n, TOTAL);
}

// ---- 3. Section 01 divider -----------------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  s.addText("01", {
    x: 0.8, y: 2.0, w: 3, h: 3, fontSize: 200, bold: true,
    color: C.teal, fontFace: FONT_H, margin: 0,
  });
  s.addText("Why AI systems are harder to monitor", {
    x: 4.0, y: 3.0, w: 8.5, h: 2, fontSize: 36, bold: true,
    color: C.white, fontFace: FONT_H, margin: 0,
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 4.0, y: 4.8, w: 1.0, h: 0.05, fill: { color: C.accent }, line: { color: C.accent },
  });
  s.addText("Non-determinism · semantic failures · silent drift · long tail", {
    x: 4.0, y: 4.95, w: 8, h: 0.4, fontSize: 14, color: C.bg2, fontFace: FONT_H, italic: true, margin: 0,
  });
  addFooter(s, ++n, TOTAL);
}

// ---- 4. Why classical monitoring underfits -------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.bg2 };
  addSectionTag(s, "01 / Why AI is harder");
  addTitle(s, "Classical monitoring underfits AI systems");
  contentCard(s, 0.6, 2.0, 6.1, 5.0, "The five breakages", [
    "Non-determinism — same input, different output. Flakiness is the substrate, not a bug.",
    "Semantic failures — a wrong answer returns HTTP 200. Confident, well-formed, hallucinated.",
    "Silent drift — provider ships a new checkpoint; your code didn't change, your quality did.",
    "Long-tailed failures — most traffic is fine; failures cluster in narrow slices.",
    "Cost & latency ARE correctness — a cheap wrong answer is often worse than an expensive right one.",
  ], { accentColor: C.danger });
  contentCard(s, 6.9, 2.0, 6.0, 5.0, "Three horizons of feedback",
    [
      "Offline (seconds–minutes) — CI gates on a golden set. Fast, cheap, low fidelity.",
      "Online (minutes–hours) — canary, shadow, sampled judges. Real distribution, higher fidelity.",
      "Human (hours–weeks) — thumbs, tickets, manual review. Slowest, only source of certain ground truth.",
      "Any system on one horizon alone is flying partially blind.",
    ], { accentColor: C.primary });
  addFooter(s, ++n, TOTAL);
}

// ---- 5. Thesis: alert on proxies -----------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  addSectionTag(s, "01 / Key insight");
  s.addText("KEY INSIGHT", {
    x: 0.8, y: 1.4, w: 12, h: 0.4, fontSize: 14, color: C.accent,
    fontFace: FONT_H, bold: true, charSpacing: 6, margin: 0,
  });
  s.addText(
    "You cannot alert on \"the model got it wrong.\"",
    { x: 0.8, y: 2.0, w: 12, h: 1.0, fontSize: 32, bold: true, color: C.white, fontFace: FONT_H, margin: 0 },
  );
  s.addText(
    "You can only alert on proxies — guardrail rejection rate, latency, cost, "
    + "judge score on sampled traffic, thumbs, retry rate, tool-failure rate.",
    { x: 0.8, y: 3.1, w: 12, h: 1.2, fontSize: 18, color: C.bg2, fontFace: FONT_H, italic: true, margin: 0 },
  );
  s.addText(
    "The job of monitoring: design proxies that fail before users do — "
    + "and know each proxy's own failure modes.",
    { x: 0.8, y: 4.8, w: 12, h: 1.2, fontSize: 18, color: C.teal, fontFace: FONT_H, margin: 0 },
  );
  addFooter(s, ++n, TOTAL);
}

// ---- 6. Section 02 divider -----------------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  s.addText("02", {
    x: 0.8, y: 2.0, w: 3, h: 3, fontSize: 200, bold: true,
    color: C.teal, fontFace: FONT_H, margin: 0,
  });
  s.addText("Runtime checks & guardrails", {
    x: 4.0, y: 3.0, w: 8.5, h: 2, fontSize: 36, bold: true,
    color: C.white, fontFace: FONT_H, margin: 0,
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 4.0, y: 4.8, w: 1.0, h: 0.05, fill: { color: C.accent }, line: { color: C.accent },
  });
  s.addText("Rubrics you are willing to run on every request", {
    x: 4.0, y: 4.95, w: 8, h: 0.4, fontSize: 14, color: C.bg2, fontFace: FONT_H, italic: true, margin: 0,
  });
  addFooter(s, ++n, TOTAL);
}

// ---- 7. Where guardrails sit + failure modes -----------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.bg2 };
  addSectionTag(s, "02 / Guardrails");
  addTitle(s, "Where they sit — and how they themselves fail");
  contentCard(s, 0.6, 2.0, 6.1, 5.0, "Where they run", [
    "Input-side — schema, prompt-injection, PII/secret filters, cost/length budgets.",
    "Model-side — bounded tokens, bounded tool-call depth, timeouts, temperature discipline.",
    "Output-side — JSON/schema validation, factual anchors, policy checks, \"did it call the tool?\"",
    "Cross-cutting — per-tenant cost caps, circuit breakers that trip on rejection spikes.",
  ], { accentColor: C.primary });
  contentCard(s, 6.9, 2.0, 6.0, 5.0, "Their own failure modes", [
    "False positives that block legitimate traffic — the silent product-killer.",
    "Latency inflation — 5 × 50 ms guardrails = 250 ms tax on every call.",
    "Guardrail drift — if the guardrail IS a judge, it drifts when the judge is upgraded.",
    "Over-trust — a passing guardrail is not a proof of correctness; do not let it mute other signals.",
  ], { accentColor: C.danger });
  addFooter(s, ++n, TOTAL);
}

// ---- 8. Guardrail design patterns ----------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.bg2 };
  addSectionTag(s, "02 / Guardrails");
  addTitle(s, "Five design patterns worth owning");
  const items = [
    { t: "Fail-closed vs. fail-open — per check, not globally",
      d: "Prompt-injection: closed.  Toxicity on casual chat: probably open with a log." },
    { t: "Retry-with-repair",
      d: "On schema-invalid output, feed validator error back to the model (once)." },
    { t: "Fallback chains",
      d: "Cheap → strong → canned → human. Each layer has a different latency/cost/quality profile." },
    { t: "Circuit breakers",
      d: "If rejection rate crosses 3× baseline for 5 minutes — roll back. Rejection rate is almost always the first signal." },
    { t: "Every guardrail emits an event",
      d: "A silent reject is worse than nothing. Debugging requires visibility." },
  ];
  items.forEach((it, i) => {
    const y = 2.05 + i * 0.95;
    // Circle with number
    s.addShape(pres.shapes.OVAL, {
      x: 0.7, y, w: 0.55, h: 0.55, fill: { color: C.primary }, line: { color: C.primary },
    });
    s.addText(String(i + 1), {
      x: 0.7, y, w: 0.55, h: 0.55, fontSize: 20, bold: true, color: C.white,
      fontFace: FONT_H, align: "center", valign: "middle", margin: 0,
    });
    s.addText(it.t, {
      x: 1.45, y, w: 11.5, h: 0.3, fontSize: 16, bold: true, color: C.midnight,
      fontFace: FONT_H, margin: 0,
    });
    s.addText(it.d, {
      x: 1.45, y: y + 0.3, w: 11.5, h: 0.55, fontSize: 13, color: C.textDim,
      fontFace: FONT_B, margin: 0,
    });
  });
  addFooter(s, ++n, TOTAL);
}

// ---- 9. Section 03 divider -----------------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  s.addText("03", {
    x: 0.8, y: 2.0, w: 3, h: 3, fontSize: 200, bold: true,
    color: C.teal, fontFace: FONT_H, margin: 0,
  });
  s.addText("Logging & structured events", {
    x: 4.0, y: 3.0, w: 8.5, h: 2, fontSize: 36, bold: true,
    color: C.white, fontFace: FONT_H, margin: 0,
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 4.0, y: 4.8, w: 1.0, h: 0.05, fill: { color: C.accent }, line: { color: C.accent },
  });
  s.addText("One row per LLM call — in a table an analyst could use", {
    x: 4.0, y: 4.95, w: 8, h: 0.4, fontSize: 14, color: C.bg2, fontFace: FONT_H, italic: true, margin: 0,
  });
  addFooter(s, ++n, TOTAL);
}

// ---- 10. What to log / PII ----------------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.bg2 };
  addSectionTag(s, "03 / Logging");
  addTitle(s, "What to log — and what not to");
  contentCard(s, 0.6, 2.0, 6.1, 5.0, "Per LLM call", [
    "Identity — trace_id, span_id, parent_span_id, hashed user/session id.",
    "Config — model, model_version, prompt_version, temperature, seed, tool set.",
    "I/O — input & output token counts. Prompts/responses gated by environment.",
    "Tools — which tool, redacted args, per-tool latency and outcome.",
    "Economics — wall-clock latency, $ cost, retries, guardrail verdicts.",
    "Outcome — ok / repaired / rejected / failed / fallback.",
  ], { accentColor: C.primary });
  contentCard(s, 6.9, 2.0, 6.0, 5.0, "PII & secrets — patterns that hold up", [
    "Hash identifiers, don't store them — sha256(user_id + salt)[:16].",
    "Environment-gated verbosity — DEBUG in dev, INFO in prod. Prompts to a separate short-retention store.",
    "Redactors sit between producer and sink — scrub email/phone/SSN into typed placeholders.",
    "Never log secrets — wrap them in types whose __repr__ returns \"***\".",
    "Retention policy, written down — part of the logging design, not an afterthought.",
  ], { accentColor: C.danger });
  addFooter(s, ++n, TOTAL);
}

// ---- 11. Log levels for AI ----------------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.bg2 };
  addSectionTag(s, "03 / Logging");
  addTitle(s, "Log levels, for AI systems specifically");
  const levels = [
    ["DEBUG",    "Full prompt/response payloads, per-token events.",          "Dev & staging only.",   C.textDim],
    ["INFO",     "Normal turn records — model, tokens, latency, cost, outcome.", "Prod default.",       C.primary],
    ["WARNING",  "Guardrail repairs, fallbacks triggered, tool retries.",     "Something is bending.", C.accent],
    ["ERROR",    "Guardrail failures, unrecoverable tool errors, retry exhaustion.", "Broken path.",  C.danger],
    ["CRITICAL", "Safety-policy violations, PII leaks, cost breaches at tenant scope.", "Pages a human.", C.danger],
  ];
  levels.forEach((lv, i) => {
    const y = 2.1 + i * 0.9;
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.7, y, w: 1.7, h: 0.75, fill: { color: lv[3] }, line: { color: lv[3] },
    });
    s.addText(lv[0], {
      x: 0.7, y, w: 1.7, h: 0.75, fontSize: 18, bold: true, color: C.white,
      fontFace: FONT_M, align: "center", valign: "middle", margin: 0,
    });
    s.addText(lv[1], {
      x: 2.6, y: y + 0.05, w: 7.8, h: 0.35, fontSize: 14, color: C.text,
      fontFace: FONT_B, margin: 0,
    });
    s.addText(lv[2], {
      x: 2.6, y: y + 0.4, w: 7.8, h: 0.35, fontSize: 12, color: C.textDim,
      fontFace: FONT_B, italic: true, margin: 0,
    });
  });
  addFooter(s, ++n, TOTAL);
}

// ---- 12. Section 04 divider ----------------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  s.addText("04", {
    x: 0.8, y: 2.0, w: 3, h: 3, fontSize: 200, bold: true,
    color: C.teal, fontFace: FONT_H, margin: 0,
  });
  s.addText("Tracing & observability", {
    x: 4.0, y: 3.0, w: 8.5, h: 2, fontSize: 36, bold: true,
    color: C.white, fontFace: FONT_H, margin: 0,
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 4.0, y: 4.8, w: 1.0, h: 0.05, fill: { color: C.accent }, line: { color: C.accent },
  });
  s.addText("A causal graph of your agent's thinking", {
    x: 4.0, y: 4.95, w: 8, h: 0.4, fontSize: 14, color: C.bg2, fontFace: FONT_H, italic: true, margin: 0,
  });
  addFooter(s, ++n, TOTAL);
}

// ---- 13. What a trace looks like -----------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.bg2 };
  addSectionTag(s, "04 / Tracing");
  addTitle(s, "What a well-instrumented agent trace looks like");
  // Monospace ASCII tree
  const tree = [
    "agent.run   trace_id=t-abc · prompt.version=v7 · user.hash=…",
    " ├─ llm.call          model=gpt-x · in=812 · out=22        [decides to search]",
    " ├─ tool.call         name=search · latency=320ms · ok",
    " ├─ guardrail.check   name=schema · verdict=ok",
    " ├─ llm.call          model=gpt-x · in=994 · out=134       [final answer]",
    " ├─ guardrail.check   name=toxicity · verdict=ok",
    " └─ outcome           cost=$0.0041 · latency=1420ms",
  ];
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: 2.1, w: 9.1, h: 3.7, fill: { color: C.bg },
    line: { color: C.teal, width: 0.5 },
  });
  s.addText(
    tree.map((t, i) => ({ text: t, options: { breakLine: i < tree.length - 1 } })),
    { x: 0.85, y: 2.25, w: 8.8, h: 3.4, fontSize: 13,
      color: C.white, fontFace: FONT_M, margin: 0, paraSpaceAfter: 2 },
  );
  // GenAI conventions panel
  contentCard(s, 9.9, 2.1, 3.0, 3.7, "Use GenAI conventions", [
    "gen_ai.system",
    "gen_ai.request.model",
    "gen_ai.usage.input_tokens",
    "gen_ai.usage.output_tokens",
    "gen_ai.response.finish_reason",
    "Standard names → portable across Phoenix / Jaeger / Tempo / Langfuse.",
  ], { accentColor: C.teal });
  s.addText(
    "If you cannot reconstruct a bad output from its trace alone, you are not observable yet.",
    { x: 0.6, y: 6.1, w: 12.3, h: 0.7, fontSize: 16, italic: true, color: C.teal, fontFace: FONT_H, margin: 0 },
  );
  addFooter(s, ++n, TOTAL);
}

// ---- 14. Landscape + build vs buy ----------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.bg2 };
  addSectionTag(s, "04 / Tracing · the landscape");
  addTitle(s, "What's out there — and when to reach for it");
  const tools = [
    ["Phoenix",       "Arize · OSS",      "LLM-native UI; built-in judge runners on stored traces.\nReach for it: trace↔eval round-tripping."],
    ["Langfuse",      "OSS, self-host",   "Strong dataset/experiment management; promote trace → golden set.\nReach for it: tight offline/online loop."],
    ["Jaeger",        "CNCF · OSS",       "Classic distributed tracing; mature search at scale; not GenAI-aware.\nReach for it: embedding AI in an existing microservice stack."],
    ["LangSmith",     "LangChain · hosted", "Tight LangChain integration; trace + eval workflows.\nReach for it: already on LangChain."],
    ["Grafana Tempo", "OSS",               "High-scale trace storage; pairs with Grafana + Loki.\nReach for it: long retention, infra-metric correlation."],
  ];
  tools.forEach((t, i) => {
    const y = 2.0 + i * 0.92;
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.6, y, w: 8.2, h: 0.8, fill: { color: C.white },
      line: { color: "E2E8F0", width: 0.5 },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.6, y, w: 0.08, h: 0.8, fill: { color: C.teal }, line: { color: C.teal },
    });
    s.addText(t[0], {
      x: 0.85, y: y + 0.05, w: 2.2, h: 0.3, fontSize: 15, bold: true, color: C.midnight,
      fontFace: FONT_H, margin: 0,
    });
    s.addText(t[1], {
      x: 0.85, y: y + 0.4, w: 2.2, h: 0.3, fontSize: 10, color: C.textDim,
      fontFace: FONT_B, italic: true, margin: 0,
    });
    s.addText(t[2], {
      x: 3.1, y: y + 0.05, w: 5.6, h: 0.7, fontSize: 11, color: C.text,
      fontFace: FONT_B, margin: 0, paraSpaceAfter: 1,
    });
  });
  thesisBlock(s, 9.1, 2.0, 3.8,
    "Build vs. buy",
    "Build when you're learning or your needs are unusual. Adopt for scale, team workflows, or trace↔dataset round-tripping.",
    C.accent);
  addFooter(s, ++n, TOTAL);
}

// ---- 15. Section 05: CI & Reporting --------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  s.addText("05", {
    x: 0.8, y: 2.0, w: 3, h: 3, fontSize: 200, bold: true,
    color: C.teal, fontFace: FONT_H, margin: 0,
  });
  s.addText("CI-integrated eval harnesses & reporting", {
    x: 4.0, y: 3.0, w: 8.5, h: 2, fontSize: 32, bold: true,
    color: C.white, fontFace: FONT_H, margin: 0,
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 4.0, y: 4.8, w: 1.0, h: 0.05, fill: { color: C.accent }, line: { color: C.accent },
  });
  s.addText("Offline, online, and a weekly number you can defend", {
    x: 4.0, y: 4.95, w: 8, h: 0.4, fontSize: 14, color: C.bg2, fontFace: FONT_H, italic: true, margin: 0,
  });
  addFooter(s, ++n, TOTAL);
}

// ---- 16. Offline + Online ------------------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.bg2 };
  addSectionTag(s, "05 / CI & online eval");
  addTitle(s, "Same rubric, two cadences");
  contentCard(s, 0.6, 2.0, 6.1, 5.0, "Offline — the CI gate", [
    "Run the golden set on every PR that touches prompts / tools / loop.",
    "Budget capped: tokens, wall-clock, dollars.",
    "Regression = significantly worse (L8–L9 uncertainty), not \"mean went down.\"",
    "Pin everything in the artifact: dataset, judge, prompt, git SHA.",
    "Flaky rubric = soft-fail, not silent pass.",
  ], { accentColor: C.primary });
  contentCard(s, 6.9, 2.0, 6.0, 5.0, "Online — live traffic", [
    "Canary: 1–5% of traffic to the new version; compare judge scores & guardrail rates.",
    "Shadow: real inputs, judged outputs never reach users. Safe for high-risk changes.",
    "Sampled LLM-as-judge in prod — with its own human-agreement tracking.",
    "Drift signals: rising rejection rate, shifting input embedding, tool-call mix change.",
    "User signal: thumbs, retries, handoff rate, abandonment.",
  ], { accentColor: C.teal });
  addFooter(s, ++n, TOTAL);
}

// ---- 17. Anatomy of a weekly report --------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.bg2 };
  addSectionTag(s, "05 / Reporting");
  addTitle(s, "Anatomy of a useful weekly report");
  const bits = [
    ["01", "One quality number",   "With a confidence interval. A move inside the CI is not news.", C.primary],
    ["02", "One cost number",      "$ / successful request. Split into model / tool / guardrail if any is material.", C.teal],
    ["03", "One safety number",    "Guardrail rejection rate, plus sampled false-positive evidence.", C.danger],
    ["04", "Three sentences prose","Link the numbers to the week's deploys, dataset changes, incidents.", C.midnight],
    ["05", "One action item",      "What will we do next week because of this? A report without one becomes wallpaper.", C.accent],
  ];
  bits.forEach((b, i) => {
    const y = 2.0 + i * 0.95;
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.6, y, w: 0.9, h: 0.8, fill: { color: b[3] }, line: { color: b[3] },
    });
    s.addText(b[0], {
      x: 0.6, y, w: 0.9, h: 0.8, fontSize: 22, bold: true, color: C.white,
      fontFace: FONT_H, align: "center", valign: "middle", margin: 0,
    });
    s.addText(b[1], {
      x: 1.7, y: y + 0.05, w: 11, h: 0.35, fontSize: 16, bold: true, color: C.midnight,
      fontFace: FONT_H, margin: 0,
    });
    s.addText(b[2], {
      x: 1.7, y: y + 0.42, w: 11, h: 0.38, fontSize: 13, color: C.textDim,
      fontFace: FONT_B, margin: 0,
    });
  });
  addFooter(s, ++n, TOTAL);
}

// ---- 18. Close -----------------------------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  s.addText("WRAP", {
    x: 0.8, y: 1.0, w: 12, h: 0.4, fontSize: 14, color: C.accent,
    fontFace: FONT_H, bold: true, charSpacing: 6, margin: 0,
  });
  s.addText("Monitoring IS engineering, once your system is non-deterministic.", {
    x: 0.8, y: 1.6, w: 12, h: 1.8, fontSize: 32, bold: true, color: C.white, fontFace: FONT_H, margin: 0,
  });
  const lines = [
    "• Every guardrail is a rubric from L7.",
    "• Every CI gate uses the uncertainty from L8–L9.",
    "• Every production trace is a potential new golden-set case.",
    "• Every weekly report decides what next week's experiments should be.",
  ];
  s.addText(
    lines.map((l, i) => ({ text: l, options: { breakLine: i < lines.length - 1 } })),
    { x: 0.8, y: 3.6, w: 11.5, h: 2.4, fontSize: 18, color: C.bg2, fontFace: FONT_H, paraSpaceAfter: 8, margin: 0 },
  );
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.8, y: 6.3, w: 0.8, h: 0.04, fill: { color: C.accent }, line: { color: C.accent },
  });
  s.addText("Lab: build an instrumented agent, a hand-rolled trace viewer, and a weekly report.", {
    x: 0.8, y: 6.4, w: 12, h: 0.4, fontSize: 14, italic: true, color: C.teal, fontFace: FONT_H, margin: 0,
  });
  addFooter(s, ++n, TOTAL);
}

// Write --------------------------------------------------------------------
pres.writeFile({ fileName: "monitoring_slides.pptx" })
    .then(f => console.log(`Wrote ${f} — ${n} slides`));
