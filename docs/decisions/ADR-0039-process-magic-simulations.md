# ADR-0039: опциональные magic-прогоны через spawn

Статус: реализован и проверен в ограниченной границе, 2026-10-26. [Production backend](../../src/towr/simulation/npc_magic_parallel.py), 23 unit и 6 real-spawn integration tests, [public пример](../examples/m8/magic_parallel.py) и [аудит](../audits/m8-process-readiness.md) готовы. Исторические [transport probe](../examples/m8/process_contract_probe.py), [вывод](../examples/m8/process_contract_probe.output.txt) и [аудит контракта](../audits/m8-process-contract-readiness.md) сохранены; они не заменяют проверки готового scheduler.

## Основание и граница

[ADR-0038](ADR-0038-independent-magic-simulations.md) и [аудит sequential simulation](../audits/m8-simulation-readiness.md) закрыты. [Исходный profiling](../audits/m8-profiling-readiness.md) дал 0,18–0,22 с на 100 trials двух ограниченных боевых inputs на одном host. Это основание исследовать способ исполнения, не обещание ускорения. Process startup/serialization/shutdown и большие N пока не измерены. Общая архитектура следует [mixed ADR-0030](ADR-0030-process-mixed-simulations.md), но magic record содержит полный input scenario, поэтому перенос и владение source описаны отдельно.

Single-run admission, authored Wizard/Minions, Curse, Wound/Conditions/timing, scene facts, tactics и обязательные unsupported stops [ADR-0037](ADR-0037-magic-scenario-runner.md) сохраняются. Книги задают игровые переходы, не количество workers или формат pickle. Прямо сверены PG 1.4, Rules / Combat, стр. 112; Conditions / Broken, стр. 122; Magic in the Old World / Miscasts, стр. 157; Battle Magic / Curse of Cowardly Flight, стр. 162; Wounds Table, стр. 190–191; GM 1.1, Allies and Antagonists / Minions и Champions, стр. 91–92. Новых Rule IDs/house rules нет.

## API и зависимости

Один отдельный модуль `towr.simulation.npc_magic_parallel`:

```python
run_npc_magic_simulation_parallel(
    request: NpcMagicSimulationRequest, *, workers: int,
    batch_size: int = 32, rng_factory: Callable[[int], RandomSource] = Random,
) -> NpcMagicSimulationResult
```

Request/record/counts/result/summary и sequential API ADR-0038 не меняются. Workers/batch_size не входят в source_request, seeds или игровой input. Production модуль не зависит от примеров, tools, CLI, application или balance. Domain/engine/rules не импортируют multiprocessing/executors. Новый generic scheduler, simulator framework, event bus или cache не вводится.

Каждый trial исполняет existing `run_npc_magic_trial`, который до projection проверяет typed single-run result и его полный source. Нового kernel/runner, повторной Attack/completion и отдельной трактовки outcomes нет. В parent результат собирается прежним `NpcMagicSimulationResult`, summary — прежней pure projection. Sequential остаётся самостоятельным API.

## Preflight до создания pool

1. Только `NpcMagicSimulationRequest`; чужие families/нетипизированный input → TypeError.
2. Workers и batch_size — положительные exact int. Bool/float/str/None → TypeError; zero/negative → ValueError.
3. Factory должна быть callable. Выполнить `pickle.dumps((request, rng_factory))`; ошибка сериализации проходит наружу без pool, пробного вызова factory/RNG/trial, retry или sequential fallback.

Успешный pickle не гарантирует child importability и математическую независимость factory. Она обязана быть импортируемой/сериализуемой и создавать новый RandomSource для каждого seed. Воспроизводимость требует тех же input/правил и совместимого RNG/runtime. Платформенные пределы workers проверяет ProcessPoolExecutor; автоматический CPU count, скрытая quota и универсальный optimum batch_size не вводятся. Default 32 — техническая преемственность прежних backend, не измеренная оптимизация M8.

