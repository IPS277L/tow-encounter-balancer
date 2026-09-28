# ADR-0021: неподвижный ближний бой Minions

Статус: принято, 2026-09-28. **Production-вход, provider, исполнитель и scenario result реализованы** в указанной ниже границе.

## Основание и источники

Пользователь выбрал расширение боевой симуляции после [аудита M5](../audits/m5-external-readiness.md). K1 уже разрешает Melee Attack/Protection, а M2 переносит Close miss Staggered в roster. Однако `NpcRangedScenario` допускает только Shooting на Medium. Замена Range в его provider не создаёт корректный ближний сценарий: после поражения бойца меняется численное преимущество.

Непосредственно перечитаны локальные постраничные тексты:

| Источник | Основание контракта |
| --- | --- |
| BOOK-PLAYER-GUIDE 1.4, Rules / Combat и Ambush, стр. 112 | Один ход на участника; обычный порядок сторон; при засаде есть отдельное ограничение opposition в первом раунде |
| Та же книга, Rules / The Battlefield / Zones, Position, Range, стр. 114 | Close означает досягаемость рукой; одна Zone сама по себе Close не доказывает; позицию определяет GM |
| Та же книга, Rules / Attack Tests / Attack Modifiers, стр. 118 | Melee, Athletics/вооружённый Defence; осведомлённость; `+1d` за численное преимущество в Zone; исключение defeated/Defenceless/non-combatants из подсчёта |
| Та же книга, Rules / Attack Modifiers, Failed Attacks, Successful Attacks, Giving Ground, стр. 119 | GM вправе не применять неуместный бонус; Close miss Staggered без эскалации; Damage/Resilience и выбор при повторном Staggered |
| Та же книга, Rules / Conditions / Defenceless, Prone, Staggered, стр. 123 | Ограничения Conditions и доступные исходы повторного Staggered |
| BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91 | Одна Wound означает defeat; форму выбирает атакующий с одобрением GM |
| Та же книга, Allies and Antagonists / Understanding NPC Profiles, стр. 93 | Numeric Attack/Protection; одна выбранная атака; NPC не наследует автоматически свойства PC weapon |
| Та же книга, Allies and Antagonists / Brigands & Footpads, стр. 97 | Footpad: Dagger Close 3d/3, Dam 2, 1H; Athletics 3d/3; RES 3; Lurker вне боя. Brigand: Craven Opportunist даёт `+2d` вместо обычного `+1d` |

Правила: RULE-COMBAT-001/005..009/011/015, RULE-NPC-002/006..010, RULE-PROFILE-TALABEC-005. Число участников, фиксированные решения и список допущенных профилей ниже — граница сценария, не house rules. Существующие неоднозначности Brawn Charge/Greatsword сюда не входят.

## Решение: отдельный проверяемый вход

Реализован `domain/npc_melee_scenario_models.py` с frozen/slotted `NpcMeleeScenarioFacts`, `NpcMeleeActorPolicy`, `NpcMeleeScenario`. Конструкторы чистые: только preflight, без RNG, исполнения правил или изменения источников. Ошибка типа — TypeError, неподдержанное/несогласованное значение — ValueError. Коллекции копируются в tuple, порядки сохраняются; успешное построение является допуском, второй публичный validator не нужен.

`NpcMeleeScenario(initial, facts, actor_policies, repeated_stagger_choice, perspective_side, objective)` использует существующие `NpcRoundsRequest`, `CombatSide`, `NpcDefeatObjective` и `StaggerChoice`. Никакой зависимости от JSON/CLI/balance. `NpcRangedScenario`, simulation/balance v1 и их результаты не меняются. Новый вход не наследуется от ranged и не маскируется под него.

### Начальное состояние и профили

