"""
Poorly-documented tool definitions — same functionality as tools.py,
but with terrible names, vague docstrings, and cryptic parameter names.

Used in Section 6 to demonstrate how tool naming/documentation affects
LLM tool selection and argument passing.
"""

import json
import inspect
from typing import Any


# ---------------------------------------------------------------------------
# Tool functions (same logic as tools.py, terrible interface)
# ---------------------------------------------------------------------------

def get_data(p1: str, p2: str) -> dict:
    """Gets data."""
    seed = len(p1) + sum(ord(c) for c in p2)
    temps = [14, 18, 22, 26, 30, 8, 12, 20, 25, 16]
    conditions = ["Sunny", "Partly cloudy", "Cloudy", "Light rain", "Clear"]
    return {
        "city": p1,
        "date": p2,
        "temperature_c": temps[seed % len(temps)],
        "condition": conditions[seed % len(conditions)],
        "humidity_pct": 40 + (seed % 45),
        "wind_kmh": 5 + (seed % 30),
    }


def do_lookup(x: float, y: str, z: str) -> dict:
    """Does a lookup."""
    rates_to_usd = {
        "USD": 1.0, "EUR": 1.09, "GBP": 1.27, "JPY": 0.0067,
        "CHF": 1.13, "CAD": 0.74, "AUD": 0.65, "CNY": 0.14,
    }
    from_rate = rates_to_usd.get(y.upper(), 1.0)
    to_rate = rates_to_usd.get(z.upper(), 1.0)
    rate = from_rate / to_rate
    converted = round(x * rate, 2)
    return {
        "from_currency": y.upper(),
        "to_currency": z.upper(),
        "original_amount": x,
        "converted_amount": converted,
        "exchange_rate": round(rate, 4),
    }


def fetch(a: str, b: str, c: str, d: int = 200) -> dict:
    """Fetches results."""
    seed = len(a) + sum(ord(ch) for ch in b)
    hotel_names = [
        f"Hotel {a} Central", f"Grand {a} Palace", f"{a} Budget Inn",
        f"The {a} Boutique", f"{a} Hostel Plus",
    ]
    hotels = []
    for i, name in enumerate(hotel_names):
        price = 50 + ((seed + i * 37) % 180)
        if price <= d:
            hotels.append({
                "name": name,
                "price_per_night_eur": price,
                "rating": round(3.0 + ((seed + i * 13) % 20) / 10, 1),
                "distance_to_center_km": round(0.5 + ((seed + i * 7) % 50) / 10, 1),
            })
    return {"city": a, "checkin": b, "checkout": c, "max_price": d, "results": hotels}


def query(q: str, t: str = "all") -> dict:
    """Runs a query."""
    attractions_db = {
        "landmarks": [
            {"name": f"{q} Cathedral", "rating": 4.7, "description": f"Historic cathedral in the heart of {q}"},
            {"name": f"{q} Castle", "rating": 4.5, "description": f"Medieval fortress with panoramic city views"},
            {"name": f"Old Town {q}", "rating": 4.8, "description": f"Charming historic quarter with cobblestone streets"},
        ],
        "museums": [
            {"name": f"{q} Art Museum", "rating": 4.6, "description": f"World-class collection of European art"},
            {"name": f"{q} History Museum", "rating": 4.3, "description": f"Interactive exhibits on local history"},
        ],
        "restaurants": [
            {"name": f"La Casa de {q}", "rating": 4.9, "description": f"Traditional local cuisine, reservations recommended"},
            {"name": f"{q} Street Food Market", "rating": 4.4, "description": f"Open-air market with dozens of food stalls"},
            {"name": f"Ristorante {q}", "rating": 4.7, "description": f"Fine dining with a modern twist on classics"},
        ],
        "parks": [
            {"name": f"{q} Central Park", "rating": 4.5, "description": f"Large urban park ideal for walking and picnics"},
            {"name": f"{q} Botanical Garden", "rating": 4.6, "description": f"Lush gardens with rare Mediterranean plants"},
        ],
    }

    if t == "all":
        results = []
        for cat, items in attractions_db.items():
            for item in items:
                results.append({**item, "category": cat})
    else:
        cat_key = t.lower()
        raw = attractions_db.get(cat_key, [])
        results = [{**item, "category": cat_key} for item in raw]

    return {"city": q, "category": t, "results": results}


# ---------------------------------------------------------------------------
# Registry and helpers (same structure as tools.py)
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict[str, callable] = {
    "get_data": get_data,
    "do_lookup": do_lookup,
    "fetch": fetch,
    "query": query,
}


def _python_type_to_json_type(annotation) -> str:
    mapping = {str: "string", int: "integer", float: "number", bool: "boolean"}
    return mapping.get(annotation, "string")


def get_openai_tool_schemas() -> list[dict]:
    """Convert all registered tools into OpenAI tool schemas."""
    schemas = []
    for name, func in TOOL_REGISTRY.items():
        sig = inspect.signature(func)
        doc = inspect.getdoc(func) or ""
        description = doc.split("\n")[0].strip()

        properties = {}
        required = []
        for param_name, param in sig.parameters.items():
            prop: dict[str, Any] = {
                "type": _python_type_to_json_type(param.annotation),
            }
            # No parameter descriptions — that's the point!
            properties[param_name] = prop
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        schemas.append({
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        })
    return schemas


def execute_tool(name: str, arguments: dict) -> str:
    """Execute a tool by name."""
    func = TOOL_REGISTRY.get(name)
    if func is None:
        raise ValueError(f"Unknown tool: {name!r}. Available: {list(TOOL_REGISTRY)}")
    result = func(**arguments)
    return json.dumps(result)
