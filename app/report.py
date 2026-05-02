from __future__ import annotations

from datetime import date

from app.vk_ads import ClientSpend


def money(value: float, symbol: str = "₽") -> str:
    rounded = round(value)
    return f"{rounded:,.0f}".replace(",", " ") + f" {symbol}"


def build_daily_report(rows: list[ClientSpend], report_date: date, currency_symbol: str = "₽") -> str:
    active_rows = [row for row in rows if row.spent > 0]
    zero_rows = [row for row in rows if row.spent <= 0]
    total_spent = sum(row.spent for row in rows)

    lines: list[str] = []
    lines.append(f"📊 VK Ads — открут за {report_date.strftime('%d.%m.%Y')}")
    lines.append("")
    lines.append("Итого по агентскому кабинету:")
    lines.append(f"Расход: {money(total_spent, currency_symbol)}")
    lines.append(f"Активных проектов: {len(active_rows)}")
    lines.append(f"Проектов без открута: {len(zero_rows)}")

    if active_rows:
        lines.append("")
        lines.append("По проектам:")
        for row in active_rows:
            metrics = []
            if row.clicks:
                metrics.append(f"клики: {row.clicks}")
            if row.shows:
                metrics.append(f"показы: {row.shows}")
            metrics_text = f" ({', '.join(metrics)})" if metrics else ""
            lines.append(f"— {row.client_name} — {money(row.spent, currency_symbol)}{metrics_text}")

    if zero_rows:
        lines.append("")
        lines.append("Без открута:")
        for row in zero_rows[:30]:
            lines.append(f"— {row.client_name}")
        if len(zero_rows) > 30:
            lines.append(f"…и ещё {len(zero_rows) - 30}")

    return "\n".join(lines)
