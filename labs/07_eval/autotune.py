"""
Convenience function for running the batched prompt-optimization loop.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from math import ceil
from pathlib import Path
import re
import random
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

import pipeline
from run_loop import run_improvement_loop


load_dotenv()


def _safe_name(value: str) -> str:
    """Convert a candidate identifier into a filesystem-safe name."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned or "candidate"


def _label_distribution(dataset: list[dict[str, Any]], *, label_key: str) -> dict[str, int]:
    """Return label counts for a dataset slice."""
    return dict(sorted(Counter(str(item[label_key]) for item in dataset).items()))


def _quota_allocation(
    n_items: int,
    remaining_sizes: dict[str, int],
    split_order: list[str],
) -> dict[str, int]:
    """Allocate one label bucket across the remaining split capacities."""
    total_remaining = sum(remaining_sizes.values())
    if n_items > total_remaining:
        raise ValueError("Cannot allocate more items than remaining split capacity.")

    ideals = {
        name: (n_items * remaining_sizes[name] / total_remaining) if total_remaining else 0.0
        for name in split_order
    }
    allocations = {
        name: min(remaining_sizes[name], int(ideals[name]))
        for name in split_order
    }

    leftovers = n_items - sum(allocations.values())
    if leftovers:
        ranked_splits = sorted(
            split_order,
            key=lambda name: (
                ideals[name] - allocations[name],
                remaining_sizes[name] - allocations[name],
            ),
            reverse=True,
        )
        for name in ranked_splits[:leftovers]:
            allocations[name] += 1

    return allocations


def split_dataset_by_label(
    dataset: list[dict[str, Any]],
    *,
    tune_size: int,
    selection_size: int,
    test_size: int,
    label_key: str = "ground_truth_intent",
    seed: int = 42,
) -> dict[str, list[dict[str, Any]]]:
    """Split a labeled dataset into deterministic, approximately stratified slices."""
    required = tune_size + selection_size + test_size
    if required > len(dataset):
        raise ValueError(
            f"Requested {required} split items but the dataset only has {len(dataset)} items."
        )

    split_targets = {
        "tune": tune_size,
        "selection": selection_size,
        "test": test_size,
        "unused": len(dataset) - required,
    }
    split_order = [name for name in ["tune", "selection", "test", "unused"] if split_targets[name] > 0]

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in dataset:
        if label_key not in item:
            raise KeyError(f"Item {item.get('id')} is missing required label key '{label_key}'.")
        buckets[str(item[label_key])].append(item)

    rng = random.Random(seed)
    for items in buckets.values():
        rng.shuffle(items)

    remaining_sizes = {name: split_targets[name] for name in split_order}
    splits = {name: [] for name in split_targets}

    # Allocate rarer labels first so they do not get squeezed out by larger buckets.
    for label, items in sorted(buckets.items(), key=lambda pair: (len(pair[1]), pair[0])):
        allocations = _quota_allocation(len(items), remaining_sizes, split_order)
        start = 0
        for split_name in split_order:
            count = allocations[split_name]
            end = start + count
            splits[split_name].extend(items[start:end])
            remaining_sizes[split_name] -= count
            start = end

    if any(remaining_sizes.values()):
        raise RuntimeError(f"Split allocation failed to exhaust capacities: {remaining_sizes}")

    return splits


def _prompt_metrics(
    evaluations: list[dict[str, Any]],
    *,
    eval_mode: str,
) -> dict[str, float | int]:
    """Compute summary metrics for one evaluated prompt."""
    metrics: dict[str, float | int] = {
        "n_items": len(evaluations),
        "avg_rating": pipeline.mean_rating(evaluations),
    }
    if eval_mode == "ground_truth_intent" and evaluations:
        matches = sum(1 for item in evaluations if item.get("rating") == 5)
        metrics["accuracy"] = matches / len(evaluations)
    return metrics


def _save_prompt_evaluation(
    *,
    output_dir: Path,
    prompt_template: str,
    extractions: list[dict[str, Any]],
    evaluations: list[dict[str, Any]],
) -> dict[str, str]:
    """Persist one prompt evaluation bundle."""
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt_path = output_dir / "prompt.txt"
    extractions_path = output_dir / "extractions.json"
    evaluations_path = output_dir / "evaluations.json"

    prompt_path.write_text(prompt_template)
    pipeline.write_json(extractions_path, extractions)
    pipeline.write_json(evaluations_path, evaluations)

    return {
        "prompt_path": str(prompt_path),
        "extractions_path": str(extractions_path),
        "evaluations_path": str(evaluations_path),
    }


