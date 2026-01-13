"""
Application settings with environment variable support
"""
import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field


def get_data_dir() -> Path:
    """Get the application data directory - use XDG standard for all Unix-like systems"""
    if os.name == "nt":  # Windows
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:  # macOS and Linux - use XDG standard
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

    data_dir = base / "Nemori"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


class Settings(BaseSettings):
    """Application settings"""

    # Server
    host: str = Field(default="127.0.0.1", description="Server host")
    port: int = Field(default=21978, description="Server port")

    # Paths
    data_dir: Path = Field(default_factory=get_data_dir, description="Data directory")

    # Database
    db_name: str = Field(default="nemori.db", description="SQLite database name")

    # ChromaDB
    chroma_collection: str = Field(default="nemori_memories", description="ChromaDB collection name")

    # LLM Settings
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI API base URL"
    )
    default_model: str = Field(default="gpt-4o-mini", description="Default chat model")
    embedding_model: str = Field(
        default="google/gemini-embedding-001",
        description="Embedding model"
    )
    embedding_dimension: int = Field(default=0, description="Embedding dimension (0 = auto-adapt to model)")

    # Screenshot Settings
    capture_interval_ms: int = Field(default=10000, description="Screenshot interval in ms")
    similarity_threshold: float = Field(default=0.95, description="Image similarity threshold")

    # Memory Settings
    batch_size: int = Field(default=20, description="Memory batch processing size")
    max_local_storage_mb: int = Field(default=500, description="Max local storage in MB")

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.db_name

    @property
    def chroma_path(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def screenshots_path(self) -> Path:
        path = self.data_dir / "screenshots"
        path.mkdir(parents=True, exist_ok=True)
        return path

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
