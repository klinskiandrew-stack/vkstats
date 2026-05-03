import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    vk_ads_client_id: str
    vk_ads_client_secret: str
    vk_ads_agency_access_token: str
    vk_ads_agency_refresh_token: str
    vk_ads_agency_expires_at: str
    vk_ads_access_token: str
    telegram_bot_token: str
    telegram_chat_id: str
    telegram_proxy_url: str
    timezone: str = "Europe/Moscow"
    api_base_url: str = "https://ads.vk.com/api/v2"
    currency_symbol: str = "₽"
    token_store_path: str = "tokens.json"


def get_settings() -> Settings:
    settings = Settings(
        vk_ads_client_id=os.getenv("VK_ADS_CLIENT_ID", "").strip(),
        vk_ads_client_secret=os.getenv("VK_ADS_CLIENT_SECRET", "").strip(),
        vk_ads_agency_access_token=os.getenv("VK_ADS_AGENCY_ACCESS_TOKEN", "").strip(),
        vk_ads_agency_refresh_token=os.getenv("VK_ADS_AGENCY_REFRESH_TOKEN", "").strip(),
        vk_ads_agency_expires_at=os.getenv("VK_ADS_AGENCY_EXPIRES_AT", "").strip(),
        vk_ads_access_token=os.getenv("VK_ADS_ACCESS_TOKEN", "").strip(),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        telegram_proxy_url=os.getenv("TELEGRAM_PROXY_URL", "").strip(),
        timezone=os.getenv("TIMEZONE", "Europe/Moscow").strip(),
        api_base_url=os.getenv("VK_ADS_API_BASE_URL", "https://ads.vk.com/api/v2").strip().rstrip("/"),
        currency_symbol=os.getenv("CURRENCY_SYMBOL", "₽").strip(),
        token_store_path=os.getenv("TOKEN_STORE_PATH", "tokens.json").strip(),
    )

    missing = []
    if not settings.vk_ads_client_id:
        missing.append("VK_ADS_CLIENT_ID")
    if not settings.vk_ads_client_secret:
        missing.append("VK_ADS_CLIENT_SECRET")
    if not settings.vk_ads_agency_access_token and not settings.vk_ads_access_token:
        missing.append("VK_ADS_AGENCY_ACCESS_TOKEN или VK_ADS_ACCESS_TOKEN")
    if not settings.telegram_bot_token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not settings.telegram_chat_id:
        missing.append("TELEGRAM_CHAT_ID")

    if missing:
        raise RuntimeError("Не заполнены переменные окружения: " + ", ".join(missing))

    return settings
