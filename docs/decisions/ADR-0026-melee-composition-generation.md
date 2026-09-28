# ADR-0026: ограниченная генерация Melee-составов

Статус: принято, 2026-09-29. **Group/request preflight, construction/result/error, materialization и integration реализованы и проверены. Самостоятельный production-пример и аудит завершены в заявленной границе.** Основа — [ADR-0021](ADR-0021-melee-minion-scenario.md), [ADR-0024](ADR-0024-melee-candidate-assessment.md), [ADR-0025](ADR-0025-staged-melee-evaluation.md) и [аудит staged evaluation](../audits/m6-staged-evaluation-readiness.md). Технический образец — [ADR-0019](ADR-0019-ranged-composition-generation.md), но ranged типы и wire не переиспользуются вместо Melee.

## Источники и область поиска

Непосредственно перечитаны локальные извлечённые страницы:

| Источник | Ограничение |
| --- | --- |
| BOOK-PLAYER-GUIDE 1.4, Rules / The Battlefield / Range, стр. 114 | Одна Zone не доказывает Close, LOS или awareness |
| Та же книга, Rules / Attack Modifiers, стр. 118–119 | Outnumbering учитывает всех допустимых бойцов Zone; обычный бонус +1d, GM вправе удержать неуместный бонус; пример 7:6 не становится автоматическим порогом |
| BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91 | Wound означает defeat; disposition/GM approval не создаются генератором |
| Та же книга, Understanding NPC Profiles, стр. 93 | Numeric Attack/Protection и свойства сохраняются; PC weapon effects не выводятся из имени оружия |
| Та же книга, Brigands & Footpads, стр. 97 | Footpad применим к aware battle fixture; Lurker действует вне боя. Brigand имеет Craven Opportunist +2d и не становится обычным Melee Minion удалением Ability из numeric excerpt |

Генерируется конечное семейство **начальных** составов с разной численностью противоположной стороны. Perspective-сторона, profiles, тактика, размещение, round budget, окно и stages фиксированы. Это техническая область поиска, не правило сложности книги. Новых Rule IDs/house rules нет. Сохраняется admission неподвижных numeric Minions; PC, движение/Charge/Brawn, mixed battle и новые Abilities вне среза.

## Резерв, факты и решения GM

Caller передаёт уже допущенный `NpcMeleeScenario` с полным ordered резервом потенциальных участников. Все участники `perspective_side` включаются во все кандидаты. Весь противоположный резерв разбивается на непересекающиеся группы. Для количества n берутся первые n actor IDs группы, без перебора перестановок/всех сочетаний, клонирования, чтения каталога или создания новых actor IDs. Резерв может быть больше выбранных maximum_count.

Не выбранные из резерва actors **отсутствуют в данном исходном бою**, а не остаются в Zone как скрытые, defeated или ожидающие вступления. Изменение состава не является игровым действием удаления участника. Поэтому `all_zone_combatants_included` должно быть истинным для каждого отдельного состава, а не утверждением, что все потенциальные резервисты одновременно присутствуют в каждом бою.

Обязательные `facts: NpcMeleeScenarioFacts` caller передаёт **отдельно для всего семейства**, без default из template.facts. Их zone_id должен совпадать с template.facts.zone_id: генератор не перемещает сохранённые placements. Это дополнительный Melee preflight guard. Остальные assertions сохраняют смысл ADR-0021: каждый состав имеет explicit Close всех вражеских пар, awareness/LOS/stationary, полный состав Zone без mounts/higher ground/дополнительных правил или иных modifiers. Если family facts требуют can_leave_zone=True, у общей Zone должна быть adjacent Zone; проверяется до перебора. False не выводится автоматически из геометрии. Факты не доказываются успешным admission полного резерва; если caller не может подтвердить общий контекст, такое семейство не поддерживается.

Передача template задаёт неизменные priorities и полные `MinionDefeatDecision` для каждой сохранённой пары attacker/target, а также **тот же `outnumbering_bonus_approved` каждого actor во всех составах и их достижимых состояниях**. Значение False сохраняется так же, как True. Генератор не создаёт approval и не выбирает GM policy по count vector. Для зависящего от численности решения GM нужны отдельные явно подготовленные сценарии/семейства, а не новая эвристика здесь.

