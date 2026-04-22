from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, roc_auc_score, silhouette_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def make_customer_data(n: int = 450, seed: int = 7) -> pd.DataFrame:
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
            visits_per_month = rng.normal(6, 2)
            support_tickets = rng.poisson(2.2)
        elif seg == "routine":
            age = rng.normal(41, 8)
            income = rng.normal(68_000, 12_000)
            monthly_spend = rng.normal(480, 110)
            visits_per_month = rng.normal(9, 2.5)
            support_tickets = rng.poisson(1.2)
        else:
            age = rng.normal(36, 7)
            income = rng.normal(110_000, 16_000)
            monthly_spend = rng.normal(950, 180)
            visits_per_month = rng.normal(14, 3)
            support_tickets = rng.poisson(0.6)

        region = rng.choice(["north", "south", "east", "west"])

        logit = (
            -1.6
            + 0.65 * (seg == "price_sensitive")
            + 0.22 * support_tickets
            - 0.0025 * monthly_spend
            - 0.06 * visits_per_month
            + 0.00001 * (50_000 - income)
        )
        p_churn = 1.0 / (1.0 + np.exp(-logit))
        p_churn = float(np.clip(p_churn, 0.02, 0.95))
        churned = int(rng.random() < p_churn)

        rows.append(
            {
                "age": max(18, round(age, 1)),
                "income": max(15_000, round(income, 0)),
                "monthly_spend": max(20, round(monthly_spend, 1)),
                "visits_per_month": max(0, round(visits_per_month, 1)),
                "support_tickets": int(support_tickets),
                "region": region,
                "latent_segment": seg,
                "churned": churned,
            }
        )

    df = pd.DataFrame(rows)

    missing_idx = rng.choice(df.index, size=max(5, n // 30), replace=False)
    df.loc[missing_idx[: len(missing_idx)//2], "income"] = np.nan
    df.loc[missing_idx[len(missing_idx)//2 :], "monthly_spend"] = np.nan
    return df


def explore_data(df: pd.DataFrame, sample_rows: int = 5) -> dict[str, Any]:
    numeric_columns = df.select_dtypes(include="number").columns.tolist()
    categorical_columns = df.select_dtypes(exclude="number").columns.tolist()

    candidate_targets = []
    for col in df.columns:
        unique_non_null = df[col].dropna().nunique()
        lower = col.lower()
        if lower in {"label", "target", "class", "outcome", "churned"}:
            candidate_targets.append(col)
        elif unique_non_null <= 5 and col not in {"region", "latent_segment"}:
            candidate_targets.append(col)

    return {
        "n_rows": int(len(df)),
        "columns": df.columns.tolist(),
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "missing_values": df.isna().sum().to_dict(),
        "candidate_targets": candidate_targets,
        "sample": df.head(sample_rows).to_dict(orient="records"),
    }


def cluster_data(df: pd.DataFrame, feature_columns: list[str], k: int = 3) -> dict[str, Any]:
    X = df[feature_columns].copy()
    X = X.select_dtypes(include="number")

    prep = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    X_proc = prep.fit_transform(X)

    model = KMeans(n_clusters=k, n_init=10, random_state=0)
    cluster_labels = model.fit_predict(X_proc)

    with_clusters = df.copy()
    with_clusters["cluster"] = cluster_labels

    profiles = (
        with_clusters.groupby("cluster")[feature_columns]
        .mean(numeric_only=True)
        .round(2)
        .to_dict(orient="index")
    )

    sizes = with_clusters["cluster"].value_counts().sort_index().to_dict()
    score = float(silhouette_score(X_proc, cluster_labels))

    return {
        "k": k,
        "cluster_sizes": sizes,
        "profiles": profiles,
        "silhouette_score": round(score, 3),
    }


def classify_data(
    df: pd.DataFrame,
    target: str,
    feature_columns: list[str],
    new_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if target not in df.columns:
        raise ValueError(f"Target column '{target}' not found.")

    y = df[target]
    X = pd.get_dummies(df[feature_columns], drop_first=True)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=0, stratify=y
    )

    model = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("clf", RandomForestClassifier(n_estimators=200, random_state=0)),
        ]
    )
    model.fit(X_train, y_train)

    proba = model.predict_proba(X_test)[:, 1]
    pred = (proba >= 0.5).astype(int)

    result: dict[str, Any] = {
        "metrics": {
            "accuracy": round(float(accuracy_score(y_test, pred)), 3),
            "roc_auc": round(float(roc_auc_score(y_test, proba)), 3),
        }
    }

    clf = model.named_steps["clf"]
    importances = pd.Series(clf.feature_importances_, index=X.columns).sort_values(ascending=False)
    result["important_features"] = importances.head(5).round(4).to_dict()

    if new_row is not None:
        row = pd.DataFrame([new_row])
        row = pd.get_dummies(row, drop_first=True)
        row = row.reindex(columns=X.columns, fill_value=0)
        row_proba = float(model.predict_proba(row)[0, 1])
        row_pred = int(row_proba >= 0.5)
        result["prediction"] = {
            "predicted_class": row_pred,
            "probability_of_positive_class": round(row_proba, 3),
        }

    return result


@dataclass
class Decision:
    type: str
    name: str | None = None
    args: dict[str, Any] | None = None
    answer: str | None = None


def rule_based_controller(user_goal: str, state: dict[str, Any]) -> Decision:
    goal = user_goal.lower()

    wants_segmentation = any(word in goal for word in ["segment", "cluster", "group"])
    wants_classification = any(word in goal for word in ["churn", "predict", "classification", "classify"])
    wants_exploration_only = "what kind of data" in goal or "is churn prediction possible" in goal

    if "exploration" not in state:
        return Decision(type="tool", name="explore_data", args={"sample_rows": 3})

    exploration = state["exploration"]
    has_label = "churned" in exploration["candidate_targets"]

    if wants_exploration_only and not wants_segmentation and not wants_classification:
        answer = (
            f"The dataset has {exploration['n_rows']} rows and columns {exploration['columns']}. "
            f"Candidate target columns: {exploration['candidate_targets']}. "
            f"{'Churn prediction looks possible.' if has_label else 'Churn prediction does not look possible with the current schema.'}"
        )
        return Decision(type="final", answer=answer)

    if wants_segmentation and "clusters" not in state:
        return Decision(
            type="tool",
            name="cluster_data",
            args={
                "feature_columns": [
                    "age",
                    "income",
                    "monthly_spend",
                    "visits_per_month",
                    "support_tickets",
                ],
                "k": 3,
            },
        )

    if wants_classification and not has_label:
        return Decision(
            type="final",
            answer="A supervised churn classifier cannot be used because no suitable target label was found.",
        )

    if wants_classification and "classification" not in state:
        return Decision(
            type="tool",
            name="classify_data",
            args={
                "target": "churned",
                "feature_columns": [
                    "age",
                    "income",
                    "monthly_spend",
                    "visits_per_month",
                    "support_tickets",
                    "region",
                ],
                "new_row": {
                    "age": 29,
                    "income": 42000,
                    "monthly_spend": 180,
                    "visits_per_month": 4,
                    "support_tickets": 3,
                    "region": "south",
                },
            },
        )

    parts = []

    if wants_segmentation and "clusters" in state:
        parts.append(
            "Segmentation summary: "
            + json.dumps(state["clusters"], indent=2)
        )

    if wants_classification and "classification" in state:
        parts.append(
            "Classification summary: "
            + json.dumps(state["classification"], indent=2)
        )

    if not parts:
        parts.append("The request appears fully answered after exploration.")

    return Decision(type="final", answer="\n\n".join(parts))


def main() -> None:
    df = make_customer_data()

    tools: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
        "explore_data": lambda args: explore_data(df, **args),
        "cluster_data": lambda args: cluster_data(df, **args),
        "classify_data": lambda args: classify_data(df, **args),
    }

    user_goal = (
        "Analyze this customer dataset. Are there natural segments, "
        "and is this new customer likely to churn?"
    )

    state: dict[str, Any] = {}

    print("USER GOAL")
    print(user_goal)
    print("=" * 80)

    for step in range(1, 8):
        decision = rule_based_controller(user_goal, state)

        print(f"\nSTEP {step}")
        print("DECISION:", decision)

        if decision.type == "final":
            print("\nFINAL ANSWER")
            print(decision.answer)
            break

        assert decision.name is not None
        assert decision.args is not None

        result = tools[decision.name](decision.args)
        print(f"TOOL RESULT ({decision.name})")
        print(json.dumps(result, indent=2))

        if decision.name == "explore_data":
            state["exploration"] = result
        elif decision.name == "cluster_data":
            state["clusters"] = result
        elif decision.name == "classify_data":
            state["classification"] = result


if __name__ == "__main__":
    main()
