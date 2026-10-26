# M8: готовность sequential/process performance-среза

Дата: 2026-10-27. [Методика](../benchmarks/m8-parallel-comparison-contract.md), [исполнение](../../tools/benchmark_m8_parallel.py), [интерпретация](../benchmarks/README.md#m8-sequential-и-spawn), сырые [N100](../benchmarks/m8-parallel-100-2026-10-27.md) / [N1000](../benchmarks/m8-parallel-1000-2026-10-27.md). Это аудит измерительного среза; общий аудит массовой magic simulation остаётся следующей вехой.

## Проверенная граница

- Текущие ADR-0038/0039 и authored fixtures повторяются без изменений production. Два боевых inputs и отдельный zero-action control; seed20261026, round budget4, workers1/2, batch32, три чередующихся повтора. Полный lifecycle нового spawn pool и summary входят в wall; snapshots/GC/checks/ref release вне таймера.
- 54 полных results/summary равны, включая каждый compact record; parent request/scenario identity, input/global RNG/active children сохранены после warm-up и каждого вызова. 29 718 trials с прогревом. Unsupported не фильтруется.
- N100 три canonical digests и все counters совпали с исходным baseline. Source manifest 396 files побайтно охватывает текущий src и три tools-файла; hash `f20131529ea476bfc61b3f37c29262b1dbe13f60cdca615b8f5c44e7dd55130d` одинаков в обоих отчётах и независимо пересчитан при read-only ревью. Времена/медианы и source equality проверены независимо.
- 17 новых deterministic tests — OK (0,167 с): порядок/число вызовов и warm-up, runner+summary внутри timer, полный mismatch при равных агрегатах, exact source identity, warm-up/measured invariant mutations, strict preflight/monitoring/real cProfile preservation, исходные exception, manifest и atomic old-output preservation. Existing 34 fixture/profiling tests — OK (0,323 с). Speed threshold отсутствует.

## Вывод и ограничения

N100 spawn медленнее. N1000 w2 дал local ratios 1,506/1,547 для двух боевых inputs; w1 медленнее везде. Control быстрее sequential на обоих N. Эти observations не гарантируют ускорение других боёв и не задают automatic threshold/backend. Runtime CPython3.12.15/macOS26.5.1 arm64; внешняя нагрузка/CPU не контролируются. RSS/память процессов, другие runtime/OS/workloads и workers/batch search не измерены. Wheel повторно не собирался: package src/metadata не менялись; данный harness — developer tool.

Игровые переходы, книги/Rule IDs и ADР-0037 admission не менялись; повторного извлечения правил не было. Нового house rule, RNG/seed scheme, cache, универсального scheduler, assessment/balance/generation или JSON/CLI нет. Исторические отчёты не перезаписывались. На старте HEAD1c5268a, рабочее дерево чистое; commit/push не выполнялись.

## Последняя регрессия

Полная регрессия: **3162 tests / 33 прежних errors (97,704 с)**. Counter полных error headers и exception signatures точно равен baseline предыдущей вехи; новых ошибок нет, полный suite не зелёный. Compileall, 2858 локальных Markdown-путей и whitespace — OK. Команды и лог — в [актуальном статусе](../project-status.md#последняя-проверка).

Следующий шаг: общий аудит ADR-0038/0039 — models/trial/sequential/process/summary, source/seed/outcomes, errors/cleanup, tests/public examples/installed parity и границы performance evidence; затем отдельный контракт assessment. Новые gameplay consumers в этот аудит не входят.