- Fresh round 1; ровно две непустые стороны; roster, round participants и spatial placements содержат одних и тех же actors/стороны. Нет active/completed/excluded turns, pending, weapon bindings, использованных receipt/acknowledgement/secondary histories или movement usages. `initial.max_rounds` — положительный integer, bool запрещён; это бюджет всего сценария.
- Все placements находятся в одной явно указанной `facts.zone_id`. Другие незанятые Zones графа допустимы. Все бойцы этой Zone включены в roster; нет внешних бойцов, mounts/riders или non-combatants, влияющих на подсчёт.
- Все actors — здоровые Minions: 0 Wounds, limit 1, не defeated, никаких начальных Conditions, включая Staggered. Достижимое в ходе исполнения состояние — только обычный Staggered либо defeat после Wound.
- У definition ровно одна доступная numeric `Skill.MELEE` атака с `range_min=range_max=CLOSE`, обычным Damage multiplier 1, 1H либо 2H. Нет дополнительного pool cap, armour-ignore или secondary effects. Short-reach Melee, Brawn, Shooting/Throwing, несколько оружий и особые эффекты здесь отклоняются.
- Оружие присутствует; щита нет; текущая Resilience совпадает с definition. Броня в числовой Resilience допустима, но не создаётся по имени оружия/профиля. Shield/equipment changes этим входом не моделируются.
- Ровно один numeric Protection profile: `ATHLETICS` либо `DEFENCE`, без дополнительного pool cap. Defence разрешён уже имеющимся оружием. Это явно supplied готовая защита; автоматического сравнения Skill или переноса PC weapon bonuses нет. Строка Protection должна соответствовать реальному источнику NPC.

Пример Footpad со стр. 97 использует Athletics. Возможность supplied Defence опирается на общее правило стр. 93, а не меняет профиль Footpad.

### Явные факты позиции и применимости

`NpcMeleeScenarioFacts` не имеет defaults:

| Поле | Допуск и значение |
| --- | --- |
| `zone_id` | Непустой ID общей занятой Zone |
| `all_opponents_in_close_range` | Только True: каждая вражеская пара в Close всё время, пока оба действуют |
| `targets_aware`, `clear_line_of_sight`, `stationary` | Только True для всех этих пар на протяжении сценария |
| `all_zone_combatants_included`, `unmounted_combatants_only` | Только True: полный состав для подсчёта, каждый actor считается один раз |
| `no_higher_ground`, `no_additional_rules`, `no_other_test_modifiers` | Только True: нет высоты/Charge/Help/специальных Abilities или модификаторов, кроме рассчитываемого ниже outnumbering |
| `can_leave_zone` | Explicit bool: общий для actors факт возможности Give Ground; при True граф должен иметь соседнюю Zone. False допускается и при наличии соседей: путь может быть заблокирован |

`can_leave_zone` передаётся existing kernel, но не выбирает Give Ground: фиксированная policy выбирает Wound. Нельзя из неподвижной тактики заключать, что путь физически закрыт. Нельзя выводить Close, awareness, полную численность, LOS, доступность пути или отсутствие Abilities из графа/numeric definition. Caller отвечает за истинность фактов; конструктор проверяет их наличие, тип и совместимость с представимыми данными. При заведомо ложном `no_additional_rules=True` числовой input не доказывает соответствие книге.

Здесь нет универсального engagement graph. Область допуска — все вражеские пары Close в одной Zone. Close через границу соседних Zones разрешён книгой, но отклоняется этим срезом. Если размещение не позволяет каждому атаковать любого противника без движения, этот вход не подходит.

### Порядки, решения и цель

`NpcMeleeActorPolicy(actor_id, target_actor_ids, defeat_decisions, outnumbering_bonus_approved)` задаёт одного actor, приоритеты **всех** его противников ровно по одному разу и полный `MinionDefeatDecision` для каждого в том же порядке. Все decisions совпадают по attacker/target и имеют `gm_approved=True`; поддерживаются все три disposition. `outnumbering_bonus_approved` — обязательный bool: явное решение GM применять обычный бонус, когда он возникает, либо удерживать его во всём сценарии для этого actor. False не является неподдержанным вводом или отсутствующим ответом. Если решение GM должно зависеть от конкретного соотношения сил, первый фиксированный контракт не подходит; автоматический порог вроде 7:6 не вводится.

`actor_policies` содержит каждого actor ровно один раз; `policy_for(actor_id)` сохраняет supplied policy либо отклоняет неизвестного. Приоритет внутри стороны берётся из `initial.current.actor_order` и сохраняется с фильтрацией defeated при advance. Для первого свежего боя без surprise принимается обычный `side_order=(PLAYERS_AND_ALLIES, OPPOSITION)`. Перевёрнутый порядок отклоняется этим новым входом: настоящая засада требует отдельной модели first-round awareness. Это не меняет допуск существующего ranged API или low-level scheduler.

`repeated_stagger_choice` задаётся явно и допускает только `SUFFER_WOUND`: обычный законный выбор держать позицию, а не автоматическое правило для всех Minions. Все actors продолжают Attack; Recover/переход к другой тактике не выбираются. `perspective_side` задаётся явно и может быть любой из двух сторон; objective содержит всех и только её противников.

