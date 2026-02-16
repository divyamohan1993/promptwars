from app.config import Settings


class TestSettings:
    def test_default_values(self):
        s = Settings()
        assert s.app_title == "QuestForge"
        assert s.enable_firestore is False
        assert s.enable_tts is False
        assert s.rate_limit_per_minute == 60

    def test_load_from_env(self, monkeypatch):
        monkeypatch.setenv("ENABLE_FIRESTORE", "true")
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "30")
        s = Settings.load()
        assert s.enable_firestore is True
        assert s.rate_limit_per_minute == 30
