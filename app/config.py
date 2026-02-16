import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_title: str = "QuestForge"
    app_version: str = "1.0.0"
    app_description: str = "AI-Powered Text Adventure Game powered by Google Gemini"
    allowed_origins: tuple = ("*",)
    google_api_key: str = ""

    @classmethod
    def load(cls) -> "Settings":
        api_key = os.environ.get("GOOGLE_API_KEY", "")
        return cls(google_api_key=api_key)


settings = Settings.load()
