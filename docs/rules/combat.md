# Бой и атаки

Источник: `BOOK-PLAYER-GUIDE`, преимущественно страницы 111–120. Статус: правила атаки, базовый порядок раунда, бюджет действий, обе фазы Run и обе дальности Charge `implemented` в K1; эффекты большинства остальных действий и завершение боя ещё требуют нового battle loop.

## RULE-COMBAT-001 — раунды, стороны и ходы

Каждый участник получает один ход в каждом раунде. По умолчанию сначала действует сторона игроков и союзников, затем противники. Порядок участников внутри своей стороны выбирается заново каждый раунд; один участник полностью завершает ход до начала следующего.

Источник: страница 112.

## RULE-COMBAT-002 — основная экономика действий

Обычно участник выполняет одно боевое действие за ход и допустимые incidental actions, включая одно бесплатное перемещение. Fate или способности могут дать второе действие, но действий не может быть больше двух. Одно и то же действие нельзя повторять, а второй action не может создавать вторую атаку: поэтому Charge и обычный Attack нельзя совместить в одном ходу. GM может разрешить два разных Improvise, если они используют разные подходы.

Источник: страницы 111, 112, 116.

## RULE-COMBAT-003 — засада

При успешной засаде противники действуют первыми, и этот порядок сохраняется. В первом раунде застигнутые врасплох участники не могут Oppose атаки. Awareness и подходящие Lores могут предотвратить этот эффект.

Источник: страница 112.

## RULE-COMBAT-004 — действия

Базовый список включает Aim, Attack, Help, Improvise, Manoeuvre и Recover. Charge является вариантом Manoeuvre и включает перемещение с последующей атакой.

Источник: страницы 116–118.

Подробности:

- Aim — Awareness Test; каждый success даёт `+1d` следующей ranged attack по выбранной цели, если между ними не было другого action;
- Help использует общее правило и даёт по `+1d` за success;
- Manoeuvre выбирает Run, Charge, Move Quietly или Move Carefully;
- Improvise применяет подходящий Skill/spell/Ability, но только defeat или Defenceless гарантированно нейтрализует threat;
- Recover снимает Staggered/Prone, уменьшает Miscast Pool на один die и позволяет взаимодействовать с предметом рядом с врагом; вместо всех этих выгод можно Treat Wound либо Test снятие condition.

### Реализация порядка хода и action budget в K1

`CombatRoundState` хранит номер раунда, снимок участников двух сторон, постоянный порядок сторон, завершивших ход участников и не более одного активного `CombatTurnState`. Внутри текущей стороны actor выбирается внешней policy в любом порядке; следующая сторона открывается только после завершения всех ходов текущей. При переходе раунда orchestration передаёт новый снимок допущенных участников, а порядок сторон сохраняется, включая перевёрнутый порядок после засады.

`reserve_combat_action_slot` только проверяет и резервирует `CombatActionSlot`: первый слот обычный, второй обязан ссылаться на Fate либо конкретный Rule ID способности, третьего слота нет. Резолвер не расходует Fate и сам не исполняет Aim/Attack/Help/Improvise/Manoeuvre/Recover. `CombatActionDeclaration.produces_attack` учитывает обычный Attack, Charge и явно помеченный атакующий Improvise, поэтому скрытая вторая атака отклоняется независимо от формы действия. `ImproviseKind` явно различает Skill, spell и Ability; два Improvise требуют явного `allows_second_improvise` от GM policy и разных stable approach ID.

Первый специализированный executor подключает `CombatActionKind.ATTACK`. `AttackActionExecutionRequest` связывает active actor, конкретный зарезервированный slot, явно выбранный target ID и готовый `KernelAttackRequest`. После полного `resolve_kernel_attack` slot получает неизменяемый `ActionExecutionReceipt`, а `AttackActionExecutionResult` возвращает round state до/после и вложенный `ResolutionResult`. Не-ATTACK, Charge, чужой/несуществующий, уже исполненный slot либо slot перед незавершённым более ранним действием отклоняются до RNG. Выбор цели, перенос `target_state` в будущий общий battle state и расход Fate остаются внешними фазами.

