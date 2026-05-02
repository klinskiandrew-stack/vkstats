from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.report import build_daily_report
from app.settings import get_settings
from app.telegram_sender import send_telegram_message
from app.vk_ads import VkAdsApi


def yesterday(timezone: str):
    now = datetime.now(ZoneInfo(timezone))
    return (now - timedelta(days=1)).date()


def main() -> None:
    parser = argparse.ArgumentParser(description="VK Ads daily budget report")
    parser.add_argument(
        "command",
        choices=["check-token", "list-clients", "send-report"],
        help="Что сделать: проверить токен, вывести клиентов или отправить отчет",
    )
    parser.add_argument(
        "--date",
        help="Дата отчета в формате YYYY-MM-DD. По умолчанию — вчера по TIMEZONE.",
    )
    args = parser.parse_args()

    settings = get_settings()
    api = VkAdsApi(settings)

    if args.command == "check-token":
        token_preview = api.test_access()
        print("Доступ к VK Ads API работает.")
        print(f"Токен получен: {token_preview}")
        return

    if args.command == "list-clients":
        clients = api.get_agency_clients()
        print(f"Найдено клиентов: {len(clients)}")
        for client in clients:
            client_id = client.get("id") or client.get("user_id") or client.get("client_id")
            name = client.get("name") or client.get("username") or client.get("login") or client
            print(f"{client_id}: {name}")
        return

    if args.command == "send-report":
        report_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else yesterday(settings.timezone)
        rows = api.get_spend_by_clients(report_date)
        text = build_daily_report(rows, report_date, settings.currency_symbol)
        send_telegram_message(settings.telegram_bot_token, settings.telegram_chat_id, text)
        print("Отчет отправлен в Telegram.")
        return


if __name__ == "__main__":
    main()
