"""
Data analysis tools for the tool-calling lab.

Three tools with natural preconditions and dependencies:
- explore_data: inspect dataset structure (call first when schema is unknown)
- cluster_data: discover natural groups (unsupervised, needs numeric columns)
- classify_data: predict a target label (supervised, needs a target column)

Call init(df) once to set the working DataFrame, then each tool function
accepts only the JSON arguments the LLM sends — no wrappers needed.
"""

import json

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, roc_auc_score, silhouette_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


# ---------------------------------------------------------------------------
# Module state — set once via init(df)
# ---------------------------------------------------------------------------

_df: pd.DataFrame | None = None


def init(df: pd.DataFrame) -> None:
    """Set the working DataFrame for all tool functions."""
    global _df
    _df = df


def _get_df() -> pd.DataFrame:
    if _df is None:
        raise RuntimeError("Call init(df) before using any tool.")
    return _df


# ---------------------------------------------------------------------------
# Dataset generator
# ---------------------------------------------------------------------------

def make_customer_data(n: int = 450, seed: int = 7) -> pd.DataFrame:
    """Generate a synthetic customer dataset with churn labels.

    Columns: age, income, monthly_spend, visits_per_month, support_tickets,
    region, churned.  Has some missing values for realism.
    """
    rng = np.random.default_rng(seed)
    segments = rng.choice(
        ["price_sensitive", "routine", "premium"],
        size=n,
        p=[0.35, 0.40, 0.25],
    )

    rows = []
    for seg in segments:
        if seg == "price_sensitive":
            age = rng.normal(28, 6)
            income = rng.normal(45_000, 9_000)
            monthly_spend = rng.normal(220, 70)
            visits = rng.normal(6, 2)
            tickets = rng.poisson(2.2)
        elif seg == "routine":
            age = rng.normal(41, 8)
            income = rng.normal(68_000, 12_000)
            monthly_spend = rng.normal(480, 110)
            visits = rng.normal(9, 2.5)
            tickets = rng.poisson(1.2)
        else:
            age = rng.normal(36, 7)
            income = rng.normal(110_000, 16_000)
            monthly_spend = rng.normal(950, 180)
            visits = rng.normal(14, 3)
            tickets = rng.poisson(0.6)

        region = rng.choice(["north", "south", "east", "west"])
        logit = (
            -1.6
            + 0.65 * (seg == "price_sensitive")
            + 0.22 * tickets
            - 0.0025 * monthly_spend
            - 0.06 * visits
            + 0.00001 * (50_000 - income)
        )
        p_churn = float(np.clip(1.0 / (1.0 + np.exp(-logit)), 0.02, 0.95))
        churned = int(rng.random() < p_churn)

        rows.append({
            "age": max(18, round(float(age), 1)),
            "income": max(15_000, round(float(income), 0)),
            "monthly_spend": max(20, round(float(monthly_spend), 1)),
            "visits_per_month": max(0, round(float(visits), 1)),
            "support_tickets": int(tickets),
            "region": region,
            "churned": churned,
        })

    df = pd.DataFrame(rows)
    missing_idx = rng.choice(df.index, size=max(5, n // 30), replace=False)
    df.loc[missing_idx[: len(missing_idx) // 2], "income"] = np.nan
    df.loc[missing_idx[len(missing_idx) // 2 :], "monthly_spend"] = np.nan
    return df


# ---------------------------------------------------------------------------
# Tool functions — signatures match the JSON the LLM sends
# ---------------------------------------------------------------------------

def explore_data(sample_rows: int = 5) -> dict:
    """Inspect the dataset schema, missing values, and candidate target columns.

    Call this first when the dataset structure is unknown.
    """
    df = _get_df()
    numeric = df.select_dtypes(include="number").columns.tolist()
    categorical = df.select_dtypes(exclude="number").columns.tolist()

    candidates = []
    for col in df.columns:
        nunique = df[col].dropna().nunique()
        if col.lower() in {"label", "target", "class", "outcome", "churned"}:
            candidates.append(col)
        elif nunique <= 5 and col not in {"region"}:
            candidates.append(col)

    return {
        "n_rows": len(df),
        "columns": df.columns.tolist(),
        "numeric_columns": numeric,
        "categorical_columns": categorical,
        "missing_values": {k: int(v) for k, v in df.isna().sum().items() if v > 0},
        "candidate_targets": candidates,
        "sample": df.head(sample_rows).to_dict(orient="records"),
    }


def cluster_data(feature_columns: list[str], k: int = 3) -> dict:
    """Run KMeans clustering on numeric feature columns to discover natural groups.

    Requires knowing which columns are numeric — call explore_data first if unsure.
    """
    df = _get_df()
    X = df[feature_columns].select_dtypes(include="number").copy()
    pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    X_proc = pipe.fit_transform(X)

    model = KMeans(n_clusters=k, n_init=10, random_state=0)
    labels = model.fit_predict(X_proc)

    tmp = df.copy()
    tmp["cluster"] = labels
    profiles = (
        tmp.groupby("cluster")[feature_columns]
        .mean(numeric_only=True)
        .round(2)
        .to_dict(orient="index")
    )
    sizes = tmp["cluster"].value_counts().sort_index().to_dict()
    score = float(silhouette_score(X_proc, labels))

    return {
        "k": k,
        "cluster_sizes": {str(k): v for k, v in sizes.items()},
        "profiles": {str(k): v for k, v in profiles.items()},
        "silhouette_score": round(score, 3),
    }


def classify_data(
    target: str,
    feature_columns: list[str],
    new_row: dict | None = None,
) -> dict:
    """Train a classifier to predict a target label, optionally scoring a new row.

    Requires a valid target column — call explore_data first to check candidate_targets.
    """
    df = _get_df()
    if target not in df.columns:
        return {"error": f"Target column '{target}' not found in dataset."}

    y = df[target]
    X = pd.get_dummies(df[feature_columns], drop_first=True)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=0, stratify=y,
    )

    model = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("clf", RandomForestClassifier(n_estimators=200, random_state=0)),
    ])
    model.fit(X_train, y_train)

    proba = model.predict_proba(X_test)[:, 1]
    pred = (proba >= 0.5).astype(int)

    result = {
        "metrics": {
            "accuracy": round(float(accuracy_score(y_test, pred)), 3),
            "roc_auc": round(float(roc_auc_score(y_test, proba)), 3),
        },
        "important_features": dict(
            pd.Series(
                model.named_steps["clf"].feature_importances_,
                index=X.columns,
            )
            .sort_values(ascending=False)
            .head(5)
            .round(4)
        ),
    }

    if new_row is not None:
        row = pd.get_dummies(pd.DataFrame([new_row]), drop_first=True)
        row = row.reindex(columns=X.columns, fill_value=0)
        row_proba = float(model.predict_proba(row)[0, 1])
        result["prediction"] = {
            "predicted_class": int(row_proba >= 0.5),
            "probability": round(row_proba, 3),
        }

    return result


# ---------------------------------------------------------------------------
# Tool schemas for the OpenAI Chat Completions API
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "explore_data",
            "description": (
                "Inspect the dataset schema, missing values, basic statistics, "
                "and candidate target columns. Call this first when the dataset "
                "structure is unknown."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sample_rows": {
                        "type": "integer",
                        "description": "Number of sample rows to return (1-10).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cluster_data",
            "description": (
                "Run KMeans clustering on numeric feature columns to discover "
                "natural groups. Requires knowing which columns are numeric "
                "(call explore_data first if unsure)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "feature_columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of numeric column names to cluster on.",
                    },
                    "k": {
                        "type": "integer",
                        "description": "Number of clusters (2-10). Default: 3.",
                    },
                },
                "required": ["feature_columns"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "classify_data",
            "description": (
                "Train a supervised classifier to predict a target label and "
                "optionally score a new data point. Requires a valid target column "
                "with known labels (call explore_data first to verify candidate_targets)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Name of the column to predict.",
                    },
                    "feature_columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Column names to use as input features.",
                    },
                    "new_row": {
                        "type": "object",
                        "description": "Optional: a single row to predict, as {column: value}.",
                    },
                },
                "required": ["target", "feature_columns"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Registry & executor — the registry is just a plain dict
# ---------------------------------------------------------------------------

TOOLS = {
    "explore_data": explore_data,
    "cluster_data": cluster_data,
    "classify_data": classify_data,
}


