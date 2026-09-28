import google.generativeai as genai

from practice.config import GEMINI_API_KEY

print("Program Started")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is missing. Add it to your .env file.")

genai.configure(api_key=GEMINI_API_KEY)

print("API Configured")

for model in genai.list_models():
    print(model.name)

print("Program Finished")
