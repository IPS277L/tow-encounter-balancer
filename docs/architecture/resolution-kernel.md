# Resolution kernel K1

Этот документ уточняет `ADR-0002`. Kernel разрешает одну элементарную проверку или атаку по книжным правилам. Он не определяет порядок ходов, цели столкновения, тактику бойцов или Monte Carlo.

## Контракт

Вход состоит из:

- неизменяемого `ResolutionRequest` с видом операции, участниками, профилями, дистанцией и контекстными тегами;
- снимка затронутого `CombatState`;
- уже собранных из экипировки, Talents, Abilities и условий типизированных `RuleEffect`;
- `RandomSource`;
- `DecisionProvider` для разрешённых книжных выборов.

Выход `ResolutionResult` содержит:

- новый снимок затронутого состояния;
- полный `RollTrace` с исходными кубами, перебросами, успехами и применёнными модификаторами;
- упорядоченные доменные события;
- `FollowUpRequest`, которые battle/application orchestration разрешит после завершения текущей операции.

Kernel не читает JSON, не выбирает AI-цель и не вызывает себя рекурсивно для бесплатных атак.

## Фазы проверки

```text
validate request
  → choose base profile
  → collect pool/threshold/quality modifiers
  → apply pool cap and one-die rule
  → initial roll
  → optional after-roll decisions (например Fate)
  → Grim/Glorious reroll
  → count final successes
  → compare sides and resolve tie
  → publish TestResult
```

Оба участника Opposed Test проходят одинаковый pipeline броска. Затем отдельный comparator применяет правила атаки, общий tie-break или его явное переопределение. `0:0` хранится отдельным результатом, а не разновидностью ничьей в пользу атакующего.

## Фазы атаки

```text
validate target/range/action
  → resolve attacker Test
  → resolve defence Test or mark unopposed
  → determine hit/miss
  → apply miss consequences
  → compute Damage
  → compute effective Resilience
  → choose normal or replacement impact
  → resolve Staggered / Wound / other effects
  → resolve injury policy and wound interventions
  → commit state and emit follow-ups
```

Порядок обязателен: например, состояние от Wild Attack возникает до броска, Prone от некоторых атак — до возможности Give Ground, а Armour Bane меняет броню лишь после определения Wound текущей атакой.

## Основные типы

Предварительные имена могут измениться при реализации, но обязанности фиксированы:

- `TestProfile(characteristic, skill)` и `InlineProfile(dice, threshold)` — источник броска;
- `TestRequest` / `OpposedTestRequest` — примитивные проверки;
- `AttackRequest` — одна атака по одной основной цели;
- `TestModifier`, `TieModifier`, `DamageModifier`, `ResilienceModifier` — числовые изменения своей фазы;
- `ImpactSpec` — обычный Damage либо явная замена результата;
- `SecondaryEffectSpec` — конкретное фазовое или multi-target правило, не общий AoE;
- `InjuryPolicy` — Player/Champion, Minion, Brute или Monstrosity;
- `DecisionRequest[T]` / `DecisionProvider` — контролируемый выбор;
- `FollowUpRequest` — дополнительная атака, Test, перемещение или эффект после завершения операции.

## Модель эффектов

`RuleEffect` — не произвольная глобальная event-шина. Каждый эффект объявляет:

- стабильный `rule_id` и источник;
- одну известную фазу применения;
- условие, вычисляемое только из переданного контекста;
- типизированное изменение либо результат.

Порядок эффектов внутри фазы детерминирован: сначала базовые правила, затем обязательные замены, числовые модификаторы и, наконец, добровольные решения. Если два правила невозможно упорядочить по книге, это фиксируется в `docs/contradictions.md`, а не разрешается скрытым порядком регистрации.

## Граница K1

В K1 входят Basic/Opposed Tests, одна атака, обычный и заменяющий impact, Damage/Resilience, Staggered, четыре injury policy, журнал результата и точки расширения для Fate/Talents/Abilities.

В K1 не входят раунды, Zones как изменяемая карта, выбор порядка стороны, полноценная магия, религия, перезарядка, mounted action economy и исполнение цепочки follow-up. Необходимые сведения о дистанции, Charge, брони и состояниях передаются как контекст, поэтому книжную корректность отдельной атаки можно проверить до нового battle loop.

## Инварианты

- одинаковые вход, решения и RNG дают байт-в-байт одинаковый структурированный результат;
- состояние меняется только через итоговый reducer;
- каждый применённый эффект виден в trace по `rule_id`;
- kernel не знает о вероятностях и числе симуляций;
- ошибка неполного контекста завершается явно, а не подставляет скрытый игровой default;
- follow-up не может изменить уже завершённый результат задним числом.

## Текущая реализация

`src/towr/rules/kernel.py` связывает существующие чистые stages для одной атаки и возвращает `ResolutionResult`:

- `AttackResult` и все вложенные roll traces;
- новый снимок состояния основной цели;
- результат Staggered, Wound или Monstrosity impact;
- применённый `WoundEffectResult`, включая условия и ограничения с источником и сроком действия;
- выбранный `ImpactSpec`: обычный Damage, Condition вместо Damage или Hazard вместо Damage;
- типизированные follow-up для Staggered атакующего, Give Ground, Endurance/внешних последствий Wound, смены профильного диапазона NPC или Monstrosity Reaction.