Генератор не вычисляет и не записывает численный бонус. Existing engine продолжает считать outnumbering перед каждой Attack из текущих всех допустимых бойцов Zone, с исключением defeated/Defenceless/non-combatants и учётом заданного GM approval. Уменьшение начального состава и последующий defeat могут изменить бонус без изменения policy/profile. `no_additional_rules=True` не является разрешением игнорировать известную Ability; источник обязан действительно удовлетворять admission ADR-0021.

## API

Генерация находится в application: она собирает domain snapshots для симулятора; pure balance продолжает получать готовые inputs/aggregates. Новые файлы: `application/melee_candidate_generation_models.py`, `melee_candidate_generation.py`, `melee_candidate_generation_errors.py`.

| Тип / операция | Контракт |
| --- | --- |
| MeleeCompositionGroup(group_id, actor_ids, minimum_count, maximum_count) | Ordered непустой резерв actors с одинаковым полным NpcDefinition; включённые bounds |
| MeleeCandidateGenerationRequest(template_scenario, groups, facts, candidate_id_prefix, max_candidates, master_seed, stages, max_total_trials, window) | Typed NpcMeleeScenario/NpcMeleeScenarioFacts, tuple MeleeCompositionGroup, tuple MeleeBalanceStage, прежний ObjectiveRateWindow; derived candidate_count/planned_trials |
| MeleeCandidateGenerationResult(source_request, evaluation_request) | Полный generation source и точный MeleeStagedEvaluationRequest; candidates доступны через evaluation_request |
| generate_melee_candidates(request) | Чистая materialization/admission всего семейства, без runner/RNG/pool/IO |
| MeleeCandidateGenerationError(candidate_id: str, counts: tuple[int, ...]) | RuntimeError конкретной проекции с исходным __cause__/notes |

Модели frozen/slotted, коллекции копируются в tuple, replace повторяет guards. Ranged groups/requests/scenarios/facts/stages/results отклоняются по типу. Общий ObjectiveRateWindow остаётся тем же классом с прежним import/pickle path. После генерации caller явно передаёт `result.evaluation_request` в `evaluate_melee_candidates_staged` с existing SimulationExecutionOptions. Объединённая команда и Melee CLI/JSON не добавляются.

## Preflight до materialization

Проверить typed template/facts/window, непустые ordered groups/stages. Group ID/candidate prefix/actor IDs — непустые строки без нормализации; group IDs уникальны, actor IDs без повторов внутри/между группами. Объединение groups должно **ровно** совпадать со всеми actors противоположной template.perspective_side: unknown/friendly/omitted actors запрещены. Все члены одной группы имеют равный полный NpcDefinition, включая ID, attack/protection/resilience/injury policy; числового сходства недостаточно. Разные группы с равными definitions допустимы и не сливаются.

Bounds — exact int `0 <= minimum_count <= maximum_count <= len(actor_ids)`, без bool/coercion. Max_candidates/max_total_trials — positive exact int. Ошибочные значения/пустые или повторные IDs дают ValueError, неверные typed objects — TypeError; plain constructor errors не получают candidate ID.

Переиспользовать внутренние `_validate_stages` / `_planned_trials` из **Melee** staged models без изменения формулы/public API. Все stages проверяются, включая потенциально недостижимые. Seed допускается через один `NpcMeleeSimulationRequest(template, master_seed, stages[0].trials_per_candidate)`, без фиктивных C copies и построения всех simulation requests. Проверить согласованность family zone/can_leave_zone, описанную выше.

До декартова перебора вычислить exact int `C = product(maximum_count - minimum_count + 1) - int(all(minimum_count == 0))`. Полностью нулевой вектор исключается: пустая противоположная сторона не является автоматической победой этого сценария. При C=0 или C>max_candidates отказ всему request; нет случайной выборки, truncation или первых max_candidates.

При U[0]=C, U[i+1]=min(U[i],stage[i].keep) верхний бюджет равен sum(U[i]×stage[i].trials_per_candidate). Превышение max_total_trials отклоняется **до создания кандидатов**, даже если ранний unsupported мог бы снизить фактические затраты. Полные пакеты, включая повторные seeds, оплачиваются целиком по ADR-0025. Caps не являются квотой памяти входного резерва или гарантией времени исполнения.

## Порядок и точная проекция

Перебрать bounds по возрастанию, лексикографически в порядке groups; последняя координата меняется быстрее. Исключить только полностью нулевой вектор, не удалять составы с одинаковыми profiles/observations. Порядок кандидатов является tie-break evaluator; group order может изменить результат при точном равенстве.

