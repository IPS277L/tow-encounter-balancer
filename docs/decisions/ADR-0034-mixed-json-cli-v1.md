# ADR-0034: Mixed JSON v1 и отдельные CLI-команды

Статус: принято, 2026-09-29. **Simulation v1 реализован: Schema/command, parser/summary/error encoder, service и simulate-mixed. Balance Schema/command/result/pure parser/result encoder также реализованы. Balance service/errors/error encoder и balance-mixed реализованы; [общий аудит](../audits/m7-external-readiness.md) завершён.** Пользователь выбрал это направление после [аудита генерации](../audits/m7-generation-readiness.md). Основа — ADR-0028/0029/0030/0031/0032/0033; образец внешней границы — [ADR-0027](ADR-0027-melee-json-cli-v1.md).

## Решение и совместимость

Добавить `python -m towr simulate-mixed INPUT` и `python -m towr balance-mixed INPUT`, а также одноимённые subcommands установленного `towr`. INPUT — UTF-8 файл относительно cwd либо `-` для stdin. Команда определяет семейство parser/service/encoder, в том числе для malformed JSON без kind. Нет autodetection, fallback, flags для переопределения seed/backend/window. Четыре прежние команды `simulate`, `balance`, `simulate-melee`, `balance-melee` и их форматы сохраняются.

Оба новых пути открывают существующий неподвижный numeric Mixed Minion-сценарий. Simulation возвращает aggregate summary; balance — каталог составов и полные aggregate reports этапов. CLI не рассчитывает awareness, Close, характеристики, GM decisions или движение. Домен, engine, RNG, seed scheme и метрика не меняются. Термин `players_and_allies` обозначает сторону; все участники этого контракта — Minions, не PC.

## Документы и строгий JSON

Шесть Draft 2020-12 Schema: `mixed-{simulation|balance}-{request|result|error}-v1.schema.json`, `$id=urn:towr:mixed-{simulation|balance}:{request|result|error}:1`. Они входят в package data; refs разрешаются только bundled registry, без сети. `schema_version="1"`, `ruleset="towr-pg1.4-gmg1.1"`; версия mixed независима от других семейств.

| Семейство | Request kind | Result kind | Error kind |
| --- | --- | --- | --- |
| Simulation | npc_mixed_simulation | npc_mixed_simulation_result | mixed_simulation_error |
| Balance | npc_mixed_balance | npc_mixed_balance_result | mixed_balance_error |

Все описанные поля обязательны; неизвестные/пропущенные поля запрещены на каждом уровне. Nullable поля присутствуют явно. Object key order несущественен, array order сохраняется. ID/source ID — непустые не-whitespace строки, без trim/normalization. Actor, definition, attack, group, zone и request ID имеют отдельные пространства имён; одинаковые строки в разных пространствах сами по себе допустимы.

Общий strict reader принимает только str/bytes (иной аргумент — TypeError). Duplicate object keys, неверный UTF-8, NaN/Infinity, lone surrogates и BOM дают invalid_json. Документ должен быть одним JSON object. Числовые входные поля принимают exact integer tokens: bool/string/float/exponent coercion запрещён, включая `1.0` и `1e0`. JSON Schema integer эту лексическую границу не доказывает; её обеспечивает parser.

Master seed — каноническая десятичная строка `0` либо `[1-9][0-9]*`, значение 0..2**64−1; знаки, ведущие нули и whitespace запрещены. Trials/trials_per_candidate — integers 1..2**64−1. Round budget, caps, keep, batch_size и общий бюджет — положительные integers с ограничениями existing constructors; точность сохраняется и выше 2**53−1. Means на выходе — конечные numbers; точные sums/trials также передаются. Дроби задаются `{numerator: int>=0, denominator: int>=1}`, на входе могут быть несокращёнными, на выходе сокращаются. Window обязателен: `0 <= minimum <= target <= maximum <= 1`; пресетов Easy/Medium нет.