Kernel исполняет непосредственный эффект принятой строки Wounds Table как часть текущей injury-фазы, но не исполняет созданные им follow-up рекурсивно. Endurance использует общий Test resolver после того, как orchestration предоставит профиль персонажа; изменения инвентаря и анатомии остаются отдельными типизированными запросами.

`DamageImpactSpec` проходит полный Damage/Resilience pipeline. `ConditionImpactSpec` не вычисляет Damage; Staggered передаётся существующей repeated-Stagger policy, остальные Conditions применяются непосредственно. `HazardImpactSpec` возвращает `HazardExposureRequest` с рейтингом и Skill. После внешнего Test `resolve_hazard` вычисляет shortfall, передаёт его как базовое число кубов/профильных Wounds в общую injury policy и применяет failure Conditions.

Первые `SecondaryEffectSpec` задают две разные фазы. `ProneBeforeGiveGroundSpec` изменяет состояние основной цели до repeated-Staggered decision. `NearbyTargetsStaggerSpec` после завершения основной цели создаёт `NearbyTargetsStaggerRequest`; поиск существ и снимок их позиции остаются обязанностью будущего spatial orchestration. После выбора целей `NearbyTargetsStaggerResolutionRequest` проверяет их уникальность и отличие от основной, а executor обрабатывает входной порядок слева направо.

Основная и вторичные цели используют один `StaggerImpactRequest → StaggerImpactResult`, поэтому repeated-Staggered, injury policy, Near Miss и Wound effects не дублируются между kernel и multi-target слоем. Тот же контракт принимает `ConditionAfterGiveGroundSpec`: при выбранном перемещении follow-ups строго упорядочены как Give Ground, затем Condition. `ConditionOnHitSpec` работает только с `DamageImpactSpec` и изменяет состояние после завершения основной injury-фазы, но до исполнения отложенных Give Ground/secondary-target запросов.

`ConditionOnGiveGroundOrWoundSpec` получает уже подтверждённый исход общего Stagger/injury pipeline. Give Ground создаёт упорядоченную пару movement → Condition, а Condition после Wound применяется лишь при `wound_accepted` либо ненулевом числе профильных Wounds. Поэтому Near Miss не срабатывает как Wound. Каждый вторичный результат остаётся связан с `target_id`; применённые secondary rules записываются в trace.

Профильная Reaction тоже разделена на источник и исполнение. Kernel помещает конкретный `MonstrosityReactionSpec` и относящиеся к атаке эффекты в `MonstrosityReactionRequest`; orchestration создаёт `MonstrosityReactionResolutionRequest` с актуальным состоянием и только тем контекстом, который нужен выбранному spec. Resolver возвращает `MonstrosityReactionResolutionResult` с типизированным исходом.

Для Monstrous Flight это Give Ground или Wound; вертикальное перемещение остаётся предпочтением `GiveGroundDestinationPreference`, а не выполняется внутри kernel. Если Give Ground полностью невозможен, resolver не придумывает отсутствующую в книге замену и требует внешнего ruling. Для Unsteady это новое падение Prone либо уже имевшийся Prone. Новое падение создаёт `ReactorZoneHazardRequest`; spatial orchestration выбирает всех существ в Zone и передаёт их актуальные Test/injury contexts отдельному executor.

`ZoneHazardResolutionRequest` принимает уже выбранные цели с уникальными target/Test IDs и сохраняет переданный spatial-порядок. Один основной Skill источника остаётся обратно совместимым default; если `ZoneHazardRequest` содержит альтернативные Skills, каждая цель обязана явно передать собственный допустимый выбор. Executor создаёт по одной обычной экспозиции на цель с выбранным Skill и последовательно вызывает существующие `resolve_test` и `resolve_hazard` на общем RNG. `ReactorZoneHazardResolutionRequest` для Giant является узкой обёрткой, которая дополнительно требует присутствия самого реагирующего. Результат каждой цели хранит exposure, полный Test trace и Hazard result. Таким образом, multi-target orchestration не дублирует Test, Wounds Table, профильные injury policies, Near Miss или failure Conditions и по-прежнему не даёт kernel доступа к карте Zones.

`ZoneHazardPersistence` и необязательный `zone_anchor_target_id` описывают регистрацию Hazard во внешнем battle/spatial state, не добавляя карту Zones в kernel. Miscast `33–34` создаёт Hazard с `UNTIL_BATTLE_END`, якорем на текущей Zone мага, rating по всем фактически брошенным pool/bonus dice и выбором Endurance/Athletics. Текущие transient Abilities сохраняют прежний контракт.

Hazard может явно задать `RepeatedConditionReplacement`. Resolver сначала завершает Wound и её непосредственный эффект, затем на актуальном состоянии решает, применять исходное failure Condition или книжную замену. Эта узкая policy покрывает Soporific Breath без универсального языка эффектов: зона, доступность действия и дальность остаются во внешнем orchestration.

