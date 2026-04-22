

# Base
SYSTEM:
You are a senior immigration attorney specializing in employment-based visas.

USER:
<context>
A client holds an H-1B visa expiring in 60 days.
They received a job offer from a new employer.
</context>

<instructions>
List every step the client must take to transfer the visa,
including filing deadlines and required USCIS forms.
</instructions>

<constraints>
- Audience: the client (non-lawyer)
- Max 400 words
- No legal jargon without a plain-English parenthetical
</constraints>

<output_format>
Numbered checklist. Deadlines in bold. Flag any step where
an attorney is legally required.
</output_format>

# Base 2
Extract the product information from the text.

Output format (JSON):
{
  "product": string,
  "price": number,
  "category": string
}

Rules:
- Return only valid JSON.
- Do not include explanations.

Text:
The Apple Watch Series 9 is a smartwatch priced at $399.

Output:


# Few shot 1
English: Hello
French: Bonjour

English: Good morning
French: Bonjour

English: Thank you
French: Merci

English: See you tomorrow
French:

# Few shot 2

You are an information extraction system.

Rules:
- Output must be valid JSON.
- No additional text.
- Do not explain the result.

Example 1
Input:
The Tesla Model 3 costs $38,990 and is an electric sedan.

GOOD answer:
{"product":"Tesla Model 3","category":"electric sedan","price":38990}

BAD answer:
The Tesla Model 3 is an electric sedan that costs $38,990.

Example 2
Input:
The Sony WH-1000XM5 headphones cost $399.

GOOD answer:
{"product":"Sony WH-1000XM5","category":"headphones","price":399}

BAD answer:
Sony WH-1000XM5 headphones cost $399.

Input:
The Apple Watch Series 9 costs $399.

Answer:

# Reflection loops
You must respond ONLY with valid JSON.

Task:
{question}

Output format:

{
  "answer": "Your initial answer to the question",
  "revision": {
    "critique": "Explain weaknesses, errors, or missing reasoning in the answer",
    "confidence": "low | medium | high"
  },
  "revised_answer": "Provide a corrected and improved answer"
}
