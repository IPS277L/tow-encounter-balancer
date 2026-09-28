# ADR-0022: независимые последовательные Melee-прогоны и summary

Статус: принято и реализовано, 2026-09-28, в последовательной typed границе ниже.

## Основание и граница

Одиночный [Melee-сценарий ADR-0021](ADR-0021-melee-minion-scenario.md) закрыт [аудитом](../audits/m6-readiness.md). Этот срез повторяет его независимо и проецирует результат в компактные записи и агрегаты. Игровой допуск, тактика, kernel и runner не меняются. Непосредственно перепроверены BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112 (раунд/ход/действие), BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91 (defeat и отдельный disposition). Seed и агрегаты — технические контракты, не новые игровые правила.

`simulation` зависит от engine/domain и RandomSource. Обратных зависимостей нет. Отдельные Melee-типы не наследуются от ranged, не принимают ranged outcome по совпадению строк Enum. Форматы ranged v1 и их seed vectors сохраняются. Узкая структура повторяет [ADR-0014](ADR-0014-independent-ranged-simulations.md); универсальный battle aggregate/runner не вводится ради двух конкретных входов.

## Request и seed

Frozen/slotted `NpcMeleeSimulationRequest(scenario, master_seed, trials)` требует допущенный NpcMeleeScenario, master_seed в `[0, 2**64)`, trials в `[1, 2**64)`, только int без bool/числовых преобразований. До фабрики RNG проверяются request и trial index. `request.seed_for(index)` требует `0 <= index < trials`.

`npc_melee_trial_seed(master_seed, trial_index)` использует отдельное имя **towr:npc-melee-trial:v1**. SHA-256 получает ASCII имени, один нулевой байт, затем master_seed и index как два unsigned 8-byte big-endian числа. Digest читается как unsigned big-endian integer. Самостоятельный seed helper допускает оба числа в `[0, 2**64)`. Encoding не зависит от размера/порядка пакета, Python hash или предыдущих бросков. Golden vectors закреплены тестами; изменение схемы требует новой версии.

Каждый trial получает новый `Random(seed)` по умолчанию или RNG из внедрённой `rng_factory(seed)`. Фабрика обязана создавать отдельный поток; её произвольное внутреннее состояние автоматически не проверяется. Это детерминированные PRNG-потоки, не доказательство математической независимости. Replay требует того же scenario, правил и совместимого RNG/runtime.

Golden vectors (digest в hex):

| master_seed | trial_index | digest |
| --- | --- | --- |
| 0 | 0 | `5b39eabd5df1551b171c1963c122aaf06212cf18ff96228cbf99058b6cdf025a` |
| 42 | 7 | `5a4f78db8322628e7e3bccb5ae31de9e2366d42af0863c7b0ffabfb0b0f35a9a` |
| 2**64-1 | 2**64-1 | `87b6716704f2dcc45432d4440b0f449574903119ad6d409113a980bc10760236` |

## Исполнение и компактный результат

`run_npc_melee_trial(request, trial_index, *, rng_factory=Random)` вызывает existing run_npc_melee_scenario с исходным immutable scenario. Проверяет typed NpcMeleeScenarioResult и exact source_scenario, затем возвращает frozen/slotted `NpcMeleeTrialSummary(trial_index, seed, outcome, executed_attack_count, visited_round_count)`.

Outcome берётся из **scenario result после terminal suffix**, не из последнего raw runner stop. Attack count и visited rounds берутся из runner_report: подтверждение defeat не является дополнительной атакой, resume не является новым раундом, посещённый раунд может быть не завершён. Новое наблюдение не исполняет kernel повторно. Full journal не удерживается компактным trial.

`run_npc_melee_simulation(request, *, rng_factory=Random)` исполняет индексы `0..trials-1` последовательно. Каждый trial начинает с того же initial, continuation между боями не переносится. Ошибки RNG/executor/type/source распространяются, без retry/fallback и без выдачи partial result за полный. UNSUPPORTED_PATH, возвращённый runner, остаётся отдельным наблюдением.

Frozen/slotted `NpcMeleeSimulationResult(source_request, trials)` копирует records в tuple и сортирует по index. Требуются все индексы ровно один раз и правильный seed. Проверяются typed outcome, неотрицательные integer counters без bool, положительные visited rounds, terminal с хотя бы одной Attack, верхние границы `visited <= budget`, `attacks <= initial_actors * visited`; ROUND_LIMIT обязан достичь budget. Это структурные пределы, не повторное доказательство боевой истории.

`NpcMeleeOutcomeCounts` разделяет objective_achieved, side_defeated, round_limit, unsupported_path. Result вычисляет counts, total/mean Attack и visited rounds. Лимит не является ничьей, unsupported не является поражением. Результат хранит O(trials) компактных записей, не все журналы. Ограничение uint64 не является практической квотой памяти/времени.

## Aggregate-only summary

`summarize_npc_melee_simulation(result)` — чистая проекция в frozen/slotted `NpcMeleeSimulationSummary(source_request, outcome_counts, total_attack_count, total_visited_round_count)`. Ни records, ни result, ни journals не сохраняются. Source request остаётся точным входом; trials/means вычисляются.

Проверяются типы, сумма counts = trials, неотрицательные integer totals без bool. Если B — budget, N — trials, L — round_limit count, A — начальная численность, T — число terminal outcomes: `L*B + N-L <= total_rounds <= N*B`, `T <= total_attacks <= A*total_rounds`. Нулевые Attack допустимы для технической остановки. Эти проверки не удостоверяют происхождение агрегата или RNG после удаления records.

