# M8: ограниченное сравнение sequential и spawn

Дата: 2026-10-27. Техническое продолжение [ADR-0039](../decisions/ADR-0039-process-magic-simulations.md), без новых правил или production-оптимизации. Старый [sequential baseline](m8-baseline-2026-10-26.md) остаётся историческим.

## Вход и объём

Используются неизменённые [fixtures](../../tools/m8_benchmark_fixtures.py) и [описание фактов](m8-profiling-contract.md): curse-routes, champion-pressure и отдельный missing-departure. Первые два — authored трёхакторные бои; последний — zero-action/zero-draw technical stop. Контроль не усредняется с боем. Все unsupported сохраняются в N; Broken/уход не превращаются в defeat. Игровые источники и границы остаются в ADR-0037/0038/0039.

Два отдельных запуска harness: N=100 и 1000, master_seed=20261026, round_budget=4, workers=(1,2), batch_size=32, repeats=3. Порядок measured modes: sequential/w1/w2, w2/w1/sequential, sequential/w1/w2. Перед каждым case — sequential warm-up min(3,N), без постоянного pool или прогрева детей. Итого 54 measured full result/summary, 29 700 measured trials + 18 warm-up = 29 718. Другие workers/batches/семейства и поиск optimum не входят в срез.

## Таймер и проверки

[Harness](../../tools/benchmark_m8_parallel.py) измеряет public runner и summary внутри одного perf_counter интервала. Каждый process call включает preflight, pickle, spawn/imports, выполнение, transport, parent source validation/normalization и shutdown. Это стоимость полного вызова, а не только работы детей.

Fixtures/imports, deepcopy snapshot, gc.collect, source hash, trial digest, сравнение полных result/summary и source identity находятся вне таймера. После проверки non-reference result/summary освобождаются до следующего интервала. GC не переключается. После warm-up и каждого результата проверяются исходный input, global RNG и прежний набор active_children; request/summary сохраняют original parent request identity, каждый record — original parent scenario identity. Равные counts при отличных records недостаточны. Ошибки прерывают запуск без partial report, retry или fallback.

Активные tracemalloc, sys.getprofile либо занятый sys.monitoring.PROFILER_ID отклоняются до работы и каждого measured интервала. Harness не выключает чужую instrumentation. Во время замеров не запускаем параллельно tests/тяжёлые проверки. CPU affinity/частота и внешняя нагрузка ОС не контролируются. Память/RSS детей и общий peak не измеряются.

## Evidence и границы выводов

Отчёт содержит каждое wall время, median и отношение sequential/данный mode, N/seed/budget/batch, runtime/OS/processor/GC/HEAD+dirty, воспроизводимую команду, четыре counts и отдельные actions/started/completed, canonical trial digest из profile_m8. N100 digests/counters дополнительно сопоставляются с прежним baseline; они не подменяют полное сравнение внутри harness.

Source manifest охватывает все src/**/*.py, включая untracked, tools/profile_m8.py, tools/m8_benchmark_fixtures.py и tools/benchmark_m8_parallel.py. Алгоритм: relative POSIX paths сортируются; для каждого UTF-8 path + NUL + raw SHA-256 файла; общий SHA-256 конкатенации. Docs/tests/bytecode исключены. Hash до/после должен совпасть. Область отличается от historical profiling, поэтому старый общий hash не ожидается. Report заменяется атомарно только после измерений, rendering и source guard; при отказе прежний output сохраняется.

Детерминированные tests проверяют вызовы/таймер/alternation, preflight/instrumentation, полный result/summary/source, invariants, hash и сохранение output при ошибке. Точные wall times и пороги ускорения не являются test oracle. Наблюдение локально для этих двух workloads/контроля и runtime; оно не гарантирует ускорение других боёв и не создаёт auto backend, метрику сложности или новый API оценки кандидатов.
