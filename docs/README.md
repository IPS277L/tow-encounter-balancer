# Документация проекта

Текущий контекст восстанавливается по [статусу](project-status.md), [открытым вопросам](open-questions.md), [политике источников](source-policy.md) и [roadmap](roadmap.md). Исторические отчёты: [статус](project-status-history.md), [вопросы и закрытые boundaries](open-questions-history.md). Они не задают текущую очередь работ.

## Правила и источники

- [Реестр книг и извлечений](source-index.md), [полный аудит PG 1.4 / GM 1.1](audits/rulebooks-1.4-1.1.md).
- [Нормализованные правила](rules/README.md), [трассировка книга → код → тест](rule-traceability.md), [противоречия и неоднозначности](contradictions.md).
- [Прототип game-rules](game-rules.md) имеет меньший приоритет, чем выбранные книги.

## Архитектура и контракты

- [Обзор и направление зависимостей](architecture/overview.md), [resolution kernel](architecture/resolution-kernel.md).
- [ADR](decisions/): [K1](decisions/ADR-0002-book-first-resolution-kernel.md), [ranged input](decisions/ADR-0013-ranged-minion-scenario-input.md), [melee](decisions/ADR-0021-melee-minion-scenario.md), [mixed](decisions/ADR-0028-mixed-minion-scenario.md).
- M8: [Casting](decisions/ADR-0035-cowardly-flight-casting-boundary.md), [интеграция](decisions/ADR-0036-magic-encounter-integration.md), [single-run](decisions/ADR-0037-magic-scenario-runner.md), [independent sequential simulation](decisions/ADR-0038-independent-magic-simulations.md), [process backend ADR-0039](decisions/ADR-0039-process-magic-simulations.md), [generation contract ADR-0042](decisions/ADR-0042-magic-composition-generation.md) (реализован; [общий аудит](audits/m8-generation-readiness.md) завершён), [staged ADR-0041](decisions/ADR-0041-staged-magic-evaluation.md) (helper/models/service реализованы; [общий аудит](audits/m8-staged-evaluation-readiness.md) завершён), [assessment/list contract ADR-0040](decisions/ADR-0040-magic-candidate-assessment.md) (pure assessment/list/service реализованы; [общий аудит](audits/m8-evaluation-readiness.md) завершён).

## Готовность и примеры

| Слой | Проверенная граница | Примеры |
| --- | --- | --- |
| K1/M2 | [Ядро](audits/k1-readiness.md), [первый ranged бой](audits/m2-readiness.md) | [Ranged JSON](examples/m4/README.md) |
| M3–M5 | [Массовый ranged](audits/m3-readiness.md), [JSON simulation](audits/m4-readiness.md), [внешний balance](audits/m5-external-readiness.md) | [M5](examples/m5/README.md) |
| M6 | [Melee simulation/balance JSON/CLI](audits/m6-external-readiness.md) | [M6](examples/m6/README.md) |
| M7 | [Mixed simulation/balance JSON/CLI](audits/m7-external-readiness.md) | [M7](examples/m7/README.md) |
| M8 | [Одиночный магический бой](audits/m8-encounter-readiness.md), [последовательная simulation](audits/m8-simulation-readiness.md), [общий аудит sequential/process](audits/m8-mass-simulation-readiness.md), [bounded evaluation](audits/m8-evaluation-readiness.md) | [M8](examples/m8/README.md), [production simulation](examples/m8/magic_simulation.py) |

[Тестирование](testing.md) и [benchmarks](benchmarks/README.md) содержат evidence отдельных границ. Наличие записи каталога или отдельного reducer не означает готовность полного сценария.


M8 performance: [ограниченный контракт](benchmarks/m8-profiling-contract.md), [исходный sequential baseline](benchmarks/m8-baseline-2026-10-26.md), [аудит и следующий шаг](audits/m8-profiling-readiness.md). Это измерение developer harness, не новый backend или оценка сложности.


