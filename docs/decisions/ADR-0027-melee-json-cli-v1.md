# ADR-0027: Melee JSON v1 и отдельные CLI-команды

Статус: принято, 2026-09-29. **Melee simulation v1 реализован: Schema/command, parser/summary/error encoder, service и simulate-melee. Balance Schema/models, parser/result/error encoder, service и balance-melee также реализованы. [Общий installed end-to-end аудит](../audits/m6-external-readiness.md) завершён; контракт закрыт в текущей границе numeric Minions.** Направление выбрано пользователем после [аудита генерации](../audits/m6-generation-readiness.md). Основа — ADR-0021/0022/0023/0024/0025/0026; технические образцы — [ADR-0016](ADR-0016-ranged-simulation-json-v1.md) и [ADR-0020](ADR-0020-ranged-balance-json-v1.md).

## Решение и совместимость

Добавляются команды `python -m towr simulate-melee INPUT` и `python -m towr balance-melee INPUT`, а также те же subcommands установленного `towr`. INPUT — UTF-8 файл относительно cwd либо `-` для stdin. Прежние `simulate`/`balance` остаются ranged с прежними входами, результатами, error envelopes и exit codes. Нет определения режима боя по полям JSON, fallback в ranged, переключателя kind через flags или переопределения seed/backend/window. Выбранная команда определяет parser/service/encoder даже для malformed JSON без kind.

Оба новых пути принимают только существующий неподвижный numeric Melee Minion-сценарий. Simulation выдаёт **только aggregate summary**, без compact trial records; это отдельный формат, а не изменение ranged simulation v1. Balance выдаёт каталог составов и полные aggregate reports этапов. Сценарий, source guards, seeds, RNG и метрика прежние. CLI не вычисляет Close, awareness, характеристики или решения GM.

## Документы и строгий JSON

Шесть Draft 2020-12 Schema: `melee-{simulation|balance}-{request|result|error}-v1.schema.json`, `$id=urn:towr:melee-{simulation|balance}:{request|result|error}:1`. Schema входят в package data, registry разрешает только bundled refs; сетевой загрузки нет. `schema_version="1"`, `ruleset="towr-pg1.4-gmg1.1"`; версии двух семейств независимы.

| Семейство | Request kind | Result kind | Error kind |
| --- | --- | --- | --- |
| Simulation | npc_melee_simulation | npc_melee_simulation_result | melee_simulation_error |
| Balance | npc_melee_balance | npc_melee_balance_result | melee_balance_error |

Все описанные поля обязательны, неизвестные/пропущенные поля на любом уровне запрещены. Nullable поля присутствуют явно. Порядок object keys несущественен, arrays сохраняется. ID/source ID — непустая не-whitespace строка без trim/normalization. Duplicate object keys, неверный UTF-8, NaN/Infinity и lone surrogates — invalid_json. Reader принимает только str/bytes, иной аргумент — TypeError. Вход должен быть одним JSON object. BOM не принимается, как в нынешнем strict reader.

Числовые входные поля — exact integer tokens, без bool/string/float/exponent coercion; `1.0`/`1e0` дают invalid_input. Schema integer сам по себе эту lexical границу не доказывает. Master seed — каноническая десятичная строка `0` либо `[1-9][0-9]*`, значение 0..2**64−1; hex/знак/ведущие нули/whitespace запрещены. Counts/budgets остаются JSON integers, включая значения выше 2**53−1: клиент обязан сохранять точность. Means на выходе — конечные JSON numbers, точные суммы и trials также сохранены. `Fraction` кодируется `{numerator: int>=0, denominator: int>=1}`; вход может быть несокращённым, выход сокращён, 0→0/1. Окно проходит `0<=minimum<=target<=maximum<=1`.

Unknown строковая schema_version → unsupported_version до domain/RNG/pool; missing/нестроковая версия, неверный kind/ruleset → invalid_input. У malformed/lexically invalid входа request_id может быть null: reader не обязан восстанавливать поля после ошибки чтения.

## Общий Melee scenario

