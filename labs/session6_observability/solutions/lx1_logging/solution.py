"""
LX-1 reference solution — Instructor only.

Reference implementation of the exercise in
`../../exercises/lx1_logging/starter.py`. This is an anchor for grading,
not "the only right answer." See `../../solutions.md` for the full rubric
and the list of common failure modes.

Run with:  python solution.py
"""

import json
import logging
import sys
from dataclasses import dataclass


# ---- Logging boilerplate (same as Demo 1 / starter) ------------------------

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


# ---- Domain types ----------------------------------------------------------

class InsufficientFundsError(Exception):
    """Raised when a charge would take the balance below zero."""


@dataclass
class Account:
    account_id: str
    balance: float


# ---- Reference `charge` ----------------------------------------------------

def charge(account: Account, amount: float, low_balance_threshold: float = 10.0) -> float:
    # Invariant. A caller passing amount <= 0 has a bug.
    assert amount > 0, f"amount must be positive, got {amount}"

    # Expected-but-exceptional: balance too low. Caller can recover.
    if account.balance < amount:
        log.info(                                      # ordinary outcome, not an error
            "charge rejected",
            extra={"account_id": account.account_id, "amount": amount,
                   "balance": account.balance, "reason": "insufficient_funds"},
        )
        raise InsufficientFundsError(
            f"balance {account.balance:.2f} < amount {amount:.2f} "
            f"on account {account.account_id}"
        )

    # Happy path — update state, log it.
    account.balance -= amount
    log.info(
        "charge ok",
        extra={"account_id": account.account_id, "amount": amount,
               "balance_after": account.balance},
    )

    # Operational signal — not an error, but worth surfacing.
    if account.balance < low_balance_threshold:
        log.warning(
            "low balance after charge",
            extra={"account_id": account.account_id,
                   "balance_after": account.balance,
                   "threshold": low_balance_threshold},
        )
    return account.balance


# ---- Reference driver ------------------------------------------------------

def main() -> None:
    configure_logging(logging.INFO)
    acct = Account(account_id="acct_001", balance=100.0)

    # 7 valid charges. The last two cross the low-balance threshold (<10).
    # Running balance:  100 -> 80 -> 65 -> 55 -> 30 -> 20 -> 5* -> 2*
    # Starred lines trigger a WARNING.
    for amt in (20.0, 15.0, 10.0, 25.0, 10.0, 15.0, 3.0):
        charge(acct, amt)

    # 2 insufficient-funds cases. Caller recovers — this is not a bug, so
    # we catch the exception and carry on.
    for amt in (99.0, 500.0):
        try:
            charge(acct, amt)
        except InsufficientFundsError as e:
            log.error("caller caught insufficient funds", extra={"error": str(e)})

    # Invariant violation — LAST, uncaught. Program crashes. By design.
    print("\n=== invariant violation — program will now crash ===", file=sys.stderr)
    charge(acct, -5.0)
    # Unreachable.


if __name__ == "__main__":
    main()


# -----------------------------------------------------------------------------
# REFLECTION (reference answers).
#
#   assert : if you used `raise ValueError` instead, the check would survive
#            `python -O` and you'd signal "bad caller input" rather than
#            "bug." That's a weaker claim about what kind of failure this is.
#            If you used `log.error`, the function would happily charge a
#            negative amount — a silent corruption, the worst outcome.
#
#   raise  : if you used `assert balance >= amount` instead, the check would
#            be stripped under `-O` and the account could go negative in
#            production. If you only logged, the same thing happens without
#            the strip.
#
#   log    : if you used `assert` on the low-balance threshold, the process
#            would crash every time an account ran low — obvious showstopper.
#            If you raised, the caller would have to handle a second
#            exception class for an event that isn't a failure. The log is a
#            side channel precisely because the business action succeeded.
# -----------------------------------------------------------------------------
