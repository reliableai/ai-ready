"""
Download all support/incident datasets for the auto-improvement lab.

Usage:
    uv run python download_datasets.py

Downloads to ./datasets/ with a sample JSON (max 500 rows) for each,
ready to feed into the extraction → judge → improve pipeline.

Datasets:
  1. Bitext Customer Support (HuggingFace, Apache 2.0)
  2. Customer Support on Twitter (Kaggle, CC-BY-NC-SA-4.0)
  3. Tobi-Bueck Multilingual Support Tickets (HuggingFace)
  4. CFPB Consumer Complaints (US Gov, public domain)
"""

import json
import os
import random
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATASETS_DIR = Path(__file__).parent / "datasets"
SAMPLE_SIZE = 500


def download_bitext():
    """Bitext Customer Support LLM Chatbot Training Dataset."""
    from datasets import load_dataset

    print("Downloading Bitext Customer Support...")
    ds = load_dataset(
        "bitext/Bitext-customer-support-llm-chatbot-training-dataset",
        split="train",
    )
    out_dir = DATASETS_DIR / "bitext_customer_support"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save full dataset as parquet
    ds.to_parquet(out_dir / "full.parquet")

    # Save a sample as JSON for the pipeline
    indices = random.sample(range(len(ds)), min(SAMPLE_SIZE, len(ds)))
    sample = [ds[i] for i in sorted(indices)]
    items = [
        {
            "id": f"bitext_{i:04d}",
            "source": "bitext",
            "text": row["instruction"],
            "ground_truth_intent": row.get("intent"),
            "category": row.get("category"),
        }
        for i, row in enumerate(sample)
    ]
    (out_dir / "sample.json").write_text(json.dumps(items, indent=2))
    print(f"  Saved {len(ds)} rows (full) + {len(items)} rows (sample)")


def download_twitter_support():
    """Customer Support on Twitter (Kaggle)."""
    import subprocess

    print("Downloading Customer Support on Twitter (Kaggle)...")
    out_dir = DATASETS_DIR / "twitter_customer_support"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(
            [
                "kaggle", "datasets", "download",
                "-d", "thoughtvector/customer-support-on-twitter",
                "-p", str(out_dir),
                "--unzip",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        # Try via uv
        subprocess.run(
            [
                "uv", "run", "kaggle", "datasets", "download",
                "-d", "thoughtvector/customer-support-on-twitter",
                "-p", str(out_dir),
                "--unzip",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    # Find the CSV and sample inbound tweets
    import csv

    csv_files = list(out_dir.glob("*.csv"))
    if not csv_files:
        print("  WARNING: No CSV found after download. Check Kaggle credentials.")
        return

    csv_path = csv_files[0]
    inbound = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("inbound", "").lower() == "true" and row.get("text", "").strip():
                inbound.append(row)

    sample = random.sample(inbound, min(SAMPLE_SIZE, len(inbound)))
    items = [
        {
            "id": f"twitter_{i:04d}",
            "source": "twitter_support",
            "text": row["text"],
        }
        for i, row in enumerate(sample)
    ]
    (out_dir / "sample.json").write_text(json.dumps(items, indent=2))
    print(f"  Saved {len(inbound)} inbound tweets (full CSV) + {len(items)} rows (sample)")


def download_tobi_bueck():
    """Tobi-Bueck Multilingual Customer Support Tickets."""
    from datasets import load_dataset

    print("Downloading Tobi-Bueck Support Tickets...")
    out_dir = DATASETS_DIR / "tobi_bueck_tickets"
    out_dir.mkdir(parents=True, exist_ok=True)

    ds = load_dataset("Tobi-Bueck/customer-support-tickets", split="train")
    ds.to_parquet(out_dir / "full.parquet")

    # Filter English, sample
    english_rows = [ds[i] for i in range(len(ds)) if ds[i].get("language", "") == "English"]
    if not english_rows:
        english_rows = [ds[i] for i in range(len(ds))]  # fallback: take all

    sample = random.sample(english_rows, min(SAMPLE_SIZE, len(english_rows)))
    items = [
        {
            "id": f"tbueck_{i:04d}",
            "source": "tobi_bueck",
            "text": f"Subject: {row.get('subject', '')}\n\n{row.get('body', '')}",
            "department": row.get("department"),
            "priority": row.get("priority"),
            "ticket_type": row.get("type"),
        }
        for i, row in enumerate(sample)
    ]
    (out_dir / "sample.json").write_text(json.dumps(items, indent=2))
    print(f"  Saved {len(ds)} rows (full) + {len(items)} rows (sample)")


def download_cfpb():
    """CFPB Consumer Complaint Database (US Gov, public domain)."""
    import csv
    import io
    import zipfile
    from urllib.request import urlretrieve

    print("Downloading CFPB Consumer Complaints...")
    out_dir = DATASETS_DIR / "cfpb_complaints"
    out_dir.mkdir(parents=True, exist_ok=True)

    url = "https://files.consumerfinance.gov/ccdb/complaints.csv.zip"
    zip_path = out_dir / "complaints.csv.zip"

    if not zip_path.exists():
        print("  Fetching ZIP (this may take a minute)...")
        urlretrieve(url, zip_path)

    # Extract and sample rows that have a narrative
    print("  Extracting and sampling narratives...")
    with_narrative = []
    with zipfile.ZipFile(zip_path) as zf:
        csv_name = [n for n in zf.namelist() if n.endswith(".csv")][0]
        with zf.open(csv_name) as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
            for row in reader:
                narrative = row.get("Consumer complaint narrative", "").strip()
                if narrative:
                    with_narrative.append(row)

    sample = random.sample(with_narrative, min(SAMPLE_SIZE, len(with_narrative)))
    items = [
        {
            "id": f"cfpb_{i:04d}",
            "source": "cfpb",
            "text": row["Consumer complaint narrative"],
            "product": row.get("Product"),
            "issue": row.get("Issue"),
            "sub_issue": row.get("Sub-issue"),
        }
        for i, row in enumerate(sample)
    ]
    (out_dir / "sample.json").write_text(json.dumps(items, indent=2))
    print(f"  Found {len(with_narrative)} complaints with narratives, saved {len(items)} (sample)")


if __name__ == "__main__":
    random.seed(42)
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)

    download_bitext()
    download_tobi_bueck()
    download_twitter_support()
    download_cfpb()

    print("\nDone! All datasets in:", DATASETS_DIR)
    print("Each folder contains a sample.json ready for the pipeline.")
