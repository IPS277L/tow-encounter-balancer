# Бой и атаки

Источник: `BOOK-PLAYER-GUIDE`, преимущественно страницы 111–120. Статус: правила атаки `implemented` в K1; раунды, действия и завершение боя остаются `draft` для нового battle loop.

## RULE-COMBAT-001 — раунды, стороны и ходы

Каждый участник получает один ход в каждом раунде. По умолчанию сначала действует сторона игроков и союзников, затем противники. Порядок участников внутри своей стороны выбирается заново каждый раунд; один участник полностью завершает ход до начала следующего.

Источник: страница 112.

## RULE-COMBAT-002 — основная экономика действий

Обычно участник выполняет одно боевое действие за ход и допустимые incidental actions, включая одно бесплатное перемещение. Fate или способности могут дать второе действие, но действий не может быть больше двух. Одно и то же действие нельзя повторять, а второе действие не может создавать вторую атаку, если специальное правило явно не переопределяет это ограничение.

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

## RULE-COMBAT-015 — Give Ground и Prone

Give Ground перемещает от attacker в выбранную adjacent Zone, максимум раз/round. Вход во вражескую Zone даёт Broken. Путь не проходит через enemies, obstacles или Difficult Terrain; Prone/невозможность покинуть Zone запрещают выбор.

Prone нельзя получить повторно или сочетать с Give Ground. Если уже Staggered+Prone снова получает Staggered, результатом становится Wound.

Источник: страницы 119–120.

### Реализация spatial Give Ground в K1

`ZoneGraph` хранит стабильные Zone ID и неориентированное соседство без метров и координат. `SpatialBattleState` отдельно хранит стабильный список размещений и использованный в текущем round Give Ground. Стороны представлены coalition-like `side_id`: сущности с разными значениями считаются врагами.

`GiveGroundResolutionRequest` принимает уже выбранную destination Zone, Conditions движущегося существа и явный локальный снимок пути. Общий reducer проверяет соседство, увеличение graph-distance от атакующего при наличии `away_from_entity_id`, Prone/Defenceless, round limit, enemy blockers, obstacle и Difficult Terrain. После успешной проверки он меняет только размещение и round-scoped usage. `GiveGroundResolutionResult` хранит состояния до/после и проверяет точность этой мутации. Вход в Zone с врагом затем накладывает Broken через общий Condition reducer.

Книга не позволяет вывести путь внутри Zone только из графа. Поэтому `path_entity_ids`, `crosses_obstacle` и `crosses_difficult_terrain` сообщает orchestration/GM policy; это не скрытые defaults. Выбор destination, vertical/midair preference, cover, line of sight, Speed и Manoeuvre пока остаются снаружи этого executor. Решение границы зафиксировано в [`ADR-0003`](../decisions/ADR-0003-zone-graph-and-spatial-boundary.md).

## RULE-COMBAT-016 — Retreat

Только единогласная группа объявляет Retreat в начале round/своего side turn. Один персонаж тратит Fate на rearguard; без Fate GM назначает blood, materiel или misfortune cost. При pursuit каждый PC делает Athletics, иногда auto-success от Lore и/или opposed более быстрым врагом. За каждого провалившего бросается `1d10`, суммы определяют Run For Your Lives result; Complications могут вызвать roll даже без провалов.

Источник: страница 120. Табличные исходы `1–3` Lost, `4–6` Mocked, `7–9` Indebted, `10–12` Marked, `13–15` Exposed, `16–18` Hunted, `19–21` Robbed, `22–24` Surrounded, `25+` Trapped требуют campaign-state orchestration.
