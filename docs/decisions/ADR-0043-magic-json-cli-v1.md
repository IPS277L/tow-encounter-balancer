# ADR-0043: Magic JSON v1 и отдельные CLI-команды

Статус: принят и закрыт [общим аудитом](../audits/m8-external-readiness.md), 2026-10-28. **Пять срезов simulation/balance JSON/CLI завершены в текущем bounded magic scope.** Основа — [ADR-0037](ADR-0037-magic-scenario-runner.md), [simulation/process ADR-0038/0039](ADR-0039-process-magic-simulations.md), [assessment/stages ADR-0040/0041](ADR-0041-staged-magic-evaluation.md), [генерация ADR-0042](ADR-0042-magic-composition-generation.md) и [её аудит](../audits/m8-generation-readiness.md). Технический образец — [Mixed wire ADR-0034](ADR-0034-mixed-json-cli-v1.md), не перенос mixed классов/полей в магию.

## Решение и совместимость

Добавить python -m towr simulate-magic INPUT и balance-magic INPUT, а также одноимённые subcommands установленного towr. INPUT — UTF-8 файл относительно cwd или '-' для stdin. Команда определяет семейство parser/service/encoder даже при malformed JSON без kind; нет autodetection/fallback или flags для скрытого переопределения seed/backend/window. Шесть прежних ranged/Melee/mixed commands и formats/seed schemes сохраняются.

Simulation открывает existing independent magic trials и возвращает aggregate summary. Balance открывает explicit reserve → generator → staged evaluator, возвращает полный catalog и все aggregate rows выполненных stages. JSON не выбирает тактику/GM facts/маршруты по численности, не добавляет PC/spells/effect consumers. Wizard остаётся Champion; players_and_allies — сторона, не обещание PC-модели. Domain/engine/rules/simulation/balance не импортируют wire/CLI.

## Строгий документ и лексика

Шесть отдельных Draft2020-12 Schema: magic-{simulation|balance}-{request|result|error}-v1.schema.json; $id=urn:towr:magic-{simulation|balance}:{request|result|error}:1. Bundled registry разрешает только локальные refs, без сети. Общие ranged seed/execution fragments можно reuse без изменения их прежних constraints; scenario/facts/frames/summary принадлежат magic. Schema version '1', ruleset 'towr-pg1.4-gmg1.1'.

| Семейство | Request kind | Result kind | Error kind |
| --- | --- | --- | --- |
| Simulation | npc_magic_simulation | npc_magic_simulation_result | magic_simulation_error |
| Balance | npc_magic_balance | npc_magic_balance_result | magic_balance_error |

Все описанные поля обязательны, additionalProperties=false на каждом object level; nullable поля передаются явно, empty arrays не пропускаются. Object key order несущественен; каждый array order сохраняется. ID — nonblank string без trim/coercion; request/scenario/actor/definition/caster/day/group/zone/attack IDs — отдельные namespaces. Равные строки в разных namespaces допустимы.

Shared strict reader принимает только str/UTF-8 bytes (другой аргумент TypeError). Duplicate object keys, invalid UTF-8, BOM, lone surrogates, NaN/Infinity и не-object root запрещены. Все входные числовые поля — exact integer tokens: bool/string/float/exponent coercion, включая1.0/1e0, запрещён. Schema integer не заменяет lexical guard. Non-finite/invalid JSON — invalid_json; не-object root и числа с float/exponent syntax — invalid_input по прежней boundary.

Master seed — canonical decimal string '0' или [1-9][0-9]*, значение0..2**64−1; знак/leading zeros/whitespace запрещены. N/trials_per_candidate — integers1..2**64−1. Round budget/caps/keep/batch_size — positive ints с existing constructor limits; общие budgets/C не ограничиваются uint64, сохраняют точность выше2**53. Window — minimum/target/maximum Fraction {numerator:int>=0,denominator:int>=1}, 0<=min<=target<=max<=1. Несокращённые input fractions допустимы, echoed/result fractions сокращаются. Difficulty presets отсутствуют.

Execution — {mode:'sequential'} или {mode:'process',workers:1..61,batch_size:int>=1}. Custom RNG/import path/pickle/executable expressions на wire отсутствуют. Options/Mode/Window сохраняют прежние Python class/import/pickle identities. Неизвестная string schema_version даёт unsupported_version с /schema_version; missing/wrong type version, чужие kind/ruleset — invalid_input.