Неизвестная строка schema_version даёт unsupported_version с `/schema_version`; отсутствующая/нетипизированная версия, неверный kind/ruleset — invalid_input. Execution: `{mode:"sequential"}` либо `{mode:"process", workers:1..61, batch_size:int>=1}`. Options/enum сохраняют существующий Python import path из ranged_simulation_models. Custom RNG, import paths, pickle и исполняемые выражения на wire отсутствуют.

## Общая mixed-сцена

`scenario` содержит ровно `definitions, actors, battlefield, side_order, actor_order, perspective_side, objective_target_ids, facts, pair_ranges, repeated_stagger_choice, actor_policies`.

| Объект | Поля и допуск |
| --- | --- |
| definition | `id, source_rule_id, resilience:{toughness,bonus}, attack, protection`; resilience values — integers >=0 |
| attack | `id, source_rule_id, skill, dice, threshold, damage, range_min, range_max, hands`; dice>=1, threshold 1..10, damage>=0 |
| Melee attack | `skill="melee", range_min=range_max="close", hands="1h"` либо `"2h"` |
| Shooting attack | `skill="shooting", range_min="medium", range_max="long", hands="2h"` |
| protection | `source_rule_id, skill="athletics", dice:int>=1, threshold:1..10` |
| actor | `id, definition_id, side, zone_id` |
| battlefield | `zone_ids:[ID,...], connections:[{first_zone_id,second_zone_id},...]` |
| pair_range | `first_actor_id, second_actor_id, target_range:"close"\|"medium"` |
| actor_policy | `actor_id, outnumbering_bonus_approved:bool, can_leave_zone:bool, targets:[target_decision,...]` |
| target_decision | `target_id, disposition, gm_approved:true`; disposition: knocked_out, disarmed_and_surrendered либо killed |

Definition IDs уникальны, каждая definition использована хотя бы одним actor, лишних definitions нет. Порядок definitions сохраняется отдельно в command. Actors задают порядок roster, round participants и placements; actor_order отдельно содержит всех actors ровно один раз. Обе стороны непусты. side_order — players_and_allies, затем opposition. Perspective задаётся явно; objective содержит всех противников ровно один раз с сохранением порядка. Repeated stagger choice — только suffer_wound.

Начальное состояние выводится однозначно: Minion/wound_limit=1, ноль ран, без conditions, первый обычный round, без исполненных действий, histories, pending follow-ups и исключений. У каждого actor один доступный attack profile, wields_weapon=True, holds_shield=False, current resilience равна definition. Damage multiplier=1, без ignores_armour/secondary effects/pool cap. Иные состояния, журналы, PC, свойства оружия/способности, reload actions, Aim/hidden и move actions не выражаются этим v1. Skill/range/hands передаются явно и проверяются, а не угадываются из имени definition.

Facts — десять явных booleans: targets_aware, clear_line_of_sight, stationary, all_zone_combatants_included, unmounted_combatants_only, no_higher_ground, no_additional_rules, no_other_test_modifiers, ammunition_sufficient должны быть true; requires_reload_action — false. Здесь нет Melee-полей zone_id/all_opponents_in_close_range и общего can_leave_zone.

Pair ranges задают каждую неупорядоченную пару противников ровно один раз; запрещены unknown/self/same-side/дубли, включая обратные. Orientation и порядок списка сохраняются. В текущем допуске Close требует одну Zone, Medium — соседние Zones, но связь графа сама по себе дальность не назначает. Graph сохраняется полностью, включая неиспользованные Zones; self/duplicate/unknown connections запрещены.

Обе роли Melee/Shooting обязательны во всём составе, но не обязательно на каждой стороне. У Shooting-actor не может быть Close-врага; у каждого actor при старте должна быть доступная цель. Policies охватывают всех actors ровно один раз и всех врагов каждого actor; targets задают приоритет и полные GM-approved defeat decisions. Outnumbering approval может быть true или false; автоматического одобрения нет. can_leave_zone задаётся отдельно каждому actor; true требует существующий допустимый путь в соседнюю Zone согласно typed admission. Это разрешение для выбора исхода Staggered, не автоматическое перемещение.

