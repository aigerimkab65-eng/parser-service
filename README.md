# parser-service

HTTP-сервис: на вход — URL, на выход — Markdown/текст и метаданные в JSON. Один образ — во всех проектах.

- **lite** — без браузера (быстрее, меньше образ)
- **full** — + Playwright Chromium для SPA

GitHub: `aigerimkab65-eng/parser-service` · образы: `ghcr.io/aigerimkab65-eng/parser-service:{version}-lite|full` (без `latest`)

---

## Compose-файлы

| Файл | Назначение |
|------|------------|
| `deploy/compose.yml` | Готовый образ из ghcr, без сборки; порт наружу не открыт (сеть `parser_net`) |
| `deploy/compose.caddy.yml` | Добавка HTTPS (Caddy) к `compose.yml` |
| `deploy/compose.local.yml` | Локальная проверка на Mac (arm64/amd64), порт `127.0.0.1:8000`, `APP_ENV=dev` |
| `deploy/compose.build.yml` | Сборка из исходников (разработка) |
| `deploy/compose.full.yml` | Вариант full + Playwright, `read_only` + `tmpfs` + `cap_drop: ALL` |

В корне репозитория compose-файлов нет.

---

## Быстрый старт на Mac

1. Установите и запустите [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2. Скопируйте env:

```bash
cp .env.example .env
```

3. Поднимите локально (сборка lite):

```bash
docker compose -f deploy/compose.local.yml up --build -d
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/version
```

4. Парсинг (ключ из `.env`):

```bash
API_KEY=dev-key-change-me ./examples/curl.sh https://example.com/
```

Остановка: `docker compose -f deploy/compose.local.yml down`

---

## Ключи и APP_ENV

| Режим | Поведение |
|-------|-----------|
| `APP_ENV=dev` | Учебный ключ `dev-key-change-me` допустим (только локально) |
| `APP_ENV=production` (по умолчанию) | Без сильного `API_KEYS` (≥32 символов) сервис **не стартует** |

```bash
openssl rand -hex 32
```

---

## Готовый образ (другой проект)

```bash
export API_KEYS="$(openssl rand -hex 32)"
docker compose -f deploy/compose.yml up -d
# другие сервисы в сети parser_net → http://parser:8000
```

Фрагмент для своего compose: `examples/docker-compose.snippet.yml`.

Клиент на Python: `examples/python_client.py`.

---

## API

| Метод | Путь | Ключ |
|-------|------|------|
| `GET` | `/health` | нет |
| `GET` | `/version` | нет |
| `POST` | `/v1/parse` | `X-API-Key` |
| `POST` | `/v1/parse/batch` | `X-API-Key` (до 10 URL) |

Схема: [`openapi.json`](openapi.json).

---

## Сборка образа вручную

```bash
docker build \
  --build-arg VARIANT=lite \
  --build-arg VERSION=1.0.0 \
  --build-arg GIT_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo local)" \
  -t parser-service:1.0-lite .
```

`VERSION` / `GIT_COMMIT` попадают в env и в OCI-метки (`org.opencontainers.image.version` / `revision`), а также в `GET /version`.

---

## Безопасность контейнера

Во всех compose: `read_only: true`, `tmpfs: /tmp`, `cap_drop: [ALL]`, `no-new-privileges`.  
Для full Playwright пишет во временные каталоги под `/tmp` (`TMPDIR`/`HOME=/tmp`).

---

## Разработка без Docker

```bash
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -r requirements.txt
APP_ENV=dev API_KEYS=dev-key-change-me hypercorn app.main:app --bind 127.0.0.1:8000
pytest -q
```

---

## CI / лицензии Actions

Workflows: `.github/workflows/ci.yml`, `publish.yml`.  
Каждый `uses:` закреплён **полным SHA** коммита; в комментарии — тег версии и SPDX-лицензия (MIT / Apache-2.0).  
Секрет-скан в CI — **gitleaks CLI (MIT)**; action gitleaks не используем (у него коммерческая лицензия).

---

## Лицензия

MIT — см. `LICENSE`. Сторонние пакеты: `THIRD_PARTY_LICENSES.md`.
