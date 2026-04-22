# %% [markdown]
# # Session 5: Exercises — Tool Calling
#
# These exercises build on the session. Run `session5_tool_calling.py` first
# so you understand the patterns, then come back here.
#
# We use **open APIs that require no API keys**:
# - [Open-Meteo](https://open-meteo.com/) — weather forecasts
# - [Frankfurter](https://frankfurter.app/) — currency conversion
# - [REST Countries](https://restcountries.com/) — country information

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
# In the lesson, we gave you `tool_loop()` ready-made. Now build it yourself.
#
# **Task:** Write a function `my_tool_loop(user_message, tools, tool_schemas, system_prompt, max_iterations)`
# that:
# 1. Sends messages + tool schemas to the API
# 2. If the model returns `tool_calls`, executes each one and appends the result
# 3. If the model returns text (no tool calls), returns it as the final answer
# 4. Stops after `max_iterations` to prevent infinite loops
#
# Test it with the data tools from the lesson.

# %%
from data_tools import make_customer_data, init, TOOL_SCHEMAS, TOOLS

df = make_customer_data()
init(df)

# %%
def my_tool_loop(user_message, tools, tool_schemas, system_prompt="You are a helpful assistant.", max_iterations=10):
    """Run a tool-calling loop until the model produces a text answer.

    Args:
        user_message: the user's query
        tools: dict mapping tool name -> callable
        tool_schemas: list of tool schema dicts for the API
        system_prompt: system message content
        max_iterations: safety limit

    Returns:
        The model's final text answer
    """
    # TODO: implement the loop
    # 1. Build initial messages list with system + user
    # 2. Loop up to max_iterations:
    #    a. Call client.chat.completions.create(..., tools=tool_schemas, tool_choice="auto")
    #    b. If msg.tool_calls exists: execute each, append tool results
    #    c. If no tool_calls: return msg.content
    # 3. Return "[Max iterations reached]" if budget exhausted
    pass


# Uncomment to test:
# answer = my_tool_loop(
#     "What kind of data is in this dataset? Is churn prediction possible?",
#     tools=TOOLS,
#     tool_schemas=TOOL_SCHEMAS,
#     system_prompt="You are a data analysis assistant. Call explore_data first if unsure about the schema.",
# )
# print(answer)

# %% [markdown]
# ---
# ## Exercise 2: Parallel tool calls
#
# When the user asks to **compare** results, the model may emit multiple tool
# calls in a single response. You must handle the `tool_calls` array — execute
# all of them and return each result with the correct `tool_call_id`.
#
# **Task:** Ask the model to compare 3-cluster vs 5-cluster segmentation.
# Observe whether it issues parallel calls. If it does, make sure your loop
# handles it correctly. If it doesn't, try rephrasing the query.

# %%
# TODO:
# 1. Use my_tool_loop (or the lesson's tool_loop) with this query:
#    "Compare customer segmentation with 3 clusters vs 5 clusters.
#     Use features: age, income, monthly_spend, visits_per_month, support_tickets."
#
# 2. Print each iteration: how many tool calls? which tools? what arguments?
#
# 3. Does the model call cluster_data twice in parallel, or sequentially?
#    Try with both MODEL and a stronger model to see if behavior differs.

# Your code here

# %% [markdown]
# ---
# ## Exercise 3: Travel assistant with real APIs
#
# Build a small travel assistant with **three tools** that call real, free APIs:
#
# | Tool | API | What it does |
# |------|-----|-------------|
# | `get_weather` | Open-Meteo | 7-day forecast for a city |
# | `convert_currency` | Frankfurter | Convert between currencies |
# | `get_country_info` | REST Countries | Capital, population, languages, currency |
#
# **Task:**
# 1. Implement the three tool functions (we provide stubs below)
# 2. Write the tool schemas (JSON)
# 3. Wire them into a tool loop
# 4. Test with: "I'm planning a trip to Japan. What's the weather in Tokyo,
#    how much is 500 EUR in JPY, and tell me about the country."

# %%
# ── Tool implementations (fill in the TODO parts) ────────────────

def get_weather(city):
    """Get 7-day weather forecast for a city using Open-Meteo (no API key needed).

    Steps:
    1. Geocode the city name to lat/lon using Open-Meteo's geocoding API
    2. Fetch the 7-day forecast using the forecast API
    3. Return a summary dict
    """
    # TODO: implement this
    # Geocoding: GET https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1
    # Forecast:  GET https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min,precipitation_sum&timezone=auto
    #
    # Return: {"city": city, "coordinates": [lat, lon],
    #          "daily": [{"date": ..., "max_temp": ..., "min_temp": ..., "precip_mm": ...}, ...]}
    pass