Schema проверяет форму, parser — references и existing typed admission. Отдельный mapper используется для simulation и reserve: принимает scenario, initial ID, round budget и JSON path prefix; фиктивный simulation envelope для balance не создаётся. Публичный encoder сохраняет exact source и проверяет lossless reconstruction. Typed sources с независимыми порядками roster/round participants/placements, не представимыми одним actors array, отвергаются; молчаливого упрощения нет. Порядки definitions, actor_order, objective, policies, targets, pair ranges и graph сохраняются.

## Simulation

Request: `schema_version, kind, request_id, ruleset, simulation:{master_seed,trials,round_budget}, execution, scenario`. Initial current request ID равен внешнему request_id.

Result: `schema_version, kind, request:<полный нормализованный вход>, seed_scheme:"towr:npc-mixed-trial:v1", runtime, summary`. Runtime: `package_version, python_implementation, python_version, rng:"random.Random"`; это описание среды, не доказательство воспроизводимости на всех версиях Python. Нет timestamps/hash/custom RNG claims.

Summary: `trials, outcome_counts:{objective_achieved,side_defeated,round_limit,unsupported_path}, total_attack_count, total_visited_round_count, mean_attack_count, mean_visited_round_count`. Counts и sums — integers >=0, сумма исходов равна trials. Compact records, individual trial seeds, журналы и rates в simulation result не передаются.

Service выбирает existing sequential/process runner с заданными options и штатным RNG, проверяет полный result/source, затем summary/source. Он не обещает streaming или отсутствие внутренних trial records. Pure encoder принимает command + existing summary с exact request source; source guard сам по себе не доказывает происхождение observations/RNG. Echoed execution закономерно различается между backend, aggregate summary должна совпадать при одинаковых source/seed/runtime.

## Balance

Request: `schema_version, kind, request_id, ruleset, reserve, generation, evaluation, execution`.

| Поле | Содержимое |
| --- | --- |
| reserve | `initial_request_id, round_budget, scenario` |
| generation | `groups, facts, pair_ranges, candidate_id_prefix, max_candidates` |
| group | `group_id, actor_ids, minimum_count, maximum_count` |
| evaluation | `master_seed, stages:[{trials_per_candidate,keep},...], max_total_trials, window:{minimum,target,maximum}` |

Внешний request_id независим от reserve.initial_request_id. Groups точно разбивают весь opposing reserve; actors внутри одной группы имеют одинаковую полную definition. Порядок actors группы определяет prefix при выборе численности; bounds `0 <= minimum <= maximum <= len(actor_ids)`. Fixed perspective side неизменна. Family facts/pair_ranges передаются **отдельно**, не выводятся из reserve. Family pairs обязаны точно совпадать с ordered template pairs, включая orientation. Facts и неизменные GM policies действуют для каждого состава и его достижимых состояний; caller подтверждает эти предпосылки.

Preflight использует existing MixedCandidateGenerationRequest: C — произведение числа вариантов counts минус пустой vector при наличии; C>=1 и <=max_candidates. Полный staged budget считается до materialization. Он включает полные повторные пакеты этапов, без оплаты только разницы trials. Seed/stages/window/bounds/partition проверяются существующими моделями. Parser не запускает генератор, runner, RNG или pool.

Арифметический допуск не гарантирует допустимость каждого subset. Потеря обязательной роли или начальной доступной цели — **generation_failed**, exit 3; такой vector нельзя молча пропускать или заранее исключать из C/budget. [ADR-0033](ADR-0033-mixed-composition-generation.md) задаёт count order, candidate/initial IDs и exact projections. Генератор фильтрует ordered pairs/targets/placements согласованно с составом и сохраняет весь graph.