## Полный fresh magic scenario

Один internal mapper используется simulation и reserve; получает scenario document, round_budget и JSON path prefix. Фиктивный simulation envelope для balance не создаётся. **Внешний request_id независим от scenario.scenario_id и wizard.day_id.** Magic round не имеет отдельного ID; reserve.initial_request_id из M7 не вводится.

Scenario имеет ровно scenario_id, definitions, actors, battlefield, placements, side_order, activation_order, perspective_side, objective_target_ids, facts, wizard, spell, actor_policies, scene_frames, repeated_stagger_choice.

| Объект | Поля / неизменённый допуск |
| --- | --- |
| definition | id, source_rule_id, injury_policy, wound_limit, resilience:{toughness,bonus}, attacks:[attack,...], protection:[protection,...] |
| Wizard definition | injury_policy='champion', wound_limit=null, attacks=[]; normal unarmoured Resilience, один Athletics Protection |
| Minion definition | injury_policy='minion', wound_limit=1, один numeric Shooting attack и один Athletics Protection |
| attack | id, source_rule_id, skill='shooting', dice>=1, threshold1..10, damage>=0, range_min/range_max short/medium/long, hands1h/2h |
| protection | source_rule_id, skill='athletics', dice>=1, threshold1..10 |
| actor | id, definition_id, side; ordered array задаёт roster/round participants, **не placements** |
| battlefield | zone_ids:[ID,...], connections:[{first_zone_id,second_zone_id},...] |
| placement | entity_id, side_id, zone_id; отдельный ordered array placements покрывает всех actors ровно один раз |
| wizard | actor_id, caster:{id,source_rule_id,wizard_level:1..4,casting_profile:{dice,threshold}}, day_id |
| spell | rule_id, lore_id, casting_value, target_kind, range, duration — полный FormalSpellDefinition |
| actor_policy | actor_id, willpower:{dice,threshold}, speed:slow/normal/fast, target_actor_ids, defeat_decisions, attack_id, casting_policy, zone_priorities |
| defeat_decision | attacker_id, target_id, disposition:killed/knocked_out/disarmed_and_surrendered, gm_approved:true |

Resilience toughness/bonus — ints>=0; Wizard bonus=0. Definitions уникальны по ID, каждая используется хотя бы одним actor; extra/unused definitions отвергаются. Полное definition/source_rule_id сохраняется, не выбирается по имени из каталога. Definition order отдельно хранится в command и echo. Два разных ID могут иметь равные numeric возможности.

Начальные значения однозначно выводятся из fresh-only контракта ADR-0037: здоровые CharacterInjuryState у Wizard/ProfileInjuryState(0,1) у Minions без Conditions, текущая resilience=definition, доступен sole Minion attack, wields_weapon=True только у Minions, shields=False. Первый normal round с side_order players_and_allies→opposition, нулевые spatial usages, WizardMagicState(), пустые daily receipts/histories/expiries/pending, initial minion_attack=None. Champion/daily owner создаётся для нового roster/round и wizard.day_id. Attack multiplier=1, ignores_armour=False, secondary_effects=(), profile pool_cap=None. Иные values/history/current owner не выражаются v1, а не молча стираются encoder.

Activation_order — independent permutation всех actors. Objective перечисляет всех opposing perspective actors ровно один раз, в своём порядке. Policies должны соответствовать ordered roster; target priorities Minion включают всех hostile actors, в том числе Wizard. Defeat decisions — отдельная ordered tuple для non-Wizard targets, полный attacker/target/disposition/GM approval сохраняется. У Wizard пустые targets/decisions, attack_id=null, casting_policy='cast_when_ready', zone_priorities — permutation всех graph Zones; Willpower равен caster casting_profile. У Minions casting_policy=null/zone_priorities=[], attack_id — sole attack. Repeated stagger choice — suffer_wound.

Spell обязан в точности равняться canonical Curse: rule_id RULE-MAGIC-001:curse-of-cowardly-flight, lore_id lore:battle-magic, casting_value3, target_kind zone, range long, duration instant. Foreign canonical-looking partial spell или другое заклинание не допускаются. Полный spell передаётся явно; spellbook/каталог не подставляет отсутствующие поля.

