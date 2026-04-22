# %% [markdown]
# # Demo 3 — train + serve + monitor a classical-ML classifier
#
# This script does three things:
#
#   1. Trains a real tiny classifier — a nearest-centroid ("mean-vector")
#      model on a 10-class synthetic dataset that behaves like digits. Runs
#      in well under a second. The latest SUCCEEDED run in the fleet board
#      is this one; its holdout accuracy is real.
#   2. Simulates a fleet of ~40 training runs across the last 14 days,
#      seeded with the six failure modes every classical-ML team has
#      shipped at least once: OOM, NaN loss, schema mismatch, data-loader
#      deadlock, hung-and-never-finishes, runaway duration.
#   3. Serves 2000 synthetic prediction calls using the real classifier,
#      with two injected production issues the dashboard is meant to catch:
#         • day 8–10   — gradual input drift (feature intensities creeping up)
#         • day 12–14  — sudden feature-pipeline break (intensities doubled)
#      Labels arrive with a 6-hour delay, so the rolling-accuracy panel has
#      a realistic "hole" on recent predictions.
#
# We use nearest-centroid rather than sklearn LogisticRegression so the
# script has zero pip dependencies beyond numpy. If you already have
# scikit-learn installed and want a stronger baseline, the model shape is
# a drop-in replacement — see `train_real_classifier`.
#
# Writes:
#     train_runs.ndjson    one row per training run
#     train_errors.ndjson  one row per run — parsed error_kind + log tail
#     predictions.ndjson   one row per served prediction
#     data.js              all three wrapped for the dashboard (file:// loads)
#
# Run as a script (`python train_and_monitor.py`) or step through cell-by-cell.

# %% Imports
import hashlib
import json
import math
import random
from datetime import datetime, timedelta

import numpy as np


# %% Time model
# All data spans the 14 days ending at NOW. We freeze NOW so the dashboard is
# reproducible — seed=42 + frozen date means every student sees the same
# incidents at the same coordinates.
NOW = datetime(2026, 4, 27, 18, 0, 0)
WINDOW_DAYS = 14
WINDOW_START = NOW - timedelta(days=WINDOW_DAYS)


def day_offset(days: float) -> datetime:
    """Day offset from the start of the 14-day window."""
    return WINDOW_START + timedelta(days=days)


# %% 1. Real training run
# A nearest-centroid classifier (a.k.a. mean-vector / Rocchio classifier):
# for each class, store the centroid of its training samples; predict by
# argmin distance. One of the oldest classical-ML methods, ~20 lines, no
# dependencies beyond numpy. On our synthetic 64-dim / 10-class digits-
# like data it gets around 0.85 holdout accuracy — realistic "classical
# ML" territory, not the near-1.0 number a big model would produce.

N_FEATURES = 64
N_CLASSES = 10


def _synthetic_digits_dataset(rng: np.random.Generator, n_per_class: int = 180):
    """Synthetic dataset with the *shape* of digits: 64 float features in
    [0, 16], 10 classes, overlapping Gaussian clusters calibrated to yield
    ~0.85 holdout accuracy (realistic classical-ML territory — not the
    near-1.0 number a bigger model would produce, not the near-chance
    number that would look implausible on a dashboard). Fixed seed so every
    student sees the same holdout accuracy."""
    # Prototypes live in a narrower band so classes overlap.
    prototypes = rng.uniform(5.0, 11.0, size=(N_CLASSES, N_FEATURES))
    X, y = [], []
    for cls in range(N_CLASSES):
        noise = rng.normal(0.0, 3.3, size=(n_per_class, N_FEATURES))
        samples = np.clip(prototypes[cls] + noise, 0, 16)
        X.append(samples)
        y.extend([cls] * n_per_class)
    X = np.vstack(X)
    y = np.array(y)
    # Shuffle deterministically.
    idx = rng.permutation(len(y))
    return X[idx], y[idx]


