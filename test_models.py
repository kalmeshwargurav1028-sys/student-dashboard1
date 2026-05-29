import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)

models_to_test = [
    'gemini-flash-lite-latest',
    'gemini-2.5-flash',
    'gemini-2.5-flash-lite'
]

for m in models_to_test:
    try:
        model = genai.GenerativeModel(m)
        response = model.generate_content("Hello")
        print(f"{m}: Success! {response.text}")
    except Exception as e:
        print(f"{m}: Error: {e}")
