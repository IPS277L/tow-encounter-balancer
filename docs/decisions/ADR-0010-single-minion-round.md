# ADR-0010: ограниченная координация одного Minion-раунда

Статус: принято, 2026-09-27.

## Контекст

Roster, контроллер выбора и executor одной Minion Attack уже готовы. Для первого сценария с несколькими бойцами нужно последовательно переносить возвращённые roster/history/round и не путать исполненный slot с завершением внешних последствий. Старый P1 BattleEngine не является основанием книжного порядка ходов.

Непосредственно сверены BOOK-PLAYER-GUIDE 1.4, Rules / Combat и Ambush, стр. 112; Combat Actions, стр. 116; Attack Tests, стр. 118; Failed/Successful Attacks и Giving Ground, стр. 119; BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91; Understanding NPC Profiles, стр. 93. Книга задаёт порядок сторон, полное завершение хода и обычный один action; выбор кандидатов и ограничение сценария одной Attack — явная orchestration policy.

## Решение

`domain/npc_round_models.py` вводит frozen `NpcRoundRequest/Result` и `NpcRoundOutcome`. Запрос связывает существующие roster/history, CombatRoundState, явный actor_order и pending follow-ups. Это запрос обработки одного раунда, не новый владелец spatial/magic/Fate/inventory или общий battle aggregate.

actor_order содержит каждого участника текущего round ровно один раз. Он задаёт приоритет внутри стороны: фактическую сторону определяет сохранённый side_order CombatRoundState. Уже активный ход завершается первым. Участники раунда обязаны соответствовать actor/side в roster и иметь Minion policy. Roster может содержать дополнительные экземпляры вне текущего раунда. Defeated не удаляются автоматически.

`engine/npc_round_coordinator.py::run_npc_round` принимает внедряемые RNG, DecisionProvider и NpcRoundCandidateProvider. Для каждого незавершённого участника он:

1. Использует прежние start_combat_turn и reserve_combat_action_slot для одной STANDARD Attack; уже открытый ход/slot сохраняет.
2. Передаёт provider свежий NpcAttackSelectionRequest с пустыми candidates. Provider возвращает тот же context, заменив только ordered candidates. Изменение roster/history/round/actor/IDs/pending отклоняется до исполнения данной атаки.
3. Вызывает select_npc_attack, exact handoff и прежний execute_npc_roster_attack ровно один раз; переносит returned roster/history, round и pending queue.
4. Только при пустой pending queue завершает ход прежним end_combat_turn и переходит к следующему actor текущей стороны.

Идентификаторы производятся из стабильного request.id, номера раунда и actor ID. При возобновлении следует сохранять request.id. Цикл ограничен числом участников исходного раунда; следующего раунда, оценки победителя или цикла боя здесь нет.

Result сохраняет хронологический tuple существующих typed результатов start/reserve/selection/attack/end. Проверка журнала связывает каждый переход с предыдущими снимками, выбором, receipt и порядком. Она не исполняет Tests/kernel повторно. Итоговые state/round/pending/outcome — readonly views проверенного журнала. Журнал содержит только переходы данного вызова; caller сохраняет предыдущие результаты отдельно.

## Остановки и возобновление

- `COMPLETE`: каждый участник текущего round завершил ход либо был явно исключён из его очереди. Повтор с returned complete round ничего не исполняет и не вызывает provider/RNG.
- `PENDING_FOLLOW_UPS`: очередь сохраняется целиком. При новом Wound остаётся активный ход с исполненным slot и применённым injury; receipt не подтверждает Give Ground или форму Minion defeat. Входная непустая очередь останавливает вызов до любого перехода/provider/RNG.
- `SELECTION_BLOCKED`: result.blocked_selection сохраняет точную причину контроллера, включая NO_CANDIDATE/EXECUTION_CONSUMED. Slot остаётся зарезервированным и неисполненным; нет автоматического skip/Recover. После новых внешних фактов caller может возобновить выбор в том же slot.
- `DEFEATED_ACTOR`: следующий или активный actor уже defeated. Coordinator останавливается до Attack; не создаёт фиктивное действие, receipt или completed-turn marker, не меняет состав раунда.

Caller передаёт returned state/round/pending в новый запрос. После внешней обработки последствий он может передать подтверждённую актуальную очередь; автоматического acknowledgement нет; для формы поражения Minion доступен отдельный typed consumer ниже, для завершённого Give Ground доступен отдельный consumer ниже; выбор Zone и запуск spatial reducer остаются внешними. Если активный slot уже исполнен, request требует его receipt в consumed roster history. При пустой очереди coordinator только закрывает этот ход, не вызывает provider или kernel повторно. Затем он использует свежий context следующего actor.

