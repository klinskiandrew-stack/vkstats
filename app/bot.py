from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.ai_summary import build_ai_summary
from app.extended_report import build_extended_report, collect_extended_report_data
from app.settings import Settings, get_settings
from app.telegram_sender import answer_callback_query, get_updates, send_long_telegram_message, send_telegram_message
from app.vk_ads import VkAdsApi

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

EXTENDED_REPORT_CALLBACK = "extended_report_yesterday"


def yesterday(settings: Settings):
    now = datetime.now(ZoneInfo(settings.timezone))
    return (now - timedelta(days=1)).date()


def keyboard() -> dict:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "📊 Расширенный отчёт за вчера",
                    "callback_data": EXTENDED_REPORT_CALLBACK,
                }
            ]
        ]
    }


def is_admin(settings: Settings, user_id: int | None) -> bool:
    return bool(user_id and user_id in settings.telegram_admin_ids)


def send_menu(settings: Settings, chat_id: str) -> None:
    send_telegram_message(
        settings.telegram_bot_token,
        chat_id,
        "Выбери действие:",
        settings.telegram_proxy_url,
        reply_markup=keyboard(),
    )


def build_and_send_extended_report(settings: Settings, chat_id: str) -> None:
    send_telegram_message(
        settings.telegram_bot_token,
        chat_id,
        "Собираю расширенный отчёт. Это может занять 1–2 минуты.",
        settings.telegram_proxy_url,
    )

    api = VkAdsApi(settings)
    report_date = yesterday(settings)
    data = collect_extended_report_data(api, report_date)

    ai_summary = ""
    try:
        ai_summary = build_ai_summary(settings, data)
    except Exception as exc:
        logging.exception("AI summary failed")
        ai_summary = f"ИИ-сводка временно не сформирована: {exc}"

    text = build_extended_report(data, settings.currency_symbol, ai_summary=ai_summary)
    send_long_telegram_message(
        settings.telegram_bot_token,
        chat_id,
        text,
        settings.telegram_proxy_url,
        reply_markup=keyboard(),
    )


def handle_message(settings: Settings, message: dict) -> None:
    chat = message.get("chat", {})
    user = message.get("from", {})
    chat_id = str(chat.get("id", ""))
    user_id = user.get("id")
    text = str(message.get("text", ""))

    if not chat_id:
        return
    if not is_admin(settings, user_id):
        send_telegram_message(settings.telegram_bot_token, chat_id, "Нет доступа.", settings.telegram_proxy_url)
        return

    if text in {"/start", "/menu", "меню", "Меню"}:
        send_menu(settings, chat_id)
    elif text in {"/extended", "отчет", "отчёт"}:
        build_and_send_extended_report(settings, chat_id)
    else:
        send_menu(settings, chat_id)


def handle_callback(settings: Settings, callback_query: dict) -> None:
    query_id = str(callback_query.get("id", ""))
    user = callback_query.get("from", {})
    user_id = user.get("id")
    data = str(callback_query.get("data", ""))
    message = callback_query.get("message", {})
    chat = message.get("chat", {})
    chat_id = str(chat.get("id", ""))

    if query_id:
        answer_callback_query(settings.telegram_bot_token, query_id, settings.telegram_proxy_url, "Принято")

    if not chat_id:
        return
    if not is_admin(settings, user_id):
        send_telegram_message(settings.telegram_bot_token, chat_id, "Нет доступа.", settings.telegram_proxy_url)
        return

    if data == EXTENDED_REPORT_CALLBACK:
        build_and_send_extended_report(settings, chat_id)
    else:
        send_menu(settings, chat_id)


def main() -> None:
    settings = get_settings()
    offset: int | None = None
    logging.info("VKDailyStat bot started")

    while True:
        try:
            updates = get_updates(settings.telegram_bot_token, offset, settings.telegram_proxy_url, timeout=30)
            for update in updates:
                offset = int(update["update_id"]) + 1
                if "message" in update:
                    handle_message(settings, update["message"])
                elif "callback_query" in update:
                    handle_callback(settings, update["callback_query"])
        except KeyboardInterrupt:
            raise
        except Exception:
            logging.exception("Bot polling error")


if __name__ == "__main__":
    main()
