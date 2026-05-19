# %% [markdown]
# # Demo 1 — Basic logging primitives
#
# Three Python controls for "something unexpected happened":
#
#     assert  — invariant. A violation means the caller has a bug.
#     raise   — expected-but-exceptional flow (bad input, network, etc.).
#     logging — side channel: records what happened, does not change control flow.
#
# The happy cases and the raise case run twice — once at INFO, once at DEBUG —
# so you can see what the level knob filters out. JSON rows go to stdout and
# to `./app.log`.
#
# Then the script deliberately triggers an invariant violation and crashes.
# During development that is the right shape of failure: loud, immediate,
# traceable. Silent failures are worse than crashes.
#
# Run as a script (`python demo.py`) or step through cell-by-cell in VS Code /
# Jupyter / any editor that understands the `# %%` cell marker.

# %% Imports
import json
import logging
import sys


# %% JSON formatter
# All the attributes a vanilla LogRecord carries. Anything *not* in this set
# got there via `extra=` and should land in the JSON row.
_STDLIB_FIELDS = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message"}


class JsonFormatter(logging.Formatter):
    def format(self, record):
        row = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        row.update({k: v for k, v in vars(record).items() if k not in _STDLIB_FIELDS})
        return json.dumps(row)


log = logging.getLogger("demo1")


# %% The function from Slide 5 — three primitives, about ten lines
def divide(a, b):
    assert isinstance(a, (int, float)), f"a must be numeric, got {type(a).__name__}"
    log.debug("divide called", extra={"a": a, "b": b})
    if b == 0:
        log.warning("division by zero", extra={"a": a})
        raise ZeroDivisionError(f"cannot divide {a} by zero")
    result = a / b
    log.info("divide ok", extra={"a": a, "b": b, "result": result})
    return result


# %% Run-cases helper
def run_cases(level):
    print(f"\n=== level = {logging.getLevelName(level)} ===", file=sys.stderr)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    for h in (logging.StreamHandler(sys.stdout), logging.FileHandler("app.log", "a")):
        h.setFormatter(JsonFormatter())
        root.addHandler(h)

    divide(10, 2)                        # ordinary
    divide(7, 3)                         # ordinary
    try:
        divide(4, 0)                     # raise — caller recovers
    except ZeroDivisionError as e:
        log.error("caller caught divide failure", extra={"error": str(e)})


# %% INFO level — DEBUG rows are filtered out
run_cases(logging.INFO)

# %% DEBUG level — everything shows, including the "divide called" trace rows
run_cases(logging.DEBUG)

# %% Invariant violation — loud crash by design
# We do *not* catch this. In dev, a loud crash is exactly what we want — it
# points at the real bug with a full traceback. Silently swallowing an
# AssertionError would hide the problem and is strictly worse than a crash.
if __name__ == "__main__":
    print("\n=== invariant violation — program will now crash ===", file=sys.stderr)
    divide("ten", 2)
    # Unreachable — by design.

# %%
