# LX-5 · Instrumentation notes (reference)

Companion to `solution.py`. Covers the design choices in the reference
implementation and the half-dozen ways students get it subtly wrong.

## Span ID generation

The reference uses a deterministic counter (`_counter += 1`) hashed
into 16 hex chars. This makes the lab outputs byte-stable, which is
nice for grading but wrong for production. Real systems need
collision-resistant random IDs so that two traces generated on
different machines don't accidentally collide when merged.

In `opentelemetry-sdk`, the default id generator is `RandomIdGenerator`
which emits 64-bit trace IDs and 32-bit span IDs from `secrets.randbits`.
Students who swap in `uuid.uuid4().hex[:16]` get the same guarantee.

## Stack-based parents

The crucial invariant in `end_span` is:

```python
if self._stack and self._stack[-1] == span["span_id"]:
    self._stack.pop()
```

i.e. the pop is guarded by identity, not by length. Without this,
an inner span that exits via exception can pop the *outer* span's id
off the stack, and every subsequent start_span mis-identifies its
parent. The symptom is "my waterfall looks like a staircase" —
retrieval becomes a child of plan, answer a child of retrieval.

## Dict mutation after yield

Students sometimes return a brand-new dict from `start_span` and
then separately append it to `self.spans` from the context manager
exit hook. This works, but makes the `s["attributes"]["..."] = ...`
pattern fragile — if `s` and the appended-span are different objects,
attributes set by the caller disappear from the output.

The reference model is: *one dict, mutated in place, appended at end*.
The context manager yields the same object the caller mutates. The
eight keys are the contract; the attributes sub-dict is where the
caller lives.

## GenAI attribute naming

We set `gen_ai.step = "plan"` / `"answer"` as a local extension — this
is not in the OTel GenAI spec (which has `gen_ai.operation.name` for
the *API operation*, not the *agent phase*). If you care about
ecosystem tooling you use a prefix you own: `ourco.gen_ai.phase` or
`agent.phase`. We cheat for brevity.

The names that *are* in the spec and students should memorise:

  - `gen_ai.system` — "openai", "anthropic", "azure_openai", …
  - `gen_ai.request.model` — "gpt-4o-mini", "claude-3-5-sonnet-20240620", …
  - `gen_ai.operation.name` — "chat.completions", "embeddings", …
  - `gen_ai.usage.input_tokens` / `output_tokens`
  - `gen_ai.response.model` (the model the server actually routed to —
    can differ from request.model on some providers)
  - `gen_ai.response.finish_reasons` — array

## What this hides

- **Real async.** Our stack is a single-threaded contextvar; OTel's
  SDK uses `contextvars.ContextVar` so async/await re-entrancy works.
  The single-threaded stack blows up the moment you `asyncio.gather`.
- **Exporter.** We write to a local file. A real collector pipeline
  batches spans in memory, flushes on a timer or size trigger, retries
  on failure. Losing a span is usually preferable to blocking the
  user's request.
- **Baggage vs. context.** OTel separates "trace context" (used for
  parent-child) from "baggage" (user-defined propagated key-value
  pairs). We don't need baggage for a single-process demo, but the
  distinction matters the moment you add tenant_id.

## What a production variant looks like

Roughly this:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="..."))
)
tracer = trace.get_tracer("research-assistant")

def run_query(question: str) -> str:
    with tracer.start_as_current_span("research.task") as root:
        root.set_attribute("user.question", question)
        with tracer.start_as_current_span("llm.call") as s:
            s.set_attribute("gen_ai.system", "openai")
            # ...
```

Same mental model (context managers + stack + attributes), fifteen
extra lines of config. The lab's 20-line `Tracer` is the SDK's core
loop with the real things — ID generation, sampling, propagation,
export — stripped out for teaching.
