"""
monitoring_lab.py — instrument `minimal_agent.run_agent` three ways:

  1. Structured JSON logging (stdlib logging + a JsonFormatter)
  2. OpenTelemetry tracing (GenAI semantic conventions, ConsoleSpanExporter
     tee'd to spans.jsonl so the hand-rolled trace_viewer.py can render it)
  3. Two guardrails: schema validation with retry-with-repair, and a
     simple toxicity stub

Also runs the agent on `golden_set.json`, scores it with a mock rubric
judge, and emits `report.json` with aggregate metrics.

Run:
    python monitoring_lab.py --prompt-version v1
    python trace_viewer.py spans.jsonl --out trace.html
"""
from __future__ import annotations
import argparse, hashlib, io, json, logging, os, sys, time, uuid
from dataclasses import dataclass, asdict, field
from typing import Any, Callable, Optional

# --- Third-party (students install these: see README) ----------------------
# pip install opentelemetry-api opentelemetry-sdk pydantic
from pydantic import BaseModel, ValidationError  # noqa: E402
from opentelemetry import trace                   # noqa: E402
from opentelemetry.sdk.trace import TracerProvider             # noqa: E402
from opentelemetry.sdk.trace.export import (                   # noqa: E402
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

from minimal_agent import run_agent, mock_llm, AgentResult, PROMPT_V1, PROMPT_V2


# ===========================================================================
# 1. Structured JSON logging
# ===========================================================================

_SALT = os.environ.get("HASH_SALT", "rotate-me-per-deploy")

def hash_id(value: str) -> str:
    return hashlib.sha256((_SALT + value).encode()).hexdigest()[:16]


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any]
        if isinstance(record.msg, dict):
            payload = dict(record.msg)
        else:
            payload = {"message": record.getMessage()}
        payload["level"] = record.levelname
        payload["logger"] = record.name
        payload["ts"] = record.created
        return json.dumps(payload, default=str)


def setup_logging() -> logging.Logger:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(h)
    root.setLevel(logging.INFO)
    return logging.getLogger("agent")


# ===========================================================================
# 2. OpenTelemetry tracing
# ===========================================================================
#
# We tee spans to both the console (for live inspection) *and* a JSONL file
# so the hand-rolled trace_viewer.py can render them. The JsonlFileExporter
# below is ~20 lines of SpanExporter that serialises each span to one line.

from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace import Span

class JsonlFileExporter(SpanExporter):
    """Emit one JSON object per span to a file. Stable schema for the viewer."""
    def __init__(self, path: str):
        self.path = path
        # Truncate at start of run.
        open(self.path, "w").close()

    def export(self, spans) -> SpanExportResult:
        with open(self.path, "a") as f:
            for s in spans:
                ctx = s.get_span_context()
                parent = s.parent
                rec = {
                    "name":           s.name,
                    "trace_id":       f"{ctx.trace_id:032x}",
                    "span_id":        f"{ctx.span_id:016x}",
                    "parent_span_id": f"{parent.span_id:016x}" if parent else None,
                    "start_ns":       s.start_time,
                    "end_ns":         s.end_time,
                    "attributes":     dict(s.attributes or {}),
                    "events": [
                        {"name": e.name, "ts": e.timestamp,
                         "attributes": dict(e.attributes or {})}
                        for e in (s.events or [])
                    ],
                    "status":         s.status.status_code.name,
                }
                f.write(json.dumps(rec, default=str) + "\n")
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass


def setup_tracing(spans_path: str = "spans.jsonl") -> trace.Tracer:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(JsonlFileExporter(spans_path)))
    # Uncomment the next two lines to also print spans to stdout:
    # provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    # --- Swap to any OTel backend with one line (Phoenix/Jaeger/Tempo/…):
    # from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    # provider.add_span_processor(SimpleSpanProcessor(
    #     OTLPSpanExporter(endpoint="http://localhost:4318/v1/traces")))
    trace.set_tracer_provider(provider)
    return trace.get_tracer("agent")


# ===========================================================================
# 3. Guardrails
# ===========================================================================

class Decision(BaseModel):
    action: str        # "answer" or "search"
    query: Optional[str] = None
    answer: Optional[str] = None
    confidence: float = 0.0


# Very dumb "toxicity" stub — regex over banned words. A real guardrail
# would call a classifier or a judge LLM; here we keep it deterministic so
# students see the plumbing, not the ML.
_BANNED = {"kill", "hateful", "slur"}

