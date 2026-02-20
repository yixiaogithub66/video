from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "dev")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./runtime/platform.db",
    )
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    ops_port: int = int(os.getenv("OPS_PORT", "8080"))
    local_api_token: str = os.getenv("LOCAL_API_TOKEN", "dev-token")

    temporal_address: str = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    temporal_namespace: str = os.getenv("TEMPORAL_NAMESPACE", "default")
    temporal_task_queue: str = os.getenv("TEMPORAL_TASK_QUEUE", "video-edit-task-queue")

    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "case_embeddings")

    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    minio_access_key: str = os.getenv("MINIO_ACCESS_KEY", "minio")
    minio_secret_key: str = os.getenv("MINIO_SECRET_KEY", "minio123")
    minio_secure: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"

    raw_retention_days: int = int(os.getenv("RAW_RETENTION_DAYS", "30"))
    intermediate_retention_days: int = int(os.getenv("INTERMEDIATE_RETENTION_DAYS", "7"))
    output_retention_days: int = int(os.getenv("OUTPUT_RETENTION_DAYS", "180"))

    qa_threshold: float = float(os.getenv("QA_THRESHOLD", "0.82"))
    qa_random_review_ratio: float = float(os.getenv("QA_RANDOM_REVIEW_RATIO", "0.2"))
    max_iterations: int = int(os.getenv("MAX_ITERATIONS", "3"))

    models_dir: str = os.getenv("MODELS_DIR", "models")
    artifacts_dir: str = os.getenv("ARTIFACTS_DIR", "runtime/artifacts")

    # Model runtime strategy:
    # - "api": use remote inference APIs, do not download local model bundles by default.
    # - "local": use local model bundles.
    model_runtime_mode: str = os.getenv("MODEL_RUNTIME_MODE", "api").lower()
    model_api_provider: str = os.getenv("MODEL_API_PROVIDER", "openai_compatible")
    model_api_base_url: str | None = os.getenv("MODEL_API_BASE_URL")
    model_api_key: str | None = os.getenv("MODEL_API_KEY")
    allow_local_model_install: bool = os.getenv("ALLOW_LOCAL_MODEL_INSTALL", "false").lower() == "true"
    enable_fallback_orchestrator: bool = os.getenv("ENABLE_FALLBACK_ORCHESTRATOR", "true").lower() == "true"
    remote_model_timeout_seconds: float = float(os.getenv("REMOTE_MODEL_TIMEOUT_SECONDS", "45"))
    remote_model_max_retries: int = int(os.getenv("REMOTE_MODEL_MAX_RETRIES", "2"))
    allow_api_stub_fallback: bool = os.getenv("ALLOW_API_STUB_FALLBACK", "true").lower() == "true"
    callback_timeout_seconds: float = float(os.getenv("CALLBACK_TIMEOUT_SECONDS", "8"))
    callback_max_retries: int = int(os.getenv("CALLBACK_MAX_RETRIES", "2"))
    safety_admin_token: str | None = os.getenv("SAFETY_ADMIN_TOKEN")
    safety_override_allow_rules_raw: str = os.getenv(
        "SAFETY_OVERRIDE_ALLOW_RULES",
        "",
    )
    high_risk_review_keywords_raw: str = os.getenv(
        "HIGH_RISK_REVIEW_KEYWORDS",
        "public figure,politician,minor,medical,financial,news",
    )

    def api_tokens(self) -> list[str]:
        raw = self.local_api_token or ""
        return [token.strip() for token in raw.split(",") if token.strip()]

    def safety_override_allow_rules(self) -> set[str]:
        raw = self.safety_override_allow_rules_raw or ""
        return {token.strip() for token in raw.split(",") if token.strip()}

    def high_risk_review_keywords(self) -> list[str]:
        raw = self.high_risk_review_keywords_raw or ""
        return [token.strip().lower() for token in raw.split(",") if token.strip()]


settings = Settings()