ID = `candidate_id_prefix + ':counts:' + ','.join(decimal counts)` без ведущих нулей; initial.current.id = `candidate_id + ':initial'`. Имена групп в ID не кодируются, координаты привязаны к source.groups. ID уникален внутри request, не является глобальным hash источника: другой template/groups с тем же prefix/vector требует проверки полного source. Seed scheme остаётся `towr:npc-melee-trial:v1`.

Для каждого count vector:

1. Сохранить всех perspective actors и первые n actors каждой группы. Roster фильтровать в исходном порядке, используя прежние immutable participant snapshots/definitions/states без изменения чисел/оборудования.
2. Заново согласовать свежие NpcRosterAttackState, combat participants и actor_order, сохранив каждый исходный порядок, ordinary side_order и round 1. Нет histories/pending/weapons/использованных moves, как требует исходный admission.
3. Фильтровать spatial placements в исходном порядке, сохранив zone_id/side_id и весь ZoneGraph, включая пустые Zones. Не создавать движения или размещения.
4. Фильтровать actor policies по сохранённым actors; target_actor_ids и соответствующие **полные** defeat decisions — по retained enemies в прежнем приоритете. Сохранить outnumbering_bonus_approved без пересчёта. Порядки roster/ходов/targets не заменяются порядком groups.
5. Objective фильтровать в прежнем порядке до retained enemies; шаблон уже требует всех и только противников. Сохранить repeated Staggered choice, perspective_side и max_rounds; facts взять из отдельного family input.
6. Построить новый NpcMeleeScenario через existing constructor и прежний MeleeBalanceCandidate. Не обходить admission ссылкой на уже проверенный template.

Ошибка materialization/admission любого состава останавливает генерацию с MeleeCandidateGenerationError(candidate_id, counts) через `raise ... from error`; inputs неизменны, partial result/retry/skip нет. KeyboardInterrupt/SystemExit не оборачиваются. Ошибки сборки итогового staged request или result вне конкретной проекции проходят напрямую без вымышленного candidate ID. Генерация ничего не симулирует.

## Result и проверка происхождения

Evaluation request обязан содержать все C кандидатов в точном порядке, общие master_seed/stages/max_total_trials/window из generation source. Result constructor сравнивает ID и **полное значение scenario** с ожидаемой проекцией каждого count vector: не только количество участников. Подмена profile/state/policy/GM flag/decision/placement/facts/objective/round ID, пропуск/повтор/перестановка запрещены. Для проверки проекции строятся по одной, без второй сохранённой полной копии семейства. Равные копии source допустимы.

Одна внутренняя projection function используется pure construction и result guards; local import из constructor допустим для разрыва models/construction import cycle по образцу M5. Result не содержит outcomes/assessments/records/RNG/execution options. Caller сохраняет generation result для трассировки к резерву; existing staged report хранит сценарии, но не заменяет этот источник. Guards не доказывают истинность facts/GM approval или книжное происхождение произвольного numeric definition.

## Конечные примеры

Perspective P1,P2 фиксированы; другая сторона — полный резерв A=(E2,E1), bounds 0..2 и B=(E3), bounds 0..1. Все Footpad definitions равны; разные группы допустимы. Исходный actor_order P1,P2,E1,E2,E3, приоритет P1 к врагам E3,E2,E1. У P2 outnumbering_bonus_approved=False, у остальных True — явно заданные решения для всего семейства, не автоматический выбор.

| Counts | Retained enemies в actor_order | ID при prefix=family |
| --- | --- | --- |
| (0,1) | E3 | family:counts:0,1 |
| (1,0) | E2 | family:counts:1,0 |
| (1,1) | E2,E3 | family:counts:1,1 |
| (2,0) | E1,E2 | family:counts:2,0 |
| (2,1) | E1,E2,E3 | family:counts:2,1 |

У (1,1) приоритет P1 = (E3,E2), не actor_order и не group order. При (2,0) резерв A выбирает E2,E1, но actor_order сохраняет E1,E2. GM flags/defeat decisions/definitions/graph неизменны; для полного вектора всё равно новый initial ID и явные family facts.

При stages=(10,keep=2),(100,keep=1): C=3×2−1=5, planned=5×10+2×100=250. max_candidates=4 и budget=249 отклоняются до перебора, 5/250 допускаются. При A.minimum=1 C=4, planned=240; при обоих bounds 0..0 отказ C=0. Fixed positive vector даёт один кандидат даже при большем резерве. Range за пределами резерва, повтор/пропуск/friendly actor, mixed definitions, ranged facts, другая family Zone либо требование выхода при отсутствии adjacent Zone — ошибки preflight.

