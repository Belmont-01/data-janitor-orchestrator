import os
from crewai import LLM
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise EnvironmentError(
        "GOOGLE_API_KEY is not set. "
        "Add it to your .env file locally or to Render's environment variables."
    )

# Single shared LLM instance for all agents
llm = LLM(
    model="gemini/gemini-2.5-flash",
    api_key=api_key,
    max_rpm=1,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    timeout=120
)