Второй узкий executor подключает только `ImproviseKind.SPELL`. Stable approach ID такого slot обязан совпадать с объявленным Lore в `CastingTestRequest`; caster обязан быть active actor. `execute_casting_attempt` выполняет ровно один Casting Test и только после его успеха добавляет receipt, возвращая полный `CastingTestResult`. Следующая `resolve_casting_action_post_test` сначала применяет его Rule of Nine follow-up к Miscast Pool. При безопасном пороге она требует явный связанный `CastingDecisionRequest` и выполняет normal `CAST`/`WAIT`; при сработавшем Miscast normal decision запрещён. `prepare_casting_action_miscast` связывает triggered result с готовым `MiscastPreparationRequest`: без spell создаётся один roll, а выбранный допустимый spell строго предшествует roll и добавляет `+1d`. Target discovery, spell/table effect и сам Miscast roll не выполняются автоматически.

Третий специализированный executor подключает базовую ветвь `ManoeuvreKind.RUN`. `RunActionExecutionRequest` связывает active actor/round, зарезервированный Run slot и отдельный `SpatialBattleState`. Slow, Burdened, Prone и Defenceless отклоняются; Normal/Fast перемещаются ровно в одну соседнюю Zone. Enemy path blocker, obstacle и Difficult Terrain также требуют внешней либо отдельной фазы. Сначала создаётся новый spatial snapshot, и лишь затем выбранный slot получает `ActionExecutionReceipt`; при ошибке оба исходных состояния остаются неизменными. Ход нельзя завершить, пока зарезервированный обычный Attack, Run, Charge, Move Carefully или spell Improvise не исполнен.

Четвёртый executor подключает базовый Charge по цели на Medium Range. `ChargeActionExecutionRequest` связывает зарезервированный Charge slot, active actor/round, вражеский target, movement context и готовый `KernelAttackRequest`. Zone adjacency доказывает Medium Range; попадание в Close Range после входа в Zone цели остаётся отдельным локальным фактом. Slow/Burdened/Prone/Defenceless, враг Close в начале хода, obstacle и enemy path blocker закрывают действие до RNG. Прямой executor отклоняет Difficult Terrain, а terrain-aware composite принимает готовое пересечение. После spatial mutation либо принятия crossed state выполняется ровно одна Close Range attack, и только после её результата slot получает receipt.

Для `Skill.MELEE` executor добавляет к attacker Test один обычный `DiceModifier(+1d)` с Rule ID Charge. Другие Attack Skills бонус не получают; временная политика для неоднозначного Brawn описана в `docs/contradictions.md`. Исходная и подготовленная `KernelAttackRequest` сохраняются в результате, поэтому бонус нельзя добавить дважды или скрыть в исходном запросе. Ход нельзя завершить с неисполненным Charge.

Пятый executor подключает попытку Charge по цели ровно на Long Range. `LongChargeActionExecutionRequest` принимает тот же зарезервированный slot, готовые Athletics Test и Close attack, а также промежуточную Zone двухзвенного маршрута. Соседство `origin → intermediate → target` при отсутствии прямой связи доказывает Long Range. Все movement/path/Condition проверки и конфликт с Athletics Test для Difficult Terrain того же turn выполняются до RNG.

При успехе Athletics actor входит в Zone цели, достигает явно подтверждённого Close Range и выполняет attack с той же Melee-only политикой `+1d`. При провале actor всё равно перемещается в промежуточную Zone — ровно за одну Zone от цели, — attack не подготавливается и не выполняется, а Staggered добавляется только при его отсутствии. Обе ветви завершают исходный Charge slot одним receipt; result сохраняет Test trace, состояния до/после, Condition application и optional kernel result.

Если actor уже имеет активный Casting snapshot и вместо следующего Casting Test исполняет обычный Attack, `SkippedCastingTestAfterAttackRequest` связывает конкретный успешный `AttackActionExecutionResult` с актуальным `WizardMagicState`. Resolver создаёт source-aware увеличение пула ровно на один die и немедленно применяет общий Miscast threshold, не меняя Lore или накопленные successes. Повторное применение того же action result пока предотвращает будущий battle aggregate; добровольное прекращение Casting и другие виды действий остаются отдельными фазами.