Фабрики конкретных NPC Abilities нормализуют только последствия после успешного объявления действия. Поэтому Troll Vomit возвращает одиночную `HazardExposureRequest`, а Swamp Breath — `ZoneHazardRequest`; проверки Staggered, враждебности цели, дальности, расхода действия и выбор карты выполняются будущим action/spatial orchestration до вызова kernel-слоя.

Troll Stupidity использует отдельное неизменяемое Ability-state, поскольку одного множества Conditions недостаточно для правила «не возвращается до конца боя». Начало боя добавляет Distracted, активное состояние отдаёт source-aware –1d modifier для каждого Test, а принятая профильная Wound, успешный внешний Leadership Test или уже выполненное другим правилом снятие Condition переводят Ability в `suppressed_until_battle_end`. Эти entry points принимают завершённые результаты предыдущей фазы и не подписываются на глобальные события; будущий battle loop отвечает за их вызов и создание свежего состояния в следующем бою.

Casting Test является специализированной композицией поверх общего Test resolver, а не второй бросковой системой. `CastingTestRequest` принимает исходный `TestRequest`, сам устанавливает Rule of Nine lock и сохраняет в `WizardMagicState` объявленный Lore, накопленную сумму successes и successes последнего броска. Lore остаётся активным даже после броска с нулём successes, поэтому следующая попытка не может незаметно сменить Wind of Magic. Финальные девятки не мутируют пул внутри того же reducer, а возвращаются одним `MiscastPoolIncreaseRequest`, который существующая threshold-фаза применяет к состоянию отдельно.

Post-Casting decision также остаётся чистой фазой. `CastingDecisionRequest` получает уже обновлённое состояние и Wizard Level, поэтому normal `CAST`/`WAIT` недоступен при обязательном неразрешённом Miscast. `WAIT` сохраняет snapshot без follow-up; `CAST` валидирует Lore/CV, переносит latest-roll successes в общий `SpellCastRequest` и очищает Casting snapshot. Один и тот же spell-cast контракт используется normal и pre-Miscast ветвями; он заканчивается до target discovery и spell-specific execution.

Между cast decision и Potency находится spell-schema preflight. `FormalSpellDefinition` хранит книжные CV/Target/Range/Duration; `SpellTargetPreflightRequest` проверяет соответствие Rule ID/Lore/CV и различает неверный subject type, внешний out-of-range факт и готовое исполнение. Первый конкретный definition — `Curse of Cowardly Flight` (`3/Zone/Long/Instant`). Subject ID и affected targets разделены: валидная Zone может не содержать врагов, поэтому пустой batch допустим. Spatial layer всё ещё выбирает Zone/существ и вычисляет дальность.

Spell Potency является отдельной target-scoped фазой между preflight и эффектом заклинания. `SpellPotencyRequest` не выполняет Casting и не знает конкретных типов spell effects: он применяет числовые модификаторы к уже определённой Potency и при нуле закрывает дальнейшую ветвь для данной цели. `SpellCastExecutionRequest` добавляет над ним узкую batch-границу: принимает уже выбранные уникальные affected targets в стабильном порядке, независимо разрешает Potency каждой, сохраняет результат заблокированной цели, но создаёт `SpellEffectApplicationRequest` только для положительной effective Potency. Общий effect request переносит cast/caster/spell/lore/target/Potency до конкретного reducer и не является языком правил. Так Magic Resistance и Stone Troll переиспользуют один reducer, а конкретные заклинания получают только effective Potency. Временная target-local семантика multi-target заклинаний отмечена как `AMBIGUITY-002`.

NPC Wizard opposition пока является post-Test фазой. Пространственный/round orchestration решает, объявлена ли добровольная Reaction, и передаёт дальность, использованный budget и уже завершённый `OpposedTestResult`. Reducer не перебрасывает Casting/Willpower заново: он проверяет принадлежность двух Test IDs, фиксирует расход round budget и преобразует девятки реагирующего мага в typed `MiscastPoolIncreaseRequest`. Это отделяет обнаружение Rule of Nine от последующего применения к `WizardMagicState`; некорректный trace с переброшенной исходной девяткой отклоняется на границе.

Round/turn orchestration располагается над kernel. `CombatRoundState` хранит только участников, стороны, порядок и ход; `CombatTurnState` — actor и максимум два проверенных action slots. Slot declaration типизирует шесть книжных действий, варианты Manoeuvre и источник Improvise, но не содержит исполняемый `KernelAttackRequest`, casting state или spatial mutation. Отдельный `turn_resolution` проверяет стандартный/дополнительный слот, provenance Fate/Ability, запрет повтора и второй атаки.

Free move остаётся incidental spatial-фазой над этим состоянием, а не скрытым action slot. `FreeMovementRequest` принимает неизменённый `CombatRoundState` только для доказательства active actor/round и отдельно мутирует `SpatialBattleState`: маршрут содержит одну Zone для Slow/Normal либо до двух для Fast. Альтернативный `FreeMoveProneRemovalRequest` сохраняет placements и снимает только Prone с self либо явно близкого ally при отсутствии врага Close. Обе ветви записывают actor в общий usage, хранящийся отдельно от Give Ground до перехода spatial round. Difficult Terrain закрывается до появления требуемой Athletics-фазы.

