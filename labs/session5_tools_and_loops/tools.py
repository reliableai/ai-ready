"""
Well-documented tool definitions for the travel planning assistant.

Each tool is a plain Python function returning hardcoded/deterministic fake data.
No external APIs needed — the focus is on how tools connect to LLMs, not on the
tools themselves.

Usage:
    from tools import TOOL_REGISTRY, get_openai_tool_schemas, execute_tool
"""

import json
import inspect
from typing import Any


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------

def get_weather(city: str, date: str) -> dict:
    """Get the weather forecast for a city on a specific date.

    Args:
        city: Name of the city (e.g. "Rome", "Barcelona", "Tokyo").
        date: Date in YYYY-MM-DD format (e.g. "2026-03-15").

    Returns:
        A dict with keys: city, date, temperature_c, condition, humidity_pct, wind_kmh.

    Example:
        >>> get_weather("Rome", "2026-03-15")
        {"city": "Rome", "date": "2026-03-15", "temperature_c": 18, ...}
    """
    # Deterministic fake data keyed on city name length + date hash
    seed = len(city) + sum(ord(c) for c in date)
    temps = [14, 18, 22, 26, 30, 8, 12, 20, 25, 16]
    conditions = ["Sunny", "Partly cloudy", "Cloudy", "Light rain", "Clear"]
    return {
        "city": city,
        "date": date,
        "temperature_c": temps[seed % len(temps)],
        "condition": conditions[seed % len(conditions)],
        "humidity_pct": 40 + (seed % 45),
        "wind_kmh": 5 + (seed % 30),
    }


def convert_currency(amount: float, from_currency: str, to_currency: str) -> dict:
    """Convert an amount from one currency to another.

    Uses approximate fixed exchange rates (not live data).

    Args:
        amount: The amount to convert (e.g. 100.0).
        from_currency: ISO 4217 currency code (e.g. "USD", "EUR", "GBP", "JPY").
        to_currency: ISO 4217 currency code to convert to.

    Returns:
        A dict with keys: from_currency, to_currency, original_amount,
        converted_amount, exchange_rate.

    Example:
        >>> convert_currency(100, "USD", "EUR")
        {"original_amount": 100, "converted_amount": 92.0, "exchange_rate": 0.92, ...}
    """
    # Fixed approximate rates to USD
    rates_to_usd = {
        "USD": 1.0,
        "EUR": 1.09,
        "GBP": 1.27,
        "JPY": 0.0067,
        "CHF": 1.13,
        "CAD": 0.74,
        "AUD": 0.65,
        "CNY": 0.14,
    }
    from_rate = rates_to_usd.get(from_currency.upper(), 1.0)
    to_rate = rates_to_usd.get(to_currency.upper(), 1.0)
    rate = from_rate / to_rate
    converted = round(amount * rate, 2)
    return {
        "from_currency": from_currency.upper(),
        "to_currency": to_currency.upper(),
        "original_amount": amount,
        "converted_amount": converted,
        "exchange_rate": round(rate, 4),
    }


def search_hotels(city: str, checkin: str, checkout: str, max_price: int = 200) -> dict:
    """Search for available hotels in a city within a budget.

    Args:
        city: Name of the city to search in (e.g. "Barcelona").
        checkin: Check-in date in YYYY-MM-DD format.
        checkout: Check-out date in YYYY-MM-DD format.
        max_price: Maximum price per night in EUR (default: 200).

    Returns:
        A dict with keys: city, checkin, checkout, max_price, results (list of hotels).
        Each hotel has: name, price_per_night_eur, rating, distance_to_center_km.

    Example:
        >>> search_hotels("Barcelona", "2026-03-20", "2026-03-23", max_price=150)
        {"city": "Barcelona", "results": [{"name": "Hotel Ramblas", ...}, ...]}
    """
    seed = len(city) + sum(ord(c) for c in checkin)
    hotel_names = [
        f"Hotel {city} Central",
        f"Grand {city} Palace",
        f"{city} Budget Inn",
        f"The {city} Boutique",
        f"{city} Hostel Plus",
    ]
    hotels = []
    for i, name in enumerate(hotel_names):
        price = 50 + ((seed + i * 37) % 180)
        if price <= max_price:
            hotels.append({
                "name": name,
                "price_per_night_eur": price,
                "rating": round(3.0 + ((seed + i * 13) % 20) / 10, 1),
                "distance_to_center_km": round(0.5 + ((seed + i * 7) % 50) / 10, 1),
            })
    return {
        "city": city,
        "checkin": checkin,
        "checkout": checkout,
        "max_price": max_price,
        "results": hotels,
    }


