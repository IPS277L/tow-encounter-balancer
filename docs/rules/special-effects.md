# Модификаторы и специальные эффекты

Основные источники: `BOOK-PLAYER-GUIDE`, страницы 31, 73–81, 92–97, 111–112, 124, 162; `BOOK-GM-GUIDE`, страницы 89–91 и профили NPC на страницах 92–185. Статус: фазовая модель, базовые replacement impacts и первые secondary effects `implemented`; полный каталог Talents, предметов и NPC остаётся `draft`.

## RULE-EFFECT-001 — эффект привязан к фазе

Специальные правила изменяют не «атаку вообще», а определённую фазу: допустимость действия, выбор профиля, пул, качество броска, сравнение успехов, Damage, Resilience, результат попадания, Staggered, Wound либо действие после результата. Порядок фаз является частью правила.

Примеры: Wild Attack накладывает Staggered до броска; Armour Bane снижает Resilience только после определения Wound; Near Miss применяется после броска Wounds Table; Troublemakers Out! накладывает Prone после фактического Give Ground.

В K1 `ConditionAfterGiveGroundSpec` подключается к общему Stagger impact. Только если repeated-Staggered завершился выбором Give Ground, reducer возвращает сначала `GiveGroundRequest`, затем `ConditionAfterGiveGroundRequest`. Condition не появляется в состоянии до исполнения второго follow-up. Так моделируются Prone от Troublemakers Out! (Player’s Guide, страница 31) и Broken от Fearsome (GM Guide, страницы 136, 145–146, 174 и 180). Staggered этим spec не маскируется, поскольку повторное состояние требует собственной decision/injury policy.

`ConditionOnHitSpec` разрешён только вместе с обычным `DamageImpactSpec`. На попадании сначала полностью разрешается Damage, Staggered/Wound и injury policy, затем Condition добавляется к итоговому состоянию. Поэтому Near Miss отменяет Wound, но не дополнительный Condition самого попадания. Этот вариант покрывает serrated maw Dragon (`Dam 7, hits inflict Drained`) и Venomous Tail Wyvern (`Dam 6, hits inflict Drained`) из GM Guide, страницы 177–178. Staggered запрещён и здесь: для него требуется repeated-Staggered policy; Prone с явно указанным порядком «before Give Ground» использует отдельный spec.

`ConditionOnGiveGroundOrWoundSpec` описывает Terrifying у Dragon и Wyvern (GM Guide, страницы 177–178). Broken ставится только после одного из двух подтверждённых исходов атаки: выбран Give Ground либо цель фактически приняла Wound. В первом случае общий Stagger reducer создаёт `GiveGroundRequest`, а затем `ConditionAfterGiveGroundRequest`; до исполнения перемещения состояние не меняется. Во втором Condition добавляется после завершения injury policy. Отменённая через Near Miss Wound, первый Staggered и выбор Fall Prone не являются триггерами.

## RULE-EFFECT-002 — модификаторы проверки

Свойства оружия, Talents, состояния, дистанция и контекст могут добавлять или убирать кубы, делать Test Grim/Glorious либо добавлять фиксированные успехи. После сбора модификаторов применяются предел пула и правило единственного куба из `RULE-TEST-003`, если эффект явно не разрешает превысить предел.

Источник: Player’s Guide, страницы 73–81, 93–96, 107–108; GM Guide, профили NPC.

## RULE-EFFECT-003 — изменение встречной проверки

Эффект может:

- разрешить или запретить конкретную защиту;
- добавить защитнику кубы;
- изменить владельца ничьей;
- сделать атаку unopposed;
- изменить число успехов после броска.

Поэтому выбор Protection и сравнение результатов являются отдельными фазами. Примеры включают Battlefield Musician, Deep Formation, Short Size, Lightning Reflexes и Dispeller.

Источник: Player’s Guide, страницы 73–80.

## RULE-EFFECT-004 — изменение Damage и Resilience

До сравнения Damage с Resilience применяются контекстные модификаторы базового Damage, коэффициента успехов и эффективного Resilience. Игнорирование брони действует только для текущей атаки. Постоянное повреждение брони, например Armour Bane или отдельные NPC-способности, применяется в указанной правилом фазе после определения результата текущей атаки.

Источник: Player’s Guide, страницы 73, 93–97, 119; GM Guide, страницы 91, 155, 167.

## RULE-EFFECT-005 — замена обычного результата атаки

Некоторые атаки не вычисляют обычный Damage или заменяют его результатом профиля: Staggered, Burdened, Ablaze, Hazard, принудительным перемещением, захватом либо иным состоянием. Такой профиль должен явно задавать способ разрешения, а не маскироваться числом Damage.

Источник: Player’s Guide, страницы 93, 95–96; GM Guide, профили NPC, в частности страницы 151 и 182.

В K1 `ImpactSpec` является закрытым типизированным объединением:

- `DamageImpactSpec` содержит Damage, Resilience, игнорирование брони и модификаторы обычного пути;
- `ConditionImpactSpec` наносит одно Condition вместо Damage;
- `HazardImpactSpec` создаёт экспозицию Hazard с рейтингом и названным Skill вместо Damage.

