# TOWR Encounter Balancer

Симулятор боёв и инструмент подбора сложности столкновений для настольной RPG TOWR.

Готовы ограниченные неподвижные ranged, melee и mixed Minion-сценарии: одиночные бои, независимые sequential/process прогоны, агрегаты, поэтапный подбор и генерация составов из заданного резерва, JSON/CLI. Магия M8 поддерживает отдельный ограниченный бой с одним Champion-Wizard и Curse of Cowardly Flight, а также независимые последовательные прогоны и aggregate-only summary. Полный каталог и универсальный бой ещё не реализованы.

## Навигация

- [Актуальный статус, ограничения, проверки и следующий шаг](docs/project-status.md).
- [Открытые вопросы и действующие допущения](docs/open-questions.md).
- [Документация и нормативные источники](docs/README.md), [иерархия источников](docs/source-policy.md), [трассировка правил](docs/rule-traceability.md).
- [Архитектура](docs/architecture/overview.md), [roadmap](docs/roadmap.md).
- Внешние границы: [ranged](docs/audits/m5-external-readiness.md), [melee](docs/audits/m6-external-readiness.md), [mixed](docs/audits/m7-external-readiness.md).
- Магия: [single-run](docs/audits/m8-encounter-readiness.md), [simulation ADR-0038](docs/decisions/ADR-0038-independent-magic-simulations.md), [примеры](docs/examples/m8/README.md).

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

После установки текущего проекта: `towr simulate-melee INPUT`. INPUT — UTF-8 файл или `-` для stdin. [Пример](docs/examples/m6/json/README.md) явно задаёт numeric Minion profiles, Close/facts, решения GM, seed/trials/round budget и backend. Для процессов задайте `"execution": {"mode": "process", "workers": 2, "batch_size": 3}`. Stdout содержит полный JSON со сводкой без отдельных trial records; коды 0/2/3/4 означают result, input/usage, execution и I/O. [Контракт](docs/decisions/ADR-0027-melee-json-cli-v1.md). Ranged-команды `simulate` и `balance` сохраняют свои форматы; `balance-melee` доступна для Melee reserve/generation/evaluation JSON.

