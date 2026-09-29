# ADR-0033: ограниченная генерация mixed-составов

Статус: принято, 2026-09-29. **Контракт/probe, production group/request, construction/result/error, integration, самостоятельный пример и аудит завершены в заявленной границе.** Основа — [ADR-0028](ADR-0028-mixed-minion-scenario.md), [ADR-0031](ADR-0031-mixed-candidate-assessment.md), [ADR-0032](ADR-0032-staged-mixed-evaluation.md) и [аудит staged evaluation](../audits/m7-staged-evaluation-readiness.md). Технический образец — [ADR-0026](ADR-0026-melee-composition-generation.md); отдельные mixed типы сохраняют admission и явные пары дистанций.

## Источники и граница

Непосредственно перечитаны локальные извлечённые страницы:

| Книга, глава, страница | Применение |
| --- | --- |
| BOOK-PLAYER-GUIDE 1.4, Equipment / Ranged Weapons, стр. 94 | Любой враг в Close запрещает использование ranged weapon без Close Optimum; Warbow имеет Medium–Long Optimum |
| Та же книга, Rules / The Battlefield / Range, стр. 114 | Одна Zone не доказывает Close; расстояния задаются явно, Short не превращается в Close |
| Та же книга, Rules / Attack Tests / Attack Modifiers, стр. 118–119 | Outnumbering учитывает допустимых бойцов текущей Zone; GM вправе удержать бонус; 7:6 не автоматический порог |
| BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91 | Wound означает defeat; disposition требует решения атакующего с усмотрением GM |
| Та же книга, Understanding NPC Profiles, стр. 93 | Сохраняются полные numeric Attack/Protection и свойства профиля |
| Та же книга, Brigands & Footpads, стр. 97 | В примере Footpad Dagger и Brigand Warbow; Craven Opportunist меняет Melee-бонус Brigand, поэтому ветка Axe не добавляется. Footpad Lurker относится к Awareness вне боя |

Генерация — техническая область поиска начальных сценариев, не книжное правило сложности. Новых Rule IDs/house rules нет. Остаются все ограничения ADR-0028: неподвижные здоровые Minions, Close Melee и Medium Shooting, явные факты и решения GM. PC, движение, смена оружия, новые Abilities, awareness и mixed JSON/CLI вне среза. Потеря доступной цели в ходе уже начавшегося боя по-прежнему даёт existing unsupported_path; генератор не придумывает ожидание/перемещение.

## Резерв и применимость ко всему семейству

Caller передаёт допущенный `NpcMixedScenario` с полным ordered резервом. Все actors `perspective_side` фиксированы. Весь противоположный резерв разбивается на непересекающиеся группы; для количества n берутся первые n actor IDs группы. Нет клонирования, каталога, новых actors, перестановок или перебора всех сочетаний. Максимум группы может быть меньше размера резерва. В одной группе допускается только **одинаковое полное значение NpcDefinition**; сравнения имени/ID/Skill недостаточно. Отдельные группы могут иметь равные definitions. Разные Melee/Shooting profiles требуют разных групп.

Не выбранные actors отсутствуют в начальном бою данного кандидата. Они не скрыты, не defeated и не ждут вступления. Поэтому `all_zone_combatants_included` утверждается для каждого отдельного состава, а не для всех потенциальных резервистов одновременно.

Обязательные `facts: NpcMixedScenarioFacts` caller задаёт **отдельно для всего семейства**, без default из template. Все existing assertions ADR-0028 сохраняются, включая awareness/LOS, stationary, полноту состава Zone, отсутствие дополнительных правил/modifiers, достаточность боеприпасов и отсутствие Reload action. Допуск полного резерва не доказывает эти assertions для каждого поднабора.

Отдельный обязательный `pair_ranges: tuple[NpcMixedPairRange, ...]` утверждает применимость исходных дистанций к каждому составу. Preflight требует **полного равенства ordered tuple с template.pair_ranges**, включая ориентацию endpoints и порядок; равные копии допустимы. Это намеренная техническая граница первого генератора: он меняет численность, сохраняя геометрию и source identity дистанций. Новые дистанции задаются отдельным исходным сценарием. Противоположная ориентация пары эквивалентна для domain lookup, но не является той же ordered source для генерации. Пары нельзя выводить из общей Zone; missing/extra/duplicate/foreign pairs запрещены existing admission.

