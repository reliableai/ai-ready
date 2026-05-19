# LX-1 · Extend the logging primitives

Pairs with [Demo 1](../../demos/1_basic_logging/README.md). ~25 minutes.

## Background

Demo 1 showed the three Python primitives in isolation: `assert` for
invariants, `raise` for recoverable-by-caller conditions, `log.info/warning`
for every interesting outcome. This exercise makes you choose between
them under pressure — the same `charge()` call has to handle an
invariant violation, a recoverable business condition, and a
flow-of-business event in three consecutive lines. Get the choices
right and the resulting log is queryable, the traceback points at real
bugs, and `python -O` doesn't silently weaken your correctness checks.

## Task

Starting from `starter.py`, implement a `charge(account, amount)` function
that uses each of the three Python primitives in the right place, and drive
it with ten calls.

The rules for `charge()`:

| # | Requirement | Which primitive |
| --- | --- | --- |
| 1 | `amount` must be > 0. A caller passing <= 0 has a bug. | `assert` |
| 2 | If the balance is below `amount`, refuse the charge. The caller can recover. | `raise InsufficientFundsError` |
| 3 | Every successful charge is recorded with `account_id`, `amount`, `balance_after`. | `log.info` |
| 4 | After a successful charge, if the balance is below the threshold, emit a warning. | `log.warning` |

The rules for the driver:

- **10 calls total.** 1 invalid amount, 2 balance-exceeding, 7 valid (at least one of which crosses the low-balance threshold).
- **Invariant violation comes last.** Otherwise your program crashes before the other cases run.
- **Do not catch the final `AssertionError`.** Let it propagate — a loud crash is the correct response to an invariant violation during development.

## How to run

```bash
python starter.py
```

The script writes JSON rows to stdout and appends them to `charge.log` in
this folder. The process should exit with a traceback at the end.

## What to submit

- Your completed `starter.py` (reflection section at the bottom filled in).
- The `charge.log` produced by running it once.

## Success criteria

1. Running the script produces a well-formed JSON log file and exits with
   a final `AssertionError` traceback.
2. Every log row parses as JSON:
   ```bash
   python -c "import json; [json.loads(l) for l in open('charge.log')]; print('ok')"
   ```
3. Running with `configure_logging(logging.WARNING)` produces strictly
   fewer lines than `configure_logging(logging.INFO)`.
4. The invariant-violating call is **not** caught — it propagates out of
   `main` and exits the process.
5. The three-line reflection at the bottom of `starter.py` is filled in.

## Common pitfalls

- Using `assert` for the insufficient-funds case. `assert` gets stripped
  under `python -O`; security- or correctness-sensitive checks must use
  `raise`.
- Using `log.error` for insufficient funds. The caller recovered — that's
  not an error, it's an ordinary business outcome. Use `log.info`.
- Wrapping the final `charge(acct, -5)` in `try/except AssertionError`.
  That hides the invariant violation and is strictly worse than crashing.
- Putting `amount` or `balance` into the log message string instead of
  into `extra={}`. Rows then are not queryable by field.

## Hints

- The decision table in the *Task* section is also the answer key. If
  you find yourself reaching for `raise` to signal an invariant
  violation, re-read row 1. If you're tempted to `log.error` a
  rejected charge, re-read row 2.
- `assert x > 0, "msg"` is the shortest form; resist wrapping it in
  `if not x > 0: raise AssertionError(...)`. The assert statement is
  the whole point.
- Use one `configure_logging(level)` call at the top of `main()` and
  don't touch the root logger anywhere else. You want a single place
  where log verbosity is decided.
- The driver's ordering matters: valid calls first, then
  insufficient-funds, then the invariant violation *last*. Otherwise
  your program exits before the logger sees the interesting rows.

## What this drills

- **Severity is a design choice, not a formatting choice.** The
  difference between `info`, `warning`, and `raise` is which part of
  the system is responsible for handling the case — not which colour
  it prints in. This exercise forces four micro-decisions in the same
  function.
- **Structured > stringified.** Logs with `extra={"field": value}`
  are queryable (Splunk / Datadog / ELK all treat them as fields);
  logs with f-strings are grep-able at best. You feel the difference
  the moment you try to build LX-2's dashboard.
- **Invariant violations should crash.** `python -O` strips asserts;
  if you use `assert` for correctness, production runs silently skip
  the check. This is why row 1 of the decision table says `assert`
  for invariants *that reflect a caller bug*, not for
  security-critical checks.

## What's out of scope

- **Rotating log files / log shipping.** A production deploy points
  the file handler at a rotator and ships JSON to an aggregator;
  here we just append to `charge.log`.
- **Structured exceptions.** A real system defines a hierarchy
  (`ChargeError → InsufficientFunds`, `InvalidAmount`, …). One
  subclass is enough for the exercise.
- **Sampling / rate limits.** With 10 calls, every row lands. A live
  service might sample `info` at 1%.
