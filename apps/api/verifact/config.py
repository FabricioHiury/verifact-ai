from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", extra="ignore", hide_input_in_errors=True
    )
    app_name: str = "Verifact AI"
    app_env: Literal["development", "test"] = "development"
    app_debug: bool = False
    app_host: Literal["127.0.0.1"] = "127.0.0.1"
    app_port: int = Field(8000, ge=1024, le=65535)
    web_port: int = Field(3000, ge=1024, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    database_url: SecretStr = SecretStr("postgresql+psycopg://localhost/verifact")
    celery_broker_url: SecretStr = SecretStr("redis://localhost:6379/0")
    celery_result_backend: SecretStr = SecretStr("redis://localhost:6379/1")
    celery_worker_concurrency: int = Field(1, ge=1, le=1)
    storage_backend: Literal["filesystem", "minio"] = "minio"
    local_storage_path: Path = ROOT / "data/storage"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: SecretStr = SecretStr("")
    minio_secret_key: SecretStr = SecretStr("")
    minio_bucket: str = "verifact-media"
    minio_use_ssl: bool = False
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:4b"
    ollama_fallback_model: str = "qwen3:1.7b"
    ollama_context_length: int = Field(4096, ge=1024, le=4096)
    ollama_max_concurrent_requests: int = Field(1, ge=1, le=1)
    whisper_provider: Literal["mlx", "faster-whisper"] = "mlx"
    whisper_model: str = "mlx-community/whisper-small-mlx"
    whisper_fallback_model: str = "mlx-community/whisper-base-mlx"
    whisper_language: Literal["pt"] = "pt"
    whisper_chunk_seconds: int = Field(180, ge=10, le=180)
    whisper_chunk_overlap_seconds: int = Field(5, ge=0)
    whisper_concurrency: int = Field(1, ge=1, le=1)
    diarization_enabled: bool = True
    diarization_provider: Literal["pyannote"] = "pyannote"
    diarization_model: str = "pyannote/speaker-diarization-community-1"
    diarization_concurrency: int = Field(1, ge=1, le=1)
    huggingface_token: SecretStr = SecretStr("")
    crewai_sequential_execution: bool = True
    crewai_max_parallel_agents: int = Field(1, ge=1, le=1)
    searxng_base_url: str = "http://localhost:8080"
    search_engine: str = "duckduckgo"
    search_language: str = "pt-BR"
    search_max_results: int = Field(3, ge=1, le=10)
    search_max_concurrent_requests: int = Field(2, ge=1, le=2)
    search_request_timeout: int = Field(30, ge=1, le=120)
    research_queries_per_claim: int = Field(3, ge=2, le=5)
    max_claims_per_batch: int = Field(5, ge=1, le=10)
    max_llm_calls: int = Field(200, ge=1)
    llm_output_tokens: int = Field(768, ge=128, le=1024)
    max_retries: int = Field(2, ge=0, le=5)
    stage_timeout: int = Field(900, ge=10)
    max_concurrent_analyses: int = Field(1, ge=1, le=1)
    media_processing_concurrency: int = Field(1, ge=1, le=1)
    media_max_size_mb: int = Field(0, ge=0)
    storage_budget_mb: int = Field(10240, ge=100)
    min_free_disk_mb: int = Field(1024, ge=0)
    media_temp_dir: Path = ROOT / "data/tmp"
    social_download_enabled: bool = False
    media_download_timeout: int = Field(300, ge=10)
    source_max_bytes: int = Field(2_000_000, ge=1024, le=10_000_000)
    report_output_dir: Path = ROOT / "data/reports"
    pdf_enabled: bool = True
    next_public_api_url: str = "http://localhost:8000"
    resource_profile: Literal["apple_silicon_8gb"] = "apple_silicon_8gb"

    @model_validator(mode="after")
    def validate_profile(self) -> "Settings":
        if not self.crewai_sequential_execution:
            raise ValueError("Sequential CrewAI execution is mandatory")
        if self.whisper_chunk_overlap_seconds >= self.whisper_chunk_seconds:
            raise ValueError("Chunk overlap must be smaller than chunk duration")
        if self.llm_output_tokens >= self.ollama_context_length:
            raise ValueError("Reserve space for model input")
        for url in (self.ollama_base_url, self.searxng_base_url, self.next_public_api_url):
            parsed = urlsplit(url)
            if parsed.scheme != "http" or parsed.hostname not in ("localhost", "127.0.0.1"):
                raise ValueError("Internal services must use local HTTP endpoints")
        if self.storage_backend == "minio" and not self.minio_secret_key.get_secret_value():
            raise ValueError("MinIO credentials are required for the MinIO adapter")
        return self


@lru_cache
def settings() -> Settings:
    return Settings()