Scenario имеет ровно `definitions`, `actors`, `battlefield`, `side_order`, `actor_order`, `perspective_side`, `objective_target_ids`, `facts`, `repeated_stagger_choice`, `actor_policies`.

| Поле | Семантика |
| --- | --- |
| definitions | Непустой ordered массив уникальных definitions; каждый используется минимум одним actor |
| actors | Минимум два actor, обе стороны непусты; каждый `{id,definition_id,side,zone_id}`. IDs уникальны, ссылка на definition/Zone существует |
| battlefield | `{zone_ids:[ID,...],connections:[{first_zone_id,second_zone_id},...]}`; graph ненаправленный, без self/duplicate/unknown edges; пустые Zones допустимы |
| side_order | Только `["players_and_allies","opposition"]` — ordinary Melee admission, без ambush |
| actor_order | Каждый actor ID ровно один раз; preference внутри side |
| perspective_side | players_and_allies либо opposition; это не превращает Minions в PC |
| objective_target_ids | Все и только противоположные actors, без повторов; порядок сохраняется |
| repeated_stagger_choice | Только suffer_wound |
| actor_policies | Ровно одна policy на actor; порядок policies сохраняется |

Definition содержит ровно `id`, `source_rule_id`, `resilience:{toughness,bonus}`, `attack`, `protection`. Toughness/damage/bonus — int>=0; dice>=1, threshold 1..10. Attack: `{id,source_rule_id,dice,threshold,damage,hands}`, hands=`1h|2h`. Protection: `{source_rule_id,skill,dice,threshold}`, skill=`athletics|defence`. У Footpad явно athletics; Defence не выводится из оружия или максимума Skills. Для других явно supplied допустимых numeric profiles Defence разрешён существующим admission.

Семантика kind фиксирует TargetInjuryPolicy.MINION, wound_limit=1; одну Skill.MELEE Attack с range_min=range_max=CLOSE, обычный Damage multiplier=1, без cap override/ignore armour/secondary effects; одну Protection указанного Skill. Actor начинает здоровым, без Conditions/defeat, с единственной available Attack, definition Resilience, wields_weapon=True, holds_shield=False. Round 1 свежий, без histories/pending/weapons/usage. Это начальный сценарий, не сохранённый бой с автоматическим лечением. Поля Wounds, traits, Abilities, shields, extra attacks или Range не принимаются и не теряются молча.

`facts` содержит **11 обязательных полей**: `zone_id`; `all_opponents_in_close_range`, `targets_aware`, `clear_line_of_sight`, `stationary`, `all_zone_combatants_included`, `unmounted_combatants_only`, `no_higher_ground`, `no_additional_rules`, `no_other_test_modifiers` — только true; `can_leave_zone` — явный boolean. Все placements находятся в facts.zone_id. True can_leave_zone требует соседней Zone; наличие соседней Zone не устанавливает True автоматически.

Policy: `{actor_id,outnumbering_bonus_approved,targets:[{target_id,disposition,gm_approved},...]}`. Outnumbering flag — явный True **или False**. Targets — все враги ровно один раз в приоритете; один массив разворачивается в target IDs и полные MinionDefeatDecision. Disposition=`killed|knocked_out|disarmed_and_surrendered`, gm_approved только true. Actor/definition/Zone IDs имеют разные пространства имён.

Adapter строит roster/combat participants/placements в порядке actors, graph в исходном порядке, остальные порядки из отдельных arrays. Definition order хранится command отдельно. Все public constructors вызываются, повторные/unused definitions отклоняются до исполнения. Schema не проверяет связи, составы или истинность фактов: семантика остаётся в typed admission, ответственность за facts/профили/GM approvals — у caller.

Encoder обязан проверять **lossless command → wire → command**. Low-level source с независимым порядком combat participants/placements, который не выразим единым actors array, отклоняется, а не упорядочивается молча. Не поддержанные wire поля definition/state также нельзя терять. ID — метка, не hash или доказательство происхождения.

## Simulation request/result

