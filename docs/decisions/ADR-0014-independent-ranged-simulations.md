# ADR-0014: независимые последовательные прогоны M3

Статус: принято, 2026-09-28.

## Основание

[NpcRangedScenario](ADR-0013-ranged-minion-scenario-input.md) исполняется до terminal outcome либо технической остановки. Первый M3 повторяет этот сценарий с независимым RNG и агрегирует результаты. Игровые правила не меняются: BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112 задаёт раунды/ходы; BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91 отделяет defeat от выбранного disposition. Эти страницы непосредственно перепроверены. Seed, размер пакета и агрегаты являются техническими контрактами.

## Направление зависимостей

Новый пакет `towr.simulation` зависит от engine/domain/rules.RandomSource. Обратных зависимостей нет. `npc_ranged_models.py` хранит frozen input, компактные наблюдения и агрегаты; `npc_ranged_simulation.py` создаёт RNG и вызывает существующий executor. P1 BattleResult и прежняя статистика не используются.

## Seed и вход

`NpcRangedSimulationRequest(scenario, master_seed, trials)` принимает только допущенный NpcRangedScenario, master seed в `[0, 2**64)` и положительное число trials меньше `2**64`. Bool/строки/вещественные значения запрещены. Нулевой пакет отклоняется, поэтому средние не имеют неопределённого знаменателя.

`npc_ranged_trial_seed(master_seed, trial_index)` задаёт схему `towr:npc-ranged-trial:v1`: SHA-256 от ASCII имени схемы, одного нулевого байта, master seed как 8 байт unsigned big-endian и индекса как 8 байт unsigned big-endian. Digest читается как unsigned big-endian integer. `request.seed_for(index)` дополнительно проверяет `0 <= index < trials`. Алгоритм не использует Python hash(), состояние RNG, размер пакета или результаты предыдущих прогонов. Golden vectors закреплены в тестах; изменение encoding потребует новой версии схемы.

С одинаковыми master seed/index получается одинаковый trial seed при изменении размера пакета или порядка исполнения. Это отдельные детерминированные PRNG-потоки, а не доказательство математической независимости любых возможных последовательностей. По умолчанию используется новый `random.Random(seed)` на каждый trial; глобальный random state не используется. Полный replay требует тех же правил, scenario, RNG implementation и совместимой версии runtime, а не только стабильного SHA-256.

## Исполнение

`run_npc_ranged_trial(request, trial_index, *, rng_factory=Random)` исполняет один индекс; `run_npc_ranged_simulation(request, *, rng_factory=Random)` выполняет индексы `0..trials-1` последовательно. Фабрика внедряется для детерминированных fixtures и должна возвращать новый независимый RandomSource при каждом вызове. Произвольная пользовательская фабрика может нарушить этот контракт; автоматическое доказательство независимости её внутреннего состояния не производится.

Каждый запуск получает тот же immutable начальный scenario, без переноса его continuation между trials. Typed результат executor обязан принадлежать именно этому scenario. Его outcome, executed_attack_count и visited_round_count проецируются в NpcRangedTrialSummary; полный журнал освобождается перед следующим trial. Память результата линейна по числу компактных записей, а не по всем журналам боёв.

Ошибки executor/RNG распространяются вызывающему коду; пакет не выдаёт частичный набор за завершённый и не превращает исключение в проигрыш. UNSUPPORTED_PATH, возвращённый самим scenario runner, остаётся отдельным наблюдением. Для полной диагностики конкретного trial можно повторить scenario с seed этого индекса; сам пакет полную trace не хранит.

## Результат

`NpcRangedSimulationResult(source_request, trials)` принимает все индексы ровно по одному разу и возвращает записи в порядке индекса, даже если они собраны другим порядком. Проверяются типы, seed/index binding, полнота пакета и пределы counters по составу/бюджету; ROUND_LIMIT обязан посещать последний допустимый раунд. Record сохраняет index, derived seed, typed outcome, число Attack и посещённых раундов. Positional order при агрегации не влияет на результат.

`outcome_counts` возвращает NpcRangedOutcomeCounts с четырьмя отдельными полями: objective_achieved, side_defeated, round_limit, unsupported_path. `total_attack_count`, `total_visited_round_count`, `mean_attack_count`, `mean_visited_round_count` вычисляются из записей. Посещённый раунд может быть прерван terminal defeat; это не число полностью завершённых раундов.

Лимиты и неподдержанные пути не включаются в победы, поражения или выдуманную ничью. Вероятности, условные проценты и доверительные интервалы пока не вводятся. Компактные records не доказывают происхождение бросков: после удаления full journal доступны структурные проверки, а не полная source validation каждого исхода. Result не является криптографическим доказательством подлинности или механизмом защиты от повторной симуляции одного seed.

## Проверки и границы

[8 unit tests](../../tests/unit/test_m3_npc_ranged_simulation.py): golden seed vectors, валидация до фабрики RNG, четыре исхода/точные агрегаты, порядок/полнота/типы/бюджет, настоящий unsupported stop, чужой runner source и распространение ошибок. [3 integration tests](../../tests/integration/test_m3_npc_ranged_simulation.py): реальные исходы на заданных d10, точные счётчики, distinct RNG, immutable input, повторение/обратный порядок/расширение пакета, влияние разного числа бросков только на свой trial, сохранение глобального random state. Тесты не требуют точного Monte Carlo процента.

Полный набор: **1780 tests OK**, Python 3.14. M3 пока последовательный; фактический параллелизм не реализован и не проверен. Следующий срез — воспроизводимое профилирование репрезентативных пакетов до выбора оптимизаций или параллельного исполнения. CLI/JSON, балансировщик и расширение игрового сценария не входят в этот шаг.

## Профилирование до оптимизации

2026-09-28: developer harness tools/profile_m3.py измеряет неизменённый M3 отдельно через perf_counter, tracemalloc и cProfile. 1×1/2×2/3×2, 100 trials, seed 20260928, budget 5; все trial records совпали в каждом повторе/инструментированной фазе. Это не CLI приложения; src не менялся. [Методика и следующий срез](../benchmarks/README.md), [сырой отчёт](../benchmarks/m3-baseline-2026-09-28.md). По replace callers выбран узкий кандидат: однократное построение NpcRosterAttackExecutionResult.state без ослабления validation. Оптимизация пока не выполнена; memory/time trade-off нужно измерить. Полный набор 1784 tests OK, включая 4 новых harness tests.

Первый performance-срез завершён: однократная derived roster Attack state ([контракт ADR-0008](ADR-0008-npc-roster-boundary.md#однократная-проекция-результата-attack)). Trial digests/агрегаты всех трёх cases совпали; [время/память и ограничения](../benchmarks/README.md#однократное-построение-attack-state). Полный набор 1787 tests OK. Следующий шаг — отдельный опциональный process-based runner с тем же source/seed/result контрактом; его реализация и проверка ещё впереди.

## Опциональный process runner

Реализован отдельным API без изменения sequential contracts: [ADR-0015](ADR-0015-process-ranged-simulations.md). Реальные spawn workers сохраняют каждый trial record независимо от разбиения; ошибки не превращаются в исходы, полные журналы не передаются. Все четыре исхода сохраняются прежним result constructor. Полный набор 1797 tests OK; [wall-clock сравнение](../benchmarks/README.md#сравнение-последовательного-режима-и-spawn) включает новый pool при каждом запуске.