Result: `schema_version, kind, request:<полный нормализованный вход>, seed_scheme, runtime, candidate_count, planned_trials, total_trials, candidates:[{candidate_id,counts},...], stage_reports, status, selected_candidate_ids`.

Stage report: `stage_index, trials_per_candidate, keep, total_trials, candidates, selected_candidate_ids, continuation_candidate_ids`. Candidate row: `candidate_id, summary, rates, status, window_match`. Summary та же, что в simulation. Rates — четыре сокращённые Fraction с JSON keys `objective_achieved, side_defeated, round_limit, unsupported_path`; Python-суффикс `_rate` в wire keys не переносится. Знаменатель каждой исходной доли — все trials, включая unsupported; после сокращения denominator может уменьшиться. Row status — eligible либо unsupported_observations, window_match boolean для eligible и null при unsupported. Window относится только к objective_achieved_rate.

Каталог candidates охватывает все generated vectors, даже не прошедшие следующие этапы; counts берутся из ordered vectors/source, не разбираются из ID. Stage_index начинается с 0. Reports сохраняют все observations исполненных stages. Continuation промежуточных stages допускает outside-window, исключает unsupported и сохраняет исходный candidate order; final selection использует последний этап, без возврата раннего выбора. В последнем запрошенном stage continuation всегда пуст. Раннее отсутствие continuation даёт no_eligible_candidates; выполнение всех stages — completed, в том числе с пустым итоговым выбором. Actual<=planned, неисполненные stages не добавляются; fallback к ближайшему кандидату отсутствует.

Encoder проверяет полную source chain: command → generation result → exact staged request/report, включая каждый projected scenario, aggregate и local/final selection. Reconstructing guards допускаются; они не исполняют generation service/RNG/pool. Выход не содержит compact trials. Observations повторных stages не складываются как независимые trials; total_trials отражает стоимость исполнения, не размер объединённой статистической выборки.

## Планируемые Python-модули

Все command/result модели — frozen/slotted, ordered lists копируются в tuple; wrong family/type отвергаются. Application/domain не импортируют adapters или CLI.

| Модуль | Контракт |
| --- | --- |
| application/mixed_simulation_models.py | MixedSimulationCommand(request, execution, definition_order) |
| adapters/mixed_simulation_json.py | parse_mixed_simulation_request; encode_mixed_simulation_result(command, summary); encode_mixed_simulation_error |
| application/mixed_simulation_service.py | execute_mixed_simulation(command) → existing NpcMixedSimulationSummary |
| application/mixed_simulation_errors.py | MixedSimulationExecutionError(request_id) |
| application/mixed_balance_models.py | MixedBalanceCommand(request_id, generation_request, execution, definition_order); MixedBalanceResult(generation_result, evaluation_result) |
| adapters/mixed_balance_json.py | parse_mixed_balance_request; encode_mixed_balance_result; encode_mixed_balance_error |
| application/mixed_balance_service.py | execute_mixed_balance(command) → MixedBalanceResult |
| application/mixed_balance_errors.py | MixedBalanceGenerationError(request_id, candidate_id, counts); MixedBalanceExecutionError(request_id, stage_index, candidate_id) |
| adapters/mixed_json_errors.py | MixedInputError, MixedSimulationInputError, MixedBalanceInputError |
| adapters/mixed_json_schema.py | validate_mixed_document(document, kind); validate_mixed_balance_document(document, kind) |
| adapters/_mixed_scenario_json.py | единый internal mapper/encoder scenario для simulation и reserve |

Mixed input errors — отдельная семья, не подкласс Melee/RangedInputError. Shared `_json_common.py` расширяет лишь тип принимаемого error factory; строгая лексика переиспользуется, historical RangedInputErrorCode и прежние imports остаются. Options/enum/window не переносятся ради нового режима. Можно ссылаться на неизменяемые bundled ranged seed/execution/ID fragments; mixed scenario/facts/policies/pairs имеют собственные Schema. Balance ссылается на mixed simulation fragments. Универсального codec/rules DSL не добавляется.

