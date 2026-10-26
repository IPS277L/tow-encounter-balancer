# Аудит контракта magic process transport/spawn

> Исторический срез перед production implementation. Текущая готовность исполнителя — в [аудите ADR-0039](m8-process-readiness.md); данные конечного probe ниже сохранены.

Дата: 2026-10-26. **[ADR-0039](../decisions/ADR-0039-process-magic-simulations.md) и конечный transport probe готовы; production process backend ещё не реализован.** На старте HEAD `7ca5362` (M8 P6), рабочее дерево чистое. Source rules, engine, simulation API ADR-0038 и tools не менялись. Commit/push не выполнялись.

## Проверенная граница

[Probe](../examples/m8/process_contract_probe.py) использует public magic trial/result/summary и соседние public builders magic_simulation.py/magic_scenario.py, explicit spawn и фиксированные маленькие partitions. Это пример проверки transport, не production admission/lazy scheduler/refill/cancellation. Child PID поступает по отдельному diagnostic channel; payload — только tuple records. Точное число запущенных детей не фиксируется: max_workers не гарантирует использование всех workers.

| Evidence | Результат и предел |
| --- | --- |
| Seeded N=5 | Workers=1 с batches 3+2 и workers=2 с batches 2+2+1, reverse collection; полные result/summary равны sequential |
| Scripted N=4 | Workers=1/2, четыре реальных outcomes одного source, counts 1/1/1/1, 24 actions / 10 started / 9 completed, 120 d10 на один полный четырёх trial run |
| Zero action | Иной полный source с missing departure, unsupported, started 1/completed 0, 0 draws; не переименовывается в defeat/draw |
| Source graphs | Pickle equality без identity между сообщениями, aliasing внутри одного batch; после проверки все final records.source_scenario is parent.scenario |
| Неверный transport | 15 post-pickle cases: source type/foreign same-ID, payload type/missing/foreign record, index/order/seed, string/foreign Enum, bool и неверные counters |
| Constructor bypass | Counterfeit сначала обходит frozen fields через object.__setattr__, затем реально проходит pickle; normalizer проверяет исходный source до canonical replace, который заново выполняет strict constructor guards |
| Ошибка factory | Serializable ValueError index 1 сохранил type/message, исходную note и index/seed note; внешний marker 0/1 доказывает отсутствие index 2. Нет partial result |
| Preflight illustration | Локальная lambda не сериализуется до создания pool. Это не тест ещё отсутствующего public options/preflight API |
| Cleanup | Parent/child input и global RNG сохранены; active_children после каждого выхода равен исходному набору, diagnostic Queue закрыта. Cancel/refill/wait/submit fault injection остаётся implementation matrix |

19 успешных transported trials в 10 fixed successful batches и отдельный failed batch; всего шесть pool contexts. Probe сохраняет несколько raw source graphs только для finite identity evidence; будущий parent не должен накапливать эти graphs после нормализации. Математическая независимость произвольной factory, подлинность observations и пиковая память/RSS не доказываются.

[Stored stdout](../examples/m8/process_contract_probe.output.txt) одинаков из root и внешнего cwd, stderr пуст. [Subprocess test](../../tests/integration/test_m8_magic_process_contract_probe.py): один test OK (1,811 с). Во внешний каталог копируются ровно process_contract_probe.py, magic_simulation.py и magic_scenario.py; imports из tests/tools/private helpers отсутствуют.

## Проверки

macOS arm64 / Python 3.12.15. Полная регрессия: **3115 tests / 33 прежних errors (92,443 с)**. Counter полных error headers и exception signatures точно равен profiling baseline: 32 TypeError старых frozen/slotted Aim assertions и один ValueError replace поля init=False. Новых ошибок нет; полный suite не зелёный. [Известное ограничение](../open-questions.md#проверки-dataclasses-на-python-312), полный лог `/private/tmp/towr-m8-process-contract-tests.log`.

```sh
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python docs/examples/m8/process_contract_probe.py
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m unittest discover -s tests -q
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m compileall -q src tests tools docs/examples/m8
```

Compileall, сохранность прежних Python-файлов, public-import AST, 2779 локальных Markdown-путей/входящие status/question anchors и whitespace — OK; результат — в [статусе](../project-status.md#последняя-проверка). Другие ОС/Python, installed wheel, большие N, public scheduler/errors, память и process speedup не проверены. Ранее полученный sequential profiling не является замером этого transport probe.

## Книжная сверка и независимое ревью

Непосредственно прочитан локальный текст PG 1.4: Rules / Combat, стр. 112 (полный ход до handoff); Conditions / Broken, стр. 122 (уход/Recover не defeat); Magic in the Old World / Spell Potency / Miscasts, стр. 157 (последний roll и mandatory pending); Battle Magic / Curse of Cowardly Flight, стр. 162 (Give Ground перед Willpower); Wounds Table, стр. 190–191 (timed и lethal effects). GM 1.1: Allies and Antagonists / Minions и Champions, стр. 91–92. Техническое распределение trials не меняет эти правила и не закрывает старые Miscast ambiguities; новых Rule IDs/house rules нет.

Независимый reviewer проверил ADR, probe, output и subprocess test. Замечания по full N, strict unpickle revalidation, secondary cleanup chaining и ленивому числу worker startups учтены; блокирующих findings нет.

## Точный следующий шаг

Реализовать один `towr.simulation.npc_magic_parallel` и unit/real-spawn integration tests по матрице ADR-0039: preflight, ленивые absolute ranges и bound 2W, существующий trial, source-before-rebinding, нормализация к parent identity, четыре outcomes и fail-fast/cleanup. Это следующая законченная веха. Benchmark sequential/process с большими N и startup/serialization/shutdown — отдельный шаг после допуска backend; cache, assessment/balance/generation, CLI и gameplay расширения автоматически не добавляются.