## RULE-COMBAT-005 — выбор навыков атаки и защиты

- Melee используется с подходящим оружием ближнего боя.
- Shooting используется для стрелкового оружия.
- Throwing используется для метательного оружия.
- Brawn используется для безоружных атак.
- Осведомлённая цель обычно Oppose атаке через Athletics либо Defence, если снаряжение позволяет.
- Defence требует оружия или щита против Melee; против Shooting/Throwing Defence обычно требует щита.
- неосведомлённая или Defenceless цель не выполняет встречную защиту.

Источник: страницы 68, 92, 94, 117–118.

## RULE-COMBAT-006 — успех атаки

Атака успешна, когда атакующий получил не меньше успехов, чем защитник. Для unopposed атаки нужен хотя бы один успех, если специальное правило не говорит иначе.

Источник: страницы 109, 118.

## RULE-COMBAT-007 — промах

Промах атакой по врагу в Close Range накладывает на атакующего Staggered, только если этого состояния ещё нет. Повторный промах не усиливает уже имеющийся Staggered. Обычная дальняя атака не создаёт этот штраф; дальнее оружие при атаке в Close Range следует правилу ближнего промаха.

Источник: страницы 119 и 94.

## RULE-COMBAT-008 — урон

```text
Damage = base weapon Damage + attacker_successes - defender_successes
```

Для unopposed атаки вместо разницы добавляется общее число успехов атакующего. Базовый урон оружия может быть статическим или производным от Strength.

Источник: страница 119 и таблицы оружия на страницах 93, 95–96.

## RULE-COMBAT-009 — модификаторы атаки

На пул влияют Charge, численное преимущество в Zone, высота, дистанция, укрытие, положение Prone, свойства оружия, Help, Wounds, Talents и другие Abilities. Модификаторы должны вычисляться из контекста действия, а не сохраняться как постоянное эффективное значение характеристики.

Источник: страницы 115, 118–119 и таблицы снаряжения.

## Реализация Attack/Impact в K1

- контракты: `src/towr/domain/attack_models.py`;
- чистое разрешение одной атаки: `src/towr/rules/attack_resolution.py`;
- детерминированные проверки: `tests/unit/test_k1_attack_resolution.py`.

Чистый Attack resolver поддерживает одну основную цель, opposed/unopposed атаку, книжный tie-break, обычный Damage, коэффициент успехов профильной атаки, эффективный Resilience, игнорирование брони и последствие промаха в Close Range. `resolve_kernel_attack` применяет к основной цели Staggered, Wound и replacement impact, исполняет фазовый `ProneBeforeGiveGroundSpec` и возвращает остальные действия типизированными follow-up. Поиск вторичных целей по Zones остаётся вне K1.

`execute_attack_action` является orchestration-адаптером над этим kernel и не дублирует правила атаки. Он обновляет только execution receipt выбранного action slot; состояние цели остаётся в типизированном `ResolutionResult` до появления общего battle aggregate.

## RULE-COMBAT-010 — завершение боя

Книга предусматривает поражение, недееспособность, сдачу и групповой Retreat. Для симулятора ещё требуется формальная политика определения исхода столкновения.

Источник: страницы 117, 120 и 191. Статус: `needs_clarification` для целей симуляции.

## RULE-COMBAT-011 — Zones и Ranges

Zone имеет контекстный размер/форму и следует естественным границам сцены. Position внутри Zone сохраняет значение для line of sight, cover, concealment, окружения и препятствий.

Ranges: Close — arm’s reach; Short — та же Zone; Medium — одна Zone; Long — две; Extreme — три и более. Эти определения являются graph/spatial input, а не фиксированными метрами.

Источник: страница 114.

## RULE-COMBAT-012 — Speed и ограничения движения

- Slow: free move до Medium, без Run/Charge/Move Quietly/Move Carefully;
- Normal: free move до Medium и доступ к Manoeuvre;
- Fast: free move до Long и доступ к Manoeuvre.

