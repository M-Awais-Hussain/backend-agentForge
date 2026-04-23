import os
from langchain_groq import ChatGroq
from dotenv import load_dotenv

# Load environment variables from the .env file in the same directory as this file's parent
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=dotenv_path)

def get_llm(model="llama-3.1-8b-instant"):
    return ChatGroq(
        model=model,
        temperature=0.1,
        api_key=os.getenv("GROQ_API_KEY"),
    )