Facts — все20явных booleans NpcMagicScenarioFacts: authored_wizard_profile, targets_aware, clear_line_of_sight, all_combatants_included, unmounted_combatants_only, no_additional_rules, no_other_test_modifiers, no_cover_or_concealment, no_terrain_or_obstacles, no_external_scene_changes, no_external_condition_sources, ammunition_sufficient, requires_reload_action, knows_battle_magic, spell_memorised, no_bulky_items, no_casting_opposition, no_mixing_winds, no_potency_modifiers, no_effect_immunities. Только requires_reload_action=false, остальные true. Это caller assertions; ни wire, ни no_additional_rules не разрешают стирать известные Abilities из книжного NPC.

## Scene frames и routes без потерь

| Объект | Полные поля |
| --- | --- |
| scene_frame | key, pair_ranges, zone_ranges, give_ground_plans, broken_plans, attack_departures |
| key | placements:[placement,...] — **полный ordered архив**, live_actor_ids:[ID,...] — roster subsequence, может быть пустой |
| pair_range | first_actor_id, second_actor_id, target_range:close/short/medium/long/extreme, first_range_approved_by_gm:bool, second_range_approved_by_gm:bool |
| zone_range | zone_id, target_range:short/medium/long/extreme |
| route | path_entity_ids:[ID,...], crosses_obstacle:bool, crosses_difficult_terrain:bool |
| give_ground_plan | actor_id, can_leave_zone:bool, destination_zone_id:ID/null, route:route/null, impossible_confirmed:bool |
| broken_plan | actor_id, kind:safe_recover/free_move_recover/free_move_run, free_move_zone_ids:[ID,...], free_move_route:route/null, run_destination_zone_id:ID/null, run_route:route/null, fastest_route_confirmed:true |
| attack_departure | actor_id, can_leave_zone:bool |

Exact initial scene key обязателен; future coverage опциональна, missing scene остаётся unsupported во время боя. Все supplied frames проходят existing admission, включая unreachable/empty-live. Full placements сохраняют исходный **placement order**, все actors/архивы и side IDs; live IDs — roster subsequence. Pair ranges содержат каждую live hostile неупорядоченную пару один раз, без self/unknown/same-side/reverse duplicates; orientation/order и directed True/False approvals сохраняются. Zone ranges покрывают весь graph в graph order и согласованы с Wizard placement. Одна Zone не назначает Close; graph проверяет совместимость уже supplied Range, не создаёт его.

Give Ground plans — exact roster order живых Curse targets, пустые если Wizard не live. Plan с destination требует can_leave_zone=True/typed route/impossible=False; без destination route=null/impossible=True, но can_leave_zone остаётся независимым explicit flag. Route не пересекает obstacles/terrain/self/archived/enemy; friendly path IDs сохраняются в порядке источника. Broken plans и ordinary attack_departures — distinct live actor subsets; empty arrays допустимы и могут привести к missing-route stop, а не скрытому default. Safe Recover требует безопасную Zone, пустые free path/null routes; moving branches сохраняют supplied speed/path/fastest/destination constraints. Не добавлять маршрут/Recover по догадке.

Порядки definitions/roster/placements/activation/policies/targets/decisions/objective/graph/connections/frames/keys/pairs/plans/routes сохраняются независимо. Encoder обязан reconstruct-check exact admitted source; неподдержанное значение не упрощается и не теряется. JSON round-trip не доказывает истинность facts/GM approval или достаточность future coverage.

## Simulation envelope и native summary

Request: schema_version, kind, request_id, ruleset, simulation:{master_seed,trials,round_budget}, execution, scenario.

Result: schema_version, kind, request:<полный нормализованный вход>, seed_scheme='towr:npc-magic-trial:v1', runtime:{package_version,python_implementation,python_version,rng:'random.Random'}, summary.

Summary: trials, outcome_counts:{objective_achieved,perspective_defeated,round_limit_reached,unsupported_path}, total_action_count, total_started_round_count, total_completed_round_count. Сумма counts=trials; все N/положительные/нулевые counters и source arithmetic проверяет existing NpcMagicSimulationSummary. **Никаких side_defeated/visited_rounds/attack_count aliases**, native fields не переинтерпретируются. Derived means/float rates в simulation v1 не добавляются; compact trial records, individual seeds/journals/unsupported diagnostics не выходят на wire.

