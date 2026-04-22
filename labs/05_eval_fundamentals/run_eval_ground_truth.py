"""
Evaluate extraction results against ground-truth intent labels.

Usage:
    python run_eval_ground_truth.py \
        --dataset extracted_results.json \
        --output eval_results.json
"""

import argparse

from pipeline import evaluate_ground_truth_intent, load_json, mean_rating, write_json


def main():
    parser = argparse.ArgumentParser(description="Evaluate extracted intents against ground truth")
    parser.add_argument("--dataset", required=True, help="Path to extracted_results.json")
    parser.add_argument("--output", default="eval_results.json", help="Path to output JSON")
    args = parser.parse_args()

    dataset = load_json(args.dataset)
    results = evaluate_ground_truth_intent(dataset)
    write_json(args.output, results)

    avg = mean_rating(results)
    print(f"Evaluated {len(results)} items.")
    print(f"Average rating: {avg:.2f}")
    print(f"Results written to {args.output}")


if __name__ == "__main__":
    main()
