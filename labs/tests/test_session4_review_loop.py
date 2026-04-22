"""
Deterministic tests for the review/judge improvement loop.

These tests avoid live API calls by using fake clients and monkeypatched helpers.
"""

import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace


def _load_lab03_module(filename: str, module_name: str):
    root = Path(__file__).resolve().parents[1] / "05_eval_fundamentals"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    spec = spec_from_file_location(module_name, root / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {filename}")

    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeCompletions:
    def __init__(self, resolver):
        self._resolver = resolver

    def create(self, **kwargs):
        content = self._resolver(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=content)
                )
            ]
        )


class _FakeChat:
    def __init__(self, resolver):
        self.completions = _FakeCompletions(resolver)


class _FakeClient:
    def __init__(self, resolver):
        self.chat = _FakeChat(resolver)


def test_run_extraction_dataset_renders_prompt_and_preserves_fields():
    pipeline = _load_lab03_module("pipeline.py", "lab03_pipeline_extract")

    client = _FakeClient(lambda _: json.dumps({
        "items": [
            {"id": "bitext_1", "output": {"intent": "cancel order", "symptoms": []}},
        ]
    }))
    dataset = [
        {
            "id": "bitext_1",
            "text": "please cancel order 123",
            "ground_truth_intent": "cancel_order",
        }
    ]

    results = pipeline.run_extraction_dataset(
        client,
        dataset,
        "Request:\n{{request}}",
        "v1",
        "gpt-4.1-mini",
    )

    assert len(results) == 1
    assert results[0]["prompt_version"] == "v1"
    assert results[0]["rendered_prompt"] == "Request:\nplease cancel order 123"
    assert results[0]["ground_truth_intent"] == "cancel_order"
    assert json.loads(results[0]["llm_response"])["intent"] == "cancel order"


def test_run_extraction_dataset_batches_multiple_items_into_fewer_calls():
    pipeline = _load_lab03_module("pipeline.py", "lab03_pipeline_batching")

    call_count = {"n": 0}

    def resolver(kwargs):
        call_count["n"] += 1
        user_message = kwargs["messages"][1]["content"]
        if '"id": "1"' in user_message and '"id": "2"' in user_message:
            return json.dumps({
                "items": [
                    {"id": "1", "output": {"intent": "cancel order", "symptoms": []}},
                    {"id": "2", "output": {"intent": "change order", "symptoms": []}},
                ]
            })
        return json.dumps({
            "items": [
                {"id": "3", "output": {"intent": "track order", "symptoms": []}},
            ]
        })

    client = _FakeClient(resolver)
    dataset = [
        {"id": "1", "text": "cancel it", "ground_truth_intent": "cancel_order"},
        {"id": "2", "text": "change it", "ground_truth_intent": "change_order"},
        {"id": "3", "text": "where is it", "ground_truth_intent": "track_order"},
    ]

    results = pipeline.run_extraction_dataset(
        client,
        dataset,
        "Request:\n{{request}}",
        "v1",
        "gpt-4.1-mini",
        batch_size=2,
    )

    assert call_count["n"] == 2
    assert [r["id"] for r in results] == ["1", "2", "3"]
    assert json.loads(results[2]["llm_response"])["intent"] == "track order"


def test_evaluate_ground_truth_intent_normalizes_spacing_and_underscores():
    pipeline = _load_lab03_module("pipeline.py", "lab03_pipeline_eval")

    evaluations = pipeline.evaluate_ground_truth_intent([
        {
            "id": "bitext_1",
            "prompt_version": "v1",
            "ground_truth_intent": "cancel_order",
            "llm_response": '{"intent":"cancel order","symptoms":[]}',
        }
    ])

    assert len(evaluations) == 1
    assert evaluations[0]["rating"] == 5
    assert evaluations[0]["predicted_intent"] == "cancel order"


