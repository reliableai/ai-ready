"""
Run an iterative prompt-improvement loop.

This loop supports two evaluation modes:
- ground_truth_intent: use dataset labels such as Bitext's ground_truth_intent
- judge: use the LLM judge prompt for unlabeled extraction tasks
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

import pipeline


load_dotenv()


def _safe_name(value: str) -> str:
    """Convert a model-generated identifier into a filesystem-safe name."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned or "candidate"


def _slug(value: str) -> str:
    """Create a readable slug for prompt names."""
    return _safe_name(value).strip("_").lower() or "candidate"


def _default_prompt_name(prompt_version: str, approach_name: str | None = None) -> str:
    """Create a human-readable name if the model does not provide one."""
    if approach_name:
        return f"{prompt_version} {approach_name}"
    if prompt_version == "v1":
        return "v1 Baseline"
    return prompt_version


def _build_self_critique_prompt(prompt_template: str) -> str:
    """Append an explicit self-critique step while keeping final output JSON-only."""
    return (
        prompt_template.rstrip()
        + "\n\n"
        + "Before producing the final answer, use this process:\n"
        + "1. Draft the JSON answer.\n"
        + "2. Critique the draft for missing facts, hallucinations, merged symptoms, vague intent labels, and schema violations.\n"
        + "3. Revise the answer.\n"
        + "Return only the final revised JSON.\n"
    )


def _round_prompt_name(round_index: int, prompt_version: str, approach_name: str | None = None) -> str:
    """Create a stable display name that includes iteration and approach."""
    base_name = _default_prompt_name(prompt_version, approach_name)
    return f"R{round_index:02d} {base_name}"


