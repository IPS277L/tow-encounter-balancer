# Документация проекта

Текущий контекст восстанавливается по [статусу](project-status.md), [открытым вопросам](open-questions.md), [политике источников](source-policy.md) и [roadmap](roadmap.md). Исторические отчёты: [статус](project-status-history.md), [вопросы и закрытые boundaries](open-questions-history.md). Они не задают текущую очередь работ.

## Правила и источники

- [Реестр книг и извлечений](source-index.md), [полный аудит PG 1.4 / GM 1.1](audits/rulebooks-1.4-1.1.md).
- [Нормализованные правила](rules/README.md), [трассировка книга → код → тест](rule-traceability.md), [противоречия и неоднозначности](contradictions.md).
- [Прототип game-rules](game-rules.md) имеет меньший приоритет, чем выбранные книги.

## Архитектура и контракты

- [Обзор и направление зависимостей](architecture/overview.md), [resolution kernel](architecture/resolution-kernel.md).
- [ADR](decisions/): [K1](decisions/ADR-0002-book-first-resolution-kernel.md), [ranged input](decisions/ADR-0013-ranged-minion-scenario-input.md), [melee](decisions/ADR-0021-melee-minion-scenario.md), [mixed](decisions/ADR-0028-mixed-minion-scenario.md).
- M8: [Casting](decisions/ADR-0035-cowardly-flight-casting-boundary.md), [интеграция](decisions/ADR-0036-magic-encounter-integration.md), [single-run](decisions/ADR-0037-magic-scenario-runner.md), [independent sequential simulation](decisions/ADR-0038-independent-magic-simulations.md), [process backend ADR-0039](decisions/ADR-0039-process-magic-simulations.md), [assessment/list contract ADR-0040](decisions/ADR-0040-magic-candidate-assessment.md) (pure assessment/list models реализованы; service ещё нет).

## Готовность и примеры

| Слой | Проверенная граница | Примеры |
| --- | --- | --- |
| K1/M2 | [Ядро](audits/k1-readiness.md), [первый ranged бой](audits/m2-readiness.md) | [Ranged JSON](examples/m4/README.md) |
| M3–M5 | [Массовый ranged](audits/m3-readiness.md), [JSON simulation](audits/m4-readiness.md), [внешний balance](audits/m5-external-readiness.md) | [M5](examples/m5/README.md) |
| M6 | [Melee simulation/balance JSON/CLI](audits/m6-external-readiness.md) | [M6](examples/m6/README.md) |
| M7 | [Mixed simulation/balance JSON/CLI](audits/m7-external-readiness.md) | [M7](examples/m7/README.md) |
| M8 | [Одиночный магический бой](audits/m8-encounter-readiness.md), [последовательная simulation](audits/m8-simulation-readiness.md), [общий аудит sequential/process](audits/m8-mass-simulation-readiness.md) | [M8](examples/m8/README.md), [production simulation](examples/m8/magic_simulation.py) |

[Тестирование](testing.md) и [benchmarks](benchmarks/README.md) содержат evidence отдельных границ. Наличие записи каталога или отдельного reducer не означает готовность полного сценария.


M8 performance: [ограниченный контракт](benchmarks/m8-profiling-contract.md), [исходный sequential baseline](benchmarks/m8-baseline-2026-10-26.md), [аудит и следующий шаг](audits/m8-profiling-readiness.md). Это измерение developer harness, не новый backend или оценка сложности.


M8 process contract: [аудит ADR-0039](audits/m8-process-contract-readiness.md), [конечный public transport probe](examples/m8/process_contract_probe.py) и [stored output](examples/m8/process_contract_probe.output.txt). Контрактный probe сохранён как историческая evidence; готовый scheduler проверен отдельными unit/real-spawn tests; [performance-сравнение](benchmarks/README.md#m8-sequential-и-spawn) завершено отдельно.


M8 process API: [production readiness](audits/m8-process-readiness.md), [самостоятельный пример](examples/m8/magic_parallel.py) и [stored output](examples/m8/magic_parallel.output.txt). Public calls сохраняют исходный scenario/result/summary, workers/batch_size выбираются явно.

M8 sequential/process performance: [методика](benchmarks/m8-parallel-comparison-contract.md), [100](benchmarks/m8-parallel-100-2026-10-27.md) / [1000 trials](benchmarks/m8-parallel-1000-2026-10-27.md), [проверка готовности среза](audits/m8-parallel-comparison-readiness.md). Локальные времена не определяют backend автоматически.