## Подбор Melee-составов через JSON/CLI

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m towr balance-melee docs/examples/m6/json/melee-balance-v1.request.json
```

После установки текущего проекта: `towr balance-melee INPUT`. INPUT — UTF-8 файл или `-` для stdin. [Пример](docs/examples/m6/json/README.md) задаёт резерв, группы численности, отдельные family facts/GM policies, stages/window, полный budget и backend. Вывод содержит каталог всех составов и полные aggregate reports этапов. Exit 0 включает пустой итоговый выбор и unsupported observations; 2 — input/usage, 3 — generation/execution, 4 — I/O. Ошибки содержат внешний request ID и известный candidate/counts либо stage context. [Контракт](docs/decisions/ADR-0027-melee-json-cli-v1.md).

Следующее направление — **M7: смешанный дальний и ближний бой**. Подготовлены [контракт](docs/decisions/ADR-0028-mixed-minion-scenario.md) и [проверочный пример](docs/examples/m7/README.md); typed admission реализован и проверен 25 tests. Одиночный сценарий закрыт [аудитом](docs/audits/m7-readiness.md): 60 tests M7 и [самостоятельный пример](docs/examples/m7/mixed_scenario.py) проверены. [Контракт независимых mixed-прогонов и summary](docs/decisions/ADR-0029-independent-mixed-simulations.md) реализован: отдельная seed scheme, последовательные прогоны и aggregate summary; 25 новых tests проверяют четыре исхода и воспроизводимость. [Аудит последовательной simulation](docs/audits/m7-simulation-readiness.md) завершён; [production-пример](docs/examples/m7/mixed_simulation.py) и сохранённый вывод проверены. [Профилирование mixed-пакетов](docs/benchmarks/README.md#m7-исходное-профилирование-mixed-simulation) завершено; [кандидат оптимизации continuation](docs/benchmarks/m7-round-continuation-review.md) отклонён по измерениям, production восстановлен. [Контракт опционального mixed process runner](docs/decisions/ADR-0030-process-mixed-simulations.md) реализован: отдельный typed API с bounded spawn и 17 новыми tests. [Сравнение sequential/process](docs/benchmarks/README.md#mixed-sequential-и-spawn) завершено: records/summary равны, на 100 trials spawn медленнее; локальное преимущество двух workers на 1000 подтверждено для 3×2/2×2. [Общий аудит массовой mixed-симуляции](docs/audits/m7-mass-simulation-readiness.md) завершён: sequential/process, summary и измерения согласованы. [Контракт оценки mixed-кандидатов ADR-0031](docs/decisions/ADR-0031-mixed-candidate-assessment.md) и [конечный probe](docs/examples/m7/assessment_contract_probe.py) подготовлены; pure assessment одного кандидата реализован с 9 unit и 1 real-spawn integration test. [Модели списка](src/towr/balance/mixed_evaluation_models.py) с бюджетом, полным отчётом и ранжированием реализованы (11 tests). [Application evaluator](src/towr/application/mixed_evaluation_service.py) и ошибки реализованы (8 unit/3 integration tests). Оценка явного mixed-списка доступна через typed Python API; JSON/CLI ещё нет. [Аудит оценки mixed-списка](docs/audits/m7-evaluation-readiness.md) завершён; [самостоятельный пример](docs/examples/m7/mixed_evaluation.py) и сохранённый вывод проверены. [Контракт ADR-0032](docs/decisions/ADR-0032-staged-mixed-evaluation.md) и [конечный probe](docs/examples/m7/staged_contract_probe.py) подготовлены: полные повторные пакеты, верхний бюджет, отдельные continuation/final selection и exact report chain. [Pure helper](src/towr/balance/mixed_staged_evaluation.py) и [frozen staged models](src/towr/balance/mixed_staged_evaluation_models.py) реализованы: 19 deterministic tests. [Staged service/error](src/towr/application/mixed_staged_evaluation_service.py) реализованы: 9 unit/3 real-backend integration tests, полный source до продолжения и stage/candidate/cause context. [Аудит staged mixed evaluation](docs/audits/m7-staged-evaluation-readiness.md) завершён; [самостоятельный пример](docs/examples/m7/mixed_staged_evaluation.py) и вывод проверены. [Контракт ADR-0033](docs/decisions/ADR-0033-mixed-composition-generation.md) и [конечный probe](docs/examples/m7/generation_contract_probe.py) подготовлены: явный резерв, family facts/pairs/policies, полный бюджет и отказ при недопустимом поднаборе. [Group/request preflight](docs/decisions/ADR-0033-mixed-composition-generation.md#реализованный-первый-срез) реализован: 15 deterministic tests, C/полный бюджет без materialization. [Генератор/result/error](docs/decisions/ADR-0033-mixed-composition-generation.md#реализованный-второй-срез) реализованы: 17 новых tests, полные проекции, source guards и отказ без пропуска недопустимого состава. [Integration генератора](docs/decisions/ADR-0033-mixed-composition-generation.md#сквозная-integration) проверена: 6 новых tests, равные sequential/process reports, повтор/rename prefix, полный scripted budget и динамический локальный outnumbering. [Аудит генерации](docs/audits/m7-generation-readiness.md) завершён; [самостоятельный пример](docs/examples/m7/mixed_balance.py) и сохранённый вывод проверены. [Контракт Mixed JSON/CLI ADR-0034](docs/decisions/ADR-0034-mixed-json-cli-v1.md) и [конечные примеры](docs/examples/m7/json/README.md) подготовлены: отдельные simulate-mixed/balance-mixed, explicit pairs/facts/actor policies, aggregate outputs и phase-specific errors. Simulation Schema/command/pure parser/summary encoder реализованы: 29 unit и 2 real-backend integration tests. Simulation service/errors/error encoder и simulate-mixed реализованы (39 новых tests). Balance Schema/command/result/pure parser/result encoder реализованы (38 новых tests). Balance service/application errors/error encoder и balance-mixed реализованы (41 новый test). [Общий аудит mixed JSON/CLI](docs/audits/m7-external-readiness.md) завершён; ADR-0034 закрыт в текущей границе numeric Minions.


## Смешанный бой из JSON

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m towr simulate-mixed docs/examples/m7/json/mixed-simulation-v1.request.json
.venv/Scripts/python.exe -m towr balance-mixed docs/examples/m7/json/mixed-balance-v1.request.json
```

После установки текущей версии доступна также `towr simulate-mixed INPUT`; `-` читает stdin. [Пример и ограничения](docs/examples/m7/json/README.md) задают неподвижный бой numeric Minions, явные Close/Medium пары, решения GM и seed/backend. Результат содержит сводку четырёх исходов. Подбор смешанных составов доступен через `towr balance-mixed INPUT`; результат содержит каталог составов, отчёты этапов и итоговый выбор.

## Магия: последовательные прогоны через Python API

```sh
PYTHONPATH=src python docs/examples/m8/magic_simulation.py
```

[Пример](docs/examples/m8/magic_simulation.py) использует public simulation API и соседний [builder одиночного боя](docs/examples/m8/magic_scenario.py). Он проверяет четыре исхода, свежий RNG на trial, полный source и воспроизводимость. [Вывод](docs/examples/m8/magic_simulation.output.txt) — finite scripted evidence, не оценка сложности.

ADR-0038 сохраняет текущий single-run scope и отдельный UNSUPPORTED_PATH. Magic process backend, метрика/подбор и JSON/CLI требуют последующих контрактов; неизвестные GM facts и обязательные неподдержанные эффекты не заменяются автоматическими решениями.