На промахе replacement impact не применяется. Прямой Staggered использует общий reducer повторного Staggered; остальные Conditions добавляются к состоянию цели. Hazard сначала создаёт `HazardExposureRequest`, поскольку профиль нужного Skill принадлежит orchestration, а затем отдельный resolver сравнивает Test с рейтингом и вызывает существующую injury policy. Damage плюс простой не-Staggered Condition представлен `ConditionOnHitSpec`; несколько целей, принудительное перемещение и разные последствия конкретных исходов не маскируются вариантами `ImpactSpec`.

## RULE-EFFECT-006 — дополнительные цели задаются эффектом

Универсального AoE нет. Каждый эффект отдельно определяет:

- условие срабатывания;
- множество затронутых целей;
- нужен ли каждой цели собственный Test;
- получает ли вторичная цель Damage, Condition или Hazard;
- порядок разрешения целей.

Примеры разных моделей: Blunderbuss, Oil Flask, Blasting Charge, Cleaving Blow, Monstrosity с несколькими отдельными атаками и профильные способности существ.

Источник: Player’s Guide, страницы 74, 95–96; GM Guide, страницы 90, 149, 177, 181–185.

В K1 реализованы пять узких вариантов `SecondaryEffectSpec`:

- `ProneBeforeGiveGroundSpec` на успешном попадании накладывает Prone до разрешения обычного Staggered. Поэтому уже Staggered цель не может после этого выбрать Give Ground или повторное Prone. Флаг `affects_monstrosities` выражает различие между Noble Steed, который исключает Monstrosity, и атаками без такого исключения. Источники: Player’s Guide, страница 124; GM Guide, страницы 106, 126, 136 и 174;
- `NearbyTargetsStaggerSpec` на попадании добавляет `NearbyTargetsStaggerRequest` после полного результата основной цели. Запрос означает всех других существ, которые находились в Close Range от основной цели в момент попадания. Источник свойства Blunderbuss: Player’s Guide, страница 95;
- `ConditionAfterGiveGroundSpec` добавляет не-Staggered Condition только после выбранного Give Ground; он работает через общий `StaggerImpactRequest` и поэтому может сопровождать как основную, так и уже выбранную вторичную цель;
- `ConditionOnHitSpec` сохраняет обычный Damage pipeline и после его результата добавляет простой Condition к основной цели;
- `ConditionOnGiveGroundOrWoundSpec` после Give Ground ставит отложенный Condition follow-up, а после фактически принятой Wound добавляет Condition к итоговому состоянию. Общий `StaggerImpactRequest` поддерживает это правило и для уже выбранной вторичной цели.

Kernel не ищет существ по Zones. Spatial orchestration фиксирует подходящие цели в момент попадания и передаёт их как упорядоченный набор `IdentifiedStaggerTarget`. `resolve_nearby_targets_stagger` отклоняет основную или повторную цель и слева направо применяет к каждой общий `StaggerImpactRequest`: первое/повторное Staggered, Give Ground, Prone, Wound, нужную injury policy и Wound follow-ups. Состояния и результаты остаются привязаны к `target_id`; RNG и decision provider используются последовательно в том же порядке.

Если вторичная цель — Monstrosity, прямой Staggered разрешается общей condition/injury policy и сам по себе не предлагает Reaction: специальный выбор Monstrosity относится к Damage, а Blunderbuss вторичным целям Damage не наносит. Остальные свойства Blunderbuss — диапазон, бонус кубов и reload — принадлежат своим фазам и этим spec не реализуются.

## RULE-EFFECT-007 — последующие действия не являются частью броска

Некоторые Talents и Abilities создают бесплатную, немедленную или вторую атаку либо иное действие после события. Исходная проверка должна завершиться полностью, после чего движок ставит явно описанный follow-up в очередь. Follow-up проходит тот же resolution pipeline как самостоятельное действие и может иметь собственные ограничения.

Примеры: Bash Attack, Fight As One, Interceptor, Quick Throw, Rapid Reload, Stand and Shoot и профильные NPC-способности.

Источник: Player’s Guide, страницы 73, 76–80; GM Guide, страницы 90, 136, 173, 178.

## RULE-EFFECT-008 — Wound имеет отдельные вмешательства

Эффект может изменить число кубов Wounds Table, заменить Wound, отменить его или преобразовать модификатор таблицы в дополнительные Wounds для Brute/Monstrosity. Бросок таблицы и окончательное принятие Wound поэтому являются отдельными фазами.

Примеры: Hardy, Familiar, Near Miss, Blessings of the Lady, оружие с `+1d on Wounds Table` и модели Brute/Monstrosity.

Источник: Player’s Guide, страницы 74–76, 95, 111–112, 121; GM Guide, страницы 89–90.

## RULE-EFFECT-009 — решения принадлежат участникам

Когда правило говорит «may» или предлагает несколько исходов, kernel не выбирает сам. Он создаёт типизированный запрос решения с допустимыми вариантами и владельцем решения. Для массовой симуляции этот порт реализуется детерминированной policy.