Каждый вызов создаёт свой ProcessPoolExecutor с явным `get_context("spawn")`, даже при workers=1. Caller использует импортируемый main module и `if __name__ == "__main__"`. Workers может превышать число пакетов. Вложенных pools, persistent pool, hard-kill/timeout/resume/streaming API здесь нет.

## Ленивое планирование и worker

- Абсолютные индексы `0..N-1` делятся на непрерывные диапазоны `range(start, min(start+batch_size,N))`. Количество пакетов вычисляется арифметически `(N+batch_size-1)//batch_size`; все starts/ranges/futures не материализуются заранее. Не использовать len(range) для потенциально огромного uint64 N.
- Каждый индекс вызывает existing magic trial с исходным request, включая полный N, тем же fresh immutable scenario и отдельным RNG. Не заменять request.trials длиной пакета: это ломает абсолютные индексы. Seed — только `towr:npc-magic-trial:v1` от master_seed/абсолютного index. Worker/PID/номер пакета/порядок arrival/размер выборки не влияют на seed.
- Одновременно outstanding не более `2*workers` futures; initial fill — min этой границы и числа пакетов. После wait(FIRST_COMPLETED) сначала получить и проверить всю returned done group, затем refill. Если любой result/validation падает, нового refill нет. Порядок ошибок внутри unordered done set и фактически хронологически первая ошибка не гарантируются.
- Worker возвращает только `tuple[NpcMagicTrialRecord, ...]` в порядке своего range. Records сохраняют полный source scenario и scalars ADR-0038. Request/result/journal/pending/RNG/factory/PID дополнительно не возвращаются. PID допустим как отдельная probe/test диагностика.
- Обычный Exception внутри конкретного trial получает note `M8 trial index=<index>, seed=<seed>` и сразу пробрасывается. Следующий индекс того же пакета не исполняется. KeyboardInterrupt/SystemExit не ловятся через Exception и не становятся игровым исходом.

## Parent: проверить source до нормализации

В отличие от mixed, каждый magic record удерживает полный scenario. Pickle сохраняет общие ссылки внутри одного сообщения, но разные сообщения обычно создают равные независимые source graphs. На identity после транспорта опираться нельзя. Нельзя также перепривязать foreign record к parent source и тем самым скрыть подмену.

Для каждого completed пакета, связанного parent с его исходным range:

1. Проверить tuple, число records через `range.stop-range.start` и принадлежность каждого к NpcMagicTrialRecord. List/чужая family → TypeError, неверная полнота → ValueError.
2. Проверить исходный record.source_scenario: тип NpcMagicScenario и полное равенство request.scenario. Один ID или seed недостаточен. Это происходит **до** rebinding/снятия transported source. Foreign source → ValueError; неправильный тип source → TypeError.
3. Создать проверенную копию `replace(record, source_scenario=request.scenario)`. Dataclass unpickle не обязан вызывать __post_init__; новый constructor заново проверяет strict scalar/Enum/bool/range/counter bounds ADR-0038. Не доверять только успешному pickle или тому, что True сравнивается равным index 1. Остальные поля не исправлять и строки/float не преобразовывать.
4. Для каждой проверенной копии потребовать точный очередной абсолютный index из assigned range и seed == request.seed_for(index). Missing/duplicate/переставленные/чужие индексы или seed → ValueError. Успешный глобальный sort не заменяет принадлежность конкретному пакету.
5. В общей коллекции сохранить только проверенные копии с `source_scenario is request.scenario`. Не удерживать raw batches/Future results сверх необходимости текущей done group. Не возвращать partial complete result.

После всех пакетов existing NpcMagicSimulationResult с **исходным parent request** проверяет полную выборку, сортирует индексы и выводит counts/totals. Каждый итоговый record и summary разделяет исходный parent input. Результат и summary равны sequential при том же input/factory/runtime независимо от partitions/workers/порядка получения.

Это structural/source guards доверенной локальной simulation, не подпись observations или валидация произвольного удалённого сервиса. Верхняя память — O(N) compact records с одним общим parent scenario плюс ограниченные транспортные/worker копии inputs и пакетов. Внутри одного pickle tuple shared source обычно сериализуется один раз; request снова передаётся для каждого batch. Bounded futures не являются жёсткой byte/RSS quota, а стоимость full source validation/pickle/normalization требует измерения.

