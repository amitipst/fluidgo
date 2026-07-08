from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    OLLAMA_URL: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "phi3:mini"
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CORS_ORIGINS: str = "http://localhost,http://localhost:3000"
    ENVIRONMENT: str = "development"

    # ── Email (password reset) ────────────────────────────────────────────────
    # Microsoft 365 SMTP. Provision a no-reply mailbox in the wepsol.com tenant
    # and an app password / SMTP AUTH cred, then set these in .env. Until set,
    # reset emails are logged to the backend console instead of sent (dev-safe).
    SMTP_HOST:      str = "smtp.office365.com"
    SMTP_PORT:      int = 587
    SMTP_USER:      str = ""          # e.g. fluidgo-noreply@wepsol.com
    SMTP_PASSWORD:  str = ""          # app password from M365
    SMTP_FROM:      str = "fluidGo <fluidgo-noreply@wepsol.com>"
    APP_BASE_URL:   str = "https://fluidgo.wepsol.com"   # for building reset links
    RESET_TOKEN_TTL_MINUTES: int = 30

    @property
    def email_configured(self) -> bool:
        return bool(self.SMTP_USER and self.SMTP_PASSWORD)

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
