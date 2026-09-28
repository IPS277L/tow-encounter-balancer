# Конечный аудит M3

Дата: 2026-09-28. Рабочее дерево на старте чистое. Аудит сопоставляет текущий production-код, тесты и сохранённые измерения; он не расширяет сценарий книги.

**Вывод: четыре критерия M3 выполнены для допущенного неподвижного ranged Minion-сценария. Можно переходить к M4.** Это не готовность универсального боя, полного каталога или балансировщика.

## Матрица roadmap

| Критерий | Реализация | Проверка | Вывод |
| --- | --- | --- | --- |
| Независимые seeds | [npc_ranged_models.py](../../src/towr/simulation/npc_ranged_models.py): SHA-256 scheme v1, master seed/index; [npc_ranged_simulation.py](../../src/towr/simulation/npc_ranged_simulation.py): новый RNG каждого trial | [Unit](../../tests/unit/test_m3_npc_ranged_simulation.py): golden vectors и границы uint64; [integration](../../tests/integration/test_m3_npc_ranged_simulation.py): reverse order, larger prefix, дополнительные броски одного trial не сдвигают другой, global RNG сохранён | Выполнено; PRNG independence — техническое разделение потоков, не доказательство математической независимости |
| Агрегированные метрики | NpcRangedTrialSummary, NpcRangedSimulationResult, OutcomeCounts: четыре исхода, суммы и средние Attack/visited rounds, проверка всех indices/seeds/budgets | Те же unit/integration: точные outcomes/counters на injected d10, отдельный UNSUPPORTED_PATH, отсутствующие/чужие/повторные записи и ошибки | Выполнено; ни ROUND_LIMIT, ни UNSUPPORTED_PATH не считаются победой/ничьей |
| Воспроизводимость независимо от параллелизма | [npc_ranged_parallel.py](../../src/towr/simulation/npc_ranged_parallel.py): absolute indices, spawn, явные workers/batch_size, bounded queue, общий result constructor | [5 unit](../../tests/unit/test_m3_npc_ranged_parallel.py): reverse completion, неполный хвост, guards/cancel/error; [3 integration](../../tests/integration/test_m3_npc_ranged_parallel.py): реальные процессы 1/2, batches 1/3, три состава, injected RNG/ошибка, prefix и cleanup | Выполнено на Python 3.14.5 / Windows; Python 3.12 и другие ОС в этой сессии не проверены |
| Profiling до оптимизаций | [profile_m3.py](../../tools/profile_m3.py), исходный baseline, однократная Attack state projection, отдельный [wall-clock harness](../../tools/benchmark_m3_parallel.py) | [4 profiling tests](../../tests/unit/test_m3_profiling.py), [2 comparison tests](../../tests/unit/test_m3_parallel_benchmark.py); отчёты 100/1000 trials и совпадение records | Выполнено; оптимизация выбрана по измерениям, source/replay guards сохранены |

## Измерения и практические пределы

[Исходный baseline](../benchmarks/m3-baseline-2026-09-28.md) разделяет обычное время, tracemalloc и cProfile. [Первый performance-срез](../benchmarks/m3-cached-attack-state-2026-09-28.md) сохраняет все три trial digests; в 2×2 число replace calls из проекции Attack уменьшилось с 4334 до 1798. Это локальное сохранение immutable результата, без отключения validation.

[100 trials](../benchmarks/m3-spawn-100-2026-09-28.md) и [1000 trials](../benchmarks/m3-spawn-1000-2026-09-28.md) сравнивают sequential и fresh spawn pool с workers 1/2, batch_size 32, seed 20260928, budget 5 и тремя повторами. Время включает создание и завершение пула. Каждый режим/повтор сравнивает полные compact records; на 100 trials SHA-256 совпадают также с исходным baseline. Отчёты повторно не запускались в ходе аудита: production-код с их получения не изменён.

На 100 trials spawn медленнее. На 1000 trials два workers дают локальное отношение sequential/process 1,353 для 2×2, 1,217 для 3×2, 1,003 для 1×1. Последняя разница практически отсутствует. Автоматический выбор backend или обещание ускорения для любого входа этими измерениями не обоснованы.

Память compact результата растёт с числом trials; ограниченная очередь не делает его потоковым. Tracemalloc baseline не является RSS; общая память дочерних процессов не измерялась. Миллионы trials, большие составы, постоянный pool и более двух workers в benchmark не проверялись. Эти ограничения записаны, но не являются дополнительными критериями закрытия четырёх пунктов текущего M3.

## Игровая и техническая граница

Сохраняется [ADR-0013](../decisions/ADR-0013-ranged-minion-scenario-input.md): здоровые Minions, одна numeric Shooting Medium–Long/2H и Athletics Protection, unmodified Tests, явные facts и GM-approved defeat policies, SUFFER_WOUND, свежий первый раунд и общий бюджет. Нет автоматической awareness, Reload/движения/Recover, Brute/Champion/Monstrosity, autonomous Blunderbuss или full catalogue.

Матрица проверяет существующие [ADR-0014](../decisions/ADR-0014-independent-ranged-simulations.md) и [ADR-0015](../decisions/ADR-0015-process-ranged-simulations.md). Compact records сохраняют числовые наблюдения, но не полные источники решений, конечные injury snapshots или криптографическое доказательство бросков. RNG factory с внешним состоянием может нарушить replay; process factory должна быть importable/picklable. Ошибка не становится игровым outcome или частичным успешным пакетом; завершение ждёт уже running children. Timeout/hard-kill/retry/checkpoint не реализованы.

## Проверка аудита и переход

Повторно выполнен полный набор: **1797 tests OK**, Python 3.14.5. В том числе настоящий spawn, а не mock-only проверка. Compileall и git diff --check успешны. Домен/движок/симулятор в этом срезе не менялись.

Минимальный wire contract M4 определён в [ADR-0016](../decisions/ADR-0016-ranged-simulation-json-v1.md), с конкретными JSON-примерами. Первым implementation-срезом будут JSON Schema и pure adapters к существующему typed input/result; затем application service и CLI. JSON не должен принимать внутренние histories/receipts или подменять NpcRangedScenario admission. Новые игровые правила и балансировщик не входят в переход.
