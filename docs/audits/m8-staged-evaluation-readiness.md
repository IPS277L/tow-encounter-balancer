# M8: аудит поэтапной magic-оценки

Дата: 2026-10-27. Проверены [ADR-0041](../decisions/ADR-0041-staged-magic-evaluation.md), helper/models/service/error, 33 implementation tests и самостоятельный пример. На старте HEAD a422d25 и 18 dirty/untracked файлов прежних срезов; они сохранены как исходные изменения. Production src и прежние tests/tools в этом аудите не менялись.

**Поэтапная оценка явного magic-списка готова в границе ADR-0037/0041.** Полные повторные пакеты, continuation/final selection, верхний бюджет, точная source/report chain и ошибки согласованы. Базовый evaluator закрыт [аудитом ADR-0040](m8-evaluation-readiness.md). Generation и M8 JSON/CLI требуют отдельных контрактов.

## Матрица готовности

| Обязанность | Реализация и проверка |
| --- | --- |
| Typed input | [Models](../../src/towr/balance/magic_staged_evaluation_models.py), [21 pure tests](../../tests/unit/test_m8_magic_staged_evaluation.py): frozen/slotted stage/request/result/status, strict tuple/list без consumption generator, exact int без bool/coercion, uint64 seed/N, positive keep/cap. Все stages и полный input проверяются до работы; N строго растёт, keep может расти; shared window и pickle paths сохранены |
| Бюджет | U[0]=C, U[i+1]=min(U[i],keep[i]), planned=sum(U[i]×N[i]); local cap=len(current candidates)×N[i]. Проверены 240/2240, сокращённые actual140/40, один этап, cap239 и большие Python integers без uint64 cap суммы. Prefix считается заново с index0: 10→100 стоит110, stage/IDs/backend/N не входят в seed |
| Continuation | [Helper](../../src/towr/balance/magic_staged_evaluation.py): только ELIGIBLE, включая outside-window и ROUND_LIMIT; exact Fraction distance, stable ties/cutoff, возврат исходного порядка. Unsupported остаётся в полном report и знаменателе всех rates, но исключает целого кандидата из продолжения |
| Финал | Непоследнее пустое continuation → NO_ELIGIBLE_CANDIDATES. Полная/одноэтапная цепочка → COMPLETED даже с all-unsupported/пустым выбором. Выбор только последнего bounded report и window_match=True; ранние совпадения не возвращаются |
| Source chain | Общая private _stage_request используется service и result guards. Полное value equality по ordered IDs/full scenario/Wizard/profile/frames/policies, seed/N/window/localcap/keep до continuation. Guards отвергают partial/extra/reordered/restored reports, чужие same-ID scenarios и другие families; equal immutable copies допустимы без rebinding |
| Исполнение | [Service](../../src/towr/application/magic_staged_evaluation_service.py), [9 unit tests](../../tests/unit/test_m8_magic_staged_evaluation_service.py): один existing bounded call на достигнутый этап с тем же объектом execution; полные повторные пакеты, typed/full source до helper и следующего call. Нет нового rng_factory/scheduler/pool или prefix reuse |
| Ошибки | [MagicStagedEvaluationError](../../src/towr/application/magic_staged_evaluation_errors.py): stage_index с0, candidate_id либо None, полная cause/worker-note chain. Проверены second-stage candidate failure/no-third, assembly/continuation/foreign report, direct preflight/final constructor/BaseException; без partial/retry/fallback |
| Реальные backend | [3 integration tests](../../tests/integration/test_m8_magic_staged_evaluation.py): full sequential/spawn equality/replay/rename/reorder, parent sources, input/global RNG/children/child PID, startup failure chain. Scripted N3→N4 даёт native counts1/1/1/0→1/1/1/1, totals23/9/9→24/10/9, actual7/COMPLETED/empty; N4→N5 останавливается после4 из planned9, N5 не исполняется |
| Границы | Balance получает inputs/aggregates без records/journals/RNG/options; domain/engine/rules/simulation не приобретают outward dependencies. Старые APIs, shared classes, seed schemes и formats сохранены. Budget не RSS quota; traceback может удерживать промежуточные объекты, cleanup ждёт начатую работу |