class NearestCentroid:
    """Minimal classical-ML baseline; the API mirrors sklearn's."""
    def fit(self, X, y):
        self.centroids_ = np.stack([X[y == c].mean(axis=0) for c in range(N_CLASSES)])
        return self

    def predict(self, X):
        dists = np.linalg.norm(X[:, None, :] - self.centroids_[None, :, :], axis=2)
        return np.argmin(dists, axis=1)

    def predict_proba(self, X):
        # Softmax over negative distances — lets the predicted_proba column
        # in the predictions log reflect prediction confidence, like a real
        # classifier would. The temperature is picked so healthy-regime
        # predictions land in the 0.5–0.7 range (recognisable "confident
        # prediction") and drop toward chance during drift.
        dists = np.linalg.norm(X[:, None, :] - self.centroids_[None, :, :], axis=2)
        logits = -dists / 1.8
        e = np.exp(logits - logits.max(axis=1, keepdims=True))
        return e / e.sum(axis=1, keepdims=True)


def train_real_classifier():
    """Train a nearest-centroid classifier on the synthetic 10-class dataset.
    Returns (model, X_test, y_test, holdout_acc)."""
    rng = np.random.default_rng(42)
    X, y = _synthetic_digits_dataset(rng)
    n_train = int(0.6 * len(y))
    X_train, y_train = X[:n_train], y[:n_train]
    X_test, y_test = X[n_train:], y[n_train:]

    clf = NearestCentroid().fit(X_train, y_train)
    holdout_acc = float((clf.predict(X_test) == y_test).mean())
    return clf, X_test, y_test, holdout_acc


# %% 2. Simulated training fleet
# Six failure modes the dashboard's tile grid + error-log drawer should
# surface. Each entry names (error_kind, exit_code, log_tail_template).
# The template is a list of log lines — the last one usually pinpoints the
# cause. Students clicking a red tile should see something they recognise.

ERROR_TEMPLATES = {
    "OOM": [
        "[loader] sharded batch 128/128",
        "[trainer] epoch 3 step 412 loss=0.83",
        "[trainer] epoch 3 step 413 loss=0.81",
        "[cuda] out of memory: tried to allocate 3.12 GiB (GPU 0; 15.78 GiB total; 15.11 GiB free)",
        "[trainer] RuntimeError: CUDA out of memory",
        "[trainer] exiting with code 137",
    ],
    "NaN": [
        "[trainer] epoch 1 step 120 loss=0.94",
        "[trainer] epoch 1 step 121 loss=0.88",
        "[trainer] epoch 1 step 122 loss=nan",
        "[trainer] epoch 1 step 123 loss=nan",
        "[trainer] gradient norm exploded; check learning rate (lr=3e-2)",
        "[trainer] aborting at epoch 1; assertion failed: torch.isfinite(loss)",
    ],
    "SchemaMismatch": [
        "[loader] reading features from s3://features/v4/hourly/",
        "[loader] expected columns: ['pixel_0', 'pixel_1', ..., 'pixel_63']",
        "[loader] got columns: ['pixel_0', 'pixel_1', ..., 'pixel_62', 'brightness_mean']",
        "[loader] KeyError: 'pixel_63' not found; upstream feature job changed on 2026-04-25",
        "[trainer] exiting with code 2",
    ],
    "DataLoaderDeadlock": [
        "[loader] spawned 8 worker processes",
        "[loader] worker 3 waiting on semaphore",
        "[loader] worker 3 waiting on semaphore",
        "[loader] worker 3 still waiting (15m)",
        "[trainer] no batches produced in 30m; killing",
    ],
    "Hung": [
        "[loader] batch 48/800",
        "[trainer] epoch 0 step 48 loss=1.42",
        "[loader] waiting on shard 49 (stuck since 10:14:03)",
        "[heartbeat] last activity 23 minutes ago",
        # no further log lines — this run is still technically RUNNING
    ],
    "Runaway": [
        "[trainer] epoch 0 step 1200 loss=0.55",
        "[trainer] epoch 0 step 1300 loss=0.54",
        "[trainer] epoch 0 step 1400 loss=0.54",
        "[trainer] lr scheduler disabled; training continues",
        "[heartbeat] still running (duration 4h 12m, rolling median 45m)",
    ],
    "OK": [
        "[loader] read 1080 train / 720 test examples",
        "[trainer] fitting nearest-centroid on 10 classes × 64 features",
        "[trainer] centroids computed",
        "[eval] holdout accuracy = {ACC}",
        "[trainer] done; exit code 0",
    ],
}


