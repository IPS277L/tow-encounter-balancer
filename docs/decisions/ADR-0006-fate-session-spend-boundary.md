# ADR-0006: session-состояние и фазовая трата Fate

Статус: принято 2026-08-30.

## Контекст

Player’s Guide 1.4 на странице 111 разделяет permanent Fate rating и число расходов в текущей session. Неиспользованные расходы не переносятся, GM может разрешить refresh после перерыва, а последующий burn не должен задним числом делать уже допустимую session history невозможной. Та же страница разрешает сделать свою Test Glorious до броска либо после initial roll, но до описания исхода; уже Glorious Test и повторный reroll запрещены.

Прежний монолитный `resolve_test` выполнял initial roll и Grim/Glorious rerolls за один вызов. Встраивание списания Fate внутрь RNG resolver смешало бы ресурс персонажа, решение игрока и бросковую механику, а также не позволило бы переиспользовать один Fate pool для second action и Tactical Retreat.

## Решение

- Хранить `FateSessionState` отдельно от Test, turn и battle state. Состояние привязано к `session_id` и actor, содержит permanent `rating`, отдельный `session_spend_limit` и ordered typed history расходов.
- Вычислять remaining spends из session limit и history, а не непосредственно из rating. Это оставляет место для burn, mid-session refresh и иных явных источников без переписывания прошлой истории.
- Каждую трату хранить как `FateSpendRecord` со stable ID, session/actor, typed kind, subject ID и каноническим Rule ID. Поддержаны `GLORIOUS_TEST`, `SECOND_ACTION` и `TACTICAL_RETREAT`; новые книжные применения добавляются отдельными consumers того же pool.
- Реализовать `FateGloriousSpendRequest → Result` как чистый transition до броска либо после matching `InitialTestRoll`. Он проверяет доступный расход, запрет повтора и уже Glorious Test, добавляет одну запись history, создаёт session/actor/Test/spend-bound `FateGloriousProof` и возвращает копию Test с source-classified Glorious modifier.
- Не мутировать исходные state и Test. Result хранит previous/new state, spend, proof, подготовленную Test и Rule trace; подмена любой части отклоняется provenance-инвариантами.
- Разделить Test resolver на `roll_test_initial → InitialTestRoll` и `complete_test`; оставить `resolve_test` обратно совместимой композицией. Completion принимает исходную Test без изменений либо ту же Test с одним добавленным Fate Glorious modifier и никогда не повторяет initial roll.
- Для Grim Test применять after-roll расход до completion: добавленный Glorious отменяет Grim, поэтому обязательный reroll первоначальных successes ещё не происходил.
- Реализовать Second Action отдельным composite consumer: `FateSecondActionSpendRequest` содержит точный `CombatActionSlotRequest`, producer создаёт session/actor/round/slot/declaration-bound proof, scheduler проверяет его без доступа к `FateSessionState`, а итог одновременно возвращает новый session state и зарезервированный slot. Голый внешний `FATE` grant отклонять.
- Выполнять action-budget preflight до создания итогового spend result, чтобы повтор action, вторая attack, третий action и отсутствие GM allowance для второго Improvise не давали вызывающему коду частично применить расход.
- Реализовать Tactical Retreat ещё одним composite consumer: сначала валидируется единогласное объявление и его timing, затем расход actor из точного PC group атомарно создаёт battle/group-bound rearguard proof/result. Погоню и последствия не считать частью расхода Fate.
- Если Fate исчерпан у всей PC-группы, создавать только GM-owned alternative-price request с blood/materiel/misfortune; конкретную цену и цель не выбирать в Fate reducer. Граница состава и Retreat подробнее зафиксирована в `ADR-0007`.
- Представлять Lucky как funding первой фактической `FateSpendRecord`, а не как дополнительный rating или refresh. При наличии Talent первая запись обязательна `LUCKY_FREE`, имеет нулевую session cost и допустима при rating `0`; следующие записи используют обычный pool. Все три общих spend consumer переиспользуют один funding helper.
- Представлять постоянный Glorious Lucky для gambling Test отдельным Talent producer без `FateSessionState`. Typed request подтверждает actor, Test, game-of-chance context и talent snapshot; result создаёт bound proof и добавляет `TALENT` quality modifier до initial roll. `Drained` валидирует proof, но удаляет этот Glorious, поскольку его исключение относится только к расходу Fate.
- Представлять mid-session refresh отдельным GM-owned request/result и ordered record history. Подтверждённый break восстанавливает remaining до текущего rating увеличением allowance, не удаляя spends и не восстанавливая уже использованный Lucky; break ID и approval ID одноразовы.
- Представлять permanent burn отдельным actor-owned transition, а не отрицательным spend. `FateBurnRecord` всегда уменьшает permanent rating ровно на `1`; refresh и burn имеют общий ordered resource-event index, чтобы их можно было безопасно чередовать без потери provenance.
- Если в момент burn остаётся платный session spend, одновременно уменьшать текущий allowance на `1`. Если pool уже исчерпан, не переписывать допустимую историю и отложить уменьшение effective session rating до следующей session. Deferred burn остаётся видимым в typed record и не теряется при позднейшем GM refresh этой же session.
- Разделить burn на закрытые `Unmitigated Success`, `Near Miss` и `Last Stand`. Каждый producer создаёт subject-bound proof и специализированный effect request; Fate reducer не подменяет Test, injury либо character-death aggregate повествовательной мутацией.

## Последствия

Трата Fate на Glorious до либо после initial roll имеет проверяемую цену и создаёт proof, который принимает `Drained` preparation. Second Action и Tactical Retreat используют тот же funding/pool. Lucky оплачивает только первую session-запись и отдельно делает gambling Tests Glorious без расхода; различие `FATE`/`TALENT` сохраняет правильное поведение при Drained. Неиспользованный Lucky не открывает alternative Retreat price. Refresh восстанавливает ресурс без потери provenance и без повторного Lucky. Burn уменьшает permanent rating, не делает прошлые расходы недействительными и выдаёт typed follow-up вместо скрытого применения исхода. Permanent rating не смешивается с session allowance, история не переносится между actor/session, а повтор Test/slot/Retreat/break/burn-subject в одном actor state отклоняется. Initial pool имеет отдельный immutable provenance snapshot и не бросается повторно после решения. Исполнение burn follow-ups остаётся отдельной границей.