## Исходы и counters

Четыре typed magic outcomes сохраняются: OBJECTIVE_ACHIEVED, PERSPECTIVE_DEFEATED, ROUND_LIMIT_REACHED, UNSUPPORTED_PATH. Ни один не заменяется строкой/чужим Enum, не фильтруется и не перезапускается ради другого результата. N — полный denominator, public rates/метрика в этот API не добавляются.

Broken/другая Zone не являются defeat. Обязательные Wound/Miscast pending и chronology остаются stops существующего runner. Actions/started/completed берутся из existing trial; completion/defeat acknowledgement/end-turn не создают дополнительные actions или rounds. Zero-action unsupported с started=1/completed=0 допустим. Live positions, magic pool, daily/Wound/expiry histories и IDs между trials не переносятся.

## Ошибки и cleanup

Serializable worker error передаётся Future с type/message/notes; transport/import/pickle ошибки распространяются в своей категории. Идентичность экземпляра exception и исходный локальный __cause__ через process не обещаются; child traceback может стать RemoteTraceback. Parent preflight/submit/wait/result/source/normalization/final-constructor errors также не превращаются в unsupported/loss или partial success.

На любом выходе в finally попытаться cancel outstanding futures, которые ещё допускают отмену. Context manager закрывает pool и ждёт уже выполняющуюся работу. Уже отправленные/running пакеты могут завершиться; это не атомарная отмена всех trials при первой ошибке. Никаких retry, повторного вызова factory/trial или sequential fallback. Parent input/global RNG не меняются; внешние side effects custom factory не откатываются.

Secondary cleanup errors не подавляются молча и не считаются игровыми исходами: исходная причина сохраняется через стандартную цепочку исключений Python либо notes. При нескольких конкурентных/cleanup сбоях не обещается приоритет хронологически первой причины. Проверки следующей реализации должны отдельно установить отказ и cleanup на submission/wait/validation failures, без ложного обещания мгновенной отмены всех задач.

## Конечный transport probe

[process_contract_probe.py](../examples/m8/process_contract_probe.py) и [его вывод](../examples/m8/process_contract_probe.output.txt) используют existing public APIs и соседние public builders magic_simulation.py/magic_scenario.py. Это фиксированные маленькие partitions и ручная локальная проверка transported records, **не production API** и не реализация lazy scheduling/refill/cancel.

Probe должен показать настоящий child PID при workers=1/2, pickle equality/aliasing, reverse collection, sorted complete equality result/summary и исходную parent scenario identity после нормализации. Отдельные scripted trials одного source дают четыре outcomes; zero-action stop имеет иной полный source. Проверяются foreign same-ID source до rebinding и malformed payload/index/seed/Enum/bool guards, pickle failure до pool, index/seed notes и остановка следующего trial того же failed batch, input/global RNG и отсутствие оставшихся детей. Внешний cwd запуск требует три соседних example файла и установленный towr либо PYTHONPATH=src.

Probe не доказывает будущий public preflight, lazy ranges/bounded queue/refill, cancellation/submission/wait errors, все interrupts или производительность. Матрица ниже проверена отдельными magic implementation tests; наличие похожего mixed backend не подменяет эти проверки.

## Проверенный контрактный срез

На одном healthy authored input seeded N=5 сравнен с fixed plans 3+2 при workers=1 и 2+2+1 при workers=2; получение в обратном порядке даёт полные result/summary, равные sequential. Четыре scripted trials одного source проверены при workers=1/2: counts=1/1/1/1, totals=24 actions / 10 started / 9 completed, 120 d10 на полный N=4 run. Отдельный source даёт zero-action unsupported без draws.

