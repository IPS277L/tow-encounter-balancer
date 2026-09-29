# Аудит последовательной mixed simulation и summary

Дата: 2026-09-29. Сохранены 26 исходных dirty/untracked файлов. Проверены [ADR-0029](../decisions/ADR-0029-independent-mixed-simulations.md), четыре production simulation-модуля и 25 tests реализации. Игровая граница остаётся в [аудите одиночного M7](m7-readiness.md). Production src в этом аудите не менялся; исправлений не потребовалось.

**Последовательные независимые mixed-прогоны и aggregate summary готовы в границах ADR-0029.** Добавлены [самостоятельный пример](../examples/m7/mixed_simulation.py), [сохранённый вывод](../examples/m7/mixed_simulation.output.txt) и [subprocess test](../../tests/integration/test_m7_simulation_example.py). Process backend, измерения производительности и mixed balance/CLI этим выводом не охватываются.

## Матрица контракта

| Обязанность | Реализация | Проверка |
| --- | --- | --- |
| Допущенный immutable input | [NpcMixedSimulationRequest](../../src/towr/simulation/npc_mixed_models.py) сохраняет полный NpcMixedScenario, uint64 master_seed и положительные trials. Bool/строки/float не преобразуются; scenario/index проверяются до RNG factory | [12 unit simulation tests](../../tests/unit/test_m7_npc_mixed_simulation.py): wrong family/type/range/index, zero trials, uint64 границы, frozen/slotted |
| Собственная стабильная seed scheme | SHA-256 от ASCII towr:npc-mixed-trial:v1, нулевого byte, uint64be seed/index; схема не зависит от размера/порядка пакета и не меняет ranged/Melee vectors | Unit: три golden vectors и family separation; [integration](../../tests/integration/test_m7_npc_mixed_simulation.py): repeat/reverse/expanded prefix, дополнительные броски trial 0 не сдвигают остальные |
| Независимое исполнение | [run_npc_mixed_trial/simulation](../../src/towr/simulation/npc_mixed_simulation.py): новый RNG на trial, тот же immutable initial, exact typed NpcMixedScenarioResult/source до проекции | Integration: разные RNG instances и правильный seed каждой фабрики; source/global RNG unchanged. Unit: чужой полный scenario даже с тем же ID отклоняется |
| Четыре исхода и правильные счётчики | Trial использует итог после terminal suffix; Attack/visited из runner_report. Resume calls не становятся раундами, suffix не создаёт Attack/receipt | Integration одного 2×2 input: четыре реальных исхода, 17 Attack/6 visited, 24/24/48/6 RNG calls. Terminal raw stop=pending, итог без pending; настоящий NO_CANDIDATE сохраняет неисполненный slot |
| Полный compact result | Records копируются в tuple, сортируются по index; индексы полные и уникальные, seed совпадает, typed mixed outcome. visited <= B, attacks <= A*visited; ROUND_LIMIT достигает B | Unit: missing/duplicate/foreign seed/index, early limit, invalid counters и cross-family records/Enum отвергаются. Full journals не входят в TrialSummary |
| Ошибки без partial success | Ошибки factory/RNG/executor/result type/source и interrupts распространяются; нет retry/fallback или автоматической подмены исхода | Unit: после первого успеха ошибка/interrupt второго trial не запускает третий; source-consistent технический stop остаётся отдельной записью |
| Чистая aggregate summary | [Summary model](../../src/towr/simulation/npc_mixed_summary_models.py), [projection](../../src/towr/simulation/npc_mixed_summary.py): exact source request, четыре counts, две суммы; means вычисляются. Counts sum=N, L*B+N-L <= rounds <= N*B, terminal_count <= attacks <= A*rounds | [9 summary tests](../../tests/unit/test_m7_npc_mixed_summary.py): types/source/count/totals guards, frozen copies, zero technical stop, рекурсивное отсутствие trial/result/journals; нет вызовов RNG/runner/pool |
| Публичное использование | Новый пример вызывает готовые simulation/summary, берёт builder одиночного примера, использующий public constructors. Нет tests/private imports или собственной симуляции | Subprocess test из временного каталога, только src в PYTHONPATH; два запуска с одинаковым stdout, внутри каждого полное equality result/summary. Тест не закрепляет случайный процент или победителя |

