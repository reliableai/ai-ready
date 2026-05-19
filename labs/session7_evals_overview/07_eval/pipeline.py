"""
Shared helpers for the review/judge prompt-iteration lab.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any

from jinja2 import Template

from prompt_templates import render_prompt


def load_json(path: str | Path) -> Any:
    """Load JSON from disk."""
    return json.loads(Path(path).read_text())


def write_json(path: str | Path, payload: Any) -> None:
    """Write JSON to disk with stable formatting."""
    Path(path).write_text(json.dumps(payload, indent=2))


def extract_json_text(text: str) -> str:
    """Extract a JSON payload from plain text or fenced markdown."""
    if "```" in text:
        start = text.index("```") + 3
        if text[start:].startswith("json"):
            start += 4
        end = text.index("```", start)
        return text[start:end].strip()
    return text.strip()


def render_request_prompt(prompt_template: str, request: str) -> str:
    """Render a plain prompt template that uses {{request}}."""
    return Template(prompt_template).render(request=request)


def chunked(items: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    """Split items into contiguous chunks."""
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")
    return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]


def chat_completion_text(
    client: Any,
    model: str,
    messages: list[dict[str, str]],
    *,
    max_completion_tokens: int,
    temperature: float = 0,
    json_mode: bool = False,
) -> str:
    """Send a chat completion request and return the message text."""
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_completion_tokens": max_completion_tokens,
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""


def _json_response_items(text: str) -> list[dict[str, Any]]:
    """Parse a JSON object with an 'items' list."""
    payload = json.loads(extract_json_text(text))
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("response JSON must contain an 'items' list")
    return items


def _batch_extract_outputs(
    client: Any,
    batch: list[dict[str, Any]],
    prompt_template: str,
    model: str,
    *,
    max_completion_tokens: int,
    temperature: float,
) -> dict[str, str]:
    """Run one batched extraction call and return llm_response strings by item id."""
    items_payload = [
        {"id": item["id"], "request": item["text"]}
        for item in batch
    ]
    system, user = render_prompt(
        "batch_extract.j2",
        prompt_template=prompt_template,
        items_json=json.dumps(items_payload, indent=2, ensure_ascii=False),
    )
    text = chat_completion_text(
        client,
        model,
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_completion_tokens=max_completion_tokens,
        temperature=temperature,
        json_mode=True,
    )

    outputs: dict[str, str] = {}
    for entry in _json_response_items(text):
        item_id = entry.get("id")
        output = entry.get("output")
        if not isinstance(item_id, str):
            raise ValueError("each batched extraction result must include a string 'id'")
        if not isinstance(output, dict):
            raise ValueError(f"batched extraction output for item '{item_id}' must be a JSON object")
        outputs[item_id] = json.dumps(output, indent=2, ensure_ascii=False)
    return outputs


def run_extraction_dataset(
    client: Any,
    dataset: list[dict[str, Any]],
    prompt_template: str,
    prompt_version: str,
    model: str,
    *,
    max_completion_tokens: int = 4096,
    temperature: float = 0,
    batch_size: int = 30,
) -> list[dict[str, Any]]:
    """Run an extraction prompt over a raw-text dataset."""
    results: list[dict[str, Any]] = []
    for batch in chunked(dataset, batch_size):
        rendered_prompts = {
            item["id"]: render_request_prompt(prompt_template, item["text"])
            for item in batch
        }
        try:
            llm_responses = _batch_extract_outputs(
                client,
                batch,
                prompt_template,
                model,
                max_completion_tokens=max_completion_tokens,
                temperature=temperature,
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            llm_responses = {
                item["id"]: json.dumps(
                    {"error": f"Batch extraction error: {exc}"},
                    indent=2,
                    ensure_ascii=False,
                )
                for item in batch
            }

        for item in batch:
            result = dict(item)
            result["prompt_version"] = prompt_version
            result["rendered_prompt"] = rendered_prompts[item["id"]]
            result["llm_response"] = llm_responses.get(
                item["id"],
                json.dumps(
                    {"error": "Batch extraction omitted this item"},
                    indent=2,
                    ensure_ascii=False,
                ),
            )
            results.append(result)
    return results


def judge_item(client: Any, item: dict[str, Any], model: str) -> dict[str, Any]:
    """Judge one extraction item."""
    system, user = render_prompt(
        "judge_extraction.j2",
        extraction_rendered_prompt=item["rendered_prompt"],
        llm_response_to_be_assessed=item["llm_response"],
    )
    text = chat_completion_text(
        client,
        model,
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_completion_tokens=1024,
        temperature=0,
        json_mode=True,
    )
    return json.loads(extract_json_text(text))


def _batch_judgements(
    client: Any,
    batch: list[dict[str, Any]],
    model: str,
    *,
    max_completion_tokens: int,
) -> dict[str, dict[str, Any]]:
    """Run one batched judge call and return judgement payloads by item id."""
    items_payload = [
        {
            "id": item["id"],
            "rendered_prompt": item["rendered_prompt"],
            "llm_response": item["llm_response"],
        }
        for item in batch
    ]
    system, user = render_prompt(
        "batch_judge_extraction.j2",
        items_json=json.dumps(items_payload, indent=2, ensure_ascii=False),
    )
    text = chat_completion_text(
        client,
        model,
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_completion_tokens=max_completion_tokens,
        temperature=0,
        json_mode=True,
    )

    judgements: dict[str, dict[str, Any]] = {}
    for entry in _json_response_items(text):
        item_id = entry.get("id")
        motivation = entry.get("motivation")
        rating = entry.get("rating")
        if not isinstance(item_id, str):
            raise ValueError("each batched judgement must include a string 'id'")
        if not isinstance(motivation, str):
            raise ValueError(f"batched judgement for item '{item_id}' must include string 'motivation'")
        if not isinstance(rating, int):
            raise ValueError(f"batched judgement for item '{item_id}' must include integer 'rating'")
        judgements[item_id] = {
            "motivation": motivation,
            "rating": rating,
        }
    return judgements


def run_judge_dataset(
    client: Any,
    dataset: list[dict[str, Any]],
    model: str,
    *,
    batch_size: int = 30,
    max_completion_tokens: int = 4096,
) -> list[dict[str, Any]]:
    """Judge a dataset of extraction outputs."""
    results: list[dict[str, Any]] = []
    for batch in chunked(dataset, batch_size):
        try:
            judgements = _batch_judgements(
                client,
                batch,
                model,
                max_completion_tokens=max_completion_tokens,
            )
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            judgements = {
                item["id"]: {
                    "motivation": f"Judge parse error: {exc}",
                    "rating": None,
                }
                for item in batch
            }

        for item in batch:
            judgement = judgements.get(
                item["id"],
                {
                    "motivation": "Judge parse error: batched judge omitted this item",
                    "rating": None,
                },
            )
            results.append({
                "id": item["id"],
                "prompt_version": item["prompt_version"],
                "rating": judgement.get("rating"),
                "motivation": judgement.get("motivation"),
            })
    return results


def normalize_intent(value: str) -> str:
    """Normalize intent strings so spaces, hyphens, and underscores compare cleanly."""
    cleaned = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return " ".join(cleaned.split())


def parse_llm_json(text: str) -> dict[str, Any]:
    """Parse a JSON object from a raw model response."""
    return json.loads(extract_json_text(text))


def evaluate_ground_truth_intent(
    extraction_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Evaluate extracted intents against a gold label."""
    evaluations: list[dict[str, Any]] = []

    for item in extraction_results:
        expected_intent = item.get("ground_truth_intent")
        if not expected_intent:
            raise KeyError(
                f"Item {item.get('id')} is missing 'ground_truth_intent', "
                "which is required for ground_truth_intent evaluation."
            )

        predicted_intent: str | None = None
        try:
            parsed = parse_llm_json(item["llm_response"])
            raw_intent = parsed.get("intent")
            if not isinstance(raw_intent, str) or not raw_intent.strip():
                raise ValueError("missing or invalid 'intent' field")
            predicted_intent = raw_intent.strip()
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            evaluations.append({
                "id": item["id"],
                "prompt_version": item["prompt_version"],
                "rating": 1,
                "motivation": (
                    f"The output could not be evaluated because the extracted JSON was not usable: {exc}. "
                    "This evaluator only checks the intent label because the dataset has no gold symptom labels."
                ),
                "predicted_intent": None,
                "ground_truth_intent": expected_intent,
            })
            continue

        matches = normalize_intent(predicted_intent) == normalize_intent(expected_intent)
        if matches:
            rating = 5
            motivation = (
                f"The extracted intent '{predicted_intent}' matches the ground-truth intent "
                f"'{expected_intent}'. Symptoms were not evaluated because this dataset does not "
                "include gold symptom labels."
            )
        else:
            rating = 2
            motivation = (
                f"The extracted intent '{predicted_intent}' does not match the ground-truth intent "
                f"'{expected_intent}'. Symptoms were not evaluated because this dataset does not "
                "include gold symptom labels."
            )

        evaluations.append({
            "id": item["id"],
            "prompt_version": item["prompt_version"],
            "rating": rating,
            "motivation": motivation,
            "predicted_intent": predicted_intent,
            "ground_truth_intent": expected_intent,
        })

    return evaluations


