# TOWR Encounter Balancer

Расширяемый симулятор боёв и инструмент подбора сложности столкновений для настольной RPG TOWR.

Книжное ядро K1 и M2 готовы для заявленного неподвижного ranged Minion-сценария: проверка входа, явные решения, исполнение до исхода или общего лимита и отчёт с источниками. M3 поддерживает последовательные независимые прогоны и опциональный [запуск в процессах](docs/decisions/ADR-0015-process-ranged-simulations.md) с одинаковыми seeds и агрегатами исходов, атак и раундов. Конкретный Blunderbuss multi-target подключён отдельным композиционным путём; полный каталог и универсальный бой пока не реализованы. Границы: [аудит K1](docs/audits/k1-readiness.md), [аудит M2](docs/audits/m2-readiness.md), [контракт сценария](docs/decisions/ADR-0013-ranged-minion-scenario-input.md). Актуальный следующий шаг и проверки — в [`docs/project-status.md`](docs/project-status.md).

## Навигация

- [`docs/README.md`](docs/README.md) — карта документации;
- [`docs/game-rules.md`](docs/game-rules.md) — зафиксированные правила;
- [`docs/source-policy.md`](docs/source-policy.md) — приоритет книги и других источников;
- [`docs/architecture/overview.md`](docs/architecture/overview.md) — границы архитектуры;
- [`docs/architecture/resolution-kernel.md`](docs/architecture/resolution-kernel.md) — контракт K1;
- [`docs/open-questions.md`](docs/open-questions.md) — нерешённые вопросы;
- [`AGENTS.md`](AGENTS.md) — правила работы в новых сессиях.

## Локальная проверка

Требуется Python 3.12 или новее.

```powershell
$env:PYTHONPATH = "src"
py -3.12 -m unittest discover -s tests -v
```