Матрица: **33 implementation tests = 21 pure + 9 service + 3 integration**. Синтетические observations проверяют арифметику и guards; scripted production runners — все четыре исхода и unsupported внутри окна. Structural validation не доказывает происхождение manual aggregates. Ни процент Monte Carlo, ни победитель не закреплены в assertions. Независимое read-only ревью контракта, кода, tests и нового примера блокеров не выявило.

## Самостоятельный пример

[magic_staged_evaluation.py](../examples/m8/magic_staged_evaluation.py) вызывает public staged API, builder/printer из [magic_evaluation.py](../examples/m8/magic_evaluation.py) и прежние [magic_simulation.py](../examples/m8/magic_simulation.py)/[magic_scenario.py](../examples/m8/magic_scenario.py). Четыре файла копируются вместе, без tests/private imports. Champion-Wizard Level2, Curse, allied/enemy Shooting Minions и все scene/route/GM facts прежние; две authored альтернативы меняют только enemy target priority. Это numeric experiment inputs, не именованные книжные NPC.

Seed42, B4, окно [1/4,1/2,3/4], stages=(8,keep1),(32,keep1), planned/max48 на backend. Process workers2/batch3. До печати сравниваются полные sequential/process reports, parent request и derived simulation sources, window identity, actual<=planned<=cap, input/global RNG и отсутствие детей. Число этапов/selection в assertions не подменяется ожидаемым победителем.

[Stored output](../examples/m8/magic_staged_evaluation.output.txt), CPython3.12.15/macOS arm64:

| Этап / ID | Goal / defeated / limit / unsupported | Результат |
| --- | --- | --- |
| N8 ally-first | 6/0/0/2 | Unsupported, не продолжает |
| N8 wizard-first | 8/0/0/0 | Eligible вне окна; local selected пуст, continuation непуст |
| N32 wizard-first | 23/0/4/5 | Goal23/32 внутри окна, но unsupported даёт window_match=None; финальный выбор пуст |

Status COMPLETED, actual48 на backend; **96 trials на запуск примера**. Пакет N32 вычислен целиком, первые8 повторены. Counts/rates этапов не складываются в одну оценку; этапы не независимы. Наблюдение seed/runtime не является preset, oracle, гарантией сложности/полноты тактики или новым performance-измерением.

[Два новых integration tests](../../tests/integration/test_m8_magic_staged_evaluation_example.py) — **OK (1,562 с)**: четыре скопированных файла из external cwd дают stored stdout/empty stderr. Поздний отказ выполняет реальные 16trials первого этапа, затем real bounded wrapper получает runner OSError+note. ID берётся из фактического второго stage request; проверяются stage1 → MagicBalanceEvaluationError → исходный OSError identity/notes, no process/retry/next и сохранность input/global RNG/children. Marker подтверждает 16trials; stdout пуст, entry point пишет контекст в stderr и пробрасывает исходную цепочку.

## Установленный пакет

Свежий wheel собран offline из временной копии текущего src и установлен в отдельное чистое venv вне repo. Все **420 Python/Schema files** побайтно равны src, wheel и installed site. Для subprocess удалён PYTHONPATH и отключён user site; isolated imports staged service/models указывают в installed site.

Обычный четырёхфайловый пример из external cwd даёт stored stdout/empty stderr; поздний stage failure после 16real trials повторяет тот же error/notes/cleanup/empty-stdout путь на установленном пакете. Это проверка текущего staged API, отдельно от прежнего installed contract probe.

