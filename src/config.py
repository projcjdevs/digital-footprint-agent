import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')

    GEMINI_RPM_LIMIT = int(os.getenv('GEMINI_RPM_LIMIT', 15))
    GROQ_RPM_LIMIT = int(os.getenv('GROQ_RPM_LIMIT', 30))

    GEMINI_MODEL = "gemini-2.5-flash"
    GROQ_MODEL = "llama-3.3-70b-versatile"

    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/models"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1/chat/completions"

    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')

    DDG_MAX_RESULTS = 8

    PORT = int(os.getenv('PORT', 3001))
