from app.config import Settings


class TestSettings:
    def test_default_values(self):
        s = Settings()
        assert s.app_title == "QuestForge: The Upside Down"
        assert s.app_version == "2.0.0"
        assert s.enable_firestore is False
        assert s.enable_tts is False
        assert s.enable_translate is False
        assert s.enable_storage is False
        assert s.enable_imagen is False
        assert s.gcs_bucket_name == ""
        assert s.default_language == "en"
        assert s.rate_limit_per_minute == 60

    def test_load_from_env(self, monkeypatch):
        monkeypatch.setenv("ENABLE_FIRESTORE", "true")
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "30")
        s = Settings.load()
        assert s.enable_firestore is True
        assert s.rate_limit_per_minute == 30

    def test_new_service_toggles_from_env(self, monkeypatch):
        monkeypatch.setenv("ENABLE_TRANSLATE", "true")
        monkeypatch.setenv("ENABLE_STORAGE", "true")
        monkeypatch.setenv("ENABLE_IMAGEN", "true")
        monkeypatch.setenv("GCS_BUCKET_NAME", "my-bucket")
        monkeypatch.setenv("DEFAULT_LANGUAGE", "es")
        s = Settings.load()
        assert s.enable_translate is True
        assert s.enable_storage is True
        assert s.enable_imagen is True
        assert s.gcs_bucket_name == "my-bucket"
        assert s.default_language == "es"

    def test_rate_limit_clamped_to_minimum(self):
        s = Settings(rate_limit_per_minute=0)
        assert s.rate_limit_per_minute == 1

    def test_invalid_language_falls_back_to_en(self):
        s = Settings(default_language="INVALID")
        assert s.default_language == "en"

    def test_invalid_port_falls_back_to_default(self):
        s = Settings(port=99999)
        assert s.port == 8080

    def test_parse_bool_accepts_yes_and_1(self, monkeypatch):
        monkeypatch.setenv("ENABLE_TTS", "1")
        monkeypatch.setenv("ENABLE_STORAGE", "yes")
        s = Settings.load()
        assert s.enable_tts is True
        assert s.enable_storage is True

    def test_log_level_normalised_to_uppercase(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "debug")
        s = Settings.load()
        assert s.log_level == "DEBUG"
