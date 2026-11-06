import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

def get_llm():
    return ChatOpenAI(
        model=os.getenv("MODELSCOPE_MODEL_ID", "deepseek-flash"),
        api_key=os.getenv("MODELSCOPE_API_KEY", "your-api-key"),
        base_url=os.getenv("MODELSCOPE_BASE_URL", "https://api.deepseek.com"),
        temperature=0.7,
    )