def _job_id(i: int) -> str:
    return f"job_{i:04d}_" + hashlib.md5(f"{i}".encode()).hexdigest()[:6]


def simulate_fleet(real_holdout_acc: float) -> tuple[list[dict], list[dict]]:
    """Return (runs, errors). One error row per run; error_kind None for OK.
    The *last* SUCCEEDED run in the list is the real training run — its
    holdout accuracy is the live number from sklearn, not a simulated one."""

    # Hand-placed failures so the dashboard tells a coherent story:
    #   day 3   — an OOM cluster (bigger batch rolled out too eagerly)
    #   day 6   — a NaN (lr bump that didn't stick)
    #   day 9   — a DataLoaderDeadlock (intermittent)
    #   day 12  — two SchemaMismatch failures (feature pipeline changed; this
    #             is the same event that breaks serving 48h later)
    #   day 13  — one Runaway still going
    #   day 14 (today) — one HUNG run still technically RUNNING
    # All other slots are SUCCEEDED. Durations vary 40s – 300s.

    planned = [
        (0.3,  "OK"),       (0.8,  "OK"),       (1.2,  "OK"),
        (2.1,  "OK"),       (2.6,  "OK"),
        (3.1,  "OOM"),      (3.2,  "OOM"),      (3.4,  "OOM"),
        (3.9,  "OK"),       (4.5,  "OK"),       (5.2,  "OK"),
        (5.7,  "OK"),
        (6.3,  "NaN"),      (6.8,  "OK"),       (7.1,  "OK"),
        (7.6,  "OK"),       (8.2,  "OK"),       (8.7,  "OK"),
        (9.1,  "DataLoaderDeadlock"),
        (9.5,  "OK"),       (10.1, "OK"),       (10.5, "OK"),
        (11.0, "OK"),       (11.4, "OK"),       (11.8, "OK"),
        (12.1, "SchemaMismatch"),  (12.3, "SchemaMismatch"),
        (12.6, "OK"),       (12.9, "OK"),       (13.2, "OK"),
        (13.4, "Runaway"),
        (13.6, "OK"),       (13.8, "OK"),       (14.0 - 0.08, "OK"),
        # The very latest successful run — this is the REAL one.
        (14.0 - 0.04, "OK_REAL"),
        # One HUNG run that never finished, started ~25 min ago.
        (14.0 - 0.02, "Hung"),
    ]

    runs, errors = [], []
    rng = random.Random(42)

    for i, (day_frac, kind) in enumerate(planned):
        started = day_offset(day_frac)
        job_id = _job_id(i)

        if kind == "Hung":
            # still RUNNING, heartbeat stale
            status = "RUNNING"
            duration_s = None
            finished_at = None
            last_hb = started + timedelta(minutes=rng.uniform(6, 15))
            holdout_acc = None
            exit_code = None
        elif kind == "Runaway":
            # still RUNNING; heartbeat is fresh (actively producing log lines)
            # but duration is already many multiples of the rolling median.
            status = "RUNNING"
            last_hb = NOW - timedelta(seconds=rng.uniform(10, 45))
            duration_s = (last_hb - started).total_seconds()
            finished_at = None
            holdout_acc = None
            exit_code = None
        elif kind in ("OK", "OK_REAL"):
            status = "SUCCEEDED"
            duration_s = rng.uniform(40, 110) if kind == "OK" else rng.uniform(0.4, 1.2)
            finished_at = started + timedelta(seconds=duration_s)
            last_hb = finished_at
            holdout_acc = (
                real_holdout_acc if kind == "OK_REAL"
                else rng.uniform(0.94, 0.965)
            )
            exit_code = 0
        else:  # FAILED paths
            status = "FAILED"
            # Failed runs tend to die early.
            duration_s = rng.uniform(15, 90)
            finished_at = started + timedelta(seconds=duration_s)
            last_hb = finished_at
            holdout_acc = None
            exit_code = {"OOM": 137, "NaN": 1, "SchemaMismatch": 2,
                         "DataLoaderDeadlock": 124}[kind]

        runs.append({
            "job_id": job_id,
            "model": "digits_nc_v1" if kind != "OK_REAL" else "digits_nc_v1_live",
            "dataset": "digits-synth-2026-04",
            "started_at": started.isoformat(timespec="seconds"),
            "last_heartbeat_at": last_hb.isoformat(timespec="seconds") if last_hb else None,
            "finished_at": finished_at.isoformat(timespec="seconds") if finished_at else None,
            "status": status,
            "duration_s": round(duration_s, 2) if duration_s is not None else None,
            "holdout_acc": round(holdout_acc, 4) if holdout_acc is not None else None,
            "exit_code": exit_code,
        })

        err_kind = None if kind in ("OK", "OK_REAL") else (
            "Hung" if kind == "Hung"
            else "Runaway" if kind == "Runaway"
            else kind
        )
        tail_tpl = ERROR_TEMPLATES["OK" if kind in ("OK", "OK_REAL") else kind]
        # Fill in the accuracy placeholder for OK runs.
        acc_str = f"{holdout_acc:.4f}" if holdout_acc is not None else "—"
        tail_tpl = [ln.replace("{ACC}", acc_str) for ln in tail_tpl]
        # Stamp each tail line with a faked timestamp for realism.
        base = started
        stamped = []
        for j, line in enumerate(tail_tpl):
            t = (base + timedelta(seconds=5 * j + rng.uniform(0, 2)))
            stamped.append(f"{t.isoformat(timespec='seconds')}  {line}")
        errors.append({
            "job_id": job_id,
            "error_kind": err_kind,
            "tail_log": stamped,
        })

    return runs, errors


