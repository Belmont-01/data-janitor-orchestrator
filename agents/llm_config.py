import os
from crewai import LLM
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# Single shared LLM instance for all agents
llm = LLM(
    model="gemini/gemini-3-flash-preview",
    api_key=os.getenv("GOOGLE_API_KEY"),
    max_rpm=10,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)
