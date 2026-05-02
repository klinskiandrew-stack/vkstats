from __future__ import annotations

import requests


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }

    response = requests.post(url, json=payload, timeout=40)
    if response.status_code != 200:
        raise RuntimeError(
            f"Не удалось отправить сообщение в Telegram. "
            f"Код: {response.status_code}. Ответ: {response.text}"
        )
