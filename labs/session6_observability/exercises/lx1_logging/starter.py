"""
Lab exercise LX-1 — Extend the logging primitives.

Pairs with Demo 1. Read `README.md` in this folder for the task description
and the success criteria.

The JSON-logging boilerplate is pre-wired below (copied straight from
Demo 1) so you can focus on picking the right primitive at each step
inside `charge()` and on writing a driver that exercises all three.

Run with:  python starter.py
"""

import json
import logging
import sys
from dataclasses import dataclass


# ---- Logging boilerplate. You do not need to edit this section. ------------

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


def configure_logging(level=logging.INFO):
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    for h in (logging.StreamHandler(sys.stdout), logging.FileHandler("charge.log", "a")):
        h.setFormatter(JsonFormatter())
        root.addHandler(h)


log = logging.getLogger("lx1")


# ---- Domain types. Pre-defined so you can focus on `charge()`. -------------

class InsufficientFundsError(Exception):
    """Raised when a charge would take the balance below zero."""


@dataclass
class Account:
    account_id: str
    balance: float


# ---- YOUR TASK starts here. Implement `charge()` and the driver. -----------

def charge(account: Account, amount: float, low_balance_threshold: float = 10.0) -> float:
    """
    Apply a charge to `account`. Return the new balance.

    Requirements:
      1. `amount` must be > 0. A caller passing <= 0 has a bug — this is an
         invariant, not a user-visible error. Pick the primitive that matches.
      2. If `account.balance < amount`, raise `InsufficientFundsError`.
         Log something useful first so the operator can see why.
      3. On success, log at INFO with `account_id`, `amount`, and
         `balance_after` in the extras.
      4. After a successful charge, if the resulting balance is below
         `low_balance_threshold`, emit a WARNING with the relevant fields.

    Hint: `assert` and `raise` each appear exactly once. `log.*` appears at
    least twice (INFO on success + WARNING when crossing the threshold).
    """
    raise NotImplementedError("Implement charge().")


def main() -> None:
    """
    Drive `charge` through TEN calls that together trigger every primitive:
      -  1 call with an invalid amount (invariant violation — let it crash).
      -  2 calls that exceed the balance (InsufficientFundsError).
      -  7 calls with valid amounts; at least one should cross the
         low-balance threshold.

    Order matters: put the invariant-violating call LAST, otherwise the
    process crashes before the other cases run.
    """
    configure_logging(logging.INFO)
    acct = Account(account_id="acct_001", balance=100.0)

    # Your 10 calls go here.
    raise NotImplementedError("Fill in the driver.")


if __name__ == "__main__":
    main()


# -----------------------------------------------------------------------------
# REFLECTION (required — write 3 short lines before submitting):
#
# For each primitive, in one line: what would change about your code — or
# about the observable behaviour — if you picked the WRONG primitive at this
# site?
#
#   assert : ...
#   raise  : ...
#   log    : ...
# -----------------------------------------------------------------------------
