import os
from dotenv import load_dotenv

# Do not override existing env vars — Docker Compose / K8s must win over a local .env file.
load_dotenv(override=False)

class Config:
    # Model APIs
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")

    # Local Ollama
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_SRD_MODEL = os.getenv("OLLAMA_SRD_MODEL", "llama3")
    OLLAMA_JUDGE_MODEL = os.getenv("OLLAMA_JUDGE_MODEL", "llama3")
    OLLAMA_ROUTING_MODEL = os.getenv("OLLAMA_ROUTING_MODEL", "llama3")

    # DB Config
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./compliance_middleware.db")

    # App Settings
    DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "t")

config = Config()