## Ошибки и CLI

Error envelope: `schema_version, kind, request_id:string|null, error`. Simulation error: `code, path:string|null, message`. Balance error дополнительно содержит `candidate_id:string|null, counts:[int>=0,...]|null, stage_index:int>=0|null`. Input errors оставляют весь balance execution context null; request_id извлекается только из валидной внешней метки, не из reserve. Path — JSON Pointer с escaping `~0/~1`; для неизвестного точного поля используется ближайший достоверный context (`/scenario`, `/reserve/scenario`), для family errors — путь в generation.

| Случай | code | Exit / context |
| --- | --- | --- |
| Неверный JSON/UTF-8/duplicate keys | invalid_json | 2; path null |
| Неизвестная строковая версия | unsupported_version | 2; /schema_version |
| Форма, references, typed admission/preflight | invalid_input | 2; достоверный JSON Pointer |
| Construction недопустимого состава | generation_failed | 3; известные candidate_id/counts, path/stage_index null |
| Simulation/evaluation/source failure | execution_failed | 3; для balance известные stage_index/candidate_id, counts/path null |

Application service отвергает wrong command через TypeError до dispatch. Любой Exception внутри соответствующей фазы оборачивается в typed application error; неизвестный контекст остаётся None. Cause/notes сохраняются через `raise ... from ...`, BaseException проходит. Generation и evaluation разделяются по фазе, а не предположению о типе чужой ошибки. Нет retry, fallback и partial result. JSON execution/generation messages общие: не сериализуют raw cause/notes/traceback. Ошибки encoder не маскируются под simulation failure.

CLI: exit 0 для любого полного результата, включая round_limit/unsupported_path/пустой выбор; 2 для usage/input, 3 для generation/execution, 4 для I/O. UTF-8 чтение, stdout write/flush и stderr diagnostic errors, включая закрытые потоки, обрабатываются общей существующей I/O границей. После сбоя вывода нельзя повторно писать error JSON в тот же stdout; shutdown не должен заменять exit 4 на 120. Usage соответствует прежнему CLI; корректный результат — один JSON object и newline, без progress/log в stdout. Main guard сохраняет работоспособность spawn.

## Источники и границы

Прямо перечитаны локальные книги: **BOOK-PLAYER-GUIDE 1.4, Equipment / Ranged Weapons, стр. 94; Rules / The Battlefield / Range, стр. 114; Attack Tests / Attack Modifiers, стр. 118–119; BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91; Understanding NPC Profiles, стр. 93; Brigands & Footpads, стр. 97**. Они обосновывают прежний numeric scope, дальности и локальный outnumbering; версия JSON/имена команд — архитектурное решение, не игровое правило.

Сохраняются [допуск ADR-0028](ADR-0028-mixed-minion-scenario.md), RULE-COMBAT-009/RULE-NPC-002, authored pair distances и отдельные GM approvals. Никаких новых Rule IDs/house rules. Значения из Footpad Dagger/Brigand Warbow — явные numeric проекции, не полный каталог или автоматический расчёт способностей. Движение, смена оружия, Shields/Defence, reload, PC, магия, Aim/hidden, универсальный бой и подбор за пределами резерва не входят в этот контракт.

## Проверка контракта и порядок реализации

[Конечные JSON-примеры](../examples/m7/json/README.md) и [probe](../examples/m7/json_contract_probe.py) проверяют точное отображение двух authored requests в existing public typed APIs. Simulation — 8 trials, balance — четыре состава/stages 2/4 keep 2/1, planned=16 на backend. Полные sequential/process results равны; проверены 12 constructor rejections и generation failure (0,1) после успешного preflight C=5/budget=18. Input/global RNG/children сохраняются. Saved outputs — наблюдения runtime, не Monte Carlo oracle. Probe не валидирует произвольный wire, строгую лексику или Schema; error fixtures иллюстрируют будущую форму.

