# Datasets for the Review & Judge Lab

This lab uses four customer-support / incident datasets of increasing difficulty.
The same extraction prompt will behave very differently across them — that's what
motivates prompt adaptation and the auto-improvement loop.

## Quick comparison

| Dataset | Size | Text style | Difficulty | License | Has labels? |
|---------|------|-----------|------------|---------|-------------|
| Bitext Customer Support | 26,872 | Short, 1-2 sentences | Easy | Apache 2.0 | Yes (27 intents) |
| Tobi-Bueck Tickets | 61,765 | Email with subject + body | Medium | Free / HuggingFace | Dept, priority, type |
| CFPB Complaints | 3.7M | Real consumer narratives, PII-redacted | Hard | US Gov public domain | Product, issue |
| Twitter Support | ~3M | Tweets, informal, noisy | Hardest | CC0 | None |

---

## 1. Bitext Customer Support

**What it is:** 26,872 short customer requests spanning 27 intent types (cancel_order,
track_order, complaint, check_refund_policy, etc.) across categories like ORDER, BILLING,
ACCOUNT, SHIPPING.

**Why it's useful:** Clean data with ground-truth intent labels. Perfect for baseline
testing — you can measure extraction accuracy against known labels. Uses template
placeholders like `{{Order Number}}`.

**Sample:**

```
need help with canceling order {{Order Number}}
```
```
I want to see the cancellation and refund policy, I need to cancel
```
```
there is a problem with my payment, it keeps getting declined
```

**Download:**

```python
from datasets import load_dataset
ds = load_dataset("bitext/Bitext-customer-support-llm-chatbot-training-dataset", split="train")
```

Browse: <https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset>

---

## 2. Tobi-Bueck Multilingual Support Tickets

**What it is:** 61,765 email-style support tickets with subject line, body, department,
priority (low/medium/high/critical), and type (Problem/Incident/Request). Multilingual
(we filter to English).

**Why it's useful:** Realistic multi-paragraph email format. Tests how prompts handle
verbose input where the actual symptoms are buried in polite preamble. Has metadata
for validation (priority, department, type).

**Sample:**

```
Subject: Problem Identified in Investment Optimization Model

The investment optimization model is producing less-than-ideal recommendations
due to the use of outdated data inputs. Updating the datasets should address
this issue.
```

```
Subject: Support Request: Critical Outage on Investment Data Analytics Services

Dear Customer Support, I am writing to report a critical issue with our
investment data analytics services. Recently, we have experienced outages
that may be due to server overload or configuration errors...
```

**Download:**

```python
from datasets import load_dataset
ds = load_dataset("Tobi-Bueck/customer-support-tickets", split="train")
```

Browse: <https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets>

---

## 3. CFPB Consumer Complaints

**What it is:** 3.7 million real consumer complaints submitted to the US Consumer
Financial Protection Bureau. Contains free-text narratives plus product, issue, and
sub-issue labels. PII is redacted with `XXXX`.

**Why it's useful:** Real-world messy text. Complainants ramble, mix multiple issues,
reference dates and amounts, and express frustration. The PII redaction (XXXX) adds
noise the model must handle. Financial domain — different vocabulary than tech support.

**Sample:**

```
I signed the lease in XXXX and cancelled two service contracts in XXXX.
The cancelation form was processed on the same day; however, the cancelation
refund was not issued until three months later (XXXX), after my multiple
contacts with three different parties: XXXX, XXXX, and local dealer.
```

```
XXXX XXXX XXXXXXXX XXXX XXXX Texas XXXX This company exhibit all three
credit bureau on it's websites, for customer to access their credit report
XXXX and XXXX credit information on experience is not accurate needs updated...
```

**Download:**

Direct CSV: <https://www.consumerfinance.gov/data-research/consumer-complaints/>

Or use the download script in this lab:

```bash
uv run python download_datasets.py
```

---

## 4. Twitter Customer Support (requires Kaggle credentials)

**What it is:** ~3 million tweets between customers and major brand support accounts.
Inbound tweets are customer messages; outbound are brand responses.

**Why it's useful:** The hardest extraction challenge. Tweets are short, informal,
full of abbreviations and typos. Often lack context (the customer assumes the brand
knows what product/service they mean). No labels — pure unsupervised extraction.

**Sample:**

```
@AppleSupport my macbook pro keeps crashing when I open photoshop. tried
restarting. nothing works. help??
```

```
@AmazonHelp I ordered 3 items and only received 2. order #1234567. where
is my stuff???
```

**Download:**

Requires a Kaggle API token. Three options:

**Option A: environment variable** (recommended)

```bash
# Go to https://www.kaggle.com/settings → API → copy your token
# Add to your .env file:
KAGGLE_API_TOKEN="your_token_here"
```

**Option B: token file**

```bash
echo "your_token_here" > ~/.kaggle/access_token
chmod 600 ~/.kaggle/access_token
```

**Option C: legacy credentials file** (username + key)

```bash
# From https://www.kaggle.com/settings → "Create Legacy API Key"
# It downloads a kaggle.json file. Then:
mkdir -p ~/.kaggle
mv ~/Downloads/kaggle.json ~/.kaggle/kaggle.json
chmod 600 ~/.kaggle/kaggle.json
```

Then:

```bash
uv run python download_datasets.py
```

Or download manually: <https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter>

---

## Using the datasets

Each dataset has a `sample.json` (500 rows) with a uniform schema:

```json
{
  "id": "bitext_0042",
  "source": "bitext",
  "text": "the actual customer request text...",
  ...
}
```

The `text` field is what you feed to the extraction prompt. Additional fields
(ground_truth_intent, product, priority, etc.) are available for validation.

To download all datasets:

```bash
cd labs/05_eval_fundamentals
uv run python download_datasets.py
```
