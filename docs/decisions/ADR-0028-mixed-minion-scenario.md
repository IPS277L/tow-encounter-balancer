# ADR-0028: неподвижный смешанный бой Minions

Статус: принято, 2026-09-29. **Production mixed admission, provider, runner и result реализованы; аудит одиночного mixed-сценария остаётся следующим срезом.** Пользователь выбрал смешанный дальний и ближний бой после закрытия ADR-0027. Это следующий этап M7; существующие ranged/Melee APIs и wire v1 сохраняют свои границы.

## Источники

Непосредственно проверены локальные извлечённые страницы книг:

| Источник | Основание |
| --- | --- |
| BOOK-PLAYER-GUIDE 1.4, Equipment / Ranged Weapons, стр. 94 | Любой враг в Close запрещает ranged weapon без Close в Optimum; ограничение относится не только к выбранной цели. Вне Optimum штраф –1d; обычное заряжание возможно без отдельного Test, если оружие не требует Reload |
| Та же книга, Rules / Combat и Ambush, стр. 112 | Ходы, действия, обычный порядок сторон; surprise требует отдельного учёта осведомлённости |
| Та же книга, Rules / The Battlefield / Range, стр. 114 | Close — досягаемость, Medium — соседняя Zone; общая Zone сама по себе не устанавливает Close |
| Та же книга, Rules / Battlefield Features / Cover and Concealment, стр. 115 | Укрытие/видимость может менять Shooting; отсутствие modifiers требует внешнего утверждения |
| Та же книга, Rules / Combat Actions, стр. 116 | Движение, смена предметов и заряжание — отдельные допустимые возможности; наличие возможности не задаёт автоматическую тактику |
| Та же книга, Rules / Attack Tests / Attack Modifiers, стр. 118–119 | Opposed Attack/Protection, awareness; обычный +1d за большинство в Zone только для Melee/Brawn, право GM удержать бонус |
| Та же книга, Rules / Failed Attacks, Successful Attacks, Giving Ground, стр. 119; Conditions / Staggered, стр. 123 | Close miss даёт Staggered без повторной эскалации; Damage/Resilience, повторный Staggered и альтернативные последствия |
| BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91 | Wound побеждает Minion; disposition требует решения атакующего с учётом GM |
| Та же книга, Allies and Antagonists / Understanding NPC Profiles, стр. 93 | Числовые Attack/Protection, выбор одного Attack, явное наличие оружия; NPC не наследуют автоматически свойства оружия PC |
| Та же книга, Allies and Antagonists / Brigands & Footpads, стр. 97 | Числа Footpad Dagger и Brigand Warbow; Lurker вне боя; Craven Opportunist меняет именно Melee outnumbering |

Используются RULE-EQUIPMENT-004, RULE-COMBAT-001/005..009/011/015, RULE-NPC-002/006..010. Новых игровых правил нет. Ограниченный допуск, неподвижность и фиксированная тактика ниже — границы моделируемого сценария, не house rules.

## Вход и допуск

Отдельный `domain/npc_mixed_scenario_models.py`, без наследования от ranged/Melee, с frozen/slotted моделями:

- `NpcMixedPairRange(first_actor_id, second_actor_id, target_range)` — явная симметричная дальность одной вражеской пары. Направление записи несущественно, исходный порядок записей сохраняется; обратный дубль запрещён.
- `NpcMixedScenarioFacts(targets_aware, clear_line_of_sight, stationary, all_zone_combatants_included, unmounted_combatants_only, no_higher_ground, no_additional_rules, no_other_test_modifiers, ammunition_sufficient, requires_reload_action)` — обязательные bool без defaults. Все True, кроме requires_reload_action=False. Утверждения относятся ко всему сценарию, ammunition/reload — ко всем стрелкам и всему бюджету; ordinary Melee outnumbering не является «другим» modifier.
- `NpcMixedActorPolicy(actor_id, target_actor_ids, defeat_decisions, outnumbering_bonus_approved, can_leave_zone)` — полный приоритет врагов, одно preapproved решение на каждого в том же порядке, два обязательных bool. Для Shooting outnumbering flag сохраняется, но бонус не применяется. can_leave_zone относится к этому actor как к цели и не выводится из графа.
- `NpcMixedScenario(initial, facts, pair_ranges, actor_policies, repeated_stagger_choice, perspective_side, objective)` — existing `NpcRoundsRequest`, явные факты/пары/policies, `SUFFER_WOUND`, typed сторона и `NpcDefeatObjective`.