Template policies задают те же ordered priorities, полные `MinionDefeatDecision`, `outnumbering_bonus_approved` и `can_leave_zone` каждого сохранённого actor **во всех составах и их достижимых состояниях**. True и False сохраняются; генератор не назначает GM approvals/escape facts по численности. Для can_leave_zone=True сохраняется проверка adjacent Zone. Если caller не может подтвердить общую применимость facts/пар/policies, нужны отдельно подготовленные сценарии или семейства.

Existing engine считает локальный outnumbering перед каждой атакой из текущего состояния. Уменьшение состава или defeat могут изменить бонус без изменения профиля/policy. Генератор не записывает static bonus; удалённый стрелок не становится союзником локальной Zone. `no_additional_rules=True` не разрешает стирать известные Abilities из книжного профиля.

## API и preflight

Генератор находится в application: собирает domain snapshots для existing simulator. Balance получает готовые inputs и aggregates. Модули — `application/mixed_candidate_generation_models.py`, `mixed_candidate_generation.py`, `mixed_candidate_generation_errors.py`.

| Тип / операция | Контракт |
| --- | --- |
| MixedCompositionGroup(group_id, actor_ids, minimum_count, maximum_count) | Frozen/slotted; непустой ordered tuple уникальных ID, включённые bounds |
| MixedCandidateGenerationRequest(template_scenario, groups, facts, pair_ranges, candidate_id_prefix, max_candidates, master_seed, stages, max_total_trials, window) | Frozen/slotted; typed mixed source/facts/pairs/groups/stages, прежний ObjectiveRateWindow; derived candidate_count/planned_trials |
| generate_mixed_candidates(request) | Pure bounded materialization всего семейства через public constructors; без runner/RNG/pool/IO |
| MixedCandidateGenerationResult(source_request, evaluation_request) | Frozen/slotted; exact source-bound MixedStagedEvaluationRequest |
| MixedCandidateGenerationError(candidate_id, counts) | Контекст ошибки конкретной проекции с исходным cause и notes; partial result не возвращается |

Group/request constructor и replace проверяют непустые string IDs/prefix, ordered inputs с tuple copy, unique group IDs, actor IDs без пересечений, exact partition противоположной стороны, отсутствие friendly/foreign/missing actors, равные полные definitions внутри группы. Bounds — exact int, не bool: 0 ≤ minimum ≤ maximum ≤ длина группы. Request требует хотя бы одну группу. Melee/ranged-only типы не принимаются вместо mixed.

Факты и пары проверяются до перебора, вместе с typed template/window/stages и seed. Используются existing mixed `_validate_stages`/`_planned_trials` и один `NpcMixedSimulationRequest` для admission общих seed/trial параметров без исполнения. Все stages проходят validation, даже если будущая оценка может закончиться раньше.

Для bounds [loᵢ, hiᵢ]: `C = product(hiᵢ − loᵢ + 1) − int(all(loᵢ == 0))`. Нулевой противоположный состав исключается; C=0 — ошибка, без автоматической победы. `max_candidates` и `max_total_trials` — положительные exact int. C вычисляется арифметически и сравнивается с max_candidates **до iterator/materialization**.

Полный staged budget: n₀=C; для каждого stage прибавить `nᵢ * trials_per_candidate`, затем `nᵢ₊₁=min(nᵢ, keep)`. Это бюджет полных повторных пакетов ADR-0032, без prefix reuse. Превышение max_total_trials отклоняется до перебора. Большое C проверяется без списка кандидатов.

**C считает все ненулевые векторы bounds, а не только заранее допущенные сценарии.** Request preflight не обещает, что каждый поднабор пройдёт mixed admission. Точные subset checks выполняются при materialization; недопустимый вектор прерывает весь вызов. Нельзя молча уменьшить C, фильтровать плохие составы или вернуть успешно построенный префикс.

## Порядок и проекция

Counts перечисляются лексикографически по ordered groups и возрастающим количествам, последний индекс меняется быстрее; all-zero исключается. Dedup отсутствует. ID — `prefix:counts:` + десятичные counts через запятую, initial round ID — candidate ID + `:initial`. Имена групп не входят в ID; source_request задаёт смысл координат. Это локальная идентичность кандидата, не глобальный content hash.

Для каждого вектора сохраняются все perspective actors и prefix actors каждой группы. Через existing public constructors строятся:

- roster с исходными participant snapshots/definitions и независимым исходным порядком;
- fresh attack state, initial round participants и actor_order, каждый в своём порядке; обычный side_order, budget и absence of pending/history сохраняются;
- spatial placements в исходном порядке и **весь исходный graph**, включая пустые Zones;
- отфильтрованные family pair_ranges для сохранённых endpoints, без изменения значений, порядка и ориентации;
- policies сохранённых actors с прежними флагами, target priorities и полными defeat decisions, отфильтрованными по retained targets;
- objective с сохранённым порядком оставшихся opposing IDs; repeated_stagger_choice, perspective_side и отдельные family facts.

