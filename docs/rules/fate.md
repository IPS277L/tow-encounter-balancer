# Fate

Источник: `BOOK-PLAYER-GUIDE`, версия 1.4, глава Rules — Fate, страницы 111–112 и Retreat на странице 120. Статус области: `partially implemented`; есть session state, трата на Glorious до либо после initial roll, атомарные траты на Second Action и Tactical Retreat, injury pipeline умеет вернуть расход Near Miss, но Lucky/free spend, refresh и burn lifecycle ещё не завершены.

## RULE-FATE-001 — session resource

Fate — Ability только игровых персонажей. Rating задаёт число трат за session; неиспользованные траты не переносятся. В необычно длинной session GM может разрешить refresh после перерыва. Permanent rating и оставшиеся траты session — разные части состояния.

`FateSessionState` хранит `rating`, отдельный `session_spend_limit` и ordered `FateSpendRecord`. Каждая запись связана с session/actor и конкретным subject; остаток вычисляется из session limit, поэтому будущий burn или explicit refresh не переписывает прошлую историю. Создание состояния разрешено только character/session orchestration для игрового персонажа; текущий reducer не выводит это из battle roster.

## RULE-FATE-002 — spend Fate

Fate можно потратить на одно из трёх общих применений:

- сделать свою Test Glorious после первоначального броска, но до описания результата; на Grim Test решение принимается до обязательного reroll successes; уже Glorious Test и повторные rerolls запрещены;
- в своём battle turn выполнить второе, отличающееся action, но не вторую attack и не более двух actions всего; два разных Improvise допустимы с разрешения GM;
- обеспечить rearguard при групповом Retreat.

Источник: страница 111.

`FateGloriousSpendRequest → Result` списывает один доступный session spend до броска либо после matching `InitialTestRoll`, запрещает повтор для той же Test и уже Glorious Test, добавляет source-classified modifier и создаёт `FateGloriousProof`, связанный с session, actor, Test и записью расхода. Это proof позволяет `Drained` сохранить только книжное исключение Fate. Grim допустим и вместе с добавленным Glorious отменяется по общему правилу.

Общий Test resolver разделён на `roll_test_initial` и `complete_test`; совместимый `resolve_test` остаётся их одношаговой композицией. После initial roll completion принимает только неизменённую исходную Test либо ту же Test с ровно одним добавленным Fate Glorious modifier, поэтому исходный пул не бросается повторно. Для Grim Test Fate тратится между фазами и отменяет Grim до обязательного reroll successes.

`FateSecondActionSpendRequest → Result` принимает готовый запрос именно второго action slot, сначала проводит все проверки action budget, затем одним composite-переходом добавляет session spend и резервирует связанный slot. `FateSecondActionProof` фиксирует session, actor, round, slot `2`, declaration, slot request и spend. Голый `ActionSlotGrant.FATE` scheduler больше не принимает; повтор действия, вторая attack, третий action, чужой actor и повтор того же slot отклоняются до выдачи результата.

`FateTacticalRetreatSpendRequest → Result` принимает уже валидированное единогласное групповое объявление, списывает расход у одного входящего в группу actor и атомарно создаёт rearguard proof/result. Proof связан с session, actor, spend, battle, Retreat ID и ordered PC group, поэтому его нельзя перенести на другой бой или состав. Glorious, Second Action и Tactical Retreat расходуют один ordered session pool. При исчерпанных состояниях всех участников отдельный producer создаёт только GM-owned запрос выбора blood/materiel/misfortune; конкретная цель и цена не скрыты в reducer. Lucky/free spend и refresh ещё не расходуют это состояние.

## RULE-FATE-003 — burn Fate

Burn навсегда уменьшает Fate rating на 1 и доступен даже после исчерпания session spends. Общие варианты:

- Unmitigated Success: реалистически возможный лучший исход Test; для attack это не несколько Wounds/целей, но как минимум Total Success;
- Near Miss после Wounds Table полностью отменяет только что полученную Wound, не добавляет её к будущим rolls и сохраняет прежний Staggered;
- Last Stand доступен в desperate battle после хотя бы одной Wound: без Test совершает согласованный исключительный подвиг, после чего персонаж умирает.

Источник: страницы 111–112. Near Miss детально трассируется также как `RULE-HEALTH-004..005`.
