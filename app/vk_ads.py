from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import requests

from app.settings import Settings


@dataclass(frozen=True)
class ClientSpend:
    client_id: int | str
    client_name: str
    spent: float
    shows: int = 0
    clicks: int = 0
    goals: int = 0


class VkAdsApi:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.access_token: str | None = None

    def get_access_token(self) -> str:
        if self.access_token:
            return self.access_token

        url = f"{self.settings.api_base_url}/oauth2/token.json"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.settings.vk_ads_client_id,
            "client_secret": self.settings.vk_ads_client_secret,
        }

        if self.settings.vk_ads_agency_client_name:
            payload["grant_type"] = "agency_client_credentials"
            payload["agency_client_name"] = self.settings.vk_ads_agency_client_name

        response = requests.post(url, data=payload, timeout=40)
        self._raise_for_status(response, "получить access_token")

        data = response.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError(f"VK Ads не вернул access_token. Ответ: {data}")

        self.access_token = token
        return token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.get_access_token()}"}

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.settings.api_base_url}{path}"
        response = requests.get(url, headers=self._headers(), params=params, timeout=60)
        self._raise_for_status(response, f"выполнить GET {path}")
        return response.json()

    @staticmethod
    def _raise_for_status(response: requests.Response, action: str) -> None:
        if 200 <= response.status_code < 300:
            return

        raise RuntimeError(
            f"Не удалось {action}. Код: {response.status_code}. Ответ: {response.text}"
        )

    def test_access(self) -> str:
        token = self.get_access_token()
        auth_type = "agency_client_credentials" if self.settings.vk_ads_agency_client_name else "client_credentials"
        return f"{token[:10]}... ({auth_type})"

    def get_agency_clients(self) -> list[dict[str, Any]]:
        data = self._get("/agency/clients.json")
        return self._extract_list(data)

    def get_spend_by_client(self, client_id: int | str, report_date: date) -> ClientSpend:
        return self.get_spend_by_client_period(client_id, report_date, report_date)

    def get_spend_by_client_period(
        self,
        client_id: int | str,
        date_from: date,
        date_to: date,
    ) -> ClientSpend:
        params = {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "metrics": "base",
            "id": str(client_id),
        }
        data = self._get("/statistics/users/day.json", params=params)
        rows = self._extract_list(data)

        if not rows and isinstance(data, dict):
            rows = [data]

        spent = 0.0
        shows = 0
        clicks = 0
        goals = 0

        for row in rows:
            item_spent, item_shows, item_clicks, item_goals = self._collect_metrics(row)
            spent += item_spent
            shows += item_shows
            clicks += item_clicks
            goals += item_goals

        return ClientSpend(
            client_id=client_id,
            client_name=f"Клиент {client_id}",
            spent=spent,
            shows=shows,
            clicks=clicks,
            goals=goals,
        )

    def get_spend_by_clients(self, report_date: date) -> list[ClientSpend]:
        return self.get_spend_by_clients_period(report_date, report_date)

    def get_spend_by_clients_period(self, date_from: date, date_to: date) -> list[ClientSpend]:
        params = {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "metrics": "base",
        }
        data = self._get("/statistics/users/day.json", params=params)
        rows = self._extract_list(data)

        clients = {str(item.get("id")): item for item in self.get_agency_clients_safe()}
        grouped: dict[str, dict[str, Any]] = {}

        for row in rows:
            client_id = self._first_existing(row, ["id", "user_id", "client_id"])
            if client_id is None:
                client_id = row.get("id", "unknown")

            client_id_str = str(client_id)
            if client_id_str not in grouped:
                client_info = clients.get(client_id_str, {})
                client_name = str(
                    self._first_existing(
                        client_info,
                        ["name", "username", "login", "client_username", "email"],
                        f"Клиент {client_id}",
                    )
                )
                grouped[client_id_str] = {
                    "client_id": client_id,
                    "client_name": client_name,
                    "spent": 0.0,
                    "shows": 0,
                    "clicks": 0,
                    "goals": 0,
                }

            item_spent, item_shows, item_clicks, item_goals = self._collect_metrics(row)
            grouped[client_id_str]["spent"] += item_spent
            grouped[client_id_str]["shows"] += item_shows
            grouped[client_id_str]["clicks"] += item_clicks
            grouped[client_id_str]["goals"] += item_goals

        result = [
            ClientSpend(
                client_id=item["client_id"],
                client_name=item["client_name"],
                spent=item["spent"],
                shows=item["shows"],
                clicks=item["clicks"],
                goals=item["goals"],
            )
            for item in grouped.values()
        ]

        return sorted(result, key=lambda item: item.spent, reverse=True)

    def get_agency_clients_safe(self) -> list[dict[str, Any]]:
        try:
            return self.get_agency_clients()
        except Exception:
            return []

    @staticmethod
    def _extract_list(data: Any) -> list[dict[str, Any]]:
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]

        if isinstance(data, dict):
            for key in ("items", "data", "results", "response"):
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]

        return []

    @staticmethod
    def _extract_stats(row: dict[str, Any]) -> dict[str, Any]:
        for key in ("total", "base", "stats"):
            value = row.get(key)
            if isinstance(value, dict):
                return value

        rows = row.get("rows")
        if isinstance(rows, list) and rows:
            first = rows[0]
            if isinstance(first, dict):
                for key in ("base", "total"):
                    value = first.get(key)
                    if isinstance(value, dict):
                        return value
                return first

        return row

    def _collect_metrics(self, row: dict[str, Any]) -> tuple[float, int, int, int]:
        stats = self._extract_stats(row)

        spent = self._as_float(self._first_existing(stats, ["spent", "amount", "cost"], 0))
        shows = int(self._as_float(self._first_existing(stats, ["shows", "impressions"], 0)))
        clicks = int(self._as_float(self._first_existing(stats, ["clicks"], 0)))
        goals = int(self._as_float(self._first_existing(stats, ["goals", "conversions"], 0)))

        nested_rows = row.get("rows")
        if isinstance(nested_rows, list):
            for nested in nested_rows:
                if not isinstance(nested, dict):
                    continue
                nested_stats = self._extract_stats(nested)
                spent += self._as_float(self._first_existing(nested_stats, ["spent", "amount", "cost"], 0))
                shows += int(self._as_float(self._first_existing(nested_stats, ["shows", "impressions"], 0)))
                clicks += int(self._as_float(self._first_existing(nested_stats, ["clicks"], 0)))
                goals += int(self._as_float(self._first_existing(nested_stats, ["goals", "conversions"], 0)))

        return spent, shows, clicks, goals

    @staticmethod
    def _first_existing(source: dict[str, Any], keys: list[str], default: Any = None) -> Any:
        for key in keys:
            if key in source and source[key] not in (None, ""):
                return source[key]
        return default

    @staticmethod
    def _as_float(value: Any) -> float:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            value = value.replace(" ", "").replace(",", ".")
            try:
                return float(value)
            except ValueError:
                return 0.0
        return 0.0
