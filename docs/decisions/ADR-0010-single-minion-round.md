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

- `COMPLETE`: все участники текущего round завершили ход. Повтор с returned complete round ничего не исполняет и не вызывает provider/RNG.
- `PENDING_FOLLOW_UPS`: очередь сохраняется целиком. При новом Wound остаётся активный ход с исполненным slot и применённым injury; receipt не подтверждает Give Ground или форму Minion defeat. Входная непустая очередь останавливает вызов до любого перехода/provider/RNG.
- `SELECTION_BLOCKED`: result.blocked_selection сохраняет точную причину контроллера, включая NO_CANDIDATE/EXECUTION_CONSUMED. Slot остаётся зарезервированным и неисполненным; нет автоматического skip/Recover. После новых внешних фактов caller может возобновить выбор в том же slot.
- `DEFEATED_ACTOR`: следующий или активный actor уже defeated. Coordinator останавливается до Attack; не создаёт фиктивное действие, receipt или completed-turn marker, не меняет состав раунда.

Caller передаёт returned state/round/pending в новый запрос. После внешней обработки последствий он может передать подтверждённую актуальную очередь; автоматического acknowledgement/reducer подтверждения в этом срезе нет. Если активный slot уже исполнен, request требует его receipt в consumed roster history. При пустой очереди coordinator только закрывает этот ход, не вызывает provider или kernel повторно. Затем он использует свежий context следующего actor.

Откат всех внешних snapshots не предотвращается. Rollback только round при сохранении returned history блокируется стабильным execution ID. Ошибки provider/неподдержанного входа не превращаются в тихий skip. Входные значения immutable, но RNG и внешние решения не откатываются при исключении, в том числе после более ранних ходов данного вызова.

## Границы

Поддержан обычный Minion Attack-only сценарий: одна STANDARD Attack, без второго Fate/Ability action, дополнительных attack effects, автоматических Conditions/Ability/end-turn эффектов. Другие проверки eligibility и все awareness/range/модификаторы остаются caller/provider-owned. Выбор первой подходящей Attack переиспользует ADR-0009. Нет автоматического снятия defeated из turn queue, изменения next-round participants, завершения боя, spatial Give Ground или выбора формы поражения NPC. Это явные пределы первого координатора, не house rules.

## Проверка

10 unit tests в `test_m2_npc_round_coordinator.py`: остановки, NO_CANDIDATE resume, pending Wound/Give Ground, receipt/history, defeated, источник provider, ограничения request и целостность журнала.

3 integration tests в `test_m2_npc_round_cycle.py`: законченный 2×2 раунд с реальными Close miss/первым Staggered и переносом состояния, оба side_order с явным предпочтением actor, частичный прогресс и возобновление позднего NO_CANDIDATE. В полном раунде четыре kernel/receipt, один набор бросков на атаку, исходные snapshots неизменны. Полный набор: 1545 tests OK на Python 3.14.
