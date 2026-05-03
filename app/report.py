from __future__ import annotations

from datetime import date

from app.vk_ads import ClientSpend


def money(value: float, symbol: str = "₽") -> str:
    rounded = round(value)
    return f"{rounded:,.0f}".replace(",", " ") + f" {symbol}"


def percent_change(current: float, previous: float) -> str:
    if previous == 0 and current == 0:
        return "без изменений"
    if previous == 0:
        return "рост с 0"

    change = ((current - previous) / previous) * 100
    sign = "+" if change > 0 else ""
    return f"{sign}{change:.1f}%"


def period_title(period_name: str, date_from: date, date_to: date) -> str:
    if date_from == date_to:
        return f"отчёт за {date_from.strftime('%d.%m.%Y')}"
    return f"отчёт за {date_from.strftime('%d.%m.%Y')}–{date_to.strftime('%d.%m.%Y')}"


def build_report(
    rows: list[ClientSpend],
    date_from: date,
    date_to: date,
    period_name: str,
    currency_symbol: str = "₽",
    previous_total: float | None = None,
    previous_label: str | None = None,
) -> str:
    active_rows = [row for row in rows if row.spent > 0]
    total_spent = sum(row.spent for row in active_rows)

    lines: list[str] = []
    lines.append(f"📊 {period_title(period_name, date_from, date_to)}")
    lines.append("")
    lines.append("Итого по агентскому кабинету:")
    lines.append(f"Расход: {money(total_spent, currency_symbol)}")

    if previous_total is not None:
        label = previous_label or "предыдущий период"
        lines.append(f"Изменение к периоду «{label}»: {percent_change(total_spent, previous_total)}")
        lines.append(f"Предыдущий период: {money(previous_total, currency_symbol)}")

    lines.append(f"Клиентов с открутом: {len(active_rows)}")

    if active_rows:
        lines.append("")
        lines.append("Клиенты по откруту:")
        for index, row in enumerate(active_rows, start=1):
            metrics = []
            if row.clicks:
                metrics.append(f"клики: {row.clicks}")
            if row.shows:
                metrics.append(f"показы: {row.shows}")
            metrics_text = f" ({', '.join(metrics)})" if metrics else ""
            lines.append(f"{index}. {row.client_name} — {money(row.spent, currency_symbol)}{metrics_text}")
    else:
        lines.append("")
        lines.append("Клиентов с открутом за период нет.")

    return "\n".join(lines)


def build_daily_report(rows: list[ClientSpend], report_date: date, currency_symbol: str = "₽") -> str:
    return build_report(
        rows=rows,
        date_from=report_date,
        date_to=report_date,
        period_name="день",
        currency_symbol=currency_symbol,
    )