def toxicity_guardrail(text: str) -> tuple[str, str]:
    """Return (verdict, note). Verdict in {ok, rejected}."""
    lowered = text.lower()
    for bad in _BANNED:
        if bad in lowered:
            return "rejected", f"contains banned token '{bad}'"
    return "ok", ""


def schema_guardrail(raw: str) -> tuple[str, Decision | None, str]:
    """Return (verdict, parsed_or_none, note). Verdict in {ok, rejected}."""
    try:
        return "ok", Decision.model_validate_json(raw), ""
    except ValidationError as e:
        return "rejected", None, str(e)[:200]


# ===========================================================================
# 4. Instrumented runner — wraps minimal_agent.run_agent with full
#    logging + tracing + guardrails + retry-with-repair.
# ===========================================================================

@dataclass
class TurnRecord:
    case_id: str
    trace_id: str
    prompt_version: str
    question: str
    answer: str
    tool_calls: int
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: float
    guardrail_schema: str
    guardrail_toxicity: str
    outcome: str
    judge_score: float | None = None


def estimate_tokens(s: str) -> int:
    """Rough token count — 1 token ≈ 4 chars. Good enough for a teaching lab."""
    return max(1, len(s) // 4)


def cost_of(input_tokens: int, output_tokens: int,
            in_rate: float = 0.15e-6, out_rate: float = 0.60e-6) -> float:
    return input_tokens * in_rate + output_tokens * out_rate


def run_instrumented(
    case: dict,
    prompt_version: str,
    tracer: trace.Tracer,
    log: logging.Logger,
    llm: Callable[[str], str] = mock_llm,
    broken: bool = False,
) -> TurnRecord:
    """Run a single case with full instrumentation."""
    question = case["question"]
    case_id = case["id"]
    t0 = time.time()

    with tracer.start_as_current_span("agent.run") as root:
        ctx = root.get_span_context()
        trace_id = f"{ctx.trace_id:032x}"
        root.set_attribute("user.hash", hash_id(case_id))
        root.set_attribute("prompt.version", prompt_version)
        root.set_attribute("question.len", len(question))

        # Wrap the llm callable to emit spans + the schema guardrail.
        repair_attempts = {"n": 0}

        def traced_llm(prompt: str) -> str:
            with tracer.start_as_current_span("llm.call") as span:
                span.set_attribute("gen_ai.system", "mock")
                span.set_attribute("gen_ai.request.model", "mock-v1")
                span.set_attribute("prompt.version", prompt_version)
                it = estimate_tokens(prompt)
                raw = llm(prompt, seed=hash(case_id) & 0xFFFFFFFF, broken=broken) \
                      if llm is mock_llm else llm(prompt)
                ot = estimate_tokens(raw)
                span.set_attribute("gen_ai.usage.input_tokens", it)
                span.set_attribute("gen_ai.usage.output_tokens", ot)

                # Schema guardrail + retry-with-repair (max 1 retry).
                verdict, _, note = schema_guardrail(raw)
                with tracer.start_as_current_span("guardrail.check") as g:
                    g.set_attribute("guardrail.name", "schema")
                    g.set_attribute("guardrail.verdict", verdict)
                    if note:
                        g.set_attribute("guardrail.note", note)

                if verdict == "rejected" and repair_attempts["n"] < 1:
                    repair_attempts["n"] += 1
                    with tracer.start_as_current_span("llm.repair") as rs:
                        rs.set_attribute("prompt.version", prompt_version)
                        raw2 = llm(
                            prompt + "\nPrevious response was invalid JSON; "
                                     "please reply with valid JSON only.",
                            seed=(hash(case_id) ^ 0xA5A5A5) & 0xFFFFFFFF,
                            broken=False,
                        ) if llm is mock_llm else llm(prompt)
                        raw = raw2
                        rs.set_attribute("gen_ai.usage.output_tokens",
                                         estimate_tokens(raw2))
                return raw

        try:
            result: AgentResult = run_agent(
                question, llm=traced_llm, prompt_version=prompt_version,
            )
            answer = result.answer
            outcome = "ok" if repair_attempts["n"] == 0 else "repaired"
        except Exception as e:                               # noqa: BLE001
            root.record_exception(e)
            answer = ""
            outcome = "failed"
            result = AgentResult(answer="", tool_calls=0, raw_decisions=[])

        # Output-side toxicity guardrail.
        tox_verdict, tox_note = toxicity_guardrail(answer)
        with tracer.start_as_current_span("guardrail.check") as g:
            g.set_attribute("guardrail.name", "toxicity")
            g.set_attribute("guardrail.verdict", tox_verdict)
            if tox_note:
                g.set_attribute("guardrail.note", tox_note)
        if tox_verdict == "rejected":
            outcome = "rejected"
            answer = "[redacted by policy]"

        latency_ms = int((time.time() - t0) * 1000)
        # Token bookkeeping — sum across llm spans would be more precise,
        # but for the teaching lab we approximate from question+answer.
        input_tokens = estimate_tokens(question) * (1 + result.tool_calls)
        output_tokens = estimate_tokens(answer or "")
        cost = cost_of(input_tokens, output_tokens)

        root.set_attribute("outcome", outcome)
        root.set_attribute("cost.usd", cost)
        root.set_attribute("latency.ms", latency_ms)

        record = TurnRecord(
            case_id=case_id, trace_id=trace_id, prompt_version=prompt_version,
            question=question, answer=answer, tool_calls=result.tool_calls,
            input_tokens=input_tokens, output_tokens=output_tokens,
            latency_ms=latency_ms, cost_usd=cost,
            guardrail_schema="repaired" if outcome == "repaired" else (
                "ok" if outcome not in ("failed",) else "failed"),
            guardrail_toxicity=tox_verdict, outcome=outcome,
        )
        log.info({"event": "agent.turn", **asdict(record)})
        return record


# ===========================================================================
# 5. Mock rubric judge (from L7, simplified)
# ===========================================================================

def judge(case: dict, record: TurnRecord) -> float:
    """Return a score in [0, 1]. Deterministic, substring-based rubric."""
    if record.outcome in ("failed", "rejected"):
        return 0.0
    expected = case.get("expect_substring", "").lower()
    actual = (record.answer or "").lower()
    if not expected:
        return 0.5
    return 1.0 if expected in actual else 0.0


# ===========================================================================
# 6. Aggregate report
# ===========================================================================

def aggregate_report(records: list[TurnRecord]) -> dict:
    n = len(records)
    if n == 0:
        return {"n": 0}
    scored = [r.judge_score for r in records if r.judge_score is not None]
    mean_score = sum(scored) / len(scored) if scored else 0.0
    guardrail_rejects = sum(1 for r in records if r.guardrail_toxicity == "rejected"
                            or r.outcome == "failed")
    repaired = sum(1 for r in records if r.outcome == "repaired")
    return {
        "n": n,
        "mean_score": round(mean_score, 4),
        "p50_latency_ms": sorted(r.latency_ms for r in records)[n // 2],
        "p95_latency_ms": sorted(r.latency_ms for r in records)[min(n - 1, int(n * 0.95))],
        "total_cost_usd": round(sum(r.cost_usd for r in records), 6),
        "guardrail_reject_rate": round(guardrail_rejects / n, 4),
        "repair_rate":           round(repaired / n, 4),
        "outcomes": {
            o: sum(1 for r in records if r.outcome == o)
            for o in ("ok", "repaired", "rejected", "failed")
        },
    }


# ===========================================================================
# 7. Entry point
# ===========================================================================

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt-version", default="v1", choices=["v1", "v2"])
    ap.add_argument("--broken", action="store_true",
                    help="Inject malformed JSON ~50%% of the time (exercise 2).")
    ap.add_argument("--golden", default="golden_set.json")
    ap.add_argument("--spans",  default="spans.jsonl")
    ap.add_argument("--report", default="report.json")
    args = ap.parse_args()

    log = setup_logging()
    tracer = setup_tracing(args.spans)

    with open(args.golden) as f:
        data = json.load(f)

    records: list[TurnRecord] = []
    for case in data["cases"]:
        rec = run_instrumented(
            case, prompt_version=args.prompt_version,
            tracer=tracer, log=log, broken=args.broken,
        )
        rec.judge_score = judge(case, rec)
        records.append(rec)

    report = aggregate_report(records)
    report["prompt_version"] = args.prompt_version
    report["broken"] = args.broken
    with open(args.report, "w") as f:
        json.dump({
            "summary": report,
            "records": [asdict(r) for r in records],
        }, f, indent=2)
    log.info({"event": "run.complete", **report})
    print("\nWrote:", args.spans, args.report)


if __name__ == "__main__":
    main()