# %% 3. Serve predictions with injected drift
def drift_state(t: datetime) -> tuple[float, str]:
    """Return (intensity_multiplier, regime_label) for timestamp t.

    Regimes:
        healthy       days 0–8         multiplier 1.0  (no drift)
        creeping      days 8–10        1.0 → 1.20      (gradual drift)
        healthy_pause days 10–12       1.0             (briefly back to normal)
        broken        days 12–14       2.0             (feature-pipeline bug)
    """
    d = (t - WINDOW_START).total_seconds() / 86400.0
    if 8 <= d < 10:
        p = (d - 8) / 2.0
        return (1.0 + 0.20 * p, "creeping")
    if 10 <= d < 12:
        return (1.0, "healthy_pause")
    if 12 <= d:
        return (2.0, "broken")
    return (1.0, "healthy")


def diurnal_weight(hour_of_day: float) -> float:
    """0.1 … 1.0 across the day; peak near 14:00. Same shape as Demo 2 so
    students recognise the rate curve."""
    return 0.1 + 0.9 * (1 + math.cos(2 * math.pi * (hour_of_day - 14) / 24)) / 2


def serve_predictions(clf, X_test, y_test, n: int = 2000) -> list[dict]:
    rng = np.random.default_rng(42)
    py_rng = random.Random(43)

    # Sample prediction timestamps with a diurnal weight, spread over the
    # 14-day window.
    per_day_minutes = np.arange(0, WINDOW_DAYS * 24 * 60)           # 1-min grid
    weights = np.array([diurnal_weight((m % (24 * 60)) / 60.0) for m in per_day_minutes])
    weights = weights / weights.sum()
    minute_picks = rng.choice(per_day_minutes, size=n, replace=True, p=weights)
    minute_picks.sort()

    preds = []
    for k, m in enumerate(minute_picks):
        ts = WINDOW_START + timedelta(minutes=int(m), seconds=py_rng.uniform(0, 60))
        mult, regime = drift_state(ts)

        # Pick a random test-set row; scale its pixel features by the drift
        # multiplier. Real drift wouldn't be this uniform but the visual
        # story survives the simplification.
        i = py_rng.randrange(len(X_test))
        x = np.clip(X_test[i] * mult, 0, 16).reshape(1, -1)
        true_label = int(y_test[i])

        pred = int(clf.predict(x)[0])
        proba = float(clf.predict_proba(x)[0, pred])
        # Latency: baseline ~8 ms, occasional tail; slight drift in the
        # broken window too (pipeline is unhappy).
        base_lat = py_rng.lognormvariate(math.log(8), 0.25)
        if regime == "broken":
            base_lat *= py_rng.uniform(1.1, 1.3)
        latency_ms = int(max(1, base_lat))

        # Labels arrive with a 6-hour delay; anything within the last 6h
        # of NOW has no label yet.
        label_arrival = ts + timedelta(hours=6)
        label_arrived = label_arrival <= NOW

        preds.append({
            "ts": ts.isoformat(timespec="milliseconds"),
            "request_id": hashlib.md5(f"{ts}-{k}".encode()).hexdigest()[:12],
            "predicted_class": pred,
            "predicted_proba": round(proba, 4),
            "latency_ms": latency_ms,
            "true_label": true_label if label_arrived else None,
            "label_arrival_ts": label_arrival.isoformat(timespec="seconds") if label_arrived else None,
            "regime": regime,            # included for the dashboard's drift bands
        })

    return preds


