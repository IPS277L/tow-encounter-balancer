# Аудит process backend M8

Дата: 2026-10-26. **Опциональный process backend [ADR-0039](../decisions/ADR-0039-process-magic-simulations.md) готов в прежнем single-run scope.** На старте HEAD `7ca5362` и 16 существующих dirty/untracked файлов контрактной вехи; они учтены отдельно. Три исходных probe/.output/test сохранены побайтно. Production добавлен одним новым модулем; прежние Python-файлы src/tests/tools не менялись. Commit/push не выполнялись.

## Проверенная реализация

| Обязанность | Реализация и evidence |
| --- | --- |
| Preflight | [npc_magic_parallel.py](../../src/towr/simulation/npc_magic_parallel.py): typed magic request, exact positive int workers/batch_size, callable factory и pickle до pool, без parent factory/RNG/trial |
| Worker | Existing run_npc_magic_trial, исходный request с полным N, абсолютный index/seed, fresh RNG. Exception получает index/seed note; BaseException не становится игровым исходом |
| Transport | Tuple/cardinality/source type/full equality ДО replace; затем dataclass constructor заново проверяет forged bool/Enum/counters и exact assigned index/derived seed. Итоговый source каждого record — исходный parent scenario |
| Scheduler | Ленивые arithmetic ranges без len(range)/materialization всех задач, Future→assigned range, initial/in-flight bound 2W, вся done group до refill, удаление successful raw Future refs до следующего планирования |
| Fail-fast/cleanup | Без partial/retry/fallback, на ошибках нет refill. Все оставшиеся cancel пытаются выполниться при обычных secondary errors; первый cleanup error сохраняет дополнительные notes и standard exception context. Pool shutdown выполняется до final result constructor |
| Public result | Existing NpcMagicSimulationResult/summary, sorted complete records, parent request identity и три counters сохраняются. Четыре outcomes и zero-action unsupported не фильтруются |

[23 unit tests](../../tests/unit/test_m8_npc_magic_parallel.py) — OK (0,037 с). Проверены foreign same-ID/same-budget source до replace, реальный pickle bypass, tuple/order/index/seed/type/bounds, reverse completion/uneven/oversized batches, default 32/workers>batches, uint64 max N и huge batch без len(range), несколько done с bad batch до refill, startup/enter/submit/wait/result/normalize/final-constructor/exit failures, worker notes/interrupts, cancellation secondary errors и порядок constructor после shutdown.

[6 real-spawn integration tests](../../tests/integration/test_m8_npc_magic_parallel.py) — OK (2,910 с), 11 public pool calls, workers 1/2. Проверены child PID даже workers 1, uneven/batch>N/workers>batches, полные sequential results/summary и canonical parent identity; четыре scripted outcomes (24 actions / 10 started / 9 completed), zero-action stop без draws; repeat/expanded prefix/partition changes и дополнительные 17 draws только своего trial. Child factory failure index 1 сохраняет type/message/исходную note+index/seed note; marker 0/1 доказывает отсутствие index 2 того же пакета. Input/global RNG/active_children сохраняются.

## Публичный пример и установленный wheel

[magic_parallel.py](../examples/m8/magic_parallel.py) импортирует public APIs и соседние magic_simulation.py/magic_scenario.py. [Stored output](../examples/m8/magic_parallel.output.txt) проверен из root и отдельного cwd: [один subprocess test](../../tests/integration/test_m8_magic_parallel_example.py) — OK (1,760 с). Три seeded calls по 5 trials с workers 1/2 и batch 2/32, два scripted calls по 4 trials и zero-action call: 24 spawned trials, шесть public API calls, source/global RNG и отсутствие оставшихся детей. Это finite correctness evidence, не throughput или difficulty estimate.

Offline wheel собран в отдельной временной копии pyproject/README/LICENSE/src, без PDF/tests и repo egg-info мутаций. Установлен в отдельный venv; трёхфайловый пример вне repo без PYTHONPATH дал тот же stdout и пустой stderr. Все 411 установленных Python/Schema файлов побайтно равны src. Wheel SHA-256: `ad69e6d2d206b2877c54ec302cac118105de034d3904258e58431355da897ec6`. Временные build/install/stdout logs: `/private/tmp/towr-m8-parallel-audit-6pkg6heu`; они не обязательны для использования примера и не входят в Git.

## Регрессия и источники

Всего **30 новых tests: 23 unit + 6 real spawn + 1 example**. Полный набор: **3145 tests / 33 прежних errors (97,011 с)**, macOS arm64 / Python 3.12.15. Counter полных error headers и exception signatures точно равен baseline контрактной вехи; новых ошибок нет. Полный suite не зелёный: старые frozen/slotted Aim assertions и replace init=False остаются отдельной задачей. [Подробности](../open-questions.md#проверки-dataclasses-на-python-312), лог `/private/tmp/towr-m8-parallel-tests.log`.

```sh
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m unittest discover -s tests -q
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m compileall -q src tests tools docs/examples/m8
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python docs/examples/m8/magic_parallel.py
git diff --check
```

Непосредственно перечитаны PG 1.4 Rules / Combat, стр. 112; Conditions / Broken, стр. 122; Magic in the Old World / Miscasts, стр. 157; Battle Magic / Curse of Cowardly Flight, стр. 162; Wounds Table, стр. 190–191; GM 1.1 Allies and Antagonists / Minions и Champions, стр. 91–92. Новых Rule IDs/house rules нет; transport не исполняет старые неподдержанные Wound/Miscast/chronology effects. Независимый reviewer проверил module/tests/public example и сохранность исходного probe, блокирующих findings нет.

Compileall, public/layer imports, 2820 локальных Markdown-путей/входящие status/question anchors и whitespace — OK; итог — в [статусе](../project-status.md#последняя-проверка). Прежние domain/engine/rules/sequential/ranged/melee/mixed APIs и JSON/CLI не менялись. Другие ОС/Python, process peak/RSS, startup/serialization costs и ускорение пока не измерены.

## Точный следующий шаг

Отдельный performance-срез: сравнить existing sequential и новый process backend на 100/1000 trials двух текущих боевых workloads и отдельного zero-action control, workers 1/2, batch 32, три чередующихся повтора. Включить startup/serialization/normalization/shutdown, сохранить input/source manifest и сравнить полные records/summary. Не усреднять control с боем и не фильтровать unsupported; не принимать timing как unittest threshold. Cache, auto backend, assessment/balance/generation и JSON/CLI автоматически не добавлять.


Текущий source/harness manifest (весь src плюс tools/profile_m8.py и tools/m8_benchmark_fixtures.py): `ec3e4505ff87eae357e62342e8d4e9adef8753d370ddda90e3386682cce609b0`. Он отличается от исторического sequential baseline добавленным production process module; новым performance-измерением не является.
