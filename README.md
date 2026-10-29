# 🚗 GeorgianCars API

> Бэкенд агрегатора объявлений о продаже авто из грузинских Telegram-каналов: MTProto-инжест, LLM-парсинг постов и читающее API с фильтрами, фасетами и избранным.

![Python](https://img.shields.io/badge/Python-3.13+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?style=flat&logo=fastapi&logoColor=white)
![Beanie](https://img.shields.io/badge/Beanie_ODM-2.1-47A248?style=flat&logo=mongodb&logoColor=white)
![Pyrofork](https://img.shields.io/badge/Pyrofork-2.3+-26A5E4?style=flat&logo=telegram&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-2.13-E92063?style=flat&logo=pydantic&logoColor=white)
![uv](https://img.shields.io/badge/uv-managed-DE5FE9?style=flat&logo=uv&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-compose-2496ED?style=flat&logo=docker&logoColor=white)

## 🧭 Как это устроено

Две половины, связанные через MongoDB:

```
Telegram-каналы ──▶ ingest (pyrofork + LLM-парсер) ──▶ MongoDB ──▶ FastAPI ──▶ фронтенд
                          │
                          └──▶ data/images/{listing}/**.webp  (статика /images)
```

1. **Инжест** (`src/ingest/`, `src/scripts/ingest_channel.py`) — MTProto-клиент забирает свежие посты канала, текст поста прогоняется через LLM-парсер (`QwenParser` — любой OpenAI-совместимый `/v1/chat/completions`, по умолчанию Ollama + `qwen2.5:7b`), из ответа собирается документ `Listing` со стабильным публичным ID `tg-{channel}-{msg_id}` и дедупликацией повторов.
2. **Read API** (`src/server.py` + `src/routers/`) — FastAPI-приложение: листинги с фильтрами/сортировками/пагинацией, фасеты, избранное, сохранённые поиски, карта городов.

## ✨ Возможности

- 🤖 **LLM-парсинг объявлений** — марка/модель/год/цена/пробег/топливо/КПП/кузов/город/фичи из свободного текста поста; посты «не про продажу» отсекаются
- 🖼️ **Фото постов** — media group скачивается целиком, конвертируется в WebP (Pillow) и раздаётся как статика `/images/...`
- 🔍 **Фильтры и текстовый поиск** — диапазоны цены/года/пробега/мощности, мультивыбор марок/моделей/городов и т.д.; `q` идёт через взвешенный Mongo text index
- 📊 **Сортировки** — `newest`, `cheap`, `expensive`, `mileage_asc`, `year_desc`, `year_asc`, `best_deal`, `bargain`
- 🏷️ **Фасеты** — счётчики значений фильтров с in-process кэшем (5 мин) поверх HTTP-кэша
- ⭐ **Избранное и сохранённые поиски** — привязка к устройству через заголовок `X-Device-Id` (без регистрации), у сохранённого поиска считаются «свежие» совпадения
- 🗺️ **Карта** — агрегация объявлений по городам Грузии с координатами центров
- 🚀 **Продуманный wire-формат** — camelCase JSON (snake_case в Python), `Cache-Control: public, max-age=30, stale-while-revalidate=120` на горячих ручках
- ♻️ **Идемпотентный инжест** — дедупликация по `id_code`, повторный прогон канала ничего не задваивает

## 🛠️ Стек

| Слой | Технологии |
|---|---|
| API | FastAPI, Uvicorn (+uvloop на Linux/macOS) |
| БД | MongoDB (Beanie ODM, PyMongo) |
| Telegram | Pyrofork (MTProto, импортируется как `pyrogram`) |
| Парсинг | OpenAI-совместимый LLM-endpoint (Ollama / Qwen по умолчанию), aiohttp |
| Изображения | Pillow (WebP) |
| Тулинг | uv, Ruff, ty |

## 🚀 Запуск

### Локально

```bash
uv sync
cp .env.example .env
uv run src/main.py          # API на SERVER_HOST:SERVER_PORT (по умолчанию 0.0.0.0:8000)
```

Swagger UI: `http://localhost:8000/docs`

### Инжест канала

```bash
# 1) Один раз: логин в Telegram (API-ключи с my.telegram.org → TG_API_ID / TG_API_HASH в .env)
uv run src/scripts/tg_login.py

# 2) Забрать посты и сложить в Mongo (LLM-endpoint должен быть доступен, см. QWEN_*)
uv run src/scripts/ingest_channel.py [channel_id] [--limit N] [--dry-run]
```

`channel_id` — «голый» ID канала без префикса `-100`. `--dry-run` парсит и логирует без записи в БД.

### Docker

Compose поднимает API и MongoDB 8 и ждёт одну **внешнюю** сеть — общую с фронтендом:
```bash
docker network create cars-backend
docker compose up --build
```
API слушает порт 80 внутри compose-сети (hostname `cars-api`) и наружу не публикуется — подключается через reverse-proxy в сети `cars-backend`. Сессии и изображения — в `./data/`, база — в томе `mongo`.

### Линт и типы

```bash
uv run ruff check . && uv run ruff format .
uv run ty check
```

## ⚙️ Переменные окружения

`.env` в корне (см. `.env.example`):

| Переменная | По умолчанию | Описание |
|---|---|---|
| `MONGO_URL` | `mongodb://localhost:27017` | Строка подключения MongoDB |
| `MONGO_DB` | `georgiancars` | Имя базы |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | JSON-список origin'ов фронтенда |
| `JWT_SECRET` | — | Зарезервировано (auth ещё не подключён) |
| `DEBUG` | `true` | Debug-режим FastAPI/логов |
| `SERVER_HOST` / `SERVER_PORT` | `0.0.0.0` / `8000` | Адрес API |
| `TG_API_ID` / `TG_API_HASH` | — | Ключи приложения Telegram (my.telegram.org), нужны для инжеста |
| `TG_SESSION_NAME` | `georgiancars` | Имя файла сессии |
| `TG_SESSION_DIR` | `data/sessions` | Каталог сессий (не коммитить) |
| `QWEN_BASE_URL` | `http://localhost:11434/v1` | OpenAI-совместимый endpoint LLM |
| `QWEN_API_KEY` | — | Bearer-ключ для облачного endpoint'а; пусто для Ollama и т.п. |
| `QWEN_MODEL` | `qwen2.5:7b` | Модель для парсинга |
| `QWEN_TIMEOUT` | `600` | Таймаут запроса к LLM, сек |
| `QWEN_THINKING` | `false` | Режим «размышлений» модели |

## 📡 API

Ответы — camelCase JSON. Публичный ID объявления — `id_code` вида `tg-{channelId}-{msgId}`.

### Листинги

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/listings` | Страница объявлений: `page`, `pageSize`, `sort`, `q`, `priceFrom/To`, `yearFrom/To`, `mileageFrom/To`, `powerFrom/To`, `makes`, `models`, `fuels`, `trans`, `drives`, `bodies`, `cities`, `colors`, `channel`, `vinOnly`, `priceOnly`, `bargain`, `customsCleared` |
| `GET` | `/listings/by-ids?id=...&id=...` | Пакетная выборка по ID |
| `GET` | `/listings/{id}` | Одно объявление |
| `GET` | `/listings/{id}/similar` | Похожие (по марке/кузову) |
| `GET` | `/facets` | Значения фильтров со счётчиками |

### Персональное (заголовок `X-Device-Id` обязателен, ≥8 символов)

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/favorites` / `/favorites/ids` | Избранные объявления / только их ID |
| `POST` / `DELETE` | `/favorites/{listingId}` | Добавить / убрать из избранного |
| `GET` / `POST` | `/saved-searches` | Список / создание сохранённого поиска |
| `PATCH` / `DELETE` | `/saved-searches/{id}` | Изменение / удаление |
| `POST` | `/saved-searches/{id}/run` | Выполнить поиск, посчитать новые совпадения |

### Прочее

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/map/cities` | Города с координатами и количеством объявлений |
| `GET` | `/map/cities/{name}/listings` | Объявления города |
| `GET` | `/images/...` | Статика фотографий (WebP) |
| `GET` | `/health` | Проверка живости |

## 📁 Структура

```
src/
├── main.py            # entrypoint: uvicorn (+uvloop на Linux/macOS)
├── server.py          # FastAPI-приложение, CORS, статика /images, роутеры
├── settings.py        # pydantic-settings из .env
├── db.py              # подключение Beanie + регистрация документов
├── deps.py            # X-Device-Id, пагинация, нормализация фильтров
├── tg.py              # фабрика pyrofork-клиента
├── ingest/            # parsers (LLM), photos (WebP), pipeline (упаковка в Listing)
├── models/            # Listing, Channel, Favorite, SavedSearch, ProcessedPost, User
├── routers/           # listings, facets, favorites, saved_searches, map, health
├── schemas/           # CamelModel и схемы ответов
├── services/          # filters (Mongo-запросы), sorting, pricing
└── scripts/           # tg_login, ingest_channel (CLI)
```
