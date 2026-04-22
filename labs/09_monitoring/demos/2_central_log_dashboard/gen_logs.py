# %% [markdown]
# # Demo 2 — generate a day of synthetic SaaS logs
#
# Writes 15k JSON-per-line rows to `logs.ndjson`, simulating 24 hours of traffic
# against a tiny SaaS service (/login, /feed, /checkout, /profile) with a
# diurnal load curve and a deliberate 15-minute incident on /checkout.
#
# The incident is shaped to match what real outages look like:
#
#     13:50 - 14:00   latency creep on /checkout (no error spike yet)
#     14:00 - 14:15   error rate on /checkout → 20%, latency still elevated
#     14:15 - 14:30   recovery — latency and errors taper back to baseline
#
# That 10-minute "latency creeps before errors spike" phase is the leading
# indicator the LX-2 exercise asks students to find. Two full 5-minute buckets
# (13:50–13:55 and 13:55–14:00) sit clearly above baseline p95 before any user
# sees a 500 — wide enough for a "2 consecutive windows" alert rule to fire at
# 14:00, five minutes before the error-rate panel has anything to say.
#
# Run as a script (`python gen_logs.py`) or step through cell-by-cell.

# %% Imports
import hashlib
import json
import math
import random
from datetime import datetime, timedelta


# %% Service shape
# (method, path, traffic_share, p50_ms, tail_ms, base_error_rate)
ENDPOINTS = [
    ("GET",  "/feed",     0.60,  25, 200, 0.002),
    ("POST", "/login",    0.10,  80, 400, 0.010),
    ("POST", "/checkout", 0.20, 200, 800, 0.005),
    ("GET",  "/profile",  0.10,  30, 150, 0.001),
]


def diurnal_weight(minute_of_day: int) -> float:
    """Weight 0.1 … 1.0 across the day; peak near 14:00, trough near 02:00."""
    peak_min = 14 * 60
    return 0.1 + 0.9 * (1 + math.cos(2 * math.pi * (minute_of_day - peak_min) / 1440)) / 2


def checkout_incident(minute_of_day: int):
    """Return (latency_multiplier, error_rate_override | None) for /checkout."""
    if 830 <= minute_of_day < 840:          # 13:50–14:00 latency creep (10 min)
        p = (minute_of_day - 830) / 10.0
        return (1.5 + 3.5 * p, None)        # 1.5x → 5x; errors still baseline
    if 840 <= minute_of_day < 855:          # 14:00–14:15 full incident
        return (5.0, 0.20)
    if 855 <= minute_of_day < 870:          # 14:15–14:30 recovery
        p = (minute_of_day - 855) / 15.0
        return (5.0 - 4.0 * p, 0.20 * (1 - p))
    return (1.0, None)


# %% Row generator
def generate(total_rows: int = 15_000, day: datetime | None = None, seed: int = 42):
    random.seed(seed)
    day = day or datetime(2026, 4, 15, 0, 0, 0)     # fixed Wed for reproducibility

    weights = [diurnal_weight(m) for m in range(1440)]
    scale = total_rows / sum(weights)
    per_minute = [max(1, round(w * scale)) for w in weights]

    rows = []
    for m, n in enumerate(per_minute):
        lat_mult, err_override = checkout_incident(m)
        for _ in range(n):
            method, path, _, p50, tail, base_err = random.choices(
                ENDPOINTS, weights=[e[2] for e in ENDPOINTS]
            )[0]

            # Only /checkout is affected by the incident.
            effective_lat_mult = lat_mult if path == "/checkout" else 1.0
            effective_err = err_override if (path == "/checkout" and err_override is not None) else base_err

            # Bimodal latency: 97% from the p50 lognormal, 3% from the tail.
            # Tight sigma keeps baseline p95 stable so a leading-indicator
            # threshold can actually distinguish the incident from noise.
            body_ms = p50 if random.random() < 0.97 else tail
            latency = int(random.lognormvariate(math.log(body_ms), 0.2) * effective_lat_mult)
            latency = max(1, latency)

            if random.random() < effective_err:
                status = random.choice([500, 502, 504]) if effective_lat_mult > 1.5 else 500
                if status == 504:
                    latency = max(latency, 5000)   # timeouts look like timeouts
            else:
                status = 200 if method == "GET" else 201

            ts = day + timedelta(minutes=m, seconds=random.random() * 60)
            uid = f"u_{random.randint(1, 800):04d}"
            rows.append({
                "ts": ts.isoformat(timespec="milliseconds"),
                "request_id": hashlib.md5(f"{ts}-{random.random()}".encode()).hexdigest()[:12],
                "method": method,
                "endpoint": path,
                "status_code": status,
                "latency_ms": latency,
                "user_hash": hashlib.sha256(uid.encode()).hexdigest()[:8],
            })

    rows.sort(key=lambda r: r["ts"])
    return rows


# %% Driver
def main() -> None:
    rows = generate()

    # Canonical log file — one JSON per line. This is what a real service would
    # ship to Splunk / Loki / S3. Students can grep it, pipe it, or load it in
    # pandas in two lines.
    with open("logs.ndjson", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    # Same rows, wrapped as a JS array so the dashboard can load it via
    # `<script src="logs.js">` — needed because browsers block file:// fetch().
    with open("logs.js", "w") as f:
        f.write("// Auto-generated by gen_logs.py — same rows as logs.ndjson.\n")
        f.write("window.__LOGS__ = ")
        json.dump(rows, f)
        f.write(";\n")

    # Sanity summary — same shape as the dashboard's aggregations.
    by_ep = {e[1]: [0, 0] for e in ENDPOINTS}              # [total, errors]
    for r in rows:
        by_ep[r["endpoint"]][0] += 1
        if r["status_code"] >= 500:
            by_ep[r["endpoint"]][1] += 1

    print(f"wrote {len(rows)} rows to logs.ndjson")
    for ep, (n, e) in by_ep.items():
        print(f"  {ep:<10}  {n:>6} rows   {e:>4} errors ({e / n * 100:.2f}%)")

    # Incident window summary — what students will see on the dashboard.
    incident = [r for r in rows if r["endpoint"] == "/checkout"
                and "14:0" in r["ts"][11:15]]              # 14:00–14:09
    inc_n, inc_e = len(incident), sum(1 for r in incident if r["status_code"] >= 500)
    print(f"\n/checkout during 14:00–14:09 — {inc_n} rows, {inc_e} errors "
          f"({inc_e / max(inc_n, 1) * 100:.1f}%)")


# %% Run
if __name__ == "__main__":
    main()
