# Fate

Источник: `BOOK-PLAYER-GUIDE`, версия 1.4, Lucky на странице 78, глава Rules — Fate на страницах 111–112 и Retreat на странице 120. Статус области: `partially implemented`; есть обе части Lucky, session state, GM-approved mid-session refresh, трата на Glorious до либо после initial roll, атомарные траты на Second Action и Tactical Retreat, permanent burn lifecycle и application consumers для всех трёх видов burn. Автоматический выбор масштаба повествовательных исходов намеренно остаётся внешней policy-границей.

## RULE-FATE-001 — session resource

Fate — Ability только игровых персонажей. Rating задаёт число трат за session; неиспользованные траты не переносятся. В необычно длинной session GM может разрешить refresh после перерыва. Permanent rating и оставшиеся траты session — разные части состояния.

`FateSessionState` хранит `rating`, отдельный накопленный `session_spend_limit`, ordered `FateSpendRecord`, наличие Lucky, typed refresh/burn histories и общий `resource_event_ids`, сохраняющий порядок переходов allowance. Остаток равен allowance минус только платные записи: бесплатная Lucky-запись остаётся в истории, но имеет нулевую session cost. Refresh и burn не удаляют прошлые spends; replay общего event order проверяет непрерывность rating/allowance даже при чередовании переходов. Создание исходного состояния разрешено только character/session orchestration для игрового персонажа; reducer не выводит его из battle roster.

Вторая часть Lucky не использует `FateSessionState`: `LuckyGamblingTestPreparationRequest` является явным контекстом собственной Test actor в конкретной игре случая и требует Lucky в полном talent snapshot. Чистый producer создаёт actor/Test/game/request-bound `LuckyGamblingProof` и добавляет `QualityModifierSource.TALENT` Glorious до initial roll, не создавая spend. Общий Test resolver выполняет обычные Glorious rerolls и отмену Grim. `Drained` проверяет exact proof, но удаляет этот modifier: книжное исключение страницы 123 сохраняет только Glorious от фактической траты Fate, а не постоянный эффект Talent.

## RULE-FATE-002 — spend Fate

Fate можно потратить на одно из трёх общих применений:

- сделать свою Test Glorious после первоначального броска, но до описания результата; на Grim Test решение принимается до обязательного reroll successes; уже Glorious Test и повторные rerolls запрещены;
- в своём battle turn выполнить второе, отличающееся action, но не вторую attack и не более двух actions всего; два разных Improvise допустимы с разрешения GM;
- обеспечить rearguard при групповом Retreat.

Источник: страница 111.

`FateGloriousSpendRequest → Result` списывает один доступный session spend до броска либо после matching `InitialTestRoll`, запрещает повтор для той же Test и уже Glorious Test, добавляет source-classified modifier и создаёт `FateGloriousProof`, связанный с session, actor, Test и записью расхода. Это proof позволяет `Drained` сохранить только книжное исключение Fate. Grim допустим и вместе с добавленным Glorious отменяется по общему правилу.

Общий Test resolver разделён на `roll_test_initial` и `complete_test`; совместимый `resolve_test` остаётся их одношаговой композицией. После initial roll completion принимает только неизменённую исходную Test либо ту же Test с ровно одним добавленным Fate Glorious modifier, поэтому исходный пул не бросается повторно. Для Grim Test Fate тратится между фазами и отменяет Grim до обязательного reroll successes.

`FateSecondActionSpendRequest → Result` принимает готовый запрос именно второго action slot, сначала проводит все проверки action budget, затем одним composite-переходом добавляет session spend и резервирует связанный slot. `FateSecondActionProof` фиксирует session, actor, round, slot `2`, declaration, slot request и spend. Голый `ActionSlotGrant.FATE` scheduler больше не принимает; повтор действия, вторая attack, третий action, чужой actor и повтор того же slot отклоняются до выдачи результата.

`FateTacticalRetreatSpendRequest → Result` принимает уже валидированное единогласное групповое объявление, списывает расход у одного входящего в группу actor и атомарно создаёт rearguard proof/result. Proof связан с session, actor, spend, battle, Retreat ID и ordered PC group, поэтому его нельзя перенести на другой бой или состав. Glorious, Second Action и Tactical Retreat используют одну функцию funding: для actor с Lucky самая первая запись получает `LUCKY_FREE`, даже при rating `0`; все последующие записи получают `SESSION_POOL`. Lucky trace сохраняется только на фактически бесплатном результате. Неиспользованный Lucky считается доступной тратой и блокирует ложный переход к alternative Retreat price.

`FateRefreshRequest → Result` не является spend. Он требует подтверждённый mid-session break и GM approval, вычисляет недостающее до effective rating текущей session число расходов, добавляет `FateRefreshRecord` и сохраняет прежнюю spend history. Обычно effective rating равен permanent rating; burn при уже пустом pool откладывает уменьшение session allowance до следующей session, поэтому разрешённый позднейший refresh текущей session также использует прежнее значение. Уже полный ресурс, effective rating `0`, повтор break/approval и forged chain отклоняются. Lucky при refresh не восстанавливается: талант бесплатен только для первой фактической траты session.

## RULE-FATE-003 — burn Fate

Burn навсегда уменьшает Fate rating на 1 и доступен даже после исчерпания session spends. Общие варианты:

- Unmitigated Success: реалистически возможный лучший исход Test; для attack это не убийство нескольких врагов и не несколько Wounds, но как минимум Total Success;
- Near Miss после Wounds Table полностью отменяет только что полученную Wound, не добавляет её к будущим rolls и сохраняет прежний Staggered;
- Last Stand доступен в desperate battle после хотя бы одной Wound: без Test совершает согласованный исключительный подвиг, после чего персонаж умирает.

