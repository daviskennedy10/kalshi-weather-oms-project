from enum import StrEnum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingMode(StrEnum):
    PAPER = "paper"
    LIVE = "live"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://weather:weather@localhost:5432/weather_oms"
    trading_mode: TradingMode = TradingMode.PAPER
    kalshi_env: str = "demo"
    kalshi_key_id: str | None = None
    kalshi_private_key_path: str | None = None
    market_tickers: str = ""
    forecast_refresh_seconds: int = Field(default=900, ge=60)
    max_order_risk_cents: int = Field(default=500, ge=1)

    @property
    def tickers(self) -> list[str]:
        return [item.strip() for item in self.market_tickers.split(",") if item.strip()]

    @property
    def kalshi_ws_url(self) -> str:
        if self.kalshi_env == "prod":
            return "wss://external-api-ws.kalshi.com/trade-api/ws/v2"
        return "wss://external-api-ws.demo.kalshi.co/trade-api/ws/v2"