def get_attractions(city: str, category: str = "all") -> dict:
    """Get popular attractions and points of interest in a city.

    Args:
        city: Name of the city (e.g. "Rome", "Tokyo").
        category: Filter by category. One of: "all", "landmarks", "museums",
                  "restaurants", "parks" (default: "all").

    Returns:
        A dict with keys: city, category, results (list of attractions).
        Each attraction has: name, category, rating, description.

    Example:
        >>> get_attractions("Rome", category="landmarks")
        {"city": "Rome", "category": "landmarks", "results": [...]}
    """
    attractions_db = {
        "landmarks": [
            {"name": f"{city} Cathedral", "rating": 4.7, "description": f"Historic cathedral in the heart of {city}"},
            {"name": f"{city} Castle", "rating": 4.5, "description": f"Medieval fortress with panoramic city views"},
            {"name": f"Old Town {city}", "rating": 4.8, "description": f"Charming historic quarter with cobblestone streets"},
        ],
        "museums": [
            {"name": f"{city} Art Museum", "rating": 4.6, "description": f"World-class collection of European art"},
            {"name": f"{city} History Museum", "rating": 4.3, "description": f"Interactive exhibits on local history"},
        ],
        "restaurants": [
            {"name": f"La Casa de {city}", "rating": 4.9, "description": f"Traditional local cuisine, reservations recommended"},
            {"name": f"{city} Street Food Market", "rating": 4.4, "description": f"Open-air market with dozens of food stalls"},
            {"name": f"Ristorante {city}", "rating": 4.7, "description": f"Fine dining with a modern twist on classics"},
        ],
        "parks": [
            {"name": f"{city} Central Park", "rating": 4.5, "description": f"Large urban park ideal for walking and picnics"},
            {"name": f"{city} Botanical Garden", "rating": 4.6, "description": f"Lush gardens with rare Mediterranean plants"},
        ],
    }

    if category == "all":
        results = []
        for cat, items in attractions_db.items():
            for item in items:
                results.append({**item, "category": cat})
    else:
        cat_key = category.lower()
        raw = attractions_db.get(cat_key, [])
        results = [{**item, "category": cat_key} for item in raw]

    return {"city": city, "category": category, "results": results}


# ---------------------------------------------------------------------------
# Registry and helpers
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict[str, callable] = {
    "get_weather": get_weather,
    "convert_currency": convert_currency,
    "search_hotels": search_hotels,
    "get_attractions": get_attractions,
}


def _python_type_to_json_type(annotation) -> str:
    """Map Python type annotations to JSON Schema types."""
    mapping = {str: "string", int: "integer", float: "number", bool: "boolean"}
    return mapping.get(annotation, "string")


def get_openai_tool_schemas() -> list[dict]:
    """Convert all registered tools into OpenAI function-calling tool schemas.

    Parses each function's signature and docstring to produce the
    ``tools`` parameter expected by ``client.chat.completions.create()``.

    Returns:
        A list of dicts, each with type="function" and a function spec
        containing name, description, and parameters JSON schema.
    """
    schemas = []
    for name, func in TOOL_REGISTRY.items():
        sig = inspect.signature(func)
        doc = inspect.getdoc(func) or ""

        # Extract first line of docstring as description
        description = doc.split("\n")[0].strip()

        # Extract parameter descriptions from docstring Args section
        param_docs = {}
        in_args = False
        for line in doc.split("\n"):
            stripped = line.strip()
            if stripped.startswith("Args:"):
                in_args = True
                continue
            if in_args:
                if stripped.startswith("Returns:") or stripped.startswith("Example:"):
                    break
                if ":" in stripped and not stripped.startswith(">>>"):
                    param_name, param_desc = stripped.split(":", 1)
                    param_docs[param_name.strip()] = param_desc.strip()

        # Build parameters schema
        properties = {}
        required = []
        for param_name, param in sig.parameters.items():
            prop: dict[str, Any] = {
                "type": _python_type_to_json_type(param.annotation),
            }
            if param_name in param_docs:
                prop["description"] = param_docs[param_name]
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
    """Look up a tool by name and call it with the given arguments.

    Args:
        name: The tool function name (must be in TOOL_REGISTRY).
        arguments: A dict of keyword arguments to pass to the function.

    Returns:
        JSON string of the tool's return value.

    Raises:
        ValueError: If the tool name is not found in the registry.
    """
    func = TOOL_REGISTRY.get(name)
    if func is None:
        raise ValueError(f"Unknown tool: {name!r}. Available: {list(TOOL_REGISTRY)}")
    result = func(**arguments)
    return json.dumps(result)
