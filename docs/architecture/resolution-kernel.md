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
- `SecondaryEffectSpec` — конкретное правило дополнительных целей, не общий AoE;
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

`DamageImpactSpec` проходит полный Damage/Resilience pipeline. `ConditionImpactSpec` не вычисляет Damage; Staggered передаётся существующей repeated-Stagger policy, остальные Conditions применяются непосредственно. `HazardImpactSpec` возвращает `HazardExposureRequest` с рейтингом и Skill — resolver фактического Hazard и выбор нескольких целей остаются следующими слоями. Damage с дополнительным Condition и уникальные профильные Reactions также ещё требуют secondary/named resolvers.