Конструкторы только проверяют/копируют вход; без RNG, исполнения, materialization боёв или отдельного public validator. Коллекции копируются в tuple. Wrong type → TypeError, несовместимое/неподдержанное значение → ValueError. Непустые ID не нормализуются; source ID — метка, не доказательство полноты правил.

### Состояние и профили

Fresh round 1, две непустые стороны, обычный side_order `(PLAYERS_AND_ALLIES, OPPOSITION)`, каждый actor ровно один раз в roster/round/placements/order. Нет active/completed/excluded turns, pending, weapon bindings, использованных receipts/acknowledgements/secondary histories или spatial usages. Все actors — здоровые Minions без начальных Conditions, wound_limit=1. Текущая Resilience равна definition, оружие в руках, щита нет. Бюджет `initial.max_rounds` — положительный int, bool запрещён.

Ровно одна доступная numeric Attack на actor, fixed role на весь сценарий:

| Роль | Допуск |
| --- | --- |
| Melee | Skill.MELEE, range_min=range_max=CLOSE, 1H либо 2H |
| Shooting | Skill.SHOOTING, Optimum MEDIUM–LONG, 2H; в этом срезе исполняется только Medium |

Есть хотя бы один actor каждой роли; стороны не обязаны иметь одинаковое распределение. У всех обычный Damage multiplier=1, без cap override/ignore armour/secondary effects. Protection в первом mixed-срезе — **ровно один Athletics profile** без cap override: он применим к обоим типам входящей атаки. Defence-only/Melee opposition/shields и выбор разных Protection против разных атак требуют отдельного расширения и отвергаются до запуска, а не заменяются Athletics автоматически. Значения dice/threshold/damage/resilience передаются явно через существующие typed profiles.

Первый пример использует Footpad Melee и числовую проекцию Brigand Warbow. Bow-only Brigand не делает Melee, поэтому Craven Opportunist на этом пути не применяется; добавление Axe или смены оружия нарушит допуск. Полный Brigand Melee с +2d не поддержан. Пользователь отвечает за отсутствие других применимых Abilities: имя профиля не позволяет их игнорировать.

### Геометрия и доступность

`pair_ranges` содержит все и только неупорядоченные пары противоположных сторон ровно один раз. Self/friendly/missing/duplicate/unknown пары запрещены. Для пары разрешены только Close либо Medium. Close дополнительно требует одинаковую Zone; Medium — разные соседние Zones. Это проверка совместимости supplied facts, не автоматический расчёт Close. Close через границу соседних Zones книга допускает, но первый контракт исключает.

Включены все combatants каждой занятой Zone, без mounts, riders, non-combatants и внешних участников. Дополнительные пустые Zones разрешены. Истинный can_leave_zone требует соседней Zone; False допустим и при её наличии, поскольку граф не доказывает возможность отхода. Движение не исполняется, placements/pair_ranges не меняются при defeat; defeated исключаются из выбора и подсчёта.

На старте каждый actor должен иметь хотя бы одну допустимую цель. У Melee это враг в Close. У Shooting это враг на Medium и **отсутствие любого врага в Close**, включая врага, которого стрелок не выбирает. Bow actor с Close-врагом отклоняется целиком на preflight. В стационарном сценарии новые Close-пары не появляются.

Все и только враги присутствуют в target_actor_ids и objective противоположной perspective стороны. Policy может ставить недоступного по дальности врага первым: provider пропускает недоступные пары и берёт первую живую **доступную** цель. Нельзя подменять всю policy списком только начальных доступных целей; полный список и GM decisions остаются частью source.

## Provider и исходы

Pure projection `mixed_scenario_candidates(scenario, context, spatial)` проверяет typed context и stationary spatial snapshot (допустимо изменение round_number), использует свежий roster и supplied пары. Она нужна и provider, и проверке журнала результата.

Для Melee считать живых combatants **в Zone атакующего**, независимо от их роли, завершённости хода и Staggered. Defeated/Defenceless не считаются. При allies > enemies и явном approval добавить один `DiceModifier("RULE-COMBAT-009:outnumbering", 1)`; иначе не добавлять нулевой modifier. Стрелок в другой Zone не даёт союзнику численное преимущество. Shooting не получает этот бонус даже при большинстве. Все остальные модификаторы исключены admission.