Откат всех внешних snapshots не предотвращается. Rollback только round при сохранении returned history блокируется стабильным execution ID. Ошибки provider/неподдержанного входа не превращаются в тихий skip. Входные значения immutable, но RNG и внешние решения не откатываются при исключении, в том числе после более ранних ходов данного вызова.

## Границы

Поддержан обычный Minion Attack-only сценарий: одна STANDARD Attack, без второго Fate/Ability action, дополнительных attack effects, автоматических Conditions/Ability/end-turn эффектов. Другие проверки eligibility и все awareness/range/модификаторы остаются caller/provider-owned. Выбор первой подходящей Attack переиспользует ADR-0009. Нет автоматического снятия defeated из turn queue, изменения next-round participants, завершения боя, spatial Give Ground или выбора формы поражения NPC. Это явные пределы первого координатора, не house rules.

## Проверка

10 unit tests в `test_m2_npc_round_coordinator.py`: остановки, NO_CANDIDATE resume, pending Wound/Give Ground, receipt/history, defeated, источник provider, ограничения request и целостность журнала.

3 integration tests в `test_m2_npc_round_cycle.py`: законченный 2×2 раунд с реальными Close miss/первым Staggered и переносом состояния, оба side_order с явным предпочтением actor, частичный прогресс и возобновление позднего NO_CANDIDATE. В полном раунде четыре kernel/receipt, один набор бросков на атаку, исходные snapshots неизменны. Полный набор: 1545 tests OK на Python 3.14.

## Исключение defeated Minion из текущего раунда

Уточнение принято 2026-09-28. Непосредственно перечитаны BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91; BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112; Combat Actions, стр. 116.

`CombatRoundState.excluded_turn_entity_ids` — ordered tuple уникальных участников, не ожидающих хода в этом раунде. Он не пересекается с completed_turn_entity_ids; active actor не может быть excluded. Исходный состав обеих сторон и side_order сохраняются. next_side ищет оставшихся участников, round_complete проверяет отсутствие оставшихся. Это представление очереди, не новое игровое правило defeat.

`NpcRoundExclusionRequest(id, source: NpcRoundRequest, actor_id)` требует defeated Minion из текущего round, без завершённого хода или предыдущего исключения и с пустой pending queue. Можно исключить участника любой стороны, включая текущего active actor. Другой активный ход не меняется. `NpcRoundRequest` также проверяет defeated для всех уже excluded участников.

`exclude_defeated_npc` возвращает frozen `NpcRoundExclusionResult` с полным источником. Его round_state дополняет exclusions и очищает active_turn только у исключаемого actor. interrupted_turn хранится в источнике и доступен отдельным view: неисполненная резервация не получает receipt, ранее исполненная Attack не отменяется. Результат не создаёт completed turn, не меняет roster/consumed execution IDs и не исполняет RNG, Test или последствия повторно.

`apply_npc_round_exclusion(current, result)` проверяет exact исходный NpcRoundRequest, включая roster/history, round, actor preference, ID и pending, и возвращает запрос с новым round_state. Повтор с возвращённым состоянием и повторный запрос на исключение отвергаются. Откат всех caller-owned snapshots не предотвращается. Caller хранит результат исключения отдельно от журналов coordinator; исключение не подтверждает pending последствия.

После применения прежний coordinator пропускает excluded actor. Если все участники завершили ход или исключены, возвращается COMPLETE без provider/RNG и без вывода о победителе. Если на одной стороне не осталось ожидающих ходов, next_side переходит к другой. Живой actor без подходящей цели по-прежнему останавливается на SELECTION_BLOCKED; ему не создаётся фиктивный ход. При полном исключении обеих сторон завершён только текущий round. advance_combat_round по-прежнему требует новый явный состав обеих сторон и сбрасывает exclusions. Запуск следующего раунда автоматически не добавлен.

Проверены все потребители completed_turn_entity_ids/next_side/round_complete. Старый Retreat timing зависит именно от completed turns; композиция с exclusions явно отклоняется до отдельной интеграции. Это техническая граница, не запрет Retreat в книге.

12 новых unit и 3 integration tests: обе очередности сторон, все/одна сторона excluded, Wound/pending, exact source/history/replay, прерванные active slots, сохранение receipts, запрет старта excluded actor, next-round reset и граница Retreat. Сценарий 2×2 проходит Wound → внешнее подтверждение → DEFEATED_ACTOR → exclusion → завершение остальных ходов с тремя kernel/receipts; прямое исключение цели до закрытия атакующего также проверено. Полный набор: 1560 tests OK на Python 3.14.