Базовый Run соединяет эти два orchestration-среза явно. `RunActionExecutionRequest` принимает зарезервированный Run slot, active actor/round, speed/conditions и отдельный spatial snapshot. Resolver запрещает Slow/Burdened и общие movement blockers, проверяет одну соседнюю Zone и локальный path context, сначала создаёт новое размещение, затем добавляет receipt ровно к выбранному slot. Free-move usage не меняется.

Optional Athletics для второй extra Zone является отдельной post-movement фазой над подлинным `RunActionExecutionResult`. Она принимает типизированный Athletics `TestRequest`, current Conditions и второй path snapshot; все blockers проверяются до общего `resolve_test`. Успех меняет только placement actor, провал применяет обычный source-aware Staggered без repeated-Stagger escalation. Difficult Terrain Test в том же turn передаётся явным конфликтующим фактом. Фаза сохраняет base receipt вместо создания нового.

Общий `DifficultTerrainTraversalRequest` закрывает само пересечение одной Zone boundary отдельно от free-move/action bookkeeping. Resolver проверяет active actor, adjacency и path, создаёт новое placement и round-scoped `difficult_terrain_tested_entity_ids` до броска, затем вызывает общий Athletics Test. Провал применяет Prone после crossing и не откатывает movement; success не меняет Conditions. Result сохраняет исходный request и проверяемые path facts. Этот подтверждённый spatial usage, а не вызывающий boolean, блокирует optional Run и Long Charge Athletics в том же turn.

Terrain-aware free move и базовый Run являются consumers готового result. Их composite requests требуют равенства исходных round/spatial/Condition/path snapshots и отдельного current snapshot, равного crossed state; Run дополнительно требует прежний unexecuted slot. Consumers не вызывают RNG: free move добавляет usage, Run — receipt, а Conditions берутся из traversal, включая Prone после failure. Это защищает от подмены и применения к уже продвинутому aggregate snapshot, не вводя mutable registry внутрь pure rules.

Базовый Medium Charge использует отдельный composite request, поскольку одновременно затрагивает turn, spatial и attack kernel. Соседство Zone actor/вражеской цели доказывает Medium Range; внешний boolean подтверждает достижение локального Close Range внутри destination Zone и отдельно сохраняется факт enemy Close в начале turn. Прямой resolver проверяет movement blockers и path до RNG, создаёт новый spatial snapshot, подготавливает вложенный Attack и только после полного kernel result добавляет receipt Charge slot. Для `Skill.MELEE` в attacker `TestRequest` добавляется ровно один source-aware `+1d`; исходный request и подготовленная копия оба входят в результат. Не-Melee атака остаётся неизменной по временной политике `AMBIGUITY-007`.

Terrain-aware Medium Charge является consumer готового `DifficultTerrainTraversalResult`. Его request доказывает совпадение исходного Charge с traversal source и равенство current state crossed snapshot, а result сохраняет Conditions после Test. Spatial state больше не мутируется, но kernel attack и receipt выполняются в той же атомарной границе. Prone после failure не создаёт штраф атакующему: нормативный Condition такого эффекта не имеет; stale post-terrain Staggered и весь подготовленный Test context остаются проверяемыми.

Move Carefully использует отдельный composite над `FreeMovementRequest`, а не специальную разновидность Difficult Terrain Test. Request обязан нести terrain-route fact, active reserved slot и синхронные round/spatial snapshots. Reducer применяет обычные Speed/path/blocker ограничения, переносит actor и расходует тот же free-move usage, но сохраняет `difficult_terrain_tested_entity_ids`; затем исполняет явную optional Awareness ветвь и добавляет receipt. `DECLINE` не требует RNG, `SEARCH` делегирует одному общему `TestRequest`, поэтому бросковая механика не дублируется. Result связывает movement, optional Test trace и slot transition в одной проверяемой границе.

Move Quietly является отдельным composite над общим `OpposedTestRequest` и явным hiding choice. Стабильный snapshot наблюдателей содержит внешний `vigilance_priority`, поскольку книга не определяет формулу сравнения бдительности; kernel выбирает максимум со стабильным tie-order и проверяет, что opponent Test принадлежит выбранному Awareness. Route-вариант предварительно валидирует условный `FreeMovementRequest`, а same-Zone вариант способен потратить usage без вымышленного пересечения Zone. Оба применяются только при победе initiator и явных cover/hiding-position facts. Failure и decline оставляют spatial state неизменным, но завершают action slot. Hidden branch создаёт узкий one-next-unopposed-attack follow-up; его потребление и сброс после Attack принадлежат следующему adapter, а не глобальной event-шине.