Будущий balance получает только input/summary. Подтверждённая метрика M5 сохраняется: цель за budget, denominator = все trials, отдельный round_limit, unsupported делает оценку непригодной. Сам Melee evaluator/generator не добавляется этим ADR. Не добавляются process backend, CLI/JSON, streaming/checkpoint, новые метрики/presets, движение/PC/каталог.

## Проверки и продолжение

Требуются golden seeds и их отличие от ranged v1, invalid input до RNG, полнота/порядок/source/counter guards, frozen copies, четыре outcomes, ошибки без partial success. Реальные детерминированные циклы проверяют terminal suffix, динамический бонус, independent initial/RNG, replay/reverse/expanded batch, отсутствие влияния лишних бросков одного trial на следующий и сохранение global random state. Pure summary не исполняет runner/RNG и не удерживает records. Статистические тесты не требуют точного процента побед.

Следующий шаг после реализации — воспроизводимое профилирование Melee-пакетов на 1×1/2×2/3×2 с сохранением trial digests и агрегатов. Оптимизация и process backend требуют результатов измерений; balance/внешние форматы остаются отдельными последующими срезами.

## Реализация

[Models](../../src/towr/simulation/npc_melee_models.py), [sequential executor](../../src/towr/simulation/npc_melee_simulation.py), [summary models](../../src/towr/simulation/npc_melee_summary_models.py), [pure projection](../../src/towr/simulation/npc_melee_summary.py) реализованы. Добавлены [9 unit tests исполнения](../../tests/unit/test_m6_npc_melee_simulation.py), [9 unit tests summary](../../tests/unit/test_m6_npc_melee_summary.py) и [4 integration tests](../../tests/integration/test_m6_npc_melee_simulation.py), всего 22. Реальная пара 2×2 прогонов с заданными d10 получает по 13 бросков/2 Attack и terminal suffix; summary фиксирует 2 достижения цели, 4 Attack и 2 visited rounds, хотя raw runner observations остановились на pending. Технический unsupported проверяется имитацией controller stop с корректными candidates, не подменой игрового input.

[Пример Python API](../examples/m6/README.md#python-api-массового-прогона). Результаты полной проверки и точный следующий шаг — в [project-status.md](../project-status.md#последняя-проверка).

2026-09-28 — этап профилирования выполнен без изменения production: [harness](../../tools/profile_m6.py), [baseline и методика](../benchmarks/README.md#melee-baseline-m6), [5 tests](../../tests/unit/test_m6_profiling.py). Fixtures 1×1/2×2/3×2, 100 trials, seed 20260928, budget 5. Full records и aggregate summaries совпадают во всех timing/tracemalloc/cProfile runs. Измерения выделили MinionDefeatAcknowledgementResult.continuation для следующего локального performance-среза; сохраняются guards, а время/память проверяются повторным замером. Оптимизация/process backend пока не реализованы.

Выбранный performance-срез реализован на общей M2 границе: [однократная Minion defeat continuation](ADR-0010-single-minion-round.md#однократная-проекция-minion-defeat-continuation). Seed/records/summary и сценарный контракт не меняются; snapshot строится один раз после проверки source и удерживается result. Сравнение с исходным baseline выполняется тем же неизменённым tools/profile_m6.py в отдельном отчёте.

Performance-срез завершён: [сравнение с baseline](../benchmarks/README.md#однократная-minion-defeat-continuation). Все три trial digests и агрегаты совпали, replace calls из continuation сократились до двух на acknowledgement. Peak Python в этих пакетах не вырос; общий процент ускорения не гарантируется. Полный набор 2055 tests OK. Следующий технический контракт — отдельный опциональный process runner Melee, без изменения sequential seed/result/summary.

Продолжение: [ADR-0023](ADR-0023-process-melee-simulations.md) фиксирует отдельный опциональный process backend с прежними Melee request/seed/compact result/summary. Production backend реализован и проверен отдельными unit/real-spawn tests; [измерение sequential/process](../benchmarks/README.md#melee-sequential-и-spawn) на тех же fixtures/seeds завершено. [Аудит simulation/summary](../audits/m6-simulation-readiness.md) завершён; [контракт оценки Melee-кандидатов ADR-0024](ADR-0024-melee-candidate-assessment.md) подготовлен с прежней метрикой и явным бюджетом. Pure assessment одного Melee-кандидата реализован по ADR-0024; модели ограниченного списка с бюджетом и application service исполнения списка тоже реализованы; [аудит bounded evaluation](../audits/m6-evaluation-readiness.md) и самостоятельный typed пример завершены. [Контракт поэтапной оценки ADR-0025](ADR-0025-staged-melee-evaluation.md) реализован: pure helper, frozen staged models и application service/error; [аудит staged evaluation](../audits/m6-staged-evaluation-readiness.md) и самостоятельный пример завершены. [Контракт генерации ADR-0026](ADR-0026-melee-composition-generation.md) подготовлен; group/request preflight реализован, construction/result/error реализованы; integration генерация → staged evaluation проверена; [аудит генератора](../audits/m6-generation-readiness.md) и самостоятельный пример завершены; [контракт JSON/CLI ADR-0027](ADR-0027-melee-json-cli-v1.md) подготовлен; следующий срез — simulation Schema/command и pure adapters. [Finite spawn probe](../examples/m6/process_contract_probe.py) проверяет только транспорт объектов и existing trial, не новый scheduler.
