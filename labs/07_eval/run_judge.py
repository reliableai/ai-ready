"""
Run a judge prompt over a dataset of LLM extraction iterations.

Usage:
    python run_judge.py --dataset datasets/sample_dataset.json --output judged_results.json

Each item in the dataset must have:
    - id: unique identifier
    - prompt_version: which prompt version produced this output
    - rendered_prompt: the full prompt sent to the LLM
    - llm_response: the LLM's response

The judge assesses each extraction and outputs motivation + rating (1-5).
"""

import argparse

from dotenv import load_dotenv
from openai import OpenAI

from pipeline import load_json, run_judge_dataset, write_json


load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Run judge over extraction dataset")
    parser.add_argument("--dataset", required=True, help="Path to input JSON dataset")
    parser.add_argument("--output", default="judged_results.json", help="Path to output JSON")
    parser.add_argument("--model", default="gpt-4.1-mini", help="OpenAI model to use for judging")
    parser.add_argument("--batch-size", type=int, default=30, help="Number of judged items to process per LLM call")
    args = parser.parse_args()

    client = OpenAI()  # uses OPENAI_API_KEY env var
    dataset = load_json(args.dataset)
    results = run_judge_dataset(client, dataset, args.model, batch_size=args.batch_size)
    write_json(args.output, results)
    print(f"\nResults written to {args.output}")

    # Print summary by prompt version
    versions = sorted(set(r["prompt_version"] for r in results))
    print("\n--- Summary by prompt version ---")
    for v in versions:
        ratings = [r["rating"] for r in results if r["prompt_version"] == v and r["rating"] is not None]
        if ratings:
            avg = sum(ratings) / len(ratings)
            print(f"  {v}: avg={avg:.2f}  n={len(ratings)}  ratings={ratings}")


if __name__ == "__main__":
    main()