Long Charge остаётся отдельным composite request, а не post-фазой Medium Charge: его неуспешная Athletics-ветвь тоже перемещает actor, применяет Staggered и завершает slot, но не имеет attack result. Двухзвенный маршрут доказывает Long Range и фиксирует промежуточную Zone. После общего `resolve_test` success перемещает actor к цели и вызывает тот же kernel с той же Melee-only подготовкой; failure перемещает только в intermediate Zone, применяет общий Condition reducer и создаёт receipt без вызова kernel. Полный Athletics trace и optional attack входят в закрытый result outcome, поэтому отсутствие атаки нельзя подменить пустым kernel result.

`attack_action_execution` принимает уже зарезервированный обычный Attack slot и готовый `KernelAttackRequest`. До RNG он проверяет active actor, индекс, вид, отсутствие execution receipt и завершённость всех более ранних slots; затем вызывает неизменённый `resolve_kernel_attack` и добавляет receipt, связывающий execution ID с request/result ID kernel. Специализированный результат хранит выбранный target ID, turn state до/после и полный `ResolutionResult`; только slot receipt меняется внутри round state. `Charge` намеренно отклоняется, поскольку сначала требует Manoeuvre/spatial execution.

`casting_action_execution` повторяет ту же границу для одного spell Improvise и готового `CastingTestRequest`. Он дополнительно требует `ImproviseKind.SPELL`, совпадение approach ID с Lore и caster с active actor, вызывает существующий `resolve_casting_test` и сохраняет полный `CastingTestResult`. Receipt означает завершение только этого action/Casting Test.

Отдельный `CastingActionPostTestRequest` связывает execution result с Wizard Level и существующими reducers. Он проверяет provenance финальных девяток, применяет не более одного агрегированного `MiscastPoolIncreaseRequest` и при безопасном пороге требует явный `CastingDecisionRequest` того же actor/level/post-pool state. При сработавшем Miscast normal decision отсутствует и активный Casting snapshot сохраняется.

`CastingActionMiscastPreparationRequest` принимает только triggered post-Test result и точный `MiscastPreparationRequest` от его base roll/state. Adapter переиспользует `prepare_miscast`, проверяет actor/source/state и сохраняет книжный порядок: optional `SpellCastRequest`, затем обязательный `MiscastRollRequest`; spell добавляет ровно один bonus die. Исполнение этих follow-ups, target и effect остаются следующими фазами. Остальные action kinds подключаются такими же узкими адаптерами; универсальный action dispatcher или event bus не вводится.

Первый interrupted-Casting adapter принимает завершённый обычный Attack и отдельный актуальный magic state того же actor. `MiscastPoolIncreaseRequest` теперь имеет закрытый provenance `TEST` либо `ACTION` и единый `source_id`: Rule of Nine сохраняет Test ID, skipped Casting ссылается на Attack execution ID. Resolver добавляет ровно один die и переиспользует общий threshold без мутации round/injury state. Защита от повторного воспроизведения одного receipt принадлежит будущему battle aggregate, который будет хранить исполненные follow-up.

Добровольное прекращение Casting не резервирует и не исполняет action slot. Отдельный `CastingAbandonmentRequest` принимает актуальный magic snapshot: непустой Miscast Pool переиспользует общую preparation-фазу с optional spell → roll, а пустой пул только очищает Casting snapshot без вымышленного броска. Уже triggered pool отклоняется, чтобы один и тот же Miscast не получил второй путь подготовки.

Rule of Nine влияет на Test до броска через узкий `RerollLock`: общий resolver убирает заблокированные значения из Grim/Glorious eligibility, не вводя отдельную копию бросковой механики для магии. Post-Test проверка trace сохраняется как инвариант принимающей границы.

Miscast разделён на чистые фазы `pool increase → preparation → roll → table effect`. `WizardMagicState` хранит Miscast dice и полный активный Casting snapshot, тогда как `wizard_level` передаётся отдельно как характеристика определения мага. Применение increase оставляет `state.miscast_dice > wizard_level`, поэтому повторное увеличение до разрешения Miscast отклоняется. Preparation очищает successes, Lore и latest-roll snapshot и, если выбранное доступное заклинание сотворяется перед Miscast, упорядочивает общий `SpellCastRequest` перед броском и добавляет к нему один bonus die. Roll использует внедряемый RNG, выбирает типизированную строку исправленной таблицы и создаёт `MiscastTableEffectRequest`. Пул сохраняется до фактического результата отдельного effect reducer.