## Подтверждение формы поражения Minion

Уточнение принято 2026-09-28. Непосредственно перечитан BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91. В книге три исхода: killed, knocked out, disarmed and forced to surrender; последний — один совмещённый исход. Выбор принадлежит атакующему и подчинён усмотрению GM.

`MinionDefeatDecision` содержит attacker_id, target_id, typed NpcDefeatDisposition и явный bool gm_approved. Одобрение не выводится автоматически. `MinionDefeatAcknowledgementRequest` связывает это решение с текущим NpcRoundRequest и полным NpcRosterAttackExecutionResult: одних чисел в ProfileStateChangeRequest недостаточно, у него нет actor/target ID.

Request требует exact post-Attack roster/history и round с исходным исполненным slot, совпадение actor/target решения, GM approval и новый Minion defeat с одним ProfileStateChange, согласованным с предыдущими/текущими Wounds. Текущая pending queue обязана содержать matching item ровно один раз и все исходные pending элементы в исходном порядке; дополнительные элементы допустимы. Дубликат анонимного matching ProfileStateChange отклоняется, поскольку его нельзя однозначно связать с источником. Изменённый после Attack roster/round в этом срезе не поддержан; чужая атака с равным по значению ProfileStateChange не проходит проверку полного источника.

`acknowledge_minion_defeat` возвращает frozen результат с источником и выбранным решением; continuation — view нового NpcRoundRequest. Из очереди удаляется только один matching item, остальные сохраняются в прежнем порядке. Добавляется execution ID в acknowledged_defeat_execution_ids. Roster, injury/Conditions, equipment, consumed attack IDs и round/receipt сохраняются. Ни kernel, ни RNG, ни новый action не вызываются.

`apply_minion_defeat_acknowledgement(current, result)` принимает только exact исходный current, включая pending и actor preference. Повтор с returned state, повторный request с новым ID/другим выбором или повторно добавленным follow-up блокируется execution history. История подтверждений хранится в NpcRosterAttackState и переносится всеми последующими Attack results; значения уникальны и входят в consumed_execution_ids. Полный откат caller-owned snapshots не предотвращается. Истинность переданных решений/одобрения GM остаётся ответственностью caller.

Caller сохраняет acknowledgement result отдельно от журнала coordinator: он содержит конкретную форму поражения. При пустой возвращённой очереди можно применить существующее исключение defeated и продолжить раунд; незавершённые Give Ground и другие последствия по-прежнему блокируют оба шага. Решение не меняет spatial/inventory и не объявляет конец боя; последствия killed/knocked out/surrender вне generic ProfileInjuryState остаются отдельной границей. Общий NPC disposition engine не добавлен.

11 unit + 2 integration tests: три исхода, typed/GM/actor/target guards, отсутствие нового injury/receipt, exact source/history/queue, чужой Attack с идентичным анонимным follow-up, replay с новым ID/исходом и requeue, сохранение других pending. Сквозные сценарии: Wound → подтверждение → exclusion → оставшиеся ходы для каждого исхода (три kernel/receipt); две последовательные defeat/acknowledgement с переносом обеих историй и завершением только текущего раунда (два kernel/receipt). Полный набор: 1573 tests OK на Python 3.14.

## Применение завершённого Give Ground к M2

Уточнение принято 2026-09-28. Непосредственно перечитан BOOK-PLAYER-GUIDE 1.4, Rules / Attack Tests, Failed Attacks и Giving Ground, стр. 119. Повторный Staggered допускает выбранный Give Ground; движение от атакующего в соседнюю Zone расходует once-per-round usage, вход в Zone с врагом добавляет Broken.

`NpcGiveGroundConsumptionRequest` содержит id, current NpcRoundRequest, текущий SpatialBattleState, полный NpcRosterAttackExecutionResult и готовый GiveGroundResolutionResult. Требуются exact post-Attack roster/history/round, единственный GiveGroundRequest из исходной атаки и ровно один matching item в текущей очереди. Все исходные pending элементы сохраняются в исходном порядке, дополнительные элементы допустимы. Source result связывает target, а сохранённый movement.source_request — away_from_entity_id атакующего и исходные target Conditions. Неизменённый после Attack roster/round — явная граница этого consumer.

