from __future__ import annotations

import json
from typing import Any

import requests

from app.settings import Settings
from app.extended_report import ExtendedReportData, to_ai_payload


SYSTEM_PROMPT = """Ты аналитик рекламного агентства. Пиши краткую управленческую сводку по данным VK Ads.
Правила:
— пиши по-русски;
— не придумывай цифры;
— используй только данные из JSON;
— не пересказывай весь отчёт;
— дай 3–5 коротких выводов;
— отдельно укажи, что проверить;
— не используй markdown-звёздочки.
"""


def build_prompt(data: ExtendedReportData) -> str:
    payload = to_ai_payload(data)
    return (
        "Сформируй короткую сводку для руководителя агентства по дневному отчёту VK Ads. "
        "Нужно объяснить, что изменилось, где риски и что проверить.\n\n"
        "Данные:\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def build_ai_summary(settings: Settings, data: ExtendedReportData) -> str:
    if not settings.enable_ai_summary:
        return ""
    if not settings.ai_api_key or not settings.ai_base_url or not settings.ai_model:
        return ""

    url = f"{settings.ai_base_url}/chat/completions"
    payload: dict[str, Any] = {
        "model": settings.ai_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_prompt(data)},
        ],
        "temperature": 0.2,
        "max_tokens": 900,
    }
    headers = {
        "Authorization": f"Bearer {settings.ai_api_key}",
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers, json=payload, timeout=settings.ai_timeout_seconds)
    if response.status_code != 200:
        raise RuntimeError(f"ИИ-сводка не получена. Код: {response.status_code}. Ответ: {response.text[:500]}")
    data_json = response.json()
    return str(data_json["choices"][0]["message"]["content"]).strip()
