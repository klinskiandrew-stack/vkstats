from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, timedelta
from typing import Any

from app.report import money
from app.vk_ads import AgencyClient, ClientSpend, VkAdsApi


@dataclass(frozen=True)
class ClientAnalytics:
    client_id: int | str
    name: str
    spent: float
    previous_spent: float
    week_ago_spent: float
    spent_change_percent: float | None
    week_ago_change_percent: float | None
    share_percent: float
    shows: int
    clicks: int
    goals: int
    ctr: float
    cpc: float
    cpm: float
    goal_cost: float | None
    balance: float | None
    balance_days_left: float | None


@dataclass(frozen=True)
class CampaignLimitIssue:
    client_name: str
    campaign_id: int | str
    campaign_name: str
    daily_limit: float
    spent: float
    limit_reach_percent: float
    unspent_limit: float
    clicks: int
    shows: int


@dataclass(frozen=True)
class ExtendedReportData:
    report_date: date
    previous_date: date
    week_ago_date: date
    total_spent: float
    previous_total_spent: float
    week_ago_total_spent: float
    total_change_percent: float | None
    week_ago_change_percent: float | None
    active_clients: int
    clients: list[ClientAnalytics]
    alerts: list[str]
    campaign_limit_issues: list[CampaignLimitIssue]


def safe_percent_change(current: float, previous: float) -> float | None:
    if previous == 0:
        return None
    return ((current - previous) / previous) * 100


def pct(value: float | None) -> str:
    if value is None:
        return "н/д"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.0f}%"


def ratio_percent(part: float, total: float) -> float:
    if total <= 0:
        return 0.0
    return (part / total) * 100


def ctr(clicks: int, shows: int) -> float:
    if shows <= 0:
        return 0.0
    return (clicks / shows) * 100


def cpc(spent: float, clicks: int) -> float:
    if clicks <= 0:
        return 0.0
    return spent / clicks


def cpm(spent: float, shows: int) -> float:
    if shows <= 0:
        return 0.0
    return spent / shows * 1000


def goal_cost(spent: float, goals: int) -> float | None:
    if goals <= 0:
        return None
    return spent / goals


def balance_days_left(balance: float | None, spent: float) -> float | None:
    if balance is None or spent <= 0:
        return None
    return balance / spent


def by_client_id(rows: list[ClientSpend]) -> dict[str, ClientSpend]:
    return {str(row.client_id): row for row in rows}


def build_client_analytics(
    current_rows: list[ClientSpend],
    previous_rows: list[ClientSpend],
    week_ago_rows: list[ClientSpend],
) -> list[ClientAnalytics]:
    previous = by_client_id(previous_rows)
    week_ago = by_client_id(week_ago_rows)
    active = [row for row in current_rows if row.spent > 0]
    total = sum(row.spent for row in active)
    result: list[ClientAnalytics] = []

    for row in active:
        prev = previous.get(str(row.client_id))
        week = week_ago.get(str(row.client_id))
        prev_spent = prev.spent if prev else 0.0
        week_spent = week.spent if week else 0.0
        result.append(
            ClientAnalytics(
                client_id=row.client_id,
                name=row.client_name,
                spent=row.spent,
                previous_spent=prev_spent,
                week_ago_spent=week_spent,
                spent_change_percent=safe_percent_change(row.spent, prev_spent),
                week_ago_change_percent=safe_percent_change(row.spent, week_spent),
                share_percent=ratio_percent(row.spent, total),
                shows=row.shows,
                clicks=row.clicks,
                goals=row.goals,
                ctr=ctr(row.clicks, row.shows),
                cpc=cpc(row.spent, row.clicks),
                cpm=cpm(row.spent, row.shows),
                goal_cost=goal_cost(row.spent, row.goals),
                balance=row.balance,
                balance_days_left=balance_days_left(row.balance, row.spent),
            )
        )

    return sorted(result, key=lambda item: item.spent, reverse=True)


def build_alerts(clients: list[ClientAnalytics]) -> list[str]:
    alerts: list[str] = []
    top_share = sum(item.share_percent for item in clients[:2])
    if len(clients) >= 2 and top_share >= 60:
        alerts.append(f"2 крупнейших клиента дают {top_share:.0f}% дневного открута.")

    for item in clients:
        if item.balance_days_left is not None and item.balance_days_left < 2:
            alerts.append(f"У {item.name} баланс может закончиться примерно за {item.balance_days_left:.1f} дня.")
        if item.spent_change_percent is not None and item.spent_change_percent >= 30:
            alerts.append(f"{item.name} вырос по расходу ко вчера на {item.spent_change_percent:.0f}%.")
        if item.spent_change_percent is not None and item.spent_change_percent <= -30:
            alerts.append(f"{item.name} просел по расходу ко вчера на {abs(item.spent_change_percent):.0f}%.")
        if item.spent > 1000 and item.clicks == 0:
            alerts.append(f"У {item.name} есть расход без кликов. Нужно проверить статистику и настройки.")
    return alerts[:8]