[generation_contract_probe.py](../examples/m6/generation_contract_probe.py) вручную задаёт этот конечный резерв и пять векторов, строит public Melee snapshots и staged input, проверяет порядки/flags/facts/graph/источники и отказы existing constructors. Это не production generator, не его полная validation/error система, не наблюдение вероятностей; runner/RNG отсутствуют. Арифметические assertions caps не заменяют отдельные production tests request guards.

## Матрица реализации

| Срез | Обязательные проверки |
| --- | --- |
| Group/request | Typed Melee/отказ ranged, exact IDs/tuple copy/frozen/replace, bounds/partition/definitions, explicit facts/zone/escape path, seed/stages/window/caps, C и полный budget до iterator/projection/RNG, 5/250 против 4/249, все нули/fixed bounds |
| Construction | Пять ordered vectors/IDs без dedup; обе perspective-side; независимые порядки groups/roster/ходов/targets; snapshots/definitions/graph/facts и полные decisions/True+False GM flags; повторное admission/no runner/RNG/pool/IO; ошибка второго состава/cause/notes/interrupts без partial |
| Result | Exact common staged input и полная projection каждого count vector; равная копия, foreign/type/order/missing/duplicate, подмена policies/GM flag/facts/позиции/profile/цели/initial ID, no records/outcomes и immutable source |
| Integration | Семейство → existing staged service, реальные sequential/process reports равны; повтор генерации и rename prefix сохраняют observations при тех же rules/runtime; динамический outnumbering при разных составах и после defeat не подменён static bonus; никаких точных Monte Carlo процентов |

Первый законченный срез — MeleeCompositionGroup и MeleeCandidateGenerationRequest с полным preflight/derived C/planned_trials и deterministic tests, без перебора/materialization. Второй — result, pure construction/error и source/admission guards. Третий — integration/audit/самостоятельный пример генерация → staged evaluation. Existing M5 tests служат техническим ориентиром, не заменяют Melee checks.

Ranged APIs, existing Melee engine/simulation/staged evaluator, books и метрика не меняются. Не добавлять общий scheduler/rules engine, генерацию beyond reserve, новые профили/тактику/размещение/GM approvals, preset/confidence policy, prefix reuse или Melee CLI/JSON.

## Реализованный первый срез

2026-09-29: [MeleeCompositionGroup/MeleeCandidateGenerationRequest](../../src/towr/application/melee_candidate_generation_models.py) реализованы. Exact typed Melee inputs, неизменяемые tuple snapshots, IDs/bounds/partition/full definitions, отдельные family facts/Zone/escape path, seed/stages/window и derived C/planned_trials/caps проверяются при construction/replace. Значения GM flags и полные policies остаются в исходном template; Close/awareness/approval не выводятся. Для seed используется один existing simulation request, формула staged budget переиспользуется из Melee models. Перебора, materialization, runner/RNG/pool/IO нет.

[13 deterministic tests](../../tests/unit/test_m6_melee_candidate_generation_models.py) проверяют 5/250 и отказы 4/249, positive/fixed/all-zero bounds, ID/type/ranged/seed/stages/partition/definitions, обе perspective-side, False/True GM flags и полные source policies, family Zone/escape path, tuple copies/frozen/slots/replace. Сценарий из 40 отдельных резервных групп проверяет C=2**40−1 и бюджет C+2 арифметически; одна seed admission, без создания кандидатов и исполнения. Следующий законченный срез — pure count vectors/projection, MeleeCandidateGenerationResult и MeleeCandidateGenerationError, включая точный source/result guards и отказ без partial при ошибке проекции.

Полная регрессия после первого среза: **2145 tests OK (142,433 с)**, Windows/Python 3.14.5; compileall, 1300 локальных Markdown-путей и git diff --check успешны. Commit/push не выполнялись.

## Реализованный второй срез

2026-09-29: [generate_melee_candidates](../../src/towr/application/melee_candidate_generation.py), [MeleeCandidateGenerationResult](../../src/towr/application/melee_candidate_generation_models.py) и [MeleeCandidateGenerationError](../../src/towr/application/melee_candidate_generation_errors.py) реализованы. Лексикографические prefix-count vectors без нулевого состава/dedup дают новый public-admitted scenario на каждый кандидат. Original snapshots, independent roster/combat/actor/placement/target orders, весь graph, полные defeat decisions, True/False outnumbering flags и separate family facts сохраняются; initial IDs задаются детерминированно. Melee сохраняет обычный side_order, как требует ADR-0021.

