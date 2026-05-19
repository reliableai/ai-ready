"""
LX-3 — generate the reference + two production feature batches.

Produces three numpy files the exercise reads:

    X_train.npy           — the training reference distribution (1800 × 64)
                             what the model was fit on; ship this with the
                             model as part of the training artifact
    X_prod_healthy.npy    — a production feature batch from day 5
                             (before the day-12 pipeline break)   (200 × 64)
    X_prod_broken.npy     — a production feature batch from day 13
                             (after the break — every intensity doubled;
                             this is the same event that produced the
                             two SchemaMismatch training failures in
                             Demo 3's fleet board)              (200 × 64)

Seed is fixed (42) so every student sees the same arrays.

Run:  python gen_data.py
"""

import numpy as np


N_FEATURES = 64
N_CLASSES = 10


def _synthetic_digits_dataset(rng, n_per_class: int = 180):
    """Same generator as Demo 3 — classes are overlapping Gaussians on a
    64-dim feature space bounded to [0, 16]. Realistic classical-ML
    territory, not separable."""
    prototypes = rng.uniform(5.0, 11.0, size=(N_CLASSES, N_FEATURES))
    X = []
    for cls in range(N_CLASSES):
        noise = rng.normal(0.0, 3.3, size=(n_per_class, N_FEATURES))
        X.append(np.clip(prototypes[cls] + noise, 0, 16))
    X = np.vstack(X)
    rng.shuffle(X)
    return X


def main() -> None:
    rng = np.random.default_rng(42)

    # Training reference: the full synthetic dataset (1800 rows).
    X_train = _synthetic_digits_dataset(rng, n_per_class=180)
    np.save("X_train.npy", X_train)

    # Healthy production slice: 200 fresh samples from the same distribution.
    # (Real feature stores would keep a rolling window; here the shape is
    # what matters.)
    X_prod_healthy = _synthetic_digits_dataset(rng, n_per_class=20)
    np.save("X_prod_healthy.npy", X_prod_healthy)

    # Broken production slice: 200 samples where intensities are doubled —
    # the day-12 feature-pipeline event. The shape is the same, the mean
    # is very different.
    X_prod_broken = _synthetic_digits_dataset(rng, n_per_class=20) * 2.0
    # Clip back to [0, 16] as the real pipeline would; saturates at the top
    # end, which is in fact how this kind of bug presents — a cluster near
    # the max value that didn't exist in training.
    X_prod_broken = np.clip(X_prod_broken, 0, 16)
    np.save("X_prod_broken.npy", X_prod_broken)

    # Sanity summary.
    print(f"wrote X_train.npy           {X_train.shape}   "
          f"mean={X_train.mean():.2f}  std={X_train.std():.2f}")
    print(f"wrote X_prod_healthy.npy    {X_prod_healthy.shape}   "
          f"mean={X_prod_healthy.mean():.2f}  std={X_prod_healthy.std():.2f}")
    print(f"wrote X_prod_broken.npy     {X_prod_broken.shape}   "
          f"mean={X_prod_broken.mean():.2f}  std={X_prod_broken.std():.2f}")
    print()
    print("The healthy batch should pass your CI gate.")
    print("The broken batch should fail it.")


if __name__ == "__main__":
    main()
