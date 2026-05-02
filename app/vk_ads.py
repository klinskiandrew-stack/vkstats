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
            "grant_type": "agency_client_credentials",
            "client_id": self.settings.vk_ads_client_id,
            "client_secret": self.settings.vk_ads_client_secret,
            "agency_client_name": self.settings.vk_ads_agency_client_name,
        }

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
        return token[:10] + "..."

    def get_agency_clients(self) -> list[dict[str, Any]]:
        """Возвращает клиентов агентского кабинета.

        В новом VK Ads API используется наследие myTarget API. Для агентств
        основной справочник клиентов обычно доступен по /agency/clients.json.
        """
        data = self._get("/agency/clients.json")
        return self._extract_list(data)

    def get_spend_by_clients(self, report_date: date) -> list[ClientSpend]:
        """Получает расход по клиентам агентства за дату.

        Используется статистика v2 с группировкой users, которая подходит для
        агентских кабинетов: /statistics/users/day.json.
        """
        params = {
            "date_from": report_date.isoformat(),
            "date_to": report_date.isoformat(),
            "metrics": "base",
        }
        data = self._get("/statistics/users/day.json", params=params)
        rows = self._extract_list(data)

        clients = {str(item.get("id")): item for item in self.get_agency_clients_safe()}
        result: list[ClientSpend] = []

        for row in rows:
            client_id = self._first_existing(row, ["id", "user_id", "client_id"])
            stats = self._extract_stats(row)
            spent = self._as_float(self._first_existing(stats, ["spent", "amount", "cost"], 0))

            if client_id is None:
                client_id = row.get("id", "unknown")

            client_info = clients.get(str(client_id), {})
            client_name = str(
                self._first_existing(
                    client_info,
                    ["name", "username", "login", "client_username", "email"],
                    f"Клиент {client_id}",
                )
            )

            result.append(
                ClientSpend(
                    client_id=client_id,
                    client_name=client_name,
                    spent=spent,
                    shows=int(self._as_float(self._first_existing(stats, ["shows"], 0))),
                    clicks=int(self._as_float(self._first_existing(stats, ["clicks"], 0))),
                    goals=int(self._as_float(self._first_existing(stats, ["goals"], 0))),
                )
            )

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