def get_campaign_limit_issues(
    api: VkAdsApi,
    report_date: date,
    active_clients: list[ClientAnalytics],
    all_clients: list[AgencyClient],
    min_daily_limit: float = 1000,
    max_limit_reach_percent: float = 80,
    max_clients_to_scan: int = 10,
) -> list[CampaignLimitIssue]:
    clients_by_id = {str(client.client_id): client for client in all_clients}
    issues: list[CampaignLimitIssue] = []

    for item in active_clients[:max_clients_to_scan]:
        client = clients_by_id.get(str(item.client_id))
        if not client:
            continue
        try:
            plans = api.get_ad_plans(client)
            plans = [plan for plan in plans if plan.budget_limit_day >= min_daily_limit]
            spends = api.get_ad_plan_spends(client, [plan.id for plan in plans], report_date)
        except Exception:
            continue

        for plan in plans:
            spend = spends.get(str(plan.id))
            spent = spend.spent if spend else 0.0
            reach = ratio_percent(spent, plan.budget_limit_day)
            if reach >= max_limit_reach_percent:
                continue
            issues.append(
                CampaignLimitIssue(
                    client_name=item.name,
                    campaign_id=plan.id,
                    campaign_name=plan.name,
                    daily_limit=plan.budget_limit_day,
                    spent=spent,
                    limit_reach_percent=reach,
                    unspent_limit=max(plan.budget_limit_day - spent, 0),
                    clicks=spend.clicks if spend else 0,
                    shows=spend.shows if spend else 0,
                )
            )

    return sorted(issues, key=lambda row: row.unspent_limit, reverse=True)[:20]


def collect_extended_report_data(api: VkAdsApi, report_date: date) -> ExtendedReportData:
    previous_date = report_date - timedelta(days=1)
    week_ago_date = report_date - timedelta(days=7)

    current_rows = api.get_spend_by_clients_period(report_date, report_date)
    previous_rows = api.get_spend_by_clients_period(previous_date, previous_date)
    week_ago_rows = api.get_spend_by_clients_period(week_ago_date, week_ago_date)

    total = sum(row.spent for row in current_rows if row.spent > 0)
    previous_total = sum(row.spent for row in previous_rows if row.spent > 0)
    week_ago_total = sum(row.spent for row in week_ago_rows if row.spent > 0)

    clients = build_client_analytics(current_rows, previous_rows, week_ago_rows)
    all_clients = api.get_agency_clients()
    campaign_issues = get_campaign_limit_issues(api, report_date, clients, all_clients)
    alerts = build_alerts(clients)

    if campaign_issues:
        total_unspent = sum(row.unspent_limit for row in campaign_issues)
        alerts.append(
            f"Найдено {len(campaign_issues)} кампаний с низким достижением дневного лимита, суммарный недокрут — {money(total_unspent)}."
        )

    return ExtendedReportData(
        report_date=report_date,
        previous_date=previous_date,
        week_ago_date=week_ago_date,
        total_spent=total,
        previous_total_spent=previous_total,
        week_ago_total_spent=week_ago_total,
        total_change_percent=safe_percent_change(total, previous_total),
        week_ago_change_percent=safe_percent_change(total, week_ago_total),
        active_clients=len(clients),
        clients=clients,
        alerts=alerts[:10],
        campaign_limit_issues=campaign_issues,
    )


def to_ai_payload(data: ExtendedReportData) -> dict[str, Any]:
    payload = asdict(data)
    payload["report_date"] = data.report_date.isoformat()
    payload["previous_date"] = data.previous_date.isoformat()
    payload["week_ago_date"] = data.week_ago_date.isoformat()
    return payload


def build_extended_report(data: ExtendedReportData, currency_symbol: str = "₽", ai_summary: str = "") -> str:
    lines: list[str] = []
    lines.append(f"📊 расширенный отчёт за {data.report_date.strftime('%d.%m.%Y')}")

    if ai_summary:
        lines.append("")
        lines.append(ai_summary.strip())

    if data.alerts:
        lines.append("")
        lines.append("Что требует внимания:")
        for alert in data.alerts:
            lines.append(f"— {alert}")

    lines.append("")
    lines.append("Итого по агентскому кабинету:")
    lines.append(f"Расход: {money(data.total_spent, currency_symbol)}")
    lines.append(f"Ко вчера: {money(data.total_spent - data.previous_total_spent, currency_symbol)}, {pct(data.total_change_percent)}")
    lines.append(f"К тому же дню прошлой недели: {money(data.total_spent - data.week_ago_total_spent, currency_symbol)}, {pct(data.week_ago_change_percent)}")
    lines.append(f"Клиентов с открутом: {data.active_clients}")

    if data.clients:
        lines.append("")
        lines.append("Клиенты по откруту:")
        for index, item in enumerate(data.clients, start=1):
            lines.append(
                f"{index}. {item.name} — {money(item.spent, currency_symbol)}, "
                f"{item.share_percent:.0f}% бюджета, ко вчера: {pct(item.spent_change_percent)}"
            )
            metrics = [
                f"клики: {item.clicks}",
                f"показы: {item.shows}",
                f"CTR: {item.ctr:.2f}%",
                f"CPC: {money(item.cpc, currency_symbol)}",
                f"CPM: {money(item.cpm, currency_symbol)}",
            ]
            if item.goals:
                metrics.append(f"цели VK: {item.goals}")
                if item.goal_cost is not None:
                    metrics.append(f"цена цели: {money(item.goal_cost, currency_symbol)}")
            lines.append("   " + ", ".join(metrics))
            if item.balance is not None:
                days = f", хватит примерно на {item.balance_days_left:.1f} дня" if item.balance_days_left else ""
                lines.append(f"   баланс: {money(item.balance, currency_symbol)}{days}")

    if data.campaign_limit_issues:
        lines.append("")
        lines.append("Кампании с низким достижением дневного лимита:")
        last_client = ""
        for issue in data.campaign_limit_issues:
            if issue.client_name != last_client:
                lines.append(issue.client_name)
                last_client = issue.client_name
            lines.append(f"— {issue.campaign_name}")
            lines.append(
                f"  дневной лимит: {money(issue.daily_limit, currency_symbol)}, "
                f"открут: {money(issue.spent, currency_symbol)}, "
                f"достижение лимита: {issue.limit_reach_percent:.0f}%"
            )
            lines.append(f"  недокрут до лимита: {money(issue.unspent_limit, currency_symbol)}")

    return "\n".join(lines)