Request содержит ровно `schema_version`, `kind`, `request_id`, `ruleset`, `simulation`, `execution`, `scenario`. `simulation={master_seed,trials,round_budget}`; trials int 1..2**64−1, round_budget int>=1. Request_id становится initial.current.id. Execution: ровно `{mode:"sequential"}` либо `{mode:"process",workers:int 1..61,batch_size:int>=1}`. RNG/callables/import paths/pickle не передаются; штатный service создаёт random.Random для каждого trial через существующий simulator.

Result содержит ровно `schema_version`, `kind`, `request` (полный нормализованный вход), `seed_scheme="towr:npc-melee-trial:v1"`, `runtime`, `summary`. Runtime: `{package_version,python_implementation,python_version,rng:"random.Random"}`. Summary: `trials`, `outcome_counts:{objective_achieved,side_defeated,round_limit,unsupported_path}`, `total_attack_count`, `total_visited_round_count`, `mean_attack_count`, `mean_visited_round_count`. Counts/sums — неотрицательные integers; сумма исходов=trials, source/budget/aggregate guards прежние. Нет rates, winner, trial records, seeds отдельных trials или combat journal. Доли можно точно получить из counts/trials.

Service исполняет весь existing NpcMeleeSimulationResult, затем вызывает existing summarize_npc_melee_simulation и возвращает NpcMeleeSimulationSummary; отсутствие records в wire **не означает streaming или bounded-memory simulator**. Encoder требует summary.source_request==command.request и lossless input. Pure summary guards не доказывают происхождение наблюдений; custom RNG summaries нельзя выдавать за штатный JSON путь. Runtime описывает encoder/runtime, не hash кода. Timing/timestamp/report UUID отсутствуют. При сравнении sequential/process echoed execution отличается, summary совпадает.

## Balance request/result

Request содержит ровно `schema_version`, `kind`, `request_id`, `ruleset`, `reserve`, `generation`, `evaluation`, `execution`.

- Reserve: `{initial_request_id,round_budget,scenario}`; это полный свежий admitted Melee reserve. Внешний request_id и reserve ID независимы. Нет вложенного simulation request с фиктивными trials.
- Generation: `{groups,facts,candidate_id_prefix,max_candidates}`. Groups: ordered `{group_id,actor_ids,minimum_count,maximum_count}` по ADR-0026; полное разбиение всех и только противников, exact definitions внутри групп, prefix subsets, bounds exact int. Family facts обязательны отдельно даже при совпадении с reserve facts; та же Zone и допустимый escape path. Фиксированы policies/GM flags для всего семейства.
- Evaluation: `{master_seed,stages,max_total_trials,window}`. Stages — ordered непустой массив `{trials_per_candidate,keep}`, строго возрастающие uint64 positive trials, keep>=1. Window — minimum/target/maximum Fraction. Caps positive exact int. C и полный `sum(U[i]*trials[i])` проверяются до materialization; U[0]=C, U[i+1]=min(U[i],keep[i]); полностью нулевой count vector запрещён. Повторные пакеты оплачиваются целиком, no prefix reuse.
- Execution — та же форма, что у simulation. Candidate ID=`prefix:counts:`+decimal vector, initial ID=`candidate_id:initial`; не глобальные ID. No dedup identical profiles.

Result имеет ровно `schema_version`, `kind`, `request`, `seed_scheme`, `runtime`, `candidate_count`, `planned_trials`, `total_trials`, `candidates`, `stage_reports`, `status`, `selected_candidate_ids`.

Candidates — полный ordered каталог `{candidate_id,counts:[int>=0,...]}` всех C, включая не дошедшие до финала. Counts берутся из исходных диапазонов в порядке генерации, не парсятся из candidate ID. Scenario восстанавливается по echoed reserve/family input. Stage report: `{stage_index,trials_per_candidate,keep,total_trials,candidates,selected_candidate_ids,continuation_candidate_ids}`; оценки — все исполненные кандидаты в исходном порядке.

