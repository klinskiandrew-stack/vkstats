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
    telegram_admin_ids: set[int]
    timezone: str = "Europe/Moscow"
    api_base_url: str = "https://ads.vk.com/api/v2"
    currency_symbol: str = "₽"
    token_store_path: str = "tokens.json"
    enable_ai_summary: bool = False
    ai_api_key: str = ""
    ai_base_url: str = ""
    ai_model: str = ""
    ai_timeout_seconds: int = 30


def _parse_admin_ids(value: str) -> set[int]:
    result: set[int] = set()
    for item in value.replace(";", ",").split(","):
        item = item.strip()
        if not item:
            continue
        try:
            result.add(int(item))
        except ValueError:
            continue
    return result


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on", "да"}


def _parse_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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
        telegram_admin_ids=_parse_admin_ids(os.getenv("TELEGRAM_ADMIN_IDS", "5245218509")),
        timezone=os.getenv("TIMEZONE", "Europe/Moscow").strip(),
        api_base_url=os.getenv("VK_ADS_API_BASE_URL", "https://ads.vk.com/api/v2").strip().rstrip("/"),
        currency_symbol=os.getenv("CURRENCY_SYMBOL", "₽").strip(),
        token_store_path=os.getenv("TOKEN_STORE_PATH", "tokens.json").strip(),
        enable_ai_summary=_parse_bool(os.getenv("ENABLE_AI_SUMMARY", "false")),
        ai_api_key=os.getenv("AI_API_KEY", "").strip(),
        ai_base_url=os.getenv("AI_BASE_URL", "").strip().rstrip("/"),
        ai_model=os.getenv("AI_MODEL", "").strip(),
        ai_timeout_seconds=_parse_int(os.getenv("AI_TIMEOUT_SECONDS", "30"), 30),
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
    if settings.enable_ai_summary:
        if not settings.ai_api_key:
            missing.append("AI_API_KEY")
        if not settings.ai_base_url:
            missing.append("AI_BASE_URL")
        if not settings.ai_model:
            missing.append("AI_MODEL")

    if missing:
        raise RuntimeError("Не заполнены переменные окружения: " + ", ".join(missing))

    return settings