Всего 19 успешных transported trials в 10 fixed batches, плюс один failed batch в отдельном pool; все шесть pools закрыты. Within-batch aliasing и разные source copies между сообщениями проверены, итоговые records разделяют исходный parent scenario. 15 negative probes отвергают foreign same-ID source, неполный/чужой payload, indices/seeds, строки/чужой Enum, bool и invalid counters после реального pickle round-trip с обходом frozen construction. Lambda отказала до pool; child factory failure на index=1 сохранил type/message/две notes, marker содержит только indices 0/1, без index2 и partial result.

Root и external-cwd трёхфайловый bundle дали тот же stdout/пустой stderr; [один subprocess test](../../tests/integration/test_m8_magic_process_contract_probe.py) — OK (1,811 с). Полная регрессия: 3115 tests / прежние 33 dataclasses errors Python 3.12, новых ошибок нет. Source/cleanup/pending guards public backend, lazy scheduling и его performance этим не объявлены проверенными; [подробности](../audits/m8-process-contract-readiness.md).

## Матрица реализации и проверки

| Срез | Проверки |
| --- | --- |
| Admission | Typed magic request, чужие families, exact positive workers/batch_size, callable/pickle failures до pool без factory/RNG/trial calls |
| Worker и source | Existing trial один раз, shared fresh input/new RNG, tuple-only payload, index/seed note, no next index after failure, BaseException без игрового wrapper |
| Transport normalization | Полный source до rebinding, equal copies → original identity, source type/foreign same-ID, unpickle bypass с bool/Enum/counter forgery, exact range/index/seed/cardinality, tuple type и сохранение всех трёх counters |
| Scheduler | Явный spawn, arithmetic huge-N/lazy initial/refill, bound 2W, reverse completion, uneven tail, batch>N/workers>batches, все done до refill |
| Ошибки parent | Initial/refill submit, wait/Future.result, malformed batch/normalization/final constructor; best-effort cancel/shutdown, no partial/retry/fallback |
| Real spawn | Workers1/2, несколько partitions, полный sequential/result/summary equality, repeat/reverse/prefix/extra-draw isolation; четыре real outcomes, zero-action unsupported и input/global RNG/cleanup |
| Performance после готовности | Отдельно sequential/process на большем N с startup/serialization/shutdown, source manifest и равными полными records/summary; no timing threshold в tests |

Production module и его unit/real-spawn integration tests реализованы по этой матрице. Следующий законченный шаг — отдельное сравнение sequential/process с большими N и полными startup/serialization/shutdown costs. Assessment/balance/generation, JSON/CLI и новые gameplay consumers требуют дальнейших отдельных срезов.


## Реализация и проверка готового API

Один новый npc_magic_parallel.py использует Future→assigned range, ленивые starts и arithmetic batch_count; после полной проверки done group raw Future references удаляются до refill. _normalize_batch проверяет tuple/cardinality/types/full source до replace, который заново проверяет dataclass после pickle. Final constructor вызывается после shutdown, все records.source_scenario разделяют исходный parent scenario. При обычных cancellation errors попытки остальных cancel продолжаются; первый cleanup error поднимается с дополнительными notes и стандартной цепочкой исходной причины.

23 unit tests покрывают preflight до pool без RNG, huge uint64 ranges/batches, разные completions и bound 2W, multi-done no-refill-after-bad, foreign same-ID/same-budget source до replace, forged transported bool/Enum/counters, worker/parent/constructor failures и secondary cleanup. 6 real-spawn tests проверяют workers1/2, uneven/oversized batches и workers>batches, полные sequential results/summary и parent identity, четыре scripted outcomes, zero-action stop, repeat/prefix и extra-draw isolation, child failure notes/marker/no-next-index и cleanup. Performance не является test expectation.

[Public трёхфайловый пример](../examples/m8/magic_parallel.py) проверен из внешнего cwd отдельным subprocess test и из установленного wheel без PYTHONPATH. Итого 30 новых tests; полная регрессия 3145 tests / прежние 33 dataclasses errors Python 3.12, новых ошибок нет. Подробнее — [readiness audit](../audits/m8-process-readiness.md). Первоначальные probe/.output/test сохранены побайтно. Игровые правила, domain/engine и прежние sequential/ranged/melee/mixed API не менялись.