1. **Реализовано:** три simulation Schema, command, shared scenario mapper, pure parser/summary encoder и typed input errors; deterministic lexical/admission/source/lossless tests плюс regression прежних семейств. Service/error encoder/CLI пока не входят.
2. **Реализовано:** simulation service/application error/error encoder и simulate-mixed; tests dispatch, phase/source errors, file/stdin/I/O/real spawn и installed wheel.
3. **Реализовано:** три balance Schema, command/result, pure parser/result encoder; exact reserve/family pairs/GM flags, budget/counts/source chain и finite integration tests.
4. **Реализовано:** balance service/application errors/error encoder и balance-mixed; phase-specific failures, no partial, I/O/installed CLI.
5. **Завершено:** [общий installed аудит](../audits/m7-external-readiness.md) обеих mixed-команд и регрессия четырёх прежних команд, актуальные примеры/статус.


## Реализованный первый срез

2026-09-29: [MixedSimulationCommand](../../src/towr/application/mixed_simulation_models.py), [pure parser/summary encoder](../../src/towr/adapters/mixed_simulation_json.py), [scenario mapper](../../src/towr/adapters/_mixed_scenario_json.py), [mixed input errors](../../src/towr/adapters/mixed_json_errors.py) и [локальная Schema validation](../../src/towr/adapters/mixed_json_schema.py) реализованы. Три bundled simulation Schema используют неизменённые ranged simulation/execution fragments и собственные mixed scenario/facts/pairs/policies. Package-data glob уже включает новые файлы. В `_json_common` расширен только тип error factory; ranged/Melee implementations и схемы не менялись. Command frozen/slotted, принимает tuple/list definition order с копированием; другие типы последовательности отклоняются.

[29 unit tests](../../tests/unit/test_m7_mixed_json.py) проверяют strict JSON/UTF-8/uint64/integer spelling, required/unknown fields на всех уровнях, Schema request/result/error, отдельное семейство ошибок, immutable command, fresh admission и ссылки, mixed roles/Skill/Range/Hands/Athletics, полные пары без reverse duplicates, actor-scoped can_leave_zone/outnumbering/GM decisions, exact summary source и lossless orders. [Два integration tests](../../tests/integration/test_m7_mixed_json.py) соединяют parser → existing runner → summary → encoder; полные sequential/process results и агрегаты равны. Saved result fixture проверяет кодирование заданной сводки, без ожидания Monte Carlo процента нового прогона. Parser/encoder не создают RNG/pool и не вызывают simulation; ошибочная source сводки отвергается до кодирования.

Новые 31 tests прошли на Windows/Python 3.14.5 (3,143 с). Error Schema задаёт только форму: application error/service/error encoder/CLI будут следующим срезом. Новых правил, balance parser или публичного execution API этот срез не добавляет.

Проверка первого среза: полная регрессия **2546 tests OK (288,168 с)** на Windows/Python 3.14.5; compileall, AST layer boundaries, 2173 локальных Markdown-пути и diff --check успешны. Изначальные изменения документации/fixtures сохранены. Python 3.12/другие ОС, новый installed wheel и performance не проверялись; commit/push не выполнялись.


## Реализованный второй срез

2026-09-29: [execute_mixed_simulation](../../src/towr/application/mixed_simulation_service.py) исполняет admitted command через existing sequential/process API с exact options и штатным RNG, проверяет полный result/source и summary/source, возвращает existing aggregate summary. [MixedSimulationExecutionError](../../src/towr/application/mixed_simulation_errors.py) сохраняет request ID и cause/notes; wrong command TypeError до dispatch, BaseException проходит. [Error encoder](../../src/towr/adapters/mixed_simulation_json.py) принимает только mixed input/execution errors; execution message общий, без raw cause/notes. Input diagnostics кодируются безопасно для UTF-8, включая escaped surrogates.