def test_run_improvement_loop_accepts_better_prompt_then_stops(tmp_path, monkeypatch):
    run_loop = _load_lab03_module("run_loop.py", "lab03_run_loop")

    score_by_version = {
        "v1": 3.0,
        "v2a": 4.0,
        "v2b": 2.0,
        "v2c": 5.0,
        "v3a": 4.0,
        "v3b": 3.0,
    }
    evaluated_versions = []

    def fake_run_extraction_dataset(
        client,
        dataset,
        prompt_template,
        prompt_version,
        model,
        *,
        max_completion_tokens=1024,
        temperature=0,
        batch_size=30,
    ):
        return [{
            "id": dataset[0]["id"],
            "prompt_version": prompt_version,
            "ground_truth_intent": dataset[0]["ground_truth_intent"],
            "rendered_prompt": prompt_template.replace("{{request}}", dataset[0]["text"]),
            "llm_response": '{"intent":"request refund","symptoms":[]}',
        }]

    def fake_evaluate_ground_truth_intent(extractions):
        version = extractions[0]["prompt_version"]
        evaluated_versions.append(version)
        score = score_by_version[version]
        return [{
            "id": extractions[0]["id"],
            "prompt_version": version,
            "rating": score,
            "motivation": f"score={score}",
        }]

    def fake_improve_prompt_variations(
        client,
        current_prompt,
        best_practices_yaml,
        judged_results,
        prompt_version,
        model,
        *,
        max_rationales=100,
        sampling_seed=42,
    ):
        if prompt_version == "v1":
            variations = [
                {
                    "variation_id": "v2a",
                    "changes": ["tighten intent wording"],
                    "rationale": "Improves specificity.",
                    "prompt_template": "prompt v2a {{request}}",
                },
                {
                    "variation_id": "v2b",
                    "changes": ["negative instructions"],
                    "rationale": "Reduces hallucinations.",
                    "prompt_template": "prompt v2b {{request}}",
                },
                {
                    "variation_id": "v2c",
                    "changes": ["few-shot examples"],
                    "rationale": "Would be best, but should not be evaluated because it is ranked third.",
                    "prompt_template": "prompt v2c {{request}}",
                },
            ]
        elif prompt_version == "v2a":
            variations = [
                {
                    "variation_id": "v3a",
                    "changes": ["few-shot example"],
                    "rationale": "Might help, but does not improve score.",
                    "prompt_template": "prompt v3a {{request}}",
                },
                {
                    "variation_id": "v3b",
                    "changes": ["quote grounding"],
                    "rationale": "Also worse than current.",
                    "prompt_template": "prompt v3b {{request}}",
                },
            ]
        else:
            raise AssertionError(f"Unexpected prompt version {prompt_version}")

        return {
            "source_prompt_version": prompt_version,
            "avg_rating": score_by_version[prompt_version],
            "n_items": 1,
            "n_rationales_sampled": 1,
            "analysis": "Stub analysis",
            "variations": variations,
        }

    monkeypatch.setattr(run_loop.pipeline, "run_extraction_dataset", fake_run_extraction_dataset)
    monkeypatch.setattr(run_loop.pipeline, "evaluate_ground_truth_intent", fake_evaluate_ground_truth_intent)
    monkeypatch.setattr(run_loop.pipeline, "improve_prompt_variations", fake_improve_prompt_variations)

    dataset = [{"id": "1", "text": "please refund me", "ground_truth_intent": "request_refund"}]
    summary = run_loop.run_improvement_loop(
        client=object(),
        dataset=dataset,
        initial_prompt_template="prompt v1 {{request}}",
        initial_prompt_version="v1",
        best_practices_yaml="catalog: []",
        output_dir=tmp_path,
        eval_mode="ground_truth_intent",
        extract_model="gpt-4.1-mini",
        eval_model="gpt-4.1-mini",
        improve_model="gpt-4.1-mini",
        max_rounds=3,
        min_improvement=0.05,
        variations_per_round=2,
        include_forced_self_critique=False,
    )

    assert summary["best_prompt_version"] == "v2a"
    assert abs(summary["best_avg_rating"] - 4.0) < 1e-9
    assert len(summary["rounds"]) == 2
    assert summary["rounds"][0]["accepted"] is True
    assert summary["rounds"][1]["accepted"] is False
    assert "v2c" not in evaluated_versions
    assert summary["rounds"][0]["variations_proposed"] == 3
    assert summary["rounds"][0]["variations_evaluated"] == 2
    assert any(version["prompt_version"] == "v2a" and version["is_best"] for version in summary["versions"])
    assert (tmp_path / "best_prompt.txt").read_text() == "prompt v2a {{request}}"
    assert (tmp_path / "prompt_versions.json").exists()


