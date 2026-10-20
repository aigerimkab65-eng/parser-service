# Third-party licenses

## Прямые зависимости (MIT / Apache-2.0)

| Пакет | Версия | Лицензия |
|-------|--------|----------|
| fastapi | 0.143.3 | MIT |
| pydantic | 2.14.1 | MIT |
| Hypercorn | 0.18.0 | MIT License |
| aiohttp | 3.14.5 | Apache-2.0 AND MIT |
| trafilatura | 2.3.1 | Apache-2.0 |
| cachetools | 7.2.2 | MIT |
| pytest | 9.1.1 | MIT |
| pip-licenses | 5.5.5 | MIT |
| playwright | 1.55.0 | Apache-2.0 (только VARIANT=full, в lite не установлен) |

## Все установленные пакеты (pip-licenses)

| Name | Version | License | URL |
|------|---------|---------|-----|
| aiohappyeyeballs | 2.7.1 | Python Software Foundation License |  |
| aiohttp | 3.14.5 | Apache-2.0 AND MIT |  |
| aiosignal | 1.4.0 | Apache Software License |  |
| annotated-doc | 0.0.5 | MIT |  |
| annotated-types | 0.8.0 | MIT |  |
| anyio | 4.15.1 | MIT |  |
| attrs | 26.1.0 | MIT |  |
| babel | 2.18.0 | BSD License |  |
| cachetools | 7.2.2 | MIT |  |
| certifi | 2026.7.22 | Mozilla Public License 2.0 (MPL 2.0) |  |
| charset-normalizer | 3.5.2 | MIT |  |
| courlan | 1.4.0 | Apache-2.0 |  |
| dateparser | 1.4.3 | BSD-3-Clause |  |
| fastapi | 0.143.3 | MIT |  |
| frozenlist | 1.8.0 | Apache-2.0 |  |
| h11 | 0.16.0 | MIT License |  |
| h2 | 4.4.1 | MIT |  |
| hpack | 4.2.0 | MIT |  |
| htmldate | 1.11.0 | Apache-2.0 |  |
| Hypercorn | 0.18.0 | MIT License |  |
| hyperframe | 6.1.0 | MIT License |  |
| idna | 3.20 | BSD-3-Clause |  |
| iniconfig | 2.3.1 | MIT |  |
| jusText | 3.0.2 | BSD License |  |
| lxml | 6.1.3 | BSD-3-Clause |  |
| lxml_html_clean | 0.4.5 | BSD-3-Clause |  |
| multidict | 7.1.0 | Apache-2.0 |  |
| opentelemetry-api | 1.45.1 | Apache-2.0 |  |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |  |
| pluggy | 1.7.0 | MIT License |  |
| priority | 2.0.0 | MIT License |  |
| propcache | 0.5.4 | Apache-2.0 |  |
| pydantic | 2.14.1 | MIT |  |
| pydantic_core | 2.50.1 | MIT |  |
| Pygments | 2.21.0 | BSD-2-Clause |  |
| pytest | 9.1.1 | MIT |  |
| python-dateutil | 2.9.0.post0 | Apache Software License; BSD License |  |
| pytz | 2026.5 | MIT License |  |
| regex | 2026.9.29 | Apache-2.0 AND CNRI-Python |  |
| six | 1.17.0 | MIT License |  |
| starlette | 1.8.0 | BSD-3-Clause |  |
| tld | 0.13.2 | MPL-1.1 OR GPL-2.0-only OR LGPL-2.1-or-later |  |
| trafilatura | 2.3.1 | Apache-2.0 |  |
| typing-inspection | 0.4.4 | MIT |  |
| typing_extensions | 4.16.0 | PSF-2.0 |  |
| tzlocal | 5.4.4 | MIT |  |
| urllib3 | 2.8.0 | MIT |  |
| wsproto | 1.3.2 | MIT |  |
| yarl | 1.25.1 | Apache-2.0 |  |

## Косвенные зависимости с лицензиями не MIT/Apache-2.0

### Решение (принято)

1. **`tld` (MPL-1.1 OR GPL-2.0-only OR LGPL-2.1-or-later)**  
   Используется по лицензии **MPL-1.1** (выбор из тройной лицензии).  
   Файлы пакета `tld` **не изменяются**. Зависимость тянется через `courlan` → `trafilatura`.

2. **BSD / PSF / MPL-2.0** (ниже) — **разрешены**; коммерческое использование допускается.  
   Пакеты не заменялись вручную.

| Пакет | Версия | Лицензия | Решение |
|-------|--------|----------|---------|
| aiohappyeyeballs | 2.7.1 | PSF | разрешено |
| babel | 2.18.0 | BSD | разрешено |
| certifi | 2026.7.22 | MPL-2.0 | разрешено |
| dateparser | 1.4.3 | BSD-3-Clause | разрешено |
| idna | 3.20 | BSD-3-Clause | разрешено |
| jusText | 3.0.2 | BSD | разрешено |
| lxml | 6.1.3 | BSD-3-Clause | разрешено |
| lxml_html_clean | 0.4.5 | BSD-3-Clause | разрешено |
| Pygments | 2.21.0 | BSD-2-Clause | разрешено (dev) |
| starlette | 1.8.0 | BSD-3-Clause | разрешено |
| tld | 0.13.2 | MPL-1.1 *(выбрана)* | MPL-1.1, без правок файлов |
| typing_extensions | 4.16.0 | PSF-2.0 | разрешено |
