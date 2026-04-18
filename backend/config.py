from pydantic_settings import BaseSettings
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env de la raiz del proyecto al environment del proceso
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=True)


class Settings(BaseSettings):
    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    OLLAMA_VISION_MODEL: str = "llava"

    # Paths
    OBSIDIAN_VAULT: str = r"C:\Users\Emmanuel\Documents\CerebroEmmanuel"
    PROJECT_ROOT: str = str(Path(__file__).parent.parent)

    # Whisper
    WHISPER_MODEL: str = "base"
    WHISPER_LANGUAGE: str = "es"

    # APIs externas (opcionales, free tiers)
    WEATHER_API_KEY: str = ""  # OpenWeatherMap free
    WEATHER_CITY: str = "Queretaro"
    WEATHER_COUNTRY: str = "MX"

    # Shopify
    SHOPIFY_STORE: str = "grop-7604.myshopify.com"
    SHOPIFY_ACCESS_TOKEN: str = ""

    # Free AI (gratis, mejor que Ollama)
    FREE_AI_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = ""
    CEREBRAS_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    FREE_AI_MODEL: str = ""

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8766

    # Camera
    CAMERA_INDEX: int = 0

    class Config:
        env_file = [".env", str(Path(__file__).parent.parent / ".env")]
        env_file_encoding = "utf-8"


settings = Settings()