Каждый новый `NpcMixedScenario` повторно проходит полный existing admission: обе Melee/Shooting роли, отсутствие Close-врага у стрелка, доступная начальная цель каждого actor, все enemy pairs, согласованность Zones/policies/objective/escape context. Роли нужны во всём сценарии, не обязательно на каждой стороне. Фильтрация не назначает новые цели и не переставляет приоритеты, чтобы «исправить» недопустимый состав.

Любой Exception при построении конкретного candidate оборачивается MixedCandidateGenerationError с его ID/counts, `__cause__` и сохранёнными notes; KeyboardInterrupt/SystemExit и другие BaseException проходят напрямую. Ошибки финального staged/result constructor идут напрямую, без вымышленного candidate ID.

Result constructor сверяет весь ordered staged input: C, ID/order, master_seed/stages/budget/window и **полное значение каждой ожидаемой projection**, а не только размеры roster. Подмена pairs/facts/GM flags/decisions/profile/state/placement/objective/round ID, пропуски/повторы/перестановки запрещены; равные source copies допустимы. Одна внутренняя projection function используется construction и guards; local import допустим для models/construction cycle. Guards строят по одной проекции, без второй сохранённой полной копии семейства. Result не содержит simulation records/outcomes/RNG/options. Guards не доказывают истинность facts или книжное происхождение произвольного numeric profile.

## Конечные примеры и проверки

В [probe](../examples/m7/generation_contract_probe.py) фиксированы Pbow@rear и P1/P2@arena. Противоположный резерв: A=(E2,E1), Footpad Dagger @arena, bounds 1..2; B=(E3), Brigand Warbow @far, bounds 0..1. Все enemy pairs заданы явно: пары melee–melee Close, остальные Medium с adjacent Zones. Actor order Pbow,P1,P2,E1,E2,E3; приоритет P1 — E3,E2,E1. Для P2 GM outnumbering=False/can_leave_zone=True, для остальных True/False соответственно; это явные решения для всего семейства.

| Counts | Enemies в actor_order | Приоритет P1 | Число пар |
| --- | --- | --- | --- |
| (1,0) | E2 | E2 | 3 |
| (1,1) | E2,E3 | E3,E2 | 6 |
| (2,0) | E1,E2 | E2,E1 | 6 |
| (2,1) | E1,E2,E3 | E3,E2,E1 | 9 |

C=4; stages=(10,keep=2),(100,keep=1) требуют 240 trials. Cap=3 или budget=239 должны отклоняться до перебора. При A.minimum=0 арифметика даёт C=5 и budget=250; первый ненулевой вектор (0,1) недопустим: P1/P2 не имеют Close-цели. Это отказ всего семейства при materialization, не четыре успешно сгенерированных кандидата. Отдельный пример с fixed opposition и удалением единственного Pbow отклоняется из-за отсутствия Shooting-роли. При всех bounds 0..0 C=0, при одном фиксированном положительном векторе C=1.

Probe вручную задаёт конечные векторы, строит public snapshots/staged request и проверяет сохранение sources/orders/pairs/policies/flags/graph. Пять отказов existing constructors: budget, family facts, missing pair, no Close target, no Shooting role. [Сохранённый вывод](../examples/m7/generation_contract_probe.output.txt) не содержит Monte Carlo-результатов. Сам probe не использует production group/request preflight; его арифметические assertions cap не заменяют отдельные request tests, добавленные первым production-срезом ниже. Enumeration/result/error API реализованы вторым production-срезом ниже.

| Срез | Обязательные deterministic checks |
| --- | --- |
| Group/request | Frozen/slots/tuple copy/replace, exact IDs/bounds/partition/full definitions; отдельные typed facts/pairs, exact ordered pair equality; обе perspective; seed/window/все stages; C/caps/planned до enumeration/RNG, огромный C, fixed/all-zero bounds |
| Construction | Все ordered vectors/IDs; независимые groups/roster/combat/actor/placement/pair/policy/target orders; full snapshots/graph/decisions/True+False flags; оба направления perspective; отсутствие runner/RNG/pool/IO; повторный mixed admission, потеря роли/цели, fail first/later без silent skip/partial, cause/notes/interrupts/final boundaries |
| Result | Exact source/full projection; equal copies, foreign types, order/missing/duplicates; подмена pairs/orientation/facts/flags/profile/позиции/цели/ID; immutable source и отсутствие observations |
| Integration | Generation → existing staged service; полные sequential/process reports равны; repeat/rename prefix; локальный outnumbering до/после defeat при разных составах, удалённый стрелок не учитывается в другой Zone, полные GM decisions; без exact Monte Carlo percentages |

