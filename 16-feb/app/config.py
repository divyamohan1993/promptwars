"""Application configuration loaded from environment variables.

Uses a frozen dataclass for immutable, type-safe settings with validation.
All Google Cloud service toggles default to disabled for safe local development.
"""

import os
import re
from dataclasses import dataclass

# Allowed BCP-47 language codes (subset used by Cloud Translate / TTS).
_LANGUAGE_RE = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")


def _parse_bool(value: str) -> bool:
    """Parse a boolean from an environment string, accepting common truthy values."""
    return value.strip().lower() in ("true", "1", "yes")


@dataclass(frozen=True)
class Settings:
    """Immutable application settings populated from environment variables."""

    app_title: str = "QuestForge: The Upside Down"
    app_version: str = "2.0.0"
    app_description: str = (
        "AI-Powered Interactive Adventure Game inspired by Stranger Things, "
        "powered by Google Gemini"
    )
    allowed_origins: tuple = ("*",)

    # Google Cloud credentials
    google_api_key: str = ""
    gcp_project_id: str = ""

    # Firestore
    firestore_collection: str = "games"
    enable_firestore: bool = False

    # Optional Google Cloud services
    enable_tts: bool = False
    enable_translate: bool = False
    enable_storage: bool = False
    enable_imagen: bool = False

    # Cloud Storage
    gcs_bucket_name: str = ""

    # Internationalisation
    default_language: str = "en"

    # Rate limiting
    rate_limit_per_minute: int = 60

    # Server
    port: int = 8080
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        """Validate settings after initialisation."""
        if self.rate_limit_per_minute < 1:
            object.__setattr__(self, "rate_limit_per_minute", 1)
        if not _LANGUAGE_RE.match(self.default_language):
            object.__setattr__(self, "default_language", "en")
        if self.port < 1 or self.port > 65535:
            object.__setattr__(self, "port", 8080)

    @classmethod
    def load(cls) -> "Settings":
        """Create a Settings instance from the current environment variables."""
        return cls(
            google_api_key=os.environ.get("GOOGLE_API_KEY", ""),
            gcp_project_id=os.environ.get("GCP_PROJECT_ID", ""),
            firestore_collection=os.environ.get("FIRESTORE_COLLECTION", "games"),
            enable_firestore=_parse_bool(os.environ.get("ENABLE_FIRESTORE", "false")),
            enable_tts=_parse_bool(os.environ.get("ENABLE_TTS", "false")),
            enable_translate=_parse_bool(os.environ.get("ENABLE_TRANSLATE", "false")),
            enable_storage=_parse_bool(os.environ.get("ENABLE_STORAGE", "false")),
            enable_imagen=_parse_bool(os.environ.get("ENABLE_IMAGEN", "false")),
            gcs_bucket_name=os.environ.get("GCS_BUCKET_NAME", ""),
            default_language=os.environ.get("DEFAULT_LANGUAGE", "en"),
            rate_limit_per_minute=int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60")),
            port=int(os.environ.get("PORT", "8080")),
            log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        )


settings = Settings.load()
