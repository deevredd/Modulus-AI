import os
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

class BaseAgent:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Missing GROQ_API_KEY. Set it in your environment or .env file."
            )
        # Llama 3.3 70B is incredible for reasoning and is free on Groq
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0,
            groq_api_key=api_key
        )

    def invoke_llm(self, prompt: str):
        return self.llm.invoke(prompt).content