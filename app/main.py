from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.report import build_report, money
from app.settings import get_settings
from app.telegram_sender import send_telegram_message
from app.vk_ads import VkAdsApi


def yesterday(timezone: str) -> date:
    now = datetime.now(ZoneInfo(timezone))
    return (now - timedelta(days=1)).date()


def parse_report_date(date_value: str | None, timezone: str) -> date:
    if date_value:
        return datetime.strptime(date_value, "%Y-%m-%d").date()
    return yesterday(timezone)


def week_range_for_report(today: date) -> tuple[date, date, date, date]:
    current_end = today - timedelta(days=1)
    current_start = current_end - timedelta(days=6)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=6)
    return current_start, current_end, previous_start, previous_end


def month_range_for_report(today: date) -> tuple[date, date, date, date]:
    first_day_this_month = today.replace(day=1)
    current_end = first_day_this_month - timedelta(days=1)
    current_start = current_end.replace(day=1)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end.replace(day=1)
    return current_start, current_end, previous_start, previous_end


def total_spent(rows) -> float:
    return sum(row.spent for row in rows)


def send_message(settings, text: str) -> None:
    send_telegram_message(
        settings.telegram_bot_token,
        settings.telegram_chat_id,
        text,
        settings.telegram_proxy_url,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="VKDailyStat")
    parser.add_argument(
        "command",
        choices=["check-token", "list-clients", "client-spend", "send-report", "send-auto-report"],
        help="Что сделать: проверить токен, вывести клиентов, проверить клиента или отправить отчет",
    )
    parser.add_argument("--date", help="Дата отчета в формате YYYY-MM-DD. По умолчанию — вчера по TIMEZONE.")
    parser.add_argument("--client-id", help="ID клиента VK Ads для проверки одного клиента.")
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
            balance = f", баланс: {money(client.balance, settings.currency_symbol)}" if client.balance is not None else ""
            print(f"{client.client_id}: {client.name} / {client.username} / доступ: {client.access_type}{balance}")
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
        if row.balance is not None:
            print(f"Баланс: {money(row.balance, settings.currency_symbol)}")
        return

    if args.command == "send-report":
        report_date = parse_report_date(args.date, settings.timezone)
        rows = api.get_spend_by_clients_period(report_date, report_date)
        text = build_report(rows, report_date, report_date, "день", settings.currency_symbol)
        send_message(settings, text)
        print("Дневной отчет отправлен в Telegram.")
        return

    if args.command == "send-auto-report":
        now = datetime.now(ZoneInfo(settings.timezone)).date()
        report_date = parse_report_date(args.date, settings.timezone)
        day_rows = api.get_spend_by_clients_period(report_date, report_date)
        messages = [build_report(day_rows, report_date, report_date, "день", settings.currency_symbol)]

        if now.weekday() == 0:
            current_start, current_end, previous_start, previous_end = week_range_for_report(now)
            current_rows = api.get_spend_by_clients_period(current_start, current_end)
            previous_rows = api.get_spend_by_clients_period(previous_start, previous_end)
            messages.append(
                build_report(
                    current_rows,
                    current_start,
                    current_end,
                    "неделя",
                    settings.currency_symbol,
                    previous_total=total_spent(previous_rows),
                    previous_label=f"{previous_start.strftime('%d.%m.%Y')}–{previous_end.strftime('%d.%m.%Y')}",
                )
            )

        if now.day == 1:
            current_start, current_end, previous_start, previous_end = month_range_for_report(now)
            current_rows = api.get_spend_by_clients_period(current_start, current_end)
            previous_rows = api.get_spend_by_clients_period(previous_start, previous_end)
            messages.append(
                build_report(
                    current_rows,
                    current_start,
                    current_end,
                    "месяц",
                    settings.currency_symbol,
                    previous_total=total_spent(previous_rows),
                    previous_label=f"{previous_start.strftime('%d.%m.%Y')}–{previous_end.strftime('%d.%m.%Y')}",
                )
            )

        send_message(settings, "\n\n——————————\n\n".join(messages))
        print("Автоотчет отправлен в Telegram.")
        return


if __name__ == "__main__":
    main()