Общий resolve_give_ground теперь сохраняет полный GiveGroundResolutionRequest в result.source_request. При наличии этого поля результат сверяет source, previous_state, mover, destination, сохранение исходных Conditions и единственную Broken application. Поле имеет default None для прежних standalone результатов; новый M2 consumer требует его наличия. Это запись источника, не повторное исполнение movement/Condition rules и не доказательство истинности caller-supplied path facts.

Spatial snapshot должен совпадать с movement.previous_state, номер раунда — с combat round. Каждый участник текущего round должен иметь placement с side_id == CombatSide.value; дополнительные placements остаются явными пространственными фактами caller. Проверяются target availability/once-per-round из Attack context и movement trace. Выбор Zone, препятствия и path facts остаются внешними; их обрабатывает существующий spatial reducer.

`consume_npc_give_ground` возвращает frozen результат с полным source. continuation содержит новый NpcRoundRequest: только Conditions цели берутся из завершённого движения, её Wounds/equipment и остальные участники не меняются. Из pending удаляется ровно один matching GiveGroundRequest. consumed_give_ground_execution_ids дополняется execution ID этой атаки, без нового action receipt. spatial_state — view прежнего movement.state с placement и once-per-round usage; free move/terrain usage сохраняются.

`apply_npc_give_ground(current, spatial_state, result)` сверяет оба exact текущих снимка и возвращает пару `(NpcRoundRequest, SpatialBattleState)`. Caller обязан сохранить оба и полный consumption result отдельно от coordinator journal. Consumer не вызывает kernel, RNG, movement или Condition reducers. История Give Ground — уникальное подмножество consumed Attack IDs в NpcRosterAttackState, переносимое последующими атаками. Повтор с новым ID/requeued follow-up/возвращённой историей отклоняется, даже когда Conditions не изменились. Полный откат всех caller-owned snapshots не предотвращается.

Без pending coordinator закрывает прежний receipt и продолжает с новым roster. Spatial state передаётся внешнему candidate provider отдельно: автоматического определения дальности или общей eligibility здесь нет. Broken запрещает продолжить Attack: теперь controller возвращает ACTOR_BROKEN даже при supplied candidate; фильтр в integration provider удалён. Остальные pending по-прежнему блокируют продолжение. Атомарный preflight перед самим movement реализован отдельным adapter ниже; standalone consumer по-прежнему принимает уже завершённый результат.

Проверки: 10 unit + 2 integration tests, включая safe/enemy Zone/уже Broken, Conditions/source/trace, очередь, обе стороны/round/spatial, history/replay, unchanged injury и единственное движение. Safe 2×2 cycle завершает раунд: четыре kernel/receipt и один Give Ground; enemy-Zone cycle передаёт Broken следующему provider и останавливает Broken actor без исполнения. Старый hidden consumer negative test сохранён для legacy result, добавлена проверка более раннего отказа нового result при подмене source. Полный набор: 1585 tests OK на Python 3.14.

## Атомарное исполнение Give Ground M2

Уточнение принято 2026-09-28. Непосредственно перечитан BOOK-PLAYER-GUIDE 1.4, Rules / Giving Ground, стр. 119. Новых игровых правил нет.

`NpcGiveGroundExecutionRequest` связывает текущие round/spatial snapshots, полный Attack result и pending GiveGroundResolutionRequest с явно выбранной Zone. Общий `validate_npc_give_ground_context` вызывается при создании обоих request types и перед исполнением adapter: проверяет exact source/history/pending, mover/attacker/Conditions, round/side и once-per-round. Completed ветвь дополнительно требует полный movement source и trace. Пространственная допустимость маршрута (adjacency, away, препятствия, terrain, enemies) остаётся в существующем resolve_give_ground.

`execute_npc_give_ground` вызывает один resolve_give_ground, сверяет returned source_request с точным исполнявшимся запросом и вызывает один consume_npc_give_ground. Возвращается прежний NpcGiveGroundConsumptionResult, хранящий единственный completed movement и оба snapshots через views. Дополнительного result wrapper/receipt/RNG нет. Прежний apply_npc_give_ground сверяет текущие снимки и отдаёт пару continuation/spatial_state.

Stale/replay/mismatched queue отбрасываются до movement. Ошибка route legality не запускает consumer. Исключение resolver/consumer или подмена результата не возвращает частично обновлённое состояние: исходные значения immutable. Внешние побочные эффекты подменённых функций не откатываются. Выбор Zone, истинность path facts, сохранение обоих возвращённых snapshots и общая eligibility остаются ответственностью caller. Остальные pending не погашаются автоматически.