Burdened запрещает Manoeuvre, Prone — выход из Zone, Defenceless — любое движение. При длительной погоне более высокий Speed в итоге догоняет; при равенстве либо head start используется Opposed Athletics.

Источник: страница 115.

## RULE-COMBAT-013 — battlefield features

Cover/concealment даёт атакующему `-1d` Shooting. В темноте Long/Extreme не видны; attack по невидимой цели считается Blinded и Grim. Difficult Terrain требует Athletics при пересечении, провал роняет Prone после пересечения; Move Carefully и конкретный Lore обходят Test. В тот же turn нельзя также Athletics для дополнительной Zone Run/Charge.

Источник: страница 115.

## RULE-COMBAT-014 — free actions и Manoeuvre

Раз за turn даётся free move по Speed; вместо него без врага Close можно снять Prone с себя/союзника Close. К incidental actions относятся draw/swap, non-Test reload prep, добровольный Prone, короткая речь и простое взаимодействие Close; рядом с врагом взаимодействие требует Recover.

Run добавляет одну Zone и может добавить вторую успешной Athletics, провал впервые даёт Staggered. Charge достигает цели Medium, даёт Melee `+1d`; Long требует Athletics, провал останавливает за Zone, отменяет attack и впервые даёт Staggered. Charge запрещён при начале Close к врагу. Move Quietly — Stealth против наиболее vigilant Awareness и требует cover/concealment. Move Carefully игнорирует Difficult Terrain и может добавить Awareness search.

Источник: страницы 116–117.

### Реализация free movement в K1

`MovementSpeed` типизирует Slow, Normal и Fast. `FreeMovementRequest` связывает `SpatialBattleState` с активным actor из отдельного `CombatRoundState`, требует одинаковый номер round и принимает явный маршрут по Zone graph. Slow/Normal могут пересечь одну границу Zone (Medium Range), Fast — до двух (Long Range). Это incidental-фаза: action slot не резервируется и round state не мутируется.

После успешного перехода меняется только Zone actor и `free_move_used_entity_ids`. Список хранится до следующего spatial round: при текущей модели один actor получает один ход за round, поэтому он однозначно представляет книжный предел once per turn отдельно от `gave_ground_entity_ids`. Prone и Defenceless блокируют движение, Burdened не блокирует free move. Явно переданный enemy path blocker или obstacle отклоняет маршрут; союзник на пути не считается врагом.

Difficult Terrain имеет отдельную общую Athletics movement-фазу. Free move, базовый Run и Medium Charge принимают её готовый результат через отдельные composite adapters; прямые reducers по-прежнему закрывают terrain route. Текущий terrain-aware free move покрывает одну границу Zone: Fast-маршрут с несколькими terrain/non-terrain сегментами требует будущего route orchestration. Перемещение позиции внутри одной Zone не представимо одним `zone_id` и остаётся внешним spatial context.

`FreeMoveProneRemovalRequest` представляет книжную альтернативу тому же free move. `ProneRemovalTargetKind` явно различает `SELF` и `ALLY`; для союзника обязателен внешний Close Range fact, совпадение `side_id` и отличный от actor target ID. Отдельный `actor_has_enemy_in_close_range` нельзя выводить из общей Zone, поскольку Short и Close Range не совпадают. При наличии такого врага, отсутствии Prone или уже использованном free move reducer закрывается без изменений. Успех удаляет только Prone из переданного `ConditionState`, не меняет placements/action slots и записывает actor в общий `free_move_used_entity_ids`, поэтому после снятия Prone обычное движение уже недоступно и наоборот.

### Реализация базового Run в K1

`execute_run_action` требует уже зарезервированный Run slot и завершённость более раннего slot. Базовая дистанция не зависит от Normal/Fast и равна одной дополнительной соседней Zone; она не расходует и не восстанавливает отдельный free-move usage. Round и spatial snapshots имеют общий номер, а successful result меняет только placement actor и receipt выбранного slot.

