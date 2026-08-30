# ADR-0006: session-состояние и фазовая трата Fate

Статус: принято 2026-08-30.

## Контекст

Player’s Guide 1.4 на странице 111 разделяет permanent Fate rating и число расходов в текущей session. Неиспользованные расходы не переносятся, GM может разрешить refresh после перерыва, а последующий burn не должен задним числом делать уже допустимую session history невозможной. Та же страница разрешает сделать свою Test Glorious до броска либо после initial roll, но до описания исхода; уже Glorious Test и повторный reroll запрещены.

Прежний монолитный `resolve_test` выполнял initial roll и Grim/Glorious rerolls за один вызов. Встраивание списания Fate внутрь RNG resolver смешало бы ресурс персонажа, решение игрока и бросковую механику, а также не позволило бы переиспользовать один Fate pool для second action и Tactical Retreat.

## Решение

- Хранить `FateSessionState` отдельно от Test, turn и battle state. Состояние привязано к `session_id` и actor, содержит permanent `rating`, отдельный `session_spend_limit` и ordered typed history расходов.
- Вычислять remaining spends из session limit и history, а не непосредственно из rating. Это оставляет место для burn, mid-session refresh и иных явных источников без переписывания прошлой истории.
- Каждую трату хранить как `FateSpendRecord` со stable ID, session/actor, typed kind, subject ID и каноническим Rule ID. На первом срезе поддержан только `GLORIOUS_TEST`; новые книжные применения добавляются отдельными consumers того же pool.
- Реализовать `FateGloriousSpendRequest → Result` как чистый transition до броска либо после matching `InitialTestRoll`. Он проверяет доступный расход, запрет повтора и уже Glorious Test, добавляет одну запись history, создаёт session/actor/Test/spend-bound `FateGloriousProof` и возвращает копию Test с source-classified Glorious modifier.
- Не мутировать исходные state и Test. Result хранит previous/new state, spend, proof, подготовленную Test и Rule trace; подмена любой части отклоняется provenance-инвариантами.
- Разделить Test resolver на `roll_test_initial → InitialTestRoll` и `complete_test`; оставить `resolve_test` обратно совместимой композицией. Completion принимает исходную Test без изменений либо ту же Test с одним добавленным Fate Glorious modifier и никогда не повторяет initial roll.
- Для Grim Test применять after-roll расход до completion: добавленный Glorious отменяет Grim, поэтому обязательный reroll первоначальных successes ещё не происходил.
- Не подключать этот consumer автоматически к second action slot. `turn_resolution` пока принимает Fate grant как внешний факт; отдельный adapter позже обязан потратить тот же session resource и связать расход с конкретным slot.

## Последствия

Трата Fate на Glorious до либо после initial roll имеет проверяемую цену и создаёт proof, который принимает `Drained` preparation. Permanent rating не смешивается с session allowance, повтор той же Test нельзя скрыть передачей исходного `TestRequest`, а история не переносится между actor/session. Initial pool имеет отдельный immutable provenance snapshot и не бросается повторно после решения. Lucky/free spends, refresh producer, burn, second action и Tactical Retreat остаются отдельными границами.
