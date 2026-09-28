import google.generativeai as genai
import re

from practice.config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel(
    "gemini-2.5-flash"
)


def clean_sql(text):

    match = re.search(
        r"(SELECT.*?;)",
        text,
        re.IGNORECASE | re.DOTALL
    )

    if match:
        return match.group(1).strip()

    return text.strip()


response = model.generate_content(
    "Convert to SQL: Show all sales"
)

print("\nRAW RESPONSE:")
print(response.text)

sql = clean_sql(
    response.text
)

print("\nEXTRACTED SQL:")
print(sql)