Опциональный Athletics Test для второй дополнительной Zone выполняется отдельным `RunAthleticsExtensionRequest → RunAthleticsExtensionResult` после базового Run. Само наличие запроса означает добровольный выбор попытки; он принимает готовый `TestRequest`, вторую соседнюю destination и явный path context. Все spatial-проверки происходят до RNG. Успех перемещает actor ещё на одну Zone; провал оставляет placement прежним и добавляет Staggered только при отсутствии этого Condition. Уже имеющийся Staggered не превращается в repeated-Staggered choice.

Фаза не создаёт второй receipt и сохраняет free-move/Give Ground usage. Наличие actor в `SpatialBattleState.difficult_terrain_tested_entity_ids` запрещает попытку после Athletics Test для Difficult Terrain; вызывающая сторона больше не передаёт доверенный boolean. Сама extra Zone также не может одновременно пересекать Difficult Terrain. Регистрация уже выбранной optional-фазы и защита от повторного воспроизведения одного base result остаются ответственностью будущего battle aggregate.

Terrain-aware базовый Run разделён на фактическое пересечение и bookkeeping action slot. `DifficultTerrainRunActionExecutionRequest` требует точного совпадения исходных round/spatial snapshots, actor, Conditions, destination, path и obstacle с сохранённым source traversal, а current snapshots — с ещё неисполненным Run slot и crossed state. Затем adapter только добавляет receipt, не бросает Athletics повторно и не меняет spatial state. Провал terrain Athletics поэтому завершает Run уже в destination Zone и сохраняет Prone.

### Реализация Charge в K1

Medium и Long используют один Charge slot и одинаковую подготовку последующей атаки, но разные типизированные composite contracts. Medium требует одну границу Zone и всегда доходит до attack после preflight. Long требует ровно две границы и сначала выполняет Athletics: success доходит до цели и атакует, failure останавливается в промежуточной Zone, впервые применяет Staggered и завершает действие без attack. Ни одна ветвь не расходует и не восстанавливает free-move/Give Ground usage.

### Реализация Difficult Terrain в K1

`DifficultTerrainTraversalRequest → DifficultTerrainTraversalResult` представляет одно фактическое пересечение границы Zone через terrain. Request связывает active actor/round, исходный spatial snapshot, готовый Athletics `TestRequest`, Conditions, destination и локальный path context. Result сохраняет полный source request и дублирует проверяемые path/obstacle facts, чтобы следующий adapter мог доказать provenance. Prone/Defenceless, obstacle, enemy blocker и несоседняя Zone закрываются до RNG; Burdened не блокирует общий traversal, поскольку Difficult Terrain встречается и при free move.

Reducer сначала создаёт spatial snapshot после пересечения и записывает actor в `difficult_terrain_tested_entity_ids`, затем разрешает Athletics. Success сохраняет Conditions, failure немедленно добавляет Prone через общий Condition reducer, не отменяя movement. Повторное пересечение в том же turn требует новый Test, но не дублирует usage ID. `start_next_spatial_round` очищает usage вместе с Give Ground/free move. Optional Run и Long Charge читают этот авторитетный факт и закрываются до RNG.

`DifficultTerrainFreeMovementRequest` принимает только исходный free-move request с terrain flag, точно соответствующий сохранённому traversal source, и current spatial state, равный crossed state. Adapter добавляет лишь `free_move_used_entity_ids`; failed Athletics сохраняет движение и Prone. Аналогичный Run composite принимает ещё current round state и добавляет только action receipt. Подмена result или его применение к уже обновлённым snapshots отклоняется.

`DifficultTerrainChargeActionExecutionRequest` связывает тот же traversal с исходным Medium Charge. Он требует точного совпадения actor/round/origin/target destination/path/Conditions и current crossed state, после чего выполняет Close attack и добавляет Charge receipt, не двигая actor повторно. Failed terrain Test сохраняет Prone, но не отменяет атаку: по странице 123 Prone запрещает последующий выход из Zone и модифицирует атаки против лежащего, а не его собственную атаку. Post-terrain Staggered fact всё равно обязан совпасть с `AttackRequest`; Melee получает обычный `+1d`, другие Skills следуют временной политике `AMBIGUITY-007`.

### Реализация Move Carefully в K1

