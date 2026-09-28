# TOWR Encounter Balancer

Расширяемый симулятор боёв и инструмент подбора сложности столкновений для настольной RPG TOWR.

Книжное ядро K1 и M2 готовы для заявленного неподвижного ranged Minion-сценария: проверка входа, явные решения, исполнение до исхода или общего лимита и отчёт с источниками. M3 поддерживает последовательные независимые прогоны и опциональный [запуск в процессах](docs/decisions/ADR-0015-process-ranged-simulations.md) с одинаковыми seeds и агрегатами исходов, атак и раундов. Конкретный Blunderbuss multi-target подключён отдельным композиционным путём; полный каталог и универсальный бой пока не реализованы. Границы: [аудит K1](docs/audits/k1-readiness.md), [аудит M2](docs/audits/m2-readiness.md), [контракт сценария](docs/decisions/ADR-0013-ranged-minion-scenario-input.md). Актуальный следующий шаг и проверки — в [`docs/project-status.md`](docs/project-status.md).

## Навигация

[Конечный аудит M4](docs/audits/m4-readiness.md) подтверждает готовность Schema, чистых адаптеров, application service и CLI simulate в указанной границе сценария. [JSON-контракт v1](docs/decisions/ADR-0016-ranged-simulation-json-v1.md) поддерживает явный выбор sequential/process и кодирование ошибок. Для [первого M5](docs/decisions/ADR-0017-ranged-candidate-assessment.md) реализована оценка явного списка кандидатов с бюджетом и выбором подходящих top_k: точная доля достижения цели за лимит, отдельные остановки и явное окно без пресетов. Это typed Python API; CLI balance пока отсутствует. [Поэтапная оценка](docs/decisions/ADR-0018-staged-ranged-evaluation.md) реализована: промежуточное уточнение, общий бюджет повторных прогонов и полные отчёты этапов. Генератор численности по [ADR-0019](docs/decisions/ADR-0019-ranged-composition-generation.md) реализован: явный резерв участников, неизменные профили/решения, предел составов и полный staged budget. Следующий шаг — сквозной аудит первого M5 и воспроизводимый пример генерации → поэтапной оценки.

- [`docs/README.md`](docs/README.md) — карта документации;
- [`docs/game-rules.md`](docs/game-rules.md) — зафиксированные правила;
- [`docs/source-policy.md`](docs/source-policy.md) — приоритет книги и других источников;
- [`docs/architecture/overview.md`](docs/architecture/overview.md) — границы архитектуры;
- [`docs/architecture/resolution-kernel.md`](docs/architecture/resolution-kernel.md) — контракт K1;
- [`docs/open-questions.md`](docs/open-questions.md) — нерешённые вопросы;
- [`AGENTS.md`](AGENTS.md) — правила работы в новых сессиях.

## Локальная проверка

Требуется Python 3.12 или новее. Установить проект и зависимости JSON Schema в локальное окружение:

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -e .
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

## Запуск симуляции

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m towr simulate docs/examples/m4/ranged-v1.request.json
```

После установки текущего проекта также доступна `.venv/Scripts/towr.exe simulate INPUT`. `INPUT` — путь к UTF-8 JSON или `-` для stdin. [Пример входа](docs/examples/m4/ranged-v1.request.json) содержит режим, seed, trials и все решения; CLI не переопределяет их. Для процессов задайте в JSON `"execution": {"mode": "process", "workers": 2, "batch_size": 1}`.

Stdout содержит один UTF-8 JSON result или typed error; краткая диагностика идёт в stderr. Exit codes: 0 — полный результат (включая round_limit/unsupported_path), 2 — неверный JSON/admission или аргументы CLI, 3 — ошибка исполнения, 4 — I/O. При ошибке аргументов или чтения файла stdout пуст. [Подробный контракт и ограничения вывода](docs/decisions/ADR-0016-ranged-simulation-json-v1.md#cli-simulate).