# %% 4. The Slide-15 assertion, run two ways
def run_quality_assertions(preds: list[dict], holdout_acc: float) -> None:
    """Print the Slide-13 dual-threshold assertion two ways — once against
    the *holdout* accuracy (what the CI gate sees) and once against
    *production* accuracy (what users see). Both have the shape of a
    Python assert; the difference is the value being asserted on is a
    summary over a dataset, not a single request."""
    labelled = [p for p in preds if p["true_label"] is not None]
    correct = sum(1 for p in labelled if p["predicted_class"] == p["true_label"])
    prod_acc = correct / len(labelled) if labelled else 0.0

    print(f"\nholdout accuracy     (from training): {holdout_acc:.4f}")
    print(f"production accuracy  (on {len(labelled)} labelled requests): {prod_acc:.4f}")

    print()
    print("Slide-13 assertion, run against both:")
    for name, val in (("holdout", holdout_acc), ("production", prod_acc)):
        for threshold in (0.85, 0.95):
            ok = val >= threshold
            verdict = "PASS" if ok else "FAIL"
            print(f"  assert {name:<10} acc >= {threshold:.2f}   →   {verdict}")

    if holdout_acc >= 0.95 and prod_acc < 0.95:
        print("\n  ← that is the Slide-13 point: CI gate green, reality red.")


# %% 5. Emit outputs
def emit(runs, errors, preds) -> None:
    for name, rows in (
        ("train_runs.ndjson", runs),
        ("train_errors.ndjson", errors),
        ("predictions.ndjson", preds),
    ):
        with open(name, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")

    # Same rows wrapped for file:// loading by dashboard.html (browsers
    # block fetch() from file://; a <script src> still works).
    with open("data.js", "w") as f:
        f.write("// Auto-generated by train_and_monitor.py — same rows as the ndjson files.\n")
        f.write("window.__DATA__ = ")
        json.dump({"runs": runs, "errors": errors, "preds": preds}, f)
        f.write(";\n")


# %% Driver
def main() -> None:
    random.seed(42)

    print("[1/3] training real classifier (nearest-centroid on synthetic digits)...")
    clf, X_test, y_test, holdout_acc = train_real_classifier()
    print(f"      holdout accuracy = {holdout_acc:.4f}  on {len(y_test)} examples")

    print("[2/3] simulating fleet of 36 training runs across 14 days...")
    runs, errors = simulate_fleet(holdout_acc)
    by_status = {}
    for r in runs:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    print(f"      {len(runs)} runs — " + ", ".join(f"{s}: {n}" for s, n in by_status.items()))

    print("[3/3] serving 2000 predictions with drift + pipeline-break events...")
    preds = serve_predictions(clf, X_test, y_test, n=2000)
    labelled = sum(1 for p in preds if p["true_label"] is not None)
    print(f"      {len(preds)} served, {labelled} with ground truth (the rest are in flight)")

    run_quality_assertions(preds, holdout_acc)

    emit(runs, errors, preds)
    print("\nwrote train_runs.ndjson, train_errors.ndjson, predictions.ndjson, data.js")


# %% Run
if __name__ == "__main__":
    main()