def _evaluate_prompt_on_dataset(
    *,
    client: Any,
    dataset: list[dict[str, Any]],
    prompt_template: str,
    prompt_version: str,
    prompt_name: str,
    eval_mode: str,
    extract_model: str,
    eval_model: str,
    extract_batch_size: int,
    judge_batch_size: int,
    output_dir: Path,
) -> dict[str, Any]:
    """Evaluate one prompt on a held-out dataset and save the artifacts."""
    extractions = pipeline.run_extraction_dataset(
        client,
        dataset,
        prompt_template,
        prompt_version,
        extract_model,
        batch_size=extract_batch_size,
    )
    if eval_mode == "judge":
        evaluations = pipeline.run_judge_dataset(
            client,
            extractions,
            eval_model,
            batch_size=judge_batch_size,
        )
    elif eval_mode == "ground_truth_intent":
        evaluations = pipeline.evaluate_ground_truth_intent(extractions)
    else:
        raise ValueError(f"Unsupported eval_mode: {eval_mode}")

    metrics = _prompt_metrics(evaluations, eval_mode=eval_mode)
    paths = _save_prompt_evaluation(
        output_dir=output_dir,
        prompt_template=prompt_template,
        extractions=extractions,
        evaluations=evaluations,
    )
    return {
        "prompt_version": prompt_version,
        "prompt_name": prompt_name,
        "prompt_template": prompt_template,
        **metrics,
        **paths,
    }


