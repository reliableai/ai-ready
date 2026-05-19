"""
Generate improved prompt variations based on judge feedback.

Usage:
    python run_improve.py \
        --prompt-template prompt_templates/extract_v1.j2 \
        --judged-results judged_results.json \
        --best-practices best_practices.yaml \
        --output improvements.json \
        --prompt-version v1

Reads judge results, samples up to 100 rationales for the given prompt version,
and asks the LLM to propose 5 prompt variations informed by failure patterns.
"""

import argparse
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from pipeline import improve_prompt_variations, load_json, write_json


load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Generate improved prompt variations")
    parser.add_argument("--prompt-template", required=True, help="Path to current prompt template (.txt)")
    parser.add_argument("--judged-results", required=True, help="Path to judged_results.json")
    parser.add_argument("--best-practices", default="best_practices.yaml", help="Path to best_practices.yaml")
    parser.add_argument("--output", default="improvements.json", help="Output path for variations")
    parser.add_argument("--prompt-version", required=True, help="Which prompt version to analyze (e.g., v1)")
    parser.add_argument("--model", default="gpt-4.1-mini", help="OpenAI model to use")
    parser.add_argument("--max-rationales", type=int, default=100, help="Max rationales to sample")
    args = parser.parse_args()

    client = OpenAI()

    current_prompt = Path(args.prompt_template).read_text()
    best_practices = Path(args.best_practices).read_text()
    judged = load_json(args.judged_results)
    version_results = [r for r in judged if r["prompt_version"] == args.prompt_version]
    if not version_results:
        print(f"No results found for prompt version '{args.prompt_version}'")
        return

    result = improve_prompt_variations(
        client,
        current_prompt,
        best_practices,
        judged,
        args.prompt_version,
        args.model,
        max_rationales=args.max_rationales,
    )

    print(
        f"Analyzing {result['n_items']} items for prompt version '{args.prompt_version}' "
        f"(avg rating: {result['avg_rating']:.2f})..."
    )
    print("Generating 5 prompt variations...\n")

    write_json(args.output, result)
    print(f"Analysis:\n{result['analysis']}\n")
    for v in result["variations"]:
        print(f"  {v['variation_id']}: {v['rationale'][:120]}...")
    print(f"\nFull results written to {args.output}")


if __name__ == "__main__":
    main()