Итого для слоя simulation 26 tests: 12 unit simulation + 9 summary + 4 integration + 1 subprocess example. С одиночным сценарием — 86 tests M7. Профили и сами правила K1/M2 не дублируются в simulation; generic runner/aggregate не добавлялся. Направление импортов проверено: simulation → engine/domain/rules, без application/adapters/CLI и обратных импортов в domain/engine.

## Непосредственная книжная сверка

| Источник | Связь с проверенным поведением |
| --- | --- |
| BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112 | Раунд, ход, действие; текущий ограниченный runner выполняет одну Attack каждого доступного actor за раунд |
| Та же книга, Rules / Attack Tests / Attack Modifiers, стр. 118–119; Failed Attacks / Successful Attacks, стр. 119 | Opposed Attack, актуальный Zone outnumbering, GM withholding, Close miss, Damage/Resilience. Trial повторяет existing runner, не заменяет правила статистикой |
| BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91 | Wound побеждает Minion, attacker/GM disposition сохраняется отдельно; acknowledgement не дополнительная Attack |
| Та же книга, Understanding NPC Profiles, стр. 93; Brigands & Footpads, стр. 97 | Numeric Attack/Protection, Footpad Dagger и Brigand Warbow в public builder; пример не выполняет Melee Brigand с Craven Opportunist |

Страницы прочитаны в локальном извлечённом тексте. Seed derivation и агрегаты — технические контракты, не книжные механики. Новых Rule IDs, противоречий или house rules нет. Остальные факты неподвижного сценария и правила допуска остаются в ADR-0028; прототип не используется как приоритетный источник.

## Наблюдения публичного примера

Явные master_seed=42, trials=8, round_budget=2. Составы берутся из публичного builder в [mixed_scenario.py](../examples/m7/mixed_scenario.py); факты, placements, все enemy pairs, target order и решения выведены рядом со сводкой. Каждый пакет повторяется целиком для equality, поэтому один запуск примера выполняет 32 trials. Повторы не прибавляются к отчётным N=8 и разные составы не объединяются.

В [сохранённом запуске](../examples/m7/mixed_simulation.output.txt), Windows/Python 3.14.5:

| Состав | Цель / поражение / лимит / unsupported | Attack | Visited rounds | Доля цели от всех 8 trials |
| --- | --- | --- | --- | --- |
| 3×2, один лучник союзников | 6 / 0 / 2 / 0 | 49 | 15 | 3/4 |
| 2×2, по лучнику с каждой стороны | 0 / 1 / 0 / 7 | 27 | 12 | 0/8 |

Это наблюдения маленькой выборки данного runtime, не эталон Monte Carlo-процента и не оценка баланса. Во втором составе семь остановок показывают, что фиксированная Attack-only тактика не завершает многие пути. Нельзя назвать их семью поражениями, исключить из знаменателя или рассчитать условную вероятность победы среди «доигранных». Будущий assessment должен отклонить кандидат при ненулевом unsupported; такого mixed assessment API сейчас нет. Ноль unsupported в первой выборке не доказывает невозможность этой остановки.

Visited rounds включают незавершённый последний раунд. Полное battle source validation выполняется до compact projection; после удаления журнала record/result/summary проверяют лишь структурные ограничения и не доказывают происхождение бросков. Summary хранит начальный request, но не simulation result или журналы. Произвольная пользовательская RNG factory отвечает за отдельные потоки; full snapshot rollback и ложные GM facts этими слоями не предотвращаются.

## Границы и точный следующий шаг

Не входят: mixed process, auto backend, streaming/checkpoint, балансировщик/генератор, JSON/CLI, новые действия/роли, движение, смена оружия, магия, общий battle aggregate. Ограничения uint64 не являются практической квотой памяти или времени. Python 3.12/другие ОС, installed wheel и performance этим аудитом не проверялись.