Оценка: `{candidate_id,summary,rates,status,window_match}`. Summary той же формы, что simulation summary. Rates — четыре outcome-имени, значения сокращённые Fraction; знаменатель исходной доли — все trials, включая unsupported. Status=`eligible|unsupported_observations`; window_match boolean либо null только для unsupported. Source assessment восстанавливается из request/catalog/stage trials, новые независимые source поля не принимаются.

Local selected — ranked top_k внутри окна; continuation — пригодные кандидаты, включая outside-window, в исходном порядке. На последнем заданном этапе continuation всегда `[]`. При исчерпании пригодных до последнего этапа status=no_eligible_candidates и final selected=[]; если все этапы выполнены, status=completed даже при пустом final selection или all-unsupported. Это exit 0, а не execution failure. Final selected только из последнего этапа, ранние counts не суммируются. Нет confidence/preset/nearest fallback.

Encoder требует generation_result.source_request==command.generation_request, exact evaluation source==generated evaluation_request, полную staged цепочку и lossless command. Ошибка/неполный отчёт не кодируется успешным префиксом. Успешный wire/result не содержит trial records, но retains reserve/catalog/scenarios/stage aggregates; caps не гарантируют RAM/время.

## Typed boundary и reuse

| Файл / публичный контракт | Назначение |
| --- | --- |
| application/melee_simulation_models.py: MeleeSimulationCommand(request,execution,definition_order) | Frozen/slotted NpcMeleeSimulationRequest + существующие SimulationExecutionOptions + полный уникальный used definition order |
| adapters/melee_simulation_json.py: parse_melee_simulation_request, encode_melee_simulation_result, encode_melee_simulation_error | str/bytes → command; command+summary → JSON str+LF; typed error → отдельный envelope |
| application/melee_simulation_service.py: execute_melee_simulation(command) | Existing sequential/process runner → summary; только штатный RNG |
| application/melee_balance_models.py: MeleeBalanceCommand(request_id,generation_request,execution,definition_order), MeleeBalanceResult(generation_result,evaluation_result) | Frozen/slotted, tuple copies/replace/type/source guards как ADR-0026/0025; вход не хранит candidates/dict |
| adapters/melee_balance_json.py: parse_melee_balance_request, encode_melee_balance_result, encode_melee_balance_error | Pure admitted input/complete exact output/error JSON |
| application/melee_balance_service.py: execute_melee_balance(command) | Existing generate_melee_candidates → evaluate_melee_candidates_staged с exact options → boundary result |
| adapters/melee_json_schema.py: validate_melee_document(document,kind), validate_melee_balance_document(document,kind) | Только shape; kind=request/result/error; bundled registry не выдаётся для мутации |

Оба command отклоняют ranged typed requests. SimulationExecutionOptions/Mode и ObjectiveRateWindow **не переносятся и не дублируются**: исторические ranged import/pickle paths сохраняются. Scenario mapping — один внутренний `_melee_scenario_json.py`: data+initial ID+round budget+path prefix → scenario/definition_order; обратное отображение без envelope/trials/RNG. Simulation и reserve balance используют его напрямую, без fake JSON round-trip через ranged.

Melee Schema может ссылаться на неизменённые bundled ranged fragments для ID/seed/execution/общей числовой формы, но **не** на ranged scenario/facts целиком. Balance ссылается на Melee simulation scenario/facts. Новые registry разрешают все используемые bases локально. Старые ranged Schema/$id не менять ради reuse.

Общую strict lexical реализацию допустимо вынести в внутренний `_json_common.py` с параметром error factory; `_ranged_json_common.py` сохраняет совместимые internal reexports, ranged regression обязательна. Не создавать второй strict reader с расходящейся семантикой. Исторический RangedInputErrorCode допускается переиспользовать напрямую как общий enum (без переноса класса); MeleeInputError/MeleeSimulationInputError/MeleeBalanceInputError — отдельные классы, не subclasses ranged errors. Helper typing ограничен union двух типов input errors только для error factory; новая универсальная hierarchy/dispatcher не требуется.

## Errors и CLI