Result проверяет полный ordered staged input и exact projection от reserve source, включая policies/facts/позицию/ID; равные копии допускаются. Повторная проекция для проверки строится по одной; в result нет records/observations/RNG/options. Ошибка materialization/admission конкретного состава сохраняет candidate/counts/cause/notes и останавливает весь вызов; BaseException проходит напрямую. Финальные staged/result constructor errors не получают вымышленный candidate ID.

[14 tests](../../tests/unit/test_m6_melee_candidate_generation.py) проверяют пять составов, оба направления perspective, prefixes/независимые порядки/full snapshots/GM flags/family facts, полный budget, caps до перебора, typed/ranged отказ, exact source/result подмены, frozen/equal-copy/no records, отсутствие runner/RNG/pool, ошибку второго состава и interrupts/final constructor boundaries. Вместе с 13 request tests — 27. Следующий шаг — integration с реальными sequential/process staged reports, повтор/rename prefix и динамический outnumbering до/после defeat, затем самостоятельный production-пример и аудит. Новых игровых rules/CLI/JSON нет.

Полная регрессия после второго среза: **2159 tests OK (137,836 с)**, Windows/Python 3.14.5; compileall, 1314 локальных Markdown-путей и git diff --check успешны. Integration нового generator с staged API остаётся отдельным следующим срезом.

## Сквозная integration

2026-09-29: [5 integration tests](../../tests/integration/test_m6_melee_candidate_generation.py) проверяют production generator вместе с существующими staged/engine APIs; production src не менялись. Семейство из пяти составов, stages=(2,keep=2),(4,keep=1), window=[0,1/2,1], полный бюджет 5×2+2×4=18. Полные sequential/process reports и selected IDs равны (real spawn, workers=2,batch_size=3), повтор генерации/исполнения даёт тот же отчёт, вход/global RNG не меняются, дочерние процессы завершены. Смена prefix меняет candidate/initial IDs, но сохраняет seeds, полные assessments после нормализации source ID, outcomes/attack/round totals и выбранные составы; точные Monte Carlo проценты не фиксируются.

На generated scenarios public runner с SequenceRandom подтверждает ordinary outnumbering: разные начальные составы 2×1/2×2/2×3 используют только своих участников, при defeat врага в 2×2 бонус появляется на следующей Attack, при потере союзника в 2×1 бонус исчезает в следующем раунде. Все случаи проверены с True и False GM flags, точной trace (+1d один раз), размером пула/расходом RNG, явными defeat decisions и неизменностью generation source. Книжное основание: PG1.4 Rules / Attack Tests / Attack Modifiers, стр. 118–119; GM1.1 Allies and Antagonists / Minions, стр. 91.

Всего generation tests — 32 (13 preflight + 14 construction/result/error + 5 integration). Следующий законченный срез — самостоятельный production-пример генерация → staged evaluation и аудит полной матрицы ADR-0026. Этот тестовый срез не является benchmark и не закрывает внешнюю Melee CLI/JSON границу.

Полная регрессия после integration: **2164 tests OK (140,874 с)**, Windows/Python 3.14.5; compileall, 1320 локальных Markdown-путей и git diff --check успешны. Production src не менялись; это проверка корректности, не performance-замер.

## Аудит и продолжение

[Аудит готовности](../audits/m6-generation-readiness.md) завершён 2026-09-29: контракт сопоставлен с 32 tests и public APIs, книги перечитаны напрямую. [Самостоятельный пример](../examples/m6/melee_balance.py) / [вывод](../examples/m6/melee_balance.output.txt) проверяют пять составов, full budget 104 на backend, равные sequential/process reports и пустой итоговый выбор при выходе уточнённых оценок за окно. Это допустимое наблюдение, не preset/гарантия. Input/global RNG/cleanup и обработка ошибок проверены, source/memory/performance ограничения записаны.

Пользователь выбрал JSON/CLI для Melee. Следующий законченный шаг — ADR-0027 отдельной внешней границы simulation/balance с сохранением existing typed APIs и ranged v1. В этом аудите production src/tests/tools не менялись; реализация wire/CLI впереди.

Полная регрессия аудита: **2164 tests OK (148,644 с)**, Windows/Python 3.14.5; compileall, 1360 локальных Markdown-путей и git diff --check успешны.