Service выбирает existing runner по exact options/default indexed RNG, проверяет полный result/source и summary/source. Pure encoder принимает command+existing summary, сверяет полное NpcMagicSimulationRequest value и lossless scenario; RNG/runner/pool не вызывает. Echoed execution закономерно различается между backend; summary равна при том же source/seed/runtime. Runtime не является гарантией межверсионной воспроизводимости и не содержит timestamps/hashes/custom-RNG claims.

## Balance envelope и полный staged output

Request: schema_version, kind, request_id, ruleset, reserve:{round_budget,scenario}, generation, evaluation, execution.

Generation: groups:[{group_id,actor_ids,minimum_count,maximum_count},...], facts, scene_frames, candidate_id_prefix, max_candidates. Evaluation: master_seed, stages:[{trials_per_candidate,keep},...], max_total_trials, window:{minimum,target,maximum}.

Факты и полные frame snapshots передаются **отдельно** от reserve. Family frames требуют exact ordered equality, включая keys/архивы/orientation/routes/flags. Все fixed perspective actors и Wizard сохраняются, groups partition только opposing Minions без Wizard. Prefix bounds/полные definitions/C/all-zero exclusion и полный повторный staged budget проверяются existing request до materialization. Parser не запускает generator/simulation/RNG/pool и не проверяет все subsets.

Успешный preflight не обещает допустимость каждого subset. Collision unequal projected frames, invalid Broken route или потеря начальной цели на materialization — generation_failed/exit3, не invalid_input/exit2. Нельзя уменьшить C/budget, исправить route или пропустить vector. Counts/IDs/projections/frame collapse сохраняют ADR-0042; у Magic round нет отдельного ID.

Result: schema_version, kind, request:<нормализованный полный вход>, seed_scheme, runtime, candidate_count, planned_trials, total_trials, candidates:[{candidate_id,counts},...], stage_reports, status, selected_candidate_ids.

Stage report: stage_index, trials_per_candidate, keep, total_trials, candidates:[row,...], selected_candidate_ids, continuation_candidate_ids. Row: candidate_id, summary:<native summary>, rates:{objective_achieved,perspective_defeated,round_limit_reached,unsupported_path}, status:eligible/unsupported_observations, window_match:bool/null. Все rates — reduced Fraction objects, исходный знаменатель — все N, включая unsupported. Wire key round_limit_reached отображает Python round_limit_rate; side_defeated не вводится.

Каталог охватывает все generated vectors; counts берутся из source ordered enumeration, не разбираются из candidate ID. Полные исполненные reports сохраняют outside/unsupported rows; intermediate continuation допускает outside-window и возвращает original order, исключает unsupported. В **последнем запрошенном** stage continuation_candidate_ids=[]; ранний empty continuation даёт no_eligible_candidates, полная цепочка completed даже при all-unsupported/empty selection. Final selection только из последнего bounded report; ранние попадания не возвращаются. Actual<=planned<=cap; total_trials включает повторную работу, stages не объединяются в независимую выборку.

Encoder принимает command+MagicBalanceResult(generation_result,evaluation_result), проверяет exact command→generation source→staged request/report chain и full scenarios. Reconstructing pure model guards допустимы, generation service/RNG/runner/pool при encoding не вызываются. Output не содержит trial records/execution journals/RNG/options вне echoed request.

## Python API и изоляция слоёв

Все новые command/result модели frozen/slotted, tuple/list с tuple copy и strict family types. Definition order — explicit tuple всех used definition IDs, без duplicates/unused/missing; command хранит его отдельно от domain roster. Request ID в command обязателен отдельно от scenario ID и проверяется без trim.

| Модуль | Планируемый контракт |
| --- | --- |
| application/magic_simulation_models.py | MagicSimulationCommand(request_id,request,execution,definition_order) |
| adapters/_magic_scenario_json.py | Общий узкий scenario mapper/inverse; separate round_budget/path prefix, без fake envelope |
| adapters/magic_json_errors.py | MagicInputError, MagicSimulationInputError, MagicBalanceInputError; shared code enum/class paths прежних families не меняются |
| adapters/magic_json_schema.py | Локальный registry/validation simulation+balance, без network refs |
| adapters/magic_simulation_json.py | parse_magic_simulation_request; encode_magic_simulation_result(command,summary); encode_magic_simulation_error |
| application/magic_simulation_service.py | execute_magic_simulation(command) → existing NpcMagicSimulationSummary |
| application/magic_simulation_errors.py | MagicSimulationExecutionError(request_id), Python cause/notes сохраняются |
| application/magic_balance_models.py | MagicBalanceCommand(request_id,generation_request,execution,definition_order), MagicBalanceResult(generation_result,evaluation_result) с exact staged source |
| adapters/magic_balance_json.py | parse_magic_balance_request; encode_magic_balance_result; encode_magic_balance_error |
| application/magic_balance_service.py | execute_magic_balance(command) → MagicBalanceResult |
| application/magic_balance_errors.py | MagicBalanceGenerationError(request_id,candidate_id,counts), MagicBalanceExecutionError(request_id,stage_index,candidate_id) |

