import os
import google.generativeai as genai
from dotenv import load_dotenv, find_dotenv

# 1. Load your .env file
load_dotenv(find_dotenv())
api_key = os.getenv("GOOGLE_API_KEY")

# 2. Configure the Google SDK
genai.configure(api_key=api_key)

# 3. List the models
print("--- AVAILABLE MODELS ---")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"Model Name: {m.name}")
except Exception as e:
    print(f"Error connecting to Google: {e}")