def _unique_prompt_candidates(versions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse duplicate prompt texts so the validation step evaluates each prompt once."""
    unique: dict[str, dict[str, Any]] = {}
    for version in versions:
        prompt_path = Path(version["prompt_path"])
        prompt_template = prompt_path.read_text()
        key = prompt_template
        if key in unique:
            continue
        unique[key] = {
            "prompt_key": version["prompt_key"],
            "prompt_name": version["prompt_name"],
            "prompt_version": version["prompt_version"],
            "tune_avg_rating": version["avg_rating"],
            "prompt_template": prompt_template,
            "source_prompt_path": str(prompt_path),
        }
    return list(unique.values())


def estimate_total_llm_calls(
    *,
    eval_mode: str,
    n_items: int,
    extract_batch_size: int,
    judge_batch_size: int,
    max_rounds: int,
    variations_per_round: int,
    include_forced_self_critique: bool,
) -> int:
    """Estimate total LLM calls for the configured loop."""
    extraction_calls = ceil(n_items / extract_batch_size)

    total_variations_per_round = variations_per_round + (1 if include_forced_self_critique else 0)

    if eval_mode == "ground_truth_intent":
        return extraction_calls + max_rounds * (1 + total_variations_per_round * extraction_calls)

    if eval_mode == "judge":
        judge_calls = ceil(n_items / judge_batch_size)
        initial_calls = extraction_calls + judge_calls
        per_round_calls = 1 + total_variations_per_round * (extraction_calls + judge_calls)
        return initial_calls + max_rounds * per_round_calls

    raise ValueError(f"Unsupported eval_mode: {eval_mode}")


def run_batched_prompt_optimization(
    *,
    dataset_path: str | Path,
    prompt_template_path: str | Path,
    best_practices_path: str | Path,
    output_dir: str | Path,
    eval_mode: str = "ground_truth_intent",
    initial_version: str = "v1",
    extract_model: str = "gpt-4.1-mini",
    eval_model: str = "gpt-4.1-mini",
    improve_model: str = "gpt-4.1-mini",
    max_items: int = 60,
    max_rounds: int = 2,
    min_improvement: float = 0.05,
    extract_batch_size: int = 30,
    judge_batch_size: int = 30,
    variations_per_round: int = 2,
    include_forced_self_critique: bool = True,
    max_rationales: int = 100,
    sampling_seed: int = 42,
    llm_call_budget: int = 30,
    client: Any | None = None,
) -> dict[str, Any]:
    """Run the batched optimization loop and save all prompt versions plus the final winner."""
    dataset = pipeline.load_json(dataset_path)
    dataset = dataset[:max_items]
    if not dataset:
        raise ValueError("The selected dataset slice is empty.")

    estimated_calls = estimate_total_llm_calls(
        eval_mode=eval_mode,
        n_items=len(dataset),
        extract_batch_size=extract_batch_size,
        judge_batch_size=judge_batch_size,
        max_rounds=max_rounds,
        variations_per_round=variations_per_round,
        include_forced_self_critique=include_forced_self_critique,
    )
    if estimated_calls > llm_call_budget:
        raise ValueError(
            f"Estimated {estimated_calls} LLM calls, which exceeds the budget of {llm_call_budget}. "
            "Reduce max_items, max_rounds, or variations_per_round, or increase batch sizes."
        )

    prompt_template = Path(prompt_template_path).read_text()
    best_practices_yaml = Path(best_practices_path).read_text()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "dataset_path": str(Path(dataset_path)),
        "prompt_template_path": str(Path(prompt_template_path)),
        "best_practices_path": str(Path(best_practices_path)),
        "output_dir": str(output_dir),
        "eval_mode": eval_mode,
        "initial_version": initial_version,
        "extract_model": extract_model,
        "eval_model": eval_model,
        "improve_model": improve_model,
        "max_items": len(dataset),
        "max_rounds": max_rounds,
        "min_improvement": min_improvement,
        "extract_batch_size": extract_batch_size,
        "judge_batch_size": judge_batch_size,
        "variations_per_round": variations_per_round,
        "include_forced_self_critique": include_forced_self_critique,
        "max_rationales": max_rationales,
        "sampling_seed": sampling_seed,
        "llm_call_budget": llm_call_budget,
        "estimated_llm_calls": estimated_calls,
    }
    pipeline.write_json(output_dir / "run_config.json", config)

    client = client or OpenAI()
    summary = run_improvement_loop(
        client,
        dataset,
        prompt_template,
        initial_prompt_version=initial_version,
        best_practices_yaml=best_practices_yaml,
        output_dir=output_dir,
        eval_mode=eval_mode,
        extract_model=extract_model,
        eval_model=eval_model,
        improve_model=improve_model,
        max_rounds=max_rounds,
        min_improvement=min_improvement,
        extract_batch_size=extract_batch_size,
        judge_batch_size=judge_batch_size,
        variations_per_round=variations_per_round,
        include_forced_self_critique=include_forced_self_critique,
        max_rationales=max_rationales,
        sampling_seed=sampling_seed,
    )
    return summary


def run_split_prompt_optimization(
    *,
    dataset_path: str | Path,
    prompt_template_path: str | Path,
    best_practices_path: str | Path,
    output_dir: str | Path,
    eval_mode: str = "ground_truth_intent",
    initial_version: str = "v1",
    extract_model: str = "gpt-4.1-mini",
    eval_model: str = "gpt-4.1-mini",
    improve_model: str = "gpt-4.1-mini",
    tune_size: int = 200,
    selection_size: int = 100,
    test_size: int = 100,
    split_label_key: str = "ground_truth_intent",
    split_seed: int = 42,
    max_rounds: int = 2,
    min_improvement: float = 0.05,
    extract_batch_size: int = 30,
    judge_batch_size: int = 30,
    variations_per_round: int = 5,
    include_forced_self_critique: bool = True,
    max_rationales: int = 100,
    sampling_seed: int = 42,
    client: Any | None = None,
) -> dict[str, Any]:
    """Tune on one split, pick a winner on a second split, and test it on a third split."""
    dataset = pipeline.load_json(dataset_path)
    if eval_mode == "judge":
        raise ValueError("run_split_prompt_optimization currently supports labeled evaluation only.")

    splits = split_dataset_by_label(
        dataset,
        tune_size=tune_size,
        selection_size=selection_size,
        test_size=test_size,
        label_key=split_label_key,
        seed=split_seed,
    )

    prompt_template = Path(prompt_template_path).read_text()
    best_practices_yaml = Path(best_practices_path).read_text()
    output_dir = Path(output_dir)
    tune_dir = output_dir / "tune"
    selection_dir = output_dir / "selection"
    test_dir = output_dir / "test"
    output_dir.mkdir(parents=True, exist_ok=True)

    split_summary = {
        "dataset_path": str(Path(dataset_path)),
        "split_label_key": split_label_key,
        "split_seed": split_seed,
        "tune_size": len(splits["tune"]),
        "selection_size": len(splits["selection"]),
        "test_size": len(splits["test"]),
        "unused_size": len(splits["unused"]),
        "tune_label_distribution": _label_distribution(splits["tune"], label_key=split_label_key),
        "selection_label_distribution": _label_distribution(splits["selection"], label_key=split_label_key),
        "test_label_distribution": _label_distribution(splits["test"], label_key=split_label_key),
        "unused_label_distribution": _label_distribution(splits["unused"], label_key=split_label_key),
    }
    pipeline.write_json(output_dir / "split_summary.json", split_summary)
    pipeline.write_json(output_dir / "tune_dataset.json", splits["tune"])
    pipeline.write_json(output_dir / "selection_dataset.json", splits["selection"])
    pipeline.write_json(output_dir / "test_dataset.json", splits["test"])
    if splits["unused"]:
        pipeline.write_json(output_dir / "unused_dataset.json", splits["unused"])

    client = client or OpenAI()
    tune_summary = run_improvement_loop(
        client,
        splits["tune"],
        prompt_template,
        initial_prompt_version=initial_version,
        best_practices_yaml=best_practices_yaml,
        output_dir=tune_dir,
        eval_mode=eval_mode,
        extract_model=extract_model,
        eval_model=eval_model,
        improve_model=improve_model,
        max_rounds=max_rounds,
        min_improvement=min_improvement,
        extract_batch_size=extract_batch_size,
        judge_batch_size=judge_batch_size,
        variations_per_round=variations_per_round,
        include_forced_self_critique=include_forced_self_critique,
        max_rationales=max_rationales,
        sampling_seed=sampling_seed,
    )

    prompt_candidates = _unique_prompt_candidates(tune_summary["versions"])
    selection_results: list[dict[str, Any]] = []
    for candidate in prompt_candidates:
        evaluated = _evaluate_prompt_on_dataset(
            client=client,
            dataset=splits["selection"],
            prompt_template=candidate["prompt_template"],
            prompt_version=candidate["prompt_key"],
            prompt_name=candidate["prompt_name"],
            eval_mode=eval_mode,
            extract_model=extract_model,
            eval_model=eval_model,
            extract_batch_size=extract_batch_size,
            judge_batch_size=judge_batch_size,
            output_dir=selection_dir / _safe_name(candidate["prompt_key"]),
        )
        selection_results.append({
            "prompt_key": candidate["prompt_key"],
            "prompt_name": candidate["prompt_name"],
            "prompt_version": candidate["prompt_version"],
            "tune_avg_rating": candidate["tune_avg_rating"],
            "selection_avg_rating": evaluated["avg_rating"],
            "selection_accuracy": evaluated.get("accuracy"),
            "selection_n_items": evaluated["n_items"],
            "prompt_path": evaluated["prompt_path"],
            "extractions_path": evaluated["extractions_path"],
            "evaluations_path": evaluated["evaluations_path"],
            "source_prompt_path": candidate["source_prompt_path"],
        })

    ranked_selection = sorted(
        selection_results,
        key=lambda item: (
            -item["selection_avg_rating"],
            -(item["selection_accuracy"] if item["selection_accuracy"] is not None else -1),
            -item["tune_avg_rating"],
            item["prompt_name"],
        ),
    )
    selection_winner = ranked_selection[0]
    selection_summary = {
        "n_candidates_evaluated": len(ranked_selection),
        "winner_prompt_key": selection_winner["prompt_key"],
        "winner_prompt_name": selection_winner["prompt_name"],
        "winner_prompt_version": selection_winner["prompt_version"],
        "winner_selection_avg_rating": selection_winner["selection_avg_rating"],
        "winner_selection_accuracy": selection_winner["selection_accuracy"],
        "candidates": ranked_selection,
    }
    pipeline.write_json(selection_dir / "selection_summary.json", selection_summary)

    winner_prompt_template = Path(selection_winner["prompt_path"]).read_text()
    test_result = _evaluate_prompt_on_dataset(
        client=client,
        dataset=splits["test"],
        prompt_template=winner_prompt_template,
        prompt_version=selection_winner["prompt_key"],
        prompt_name=selection_winner["prompt_name"],
        eval_mode=eval_mode,
        extract_model=extract_model,
        eval_model=eval_model,
        extract_batch_size=extract_batch_size,
        judge_batch_size=judge_batch_size,
        output_dir=test_dir / "winner",
    )
    test_summary = {
        "winner_prompt_key": selection_winner["prompt_key"],
        "winner_prompt_name": selection_winner["prompt_name"],
        "winner_prompt_version": selection_winner["prompt_version"],
        "test_avg_rating": test_result["avg_rating"],
        "test_accuracy": test_result.get("accuracy"),
        "test_n_items": test_result["n_items"],
        "prompt_path": test_result["prompt_path"],
        "extractions_path": test_result["extractions_path"],
        "evaluations_path": test_result["evaluations_path"],
    }
    pipeline.write_json(test_dir / "test_summary.json", test_summary)

    final_best_prompt_path = output_dir / "best_prompt.txt"
    final_best_prompt_path.write_text(winner_prompt_template)

    final_summary = {
        "split_summary_path": str(output_dir / "split_summary.json"),
        "tune_summary_path": str(tune_dir / "loop_summary.json"),
        "selection_summary_path": str(selection_dir / "selection_summary.json"),
        "test_summary_path": str(test_dir / "test_summary.json"),
        "best_prompt_path": str(final_best_prompt_path),
        "tune_best_prompt_name": tune_summary["best_prompt_name"],
        "tune_best_avg_rating": tune_summary["best_avg_rating"],
        "selection_winner_prompt_name": selection_winner["prompt_name"],
        "selection_winner_prompt_key": selection_winner["prompt_key"],
        "selection_winner_avg_rating": selection_winner["selection_avg_rating"],
        "selection_winner_accuracy": selection_winner["selection_accuracy"],
        "test_avg_rating": test_result["avg_rating"],
        "test_accuracy": test_result.get("accuracy"),
        "n_selection_candidates": len(ranked_selection),
    }
    pipeline.write_json(output_dir / "final_summary.json", final_summary)
    return final_summary