Кандидат сохраняет actual pair range, наличие любого живого Close-врага, явную awareness, Athletics options цели, её can_leave_zone и свежие modifiers. Protection/Attack/receipt исполняются существующими APIs. Close miss Staggered и отсутствие penalty у Medium miss остаются в существующем executor. Successful low Damage по уже Staggered цели использует заранее выбранный SUFFER_WOUND; recover/движение/Prone не выбираются автоматически.

`engine/npc_mixed_scenario_runner.py::run_npc_mixed_scenario(scenario, rng)` соединяет существующий `run_npc_rounds(..., max_rounds=1)`, Minion acknowledgement/exclusion и advance с общим бюджетом. Сначала погасить supported defeat и проверить terminal side; затем resume/advance. Defeated не возвращается, неподдержанная остановка не поглощается, RNG внедрён, kernel и Attack не повторяются.

Отдельные `NpcMixedScenarioResult/Outcome` сохраняют exact source, `NpcRoundsChainSummary` и terminal acknowledgement/exclusion suffix. Четыре исхода: OBJECTIVE_ACHIEVED, SIDE_DEFEATED, ROUND_LIMIT, UNSUPPORTED_PATH. Проверяется вся цепочка sources, пары/приоритет **доступных** целей, актуальные модификаторы, decisions, бюджет и отсутствие работы после terminal defeat. Source guards не защищают от полного внешнего отката snapshot и не доказывают происхождение RNG.

**Потеря всех доступных целей — техническая остановка.** Если обе стороны живы, но очередной actor больше не может атаковать, existing NO_CANDIDATE/SELECTION_BLOCKED становится UNSUPPORTED_PATH с полным stop context. Slot остаётся неисполненным. Не пропускать ход, не объявлять ничью/поражение/исчерпание раундов и не выбирать Wait/Recover/движение/смену оружия. Это существенно: другие actors ещё могли бы продолжить бой, но текущая fixed-role Attack-only policy его не завершает. Mixed input не обещает terminal result для каждого набора бросков.

## Проверочный пример и матрица реализации

[Конечный probe](../examples/m7/mixed_contract_probe.py) использует public constructors, `run_npc_round`, acknowledge/apply/exclude и scripted RNG, без imports tests/private builders. Это совместимость K1/M2, не production mixed API:

1. Pbow на Medium побеждает E1; P1 атакует E2 в Close с новым большинством 2:1 в arena. Пулы 3/4, 13 RNG calls, две Attack/receipts/defeat, прежний source не изменён.
2. Пять промахов при локальном 2:2: 30 RNG calls, Staggered получают только четыре Close-атакующих. Глобальное большинство 3:2 с удалённым стрелком не создаёт +1d в arena.
3. Pbow побеждает единственного Close-врага P1; другой enemy archer остаётся на Medium. Следующий P1 останавливается на NO_CANDIDATE без Attack/RNG и с неисполненным slot.

| Срез | Что требуется и чем проверять |
| --- | --- |
| 1. Typed admission | Модели выше; valid 2×1/3×2/2×2, роли, pairs/order/tuple/replace, обе perspective и dispositions, explicit bool, все fresh/profile/facts/graph отказы до RNG. Bow + любой Close-враг, неполная пара, Defence-only, нулевая начальная доступность обязательно отклоняются |
| 2. Provider/result/runner | Две роли в одном журнале, актуальный zone count после defeat обеих сторон, полный source/target-range/protection chain; terminal suffix и общий budget; NO_CANDIDATE как unsupported без skip; повторные IDs/подмена пары/старого modifier отклоняются |
| 3. Integration и аудит одиночного сценария | Scripted hit/miss/first и repeated Staggered, цели до/после defeat, GM withholding, недоступная первая цель, конец раунда/resume/advance, четыре исхода, неизменность inputs и ограниченное число исполнений; public пример и source/readiness matrix |

После аудита отдельно определяются независимые прогоны/summary/process, balance/generation и mixed JSON/CLI. Не переносить автоматически старые seed scheme, wire kinds или admissibility на новый бой. Текущий этап не добавляет движение, переключение оружия, новый scheduler, общий battle aggregate, универсальную систему правил, auto awareness/GM approval или новый пресет сложности. Подтверждённая метрика цели за лимит остаётся ориентиром для будущего агрегирования, но сам агрегатор этим ADR не реализуется.

