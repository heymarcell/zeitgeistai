"""
Zeitgeist Engine Configuration

Centralized configuration management using pydantic-settings.
Loads from environment variables and .env file.
"""

from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # =========================================================================
    # Google Cloud (BigQuery)
    # =========================================================================
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    GDELT_LOOKBACK_HOURS: int = 4
    GDELT_MAX_ARTICLES: int = 5000
    
    # =========================================================================
    # Qdrant Vector Database
    # =========================================================================
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION: str = "zeitgeist_articles"
    
    # =========================================================================
    # LLM Configuration - Best Models per Spec
    # =========================================================================
    # Extraction (high-volume, cheap)
    GEMINI_API_KEY: str = ""  # Required for generation
    GEMINI_MODEL_EXTRACTION: str = "gemini-2.5-flash"  # Entity/claim extraction
    GEMINI_MODEL_SUMMARIZATION: str = "gemini-3-pro"   # Article summarization
    
    # Synthesis (best quality)
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL_SYNTHESIS: str = "claude-opus-4.5"    # Narrative synthesis
    CLAUDE_MODEL_ILLUSTRATION: str = "claude-sonnet-4.5"  # Illustration concepts
    
    # Verification (adversarial judge)
    OPENAI_API_KEY: str = ""
    GPT_MODEL_VERIFICATION: str = "gpt-5.2"            # Fact verification
    
    # =========================================================================
    # Bluesky Configuration
    # =========================================================================
    BLUESKY_HANDLE: str = ""
    BLUESKY_APP_PASSWORD: str = ""
    BLUESKY_SAMPLE_SIZE: int = 200
    
    # =========================================================================
    # Mastodon Configuration
    # =========================================================================
    MASTODON_INSTANCE: str = "https://mastodon.social"
    MASTODON_ACCESS_TOKEN: str = ""
    MASTODON_SAMPLE_SIZE: int = 100
    
    # =========================================================================
    # Processing Configuration
    # =========================================================================
    MIN_CLUSTER_SIZE: int = 5
    MIN_SAMPLES: int = 2
    UMAP_N_COMPONENTS: int = 50
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    
    # =========================================================================
    # Generation Configuration
    # =========================================================================
    FAITHFULNESS_THRESHOLD: float = 0.95
    MAX_ARTICLES_PER_CLUSTER: int = 50
    DIGEST_MAX_WORDS: int = 500
    
    # =========================================================================
    # Output Configuration
    # =========================================================================
    OUTPUT_DIR: str = "./output"
    ENABLE_BLUESKY_POST: bool = True
    ENABLE_MASTODON_POST: bool = True
    
    # =========================================================================
    # Scheduling
    # =========================================================================
    DIGEST_FREQUENCY_HOURS: int = 4
    
    # =========================================================================
    # Feature Flags
    # =========================================================================
    USE_ASYNC_COLLECTORS: bool = True  # Use async collectors for parallel fetching
    
    # =========================================================================
    # Alerting
    # =========================================================================
    DISCORD_WEBHOOK_URL: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience export
settings = get_settings()
