import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_title: str = "QuestForge"
    app_version: str = "1.0.0"
    app_description: str = "AI-Powered Text Adventure Game powered by Google Gemini"
    allowed_origins: tuple = ("*",)
    google_api_key: str = ""
    gcp_project_id: str = ""
    firestore_collection: str = "games"
    enable_firestore: bool = False
    enable_tts: bool = False
    rate_limit_per_minute: int = 60
    port: int = 8080
    log_level: str = "INFO"

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            google_api_key=os.environ.get("GOOGLE_API_KEY", ""),
            gcp_project_id=os.environ.get("GCP_PROJECT_ID", ""),
            firestore_collection=os.environ.get("FIRESTORE_COLLECTION", "games"),
            enable_firestore=os.environ.get("ENABLE_FIRESTORE", "false").lower() == "true",
            enable_tts=os.environ.get("ENABLE_TTS", "false").lower() == "true",
            rate_limit_per_minute=int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60")),
            port=int(os.environ.get("PORT", "8080")),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
        )


settings = Settings.load()