## Численное преимущество перед каждой атакой

Provider получает **текущий** roster/history и spatial snapshot. Для acting actor считает всех союзников (включая его) и врагов (включая target) в его Zone, исключая defeated и Defenceless. В admitted сценарии нет non-combatants/mounts; новые такие участники не появляются. Завершённый ход не исключает бойца из счёта. Staggered сам по себе также не исключает бойца.

При allies > enemies и `outnumbering_bonus_approved=True` добавить ровно один `DiceModifier("RULE-COMBAT-009:outnumbering", 1)` с обычным ограничением пула. При равенстве, меньшинстве или явном withholding не добавлять нулевой modifier. Бонус применяется только к Attack, не к Protection. Provider сам строит modifiers; внешний произвольный список не входит в scenario input.

Пересчёт происходит после каждого результата, а не только при новом раунде: `2:2 → defeat → 2:1` даёт следующему союзнику `+1d`, даже если defeated всё ещё присутствует в roster/placements. IDs/исходный размер стороны/только ожидающие ходы не заменяют подсчёт. Полный selection source и modifier остаются в журнале, отдельного mutable счётчика нет. Результат проверяет ожидаемые candidates по каждому текущему source, поэтому сохранение старого бонуса после изменения состава отклоняется.

Brigand в общем сценарии с возможным преимуществом не соответствует `no_additional_rules=True`: Craven Opportunist ещё не подключён и требует отдельного расширения. Нельзя объявить его поддержанным только потому, что в начале 2:2. Первым fixture выбран Footpad: Lurker относится к обнаружению вне боя, которого этот уже осведомлённый сценарий не исполняет.

## Реализованные исполнение и результат

`engine/npc_melee_scenario_runner.py::run_npc_melee_scenario(scenario, rng)` переиспользует один existing `run_npc_rounds(..., max_rounds=1)` на каждый остаток раунда. RNG внедрён, kernel/Attack/receipt не дублируются. Candidate использует Close, aware=True, exact numeric Attack/Protection и свежий бонус. Staggered actor берётся из roster; existing executor переносит Close miss Staggered **без** repeated-Staggered escalation. Successful low Damage по уже Staggered цели вызывает заданный SUFFER_WOUND и Minion defeat.

Pending defeat обрабатывается existing acknowledgement по полной последней Attack и supplied GM decision, затем existing exclusion убирает ещё не завершённый ход цели. Defeated остаётся в roster и исключается из последующих targets/подсчёта. Если осталась одна действующая сторона, исполнение заканчивается немедленно после этих последствий, до нового actor/advance. Иначе resume сохраняет ID/round/history, а завершённый раунд при оставшемся глобальном бюджете проходит existing advance с surviving participants и сохранённым порядком.

`domain/npc_melee_scenario_result_models.py` содержит отдельные `NpcMeleeScenarioResult/Outcome` и чистую проекцию ожидаемых candidates для provider и проверки журнала. Результат сохраняет exact source scenario, `NpcRoundsChainSummary`, optional terminal acknowledgement/exclusion. Последний suffix не создаёт фиктивный runner observation, не повторяет kernel и не объявляет незавершённый раунд завершённым. `current` включает suffix; решения и счётчики производны из полных источников.

Четыре исхода: OBJECTIVE_ACHIEVED, SIDE_DEFEATED, ROUND_LIMIT, UNSUPPORTED_PATH. Бюджет не сбрасывается на resume; ROUND_LIMIT означает исчерпание раундов при обеих действующих сторонах. Неподдержанная остановка сохраняет причину/pending и не считается поражением; неверный input/source и неожиданные exceptions не маскируются под игровой исход. Проверка результата требует exact цепочку, actual candidate/modifier/GM decisions, лимит и отсутствие работы после terminal defeat. Повторные apply блокируются существующими source/history guards; полный откат всех внешних snapshots не предотвращается.

Автоматические awareness, recovery, движение, поиск лучшей тактики, Monte Carlo и общий battle aggregate не добавляются. Ranged loop не обобщается заранее: общие узкие helper возможны только при обнаруженной реальной дубликации, без изменения прежних контрактов.

## Соответствие существующим API и проверки