Shared strict reader/execution options/window и package-data glob reuse допустимы без generic codec/rules framework. Расширение type error factory в _json_common при implementation не меняет прежние сигнатуры/семантику и проверяется регрессией. Application не зависит от adapters/JSON/CLI; внутренняя domain не знает external request ID/definition order.

## Ошибки и CLI

Error envelope: schema_version, kind, request_id:string/null, error:{code,path:string/null,message}. У magic_balance_error внутри error дополнительно обязательные nullable candidate_id, counts:[int>=0,...]/null, stage_index:int>=0/null.

Input codes: invalid_json/unsupported_version/invalid_input; path — JSON pointer или null, request_id извлекается только из valid nonblank string, unknown context=null. MagicSimulationInputError не смешивается с balance/прежними families. Runtime code simulation_failed; balance generation_failed/evaluation_failed с внешним request ID, известными candidate/counts либо stage/candidate. Runtime error.path: null для simulation_failed, /generation для generation_failed, /evaluation для evaluation_failed. Counts известны только в generation phase; stage_index только в evaluation phase; остальные slots=null. Phase классифицируется активным service path, не чужим exception class. Python cause/worker notes сохраняются в exception chain, в JSON — generic message без raw cause/notes/import paths. Encoder failures не маскируются execution error; BaseException проходит напрямую.

CLI exit0 — полный результат, включая unsupported/round_limit и no_eligible/empty selection; exit2 — input/usage, exit3 — simulation/generation/evaluation error, exit4 — I/O. UTF-8 file/stdin/stdout/stderr/write/flush/closed streams следуют existing CLI boundary. Stdout — один JSON object+newline либо typed error; при ошибке чтения/usage stdout пуст. После output failure нет повторной записи error JSON в тот же поток; shutdown не заменяет exit4 на120. Spawn main guard сохраняется. Новые handlers не меняют dispatch/errors старых шести команд.

## Источники и finite evidence

BOOK-PLAYER-GUIDE1.4: Equipment / Ranged Weapons, стр.94; Rules / Combat, стр.112; The Battlefield / Range / Speed, стр.114–115; Giving Ground, стр.119; Conditions / Broken, стр.122; Magic in the Old World / Casting a Spell / Interrupted Casting, стр.156; Spell Potency / Miscasts, стр.157; Battle Magic / Curse, стр.162; Wounds Table, стр.190–191. BOOK-GM-GUIDE1.1: Allies and Antagonists / Minions / Champions, стр.91–92. Книжные rules/house rules не добавляются; имена commands/wire fields/версии — архитектурный контракт. Unsupported mandatory consumers/pending и distinction Minion/Champion сохраняются.

[Finite JSON examples](../examples/m8/json/README.md) и [mapping probe](../examples/m8/json_contract_probe.py) вручную отображают два конкретных request в existing public typed APIs и обратно, сравнивают полные sequential/process results и native outputs. Simulation4trials; balance C4/stages2/4 keep2/1 upper16. Fixtures сохраняют external/scenario/day IDs и независимые arrays. Негативные constructor cases и subsequent generation failure после успешного C/budget preflight не превращают probe в wire parser/Schema validator. Strict lexing/unknown fields/version проверяют отдельные production simulation tests первого среза; simulation error encoder реализован вторым срезом, balance pure wire — третьим; balance execution/error encoder реализован четвёртым срезом.

## Порядок и обязательная матрица реализации

