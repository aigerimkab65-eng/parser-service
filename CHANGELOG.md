# Changelog

## 1.0.0 — 2026-10-20

- Упаковка для переиспользования: Docker lite/full, `deploy/` compose-файлы, `examples/`.
- `APP_ENV` + жёсткая проверка `API_KEYS` при старте (production не стартует со слабым ключом).
- `GET /version` — версия и commit из build args / OCI labels.
- GitHub Actions: pin по полному SHA, Trivy, публикация в ghcr без тега `latest`.
- Зависимости в образе только по lock-файлам с хешами (`--require-hashes`).
