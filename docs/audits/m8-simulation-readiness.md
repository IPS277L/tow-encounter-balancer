# Аудит последовательной magic simulation ADR-0038

Дата: 2026-10-26. **Независимые последовательные прогоны и aggregate-only summary готовы в ограниченной границе [ADR-0038](../decisions/ADR-0038-independent-magic-simulations.md).** Single-run [ADR-0037](../decisions/ADR-0037-magic-scenario-runner.md) и его gameplay scope не менялись. На старте рабочее дерево чистое, HEAD `6005ec5` (M8 P4). Commit/push не выполнялись.

## Реализация и доказательства

| Обязанность | Реализация | Проверка |
| --- | --- | --- |
| Seed и request | [npc_magic_models.py](../../src/towr/simulation/npc_magic_models.py): отдельная scheme `towr:npc-magic-trial:v1`, SHA-256/нулевой byte/uint64be, frozen/slotted source request | 3 golden vectors и независимый struct encoding; uint64/uint256, bool/type/range/family отказы, index admission до factory; ranged/melee/mixed schemes сохраняются |
| Compact record | Полный immutable input и scalar outcome/actions/started/completed, без result/journal/pending/RNG; источник разделяется ссылкой | Полный source/equal copy, поля модели, zero-action unsupported, terminal action minimum, completed<=actions, round/actor bounds и premature limit |
| Полный batch result | Ordered tuple/list копируется и сортируется, ровно 0..N-1, parent-derived seed и полный scenario | Missing/duplicate/foreign index/seed/source, чужие семьи/Enum, defensive list copy; counts и три totals выводятся из records |
| Trial/batch | [npc_magic_simulation.py](../../src/towr/simulation/npc_magic_simulation.py): новый RNG и один existing runner на каждый index, typed full source до scalar projection | 13 unit tests: property spies не допускают проекцию foreign same-ID source; equal source copy сохраняет original identity; factory/runner/record failures на втором trial останавливают пакет, constructor/BaseException/cause/notes проходят без retry/partial |
| Summary | [Модель](../../src/towr/simulation/npc_magic_summary_models.py) и [pure projection](../../src/towr/simulation/npc_magic_summary.py): полный request, counts и actions/started/completed totals | 11 tests всех inequalities ADR, strict types/families и count sum; no records/results/journals/rates/means, no engine/RNG/pool вызовов |
| Real integration | [8 tests](../../tests/integration/test_m8_npc_magic_simulation.py) используют existing M8 transitions | Четыре исхода одного source; 3 Champion Wounds/daily receipts/rolls и смерть Wizard; архив defeated ally; pending Miscast, zero-action stop и foreign full source, Stomach Blow expiry, Curse/Broken Recover без ложного defeat |
| Воспроизводимость | Independent Random(seed), отдельный source на каждый batch без live-state переноса | Repeat/reverse/prefix/rename, extra draws только в первом trial; shared source/новые RNG identities и input/global RNG unchanged. Не фиксируется Monte Carlo rate |
| Публичный пример | [magic_simulation.py](../examples/m8/magic_simulation.py) + соседний [magic_scenario.py](../examples/m8/magic_scenario.py) | [Subprocess test](../../tests/integration/test_m8_magic_simulation_example.py) вне repo cwd, [stored output](../examples/m8/magic_simulation.output.txt); installed-wheel stdout равен source example без PYTHONPATH |

Всего **49 новых tests: 16 models + 13 execution + 11 summary + 8 real integration + 1 external-cwd example**. Наличие guards доказывает согласованность input и observations, а не подлинность dice или математическую независимость произвольной factory.

## Public example и installed distribution