Каждая строка таблицы имеет отдельный reducer без общего интерпретатора. `Sense of Loss` возвращает мгновенный ordered Medium Range narrative effect без inventory mutation; `Nauseating Wave` возвращает мгновенный ordered Short Range narrative effect без дополнительных mechanics; `Objects Transfigured` бросает `1d10` и возвращает Short Range random-object spatial/inventory follow-up; `Shadow Chittering` хранит caster-scoped auditory effect до Mannslieb full без числового penalty; `Food Spoiled` возвращает Long Range spatial/inventory follow-up с явным разделением fresh/preserved food; `Arcane Spill` делегирует общему Stagger impact и возвращает typed minor-Lore follow-up; `Hideous Stench` создаёт индивидуальные Give Ground/next-Test follow-ups и отдельный caster-scoped Fellowship effect; `Unnatural Weather` возвращает GM-owned локальный narrative effect без вымышленных area/duration/mechanical defaults; `Random Transport` выбирает внешний stable Zone option и возвращает relocation follow-up; `Sunlight Blindness` хранит caster-scoped illumination policy до downtime; `Unnatural Wind` применяет Prone к уже выбранным целям и явно исключает Monstrosity; `Spell Recast` выбирает один внешний recent-spell option и возвращает GM-targeted Potency 1 follow-up; `Truthbound` создаёт caster-scoped ограничение речи до downtime; `Arcane Sight` хранит лунный perception state и context-aware Test modifier; `Feared Foe Illusion` хранит внешний appearance reference и battle/minute duration; `Internal Damage` делегирует character/profile injury policy; `Zone Hazard` создаёт battle-scoped общий Zone Hazard с индивидуальным выбором Endurance/Athletics; `Ears ringing` исполняет уже выбранные разные цели в стабильном порядке; `Daemon Rift` возвращает GM-owned запрос манифестации без создания NPC; `Fascinating Rift` исполняет уже выбранных свидетелей через psychological preflight и общий Test resolver; `Catastrophic Death` применяет безусловный terminal state. `WoundRecordOrigin.FIXED_ENTRY` отличает названную книгой Wound от результата броска и запрещает сохранять синтетические dice values. После полного структурного разрешения строки reducer обнуляет Miscast Pool.

Для `Hideous Stench` spatial orchestration фиксирует цели и доступность Give Ground на момент броска, но не принимает решения за них. Reducer сохраняет входной порядок, обращается к `DecisionOwner.TARGET` только при двух допустимых исходах и возвращает movement либо one-shot modifier follow-up. Длительный Grim Fellowship мага хранится отдельным запросом до появления общего effect-state с событием купания; он не маскируется Condition и не превращается в постоянный modifier всех Tests.

`Spell Recast` отделяет случайный выбор заклинания от выбора его новой цели. Casting orchestration формирует стабильный непустой набор `MiscastRecentSpellOption` с уникальными option IDs; spell Rule ID могут повторяться, если внешняя policy сознательно представляет несколько вариантов одним заклинанием. Reducer выбирает индекс через общий RNG и создаёт follow-up с `DecisionOwner.GM`, но не исполняет неизвестную схему spell effect. Пустой snapshot отклоняется до очистки пула как требующий ruling крайний случай.

`Truthbound` не является Condition и не меняет результаты Test непосредственно. Reducer возвращает `MiscastTruthboundUntilDowntimeRequest`, а будущий campaign/effect state регистрирует и снимает его на границе следующего downtime. Проверка конкретной реплики и субъективного знания мага остаётся вне механического kernel.

`Arcane Sight` также хранится вне Condition state. `MiscastArcaneSightUntilMorrsliebFullRequest` задаёт источник и срок, а `MiscastArcaneSightTestContext` заставляет orchestration явно отличить затронутую обычную Awareness от обнаружения магического явления. Только после такой классификации helper создаёт `QualityModifier`; календарь Morrslieb и решение, входит ли обычная Test в книжное `most`, остаются внешними.

`Feared Foe Illusion` не создаёт combat profile и не меняет identity мага: это внешний appearance effect. `MiscastFearedFoeIllusionRequest` требует narrative reference и текущий battle context. Reducer преобразует его либо в `UNTIL_BATTLE_END`, либо в `MINUTES`; out-of-battle значение выбирает GM, поскольку книга не даёт точного числа. Регистрация appearance и истечение времени остаются в battle/campaign state.

`Daemon Rift` также не создаёт сущность внутри rules-kernel. `MiscastDaemonManifestationRequest` сохраняет мага как источник разрыва и отдельно маркирует GM-владение выбором природы, stat block, точного размещения и начального курса. Враждебность к магу и его союзникам, варианты beguile/corrupt/destroy, возможность немедленного действия либо ухода для подготовки и оба события возврата в Realm of Chaos являются неизменяемой частью контракта. Внешний battle/campaign слой выбирает и регистрирует профиль, создаёт сущность, планирует немедленное действие или бегство и отслеживает lifecycle.

`Fascinating Rift` получает уже выбранный GM `zone_id` и стабильный снимок разных свидетелей с уникальными Test IDs. `MiscastFascinatingRiftPortal` фиксирует Long Range и два исчерпывающих события закрытия; spatial-поиск Zone и определение факта наблюдения остаются снаружи kernel. Каждый свидетель сначала проходит source-level `PSYCHOLOGICAL` preflight, поэтому иммунная цель не расходует RNG. Для остальных reducer добавляет ровно `−1d` к переданному базовому Willpower Test и исполняет общий Test resolver слева направо. Провал не маскируется существующей Condition: отдельный compulsion follow-up связывает цель с порталом, требует попытки войти и явно различает физическое удержание от окончания эффекта. Battle/campaign state отвечает за движение, restraint и обработку close events.

