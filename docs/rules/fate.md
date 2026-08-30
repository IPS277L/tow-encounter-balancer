# Fate

Источник: `BOOK-PLAYER-GUIDE`, версия 1.4, глава Rules — Fate, страницы 111–112. Статус области: `partially implemented`; injury pipeline умеет вернуть расход Near Miss, а Test-модель — проверить actor/Test-bound proof траты на Glorious, но общего session/turn Fate state и producer такого proof ещё нет.

## RULE-FATE-001 — session resource

Fate — Ability только игровых персонажей. Rating задаёт число трат за session; неиспользованные траты не переносятся. В необычно длинной session GM может разрешить refresh после перерыва. Permanent rating и оставшиеся траты session — разные части состояния.

## RULE-FATE-002 — spend Fate

Fate можно потратить на одно из трёх общих применений:

- сделать свою Test Glorious после первоначального броска, но до описания результата; на Grim Test решение принимается до обязательного reroll successes; уже Glorious Test и повторные rerolls запрещены;
- в своём battle turn выполнить второе, отличающееся action, но не вторую attack и не более двух actions всего; два разных Improvise допустимы с разрешения GM;
- обеспечить rearguard при групповом Retreat.

Источник: страница 111.

K1 представляет уже совершённую трату на Glorious типизированным `FateGloriousProof`, связанным с actor и Test. Это позволяет `Drained` сохранить только книжное исключение Fate и отвергнуть строковую подделку. Текущий reducer не списывает session resource и не реализует интерактивное решение после initial roll: эти обязанности остаются будущему Fate orchestration.

## RULE-FATE-003 — burn Fate

Burn навсегда уменьшает Fate rating на 1 и доступен даже после исчерпания session spends. Общие варианты:

- Unmitigated Success: реалистически возможный лучший исход Test; для attack это не несколько Wounds/целей, но как минимум Total Success;
- Near Miss после Wounds Table полностью отменяет только что полученную Wound, не добавляет её к будущим rolls и сохраняет прежний Staggered;
- Last Stand доступен в desperate battle после хотя бы одной Wound: без Test совершает согласованный исключительный подвиг, после чего персонаж умирает.

Источник: страницы 111–112. Near Miss детально трассируется также как `RULE-HEALTH-004..005`.
