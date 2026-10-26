# Текущий статус проекта

Дата обновления: 2026-10-27.

## Текущий этап

**M8: общий аудит массовой magic simulation завершён.** [Readiness](audits/m8-mass-simulation-readiness.md) сопоставляет ADR-0038/0039, пять production modules, 131 existing test, public examples/installed parity и performance evidence. Исправлений src/tests/tools не потребовалось. Сохранены [методика](benchmarks/m8-parallel-comparison-contract.md), [harness](../tools/benchmark_m8_parallel.py), [сырые N100](benchmarks/m8-parallel-100-2026-10-27.md) / [N1000](benchmarks/m8-parallel-1000-2026-10-27.md), [интерпретация](benchmarks/README.md#m8-sequential-и-spawn) и [проверка готовности среза](audits/m8-parallel-comparison-readiness.md). На N100 процессы медленнее; на N1000 два workers локально быстрее двух боевых inputs в 1,506/1,547 раза. Zero-action control быстрее sequential. Общий порог выбора backend не вводится.

Работа идёт небольшими шагами до законченной вехи без подтверждений между ними; независимые tests/review делегируются с раздельным владением файлами, интеграцию ведёт главный агент. Режим закреплён в [AGENTS.md](../AGENTS.md#автономная-работа-до-согласованной-вехи). Commit/push выполняет пользователь.

## Зафиксировано

| Область | Готовность и граница |
| --- | --- |
| R1 | PG1.4/GM1.1 проиндексированы; [аудит книг](audits/rulebooks-1.4-1.1.md), [трассировка](rule-traceability.md) |
| K1 | Typed Tests/Attack/Wounds и выбранные action/movement/healing/Fate/Casting boundaries; [аудит](audits/k1-readiness.md). Полного каталога и универсального боя нет |
| M2–M7 | Ограниченные stationary ranged/melee/mixed numeric Minion encounters, sequential/process, summary/assessment/stages/generation, JSON/CLI; [M5](audits/m5-external-readiness.md), [M6](audits/m6-external-readiness.md), [M7](audits/m7-external-readiness.md) |
| M8 single-run | Один authored Champion-Wizard, Curse, allied/enemy Shooting Minions, explicit scene facts, owner/journal и continuations/end-turn; [аудит](audits/m8-encounter-readiness.md) |
| M8 sequential | Отдельная seed scheme, fresh input/RNG, full-source compact records, четыре исхода и aggregate-only summary; [ADR-0038](decisions/ADR-0038-independent-magic-simulations.md), [аудит](audits/m8-simulation-readiness.md) |
| M8 process | Strict preflight/transport/full-source-before-rebinding, lazy bound2W, fail-fast/cleanup; [ADR-0039](decisions/ADR-0039-process-magic-simulations.md), [аудит](audits/m8-process-readiness.md), [public пример](examples/m8/magic_parallel.py) |
| M8 mass audit | [Общий аудит](audits/m8-mass-simulation-readiness.md): источник/seed/source/aggregate/ошибки/cleanup и installed parity подтверждены; новые runtime contracts не добавлены |
| M8 performance | Historical [profiling](audits/m8-profiling-readiness.md) и новое сравнение N100/1000, workers1/2, batch32, seed20261026/B4/repeats3; все 54 measured full results/summary равны, input/global RNG/children и parent identity сохранены |

## Ограничения

- PG1.4/GM1.1 имеют приоритет над прототипом; [source policy](source-policy.md). В общем аудите напрямую перечитаны PG1.4 Combat112, Broken122, Magic/Miscasts157, Battle Magic/Curse162, Wounds190–191; GM1.1 Allies and Antagonists/Minions/Champions91–92. Игровые правила/Rule IDs и production не менялись.
- Numeric profiles/явные GM facts не заменяют полный NPC/spell/Talent/item каталог, PC-сценарии, универсальную тактику и battle orchestration. Открытые игровые вопросы — [здесь](open-questions.md).
- Magic runner поддерживает Curse, Broken Recover/Run и Stomach Blow → Drained expiry. Другие обязательные Wound/Miscast последствия, обычный Attack Give Ground, неизвестные scene/route/chronology остаются явными unsupported stops. Pending/history не очищаются для продолжения.
- Broken/другая Zone не defeat. Unsupported отдельно учитывается в N, не становится draw/loss/success и не фильтруется.
- Assessment/balance/generation и JSON/CLI M8 требуют отдельных последующих контрактов; public rates/means нет. Новые gameplay consumers, cache, auto backend и generic scheduler не добавлены.
- Замеры локальны для двух authored боевых workloads и отдельного zero-action control на CPython3.12.15/macOS26.5.1 arm64. CPU affinity/частота/внешняя нагрузка не контролировались. Другие runtime/ОС/inputs, RSS/память детей, workers/batch search, persistent pool и installed-wheel performance не измерены. Startup/import/serialization/normalization/shutdown и summary включены.
- 33 прежних dataclasses errors Python3.12 — отдельная задача; [причина](open-questions.md#проверки-dataclasses-на-python-312). Полный suite не зелёный; новые ошибки нельзя списывать на baseline.

## Следующий шаг

Подготовить ADR-0040 и конечный probe оценки magic-кандидатов: pure assessment по принятой метрике objective_achieved / все N с Fraction/window/unsupported guard и bounded evaluation явного списка. Зафиксировать exact input/summary source, общий budget preflight, aggregate-only полный report/stable ranking, explicit sequential/process и candidate errors; проверить минимальный reuse ObjectiveRateWindow/SimulationExecutionOptions без смешения families. Сначала контракт/probe, затем production assessment/list/service. Staged/generation/JSON/CLI и новые gameplay consumers отдельно.

## Последняя проверка

Текущий аудит: read-only сверка contracts/пяти modules/131 existing tests и AST boundaries 311 modules, прямая проверка локальных книг и performance manifest — блокеров нет. Исправлены только устаревшие описания готовности архитектуры и доступности GM Guide. Все 754 Python-файла src/tests/tools сохранены побайтно; новые tests не добавлялись. Последние relevant checks предыдущего среза: 17 harness tests OK (0,167 с), existing 34 fixture/profiling OK (0,323 с). N100 три digests/counts/actions/started/completed совпали с historical baseline; все 18 median rows проверены. 29 700 measured trials + 18 warm-up; контроль отдельно от боя.

Source/harness SHA-256 `f20131529ea476bfc61b3f37c29262b1dbe13f60cdca615b8f5c44e7dd55130d`: 396 files, весь src Python + profile_m8/fixtures/new harness. Совпадает до/после обоих запусков и независимо пересчитан при ревью. Production src/fixtures/tools/tests не менялись. Текущие 411 Python/Schema files побайтно равны установленному package и ранее собранному wheel; пять magic modules загружены из installed site-packages. Оба public examples исполнены на одном installed tree вне repo без PYTHONPATH: stdout равен stored output/stderr пуст. Wheel повторно не собирался; metadata README исторический. Evidence `/private/tmp/towr-m8-mass-installed-report.json`.

Последняя полная регрессия предыдущей вехи: **3162 tests / 33 прежних errors (97,704 с)**; в doc-only аудите неизменный набор не перезапускался. Counter полных error headers + exception signatures точно равен baseline предыдущей вехи; новых ошибок нет, полный suite не зелёный. Лог `/private/tmp/towr-m8-comparison-tests.log`. Текущие 2906 локальных Markdown-путей, 61 anchor, границы импортов 311 modules, whitespace и сохранность 754 Python-файлов — OK; новых benchmark-запусков нет.

Команды предыдущей регрессии и текущей файловой проверки:

```sh
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m unittest tests.unit.test_m8_parallel_benchmark -q
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m unittest discover -s tests -q
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m compileall -q src tests tools docs/examples/m8
git diff --check
```

## История и изменения

[Архив статуса](project-status-history.md) и [история вопросов](open-questions-history.md) сохраняют прежнюю evidence; текущие contracts/audits доступны через [индекс документации](README.md). Исходные книги перечислены в [source-index](source-index.md).

На старте аудита HEAD `1c5268a` (M8 P7) и 16 existing dirty/untracked файлов performance-вехи; они сохранены как исходные. В аудите добавлен общий readiness-документ, синхронизированы статус/индексы/архитектура и уточнена ссылка на GM Guide в нормализованных Wounds rules. Первоначальные Python/отчёты/методика сохранены побайтно; commit/push не выполнялись. Точный незакоммиченный diff доступен через `git status --short`.

Всего 22 незакоммиченных файла, включая 16 исходных. Шесть дополнительных путей аудита: docs/audits/m8-mass-simulation-readiness.md, docs/architecture/overview.md, docs/contradictions.md, docs/examples/m8/README.md, docs/rules/wounds-and-conditions.md и docs/source-index.md.