`Sunlight Blindness` — ещё один внешний effect-state, но не психологический эффект и не `Blinded`. `MiscastSunlightBlindnessUntilDowntimeRequest` содержит исчерпывающую типизированную политику источников света: sunlight и другой natural light не обеспечивают видимость, тогда как torchlight, другой artificial light и arcane illumination доступны. Scene orchestration классифицирует фактический набор освещения и применяет книжное «as though it were the dead of night» при отсутствии доступного источника; kernel не анализирует описание сцены и не изобретает числовой penalty.

`Random Transport` отделяет построение spatial-множества от случайного выбора. Orchestration передаёт текущую Zone и стабильный непустой список уникальных доступных Zone ровно на Medium Range; текущая Zone отклоняется согласно определению Range на странице 114. Reducer выбирает равновероятный индекс через общий RNG и возвращает `MiscastRandomTransportRelocationRequest` с origin, destination и source Rule ID. Проверка проходимости, построение snapshot и фактическая мутация позиции остаются во внешнем spatial state.

`Unnatural Weather` отделяет нормативный факт изменения погоды от решений сцены, которых в таблице нет. Reducer привязывает `MiscastUnnaturalWeatherApplicationRequest` к магу и отдаёт выбор затронутой локальной области и конкретного явления GM. Два книжных описания сохраняются как примеры, а fixed-флаги контракта запрещают считать определёнными точный spatial radius, duration или механические последствия. Регистрация погоды и любые дальнейшие GM rulings принадлежат scene/campaign state.

`Food Spoiled` также не требует переносить inventory в rules-kernel. `MiscastFoodSpoilageApplicationRequest` задаёт caster anchor, Long Range и исчерпывающее разделение: `FRESH` портится, `PRESERVED` остаётся пригодной. Dried/salted/pickled представлены отдельными неисчерпывающими примерами сохранения, поэтому неизвестный способ консервации не становится свежей едой по умолчанию. Spatial/inventory orchestration находит все затронутые запасы и применяет изменение атомарно.

`Shadow Chittering` отделяет persistent perception state от расписания повествовательных событий. `MiscastShadowChitteringUntilMannsliebFullRequest` фиксирует мага как recurring listener, nearby shadow как источник и frequent/entirely unpredictable recurrence. Calendar/effect state снимает эффект при следующем полнолунии Mannslieb и при необходимости планирует звуковые эпизоды; отсутствие книжного механического последствия не позволяет kernel автоматически назначать Condition, modifier или случайный интервал.

`Objects Transfigured` разделяет три источника неопределённости. Reducer немедленно бросает только нормативный `1d10` и сохраняет результат как `object_count_roll`; follow-up требует случайного выбора именно такого числа малых объектов из внешнего stable Short Range snapshot. Конкретные виды различных малых существ принадлежат GM, а случайные направления — будущему spatial executor с тем же принципом внедряемого RNG. Недостаток подходящих объектов не имеет книжного fallback и остаётся явной policy, а не автоматическим сокращением числа.

`Nauseating Wave` не использует Condition state: фраза `there is no other effect` закрывает дальнейшую механическую ветвь. Spatial orchestration передаёт стабильный snapshot уникальных target IDs в Short Range, reducer сохраняет порядок и возвращает факт внезапной тошноты для всех целей. Пустой snapshot всё равно структурно разрешает строку и очищает Miscast Pool. Включение самого мага не выводится внутри kernel из неоднозначного `anyone within Short Range of you`.

`Sense of Loss` использует ту же границу multi-target snapshot, но с Medium Range. `MiscastSenseOfLossApplicationRequest` фиксирует ощущение внезапной потери и невозможность назвать якобы потерянное; `removes_inventory_items=False` не позволяет narrative wording превратиться в фактическое удаление имущества. Включение источника в `all those within Medium Range` остаётся частью общей spatial self-inclusion policy.

Обычная Troll Regeneration является явной end-turn операцией, а не реакцией на изменение счётчика Wounds. Request получает готовое состояние и минимальный provenance-контекст о наличии неогненной Wound. Только доступная добровольная ветвь вызывает `DecisionOwner.ACTOR`; выбранное лечение применяет Staggered через общий Condition reducer и возвращает новый профиль вместе с `ProfileStateChangeRequest`. Kernel не выбирает конкретную Wound и не определяет конец хода.

Reaction Monstrous Regeneration возвращает неизменённый injury state и `SuppressRegenerationNextTurnRequest`. Такой follow-up хранит Rule ID источника, но не добавляет временный флаг в `ProfileInjuryState`. Отдельный end-turn reducer получает готовый suppression-снимок: если он есть, возвращает его как однократно потреблённый до проверки Wounds; если нет — выполняет добровольную Regeneration через `DecisionOwner.ACTOR`, не запрещая лечение уже Staggered Monstrosity. Будущий turn orchestration отвечает только за привязку и перенос запроса между Reaction и ближайшим end-turn окном той же сущности.

Контекст исполнения Reaction является закрытым типизированным union, а не набором необязательных флагов общего назначения. Monstrous Flight получает собственный turn-scoped Give Ground context; Undead Monstrosity — mounted context с типом всадника и round-scoped доступностью Give Ground; Unsteady и Monstrous Regeneration отклоняют любой посторонний context.