Первый срез — **MixedCompositionGroup и MixedCandidateGenerationRequest с полным preflight/derived C/planned_trials и tests** — реализован без перебора/материализации. Construction/result/error, integration, самостоятельный production-пример и аудит также завершены; следующий выбранный этап — контракт mixed JSON/CLI. Existing M6 tests служат техническим ориентиром, не заменяют mixed checks. Domain/engine/simulation/evaluation, игровые правила, метрика и ранее согласованный roadmap направления не меняются.

## Реализованный первый срез

2026-09-29: [MixedCompositionGroup/MixedCandidateGenerationRequest](../../src/towr/application/mixed_candidate_generation_models.py) реализованы в application. Frozen/slotted типы принимают tuple/list с копированием в tuple; set/mapping/string/iterator вместо ordered input отклоняются. Проверены exact IDs/bounds/partition/full definitions, typed mixed inputs, отдельные family facts и exact ordered equality pair_ranges, seed/window/все stages, арифметические C/max_candidates и полный planned_trials/max_total_trials. Используются existing mixed stage validators/budget и одна simulation request admission для seed. Template policies, включая can_leave_zone/GM flags/полные decisions, сохраняются; existing scenario admission уже проверяет escape path при неизменном graph/placements.

[15 deterministic tests](../../tests/unit/test_m7_mixed_candidate_generation_models.py) проверяют C=4/budget=240, отказы 3/239, расширенные bounds C=5/250 без фильтрации недопустимого поднабора, fixed/all-zero bounds, обе perspective, typed family отказ, порядок/ориентацию/значения и explicit presence пар, tuple copies/frozen/replace и сохранение источника/GM flags. Сорок групп дают C=2**40−1 арифметически; одна seed admission, запрет enumeration/projection/candidate/RNG/runner/pool проверен. Материализации и проверки каждого subset ещё нет; запрос не обещает допустимость всего семейства. Production construction/result/error и сквозная evaluation остаются следующими срезами.

Полная регрессия после первого среза: **2492 tests OK (276,023 с)**, Windows/Python 3.14.5; compileall, локальные ссылки, finite probe и git diff --check успешны. Commit/push не выполнялись.

## Реализованный второй срез

2026-09-29: [generate_mixed_candidates](../../src/towr/application/mixed_candidate_generation.py), [MixedCandidateGenerationResult](../../src/towr/application/mixed_candidate_generation_models.py) и [MixedCandidateGenerationError](../../src/towr/application/mixed_candidate_generation_errors.py) реализованы. Ordered prefix-count vectors без all-zero/dedup строят новые public-admitted сценарии. Исходные snapshots, независимые orders roster/combat/actor/placement/pairs/policies/targets, весь graph, полные defeat decisions и оба True/False policy flags сохраняются; family facts/pairs не синтезируются. Каждый subset повторно проходит полный NpcMixedScenario admission, включая роли и начальные цели.

Result сравнивает полные projections и общие staged параметры с source_request; равные source copies допустимы. Ожидаемые проекции проверяются по одной без второй сохранённой копии семейства. Ошибка любого состава прерывает вызов без silent skip/partial и сохраняет candidate ID/counts/original cause с notes. BaseException и финальные staged/result constructor errors проходят напрямую. RNG/runner/pool/evaluation не исполняются.

[17 deterministic tests](../../tests/unit/test_m7_mixed_candidate_generation.py), вместе с 15 preflight — 32, проверяют четыре count vectors, отдельное all-zero/dedup семейство, обе perspective, reserve больше выбранного maximum, повтор/rename prefix, independent orders/pairs orientation/full snapshots/GM decisions/flags/graph, exact source/result substitutions и frozen/equal-copy/no-records. Реальный bow-only subset вызывает отказ из-за отсутствия Close-цели первым или после двух допущенных составов; потеря единственной Shooting-роли также отклоняется. Инъекция второго admission failure сохраняет cause/notes; interrupts/final boundaries проверены. Domain/engine/simulation/staged evaluator не менялись.

Следующий шаг — сквозная integration генерация → existing staged service через оба backend, повтор/rename prefix и динамический локальный outnumbering до/после defeat при разных составах и True/False GM flags. Самостоятельный production-пример и аудит затем; JSON/CLI и новые игровые действия вне среза.