В [CLI](../../src/towr/cli.py) добавлен отдельный simulate-mixed с собственным dispatch/error family; четыре прежние команды и общая I/O boundary сохраняются. Encoder failures не превращаются в execution errors. Полный результат, включая unsupported_path/round_limit, даёт exit 0; invalid input — 2, execution — 3, I/O — 4. Нет partial stdout/retry/fallback.

[9 unit tests service](../../tests/unit/test_m7_mixed_service.py), [6 error JSON tests](../../tests/unit/test_m7_mixed_error_json.py), [13 CLI unit tests](../../tests/unit/test_m7_mixed_cli.py) и [11 CLI integration tests](../../tests/integration/test_m7_mixed_cli.py) прошли: 39 tests OK (38,514 с). Проверены exact dispatch/source, в том числе pair order/actor escape flags, wrong-family commands/errors, причина и notes, сбой второго trial после первого завершённого, generic output без частичной сводки, все четыре исхода как success, file/stdin/Unicode/real spawn и read/write/flush/closed streams. Полная регрессия: **2585 tests OK (349,513 с)**. Installed wheel проверен в чистом venv вне repo/PYTHONPATH: 367 Python/Schema-файлов равны src, module/console × sequential/process дают равные mixed aggregates, четыре прежние команды/семейства ошибок сохранены, три mixed Schema/local refs и pip check успешны. Compileall, AST boundaries, 2184 локальных Markdown-пути и diff --check успешны.

Следующий срез — balance Schema/command/result/pure parser/result encoder. Simulation API/CLI остаётся в прежнем scope numeric Minions; новых правил, изменений RNG или balance wire в этом срезе нет.


## Реализованный третий срез

2026-09-29: [MixedBalanceCommand/Result](../../src/towr/application/mixed_balance_models.py), [pure parser/result encoder](../../src/towr/adapters/mixed_balance_json.py), MixedBalanceInputError и три bundled balance Schema реализованы. [Registry](../../src/towr/adapters/mixed_json_schema.py) разрешает локальные refs на mixed simulation scenario/facts/pairs/summary/error и неизменённые ranged seed/execution fragments; simulation helper сохраняет сигнатуру. Shared scenario mapper выделяет два внутренних helpers pair_ranges; reserve использует собственные ID/round budget/path prefix без фиктивного simulation envelope. Strict lexical reader, simulation Schema и CLI не менялись.

[36 unit tests](../../tests/unit/test_m7_mixed_balance_json.py) покрывают required/unknown fields, strict JSON/UTF-8/version/uint64/integer controls, Fraction normalization, большие бюджеты выше 2**64, immutable tuple inputs, exact group partition, отдельные family facts/pairs, actor-scoped escape/GM flags, reserve context pointers и разные error families. Encoder сохраняет lossless input и полную generation/staged source chain, каталог counts берёт из ordered vectors, не разбирает ID. Проверены ранняя остановка, outside-window continuation, четыре исхода, unsupported exclusion и пустой final selection. Результаты кодируются без вызова генератора/RNG/pool; guards уже проверенных immutable моделей не дублируют исполнение.

Допуск bounds A.minimum=0/C=5/budget=18 не материализует составы: subsequent existing generation отклоняет (0,1) из-за потери Close-цели, без silent skip и без input-error подмены. Family pairs требуют exact ordered equality, включая orientation, с `/generation/pair_ranges` context; snapshots копируются отдельно от reserve. Чужой pair order/GM policy/window делает результат чужим source даже при прежних ID.

[Два integration tests](../../tests/integration/test_m7_mixed_balance_json.py) соединяют parser → existing generator → staged evaluator → typed result → encoder. Проверены fixture C=4/planned=16 и вариант с дополнительной definition, обратными groups/targets/pairs и полной GM disposition; sequential/process reports и JSON равны после исключения echoed execution. Saved result fixture проверяет кодирование заданных aggregates, не Monte Carlo исход нового прогона. Новые 38 tests OK (15,201 с), Windows/Python 3.14.5.

