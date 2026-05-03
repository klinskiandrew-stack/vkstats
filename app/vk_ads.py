from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import requests

from app.settings import Settings
from app.token_store import StoredToken, TokenStore


@dataclass(frozen=True)
class AgencyClient:
    client_id: int | str
    username: str
    name: str
    access_type: str = ""
    status: str = ""
    balance: float | None = None


@dataclass(frozen=True)
class ClientSpend:
    client_id: int | str
    client_name: str
    spent: float
    shows: int = 0
    clicks: int = 0
    goals: int = 0
    balance: float | None = None


class VkAdsApi:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = TokenStore(settings.token_store_path, settings.timezone)
        self._agency_token: str | None = None

    def _headers(self, access_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token}"}

    def _get(self, path: str, access_token: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.settings.api_base_url}{path}"
        response = requests.get(url, headers=self._headers(access_token), params=params, timeout=60)
        self._raise_for_status(response, f"выполнить GET {path}")
        return response.json()

    def _post(self, path: str, payload: dict[str, Any]) -> Any:
        url = f"{self.settings.api_base_url}{path}"
        response = requests.post(url, data=payload, timeout=60)
        self._raise_for_status(response, f"выполнить POST {path}")
        return response.json()

    @staticmethod
    def _raise_for_status(response: requests.Response, action: str) -> None:
        if 200 <= response.status_code < 300:
            return
        raise RuntimeError(f"Не удалось {action}. Код: {response.status_code}. Ответ: {response.text}")

    def test_access(self) -> str:
        token = self.get_agency_access_token()
        mode = "agency_token_with_refresh" if self.settings.vk_ads_agency_refresh_token else "static_token"
        return f"{token[:10]}... ({mode})"

    def get_agency_access_token(self) -> str:
        if self._agency_token:
            return self._agency_token

        stored = self.store.get_agency_token()
        if stored and not self.store.is_expiring_soon(stored):
            self._agency_token = stored.access_token
            return self._agency_token

        if stored and stored.refresh_token:
            refreshed = self.refresh_token(stored.refresh_token)
            self.store.set_agency_token(refreshed)
            self._agency_token = refreshed.access_token
            return self._agency_token

        if self.settings.vk_ads_agency_access_token:
            token = StoredToken(
                access_token=self.settings.vk_ads_agency_access_token,
                refresh_token=self.settings.vk_ads_agency_refresh_token,
                expires_at=self.settings.vk_ads_agency_expires_at or self.store.build_expires_at(86400),
            )
            if self.store.is_expiring_soon(token) and token.refresh_token:
                token = self.refresh_token(token.refresh_token)
            self.store.set_agency_token(token)
            self._agency_token = token.access_token
            return self._agency_token

        if self.settings.vk_ads_access_token:
            self._agency_token = self.settings.vk_ads_access_token
            return self._agency_token

        raise RuntimeError("Нет агентского access_token. Заполните VK_ADS_AGENCY_ACCESS_TOKEN.")

    def refresh_token(self, refresh_token: str) -> StoredToken:
        data = self._post(
            "/oauth2/token.json",
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.settings.vk_ads_client_id,
                "client_secret": self.settings.vk_ads_client_secret,
            },
        )
        return self._token_from_response(data)

    def get_client_access_token(self, client: AgencyClient) -> str:
        stored = self.store.get_client_token(client.client_id)
        if stored and not self.store.is_expiring_soon(stored):
            return stored.access_token

        if stored and stored.refresh_token:
            refreshed = self.refresh_token(stored.refresh_token)
            refreshed.username = client.username
            refreshed.name = client.name
            refreshed.balance = client.balance
            self.store.set_client_token(client.client_id, refreshed)
            return refreshed.access_token

        payload = {
            "grant_type": "agency_client_credentials",
            "client_id": self.settings.vk_ads_client_id,
            "client_secret": self.settings.vk_ads_client_secret,
            "access_token": self.get_agency_access_token(),
            "agency_client_id": str(client.client_id),
        }

        data = self._post("/oauth2/token.json", payload)
        token = self._token_from_response(data)
        token.username = client.username
        token.name = client.name
        token.balance = client.balance
        self.store.set_client_token(client.client_id, token)
        return token.access_token

    def get_agency_clients(self) -> list[AgencyClient]:
        access_token = self.get_agency_access_token()
        clients: list[AgencyClient] = []
        offset = 0
        limit = 50

        while True:
            data = self._get(
                "/agency/clients.json",
                access_token,
                params={"limit": limit, "offset": offset, "status": "active"},
            )
            items = self._extract_list(data)
            for item in items:
                client = self._parse_agency_client(item)
                if client:
                    clients.append(client)

            count = int(data.get("count", len(items)) if isinstance(data, dict) else len(items))
            offset += limit
            if not items or offset >= count:
                break

        return clients

    def get_spend_by_client_period(self, client: AgencyClient, date_from: date, date_to: date) -> ClientSpend:
        access_token = self.get_client_access_token(client)
        data = self._get(
            "/statistics/users/day.json",
            access_token,
            params={
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "metrics": "base",
                "id": str(client.client_id),
            },
        )
        spent, shows, clicks, goals = self._collect_metrics_from_response(data)
        return ClientSpend(
            client_id=client.client_id,
            client_name=client.name or client.username or f"Клиент {client.client_id}",
            spent=spent,
            shows=shows,
            clicks=clicks,
            goals=goals,
            balance=client.balance,
        )

    def get_spend_by_clients_period(self, date_from: date, date_to: date) -> list[ClientSpend]:
        clients = self.get_agency_clients()
        result: list[ClientSpend] = []
        errors: list[str] = []

        for client in clients:
            try:
                result.append(self.get_spend_by_client_period(client, date_from, date_to))
            except Exception as exc:
                errors.append(f"{client.name or client.username or client.client_id}: {exc}")

        if errors and not result:
            raise RuntimeError("Не удалось получить статистику клиентов: " + " | ".join(errors[:5]))

        return sorted(result, key=lambda item: item.spent, reverse=True)

    def get_spend_by_client(self, client_id: int | str, report_date: date) -> ClientSpend:
        for client in self.get_agency_clients():
            if str(client.client_id) == str(client_id):
                return self.get_spend_by_client_period(client, report_date, report_date)
        raise RuntimeError(f"Клиент {client_id} не найден в агентском кабинете")

    def _token_from_response(self, data: dict[str, Any]) -> StoredToken:
        access_token = data.get("access_token")
        if not access_token:
            raise RuntimeError(f"VK Ads не вернул access_token. Ответ: {data}")
        return StoredToken(
            access_token=str(access_token),
            refresh_token=str(data.get("refresh_token", "")),
            expires_at=self.store.build_expires_at(data.get("expires_in", 86400)),
        )

    def _parse_agency_client(self, item: dict[str, Any]) -> AgencyClient | None:
        user = item.get("user") if isinstance(item.get("user"), dict) else item
        client_id = self._first_existing(user, ["id", "user_id", "client_id"])
        if client_id is None:
            return None

        username = str(self._first_existing(user, ["username", "login", "email"], ""))
        additional_info = user.get("additional_info") if isinstance(user.get("additional_info"), dict) else {}
        name = str(
            self._first_existing(
                additional_info,
                ["client_name", "name"],
                self._first_existing(user, ["name"], username or f"Клиент {client_id}"),
            )
        )
        account = user.get("account") if isinstance(user.get("account"), dict) else {}
        balance = self._first_existing(account, ["balance", "amount"], None)

        return AgencyClient(
            client_id=client_id,
            username=username,
            name=name,
            access_type=str(item.get("access_type", "")),
            status=str(item.get("status", "")),
            balance=self._as_float(balance) if balance is not None else None,
        )

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

    def _collect_metrics_from_response(self, data: Any) -> tuple[float, int, int, int]:
        spent = shows = clicks = goals = 0
        if isinstance(data, dict) and isinstance(data.get("total"), dict):
            spent, shows, clicks, goals = self._collect_metrics(data["total"])
            return spent, shows, clicks, goals

        for row in self._extract_list(data):
            s, sh, c, g = self._collect_metrics(row)
            spent += s
            shows += sh
            clicks += c
            goals += g
        return float(spent), int(shows), int(clicks), int(goals)

    def _collect_metrics(self, row: dict[str, Any]) -> tuple[float, int, int, int]:
        stats = self._extract_stats(row)
        spent = self._as_float(self._first_existing(stats, ["spent", "amount", "cost"], 0))
        shows = int(self._as_float(self._first_existing(stats, ["shows", "impressions"], 0)))
        clicks = int(self._as_float(self._first_existing(stats, ["clicks"], 0)))
        goals = int(self._as_float(self._first_existing(stats, ["goals", "conversions"], 0)))
        return spent, shows, clicks, goals

    @staticmethod
    def _extract_stats(row: dict[str, Any]) -> dict[str, Any]:
        for key in ("base", "total", "stats"):
            value = row.get(key)
            if isinstance(value, dict):
                if "base" in value and isinstance(value["base"], dict):
                    return value["base"]
                return value
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
