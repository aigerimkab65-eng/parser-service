# Безопасность parser-service

## Что уже защищено

| Угроза | Защита |
|--------|--------|
| SSRF (доступ к localhost / metadata / private IP) | Только `ip.is_global`; DNS rebinding-проверка в `SafeAsyncResolver`; ручные редиректы |
| Подбор API-ключа по времени | `hmac.compare_digest` |
| Злоупотребление API | `RATE_LIMIT_PER_MIN` на ключ |
| Огромные страницы / gzip-бомба | Лимит `MAX_PAGE_MB` по **распакованным** байтам → `TOO_LARGE` |
| robots.txt как DoS | Обрезка до 500 КБ |
| XSS / clickjacking UI | CSP, `X-Frame-Options: DENY`, `nosniff` |
| Утечка через кэш браузера | `Cache-Control: no-store` на `/v1/*` и `/ui/*` |
| Браузерный SSRF | По умолчанию `BROWSER_ENABLED=false` |

## Обязательно на VPS

1. Сгенерируй сильный ключ и пропиши в `.env`:

```bash
openssl rand -hex 32
# API_KEYS=<результат>
```

2. Оставь:

```env
BROWSER_ENABLED=false
DOCS_ENABLED=false
```

3. При необходимости спрячь тестовую панель:

```env
UI_ENABLED=false
```

4. Не публикуй порт `8000` наружу — только Caddy на 80/443.

## Известные ограничения

- В режиме Playwright DNS rebinding закрыт не полностью (браузер резолвит сам).
- Тестовая панель (`/` + `POST /ui/parse`) **не требует** API-ключа. Смягчения: rate limit по IP, блокировка cross-site/`Origin`, браузер только при `BROWSER_ENABLED=true` и галочке в UI. На публичном VPS лучше `UI_ENABLED=false` или basic auth в Caddy.
- Программный API (`/v1/parse`) по-прежнему требует заголовок `X-API-Key` по HTTPS.