def _build_versions_ledger(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a ledger of every evaluated prompt instance."""
    ledger: list[dict[str, Any]] = []

    for round_summary in summary["rounds"]:
        ledger.append({
            "prompt_key": round_summary["current_prompt_key"],
            "prompt_name": round_summary["current_prompt_name"],
            "prompt_version": round_summary["current_prompt_version"],
            "avg_rating": round_summary["current_avg_rating"],
            "prompt_path": round_summary["current_prompt_path"],
            "extractions_path": round_summary["current_extractions_path"],
            "evaluations_path": round_summary["current_evaluations_path"],
            "source_round": round_summary["round_index"],
            "kind": "current",
            "is_best": round_summary["current_prompt_key"] == summary["best_prompt_key"],
        })

        for variation in round_summary["variations"]:
            ledger.append({
                "prompt_key": variation["prompt_key"],
                "prompt_name": variation["prompt_name"],
                "prompt_version": variation["variation_id"],
                "avg_rating": variation["avg_rating"],
                "prompt_path": variation["prompt_path"],
                "extractions_path": variation["extractions_path"],
                "evaluations_path": variation["evaluations_path"],
                "source_round": round_summary["round_index"],
                "kind": "variation",
                "is_best": variation["prompt_key"] == summary["best_prompt_key"],
            })

    return ledger


def _save_candidate_artifacts(
    round_dir: Path,
    candidate_name: str,
    prompt_template: str,
    extractions: list[dict[str, Any]],
    evaluations: list[dict[str, Any]],
) -> dict[str, str]:
    """Write prompt, extraction results, and evaluation results for one candidate."""
    candidate_dir = round_dir / _safe_name(candidate_name)
    candidate_dir.mkdir(parents=True, exist_ok=True)

    prompt_path = candidate_dir / "prompt.txt"
    extractions_path = candidate_dir / "extractions.json"
    evaluations_path = candidate_dir / "evaluations.json"

    prompt_path.write_text(prompt_template)
    pipeline.write_json(extractions_path, extractions)
    pipeline.write_json(evaluations_path, evaluations)

    return {
        "prompt_key": candidate_dir.name,
        "prompt_path": str(prompt_path),
        "extractions_path": str(extractions_path),
        "evaluations_path": str(evaluations_path),
    }


def _evaluate_prompt_candidate(
    client: Any,
    dataset: list[dict[str, Any]],
    prompt_template: str,
    prompt_version: str,
    prompt_name: str,
    *,
    eval_mode: str,
    extract_model: str,
    eval_model: str,
    extract_batch_size: int,
    judge_batch_size: int,
) -> dict[str, Any]:
    """Run extraction + evaluation for one prompt candidate."""
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

    return {
        "prompt_version": prompt_version,
        "prompt_name": prompt_name,
        "prompt_template": prompt_template,
        "extractions": extractions,
        "evaluations": evaluations,
        "avg_rating": pipeline.mean_rating(evaluations),
    }


def run_improvement_loop(
    client: Any,
    dataset: list[dict[str, Any]],
    initial_prompt_template: str,
    *,
    initial_prompt_version: str,
    best_practices_yaml: str,
    output_dir: Path,
    eval_mode: str,
    extract_model: str,
    eval_model: str,
    improve_model: str,
    max_rounds: int,
    min_improvement: float,
    extract_batch_size: int = 30,
    judge_batch_size: int = 30,
    variations_per_round: int = 2,
    include_forced_self_critique: bool = True,
    max_rationales: int = 100,
    sampling_seed: int = 42,
) -> dict[str, Any]:
    """Run the iterative prompt-optimization loop."""
    output_dir.mkdir(parents=True, exist_ok=True)

    current = _evaluate_prompt_candidate(
        client,
        dataset,
        initial_prompt_template,
        initial_prompt_version,
        _round_prompt_name(0, initial_prompt_version, "Baseline"),
        eval_mode=eval_mode,
        extract_model=extract_model,
        eval_model=eval_model,
        extract_batch_size=extract_batch_size,
        judge_batch_size=judge_batch_size,
    )
    best_overall = current

    summary: dict[str, Any] = {
        "eval_mode": eval_mode,
        "extract_model": extract_model,
        "eval_model": eval_model,
        "improve_model": improve_model,
        "initial_prompt_version": initial_prompt_version,
        "max_rounds": max_rounds,
        "min_improvement": min_improvement,
        "extract_batch_size": extract_batch_size,
        "judge_batch_size": judge_batch_size,
        "variations_per_round": variations_per_round,
        "include_forced_self_critique": include_forced_self_critique,
        "rounds": [],
    }

    for round_index in range(1, max_rounds + 1):
        round_dir = output_dir / f"round_{round_index:02d}"
        round_dir.mkdir(parents=True, exist_ok=True)

        current_paths = _save_candidate_artifacts(
            round_dir,
            f"r{round_index:02d}_current_{current['prompt_name']}",
            current["prompt_template"],
            current["extractions"],
            current["evaluations"],
        )
        current = {**current, **current_paths}
        if (
            best_overall["prompt_version"] == current["prompt_version"]
            and best_overall["avg_rating"] == current["avg_rating"]
            and "prompt_key" not in best_overall
        ):
            best_overall = current

        improvements = pipeline.improve_prompt_variations(
            client,
            current["prompt_template"],
            best_practices_yaml,
            current["evaluations"],
            current["prompt_version"],
            improve_model,
            max_rationales=max_rationales,
            sampling_seed=sampling_seed,
        )
        improvements_path = round_dir / "improvements.json"
        pipeline.write_json(improvements_path, improvements)

        variation_summaries: list[dict[str, Any]] = []
        best_variation: dict[str, Any] | None = None

        all_variations = list(improvements["variations"])
        if include_forced_self_critique:
            all_variations.insert(0, {
                "variation_id": f"{current['prompt_version']}_self_critique",
                "approach_name": "Self-Critique Final JSON",
                "changes": [
                    "Add an explicit draft -> critique -> revise process before the final JSON output",
                    "Require the model to return only the final revised JSON after self-review",
                ],
                "rationale": (
                    "A self-critique pass can catch missing facts, vague intent labels, "
                    "hallucinations, and schema mistakes before the final answer is emitted."
                ),
                "prompt_template": _build_self_critique_prompt(current["prompt_template"]),
                "forced_candidate": True,
            })

        ranked_variations = (
            all_variations[: variations_per_round + 1]
            if include_forced_self_critique
            else all_variations[:variations_per_round]
        )

        for variation in ranked_variations:
            variation_name = _round_prompt_name(
                round_index,
                variation["variation_id"],
                variation.get("approach_name"),
            )
            candidate = _evaluate_prompt_candidate(
                client,
                dataset,
                variation["prompt_template"],
                variation["variation_id"],
                variation_name,
                eval_mode=eval_mode,
                extract_model=extract_model,
                eval_model=eval_model,
                extract_batch_size=extract_batch_size,
                judge_batch_size=judge_batch_size,
            )
            candidate_paths = _save_candidate_artifacts(
                round_dir,
                variation_name,
                candidate["prompt_template"],
                candidate["extractions"],
                candidate["evaluations"],
            )
            candidate = {**candidate, **candidate_paths}

            summary_item = {
                "variation_id": variation["variation_id"],
                "approach_name": variation.get("approach_name"),
                "prompt_name": candidate["prompt_name"],
                "forced_candidate": variation.get("forced_candidate", False),
                "avg_rating": candidate["avg_rating"],
                "changes": variation.get("changes", []),
                "rationale": variation.get("rationale"),
                **candidate_paths,
            }
            variation_summaries.append(summary_item)

            if best_variation is None or candidate["avg_rating"] > best_variation["avg_rating"]:
                best_variation = candidate

        if best_variation is None:
            raise RuntimeError("Improvement step returned no variations to evaluate.")

        improvement = best_variation["avg_rating"] - current["avg_rating"]
        accepted = improvement > min_improvement

        round_summary = {
            "round_index": round_index,
            "current_prompt_key": current["prompt_key"],
            "current_prompt_name": current["prompt_name"],
            "current_prompt_version": current["prompt_version"],
            "current_avg_rating": current["avg_rating"],
            "current_prompt_path": current_paths["prompt_path"],
            "current_extractions_path": current_paths["extractions_path"],
            "current_evaluations_path": current_paths["evaluations_path"],
            "improvements_path": str(improvements_path),
            "best_variation_version": best_variation["prompt_version"],
            "best_variation_name": best_variation["prompt_name"],
            "best_variation_key": best_variation["prompt_key"],
            "best_variation_avg_rating": best_variation["avg_rating"],
            "improvement": improvement,
            "accepted": accepted,
            "model_variations_proposed": len(improvements["variations"]),
            "forced_variations_proposed": 1 if include_forced_self_critique else 0,
            "variations_proposed": len(all_variations),
            "variations_evaluated": len(ranked_variations),
            "variations": variation_summaries,
        }
        summary["rounds"].append(round_summary)

        if best_variation["avg_rating"] > best_overall["avg_rating"]:
            best_overall = best_variation

        if not accepted:
            summary["stopped_reason"] = (
                f"No candidate improved the current prompt by more than {min_improvement:.2f}."
            )
            break

        current = best_variation
    else:
        summary["stopped_reason"] = "Reached max_rounds."

    best_prompt_path = output_dir / "best_prompt.txt"
    best_prompt_path.write_text(best_overall["prompt_template"])

    summary["best_prompt_version"] = best_overall["prompt_version"]
    summary["best_prompt_name"] = best_overall["prompt_name"]
    summary["best_prompt_key"] = best_overall["prompt_key"]
    summary["best_avg_rating"] = best_overall["avg_rating"]
    summary["best_prompt_path"] = str(best_prompt_path)
    summary["versions"] = _build_versions_ledger(summary)

    summary_path = output_dir / "loop_summary.json"
    pipeline.write_json(summary_path, summary)
    pipeline.write_json(output_dir / "prompt_versions.json", summary["versions"])
    return summary


def main():
    parser = argparse.ArgumentParser(description="Run iterative prompt-improvement loop")
    parser.add_argument("--dataset", required=True, help="Path to raw dataset JSON")
    parser.add_argument("--prompt-template", required=True, help="Path to initial prompt template (.txt)")
    parser.add_argument("--best-practices", default="best_practices.yaml", help="Path to best_practices.yaml")
    parser.add_argument("--output-dir", default="loop_runs/latest", help="Directory for all loop artifacts")
    parser.add_argument("--eval-mode", choices=["judge", "ground_truth_intent"], required=True)
    parser.add_argument("--initial-version", default="v1", help="Version label for the initial prompt")
    parser.add_argument("--extract-model", default="gpt-4.1-mini", help="OpenAI model for extraction")
    parser.add_argument("--eval-model", default="gpt-4.1-mini", help="OpenAI model for judge evaluation")
    parser.add_argument("--improve-model", default="gpt-4.1-mini", help="OpenAI model for prompt improvement")
    parser.add_argument("--max-rounds", type=int, default=3, help="Maximum number of improvement rounds")
    parser.add_argument("--min-improvement", type=float, default=0.05, help="Minimum average-rating gain to continue")
    parser.add_argument("--extract-batch-size", type=int, default=30, help="Number of requests to extract per LLM call")
    parser.add_argument("--judge-batch-size", type=int, default=30, help="Number of judged items to score per LLM call")
    parser.add_argument("--variations-per-round", type=int, default=2, help="How many ranked prompt variations to fully evaluate each round")
    parser.add_argument("--no-forced-self-critique", action="store_true", help="Disable the always-included self-critique candidate")
    parser.add_argument("--max-rationales", type=int, default=100, help="Maximum rationales to pass into improvement")
    parser.add_argument("--sampling-seed", type=int, default=42, help="Random seed for rationale sampling")
    parser.add_argument("--max-items", type=int, default=None, help="Optional cap on dataset size")
    args = parser.parse_args()

    dataset = pipeline.load_json(args.dataset)
    if args.max_items is not None:
        dataset = dataset[:args.max_items]

    prompt_template = Path(args.prompt_template).read_text()
    best_practices_yaml = Path(args.best_practices).read_text()

    client = OpenAI()
    summary = run_improvement_loop(
        client,
        dataset,
        prompt_template,
        initial_prompt_version=args.initial_version,
        best_practices_yaml=best_practices_yaml,
        output_dir=Path(args.output_dir),
        eval_mode=args.eval_mode,
        extract_model=args.extract_model,
        eval_model=args.eval_model,
        improve_model=args.improve_model,
        max_rounds=args.max_rounds,
        min_improvement=args.min_improvement,
        extract_batch_size=args.extract_batch_size,
        judge_batch_size=args.judge_batch_size,
        variations_per_round=args.variations_per_round,
        include_forced_self_critique=not args.no_forced_self_critique,
        max_rationales=args.max_rationales,
        sampling_seed=args.sampling_seed,
    )

    print(f"Best prompt version: {summary['best_prompt_version']}")
    print(f"Best avg rating: {summary['best_avg_rating']:.2f}")
    print(f"Artifacts written to: {args.output_dir}")


if __name__ == "__main__":
    main()