MeleeSimulationInputError / MeleeBalanceInputError содержат code/path/request_id. Envelope: `{schema_version:"1",kind:<error kind>,request_id:ID|null,error:{...}}`. Simulation error имеет ровно `code,path,message`; balance добавляет обязательные nullable `candidate_id,counts,stage_index`. Message — человеческое нестабильное описание; path — JSON Pointer или null, с escape `~0`/`~1` и prefix `/scenario` либо `/reserve/scenario`. Unknown semantic context указывает ближайший известный объект, не выдуманное поле.

| Code | Фаза / контекст | Exit |
| --- | --- | --- |
| invalid_json | UTF-8/JSON/duplicate/nonfinite/surrogate; path обычно null, balance context null | 2 |
| unsupported_version | path=/schema_version, balance context null | 2 |
| invalid_input | Schema/lexical floats/admission/groups/family/window/C/budget; known pointer, balance context null | 2 |
| generation_failed | Только balance materialization после preflight; candidate/counts при известном контексте; stage/path=null | 3 |
| execution_failed | Simulation runner/summary либо balance staged/result; balance stage/candidate при известном контексте, counts/path=null | 3 |

Application errors: MeleeSimulationExecutionError(request_id), MeleeBalanceGenerationError(request_id,candidate_id|null,counts|null), MeleeBalanceExecutionError(request_id,stage_index|null,candidate_id|null). Внешний request_id — из command, никогда reserve ID. Service сохраняет low-level cause/notes через raise from. Любой другой Exception внутри соответствующей фазы получает фазовую категорию с неизвестными полями null; неверный аргумент service — TypeError, BaseException проходит наружу. JSON execution/generation message общий, без traceback/raw cause. Input message может объяснять поле. Encoder принимает только свои typed boundary errors; не кодирует неизвестный Exception как invalid_input. Ошибки самого encoder не маскируются execution failure.

Stdout — один полный UTF-8 JSON+LF после execution/encoding. Stderr — краткая строка typed failure. Exit 0=result/help (включая empty selection/round_limit/unsupported); 2=input/usage (usage только stderr); 3=generation/execution; 4=read/write/flush/diagnostic IO. При read failure stdout пуст; при write failure нет второй попытки JSON, shutdown flush не меняет exit 4 на 120. Частично доставленные bytes pipe при ошибке получатель отбрасывает. Нет streaming/output-file/retry/fallback/автовыбора backend. Protected main сохраняет spawn. Существующие ranged команды не принимают Melee kind и наоборот.

## Конечные примеры и реализация

[Примеры и probe](../examples/m6/json/README.md) фиксируют exact mapping к existing typed Melee fixtures, прогон обоих backend и семантические отказы. Это проверка контрактного отображения, **не production reader/Schema/encoder/CLI**. Лексические, unknown-field и wire error checks остаются в матрице реализации; probe не объявляет произвольный JSON допустимым.

| Срез | Обязательные проверки |
| --- | --- |
| Schema/package/strict | Шесть schemas/local refs; module/wheel вне cwd/PYTHONPATH; UTF-8/duplicates/surrogates/nonfinite, float/exponent/bool, uint64 seed/counters, wrong family/version/ruleset, unknown/missing nested fields; old ranged fixtures/ошибки без изменений |
| Scenario/commands | Полные references/unused definitions, fresh state/lossless orders, ordinary side order, facts/Zone/Close/escape path, explicit True/False flags, attacks hands/protection skill, public admission, frozen/tuple/replace/ranged отказ |
| Balance input/result | Внешний/reserve ID, family facts отдельно, partition/full definitions/bounds/C/budget до RNG; Fraction normalization; source/catalog/counts/full chain/local vs continuation/final, all-unsupported/early stop/empty selection, no records |
| Simulation output | Exact summary source, четыре counts/sums/means, no trial records, lossless echo/runtime; неисполнение runner/RNG encoder-ом |
| Services/errors | Exact options/standard RNG; low-level и unknown failures по фазам, candidate/counts/stage/context/null, cause/notes/interrupts, нет partial/retry/fallback; encoder errors отдельно |
| CLI | Все четыре команды, module/console/file/stdin/Unicode, real spawn, installed wheel, exit 0/2/3/4/help/usage, closed streams/read/write/flush, сохранение прежних ranged bytes/семантики |

