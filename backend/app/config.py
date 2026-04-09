from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash-preview-05-20"
    GEMINI_MAX_REQUESTS_PER_SECOND: float = 2.0
    GEMINI_MAX_CONCURRENT_REQUESTS: int = 1
    GEMINI_MOCK_MODE: bool = False
    STORAGE_BASE_PATH: str = "./data/jobs"
    DATABASE_URL: str = "sqlite:///./loss_run.db"
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        origins: list[str] = []
        for origin in self.CORS_ORIGINS.split(","):
            cleaned = origin.strip().rstrip("/")
            if cleaned:
                origins.append(cleaned)
        return origins


settings = Settings()