Следующий законченный срез — воспроизводимое профилирование **неизменённого** последовательного mixed simulation. Подготовить developer harness для явных 2×1, 3×2 и 2×2 с двумя лучниками, 100 trials, master_seed=20260929, round_budget=5. Fixtures должны проходить production admission, использовать public constructors и сохранять все pair ranges/GM policies. В 2×2 обязательно учитывать unsupported как отдельный исход, не исключая его trials из времени/агрегатов.

Сохранить полные compact records либо стабильный digest канонического index/seed/outcome/attacks/visited представления и aggregate summary. Сверить equality baseline, timing repetitions, отдельного tracemalloc и cProfile; не смешивать их overhead в одно время. Измерять wall time и peak Python allocation, записать версии/runtime/команды и top cumulative/call counts. До измерений не оптимизировать, не добавлять process и не обещать ускорения. По данным выбрать один узкий следующий шаг либо зафиксировать отсутствие убедительного кандидата.

Команды и результаты проверки аудита — в [статусе проекта](../project-status.md#последняя-проверка).

Проверка аудита: **26 tests simulation OK (2,108 с)**; полный набор **2384 tests OK (226,194 с)**, Windows/Python 3.14.5. Compileall, 1654 локальных Markdown-пути, AST import boundaries, diff --check и whitespace новых файлов успешны. Все 26 исходных dirty/untracked файлов сохранены; новые audit/example/output/test и изменения документации не закоммичены. Commit/push не выполнялись.

## Выполненный следующий срез: профилирование

[Методика и исходный отчёт](../benchmarks/README.md#m7-исходное-профилирование-mixed-simulation) готовы. Три admitted fixtures прошли по пять измерительных пакетов каждый, records/summary совпали; добавлены семь deterministic tests harness. Production src не менялся. Точный следующий шаг — проверить однократное построение NpcRoundResult.continuation, сохранить все guards/value semantics и сопоставить wall time/память/digests с baseline. Ускорение и mixed process ещё не реализованы.

## Итог эксперимента round continuation

[Измерения и отказ](../benchmarks/m7-round-continuation-review.md): source/result correctness сохранялась, но критерий подтверждённой общей пользы не выполнен. Кандидат снят, production восстановлен. Следующий срез — контракт опционального mixed process runner с прежними четырьмя исходами и без автоматического backend.

## Следующий контракт подготовлен

[ADR-0030](../decisions/ADR-0030-process-mixed-simulations.md) фиксирует отдельный опциональный mixed process runner с прежними seed/result/summary. [Конечный transport probe](../examples/m7/process_contract_probe.py) проверяет fixed partitions и реальные четыре исхода; production preflight/bounded queue/cancellation остаются обязательствами следующей реализации. Аудит sequential не объявляет отсутствующий process backend готовым.

## Реализация следующего process-среза

[Backend ADR-0030](../../src/towr/simulation/npc_mixed_parallel.py) реализован с 11 unit/6 real-spawn integration tests. Source/seed/result/summary прежние, реальные unsupported не фильтруются. Это дополнение к sequential; [end-to-end измерения sequential/process](../benchmarks/README.md#mixed-sequential-и-spawn) завершены на 100/1000 trials с полным равенством результатов. Следующий срез — общий аудит массового mixed-слоя по ADR-0029/0030, включая source/seed/outcomes, ошибки/cleanup, summaries и границы применимости измерений. Прежний аудит sequential не является самостоятельным performance-аудитом process.

## Общий аудит завершён

[Аудит массовой mixed-симуляции](m7-mass-simulation-readiness.md) объединяет готовые sequential/process/summary и сохранённые измерения. Проверены 56 tests слоя (116 M7 суммарно), текущий source/harness hash совпадает с обоими process отчётами. Следующий срез — контракт оценки mixed-кандидатов; исходные результаты последовательного аудита выше остаются историческими.
