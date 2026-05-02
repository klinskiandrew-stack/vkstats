import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    vk_ads_client_id: str
    vk_ads_client_secret: str
    vk_ads_agency_client_name: str
    telegram_bot_token: str
    telegram_chat_id: str
    timezone: str = "Europe/Moscow"
    api_base_url: str = "https://ads.vk.com/api/v2"
    currency_symbol: str = "₽"


def get_settings() -> Settings:
    settings = Settings(
        vk_ads_client_id=os.getenv("VK_ADS_CLIENT_ID", "").strip(),
        vk_ads_client_secret=os.getenv("VK_ADS_CLIENT_SECRET", "").strip(),
        vk_ads_agency_client_name=os.getenv("VK_ADS_AGENCY_CLIENT_NAME", "").strip(),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        timezone=os.getenv("TIMEZONE", "Europe/Moscow").strip(),
        api_base_url=os.getenv("VK_ADS_API_BASE_URL", "https://ads.vk.com/api/v2").strip().rstrip("/"),
        currency_symbol=os.getenv("CURRENCY_SYMBOL", "₽").strip(),
    )

    missing = []
    if not settings.vk_ads_client_id:
        missing.append("VK_ADS_CLIENT_ID")
    if not settings.vk_ads_client_secret:
        missing.append("VK_ADS_CLIENT_SECRET")
    if not settings.vk_ads_agency_client_name:
        missing.append("VK_ADS_AGENCY_CLIENT_NAME")
    if not settings.telegram_bot_token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not settings.telegram_chat_id:
        missing.append("TELEGRAM_CHAT_ID")

    if missing:
        raise RuntimeError("Не заполнены переменные окружения: " + ", ".join(missing))

    return settings