def mean_rating(results: list[dict[str, Any]]) -> float:
    """Compute the average rating over valid numeric ratings."""
    ratings = [r["rating"] for r in results if isinstance(r.get("rating"), (int, float))]
    return (sum(ratings) / len(ratings)) if ratings else 0.0


def improve_prompt_variations(
    client: Any,
    current_prompt: str,
    best_practices_yaml: str,
    judged_results: list[dict[str, Any]],
    prompt_version: str,
    model: str,
    *,
    max_rationales: int = 100,
    sampling_seed: int = 42,
) -> dict[str, Any]:
    """Generate prompt variations from evaluator results."""
    version_results = [r for r in judged_results if r["prompt_version"] == prompt_version]
    if not version_results:
        raise ValueError(f"No results found for prompt version '{prompt_version}'")

    avg_rating = mean_rating(version_results)
    rationales = [r["motivation"] for r in version_results if r.get("motivation")]
    if len(rationales) > max_rationales:
        rng = random.Random(sampling_seed)
        rationales = rng.sample(rationales, max_rationales)

    system, user = render_prompt(
        "improve_prompt.j2",
        current_prompt=current_prompt,
        best_practices_yaml=best_practices_yaml,
        avg_rating=f"{avg_rating:.2f}",
        n_items=len(version_results),
        rationales=rationales,
    )
    text = chat_completion_text(
        client,
        model,
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_completion_tokens=4096,
        temperature=0,
        json_mode=True,
    )
    result = json.loads(extract_json_text(text))
    return {
        "source_prompt_version": prompt_version,
        "avg_rating": avg_rating,
        "n_items": len(version_results),
        "n_rationales_sampled": len(rationales),
        "analysis": result["analysis"],
        "variations": result["variations"],
    }
