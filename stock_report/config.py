from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseModel):
    api_base_url: str = Field(
        default="https://api.finmindtrade.com/api/v4/data",
        description="Base URL for FinMind API requests.",
    )
    timeout: float = Field(default=30.0, ge=0.1, description="HTTP request timeout in seconds.")
    retry: int = Field(default=3, ge=0, description="Retry count for transient upstream failures.")


class GenerationSettings(BaseModel):
    model_config = {"protected_namespaces": ()}

    model_name: str = Field(default="claude-3-5-sonnet-latest", description="LLM model name.")
    max_tokens: int = Field(default=2048, ge=1, description="Maximum output tokens for report generation.")
    temperature: float = Field(default=0.2, ge=0.0, le=1.0, description="Sampling temperature.")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    finmind_token: str | None = Field(default=None, alias="FINMIND_TOKEN")
    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    api_key: str | None = Field(default=None, alias="API_KEY")
    deepseek_api_key: str | None = Field(default=None, alias="DEEPSEEK_API_KEY")
    deepseek_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_MODEL")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash", alias="GEMINI_MODEL")
    debug: bool = Field(default=False, alias="DEBUG")
    service: ServiceSettings = Field(default_factory=ServiceSettings)
    generation: GenerationSettings = Field(default_factory=GenerationSettings)


settings = Settings()
