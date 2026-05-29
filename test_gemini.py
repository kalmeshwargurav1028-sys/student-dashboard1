import google.generativeai as genai
import os

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-2.5-flash')
try:
    response = model.generate_content("hello")
    print(response.text)
except Exception as e:
    print("Error:", e)