Это требуется как минимум для Fate, повторного Staggered, Defensive Stance, Monstrosity Reaction/Wound и некоторых дополнительных действий.

Foul Stench Wyvern добавляет `DecisionOwner.TARGET`: если у цели нет свободной руки, но есть удерживаемый предмет, она сама выбирает между `DropHeldHandItemRequest` и Distracted. При единственном допустимом исходе decision provider не вызывается.

Добровольная end-turn Regeneration обычного Troll использует `DecisionOwner.ACTOR`: решение принадлежит контроллеру существа, чей ход завершается. Provider вызывается только если Troll не Staggered, имеет Wounds и хотя бы одну допустимую неогненную Wound. Выбор Regenerate сначала применяет source-aware Staggered, затем уменьшает профильные Wounds и создаёт `ProfileStateChangeRequest`; Skip и недоступные ветви состояния не меняют.

Выбор `Wound/Reaction` и исполнение выбранной Reaction являются разными фазами. Для Monstrous Flight kernel сначала возвращает `MonstrosityReactionRequest`; отдельный resolver получает актуальное состояние Monstrosity и сведения о Give Ground в текущем ходу. Результат содержит фактический исход `GIVE_GROUND` или `SUFFER_WOUND`, новое состояние, follow-ups и применённые Rule ID. Так secondary effect вроде Terrifying реагирует на результат Reaction, не заставляя kernel рекурсивно исполнять очередь.

Тот же контракт принимает `UnsteadyReactionSpec`, но не требует Give Ground context. Он различает новое падение и уже имеющийся Prone. Только новое падение создаёт `ReactorZoneHazardRequest` для последующего spatial-выбора всех существ в Zone; это не универсальное событие «Condition изменился», а прямое следствие конкретной профильной Ability Giant. После выбора целей отдельный executor проверяет наличие реагирующего, уникальность IDs и последовательно проводит каждую цель через общие Test/Hazard resolvers.

`MonstrousRegenerationReactionSpec` также не требует пространственного контекста. Reaction не лечит и не меняет состояние немедленно: resolver создаёт `SuppressRegenerationNextTurnRequest` с Rule ID способности. Внешний turn orchestration сохраняет его до ближайшего end-turn окна той же сущности и передаёт в `MonstrousRegenerationEndTurnRequest`. End-turn resolver потребляет такой запрос ровно один раз до проверки доступных Wounds и не обращается к decision policy. Без suppression допустимое лечение требует выбора Actor, уменьшает профильные Wounds на 1 и применяет Staggered только если его ещё нет; уже имеющийся Staggered не запрещает Monstrous Regeneration. Временный запрет не моделируется Condition или универсальным cooldown.

`UndeadMonstrosityReactionSpec` разделяет немонтированную и mounted-ветви типизированным контекстом. Без Liche/Tomb King Bone Dragon автоматически получает профильную Wound. При допустимом всаднике `DecisionProvider` получает владельца `MONSTROSITY` и только доступные варианты Wound/Give Ground/Prone. Недоступное перемещение, уже выполненный в раунде Give Ground и уже имеющийся Prone исключают соответствующие варианты до вызова policy. Фактические Give Ground и Wound проходят общие обработчики, поэтому условные эффекты вроде Terrifying сохраняют тот же порядок и семантику.

Иммунитет проверяется по явной классификации источника эффекта. `EffectClassification.PSYCHOLOGICAL` не выводится автоматически из Broken, Staggered или другого значения Condition. `EffectImmunity` принадлежит профилю цели и содержит Rule ID Ability. Общий resolver применения Condition при блокировке сохраняет Rule ID источника отдельно от Rule ID применённого иммунитета; неклассифицированное воздействие проходит без предположений.

Этот контракт используется `ConditionImpactSpec`, `ConditionOnHitSpec`, `ConditionOnGiveGroundOrWoundSpec` и `ConditionAfterGiveGroundSpec`. Непосредственные фазы добавляют полный `ConditionApplicationResult` в результат resolution. Отложенная фаза копирует классификацию и иммунитеты в `ConditionAfterGiveGroundRequest`, а её resolver возвращает приложение вместе с обновлённым либо неизменённым состоянием. Поэтому movement/Wound остаются совершившимися даже при блокировке последующего Fearsome/Terrifying Condition.

Для составного психологического источника граница может находиться раньше отдельных последствий. `Curse of Cowardly Flight` (Player’s Guide, страница 162) сначала проходит один source-level preflight, который при блокировке отменяет и forced Give Ground, и Willpower Test с возможным Broken. При отсутствии блокировки resolver выдаёт movement и Test как два упорядоченных follow-up. Это узкий контракт конкретного заклинания, а не универсальная шина принуждения.

## RULE-EFFECT-010 — профильная способность может быть уникальной

Книжные NPC содержат как повторяющиеся модификаторы, так и уникальные правила: ограничения целей, проглатывание, регенерацию, случайный выбор атаки, изменение состояния поля и Reactions. Общие случаи представляются типизированными эффектами; действительно уникальное правило допускается как отдельный именованный resolver с Rule ID. Строки описания из PDF не исполняются как код.

Источник: GM Guide, страницы 92–185.
