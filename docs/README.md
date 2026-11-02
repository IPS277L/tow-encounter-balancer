# Документация проекта

Текущий контекст восстанавливается по [статусу](project-status.md), [открытым вопросам](open-questions.md), [политике источников](source-policy.md) и [roadmap](roadmap.md). Исторические отчёты: [статус](project-status-history.md), [вопросы и закрытые boundaries](open-questions-history.md). Они не задают текущую очередь работ.

## Правила и источники

- [Реестр книг и извлечений](source-index.md), [полный аудит PG 1.4 / GM 1.1](audits/rulebooks-1.4-1.1.md).
- [Нормализованные правила](rules/README.md), [трассировка книга → код → тест](rule-traceability.md), [противоречия и неоднозначности](contradictions.md).
- [Прототип game-rules](game-rules.md) имеет меньший приоритет, чем выбранные книги.

## Архитектура и контракты

[ADR-0056](decisions/ADR-0056-source-bound-crushed-rib-owner-bridge.md) закрыт для ручного M8 full-owner bridge после55. [Actual63d10](examples/m8/crushed_rib_owner.py), [copied test](../tests/integration/test_m8_crushed_rib_owner_example.py),62targeted checks и installed477files/8commands прошли; [приёмка](audits/m8-crushed-rib-owner-readiness.md) фиксирует составное4158покрытие и33прежние errors отдельно. [Probe25d10](examples/m8/crushed_rib_owner_contract_probe.py) сохранён как исторический contract proof. Automatic dispatcher/journal/policy и transport потребуют отдельной вехи.

[ADR-0055](decisions/ADR-0055-source-bound-crushed-rib-test.md) реализован для K1 injury-bound Crushed Rib10: pure preparation, actual ordinary/Casting Test, strict completion и exact-injury apply. [Actual33d10](examples/m8/crushed_rib_test.py), copied tests и [installed audit](audits/m8-crushed-rib-test-readiness.md) прошли; полная регрессия4110tests/33known errors/0failures завершена. M8 full-owner admission остаётся отдельной границей.

[ADR-0054](decisions/ADR-0054-repeated-leg-spasm-generation-and-magic-json-v4.md) реализован: matching generation assertion, обе Magic JSON/CLI v4 families, required nullable repeated permission и strict source/error metadata. [Production proof96d10](examples/m8/repeated_leg_spasm_transport_contract_probe.py), copied unittest и [итоговый installed/regression аудит](audits/m8-repeated-leg-spasm-transport-readiness.md) завершены. JSON1/2/3 сохраняют lossless отказ.

[ADR-0053](decisions/ADR-0053-native-repeated-leg-spasm-continuation.md) реализован: отдельное nullable разрешение, bounded cursor вне battle root и exact full witness membership собственного prefix. [Automatic пример330d10](examples/m8/repeated_leg_spasm_runner.py), [native/installed audit](audits/m8-native-repeated-leg-spasm-readiness.md); [исходный proof86d10](examples/m8/repeated_leg_spasm_native_contract_probe.py) сохраняет old-policy controls. Generation и JSON4 подключены ADR-0054 с отдельным matching assertion; JSON1/2/3 новое nonNone явно отвергают.

Реализован low-level [ADR-0052](decisions/ADR-0052-source-bound-repeated-leg-spasm-stand.md) для повторного Leg Spasm после подтверждённого stand48: [actual-bound пример](examples/m8/repeated_leg_spasm_stand.py), [аудит](audits/m8-repeated-leg-spasm-stand-readiness.md), [исходный contract proof](examples/m8/repeated_leg_spasm_contract_probe.py). Automatic runner/policy подключены отдельным ADR-0053; сравнение следующих consumers — в [inventory](audits/m8-continuation-inventory.md).

[ADR-0051](decisions/ADR-0051-stationary-wound-generation-and-magic-json-v3.md) закрыт [итоговым source/wheel/installed аудитом](audits/m8-stationary-wound-transport-readiness.md): [native generation](audits/m8-stationary-wound-generation-readiness.md), [simulation3](audits/m8-simulation-v3-readiness.md), [balance3](audits/m8-balance-v3-readiness.md), [public JSON](examples/m8/json/README.md) и [probe](examples/m8/stationary_wound_transport_contract_probe.py). Закрытые prerequisites: [native ADR-0050](audits/m8-native-stationary-wound-readiness.md), [low-level ADR-0049](audits/m8-stationary-leg-spasm-readiness.md) и [stand ADR-0048](audits/m8-leg-spasm-stand-readiness.md).

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

[ADR-0047](decisions/ADR-0047-opt-in-generation-and-magic-json-v2.md), этапы1–3 реализованы: отдельное family opt-in подтверждение, full template equality и полная policy в каждом subset; [аудит generation](audits/m8-opt-in-generation-readiness.md). Simulation JSON v2 сохраняет nullable/full policy и версию request/result/error через прежнюю CLI-команду; [аудит simulation v2](audits/m8-simulation-v2-readiness.md), [входной пример](examples/m8/json/magic-simulation-v2.request.json). [Balance v2](audits/m8-balance-v2-readiness.md) сохраняет отдельные reserve/family assertions, полный source chain и phase errors; [вход](examples/m8/json/magic-balance-v2.request.json). [Проверочный пример](examples/m8/opt_in_transport_contract_probe.py) использует настоящий opted generator и обе v2 families, без temporary legacy views. [Итоговый installed audit](audits/m8-opt-in-transport-readiness.md) завершён:455files,12magic schemas,95child commands, обе magic и шесть прежних routes. ADR-0047 закрыт; v1 неизменен.
