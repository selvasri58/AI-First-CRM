import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://hcp_user:hcp_password@localhost:5432/hcp_crm",
    )
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

    # See .env.example for why this defaults away from the spec's
    # `gemma2-9b-it` (deprecated by Groq on 2025-10-08).
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

    FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")


settings = Settings()