Четыре scripted trials одного input B=4: OBJECTIVE 2 actions / 1 started / 1 completed; PERSPECTIVE_DEFEATED 9 / 4 / 4; LIMIT 12 / 4 / 4; UNSUPPORTED Miscast 1 / 1 / 0. Counts=1/1/1/1, totals=24 actions / 10 started / 9 completed, 120 d10. Отдельный replay использует тот же scripted stream и проверяет lethal Champion chain за 48 d10. Zero-action missing-departure stop не расходует dice и имеет другой полный source при тех же ID/seed. Ещё 26 seeded calls проверяют воспроизводимость; всего 32 single-run calls. Эти конечные observations не являются Monte Carlo-измерением сложности.

Offline wheel собран из отдельной временной копии pyproject/README/LICENSE/src, без PDF/tests и без изменения repo egg-info. Установлен в отдельный venv; два public example файла скопированы во внешний каталог. Запуск без PYTHONPATH и с отключённым user site дал тот же stdout и пустой stderr. Все 410 установленных Python/Schema файлов побайтно совпали с src. Wheel SHA-256: `f47ce4f8aed7eeccfe5f85d3b827a79a975a681f308c6dcbf49c69ab004494e7`. Build/install/stdout evidence: `/private/tmp/towr-adr0038-audit-2h_oo8f6` (временные файлы, не обязательная зависимость примера).

## Проверки и ограничения окружения

macOS arm64 / Python 3.12.15. Новые 40 unit tests — OK (0,042 с), 9 integration/example tests — OK (0,423 с). Полный набор: **3080 tests, 33 прежних errors (96,293 с)**. Counter полных error headers и exception signatures точно равен предыдущему полному аудиту: 32 TypeError в старых frozen/slotted Aim property assertions и 1 ValueError от replace поля init=False. Новых ошибок нет; полный suite не зелёный. Подробности — [open questions](../open-questions.md#проверки-dataclasses-на-python-312). Текущий полный лог: `/private/tmp/towr-adr0038-tests.log`.

```sh
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m unittest discover -s tests -q
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python -m compileall -q src tests tools docs/examples/m8
git diff --check
```

Compileall, AST dependencies/public imports, 2699 локальных Markdown-путей/входящие status/question anchors и whitespace — OK. Production diff ограничен четырьмя новыми simulation-модулями; прежние domain/engine/rules и существующие tests/tools не менялись. Независимый агент проверил контракт, production и test matrix; обнаруженных дефектов нет. Другие ОС/Python и performance не проверялись.

## Непосредственная книжная сверка

| Источник | Проверенный предел |
| --- | --- |
| PG 1.4, Rules / Combat, стр. 112 | Полный ход перед следующим actor; completion/end-turn не новые actions |
| PG 1.4, Conditions / Broken, стр. 122 | Уход/Recover не равны defeat |
| PG 1.4, Magic in the Old World / Miscasts, стр. 157 | Mandatory pending сохраняется, pool очищается после effect |
| PG 1.4, Battle Magic / Curse of Cowardly Flight, стр. 162 | Give Ground перед Willpower/Broken |
| PG 1.4, Wounds Table, стр. 190–191 | Временный Stomach Blow и lethal effects различаются |
| GM 1.1, Allies and Antagonists / Minions, Champions, стр. 91–92 | Defeated Minion и Champion Wounds Table |

Прочитан локальный извлечённый текст независимым reviewer. Новых Rule IDs/house rules нет. Неоднозначности Miscast не разрешены техническими seeds или агрегированием.

## Граница готовности и следующий шаг

Сохраняются все single-run stops: неизвестные scene/route, обязательные неподдержанные Wound/Miscast effects, обычный Attack Give Ground и chronology. Aggregate counts не скрывают UNSUPPORTED_PATH. Records сохраняют input и scalars; для диагностики требуется повтор с тем же source/indexed seed и совместимой factory/runtime. Межверсионная гарантия Python Random не заявляется.

Следующий законченный шаг — **отдельный контракт первого profiling-среза последовательных magic-пакетов**: ограниченные workloads, исходные наблюдения/замеры и критерии сравнения, без новой gameplay policy или автоматического process backend. Assessment/balance/generation и JSON/CLI остаются последующими отдельными контрактами.