| Обязанность | Уже существующее основание | Что ещё требуется M6 |
| --- | --- | --- |
| Immutable definitions/actors | [ADR-0008](ADR-0008-npc-roster-boundary.md), `NpcRoster` | Melee scenario admission поверх low-level roster |
| NPC Attack/Protection | `prepare_npc_attack`, `prepare_npc_attack_protection`; [preparation tests](../../tests/unit/test_k1_npc_attack_preparation.py), [Protection tests](../../tests/unit/test_k1_protection_preparation.py) | Свежий обычный outnumbering и фиксированные Close/facts |
| Выбор/однократное исполнение | [ADR-0009](ADR-0009-npc-attack-selection-policy.md), `select_npc_attack`, `execute_npc_roster_attack`; [roster execution tests](../../tests/unit/test_m2_npc_roster_attack_execution.py) | Policy-based candidate provider; Close miss уже переносится |
| Turn/defeat/advance | [ADR-0010](ADR-0010-single-minion-round.md), [ADR-0011](ADR-0011-bounded-minion-rounds.md); [round tests](../../tests/unit/test_m2_npc_round_coordinator.py), [Staggered tests](../../tests/unit/test_k1_stagger_resolution.py) | Замкнутый loop с общим бюджетом и полным GM suffix |
| Source-bound report | `NpcRoundsChainSummary`, пример [ADR-0013](ADR-0013-ranged-minion-scenario-input.md) | Отдельный Melee result и проверка каждого динамического modifier |

[Исполняемый probe](../examples/m6/README.md) строит numeric Footpad input существующими constructors, выполняет две реальные Attack с acknowledgement/exclusion, подтверждает изменение пула 3→4 после defeat при 13 RNG calls, проверяет четыре отказа source/replay/budget. Он проверяет совместимость существующих деталей, **не** является реализацией `NpcMeleeScenario` и не заменяет tests полного admission/runner.

Реализованный preflight принимает 1×1/2×2/3×2, оба значения GM бонуса, оба Protection skills на корректных numeric источниках, оба perspective и все dispositions. Отклоняет missing/duplicate policies/targets, неправильную цель, все начальные Conditions, использованные состояния, чужие стороны/placements, разные занятые Zones, неподтверждённый Close/awareness, несовместимые profiles/equipment/effects, неподдержанные facts, другой StaggerChoice и перевёрнутый initial side order. Неверный input не вызывает RNG/runner.

Для provider/runner нужны детерминированные проверки: равенство/большинство/меньшинство/withholding; 2:2→2:1 в том же раунде; completed и Staggered продолжают считаться; defeated не считается до/после exclusion; единственный бонус под cap; Protection без бонуса; Close miss без/с имеющимся Staggered; успешный слабый удар после Close miss вызывает Wound; terminal defeat до следующего actor; budget через resume; immutable inputs; подмена modifier/источника/решения и replay; одинаковый seed воспроизводит журнал без статистических ожиданий.

## Реализованный первый срез и следующий шаг

[Входные модели](../../src/towr/domain/npc_melee_scenario_models.py) реализуют только admission. Frozen/slotted snapshots не исполняют Attack и не создают второй публичный validator. Принимаются упорядоченные list/tuple policies/decisions/targets с копированием; set/dict не задают порядок и отклоняются. Вложенные существующие constructors сохраняют свои классы ошибок (например, NpcRoundsRequest отклоняет boolean budget через ValueError); новые поля проверяют тип до значения.

[17 unit tests](../../tests/unit/test_m6_npc_melee_scenario.py) покрывают 1×1/2×2/3×2, оба решения о бонусе и обе perspective, три disposition, independent orders/immutable copies, все initial Conditions, numeric Defence/2H/armour, guards profiles/equipment/facts/Zone/путь/порядок сторон/цель/policies/истории. Defence/2H/armour variants помечены synthetic input: они не переопределяют книжный Footpad. Существующий NpcRoundsRequest уже отвергает non-Minion в составе и несогласованные стороны; Melee boundary дополнительно исключает лишние roster/placement entries.

[6 integration tests](../../tests/integration/test_m6_npc_melee_scenario_preflight.py) передают допущенный вход существующим run_npc_round/run_npc_rounds через test-only provider. Реальные RNG/receipts проверяют четыре Close miss за два раунда без эскалации, слабое попадание после собственного промаха с SUFFER_WOUND, first/repeated Staggered с учётом уже походившего союзника, 2:2→2:1 с +1d либо явным GM withholding после acknowledgement/exclusion, все disposition и порядок целей. Invalid Ablaze и weapon-bound вход отклоняются до runner/RNG. Kernel/repeated-choice/RNG counts, неизменность источников и повтор acknowledgement проверены; реальный continuation нельзя подать как fresh input.

