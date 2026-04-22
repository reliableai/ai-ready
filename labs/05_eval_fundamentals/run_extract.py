"""
Run an extraction prompt over a raw dataset of requests.

Usage:
    python run_extract.py \
        --dataset datasets/bitext_customer_support/sample.json \
        --prompt-template prompt_templates/extract_v1.j2 \
        --prompt-version v1 \
        --output extracted_results.json
"""

import argparse

from dotenv import load_dotenv
from openai import OpenAI

from pipeline import load_json, run_extraction_dataset, write_json


load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Run extraction prompt over a dataset")
    parser.add_argument("--dataset", required=True, help="Path to raw input dataset JSON")
    parser.add_argument("--prompt-template", required=True, help="Path to prompt template (.txt)")
    parser.add_argument("--prompt-version", required=True, help="Version label for this prompt run")
    parser.add_argument("--output", default="extracted_results.json", help="Path to output JSON")
    parser.add_argument("--model", default="gpt-4.1-mini", help="OpenAI model to use")
    parser.add_argument("--max-items", type=int, default=None, help="Optional cap on dataset size")
    parser.add_argument("--batch-size", type=int, default=30, help="Number of requests to process per LLM call")
    parser.add_argument("--temperature", type=float, default=0, help="Sampling temperature")
    args = parser.parse_args()

    dataset = load_json(args.dataset)
    if args.max_items is not None:
        dataset = dataset[:args.max_items]

    with open(args.prompt_template) as f:
        prompt_template = f.read()

    client = OpenAI()
    results = run_extraction_dataset(
        client,
        dataset,
        prompt_template,
        args.prompt_version,
        args.model,
        temperature=args.temperature,
        batch_size=args.batch_size,
    )
    write_json(args.output, results)
    print(f"Processed {len(results)} items with prompt version '{args.prompt_version}'.")
    print(f"Results written to {args.output}")


if __name__ == "__main__":
    main()