M8 process contract: [аудит ADR-0039](audits/m8-process-contract-readiness.md), [конечный public transport probe](examples/m8/process_contract_probe.py) и [stored output](examples/m8/process_contract_probe.output.txt). Контрактный probe сохранён как историческая evidence; готовый scheduler проверен отдельными unit/real-spawn tests; [performance-сравнение](benchmarks/README.md#m8-sequential-и-spawn) завершено отдельно.


M8 process API: [production readiness](audits/m8-process-readiness.md), [самостоятельный пример](examples/m8/magic_parallel.py) и [stored output](examples/m8/magic_parallel.output.txt). Public calls сохраняют исходный scenario/result/summary, workers/batch_size выбираются явно.

M8 sequential/process performance: [методика](benchmarks/m8-parallel-comparison-contract.md), [100](benchmarks/m8-parallel-100-2026-10-27.md) / [1000 trials](benchmarks/m8-parallel-1000-2026-10-27.md), [проверка готовности среза](audits/m8-parallel-comparison-readiness.md). Локальные времена не определяют backend автоматически.

M8 JSON/CLI: [ADR-0043 и матрица реализации](decisions/ADR-0043-magic-json-cli-v1.md), [шесть конечных JSON-примеров](examples/m8/json/README.md), [mapping probe](examples/m8/json_contract_probe.py) / [stdout](examples/m8/json_contract_probe.output.txt). Simulation pure wire реализован: три Schema/command/shared mapper/strict parser/summary encoder/input errors. Simulation service/error encoder/CLI `simulate-magic` также реализованы; balance pure wire (три Schema/command/result/parser/result encoder) также реализован; balance service/error encoder/CLI также реализованы; общий аудит обоих magic families завершён; см. readiness ниже.

M8 JSON/CLI закрыт [общим аудитом ADR-0043](audits/m8-external-readiness.md): полная field/guard matrix,138implementation tests +contract probe, шесть packaged Schema, installed parity и явные ограничения fresh Wizard/Curse. [Инвентаризация continuations](audits/m8-continuation-inventory.md) завершена; выбран [контракт ADR-0044](decisions/ADR-0044-dead-champion-turn-exclusion.md) исключения оставшегося хода погибшего Wizard. [Finite probe](examples/m8/dead_champion_contract_probe.py) проверяет устранённый dead-awaiting gap, completed-target и missing-scene controls. Первый production срез реализован: [frozen модели](../src/towr/domain/npc_roster_dead_champion_models.py) и [pure exclusion/apply](../src/towr/rules/npc_roster_dead_champion_resolution.py). Journal/runner integration реализована; full Attack witness и обязательная последовательность проверяются до end-turn. [Propagation и итоговый аудит ADR-0044](audits/m8-dead-champion-readiness.md) завершены:7дополнительныхtests, актуальный installed wheel и [default-RNG JSON witness](examples/m8/json/dead-champion-v1.request.json).


Следующий low-level Miscast consumer: [ADR-0045](decisions/ADR-0045-source-bound-unnatural-wind.md), [public proof](examples/m8/unnatural_wind_contract_probe.py) / [stdout](examples/m8/unnatural_wind_contract_probe.output.txt). Preparation и one-roll реализованы: explicit decline/five facts, source-bound prepared/rolled pending, exact-source apply и dispatch/terminal guards. Rolled diagnosis — MISCAST_EFFECT; Pool сохраняется для любой строки. Wind21/22 с actual Prone applications и Pool0 после всех targets реализован; [общий low-level аудит](audits/m8-unnatural-wind-readiness.md) завершён, [самостоятельный пример](examples/m8/unnatural_wind.py) и installed parity444files проверены. Current Prone/runner stops сохраняются.


Завершённый контракт: [ADR-0046](decisions/ADR-0046-opt-in-miscast-runner-and-prone.md), [finite proof](examples/m8/miscast_runner_contract_probe.py) / [stdout](examples/m8/miscast_runner_contract_probe.output.txt). Реализованы explicit policy/admission, lossless generation/wire rejection, stand/end, Casting/Curse, Shooting/Protection и safe Broken+Prone Recover. Этап 3 реализован: closed journal с typed origin witness и автоматический opt-in runner. Этап 4 завершён: [propagation/installed/full audit](audits/m8-opt-in-miscast-readiness.md), [public opted example](examples/m8/opted_miscast.py).

[ADR-0047](decisions/ADR-0047-opt-in-generation-and-magic-json-v2.md), этапы1–2 реализованы: отдельное family opt-in подтверждение, full template equality и полная policy в каждом subset; [аудит generation](audits/m8-opt-in-generation-readiness.md). Simulation JSON v2 сохраняет nullable/full policy и версию request/result/error через прежнюю CLI-команду; [аудит simulation v2](audits/m8-simulation-v2-readiness.md), [входной пример](examples/m8/json/magic-simulation-v2.request.json). [Проверочный пример](examples/m8/opt_in_transport_contract_probe.py) использует настоящий opted generator и simulation v2 round-trip; только balance v2 остаётся ручным отображением. Следующий шаг — balance v2 при неизменном v1, затем общий installed audit.