Проверка контрактного среза: три сценария probe успешны; 78 существующих K1/M2/M6 tests OK (0,161 с), compileall примера, 1509 локальных Markdown-путей и diff --check успешны. Windows/Python 3.14.5. Production src/tests не менялись; полный набор повторно не запускался (последняя полная проверка 2298 OK). Точные команды — в статусе проекта.

## Реализация первого среза

[Четыре модели](../../src/towr/domain/npc_mixed_scenario_models.py) реализованы. Конструкторы проверяют весь admission без RNG/исполнения, копируют ordered sequences в tuple и сохраняют sources. `policy_for(actor_id)` возвращает исходную policy; `range_for(first_actor_id, second_actor_id)` читает supplied дальность в обоих направлениях. Unknown/self/friendly lookup отвергается, исходный порядок и направление pair records не нормализуются. Никаких cached mutable maps в состоянии нет.

[25 unit tests](../../tests/unit/test_m7_npc_mixed_scenario.py) покрывают valid 2×1/3×2/2×2, обе perspective, dispositions и bool policies, неизменяемость/порядки, fresh guards, обе роли, numeric profile границы, Athletics-only, все enemy pairs, начальную доступность и запрет bow при любом Close-враге. Более ранняя недоступная цель остаётся в полной policy; дальнейший выбор доступной цели относится к provider. Оба fixture [probe](../examples/m7/mixed_contract_probe.py) теперь сначала строят production NpcMixedScenario, затем проверяют прежнюю композицию public K1/M2. На момент первого среза mixed provider/result/runner ещё не были реализованы; их реализация описана ниже.

Проверка первого implementation-среза: 25 новых tests OK; полный набор **2323 tests OK (249,411 с)**, Windows/Python 3.14.5. Оба production-admitted fixture и три сценария probe успешны; compileall, 1515 локальных Markdown-путей, diff --check и whitespace новых файлов успешны. Исходное дерево было чистым. Commit/push не выполнялись.

## Реализация второго среза

[Pure projection и result](../../src/towr/domain/npc_mixed_scenario_result_models.py) и [runner](../../src/towr/engine/npc_mixed_scenario_runner.py) реализованы. Provider и проверка отчёта используют одну проекцию ordered доступных целей. Raw policy может начинаться с недоступной по дальности цели; реальная Attack проверяется по первому доступному кандидату. Target escape берётся из policy цели. Outnumbering считает текущую Zone, включая завершивших ход/Staggered, исключая defeated/Defenceless; применяется только к Melee при явном GM approval.

Runner использует один bounded round call на остаток раунда, существующие acknowledgement/exclusion и advance. Предел общий для всего сценария; terminal suffix не создаёт нового observation/receipt. Результат сохраняет полный typed source и пересчитывает expected candidates для каждой selection, включая фактический Range, Protection options и modifiers; отдельно проверяет GM decisions, допустимый Staggered choice и surviving advance order. Unexpected exceptions проходят, реальный NO_CANDIDATE остаётся unsupported с полной диагностикой и неисполненным slot.

[8 candidate tests](../../tests/unit/test_m7_npc_mixed_candidates.py), [17 runner/result tests](../../tests/unit/test_m7_npc_mixed_scenario_runner.py) и [9 integration tests](../../tests/integration/test_m7_npc_mixed_scenario_cycle.py) прошли. Scripted cases проверяют 3→4 dice после defeat от Shooting, реальные no-target остановки, пропуск недоступной первой цели, GM withholding, repeated Staggered через advance, четыре исхода, source/replay guards и отсутствие повторного kernel/receipt. Seeded сравнения требуют только воспроизводимости/границ, не фиксированного процента. Дополнительного battle aggregate и обобщения старых runners нет. Следующий срез — отдельный аудит одиночного mixed-сценария и public пример полного runner.

Проверка второго implementation-среза: **34 новых tests OK (0,230 с)**; полный набор **2357 tests OK (244,425 с)**, Windows/Python 3.14.5. Три scripted сценария composition probe, compileall src/tests/tools/docs/examples/m7, 1525 локальных Markdown-путей, diff --check и whitespace новых файлов успешны. Полный самостоятельный пример runner и аудит остаются следующим срезом. Commit/push не выполнялись.
