# %% [markdown]
# # Session 5: Solutions — Tool Calling

# %%
import os, json, requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()
MODEL = "gpt-4.1-mini"
print(f"Client ready — using {MODEL}")

# %% [markdown]
# ---
# ## Exercise 1: Build the agentic loop from scratch
#
# The loop: send messages → if model returns tool_calls, execute them and append
# results → if model returns text, that's the final answer → repeat up to max_iterations.

# %%
# Load the data tools from the lesson. init(df) binds tools to the dataset.
from data_tools import make_customer_data, init, TOOL_SCHEMAS, TOOLS

df = make_customer_data()
init(df)

# %%
def my_tool_loop(user_message, tools, tool_schemas, system_prompt="You are a helpful assistant.", max_iterations=10):
    """Run a tool-calling loop until the model produces a text answer."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    for i in range(1, max_iterations + 1):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tool_schemas,
            tool_choice="auto",
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            print(f"  Iteration {i}: FINAL ANSWER")
            return msg.content

        print(f"  Iteration {i}: {len(msg.tool_calls)} tool call(s)")
        messages.append(msg)

        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            print(f"    → {tc.function.name}({json.dumps(args)[:80]})")

            result = json.dumps(tools[tc.function.name](**args))

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    return "[Max iterations reached]"


# %% [markdown]
# Test with a simple query. Expect: the model calls `explore_data` once,
# sees the schema, then answers in text.

# %%
answer = my_tool_loop(
    "What kind of data is in this dataset? Is churn prediction possible?",
    tools=TOOLS,
    tool_schemas=TOOL_SCHEMAS,
    system_prompt="You are a data analysis assistant. Call explore_data first if unsure about the schema.",
)
print(f"\nAnswer:\n{answer}")

# %% [markdown]
# Now a compound query. Expect: explore_data → cluster_data → classify_data → answer.
# The model chains 3 tools before producing text.

# %%
# More complex: multi-tool
answer = my_tool_loop(
    "Find customer segments AND predict churn for: age=29, income=42k, spend=180, visits=4, tickets=3, region=south.",
    tools=TOOLS,
    tool_schemas=TOOL_SCHEMAS,
    system_prompt="You are a data analysis assistant. Call explore_data first if unsure about the schema.",
)
print(f"\nAnswer:\n{answer}")

# %% [markdown]
# ---
# ## Exercise 2: Parallel tool calls
#
# When comparing, the model may issue two `cluster_data` calls in the same
# response (k=3 and k=5). Watch for `Iteration N: 2 tool call(s)` — that
# means parallel calls. Both results are returned with matching `tool_call_id`s.

# %%
answer = my_tool_loop(
    "Compare customer segmentation with 3 clusters vs 5 clusters. "
    "Use features: age, income, monthly_spend, visits_per_month, support_tickets. "
    "Run both clusterings and compare the results.",
    tools=TOOLS,
    tool_schemas=TOOL_SCHEMAS,
    system_prompt=(
        "You are a data analysis assistant. When asked to compare multiple "
        "configurations, call the tool multiple times with different parameters. "
        "You may issue parallel tool calls if possible."
    ),
)
print(f"\nAnswer:\n{answer}")

# %% [markdown]
# ---
# ## Exercise 3: Travel assistant with real APIs
#
# Three tools calling free, keyless APIs. Each function makes HTTP requests
# and returns a structured dict (or an error dict if something goes wrong).

# %%
def get_weather(city):
    """Get 7-day weather forecast using Open-Meteo (no API key)."""
    # Step 1: geocode
    geo = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1},
        timeout=10,
    ).json()

    if not geo.get("results"):
        return {"error": f"City '{city}' not found"}

    loc = geo["results"][0]
    lat, lon = loc["latitude"], loc["longitude"]

    # Step 2: forecast
    forecast = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "auto",
        },
        timeout=10,
    ).json()

    daily = forecast["daily"]
    days = []
    for i in range(len(daily["time"])):
        days.append({
            "date": daily["time"][i],
            "max_temp_c": daily["temperature_2m_max"][i],
            "min_temp_c": daily["temperature_2m_min"][i],
            "precip_mm": daily["precipitation_sum"][i],
        })

    return {
        "city": city,
        "coordinates": [lat, lon],
        "daily": days,
    }


def convert_currency(amount, from_currency, to_currency):
    """Convert currencies using Frankfurter API (no API key)."""
    resp = requests.get(
        "https://api.frankfurter.app/latest",
        params={"amount": amount, "from": from_currency, "to": to_currency},
        timeout=10,
    ).json()

    if "message" in resp:
        return {"error": resp["message"]}

    return {
        "amount": amount,
        "from": from_currency,
        "to": to_currency,
        "result": resp["rates"].get(to_currency),
        "rate": resp["rates"].get(to_currency, 0) / amount if amount else 0,
        "date": resp.get("date"),
    }


def get_country_info(country_name):
    """Get country info using REST Countries API (no API key)."""
    resp = requests.get(
        f"https://restcountries.com/v3.1/name/{country_name}",
        params={"fields": "name,capital,population,languages,currencies,region"},
        timeout=10,
    )

    if resp.status_code != 200:
        return {"error": f"Country '{country_name}' not found"}

    data = resp.json()[0]
    return {
        "name": data["name"]["common"],
        "official_name": data["name"]["official"],
        "capital": data.get("capital", ["N/A"])[0],
        "population": data.get("population"),
        "region": data.get("region"),
        "languages": list(data.get("languages", {}).values()),
        "currencies": [
            {"code": code, "name": info["name"], "symbol": info.get("symbol", "")}
            for code, info in data.get("currencies", {}).items()
        ],
    }


# Quick test — call each tool directly to verify they work before wiring to the LLM.
# get_weather returns 7 days of forecasts; convert_currency returns the converted amount;
# get_country_info returns capital, population, languages, etc.
print("=== Weather ===")
print(json.dumps(get_weather("Tokyo"), indent=2)[:300], "...")
print("\n=== Currency ===")
print(json.dumps(convert_currency(500, "EUR", "JPY"), indent=2))
print("\n=== Country ===")
print(json.dumps(get_country_info("Japan"), indent=2))

# %% [markdown]
# Define the tool schemas. The model uses these descriptions to decide which
# tool to call and what arguments to pass — it never sees our Python code.

# %%
TRAVEL_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get a 7-day weather forecast for a city. Returns daily max/min temperature and precipitation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name, e.g. 'Tokyo' or 'Barcelona'"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "convert_currency",
            "description": "Convert an amount between currencies using current exchange rates. Use ISO 4217 currency codes (EUR, USD, JPY, GBP, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Amount to convert"},
                    "from_currency": {"type": "string", "description": "Source currency code, e.g. 'EUR'"},
                    "to_currency": {"type": "string", "description": "Target currency code, e.g. 'JPY'"},
                },
                "required": ["amount", "from_currency", "to_currency"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_country_info",
            "description": "Get information about a country: capital, population, languages, currencies, and region.",
            "parameters": {
                "type": "object",
                "properties": {
                    "country_name": {"type": "string", "description": "Country name, e.g. 'Japan' or 'Italy'"},
                },
                "required": ["country_name"],
            },
        },
    },
]

TRAVEL_TOOLS = {
    "get_weather": get_weather,
    "convert_currency": convert_currency,
    "get_country_info": get_country_info,
}

# %% [markdown]
# Wire the tools into the loop and run 4 test queries:
# 1. Multi-tool trip planning (expect: all 3 tools called)
# 2. Weather comparison (may trigger parallel get_weather calls)
# 3. Multi-currency (may trigger parallel convert_currency calls)
# 4. Error handling — "Atlantis" should return an error, model explains gracefully

# %%
TRAVEL_SYSTEM = (
    "You are a travel assistant. Use the available tools to answer "
    "questions about destinations, weather, currency, and countries. "
    "If a tool returns an error, explain the issue to the user."
)

# Test 1: multi-tool trip planning
print("=" * 60)
print("Query: Plan my Japan trip")
print("=" * 60)
answer = my_tool_loop(
    "I'm planning a trip to Japan. What's the weather in Tokyo, "
    "how much is 500 EUR in JPY, and tell me about the country.",
    tools=TRAVEL_TOOLS,
    tool_schemas=TRAVEL_TOOL_SCHEMAS,
    system_prompt=TRAVEL_SYSTEM,
)
print(f"\nAnswer:\n{answer}")

# %%
# Test 2: weather comparison (may trigger parallel calls)
print("=" * 60)
print("Query: Compare weather")
print("=" * 60)
answer = my_tool_loop(
    "Compare the weather in Barcelona and Reykjavik for next week.",
    tools=TRAVEL_TOOLS,
    tool_schemas=TRAVEL_TOOL_SCHEMAS,
    system_prompt=TRAVEL_SYSTEM,
)
print(f"\nAnswer:\n{answer}")

# %%
# Test 3: multi-currency conversion
print("=" * 60)
print("Query: Currency conversion")
print("=" * 60)
answer = my_tool_loop(
    "I have 1000 USD. How much is that in EUR and GBP?",
    tools=TRAVEL_TOOLS,
    tool_schemas=TRAVEL_TOOL_SCHEMAS,
    system_prompt=TRAVEL_SYSTEM,
)
print(f"\nAnswer:\n{answer}")

# %%
# Test 4: error handling — misspelled city
print("=" * 60)
print("Query: Bad city name")
print("=" * 60)
answer = my_tool_loop(
    "What's the weather in Atlantis?",
    tools=TRAVEL_TOOLS,
    tool_schemas=TRAVEL_TOOL_SCHEMAS,
    system_prompt=TRAVEL_SYSTEM,
)
print(f"\nAnswer:\n{answer}")

# %% [markdown]
# ---
# ## Exercise 4: Graceful error handling
#
# Three scenarios where tools can't do what's asked. The system prompt
# instructs the model to explain errors clearly instead of crashing.

# %%
# Scenario 1: no target column — the model should explore, see no candidate
# targets, and explain that churn prediction isn't possible.
init(df.drop(columns=["churned"]))

answer = my_tool_loop(
    "Will a customer with age=29, income=42k churn?",
    tools=TOOLS,
    tool_schemas=TOOL_SCHEMAS,
    system_prompt=(
        "You are a data analyst. If a tool returns an error or the data "
        "doesn't support the requested analysis, explain clearly to the user "
        "what's missing and what alternatives exist."
    ),
)
print(f"\nAnswer:\n{answer}")

# Restore full dataset
init(df)

# %% [markdown]
# Scenario 2: columns don't exist. The model should call explore_data first,
# discover available columns, and explain that favorite_color/shoe_size aren't there.

# %%
# Scenario 2: invalid column names
answer = my_tool_loop(
    "Cluster customers by favorite_color and shoe_size.",
    tools=TOOLS,
    tool_schemas=TOOL_SCHEMAS,
    system_prompt=(
        "You are a data analyst. Call explore_data first to check available columns. "
        "If requested columns don't exist, explain what columns are available."
    ),
)
print(f"\nAnswer:\n{answer}")

# %% [markdown]
# Scenario 3: vague request. With a good system prompt, the model should
# explore the data first and then propose a specific analysis.

# %%
# Scenario 3: completely vague request
answer = my_tool_loop(
    "Do something interesting with the data.",
    tools=TOOLS,
    tool_schemas=TOOL_SCHEMAS,
    system_prompt=(
        "You are a data analyst. If the request is vague, start by exploring "
        "the data and then propose a specific analysis based on what you find."
    ),
)
print(f"\nAnswer:\n{answer}")