Первый законченный implementation-срез — **Melee simulation**: три Schema, frozen MeleeSimulationCommand и pure scenario/parser/summary encoder с deterministic tests; lexical reuse только с ranged regression. Без service/error encoder/CLI. Второй — simulation service/errors/error encoder и simulate-melee. Третий — balance Schema/command/result/parser/result encoder; четвёртый — balance service/error encoder/CLI. Затем общий installed end-to-end аудит. Расширение боевых правил и prefix reuse не входят ни в один срез.

Непосредственно сверены BOOK-PLAYER-GUIDE 1.4, Rules / Attack Tests / Attack Modifiers, стр. 118–119; BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91 и Understanding NPC Profiles, стр. 93. Serialization сохраняет typed numeric profiles и GM decisions, не интерпретирует новые правила. Source labels/facts не доказываются Schema, новых Rule IDs/house rules нет.

## Проверка контрактного среза

2026-09-29, Windows/Python 3.14.5: finite mapping probe дал полное равенство с existing typed fixtures, simulation sequential/process 8 trials и balance sequential/process planned/actual 18; всего 52 trials. Семь семантических отказов public constructors, неизменность input и JSON round-trip проекций проверены. Сохранены два request/two result examples; production Schema/parser/encoder не использовались. Existing ranged JSON/CLI и Melee generation regression: **108 tests OK (78,161 с)**; compileall, 1392 локальных Markdown-путей и git diff --check успешны. Полная регрессия не повторялась (последняя 2164 OK). Production src/tests/tools не менялись, дерево на старте чистое, commit/push не выполнялись.

## Реализация первого среза

2026-09-29: [command](../../src/towr/application/melee_simulation_models.py), [parser/summary encoder](../../src/towr/adapters/melee_simulation_json.py), [scenario mapper](../../src/towr/adapters/_melee_scenario_json.py), [input errors](../../src/towr/adapters/melee_json_errors.py) и [локальная Schema validation](../../src/towr/adapters/melee_json_schema.py) реализованы. Три bundled simulation Schema входят в существующий package-data glob; request использует неизменённые ranged fragments simulation/execution, но имеет собственные Melee scenario/facts. Lexical implementation вынесена в `_json_common.py`, прежний модуль сохраняет reexports; historical options/enum/window paths и ranged formats не менялись.

[23 unit tests](../../tests/unit/test_m6_melee_json.py) проверяют все уровни required/unknown fields, strict tokens/UTF-8/версии, uint64 и большие точные counts, fresh admission/references/facts/GM flags, numeric profiles, immutable command, lossless orders и exact summary source. [Два integration tests](../../tests/integration/test_m6_melee_json.py) соединяют parser с existing runner/summary/encoder и сравнивают полный sequential/process result. Сохранённый result fixture проверяет форму и кодирование уже заданной summary, без ожидания конкретного Monte Carlo процента. Runtime metadata остаётся описательным. Schema errors готовы как форма; error encoder и application execution boundary входят во второй срез. Установленный wheel будет отдельно проверен при подключении CLI и общем аудите.

Проверка implementation-среза: Windows/Python 3.14.5, 2189 tests OK (155,055 с), включая ranged regression. После локального ужесточения regex JSON Pointer в новой error Schema — повторные 25 tests OK (2,136 с); исходные ranged Schema не менялись. Compileall, 1402 локальных Markdown-пути и diff --check успешны. Существовавшие изменения docs/fixtures сохранены; commit/push не выполнялись. Следующий срез — simulation service/errors/error encoder и simulate-melee.

## Реализация второго среза