Для Undead Monstrosity отсутствие mounted context означает обязательную профильную Wound. Liche или Tomb King открывает явный выбор владельца `MONSTROSITY` между доступными Wound, Give Ground и Prone. Resolver фильтрует невозможные пространственные/состоянийные варианты до обращения к decision policy, но не выбирает между несколькими легальными исходами самостоятельно.

Применение простого Condition выделено в `ConditionApplicationRequest → ConditionApplicationResult`. Запрос содержит состояние Conditions, Rule ID источника, явную `EffectClassification` и профильные `EffectImmunity`. Совпавшая иммунность оставляет состояние неизменным; результат отдельно хранит заблокированный source Rule ID, blocking Rule ID и фактически применённые Rule IDs. Классификация `UNCLASSIFIED` не совпадает с иммунитетом и не заменяет отсутствующие сведения догадкой по Condition.

`KernelAttackRequest` передаёт иммунитеты цели в replacement и secondary Condition-фазы. `ConditionImpactSpec` проверяется до прямого reducer или специальной Staggered policy. `ConditionOnHitSpec` и принятый `ConditionOnGiveGroundOrWoundSpec` вызывают тот же resolver после основного impact и сохраняют приложения в `ResolutionResult.condition_applications`.

Give Ground остаётся границей очереди: `ConditionAfterGiveGroundRequest` переносит classification и immunity snapshot, но применяет Condition только после движения. `StaggerImpactResult` и `MonstrosityReactionResolutionResult` хранят непосредственные outcome-приложения; blocked source не теряется, даже когда агрегированный trace содержит Rule ID иммунитета. Это не глобальная event-шина: каждый класс эффектов подключает нужный preflight и follow-up явно в своей фазе; уже подключённые non-Condition эффекты перечислены ниже.

Первый общий spatial reducer закрывает эту границу для Give Ground. `ZoneGraph` описывает только неориентированное соседство, а `SpatialBattleState` — размещения и round-scoped usage. `GiveGroundResolutionRequest` получает выбранную destination и минимальный снимок локального пути, поскольку окружение/препятствия внутри Zone нельзя вывести из графа. Resolver проверяет adjacency, направление от атакующего, Prone/Defenceless, повтор в round, enemy blockers, obstacle и Difficult Terrain, после чего возвращает состояния до/после точной мутации размещения. Несколько движений можно проверить как одну непрерывную immutable state chain. Broken при входе во вражескую Zone применяется общим Condition reducer после movement. Source-specific orchestration использует общий результат, но spatial слой не импортирует spell или attack executors.

Общая проверка `EffectApplicationRequest → EffectApplicationResult` теперь отделена от изменения Condition. Condition reducer использует её перед собственной мутацией, а Hazard — как source-level preflight до avoidance Test. Психологический Hazard при совпавшем иммунитете отменяется целиком; `Skill` и значение failure Condition классификацию не выводят. Kernel не создаёт `HazardExposureRequest` follow-up для заблокированного replacement impact, а Zone executor хранит blocked target без Test/Hazard result и без расхода RNG. Каждый non-Condition эффект требует отдельного явного подключения в своей фазе.

Первое такое подключение выполнено для `Curse of Cowardly Flight`. Target-scoped casting executor сохраняет selected Zone/caster/spell/Lore и создаёт `SpellEffectApplicationRequest`, после чего узкий `CowardlyFlightSpellEffectRequest` добавляет уже подготовленные movement/Test/injury/immunity snapshots и проверяет конкретный spell Rule ID. `CowardlyFlightZoneBatchRequest` требует точное взаимно-однозначное соответствие положительных effects и контекстов, восстанавливает порядок affected targets независимо от порядка contexts и корректно принимает пустую Zone. Один психологический preflight либо отменяет источник для конкретной цели целиком, либо выдаёт `GiveGroundRequest` и `CowardlyFlightWillpowerRequest`. Batch группирует их в отдельные очереди; target-tagged `CowardlyFlightMovementFollowUp` сохраняет адресата общего Give Ground без кодирования его в строковом ID. Общий spatial reducer исполняет movement, а узкий адаптер связывает успешный `GiveGroundResolutionResult` с `CowardlyFlightMovementCompletion`. Следующий batch восстанавливает target order, требует непрерывную цепочку всех movement transitions из selected Zone до переданного final spatial state и только затем исполняет Willpower Tests общим RNG.

`FoulStenchRequest` представляет уже произошедший вход Wyvern в Zone для одного затронутого врага; orchestration создаёт такие запросы для всех подходящих целей. Resolver получает только injury state и минимальный inventory context: наличие свободной руки и предмета, который можно отпустить. Бесплатное закрытие носа и вынужденный Distracted детерминированы; реальная развилка требует `DecisionOwner.TARGET`. Ветка предмета создаёт `DropHeldHandItemRequest`, не выбирая руку и не мутируя inventory, а ветка Condition использует общий reducer. Так spatial trigger, решение, Condition и будущая инвентарная мутация остаются отдельными фазами.
