"""
Poorly-documented tool definitions — same functionality as data_tools.py,
but with vague names, minimal docstrings, and cryptic parameter names.

Used to demonstrate how tool naming/documentation affects LLM tool selection.
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


_df = None


def init(df):
    global _df
    _df = df


def run_check(n=5):
    """Checks the data."""
    df = _df
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
        "sample": df.head(n).to_dict(orient="records"),
    }


def process_data(cols, num=3):
    """Processes the data."""
    df = _df
    X = df[cols].select_dtypes(include="number").copy()
    pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    X_proc = pipe.fit_transform(X)
    model = KMeans(n_clusters=num, n_init=10, random_state=0)
    labels = model.fit_predict(X_proc)
    tmp = df.copy()
    tmp["cluster"] = labels
    profiles = tmp.groupby("cluster")[cols].mean(numeric_only=True).round(2).to_dict(orient="index")
    sizes = tmp["cluster"].value_counts().sort_index().to_dict()
    score = float(silhouette_score(X_proc, labels))
    return {
        "k": num,
        "cluster_sizes": {str(k): v for k, v in sizes.items()},
        "profiles": {str(k): v for k, v in profiles.items()},
        "silhouette_score": round(score, 3),
    }


def get_result(col, cols, row=None):
    """Gets the result."""
    df = _df
    if col not in df.columns:
        return {"error": f"Column '{col}' not found."}
    y = df[col]
    X = pd.get_dummies(df[cols], drop_first=True)
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
            pd.Series(model.named_steps["clf"].feature_importances_, index=X.columns)
            .sort_values(ascending=False)
            .head(5)
            .round(4)
        ),
    }
    if row is not None:
        r = pd.get_dummies(pd.DataFrame([row]), drop_first=True)
        r = r.reindex(columns=X.columns, fill_value=0)
        p = float(model.predict_proba(r)[0, 1])
        result["prediction"] = {"predicted_class": int(p >= 0.5), "probability": round(p, 3)}
    return result


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "run_check",
            "description": "Checks the data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "process_data",
            "description": "Processes the data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cols": {"type": "array", "items": {"type": "string"}},
                    "num": {"type": "integer"},
                },
                "required": ["cols"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_result",
            "description": "Gets the result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "col": {"type": "string"},
                    "cols": {"type": "array", "items": {"type": "string"}},
                    "row": {"type": "object"},
                },
                "required": ["col", "cols"],
            },
        },
    },
]


TOOLS = {
    "run_check": run_check,
    "process_data": process_data,
    "get_result": get_result,
}


