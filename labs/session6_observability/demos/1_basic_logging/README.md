# Demo 1 — Basic logging primitives

Supports **Slide 5** of L10. Pairs with **lab exercise LX-1**.

## Purpose

Make the three Python control-flow primitives concrete before we introduce any
infrastructure:

| Primitive | What it's for | Who it's for |
| --- | --- | --- |
| `assert` | Invariants. A violation means the program has an internal bug. | Developer at the function's call site. |
| `raise` / `try` / `except` | Expected-but-exceptional flow. Bad input, missing file, network error. | The caller, who will recover or propagate. |
| `logging` | A side channel that records "this happened, here, with these values." Does not change control flow. | Anyone reading the log afterwards — operators, debuggers, auditors. |

## Learning outcome

After running and reading this demo, you should be able to:

1. Match each primitive to the situation it fits.
2. Read a JSON log row and name each field.
3. Predict which rows appear or disappear when you change the log level.
4. Explain why a single log file, written to disk with nothing else, is
   already useful — it's the data every later demo's dashboard reads from.

## How to run

```bash
python demo.py
```

The script writes mixed output to the terminal (each row is a single JSON
object; narration goes on stderr so you can follow along) and appends the
same JSON rows to `app.log` in this folder.

## What you should see

The script runs three cases twice — once with the logger at `INFO`, once at
`DEBUG` — and then deliberately crashes on a fourth case.

```
=== level = INFO ===
Case 1 — ordinary divide               → INFO  "divide ok"
Case 2 — another ordinary divide       → INFO  "divide ok"
Case 3 — b == 0                        → WARNING "division by zero"
                                         + ERROR "caller caught divide failure"

=== level = DEBUG ===
(same three cases, with an extra DEBUG "divide called" row before each one)

=== invariant violation — program will now crash ===
AssertionError: a must be numeric, got str
```

Confirm the shape of what landed on disk:

```bash
wc -l app.log                          # 11 rows per run — four from INFO,
                                       # seven from DEBUG. If you re-run the
                                       # script, rows append (22, 33, ...);
                                       # that's how logs behave in reality.
grep WARNING app.log                   # Just the warnings.
grep '"level": "DEBUG"' app.log        # Rows only the DEBUG run produced.
python -c "import json; [json.loads(l) for l in open('app.log')]; print('ok')"
                                       # Every row parses as JSON.
```

The crash itself does not write a log row — see the note at the bottom.

## Things worth pointing at during lecture

- **The same JSON shape across every row.** This is what makes later dashboards
  possible: they are aggregations over these rows, nothing more.
- **Case 3 produces two rows from a single call** — one `WARNING` from inside
  `divide()`, one `ERROR` from the `except` branch in the caller. Logging and
  exceptions are complementary, not alternatives.
- **The final case is not caught on purpose.** During development a loud crash
  is exactly what you want — the traceback points at the real bug. Silently
  swallowing an `AssertionError` would hide the problem and is strictly worse
  than a crash. Rule of thumb: in dev, crashes are fine; silent failures are
  not.
- **`assert` is stripped under `python -O`.** If any correctness depends on
  the assert firing, use `if ...: raise` instead. This is why `assert` is
  only for invariants — things that should never happen — and not for input
  validation.
- **`extra=` is the load-bearing parameter.** Everything you put in the
  `extra` dict becomes a top-level field in the JSON row. That is the bridge
  from a log *message* (a string for humans) to a log *event* (a structured
  object for machines).

## Why the crash does not produce a JSON row

The assert fires before any `log.*` call inside `divide()`. Python raises the
`AssertionError`, which propagates up to the top of the script and the
interpreter prints the traceback on stderr — the logger is never involved.
That is correct behaviour. An invariant violation is not a "normal event to
record"; it is a bug that should halt the program. The traceback itself is
the diagnostic artefact.

If you wanted an entry in `app.log` for *crashes themselves*, you would
install a top-level handler (`sys.excepthook`) — but that is a separate
concern from ordinary per-request logging, and we do not cover it here.

## Why no dashboard yet?

Intentional. This demo stops at the file. The point of Slide 5 is that a log
row on disk is already useful — even without any monitoring infrastructure on
top. Dashboards come in Demos 2 and 4, reading files that look exactly like
this one.
