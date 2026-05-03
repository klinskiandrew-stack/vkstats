from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


@dataclass
class StoredToken:
    access_token: str
    refresh_token: str
    expires_at: str
    username: str = ""
    name: str = ""
    balance: float | None = None


class TokenStore:
    def __init__(self, path: str, timezone: str = "Europe/Moscow") -> None:
        self.path = Path(path)
        self.timezone = timezone
        self.data = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"agency": {}, "clients": {}}

        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"agency": {}, "clients": {}}

    def save(self) -> None:
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_agency_token(self) -> StoredToken | None:
        raw = self.data.get("agency") or {}
        return self._to_token(raw)

    def set_agency_token(self, token: StoredToken) -> None:
        self.data["agency"] = asdict(token)
        self.save()

    def get_client_token(self, client_id: int | str) -> StoredToken | None:
        raw = (self.data.get("clients") or {}).get(str(client_id)) or {}
        return self._to_token(raw)

    def set_client_token(self, client_id: int | str, token: StoredToken) -> None:
        self.data.setdefault("clients", {})[str(client_id)] = asdict(token)
        self.save()

    def is_expiring_soon(self, token: StoredToken | None, minutes: int = 30) -> bool:
        if token is None or not token.access_token:
            return True
        if not token.expires_at:
            return True

        try:
            expires_at = datetime.fromisoformat(token.expires_at)
        except ValueError:
            return True

        now = datetime.now(ZoneInfo(self.timezone))
        return expires_at <= now + timedelta(minutes=minutes)

    def build_expires_at(self, expires_in: int | str | None) -> str:
        try:
            seconds = int(expires_in or 86400)
        except (TypeError, ValueError):
            seconds = 86400

        now = datetime.now(ZoneInfo(self.timezone))
        return (now + timedelta(seconds=seconds)).isoformat()

    @staticmethod
    def _to_token(raw: dict[str, Any]) -> StoredToken | None:
        if not raw or not raw.get("access_token"):
            return None

        return StoredToken(
            access_token=str(raw.get("access_token", "")),
            refresh_token=str(raw.get("refresh_token", "")),
            expires_at=str(raw.get("expires_at", "")),
            username=str(raw.get("username", "")),
            name=str(raw.get("name", "")),
            balance=raw.get("balance"),
        )
