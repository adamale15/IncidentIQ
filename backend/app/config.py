"""
Application configuration using Pydantic settings.
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://iip_user:iip_password@localhost:5432/incidentiq"
    
    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION_NAME: str = "incidents"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # Google Gemini
    GEMINI_API_KEY: str
    GEMINI_EMBEDDING_MODEL: str = "models/text-embedding-004"
    GEMINI_FLASH_MODEL: str = "models/gemini-1.5-flash"
    GEMINI_PRO_MODEL: str = "models/gemini-1.5-pro"
    
    # Cohere (optional)
    COHERE_API_KEY: str | None = None
    
    # Application
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "your-secret-key-change-in-production"
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    # Retrieval
    DENSE_WEIGHT: float = 0.7
    SPARSE_WEIGHT: float = 0.3
    TOP_K_RETRIEVAL: int = 20
    TOP_K_RERANK: int = 5
    CONTEXT_MAX_TOKENS: int = 8000
    
    # Evaluation
    EVAL_GOLDEN_DATASET_PATH: str = "/data/eval/golden_dataset.json"
    EVAL_REGRESSION_THRESHOLD: float = 0.05  # 5% drop triggers warning
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