Error Schema пока задаёт форму. Application service/errors/error encoder/CLI balance-mixed остаются следующим срезом. Новых боевых правил/метрик, зависимостей domain на wire или универсального codec нет.

Проверка третьего среза: **2623 tests OK (344,328 с)**, Windows/Python 3.14.5; compileall, AST layer boundaries, 2195 локальных Markdown-пути и diff --check успешны. Исходные изменения сохранены; новый installed wheel и другие версии Python/ОС не проверялись. Commit/push не выполнялись.

## Реализованный четвёртый срез

2026-09-29: [execute_mixed_balance](../../src/towr/application/mixed_balance_service.py) связывает existing generator и staged evaluator, передаёт exact request/options и возвращает полный MixedBalanceResult. Проверяет generation type/source до evaluation; result проверяет точную staged chain. [Application errors](../../src/towr/application/mixed_balance_errors.py) классифицируются по активной фазе, сохраняют внешний request ID, известные candidate/counts либо stage/candidate и cause/notes. Wrong-family command даёт TypeError до dispatch, BaseException проходит. Нет retry, fallback или partial result.

[Error encoder](../../src/towr/adapters/mixed_balance_json.py) принимает только mixed balance input/application errors, проверяет error Schema и оставляет неизвестный context null. Execution messages общие даже при изменённых exception args; raw causes/notes не попадают в JSON. [CLI balance-mixed](../../src/towr/cli.py) выбирает эту семью по имени команды, использует прежнюю UTF-8 file/stdin/I/O boundary и exit 0/2/3/4. Encoder failures не маскируются; повторной записи JSON после output failure нет.

[17 service/error unit tests](../../tests/unit/test_m7_mixed_balance_service.py), [12 CLI unit tests](../../tests/unit/test_m7_mixed_balance_cli.py), [3 service integration tests](../../tests/integration/test_m7_mixed_balance_service.py) и [9 CLI integration tests](../../tests/integration/test_m7_mixed_balance_cli.py) проверяют exact source/options, pair order/actor escape flags, wrong-family boundaries, invalid subset (0,1) после успешного preflight, сбой второй materialization, поздний trial failure после полного stage и отсутствие partial output. Проверены все исходы/empty selection как success, interrupts, malformed/wrong-family inputs шести команд, pool failure, file/stdin/Unicode/real spawn и read/write/flush/closed streams. Число новых tests — 41.

Новых игровых правил, метрик или runtime dependencies нет. Базовый admission и книжные ссылки выше сохраняются. Общий аудит ADR-0034 остаётся следующим шагом; проверки текущего среза записаны в [статусе](../project-status.md#последняя-проверка).

Проверка четвёртого среза: **2664 tests OK (406,250 с)**, Windows/Python 3.14.5. Offline installed wheel: 374 Python/Schema-файла равны src; обе mixed-команды module/console × sequential/process вне repo/PYTHONPATH дают равные результаты. Шесть packaged mixed Schema/local refs, прежние команды, phase errors и pip check прошли. Compileall, AST boundaries, 2204 локальных Markdown-пути и diff --check успешны. Python 3.12/другие ОС и новые performance-измерения не проверялись; commit/push не выполнялись.

## Общий аудит

2026-09-29: [матрица готовности](../audits/m7-external-readiness.md) сопоставляет контракт с шестью Schema, pure adapters, immutable commands/results, services, CLI и 149 tests ADR-0034. Установленные 374 Python/Schema-файла равны src; module/console × sequential/process, прежние команды, Schema refs, ошибки, runtime и cleanup проверены. Public probe/пример работают вне repo. Код и тесты при аудите не менялись. План этого ADR закрыт. Пользователь выбрал следующим направлением магию в боевой симуляции; первый шаг M8 — отдельный ограниченный контракт интеграции существующих K1 APIs.
