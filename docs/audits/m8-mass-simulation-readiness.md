# Аудит массовой magic simulation M8

Дата: 2026-10-27. **ADR-0038/0039 закрыты общим аудитом в ограниченном single-run scope ADR-0037.** Проверены пять production simulation модулей, 131 existing test массового слоя, public examples, installed parity и сохранённые измерения. Исправлений src/tests/tools не потребовалось, новых tests нет. На старте HEAD `1c5268a` и 16 existing dirty/untracked файлов предыдущего performance-среза; они учтены как исходные. Commit/push не выполнялись.

## Контракт, реализация и проверки

| Обязанность | Реализация | Evidence |
| --- | --- | --- |
| Admission и seed | [Models](../../src/towr/simulation/npc_magic_models.py): typed scenario, positive uint64 N, uint64 master/index, отдельная scheme `towr:npc-magic-trial:v1`; SHA-256 namespace/NUL/два uint64be, результат uint256 | [16 model tests](../../tests/unit/test_m8_npc_magic_simulation_models.py): три независимых golden vectors, strict int/Enum/family без bool/coercion; workers/batch/N/scenario ID не входят в seed |
| Свежий trial | [Trial/sequential](../../src/towr/simulation/npc_magic_simulation.py): existing single-run один раз, новый RNG по index, неизменный full input; source проверяется до scalar projection | [13 execution unit](../../tests/unit/test_m8_npc_magic_simulation.py), [8 sequential integration](../../tests/integration/test_m8_npc_magic_simulation.py): foreign same-ID source, exception/BaseException без retry/partial, repeat/reverse/prefix/rename/extra-draw isolation и global RNG |
| Compact record и полнота | Full input reference + index/seed/outcome/actions/started/completed; result требует все N records, сортирует абсолютные indices, сверяет seeds/full source | Model tests: missing/duplicate/foreign index/seed/source, premature limit, counter bounds, zero-action unsupported; records не удерживают final result/journal/RNG |
| Aggregate-only summary | [Summary model](../../src/towr/simulation/npc_magic_summary_models.py), [projection](../../src/towr/simulation/npc_magic_summary.py): полный request, четыре counts, три totals; N выводится из request | [11 summary tests](../../tests/unit/test_m8_npc_magic_summary.py): sum=N, строгие типы/арифметические bounds, frozen/replace, без runner/RNG и recursive retention records/results/journals |
| Process preflight | [Backend](../../src/towr/simulation/npc_magic_parallel.py): typed magic request, exact positive workers/batch_size, callable+pickle до pool без parent RNG/factory | [23 process unit](../../tests/unit/test_m8_npc_magic_parallel.py): invalid family/options/serialization, исходные ошибки; успешный pickle сам по себе не гарантирует importability factory |
| Transport source | Tuple/cardinality/typed source/full equality до rebinding; replace заново запускает post-init после pickle; exact assigned index/order/seed, canonical parent scenario | Process unit: foreign same-ID/same-budget source до replace, forged bool/Enum/counters после реального pickle, неправильные tuple/type/order/seed; [6 real-spawn integration](../../tests/integration/test_m8_npc_magic_parallel.py): original parent identity |
| Bounded scheduling | Fresh spawn даже w1, lazy absolute ranges с исходным полным N, arithmetic batch_count, ≤2W outstanding, вся done group проверяется до refill; raw successful done references освобождаются | Unit: huge uint64 N/batch без len(range)/eager materialization, reverse completion/multi-done, uneven tail/batch>N/workers>batches; real child PID при workers1/2 |
| Ошибки/cleanup | Worker Exception получает index/seed note, следующий index того же failed batch не выполняется. Parent отказывает без fallback/retry/partial. Cancel пытается обработать все pending при обычных secondary errors; context shutdown до final constructor | Unit: startup/enter/submit initial/refill/wait/result/normalization/final-constructor/exit, interrupts, cancel notes и исходный context. Real child failure сохраняет type/message/notes и marker0/1 без index2; global RNG/input/children сохранены |
| Исходы и counters | Четыре magic outcomes, actions и started/completed берутся из existing result properties; pending не исполняется массовым слоем | Real sequential/process integration: objective/defeat/limit/unsupported, Wound/death/archive, Curse/Broken/expiry, Miscast и zero-action stop. Counts1/1/1/1, totals24/10/9 для scripted source; completion/end-turn не новые actions |
| Public examples | [Sequential](../examples/m8/magic_simulation.py) и [process](../examples/m8/magic_parallel.py), соседний [builder](../examples/m8/magic_scenario.py) | [Seq subprocess test](../../tests/integration/test_m8_magic_simulation_example.py), [process subprocess test](../../tests/integration/test_m8_magic_parallel_example.py): external cwd/stored stdout/empty stderr. Только public APIs, без tests/tools/private helper imports |
| Измерения | [Fixtures](../../tools/m8_benchmark_fixtures.py), [profiling](../../tools/profile_m8.py), [comparison](../../tools/benchmark_m8_parallel.py) используют public simulation+summary | [10 fixture tests](../../tests/unit/test_m8_benchmark_fixtures.py), [24 profiling](../../tests/unit/test_m8_profiling.py), [17 comparison](../../tests/unit/test_m8_parallel_benchmark.py): full-record mismatch даже при равных агрегатах, guards/instrumentation/manifest/atomic output |