`MoveCarefullyActionExecutionRequest` связывает active actor/round, зарезервированный `ManoeuvreKind.MOVE_CAREFULLY` и обычный `FreeMovementRequest`, чей маршрут явно помечен как пересекающий Difficult Terrain. Это одно действие: reducer проверяет movement context, переносит actor по тому же Zone graph, расходует общий `free_move_used_entity_ids` и лишь затем добавляет receipt. Athletics Test не создаётся, а `difficult_terrain_tested_entity_ids` и прочие spatial usage сохраняются без изменений.

Normal проходит одну Zone boundary, Fast — до двух последовательных связей. Slow, Burdened, Prone, Defenceless, obstacle, enemy path blocker, неизвестный/несвязный маршрут, уже использованный free move и нарушение порядка slots закрываются до RNG. Союзник на пути не блокирует движение. Зарезервированный Move Carefully нельзя оставить неисполненным и завершить ход.

Необязательный Awareness search выражен закрытым выбором `MoveCarefullySearchChoice.DECLINE` либо `SEARCH`. `DECLINE` не принимает Test и не обращается к RNG. `SEARCH` требует `Skill.AWARENESS`, выполняет общий `TestRequest → TestResult` после movement preflight и сохраняет полный trace; интерпретация найденной скрытой возможности, слабости или противника принадлежит будущему scene/battle orchestration. Обе ветви завершают тот же slot и не создают дополнительного перемещения.

Как и остальные pure reducers, точный повтор одного неизменного request воспроизводит тот же результат; глобальную дедупликацию request ID должен обеспечить будущий battle aggregate.

## RULE-COMBAT-015 — Give Ground и Prone

Give Ground перемещает от attacker в выбранную adjacent Zone, максимум раз/round. Вход во вражескую Zone даёт Broken. Путь не проходит через enemies, obstacles или Difficult Terrain; Prone/невозможность покинуть Zone запрещают выбор.

Prone нельзя получить повторно или сочетать с Give Ground. Если уже Staggered+Prone снова получает Staggered, результатом становится Wound.

Источник: страницы 119–120.

### Реализация spatial Give Ground в K1

`ZoneGraph` хранит стабильные Zone ID и неориентированное соседство без метров и координат. `SpatialBattleState` отдельно хранит стабильный список размещений и round-scoped факты Give Ground, free move и хотя бы одного Difficult Terrain Test. Стороны представлены coalition-like `side_id`: сущности с разными значениями считаются врагами.

`GiveGroundResolutionRequest` принимает уже выбранную destination Zone, Conditions движущегося существа и явный локальный снимок пути. Общий reducer проверяет соседство, увеличение graph-distance от атакующего при наличии `away_from_entity_id`, Prone/Defenceless, round limit, enemy blockers, obstacle и Difficult Terrain. После успешной проверки он меняет только размещение и round-scoped usage. `GiveGroundResolutionResult` хранит состояния до/после и проверяет точность этой мутации. Вход в Zone с врагом затем накладывает Broken через общий Condition reducer.

Книга не позволяет вывести путь внутри Zone только из графа. Поэтому `path_entity_ids`, `crosses_obstacle` и `crosses_difficult_terrain` сообщает orchestration/GM policy; это не скрытые defaults. Выбор destination, vertical/midair preference, cover, line of sight и Manoeuvre пока остаются снаружи этого executor. Решение границы зафиксировано в [`ADR-0003`](../decisions/ADR-0003-zone-graph-and-spatial-boundary.md).

## RULE-COMBAT-016 — Retreat

Только единогласная группа объявляет Retreat в начале round/своего side turn. Один персонаж тратит Fate на rearguard; без Fate GM назначает blood, materiel или misfortune cost. При pursuit каждый PC делает Athletics, иногда auto-success от Lore и/или opposed более быстрым врагом. За каждого провалившего бросается `1d10`, суммы определяют Run For Your Lives result; Complications могут вызвать roll даже без провалов.

Источник: страница 120. Табличные исходы `1–3` Lost, `4–6` Mocked, `7–9` Indebted, `10–12` Marked, `13–15` Exposed, `16–18` Hunted, `19–21` Robbed, `22–24` Surrounded, `25+` Trapped требуют campaign-state orchestration.
