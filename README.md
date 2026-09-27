# TOWR Encounter Balancer

Расширяемый симулятор боёв и инструмент подбора сложности столкновений для настольной RPG TOWR.

Книжный resolution kernel K1 проверен для заявленного numeric Melee/Shooting среза; начат M2, реализованы состав NPC, выбор и исполнение Minion Attack и координация одного раунда с явными остановками, исключение defeated Minion и ограниченный многораундовый прогон с внешним выбором следующего состава. Границы готовности указаны в [аудите K1](docs/audits/k1-readiness.md). Актуальное состояние, следующий шаг и проверенные команды находятся в [`docs/project-status.md`](docs/project-status.md).

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
