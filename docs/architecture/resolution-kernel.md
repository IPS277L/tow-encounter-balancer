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

`ReactorZoneHazardResolutionRequest` обязан содержать реагирующего и уникальные target/Test IDs, но сохраняет переданный spatial-порядок. Executor создаёт по одной обычной экспозиции на цель и последовательно вызывает существующие `resolve_test` и `resolve_hazard` на общем RNG. Результат каждой цели хранит exposure, полный Test trace и Hazard result. Таким образом, multi-target orchestration не дублирует Test, Wounds Table, профильные injury policies, Near Miss или failure Conditions и по-прежнему не даёт kernel доступа к карте Zones.

Monstrous Regeneration возвращает неизменённый injury state и `SuppressRegenerationNextTurnRequest`. Такой follow-up хранит Rule ID источника и точный момент потребления, но не добавляет в `ProfileInjuryState` временный флаг, которым пока некому управлять. Будущий turn orchestration материализует запрет перед следующей end-turn регенерацией и удалит его после пропущенной возможности.

Контекст исполнения Reaction является закрытым типизированным union, а не набором необязательных флагов общего назначения. Monstrous Flight получает собственный turn-scoped Give Ground context; Undead Monstrosity — mounted context с типом всадника и round-scoped доступностью Give Ground; Unsteady и Monstrous Regeneration отклоняют любой посторонний context.

Для Undead Monstrosity отсутствие mounted context означает обязательную профильную Wound. Liche или Tomb King открывает явный выбор владельца `MONSTROSITY` между доступными Wound, Give Ground и Prone. Resolver фильтрует невозможные пространственные/состоянийные варианты до обращения к decision policy, но не выбирает между несколькими легальными исходами самостоятельно.