2026-09-29: [execute_melee_simulation](../../src/towr/application/melee_simulation_service.py) выбирает existing backend с exact options и штатным RNG, проверяет полный result/source и возвращает existing summary. Проверяются также type/source проекции summary. [MeleeSimulationExecutionError](../../src/towr/application/melee_simulation_errors.py) сохраняет request ID и cause/notes; BaseException проходит, wrong command даёт TypeError до запуска. Error encoder принимает только Melee typed failures, output execution message общий. В [CLI](../../src/towr/cli.py) добавлен отдельный simulate-melee; parse/service/error family выбирается по команде, без распознавания kind и fallback. Shared I/O boundary дополнительно обрабатывает ValueError закрытого Python-потока как exit 4; прежние ranged formats не менялись.

[Service tests](../../tests/unit/test_m6_melee_service.py), [error JSON tests](../../tests/unit/test_m6_melee_error_json.py), [CLI unit](../../tests/unit/test_m6_melee_cli.py) и [CLI integration](../../tests/integration/test_m6_melee_cli.py) добавляют 36 проверок: exact dispatch/source/summary, сохранение причины, failure после завершённого trial без частичной сводки, generic errors и разные families, отдельные encoder errors, UTF-8/file/stdin/real spawn, read/write/flush/closed streams и exit 0/2/3/4. Все 36 прошли. Wheel собран офлайн из локального кэша setuptools 84.0.0; установлены wheel и runtime dependencies в чистый временный venv вне репозитория. Все 330 Python/Schema файлов совпали с src после нормализации line endings. Module/console × sequential/process дали равные aggregates; прежние ranged simulate/balance и новые input errors проверены через обе точки входа. Новые правила/метрики и balance wire не добавлены.

Следующий срез — balance Schema/models/pure parser/result encoder по этому ADR; balance service/error encoder/CLI следует после него. Общий installed end-to-end аудит обеих Melee-команд остаётся последним срезом.

Полная регрессия второго среза: **2225 tests OK (188,355 с)**, новые 36 отдельно OK (29,920 с). Compileall, 1414 локальных Markdown-путей, installed pip check и diff --check успешны. Проверено на Windows/Python 3.14.5; другие ОС/Python 3.12 и performance не проверялись. Предшествующие изменения сохранены, commit/push не выполнялись.

## Реализация третьего среза

2026-09-29: [MeleeBalanceCommand/Result](../../src/towr/application/melee_balance_models.py), [parser/result encoder](../../src/towr/adapters/melee_balance_json.py), MeleeBalanceInputError и три bundled balance Schema реализованы. [Validator](../../src/towr/adapters/melee_json_schema.py) разрешает refs на Melee scenario/facts/summary/error pointer и immutable ranged seed/execution локально. Simulation helper сохраняет прежнюю сигнатуру/семейство; ranged Schema, CLI и domain/engine не менялись. Reserve проходит существующий `_melee_scenario_json` напрямую, без фиктивного simulation envelope. Внешний request_id остаётся независимой меткой, source guards связывают результат с exact generation/evaluation inputs.

[32 unit tests](../../tests/unit/test_m6_melee_balance_json.py) покрывают strict lexical и все вложенные required/unknown fields, Schema result/error, context pointers, used definitions, frozen/slotted/tuple/replace, explicit family Zone/escape/facts и True/False GM approval, hands/Protection Skill, exact uint64 и budgets выше 2**64, Fraction normalization, каталог count vectors без разбора ID, lossless orders и всю stage/source chain. Encoder не исполняет генератор/RNG/pool, parser не материализует кандидатов. Saved result fixture проверяет сериализацию уже заданных aggregates; статистические проценты нового прогона не фиксируются.

[Два integration tests](../../tests/integration/test_m6_melee_balance_json.py) соединяют parser → existing generator → existing staged evaluator → typed result → encoder; полные sequential/process reports и JSON совпадают после исключения echoed backend. Проверены fixture (пять составов, полный budget 18) и вариант с разными definitions/порядками. 34 новых tests OK. Schema error задаёт только форму: balance application errors/service/error encoder/CLI остаются четвёртым срезом. Общий installed аудит обеих Melee-команд следует после него.

