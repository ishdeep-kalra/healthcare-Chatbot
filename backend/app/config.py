import json
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "info"
    CORS_ORIGINS: Union[str, List[str]] = ["*"]
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
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [x.strip() for x in v.split(",")]
        return v

# Instantiate global settings
settings = Settings()