Полная регрессия после второго среза: **2509 tests OK (327,280 с)**, Windows/Python 3.14.5; compileall, локальные ссылки, finite probe и git diff --check успешны. Commit/push не выполнялись.

## Сквозная integration

2026-09-29: [6 integration tests](../../tests/integration/test_m7_mixed_candidate_generation.py) завершают связь generator → existing staged service в текущем контракте (всего generation 38 tests: 15 preflight, 17 construction/result/error, 6 integration). Четыре generated candidates, stages 2/4 keep 2/1, planned budget 16. Реальные sequential/process workers=2/batch_size=3 дают равные полные reports/selection; повтор генерации/исполнения воспроизводим. Rename prefix меняет candidate/initial IDs, но сохраняет seeds и все assessments после нормализации source IDs, а также выбранные составы. Natural RNG observations не закреплены точными процентами/победителем; actual budget проверяется по выполненным полным отчётам и ограничивается planned.

Отдельный importable finite RNG с промахами внедрён на existing simulation boundary. Сам generator, staged/bounded evaluation и реальные sequential/spawn runners не подменяются. Все четыре состава поддержаны, два проходят на следующий этап; stages исполняют четыре полных пакета по 2 и два по 4: actual=planned=16 на backend, без prefix reuse. Проверены parent source identity, неизменность входа/global RNG и отсутствие оставшихся дочерних процессов.

Scripted public runner получает шесть generated составов с 1..3 Melee-врагами и 0..1 удалённым стрелком. Локальные соотношения 2:1/2:2/2:3 дают ожидаемые Attack trace/pools и точное число RNG calls при True/False GM approval. Дистанции сохраняются; удалённые стрелки не учитываются в чужой Zone, а Shooting не получает Melee-бонус. Поражение врага от дальнего выстрела меняет local 2:2→2:1 для следующей Melee-атаки; поражение союзника меняет 2:1→1:1 в следующем раунде при неизменном approval. Полные явно заданные DISARMED_AND_SURRENDERED decisions сохраняются в acknowledgement, pending после разрешения пуст. Production исправлений не потребовалось.

Непосредственно перечитаны BOOK-PLAYER-GUIDE 1.4, Equipment / Ranged Weapons, стр. 94; Rules / The Battlefield / Range, стр. 114; Attack Tests / Attack Modifiers, стр. 118–119; BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91; Understanding NPC Profiles, стр. 93; Brigands & Footpads, стр. 97. Новых правил/house rules нет. Следующий шаг — самостоятельный production-пример генерация → staged evaluation и аудит контракта; новые действия/Abilities и JSON/CLI вне этого среза.

Полная регрессия после integration: **2515 tests OK (401,383 с)**, Windows/Python 3.14.5; отдельно 6 tests OK (23,033 с). Compileall, локальные ссылки и git diff --check успешны. Commit/push не выполнялись.

## Итог аудита

[Аудит](../audits/m7-generation-readiness.md) сопоставил 38 tests и public APIs с контрактом; production исправлений не потребовалось. [mixed_balance.py](../examples/m7/mixed_balance.py) через public builder задаёт резерв Footpad Dagger/Brigand Warbow и отдельные family facts/pairs/GM policies, строит четыре состава и сравнивает полные sequential/process staged reports. Seed 42, два раунда, stages 8/32 keep 2/1, верхний budget 96 на backend. [Вывод](../examples/m7/mixed_balance.output.txt): actual=96 на каждый вызов, final COMPLETED/пустой выбор; один уточнённый состав вне окна, другой имеет unsupported на его границе. Assertions не фиксируют Monte Carlo проценты/победителя.

Проверены два cwd с одинаковым stdout, реальные generation failure и инъекция late-stage failure после 32 trials без partial stdout, сохранение cause/notes и остановка до следующего backend. Source/global RNG/cleanup и layer/public imports сохранены. Полная регрессия: **2515 tests OK (300,008 с)**, Windows/Python 3.14.5; compileall, локальные ссылки и diff/whitespace успешны. Все 665 существовавших src/tests/tools файлов неизменны; новых unittest tests нет. Пользователь выбрал продолжение — JSON/CLI mixed simulation/balance, сначала отдельный контракт без новых боевых правил. Commit/push не выполнялись.


Продолжение после аудита: [ADR-0034](ADR-0034-mixed-json-cli-v1.md) и [конечные JSON-примеры](../examples/m7/json/README.md) подготовлены. Wire сохраняет отдельные family facts/pairs, actor policies и отказ при недопустимом subset; генератор и его допуск не меняются. Следующий implementation-срез — mixed simulation Schema/command/pure adapters.