Точный состав **131 tests**: 79 production/API (16+13+11+8+1+23+6+1), 51 measurement (10+24+17), [1 historical process transport probe](../../tests/integration/test_m8_magic_process_contract_probe.py). Вместе с 365 single-run/boundary M8 tests — 496 tests M8; одноимённые unit/integration файлы считаются раздельно, повторного счёта нет. AST import audit 311 domain/engine/rules/simulation modules подтвердил направление зависимостей: simulation не зависит от application/adapters/CLI/balance/tools/tests; внутренние слои не импортируют simulation/process orchestration.

## Непосредственная книжная сверка

Локальные извлечённые страницы перечитаны главным агентом и независимым reviewer. Прототип, changelog и performance не заменяют нормативный текст.

| Источник | Подтверждённая граница |
| --- | --- |
| BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112 | Один turn/action, полный ход перед следующим actor. Каждый trial начинает исходный fresh scenario; ограничения N/B технические |
| Та же книга, Conditions / Broken, стр. 122 | Движение в Zone без врага и Recover; Broken/другая Zone сами по себе не defeat |
| Та же книга, Magic in the Old World / Spell Potency / Miscasts and the Rule of Nine, стр. 157 | Potency последнего Casting Test; pool > Level запускает обязательный Miscast, pool очищается после разрешения effect. Массовый слой не пропускает pending |
| Та же книга, Battle Magic / Curse of Cowardly Flight, стр. 162 | CV3/Long/Zone/Instant, Give Ground если возможно и Willpower против Potency; existing ordered chain не заменяется scalar outcome |
| Та же книга, Wounds Table, стр. 190–191 | Wound roll/untreated dice, Stomach Blow → Drained до конца следующего turn, отдельные lethal rows и обязательные effects |
| BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, Champions, стр. 91–92 | Minion defeated от Wound с attacker/GM disposition; Champion использует Wounds Table, не Minion policy |