| Срез | Проверяемый результат |
| --- | --- |
| 1. Simulation pure wire | Три simulation Schema, command с independent request ID/definition order, shared scenario mapper, pure parser/summary encoder/input errors. Strict lexical/unknown/required/nullable/version/uint64/type tests; обе стороны Wizard/perspective, all field/array/enum mappings, canonical fresh/spell/facts/frames/routes/archives/empty fields, round-trip/lossless refusal, exact source/foreign same-ID guard, no RNG/runner/pool |
| 2. Simulation execution/CLI | Service/execution error/error encoder/simulate-magic; exact dispatch/options/result+summary source, all native outcomes как success, raw cause/notes не выходят в JSON; file/stdin/Unicode/usage/read/write/flush/closed streams, real spawn/installed module+console, регрессия прежних commands |
| 3. Balance pure wire | Три balance Schema, command/result, parser/result encoder с общим mapper; separate family facts/exact frames, groups без Wizard/обе perspective, all stages/C/caps, Fraction normalization, source/result chain/каталог без ID parsing, early/final/unsupported semantics, no generation execution при parsing/encoding |
| 4. Balance execution/CLI | Service/application errors/error encoder/balance-magic; input vs later generation failure, candidate/counts/stage contexts/cause/notes, late trial failure/no partial/retry, native unsupported/empty selection как success, I/O/real spawn/installed module+console |
| 5. Общий аудит | Шесть packaged magic Schema/local refs, полная field/guard matrix, оба новых command paths/installed parity и прежние шесть команд, public examples/probe и source/cleanup/runtime/precision boundaries |

Simulation pure wire (срез1) реализован: три packaged Schema, frozen command, общий scenario mapper, strict parser, pure summary encoder и input errors. Simulation execution/service/error encoder/CLI (срез2) также реализованы. Balance pure wire (срез3) также реализован. Balance execution/service/error encoder/CLI (срез4) также реализованы. Общий аудит5 также завершён; матрица и ограничения — в отчёте. Новые боевые consumers, выбор заклинаний/тактики/GM facts, prefix reuse и общий rules framework не входят.

## Реализованный первый срез

[MagicSimulationCommand](../../src/towr/application/magic_simulation_models.py) сохраняет independent request ID/explicit definition order и прежний execution class. [Shared scenario mapper](../../src/towr/adapters/_magic_scenario_json.py) отображает полные свежие owners, полные profiles/spell/facts/policies/frames/routes/архивы без изменения domain. [Parser/summary encoder](../../src/towr/adapters/magic_simulation_json.py) используют [локальный registry](../../src/towr/adapters/magic_json_schema.py), три simulation Schema и [Magic input errors](../../src/towr/adapters/magic_json_errors.py). `_json_common` расширен только import/type union нового error family; прежняя лексика и class paths сохранены.

Parser выполняет strict shape/type/version admission, затем существующие public constructors; generator/RNG/runner/pool не запускает. Encoder принимает `encode_magic_simulation_result(command, summary)`, сравнивает полный typed source и reconstruct-check полного command, сохраняет native четыре counts/три totals без records/means/aliases. Independent arrays, nullable routes, archived/empty-live frames, обе Wizard sides/perspectives и native outcomes проверяются [unit](../../tests/unit/test_m8_magic_json.py) и [real-backend integration tests](../../tests/integration/test_m8_magic_json.py). Первый срез не включал execution/error encoder/service/CLI; они реализованы следующим срезом ниже. Balance остаётся отдельным следующим слоем; игровой scope не расширен.

## Реализованный второй срез

[execute_magic_simulation](../../src/towr/application/magic_simulation_service.py) выбирает existing sequential/process runner по exact execution options, не передаёт custom RNG и проверяет полный typed result/source до summary и полный summary/source после неё. Возвращается только native aggregate. [MagicSimulationExecutionError](../../src/towr/application/magic_simulation_errors.py) содержит independent external command.request_id и сохраняет original cause/notes; wrong-root TypeError и BaseException проходят напрямую, retry/fallback отсутствуют.

[Error encoder](../../src/towr/adapters/magic_simulation_json.py) принимает только Magic simulation input/execution family, runtime code `simulation_failed`/path=null, generic message без cause/notes. [CLI](../../src/towr/cli.py) добавляет `simulate-magic INPUT` с прежним byte I/O и exit0/2/3/4. Все четыре native outcomes — полный success/exit0; source/error/result encoding завершается до stdout. Ошибки encoder не маскируются, output failure не запускает повторный error write. Шесть прежних routes/errors не меняются; балансная magic-команда ещё отсутствует.