def test_run_batched_prompt_optimization_enforces_call_budget(tmp_path):
    autotune = _load_lab03_module("autotune.py", "lab03_autotune")

    dataset_path = tmp_path / "dataset.json"
    prompt_path = tmp_path / "prompt.txt"
    best_path = tmp_path / "best.yaml"

    dataset_path.write_text(json.dumps([
        {"id": str(i), "text": f"request {i}", "ground_truth_intent": "cancel_order"}
        for i in range(61)
    ]))
    prompt_path.write_text("Prompt {{request}}")
    best_path.write_text("catalog: []")

    try:
        autotune.run_batched_prompt_optimization(
            dataset_path=dataset_path,
            prompt_template_path=prompt_path,
            best_practices_path=best_path,
            output_dir=tmp_path / "out",
            max_items=61,
            extract_batch_size=30,
            max_rounds=2,
            variations_per_round=2,
            llm_call_budget=10,
            client=object(),
        )
    except ValueError as exc:
        assert "exceeds the budget" in str(exc)
    else:
        raise AssertionError("Expected the call budget check to fail")


def test_split_dataset_by_label_is_deterministic_and_exact():
    autotune = _load_lab03_module("autotune.py", "lab03_autotune_split")

    dataset = [
        {"id": f"a{i}", "text": f"a{i}", "ground_truth_intent": "a"}
        for i in range(4)
    ] + [
        {"id": f"b{i}", "text": f"b{i}", "ground_truth_intent": "b"}
        for i in range(4)
    ] + [
        {"id": f"c{i}", "text": f"c{i}", "ground_truth_intent": "c"}
        for i in range(4)
    ]

    first = autotune.split_dataset_by_label(
        dataset,
        tune_size=6,
        selection_size=3,
        test_size=2,
        seed=7,
    )
    second = autotune.split_dataset_by_label(
        dataset,
        tune_size=6,
        selection_size=3,
        test_size=2,
        seed=7,
    )

    assert len(first["tune"]) == 6
    assert len(first["selection"]) == 3
    assert len(first["test"]) == 2
    assert len(first["unused"]) == 1
    assert sum(len(items) for items in first.values()) == len(dataset)
    assert len({item["id"] for split in first.values() for item in split}) == len(dataset)
    assert {
        name: [item["id"] for item in split]
        for name, split in first.items()
    } == {
        name: [item["id"] for item in split]
        for name, split in second.items()
    }