Новых Rule IDs, house rules или противоречий нет. Старые Miscast ambiguities остаются открытыми; finite summary не доказывает полноту consumer catalogue. В [нормализованном Wounds-документе](../rules/wounds-and-conditions.md#rule-health-006--типы-npc) исправлена только устаревшая фраза об отсутствии GM Guide: дана ссылка на [NPC rules](../rules/npcs.md) и GM1.1 стр.91–92. [Architecture overview](../architecture/overview.md#контракт-последовательной-magic-simulation) синхронизирован с готовыми simulation/process API; runtime контракт не менялся.

## Публичная установка

Повторно проверено соответствие **411 Python/Schema файлов**: текущий src == ранее установленный package == содержимое ранее собранного wheel. Wheel SHA-256 `ad69e6d2d206b2877c54ec302cac118105de034d3904258e58431355da897ec6`, ранее собран offline в отдельной копии без repo egg-info мутаций/PDF/tests. Metadata README отражает предыдущий срез; новый wheel в этом doc-only аудите не собирался.

В отдельном cwd, без PYTHONPATH и с отключённым user site, проверены imports всех пяти magic simulation modules из installed site-packages. Последовательный и процессный public examples скопированы тремя файлами и исполнены на одном installed tree: оба stdout побайтно равны stored output, stderr пуст. Seq example — 32 single-run calls; process — 24 spawned trials в шести public calls, full equality/source identity и отсутствие оставшихся детей. Это проверка correctness/installation, не новый performance замер.

Evidence: `/private/tmp/towr-m8-mass-audit-_58kkwfd`, отчёт `/private/tmp/towr-m8-mass-installed-report.json`. Временные артефакты не нужны для использования проекта и не включены в Git.

## Сохранённая performance evidence

[Методика и интерпретация](../benchmarks/README.md#m8-sequential-и-spawn), raw [N100](../benchmarks/m8-parallel-100-2026-10-27.md) / [N1000](../benchmarks/m8-parallel-1000-2026-10-27.md): seed20261026/B4, workers1/2, batch32, три чередующихся повтора, два боевых inputs и отдельный zero-action control. В wall входят preflight/spawn/imports/serialization/normalization/shutdown и summary; проверки/input snapshots/GC вне timer. Все 54 measured full results/summary равны; 29 718 trials с прогревом. Unsupported включены в N.

Текущий manifest **396 files / SHA-256 `f20131529ea476bfc61b3f37c29262b1dbe13f60cdca615b8f5c44e7dd55130d` совпадает с обоими raw reports**: весь src Python, profile_m8.py, m8_benchmark_fixtures.py, benchmark_m8_parallel.py. Независимо проверены все 18 median rows, шесть equality markers, N100 digests/counts/actions/started/completed против historical baseline. Область baseline manifest другая; общий historical hash напрямую не сравнивается. Benchmark повторно не запускался.

N100 spawn медленнее; N1000 w2 локально быстрее двух боевых inputs в 1,506/1,547 раза. Один worker медленнее везде; control быстрее sequential на обоих N. Результаты CPython3.12.15/macOS26.5.1 arm64 не задают общий threshold/auto backend. CPU affinity/частота/внешняя нагрузка не контролировались; другие workloads/runtime/ОС, RSS/память процессов, workers/batch search и installed-wheel performance не измерены.

## Ограничения и проверки

Structural/source guards доверенной локальной simulation не являются подписью observations. Summary проверяет необходимые арифметические bounds, не восстанавливает удалённый журнал. Произвольная factory должна быть importable/picklable и давать свежий независимый RNG; математическая независимость и межверсионная воспроизводимость Python Random не доказаны.

O(N) compact records с общим parent scenario плюс in-flight transport/worker копии и журналы; bound2W не hard byte/RSS quota. uint64 admission не практический resource cap. Shutdown ждёт уже начатую/отправленную работу, не обещает мгновенный kill, порядок конкурентных errors или rollback factory side effects. Нового cache/framework/persistent pool нет.

Неподдержанные Wound/Miscast/chronology, обычный Attack Give Ground и неизвестные scene/route остаются явными stops ADR-0037. Broken не defeat; unsupported не draw/loss/success, не исключается из N и не перезапускается. Новых gameplay consumers, PC/других NPC/spell catalogues, assessment/balance/generation или JSON/CLI аудит не добавляет.

Последняя полная регрессия **3162 tests / 33 прежних errors (97,704 с)** — из предыдущей performance-вехи. Лог и Counter полных error headers/exception signatures сверены с baseline: новых ошибок нет, ошибки вне M8, полный suite не зелёный. Python-файлы src/tests/tools в этом аудите не менялись; повторять тот же полный набор и измерения оснований нет. Текущая проверка установленного пакета описана выше. 2906 локальных Markdown-путей, 61 anchor, границы импортов 311 modules, whitespace и сохранность 754 Python-файлов — OK; детали в [статусе](../project-status.md#последняя-проверка).

## Точный следующий шаг

Подготовить **ADR-0040 и конечный probe оценки magic-кандидатов** по принятой метрике M5/M6/M7: objective_achieved / все N, точные Fraction, явное ObjectiveRateWindow minimum/target/maximum и отдельные defeat/round-limit/unsupported rates. Любой наблюдавшийся unsupported делает кандидата непригодным; отсутствие unsupported в конечной выборке не доказывает полноту сценария.

Определить pure assessment и bounded evaluation явного списка: exact full input/summary source, общий preflight бюджета, полный aggregate-only report, stable ranking и explicit sequential/process внутри кандидата. Проверить reuse ObjectiveRateWindow и SimulationExecutionOptions без смешения magic и Minion-only types. Balance получает input+summary без records/journals; service errors сохраняют candidate context и не публикуют partial success. Контракт/probe предшествуют production assessment/list/service; staged/generation/JSON/CLI и новые gameplay consumers следуют отдельно. Новая существенная книжная неоднозначность потребует решения пользователя.
