# TOWR Encounter Balancer

Расширяемый симулятор боёв и инструмент подбора сложности столкновений для настольной RPG TOWR.

Книжное ядро K1 и M2 готовы для заявленного неподвижного ranged Minion-сценария: проверка входа, явные решения, исполнение до исхода или общего лимита и отчёт с источниками. M3 поддерживает последовательные независимые прогоны и опциональный [запуск в процессах](docs/decisions/ADR-0015-process-ranged-simulations.md) с одинаковыми seeds и агрегатами исходов, атак и раундов. Конкретный Blunderbuss multi-target подключён отдельным композиционным путём; полный каталог и универсальный бой пока не реализованы. Границы: [аудит K1](docs/audits/k1-readiness.md), [аудит M2](docs/audits/m2-readiness.md), [контракт сценария](docs/decisions/ADR-0013-ranged-minion-scenario-input.md). Актуальный следующий шаг и проверки — в [`docs/project-status.md`](docs/project-status.md).

## Навигация

[Конечный аудит M4](docs/audits/m4-readiness.md) подтверждает готовность Schema, чистых адаптеров, application service и CLI simulate в указанной границе сценария. [JSON-контракт v1](docs/decisions/ADR-0016-ranged-simulation-json-v1.md) поддерживает явный выбор sequential/process и кодирование ошибок. Для [первого M5](docs/decisions/ADR-0017-ranged-candidate-assessment.md) реализована оценка явного списка кандидатов с бюджетом и выбором подходящих top_k: точная доля достижения цели за лимит, отдельные остановки и явное окно без пресетов. Подбор доступен через typed Python API и CLI balance. [Поэтапная оценка](docs/decisions/ADR-0018-staged-ranged-evaluation.md) реализована: промежуточное уточнение, общий бюджет повторных прогонов и полные отчёты этапов. Генератор численности по [ADR-0019](docs/decisions/ADR-0019-ranged-composition-generation.md) реализован: явный резерв участников, неизменные профили/решения, предел составов и полный staged budget. Первый M5 закрыт [аудитом](docs/audits/m5-readiness.md) в текущем scope; [typed пример](docs/examples/m5/README.md) проверен в sequential/process. Контракт [JSON balance v1 / CLI balance](docs/decisions/ADR-0020-ranged-balance-json-v1.md) реализован полностью в текущем scope: Schema/adapters, application service, кодирование ошибок и CLI balance. Внешняя граница M5 закрыта [аудитом](docs/audits/m5-external-readiness.md). Для выбранного M6 принят [ADR-0021](docs/decisions/ADR-0021-melee-minion-scenario.md): неподвижный ближний бой Minions с явным Close и динамическим численным преимуществом. Typed вход NpcMeleeScenario реализован: чистый допуск состава, явных фактов и решений. Одиночный Melee-сценарий закрыт [аудитом](docs/audits/m6-readiness.md); [полный typed пример](docs/examples/m6/README.md) проверен через production runner. По [ADR-0022](docs/decisions/ADR-0022-independent-melee-simulations.md) реализованы последовательные независимые Melee-прогоны и aggregate summary: отдельная seed scheme, новый RNG на trial, четыре исхода и compact records. [Первый performance-срез Melee](docs/benchmarks/README.md#однократная-minion-defeat-continuation) завершён: continuation строится один раз с сохранением проверок, trial digests/агрегаты совпали с baseline. [ADR-0023](docs/decisions/ADR-0023-process-melee-simulations.md) реализован: опциональный Melee process runner, явный spawn, bounded queue и прежние seed/result/summary; равенство sequential проверено в реальных процессах. [Сравнение sequential/process](docs/benchmarks/README.md#melee-sequential-и-spawn) завершено: результаты совпали, расходы spawn заметны на 100 trials; на 1000 два workers быстрее в измеренных 2×2/3×2. [Аудит массовой Melee-симуляции](docs/audits/m6-simulation-readiness.md) завершён: sequential/process, summary и измерения готовы в текущем scope. [ADR-0024](docs/decisions/ADR-0024-melee-candidate-assessment.md) реализован в части pure assessment одного Melee-кандидата: exact source, четыре Fraction rates, общий ObjectiveRateWindow и unsupported/window guards. Модели ограниченного списка с бюджетом, полным source-bound отчётом и stable Fraction top_k реализованы. Application evaluator исполняет список через existing sequential/process APIs, сохраняет candidate ID/cause при ошибке и возвращает только полный отчёт с агрегатами. [Аудит bounded Melee evaluation](docs/audits/m6-evaluation-readiness.md) завершён; [самостоятельный пример](docs/examples/m6/melee_evaluation.py) проверен в sequential/process. [Контракт ADR-0025](docs/decisions/ADR-0025-staged-melee-evaluation.md) подготовлен: полные повторные пакеты, верхний бюджет, отдельные continuation/final selection и exact report chain. Pure continuation helper и frozen staged models реализованы: 17 deterministic tests покрывают preflight, бюджет, порядок и exact report chain. Staged application service/error реализованы: existing bounded evaluator на каждом этапе, exact source до продолжения, stage/candidate/cause и остановка без partial/retry/fallback. [Аудит staged Melee evaluation](docs/audits/m6-staged-evaluation-readiness.md) завершён; [самостоятельный пример](docs/examples/m6/melee_staged_evaluation.py) проверен в sequential/process. [Контракт генерации ADR-0026](docs/decisions/ADR-0026-melee-composition-generation.md) подготовлен: явный резерв и family facts/GM policies, детерминированные составы и полный staged budget. Конечный constructor probe проверен. MeleeCompositionGroup/MeleeCandidateGenerationRequest реализованы: frozen/slotted вход, точное разбиение резерва, отдельные family facts/Zone/escape path, seed/stages/window и пределы C/полного budget до перебора. 13 deterministic tests прошли. Pure generator, source-bound result и typed generation error реализованы: полные согласованные составы, неизменные решения GM, exact source guards и ошибки без partial result. Добавлены 14 tests (всего generation 27). Integration генерация → staged evaluation проверена: полные sequential/process reports, повтор/rename prefix и бюджет совпадают; scripted RNG подтверждает динамический outnumbering и True/False GM flags. Добавлены 5 integration tests (всего generation 32). [Аудит генерации Melee](docs/audits/m6-generation-readiness.md) завершён; [самостоятельный пример](docs/examples/m6/melee_balance.py) проверен в sequential/process. [Контракт Melee JSON/CLI ADR-0027](docs/decisions/ADR-0027-melee-json-cli-v1.md) подготовлен: отдельные simulate-melee/balance-melee, явные facts/GM policies, aggregate simulation и staged balance outputs. [Конечные примеры](docs/examples/m6/json/README.md) проверены через typed APIs; simulation Schema/command и pure parser/summary encoder реализованы, добавлены 25 tests с ranged regression. Simulation service/error encoder и команда simulate-melee реализованы; module/console и оба backend проверены в установленном wheel. Следующий срез — balance Schema/models и pure adapters; balance-melee пока отсутствует.

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

## Пример подбора составов

[Исполняемый пример M5](docs/examples/m5/README.md) генерирует пять составов и оценивает их в два этапа. Из корня репозитория:

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m5/ranged_balance.py --mode sequential
.venv/Scripts/python.exe docs/examples/m5/ranged_balance.py --mode process
```

Вход задан в Python: фиксированный резерв Minions, явные факты и решения ведущего, seed 42 и бюджет 136 прогонов. Тот же резерв доступен через [JSON/CLI balance](docs/examples/m5/json/README.md).

## Подбор из JSON

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m towr balance docs/examples/m5/json/balance-v1.request.json
```

После установки проекта: `.venv/Scripts/towr.exe balance INPUT`. INPUT — UTF-8 файл или `-` для stdin. Режим sequential/process, seed, окно и бюджеты задаются в JSON. Stdout содержит полный aggregate result либо error envelope; stderr — диагностику. Коды: 0 — полный результат (включая no_eligible_candidates/пустой выбор), 2 — input/usage, 3 — generation/execution, 4 — I/O. [Формат и ограничения](docs/decisions/ADR-0020-ranged-balance-json-v1.md).

## Ближний бой через JSON/CLI

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m towr simulate-melee docs/examples/m6/json/melee-simulation-v1.request.json
```

После установки текущего проекта: `towr simulate-melee INPUT`. INPUT — UTF-8 файл или `-` для stdin. [Пример](docs/examples/m6/json/README.md) явно задаёт numeric Minion profiles, Close/facts, решения GM, seed/trials/round budget и backend. Для процессов задайте `"execution": {"mode": "process", "workers": 2, "batch_size": 3}`. Stdout содержит полный JSON со сводкой без отдельных trial records; коды 0/2/3/4 означают result, input/usage, execution и I/O. [Контракт](docs/decisions/ADR-0027-melee-json-cli-v1.md). Ranged-команды `simulate` и `balance` сохраняют свои форматы; `balance-melee` ещё не реализована.