Wheel SHA-256: `38ffe7bd2eb143b2ab1676369502da3463719c9befaa6d3cb44aaa369df327e9`. Evidence: `/private/tmp/towr-m8-staged-audit-f4mix3_q`, report `/private/tmp/towr-m8-staged-wheel-report.json`. Временные файлы не нужны для использования проекта и не входят в Git. Зависимости JSON/CLI не устанавливались в audit venv: этот пример их не использует; прежний wire scope не перепроверяется как новый M8 format.

## Книги и ограничения

Непосредственно перечитаны локальные извлечённые страницы:

| Книга / глава / страницы | Сохранённая граница |
| --- | --- |
| BOOK-PLAYER-GUIDE1.4, Rules / Combat, стр.112 | Полный ход перед передачей actor; stages/N/окно — технические параметры |
| Та же книга, Conditions / Broken, стр.122 | Broken ведёт к уходу/Recover, сама по себе не defeat |
| Та же книга, Magic in the Old World / Casting a Spell / Interrupted Casting, стр.156 | Casting action, накопление и skipped Tests; normative текст отделён от примера |
| Та же книга, Spell Potency / Miscasts and the Rule of Nine, стр.157 | Potency последнего Test, обязательный Miscast/pending не обходится отбором |
| Та же книга, Battle Magic / Curse of Cowardly Flight, стр.162 | Give Ground если возможно, затем Willpower против Potency исходных целей |
| Та же книга, Wounds Table, стр.190–191 | Champion Wound lifecycle; Stomach Blow до конца следующего хода и отдельные lethal rows |
| BOOK-GM-GUIDE1.1, Allies and Antagonists / Minions / Champions, стр.91–92 | Minion defeated от Wound с attacker/GM disposition; Champion использует Wounds Table |

Источники доступны. Новых Rule IDs/house rules/противоречий нет. Unsupported stops других обязательных Wound/Miscast/chronology/Attack Give Ground/scene-route сохранены; unknown facts не выводятся из adjacency. Полный NPC/spell/Talent/item каталог, PC, универсальная тактика, generation, M8 JSON/CLI, prefix reuse и confidence presets не входят в готовность ADR-0041.

## Итоговая проверка

Полная регрессия: **3240 tests / 33 прежних errors (115,653 с)**. Counters полных error headers/subtests и exception signatures точно равны предыдущему прогону 3238 tests; новых ошибок нет. Полный suite не зелёный: 32 прежние ошибки frozen/slotted Aim .state и одна dataclasses.replace(init=False) на Python3.12. Compileall, 3106 локальных Markdown-путей/79 anchors, import boundaries 311 core modules, purity пяти magic balance modules/public imports, SHA всех 792 исходных Python/JSON файлов src/tests/tools и whitespace — OK. [Команды/логи](../project-status.md#последняя-проверка). Другие ОС/runtime/RSS не проверены.

Source/harness SHA-256 `ab63ad5a8f8c1608050b759407fca65893d9885c5e65c93242ca0da131f8d92f` не изменился в аудите. Simulation/engine/fixtures/tools прежние, benchmarks не повторялись; исторические raw reports предшествуют новым outer balance/application modules и не являются замерами staged evaluator. Исходные Python/JSON files src/tests/tools сохранены побайтно; добавлены example/output/audit и два tests в одном новом файле. Commit/push не выполнялись.

## Следующий шаг

Подготовить контракт ограниченной генерации magic-кандидатов из явно заданного резерва. Зафиксировать неизменные perspective-сторону/Champion-Wizard/spell, изменяемые numeric Minion-группы, области facts/frames/routes/policies и полную проекцию roster/targets/objective/GM decisions. Каждый состав обязан пройти existing magic admission; C/max_candidates и полный staged budget проверяются до материализации. Недопустимые составы не пропускать молча; scene facts и GM approvals не вычислять по догадке.

Сначала ADR/матрица и конечные допустимые/отклоняемые примеры, production отдельно. Новые gameplay consumers, auto tactics, JSON/CLI, prefix reuse и generic framework в контракт не включать.