Источник: страницы 111–112. Near Miss детально трассируется также как `RULE-HEALTH-004..005`.

`burn_fate` принимает ровно один из `FateUnmitigatedSuccessBurnRequest`, `FateNearMissBurnRequest` и `FateLastStandBurnRequest`. Actor может вызвать переход только при permanent rating не ниже `1`; `FateBurnRecord` уменьшает его ровно на `1`, а proof связывает session, actor, kind, subject и source burn. Если до burn остаётся хотя бы один платный расход, текущий allowance тоже уменьшается на `1`. Если pool уже пуст, существующий limit и вся spend/refresh history сохраняются допустимыми, а сниженный rating становится обычным лимитом только при создании следующей session. Refresh/burn имеют единый проверяемый порядок событий.

Burn reducer намеренно не применяет последствия сам. `Unmitigated Success` возвращает Test-bound effect до либо после matching initial roll: не хуже Total Success, только реалистически возможный исход, не несколько Wounds и не убийство нескольких врагов; optional GM agreement остаётся stable fact. `Near Miss` возвращает exact `ConsumeWoundNegationRequest`. `Last Stand` требует подтверждённую ранее Wound и desperate-battle approval, затем возвращает feat-bound запрос без Test с обязательной смертью после подвига и правом GM скорректировать масштаб.

`FateUnmitigatedSuccessApplicationRequest → Result` однократно применяет proof-bearing effect к точному завершённому `TestResult`. Обычный бросковый trace, число successes и вычисленный из них ordinary outcome сохраняются неизменными; рядом создаётся книжный adjudicated outcome `TOTAL_SUCCESS`, который явно supersede обычный исход. Если burn был объявлен после initial roll, application сверяет весь сохранённый snapshot, включая исходные значения, поэтому подмена другим броском той же Test невозможна. Результат не обращается к RNG и не создаёт синтетические successes.

Нарративный лучший исход не выбирается внутри reducer. Caller обязан передать stable `outcome_reference_id` и явно подтвердить, что исход реалистически возможен при благоприятных кубах. Для attack также передаются фактические `killed_enemy_ids` и `wounds_inflicted`: допускается не более одного убитого врага и одной Wound; non-attack не может маскировать эти последствия. Optional предварительное соглашение с GM переносится из burn effect без изменений. Effect ID погашается один раз, а session/actor/Test/initial-roll provenance и каноническая арифметика полного Test trace проверяются до применения.

`FateLastStandApplicationRequest → Result` закрывает уже совершённый подвиг и затем применяет обязательную смерть. Request принимает exact session/actor/battle burn, актуальный живой `CharacterInjuryState` и stable sequence любой действительно существующей Wound в его истории. `final_scope_reference_id`, непустые ordered `affected_subject_ids` и `accomplishment_reference_ids` фиксируют выбранный масштаб, цели и уже применённые внешние последствия; reducer ничего из этого не выбирает и не исполняет повторно. Caller отдельно подтверждает завершение подвига, соответствие тону игры и то, что действие растягивает, но не нарушает пределы возможностей персонажа; optional `gm_adjustment_id` фиксирует фактическую корректировку.

Last Stand не принимает `TestRequest`, `TestResult` или RNG. Результат сохраняет уменьшенный Fate state, точную qualifying Wound и порядок `FEAT_ACCOMPLISHED → ACTOR_DIED`, после чего меняет в injury state только `dead=False → True`. Уже мёртвый actor, отсутствующая Wound, чужой battle/session/actor, пустые либо повторные target/consequence references и повтор effect отклоняются. Даже если подвиг описывает самопожертвование, внешний executor обязан оставить terminal transition этой границе, чтобы смерть не предшествовала подтверждённому accomplishment.

`FateNearMissApplicationRequest → Result` является отдельным actor-owned consumer после Wounds Table и до исполнения `WoundEffectRequest`. Он принимает неизменённые source `CharacterWoundRequest`, принятый `CharacterWoundResult` и proof-bearing burn result, сверяет resolution ID, player subject, session, actor, каноническую строку таблицы и полностью воспроизводит ожидаемый post-Wound state. Успешный переход сохраняет уже уменьшенный Fate state, возвращает точное pre-Wound injury state, помечает отменённую запись и отброшенный effect request в trace и погашает effect ID один раз. Поэтому ранее имевшийся Staggered восстанавливается автоматически, смертельная Wound также отменяется, а будущий пул не учитывает отменённую запись. Non-accepted, чужой, stale, повторный и структурно правдоподобный, но неканонический результат отклоняются.

Прямой `CharacterWoundLifecycleRollRequest → RollResult → CompletionRequest → CompletionResult` закрепляет timing книги. Первая фаза выполняет Wounds Table и останавливается с неразрешённым effect. Во второй фазе caller после просмотра результата либо передаёт actor-owned `FateNearMissBurnRequest`, и composite атомарно выполняет burn/application без daily receipt, либо закрывает окно, регистрирует Wound за день и только затем исполняет effect. Обычная не-Fate отмена также завершается без регистрации/effect. Roll ID и Near Miss effect ID погашаются раздельно; stale injury/day snapshots и replay отклоняются. Kernel Attack, Stagger, Hazard и соответствующие Miscast adapters уже переиспользуют эту pending-фазу; fixed character Wounds проходят отдельный lifecycle без окна Near Miss.