def convert_currency(amount, from_currency, to_currency):
    """Convert between currencies using Frankfurter API (no API key needed).

    GET https://api.frankfurter.app/latest?amount={amount}&from={from_currency}&to={to_currency}
    """
    # TODO: implement this
    # Return: {"amount": amount, "from": from_currency, "to": to_currency,
    #          "result": converted_amount, "rate": exchange_rate}
    pass


def get_country_info(country_name):
    """Get country information using REST Countries API (no API key needed).

    GET https://restcountries.com/v3.1/name/{country_name}?fields=name,capital,population,languages,currencies,region
    """
    # TODO: implement this
    # Return: {"name": official_name, "capital": capital_city,
    #          "population": population, "region": region,
    #          "languages": [...], "currencies": [...]}
    pass


# Test each tool individually before wiring them up:
# print(json.dumps(get_weather("Tokyo"), indent=2))
# print(json.dumps(convert_currency(500, "EUR", "JPY"), indent=2))
# print(json.dumps(get_country_info("Japan"), indent=2))

# %%
# ── Tool schemas (fill in) ───────────────────────────────────────

TRAVEL_TOOL_SCHEMAS = [
    # TODO: define the schema for get_weather
    # {
    #     "type": "function",
    #     "function": {
    #         "name": "get_weather",
    #         "description": "...",
    #         "parameters": { ... }
    #     }
    # },

    # TODO: define the schema for convert_currency

    # TODO: define the schema for get_country_info
]

TRAVEL_TOOLS = {
    "get_weather": get_weather,
    "convert_currency": convert_currency,
    "get_country_info": get_country_info,
}

# %%
# ── Wire it up and test ──────────────────────────────────────────

# TODO: use my_tool_loop (from exercise 1) or write a simple loop here
# System prompt suggestion:
#   "You are a travel assistant. Use the available tools to answer
#    questions about destinations, weather, currency, and countries.
#    If a tool returns an error, explain the issue to the user."

# Test queries:
# 1. "I'm planning a trip to Japan. What's the weather in Tokyo,
#     how much is 500 EUR in JPY, and tell me about the country."
# 2. "Compare the weather in Barcelona and Reykjavik for next week."
# 3. "I have 1000 USD. How much is that in EUR and GBP?"

# Your code here

# %% [markdown]
# ---
# ## Exercise 4: Graceful error handling
#
# Real tools fail. The model should explain errors to the user, not crash.
#
# **Task:** Using the data tools from the lesson, test these scenarios:
# 1. Remove the `churned` column and ask for churn prediction
# 2. Ask to cluster on a column that doesn't exist
# 3. Ask to classify with an empty new_row
#
# For each: does the model handle the error gracefully? If not, modify
# the system prompt to improve error handling.

# %%
# Scenario 1: no target column
# init(df.drop(columns=["churned"]))
# answer = my_tool_loop(
#     "Will a customer with age=29, income=42k churn?",
#     tools=TOOLS, tool_schemas=TOOL_SCHEMAS,
#     system_prompt="You are a data analyst. If a tool returns an error or missing data, explain clearly.",
# )
# print(answer)
# init(df)  # restore

# Scenario 2: invalid column names
# TODO: ask to cluster on ["favorite_color", "shoe_size"] — columns that don't exist

# Scenario 3: what happens with a completely vague request and no clarification mode?
# TODO: try "do something with the data" with different system prompts

# Your code here

# %% [markdown]
# ---
# ## Exercise 5: Design your own toolset (open-ended)
#
# Pick a domain and build a conversational agent with 3+ tools.
#
# **Requirements:**
# - At least 3 tools with clear, distinct purposes
# - Tools should have **natural dependencies** (call A before B)
# - Include at least one tool that can return an error
# - Write good schemas (descriptive names, rich descriptions, typed params)
# - Build the agentic loop and test with 3+ queries of varying complexity
#
# **Domain ideas:**
# - **Recipe assistant:** search recipes, get nutrition info, convert units
# - **Study planner:** look up course info, check schedule conflicts, suggest study blocks
# - **Fitness tracker:** log workout, get exercise info, calculate calories
# - **Code reviewer:** analyze code, check style, suggest improvements
#
# Use real APIs where possible (no keys needed), or write stubs with
# realistic fake data.

# %%
# Your code here
