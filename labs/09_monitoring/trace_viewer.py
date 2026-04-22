"""
trace_viewer.py — a ~150-line HTML renderer for OTel spans.

Reads a JSONL file of spans (as produced by `JsonlFileExporter` in
monitoring_lab.py) and emits a single self-contained HTML file with a
collapsible span tree per trace. Pure stdlib — no external deps.

Usage:
    python trace_viewer.py spans.jsonl --out trace.html
"""
from __future__ import annotations
import argparse, html, json, sys
from collections import defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str
    parent_span_id: str | None
    start_ns: int
    end_ns: int
    attributes: dict[str, Any]
    events: list[dict]
    status: str

    @property
    def duration_ms(self) -> float:
        if not self.start_ns or not self.end_ns:
            return 0.0
        return (self.end_ns - self.start_ns) / 1_000_000

    @classmethod
    def from_row(cls, row: dict) -> "Span":
        return cls(
            name=row["name"],
            trace_id=row["trace_id"],
            span_id=row["span_id"],
            parent_span_id=row.get("parent_span_id") or None,
            start_ns=int(row.get("start_ns") or 0),
            end_ns=int(row.get("end_ns") or 0),
            attributes=row.get("attributes") or {},
            events=row.get("events") or [],
            status=row.get("status") or "UNSET",
        )


def load_spans(path: str) -> list[Span]:
    spans = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            spans.append(Span.from_row(json.loads(line)))
    return spans


def group_by_trace(spans: list[Span]) -> dict[str, list[Span]]:
    out: dict[str, list[Span]] = defaultdict(list)
    for s in spans:
        out[s.trace_id].append(s)
    return out


def build_tree(spans: list[Span]) -> tuple[list[Span], dict[str, list[Span]]]:
    """Return (roots, children_by_parent_id)."""
    by_parent: dict[str, list[Span]] = defaultdict(list)
    ids = {s.span_id for s in spans}
    roots = []
    for s in spans:
        if s.parent_span_id and s.parent_span_id in ids:
            by_parent[s.parent_span_id].append(s)
        else:
            roots.append(s)
    # Keep children in wall-clock order.
    for k in by_parent:
        by_parent[k].sort(key=lambda s: s.start_ns)
    roots.sort(key=lambda s: s.start_ns)
    return roots, by_parent


# --- Rendering -------------------------------------------------------------

CSS = """
body{font-family:'JetBrains Mono',ui-monospace,monospace;background:#0d1117;
     color:#c9d1d9;margin:0;padding:24px;}
h1{font-family:'Sora',sans-serif;font-weight:400;color:#58a6ff;
    letter-spacing:-0.02em;margin:0 0 24px 0;}
.trace{background:#161b22;border:1px solid #30363d;border-radius:8px;
        margin-bottom:20px;padding:16px;}
.trace-hdr{color:#8b949e;font-size:12px;margin-bottom:12px;
           border-bottom:1px solid #30363d;padding-bottom:8px;}
details{margin-left:16px;margin-top:4px;}
summary{cursor:pointer;padding:3px 0;list-style:none;}
summary::-webkit-details-marker{display:none;}
summary::before{content:"▸ ";color:#58a6ff;}
details[open]>summary::before{content:"▾ ";}
.name{color:#f0f6fc;font-weight:500;}
.dur{color:#8b949e;margin-left:8px;}
.verdict-ok{color:#3fb950;}
.verdict-rejected{color:#f85149;}
.verdict-repair{color:#d29922;}
.status-ERROR{color:#f85149;}
.attrs{color:#8b949e;font-size:12px;margin-left:24px;margin-top:2px;}
.attrs .k{color:#79c0ff;}
.attrs .v{color:#a5d6ff;}
.events{margin-left:24px;font-size:12px;color:#d29922;}
.legend{color:#8b949e;font-size:12px;margin-bottom:12px;}
"""


def _verdict_class(attrs: dict[str, Any]) -> str:
    v = str(attrs.get("guardrail.verdict", "")).lower()
    return {"ok": "verdict-ok", "rejected": "verdict-rejected",
            "repaired": "verdict-repair"}.get(v, "")


def render_span(s: Span, by_parent: dict[str, list[Span]]) -> str:
    vc = _verdict_class(s.attributes)
    st = f" status-{s.status}" if s.status == "ERROR" else ""
    attrs_html = "".join(
        f'<div><span class="k">{html.escape(str(k))}</span>='
        f'<span class="v">{html.escape(str(v))}</span></div>'
        for k, v in sorted(s.attributes.items())
    )
    events_html = "".join(
        f'<div>● {html.escape(e["name"])}</div>' for e in s.events
    )
    inner = [
        f'<summary class="{vc}{st}">'
        f'<span class="name">{html.escape(s.name)}</span>'
        f'<span class="dur">{s.duration_ms:.1f} ms</span>'
        f'</summary>',
        f'<div class="attrs">{attrs_html}</div>' if attrs_html else "",
        f'<div class="events">{events_html}</div>' if events_html else "",
    ]
    for child in by_parent.get(s.span_id, []):
        inner.append(render_span(child, by_parent))
    return "<details open>" + "".join(inner) + "</details>"


def render_trace(trace_id: str, spans: list[Span]) -> str:
    roots, by_parent = build_tree(spans)
    root_attrs = roots[0].attributes if roots else {}
    summary_bits = []
    for k in ("prompt.version", "outcome", "cost.usd", "latency.ms"):
        if k in root_attrs:
            summary_bits.append(f"{k}={root_attrs[k]}")
    summary = " · ".join(summary_bits) or "(no summary attrs)"
    body = "".join(render_span(r, by_parent) for r in roots)
    return (
        f'<div class="trace">'
        f'<div class="trace-hdr">trace {trace_id[:16]}… · {len(spans)} spans · {summary}</div>'
        f'{body}</div>'
    )


def render_html(spans: list[Span], title: str) -> str:
    traces = group_by_trace(spans)
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        f"<title>{html.escape(title)}</title>",
        "<link href='https://fonts.googleapis.com/css2?family=JetBrains+Mono&family=Sora&display=swap' rel='stylesheet'>",
        f"<style>{CSS}</style></head><body>",
        f"<h1>{html.escape(title)}</h1>",
        f"<div class='legend'>{len(traces)} trace(s) · {len(spans)} span(s)</div>",
    ]
    # Sort traces by earliest start span.
    for tid in sorted(traces, key=lambda t: min(s.start_ns for s in traces[t])):
        parts.append(render_trace(tid, traces[tid]))
    parts.append("</body></html>")
    return "".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("spans", help="Path to spans.jsonl")
    ap.add_argument("--out", default="trace.html")
    ap.add_argument("--title", default="Agent traces")
    args = ap.parse_args()
    spans = load_spans(args.spans)
    with open(args.out, "w") as f:
        f.write(render_html(spans, args.title))
    print(f"Rendered {len(spans)} span(s) from "
          f"{len(group_by_trace(spans))} trace(s) → {args.out}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
