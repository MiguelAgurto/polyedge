from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="POLYEDGE_")

    discovery_limit: int = Field(default=100, ge=1, le=10000)
    page_size: int = Field(default=50, ge=1, le=100)
    request_timeout: float = Field(default=10, gt=0)
    max_retries: int = Field(default=3, ge=0, le=8)
    storage: str = Field(default="local", pattern="^(local|supabase)$")
    data_file: Path = Field(default=Path(__file__).resolve().parents[3] / "data" / "polyedge.json")
    supabase_url: str | None = Field(default=None, validation_alias="SUPABASE_URL")
    supabase_service_role_key: str | None = Field(default=None, validation_alias="SUPABASE_SERVICE_ROLE_KEY")

    gamma_url: str = "https://gamma-api.polymarket.com"
    clob_url: str = "https://clob.polymarket.com"