[Service tests](../../tests/unit/test_m8_magic_simulation_service.py), [unit CLI/error tests](../../tests/unit/test_m8_magic_cli.py) и [subprocess integration](../../tests/integration/test_m8_magic_cli.py) проверяют full-source foreign same-ID, dispatch/late failure/cause/notes, native outcomes, все I/O/error boundaries, real spawn и совместимость прежних команд. Installed module/console проверяются отдельно на свежем offline wheel; gameplay/source constraints прежние.

## Реализованный третий срез

[MagicBalanceCommand/MagicBalanceResult](../../src/towr/application/magic_balance_models.py) связывают independent external request ID/definition order с полным generation request и exact generation→staged source chain. [Pure adapters](../../src/towr/adapters/magic_balance_json.py) используют готовый shared scenario mapper напрямую с reserve round_budget/path prefix, без fake simulation envelope. Отдельные family facts/frames передаются существующему preflight; полное ordered равенство frames проверяется явно с /generation/scene_frames pointer. Parser не materialize subsets и не исполняет генератор/runner/RNG/pool.

Три balance Schema расширяют [local registry](../../src/towr/adapters/magic_json_schema.py); simulation validator сохраняет прежнюю сигнатуру и собственный набор refs. Result encoder делает полный source/lossless reconstruct-check, выводит весь catalog из source count enumeration без parsing ID и все достигнутые reports. Native summary/rates не переименовываются в mixed aliases; wire round_limit_reached соответствует Python round_limit_rate, Fraction сокращаются. Continuation/final selection и early/final statuses берутся из готовых typed models; successful preflight по-прежнему не обещает допустимость каждого subset.

[Unit tests](../../tests/unit/test_m8_magic_balance_json.py) и [real-backend integration](../../tests/integration/test_m8_magic_balance_json.py) проверяют lexical/schema/type/source/order/frame/budget/normalization boundaries, all-zero exclusion/fixed Wizard, both perspectives, native outcomes/early/final/unsupported и purity. Balance service/application errors/error encoder/CLI в этот срез не входят; gameplay scope и нижние слои сохраняются.

## Реализованный четвёртый срез

[execute_magic_balance](../../src/towr/application/magic_balance_service.py) выполняет две отдельные фазы: existing generator с exact command.generation_request и staged evaluator с exact generated evaluation_request/прежними execution options. Полный typed generation/source проверяется до evaluator, полный staged result/source — до MagicBalanceResult. Unknown context не придумывается. [Application errors](../../src/towr/application/magic_balance_errors.py) сохраняют independent external request ID/candidate/counts либо stage/candidate, full original cause/notes; классификация следует активной phase. Wrong-root TypeError и BaseException проходят напрямую, retry/fallback/partial result отсутствуют.

[Error encoder](../../src/towr/adapters/magic_balance_json.py) принимает только Magic balance input/generation/evaluation family; runtime messages константные, generation_failed/path=/generation/stage=null и evaluation_failed/path=/evaluation/counts=null. Неизвестный context=null. CLI [balance-magic](../../src/towr/cli.py) использует прежний UTF-8 byte I/O и exit0/2/3/4: native unsupported/no_eligible/empty selection — success, invalid input —2, failure после admitted preflight —3. Result/error encoding заканчивается до stdout; encoder exceptions/BaseException не переклассифицируются, output failure не делает повторный error write.

[Service tests](../../tests/unit/test_m8_magic_balance_service.py), [unit CLI/error tests](../../tests/unit/test_m8_magic_balance_cli.py) и [subprocess integration](../../tests/integration/test_m8_magic_balance_cli.py) проверяют exact source/phase/late failures/GM facts, real sequential/spawn, все8command families и прежние7routes/I/O. Новые gameplay consumers, seed scheme/RNG/options/framework не вводятся. Общий аудит обеих magic wire families завершён пятым срезом ниже.

## Общий аудит

[Readiness matrix](../audits/m8-external-readiness.md) сопоставляет все поля, modules/Schema и138implementation tests (113unit/25integration), отдельно contract probe. Блокеров нет; production/tests/tools/Python examples/fixtures не менялись. Текущий src/wheel/installed site равны по440Python/Schema files, полный suite того же byte-state —3424tests/33прежнихerrors; это не зелёный suite. Дополнительно проверены installed public probe, все6Schema/local refs и dependency consistency; успешные CLI/regression calls не повторялись. Fresh-only/unsupported/full-source/phase/error/precision/runtime границы сохранены. Дальнейший gameplay consumer требует отдельного ограниченного контракта, а не расширения этого wire v1 по умолчанию.
