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
    # Product/brand name shown on exported documents (Minutes of Meeting
    # xlsx/pdf/docx) and similar customer-facing output. A named setting
    # rather than a literal string in the generator code — this app is
    # internal-only today, but Amit's call (2026-08-04) is to keep the
    # architecture open for a future multi-tenant version without a
    # rearchitecture; this is one of the near-zero-cost things that buys,
    # not a build-now for multi-tenancy itself.
    APP_NAME: str = "fluidGo"

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

    # ── Feedback → Jira (optional) ────────────────────────────────────────────
    # In-app "Report an issue/idea" capture always works and always alerts
    # super_admin/ceo by email (reuses the SMTP config above — no separate
    # setup). Filing the matching Jira issue is a bonus on top: if these are
    # left blank, feedback still saves and still alerts, it just won't have a
    # Jira link. Get JIRA_API_TOKEN from
    # https://id.atlassian.com/manage-profile/security/api-tokens (free Jira
    # Cloud account, up to 10 users, no cost).
    JIRA_BASE_URL:    str = ""   # e.g. https://yourorg.atlassian.net
    JIRA_EMAIL:       str = ""   # Jira account email used to authenticate
    JIRA_API_TOKEN:   str = ""
    JIRA_PROJECT_KEY: str = ""   # e.g. "FGO"
    JIRA_ISSUE_TYPE:  str = "Task"

    @property
    def jira_configured(self) -> bool:
        return bool(self.JIRA_BASE_URL and self.JIRA_EMAIL and self.JIRA_API_TOKEN and self.JIRA_PROJECT_KEY)

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