def test_run_split_prompt_optimization_uses_selection_split_to_pick_winner(tmp_path, monkeypatch):
    autotune = _load_lab03_module("autotune.py", "lab03_autotune_split_workflow")

    dataset_path = tmp_path / "dataset.json"
    prompt_path = tmp_path / "prompt.txt"
    best_path = tmp_path / "best.yaml"

    dataset_path.write_text(json.dumps([
        {"id": f"id_{i}", "text": f"request {i}", "ground_truth_intent": "cancel_order" if i % 2 == 0 else "track_order"}
        for i in range(12)
    ]))
    prompt_path.write_text("Prompt {{request}}")
    best_path.write_text("catalog: []")

    def fake_run_improvement_loop(
        client,
        dataset,
        initial_prompt_template,
        *,
        initial_prompt_version,
        best_practices_yaml,
        output_dir,
        eval_mode,
        extract_model,
        eval_model,
        improve_model,
        max_rounds,
        min_improvement,
        extract_batch_size=30,
        judge_batch_size=30,
        variations_per_round=2,
        include_forced_self_critique=True,
        max_rationales=100,
        sampling_seed=42,
    ):
        baseline_dir = output_dir / "baseline"
        tune_winner_dir = output_dir / "tune_winner"
        selection_winner_dir = output_dir / "selection_winner"
        baseline_dir.mkdir(parents=True, exist_ok=True)
        tune_winner_dir.mkdir(parents=True, exist_ok=True)
        selection_winner_dir.mkdir(parents=True, exist_ok=True)

        (baseline_dir / "prompt.txt").write_text("baseline {{request}}")
        (tune_winner_dir / "prompt.txt").write_text("tune winner {{request}}")
        (selection_winner_dir / "prompt.txt").write_text("selection winner {{request}}")

        loop_summary = {
            "best_prompt_name": "R01 v2 Tune Winner",
            "best_avg_rating": 4.0,
            "versions": [
                {
                    "prompt_key": "baseline",
                    "prompt_name": "R00 v1 Baseline",
                    "prompt_version": "v1",
                    "avg_rating": 3.0,
                    "prompt_path": str(baseline_dir / "prompt.txt"),
                },
                {
                    "prompt_key": "tune_winner",
                    "prompt_name": "R01 v2 Tune Winner",
                    "prompt_version": "v2",
                    "avg_rating": 4.0,
                    "prompt_path": str(tune_winner_dir / "prompt.txt"),
                },
                {
                    "prompt_key": "selection_winner",
                    "prompt_name": "R01 v3 Selection Winner",
                    "prompt_version": "v3",
                    "avg_rating": 3.5,
                    "prompt_path": str(selection_winner_dir / "prompt.txt"),
                },
            ],
        }
        (output_dir / "loop_summary.json").write_text(json.dumps(loop_summary))
        return loop_summary

    def fake_evaluate_prompt_on_dataset(
        *,
        client,
        dataset,
        prompt_template,
        prompt_version,
        prompt_name,
        eval_mode,
        extract_model,
        eval_model,
        extract_batch_size,
        judge_batch_size,
        output_dir,
    ):
        output_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = output_dir / "prompt.txt"
        extractions_path = output_dir / "extractions.json"
        evaluations_path = output_dir / "evaluations.json"
        prompt_path.write_text(prompt_template)
        extractions_path.write_text("[]")
        evaluations_path.write_text("[]")

        if "selection" in str(output_dir):
            score_map = {
                "R00 v1 Baseline": (3.0, 0.50),
                "R01 v2 Tune Winner": (4.0, 0.75),
                "R01 v3 Selection Winner": (5.0, 1.00),
            }
        else:
            score_map = {
                "R01 v3 Selection Winner": (4.5, 0.90),
            }

        avg_rating, accuracy = score_map[prompt_name]
        return {
            "prompt_version": prompt_version,
            "prompt_name": prompt_name,
            "prompt_template": prompt_template,
            "avg_rating": avg_rating,
            "accuracy": accuracy,
            "n_items": len(dataset),
            "prompt_path": str(prompt_path),
            "extractions_path": str(extractions_path),
            "evaluations_path": str(evaluations_path),
        }

    monkeypatch.setattr(autotune, "run_improvement_loop", fake_run_improvement_loop)
    monkeypatch.setattr(autotune, "_evaluate_prompt_on_dataset", fake_evaluate_prompt_on_dataset)

    summary = autotune.run_split_prompt_optimization(
        dataset_path=dataset_path,
        prompt_template_path=prompt_path,
        best_practices_path=best_path,
        output_dir=tmp_path / "out",
        tune_size=6,
        selection_size=3,
        test_size=2,
        client=object(),
    )

    assert summary["tune_best_prompt_name"] == "R01 v2 Tune Winner"
    assert summary["selection_winner_prompt_name"] == "R01 v3 Selection Winner"
    assert summary["selection_winner_accuracy"] == 1.0
    assert summary["test_accuracy"] == 0.9
    assert (tmp_path / "out" / "best_prompt.txt").read_text() == "selection winner {{request}}"
    assert (tmp_path / "out" / "selection" / "selection_summary.json").exists()
    assert (tmp_path / "out" / "test" / "test_summary.json").exists()
