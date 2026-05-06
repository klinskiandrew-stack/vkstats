from __future__ import annotations

from typing import Any

import requests


def _proxies(proxy_url: str = "") -> dict[str, str] | None:
    if not proxy_url:
        return None
    return {
        "http": proxy_url,
        "https": proxy_url,
    }


def send_telegram_message(
    bot_token: str,
    chat_id: str,
    text: str,
    proxy_url: str = "",
    reply_markup: dict[str, Any] | None = None,
) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    response = requests.post(url, json=payload, timeout=25, proxies=_proxies(proxy_url))
    if response.status_code != 200:
        raise RuntimeError(
            f"Не удалось отправить сообщение в Telegram. "
            f"Код: {response.status_code}. Ответ: {response.text}"
        )


def send_long_telegram_message(
    bot_token: str,
    chat_id: str,
    text: str,
    proxy_url: str = "",
    reply_markup: dict[str, Any] | None = None,
    chunk_size: int = 3900,
) -> None:
    if len(text) <= chunk_size:
        send_telegram_message(bot_token, chat_id, text, proxy_url, reply_markup=reply_markup)
        return

    chunks: list[str] = []
    current = ""
    for line in text.splitlines():
        if len(current) + len(line) + 1 > chunk_size:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)

    for index, chunk in enumerate(chunks):
        send_telegram_message(
            bot_token,
            chat_id,
            chunk,
            proxy_url,
            reply_markup=reply_markup if index == len(chunks) - 1 else None,
        )


def get_updates(bot_token: str, offset: int | None = None, proxy_url: str = "", timeout: int = 30) -> list[dict[str, Any]]:
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    payload: dict[str, Any] = {"timeout": timeout}
    if offset is not None:
        payload["offset"] = offset
    response = requests.get(url, params=payload, timeout=timeout + 10, proxies=_proxies(proxy_url))
    if response.status_code != 200:
        raise RuntimeError(f"Не удалось получить updates. Код: {response.status_code}. Ответ: {response.text}")
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram вернул ошибку: {data}")
    return list(data.get("result", []))


def answer_callback_query(bot_token: str, callback_query_id: str, proxy_url: str = "", text: str = "") -> None:
    url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
    payload: dict[str, Any] = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    requests.post(url, json=payload, timeout=10, proxies=_proxies(proxy_url))