Непосредственно сверены PG1.4, Rules / Attack Tests / Attack Modifiers, стр. 118–119; GM1.1, Allies and Antagonists / Minions, стр. 91; Understanding NPC Profiles, стр. 93. Wire сохраняет supplied facts/profiles/GM decisions; ни новых игровых правил, ни автоматической осведомлённости/Close/approval, ни нового окна сложности нет.

Проверка третьего среза: **34 новых tests OK (19,973 с)**, полная регрессия **2259 tests OK (199,197 с)** на Windows/Python 3.14.5. Compileall, 1427 локальных Markdown-путей, diff --check и whitespace новых файлов успешны. Новый installed wheel/Python 3.12/другие ОС и performance не проверялись. На старте дерево чистое; commit/push не выполнялись. Следующий срез — balance service/application errors/error encoder и balance-melee.

## Реализация четвёртого среза

2026-09-29: [balance service](../../src/towr/application/melee_balance_service.py), [application errors](../../src/towr/application/melee_balance_errors.py), [error encoder](../../src/towr/adapters/melee_balance_json.py) и [CLI balance-melee](../../src/towr/cli.py) реализованы. Service проверяет generated type/source до этапной оценки и возвращает полный typed result с exact evaluation source. Ошибки классифицируются по текущей фазе; известные generation candidate/counts либо evaluation stage/candidate сохраняются, неизвестный контекст null. Внешний request ID берётся только из command. Cause/notes доступны в Python, JSON messages общие; counts копируются в tuple. Wrong command отвергается до dispatch, BaseException проходит, repeats/fallback/partial results отсутствуют.

Добавлены [16 unit tests service/errors](../../tests/unit/test_m6_melee_balance_service.py), [12 CLI unit tests](../../tests/unit/test_m6_melee_balance_cli.py), [2 service integration tests](../../tests/integration/test_m6_melee_balance_service.py) и [9 CLI integration tests](../../tests/integration/test_m6_melee_balance_cli.py). Проверяются exact source/options, обе фазы и цепочки причин, wrong-family errors, raw/mutated diagnostics, поздняя ошибка trial без частичного отчёта, terminal/unsupported/пустой выбор как success, read/write/flush/closed streams, encoder failures отдельно, command-specific dispatch, UTF-8/file/stdin/help/usage и real spawn. 39 новых tests OK (46,255 с).

Игровые правила, admission, seed/RNG, staged budget/selection и метрика прежние. Ranged Schema/команды и Melee simulation format не менялись. Новый общий scheduler или battle aggregate не вводится. Следующий срез — единый installed end-to-end аудит ADR-0027 для обеих Melee-команд, с матрицей требований/проверок и явными ограничениями.

Проверка четвёртого среза: **2298 tests OK (251,752 с)** на Windows/Python 3.14.5; новые 39 отдельно OK (46,255 с). Wheel собран офлайн, установлен в чистый venv вне repo/PYTHONPATH: 337 Python/Schema файлов равны src, обе Melee-команды равны между module/console × sequential/process (balance planned=actual=18), обе ranged-команды и четыре error families сохранены. Все шесть Melee Schema/local refs, installed pip check, compileall, 1440 локальных Markdown-путей и diff --check успешны. Python 3.12/другие ОС и performance не проверялись. Предшествующие изменения сохранены; commit/push не выполнялись. Общий readiness audit ADR-0027 ещё предстоит.

## Завершающий аудит

2026-09-29: [матрица внешней границы](../audits/m6-external-readiness.md) сопоставляет все четыре среза с кодом, Schema, tests и установленными entrypoints. 241 targeted/regression tests OK (178,641 с), включая 134 tests ADR-0027; обе Melee-команды, обе ranged-команды и standalone examples проверены вне repo/PYTHONPATH. Все 337 Python/Schema файлов установленного wheel равны src. Новых механик или house rules нет; src/tests этим аудитом не менялись. Исторические проверки выше описывают состояние соответствующих срезов. План ADR-0027 завершён, дальнейшее направление выбирается отдельно.
