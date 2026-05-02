from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.report import build_daily_report, money
from app.settings import get_settings
from app.telegram_sender import send_telegram_message
from app.vk_ads import VkAdsApi


def yesterday(timezone: str):
    now = datetime.now(ZoneInfo(timezone))
    return (now - timedelta(days=1)).date()


def parse_report_date(date_value: str | None, timezone: str):
    if date_value:
        return datetime.strptime(date_value, "%Y-%m-%d").date()
    return yesterday(timezone)


def main() -> None:
    parser = argparse.ArgumentParser(description="VK Ads daily budget report")
    parser.add_argument(
        "command",
        choices=["check-token", "list-clients", "client-spend", "send-report"],
        help="Что сделать: проверить токен, вывести клиентов, проверить клиента или отправить отчет",
    )
    parser.add_argument(
        "--date",
        help="Дата отчета в формате YYYY-MM-DD. По умолчанию — вчера по TIMEZONE.",
    )
    parser.add_argument(
        "--client-id",
        help="ID клиента VK Ads для проверки одного клиента.",
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

    if args.command == "client-spend":
        if not args.client_id:
            raise RuntimeError("Для команды client-spend нужен параметр --client-id")
        report_date = parse_report_date(args.date, settings.timezone)
        row = api.get_spend_by_client(args.client_id, report_date)
        print(f"VK Ads — клиент {row.client_id}, дата {report_date.strftime('%d.%m.%Y')}")
        print(f"Расход: {money(row.spent, settings.currency_symbol)}")
        print(f"Показы: {row.shows}")
        print(f"Клики: {row.clicks}")
        print(f"Цели: {row.goals}")
        return

    if args.command == "send-report":
        report_date = parse_report_date(args.date, settings.timezone)
        rows = api.get_spend_by_clients(report_date)
        text = build_daily_report(rows, report_date, settings.currency_symbol)
        send_telegram_message(settings.telegram_bot_token, settings.telegram_chat_id, text)
        print("Отчет отправлен в Telegram.")
        return


if __name__ == "__main__":
    main()
