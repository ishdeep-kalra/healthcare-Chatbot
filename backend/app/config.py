import json
import logging
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("healthcare-chatbot")

# Default allowed origins for local development only.
# In production (Render), set CORS_ORIGINS env var to your Vercel URL(s).
_DEFAULT_DEV_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:3000",
]


class Settings(BaseSettings):
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "info"
    CORS_ORIGINS: Union[str, List[str]] = _DEFAULT_DEV_ORIGINS
    GEMINI_API_KEY: str = ""
    LLM_PROVIDER: str = "gemini"
    OLLAMA_MODEL: str = "llama3.2"
    CHROMA_PERSIST_DIR: str = "../data/chromadb"

    # Configure Pydantic to read from backend/.env file
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            # Support JSON array: '["https://example.vercel.app"]'
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            # Support comma-separated list: "https://a.com,https://b.com"
            return [x.strip() for x in v.split(",") if x.strip()]
        return v


# Instantiate global settings
settings = Settings()
