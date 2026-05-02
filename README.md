# vkstats

Ежедневный отчет по откруту рекламного бюджета в новом рекламном кабинете VK Ads.

## Что умеет первая версия

- получает `access_token` через агентский доступ VK Ads;
- выводит список клиентов агентского кабинета;
- собирает расход за выбранную дату по клиентам агентства;
- отправляет отчет в Telegram.

## Настройка на сервере

```bash
git clone https://github.com/klinskiandrew-stack/vkstats.git
cd vkstats
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
```

В `.env` нужно заполнить реальные значения:

```env
VK_ADS_CLIENT_ID=...
VK_ADS_CLIENT_SECRET=...
VK_ADS_AGENCY_CLIENT_NAME=...
VK_ADS_API_BASE_URL=https://ads.vk.com/api/v2

TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
TIMEZONE=Europe/Moscow
CURRENCY_SYMBOL=₽
```

Секреты нельзя коммитить в GitHub. Файл `.env` уже добавлен в `.gitignore`.

## Проверка доступа к VK Ads

```bash
source venv/bin/activate
python -m app.main check-token
```

Ожидаемый результат:

```text
Доступ к VK Ads API работает.
Токен получен: **********...
```

## Проверка клиентов агентского кабинета

```bash
python -m app.main list-clients
```

## Отправка отчета в Telegram

За вчера:

```bash
python -m app.main send-report
```

За конкретную дату:

```bash
python -m app.main send-report --date 2026-05-01
```

## Запуск каждый день через cron

Открыть расписание:

```bash
crontab -e
```

Добавить строку для запуска каждый день в 09:00 по времени сервера:

```cron
0 9 * * * cd /opt/vkstats && /opt/vkstats/venv/bin/python -m app.main send-report >> /opt/vkstats/vkstats.log 2>&1
```

## Важный технический момент

Если запрос статистики вернет ошибку по адресу `/statistics/users/day.json`, нужно будет проверить фактический путь статистики в вашем доступе VK Ads. В коде специально вынесен `VK_ADS_API_BASE_URL`, чтобы можно было быстро переключить базовый адрес API без переписывания проекта.