Production candidates/runner/result реализованы следующим срезом, описанным ниже. Test-only provider первоначальных admission tests остаётся отдельной проверкой передачи входа. Одиночный Melee-срез закрыт [аудитом](../audits/m6-readiness.md); [полный воспроизводимый пример](../examples/m6/README.md) использует public runner. Следующий отдельный контракт — последовательные независимые Melee-прогоны и aggregate summary. JSON v1 не расширяется этим завершением typed runner.

## Проверка production-исполнителя

[melee_scenario_candidates](../../src/towr/domain/npc_melee_scenario_result_models.py) принимает scenario, текущий selection context и SpatialBattleState. Проверяет совпадение spatial с исходными graph/placements/usages, кроме текущего round_number, считает живых не-Defenceless участников в общей Zone и строит ordered surviving targets. Provider и проверка результата используют одну чистую проекцию. Ни selection projection, ни result validation не вызывают RNG или повторный kernel. Источники каждого modifier сохраняются в preparation/Test trace. Бонус обычный, без bypass cap: BOOK-PLAYER-GUIDE 1.4, Rules / Rolling Dice / Dice Modifiers, стр. 107 ограничивает пул удвоенной Characteristic; отдельного потолка 10 для K1 нет.

[run_npc_melee_scenario](../../src/towr/engine/npc_melee_scenario_runner.py) сохраняет existing policies/receipts, завершает полный supported defeat acknowledgement и необходимый exclusion перед terminal outcome. Последняя уже походившая цель не исключается повторно. Global budget не сбрасывается при resume, законченные раунды и посещённые номера не смешиваются. Source-bound result проверяет candidates даже при blocked selection: неподходящий supplied список или stale bonus дают ValueError, а не ложный UNSUPPORTED_PATH. Корректная техническая остановка сохраняет blocked reason/очередь, exceptions RNG/executor пробрасываются. Для штатного допущенного сценария техническая остановка не ожидается; она проверена имитацией controller stop с корректными candidate sources, не новым игровым правилом.

Добавлены [6 candidate unit tests](../../tests/unit/test_m6_npc_melee_candidates.py), [15 runner/result unit tests](../../tests/unit/test_m6_npc_melee_scenario_runner.py), [9 integration tests](../../tests/integration/test_m6_npc_melee_scenario_cycle.py). Всего новый срез — 30 tests, весь M6 — 53 (38 unit + 15 integration), без повторного счёта прежних K1/M2 tests. Покрыты equality/majority/minority/GM withholding, completed/Staggered в подсчёте, исключение defeated до и после turn exclusion, Defenceless в counting projection, armed Defence и явный can_leave_zone, обычный cap/однократный trace; оба perspective/все dispositions, изменение targets, terminal до нового actor/advance, already-acted target, repeated Staggered между раундами, budgets 1/2/3 после defeat resume, все промахи, 20 повторяемых seeds без статистических порогов. Подмена source/GM decision/bonus/candidates/StaggerChoice/advance order/budget, отсутствие terminal suffix, duplicate переходы и post-terminal observation отклоняются. Повтор apply Attack/acknowledgement с returned state запрещён existing consumers.

Синтетическая Defenceless-проверка относится только к формуле подсчёта; initial admission по-прежнему отвергает эту Condition. Нельзя считать её добавлением тактики Defenceless/Prone или нового сценария. Документальный constructor probe сохранён и не заменяет production runner; CLI/JSON/Monte Carlo/балансировщик Melee ещё не подключены.

2026-09-28 — [аудит одиночного среза](../audits/m6-readiness.md) завершён: обязательства сопоставлены с APIs и 53 existing tests, добавлен один [subprocess test примера](../../tests/integration/test_m6_example.py). Всего M6 54 tests (38 unit, 16 integration). Production src и этот игровой контракт не менялись. Минимальные требования к следующему simulation/summary записаны в аудите как будущий отдельный срез; CLI/JSON/balance ещё не расширены.

Продолжение реализовано по [ADR-0022](ADR-0022-independent-melee-simulations.md): последовательные независимые прогоны и aggregate summary поверх неизменённого одиночного runner. Исход после terminal suffix используется отдельно от raw runner stop. Игровой допуск ADR-0021 не расширен.