8 unit tests проверяют safe/enemy/уже Broken, один movement/consumer, guards до movement, once-per-round, illegal routes, requeue/new-ID replay, сохранение предыдущей defeat history и чужой pending, exceptions/подмену результата/types. Один integration test с двумя ветвями проходит pending Attack → атомарный Give Ground → продолжение того же раунда; safe завершает четыре Attack, enemy переносит Broken в свежий provider и останавливает Broken actor. Прежние 12 consumer/integration tests сохранены. Полный набор: 1594 tests OK на Python 3.14.

Проверка композиции 2026-09-28: test_m2_mixed_round_cycle.py содержит один тест / 6 сочетаний обоих порядков сторон и всех трёх defeat dispositions. Pending Give Ground → atomic movement/consumer → следующая Attack/Wound → typed acknowledgement → exclusion → последний допустимый ход завершают один 2×2 раунд. Provider получает returned spatial state, выживший стреляет Warbow из соседней Zone. Три kernel/receipt, один movement/consumer, 18 RNG вызовов; вручную pending не очищается. Проверены обе блокировки на pending, непрерывность трёх histories, сохранение slots/usage и replay обоих последствий/exclusion. Новых API или архитектурных решений нет. Полный набор: 1595 tests OK. Источники: BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112; Giving Ground, стр. 119; BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91.

## Явный переход к следующему раунду M2

Уточнение принято 2026-09-28. Источники непосредственно перечитаны: BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112; Giving Ground, стр. 119; BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91.

`NpcRoundAdvanceRequest(id, current, spatial_state, next_round_participants, next_actor_order)` требует завершённый CombatRoundState без active turn, пустую pending queue и тот же spatial round number. Следующий состав/порядок задаются явно; общие CombatRoundState/NpcRoundRequest проверяют уникальность IDs, наличие обеих сторон, точное соответствие roster, Minion policy и actor order. Defeated в новом составе отклоняется. Все участники прежнего и следующего раунда должны иметь текущий placement с canonical CombatSide.value. Новые участники из уже имеющегося roster допустимы при этих проверках; общего добавления/создания definitions нет.

`advance_npc_round` вызывает прежние advance_combat_round и start_next_spatial_round по одному разу. `NpcRoundAdvanceResult` хранит источник, существующий CombatRoundAdvanceResult и новый SpatialBattleState; проверяет точный новый номер, состав, side_order, сброс completed/excluded/active turn и всех трёх spatial usage списков. Placements/graph сохраняются. continuation — новый NpcRoundRequest с прежними id, roster, Conditions и всеми histories; меняются только round и явный actor_order. Это не запуск нового действия и не восстановление Conditions.

`apply_npc_round_advance(current, spatial, result)` сверяет оба exact исходных snapshots, включая pending/history, и возвращает continuation/spatial_state вместе. Повтор и частичное применение одного из двух переходов отклоняются. Новый request на ещё не сыгранный round с возвращёнными snapshots также отклоняется как незавершённый. Полный откат всех caller-owned snapshots не предотвращается. При ошибке reducer/result validation не возвращается частичный результат; исходные immutable значения сохраняются, внешние эффекты подменённых функций не откатываются.

Без обеих сторон advance отклоняется по существующему контракту; это техническая граница, не определение победителя или дополнительное книжное правило. Состав не фильтруется автоматически, battle loop не запускается. Caller сохраняет результат перехода и оба snapshots, затем отдельно вызывает coordinator. Смена actor preference внутри стороны разрешена, persistent side_order сохраняется.

8 unit tests: синхронность, один вызов каждого reducer, exact source/replay, malformed transitions, pending/active/incomplete, defeated/одна сторона, placements/side/round, normalization и exceptions. Новый integration test в test_m2_mixed_round_cycle.py продолжает прежний смешанный 2×2 цикл следующим 2×1 раундом: 6 сочетаний обоих side_order и трёх dispositions, шесть kernel/receipt суммарно, один Give Ground, свежие slots/IDs, неизменные три histories и сброшенный usage. Прежний тест первого раунда сохранён отдельно. Полный набор: 1604 tests OK на Python 3.14.

Actor eligibility уточнена в [ADR-0009](ADR-0009-npc-attack-selection-policy.md#запрет-attack-по-conditions-атакующего): Broken/Defenceless дают SELECTION_BLOCKED до исполнения Attack, pending сохраняет приоритет. Coordinator не закрывает такой slot и не выбирает вместо него другое действие.

Ограниченная композиция нескольких таких раундов реализована отдельно в [ADR-0011](ADR-0011-bounded-minion-rounds.md). Сам run_npc_round по-прежнему не запускает следующий раунд; новый runner сохраняет его остановки и использует прежний explicit advance.
