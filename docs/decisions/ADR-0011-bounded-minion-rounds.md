# ADR-0011: ограниченный прогон Minion-раундов

Статус: принято, 2026-09-28.

## Основание

Координатор одного раунда и согласованный combat/spatial advance готовы. Для последовательного прогона нужны ограничение числа раундов, актуальный spatial context и явный следующий состав; исполнение Attack и обработка последствий остаются в существующих компонентах.

Непосредственно перечитаны BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112; Giving Ground, стр. 119; BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91. Книга задаёт порядок ходов, once-per-round usage и поражение Minion, но не технический лимит симулятора. ROUND_LIMIT не означает ничью или завершение боя по правилам. P1 policy не переносится.

## Контракты

`NpcRoundsRequest(current, spatial_state, max_rounds)` хранит immutable NpcRoundRequest и SpatialBattleState. Лимит — положительный int (bool запрещён); combat/spatial round numbers совпадают, каждый текущий участник имеет placement с canonical CombatSide.value.

Лимит считает посещённые номера раундов **включая текущий**. Частичный раунд использует одну позицию лимита. Уже завершённый входной раунд также учитывается, но повторно не исполняется: при max_rounds=1 результат сразу ROUND_LIMIT, при 2 можно перейти к следующему и сыграть его. Новый вызов имеет собственный лимит; общего накопленного бюджета боя нет. Caller, желающий сыграть ровно N новых раундов после complete snapshot, сначала явно выполняет advance либо учитывает этот snapshot в лимите.

`run_npc_rounds(request, candidates, next_rounds, rng, *, decisions=None)` последовательно вызывает существующий run_npc_round. Каждый переход к следующему раунду проходит через прежние advance_npc_round и apply_npc_round_advance. RNG/decisions передаются исходному executor; runner не бросает кубики самостоятельно и не создаёт action receipts.

`NpcRoundsCandidateProvider.get_candidates(context, spatial_state)` получает свежий NpcAttackSelectionRequest и актуальный spatial snapshot. На каждый раунд создаётся внутренний immutable adapter к прежнему NpcRoundCandidateProvider; после advance он привязан к новому spatial state. Provider может менять только candidates, что проверяет прежний coordinator. Range/awareness/modifiers по-прежнему внешние facts.

`NpcNextRoundProvider.get_next_round(current, spatial_state)` получает точный завершённый NpcRoundRequest и текущий spatial snapshot, возвращает прежний NpcRoundAdvanceRequest с явными next_round_participants/next_actor_order. Подмена current/history/pending/spatial отклоняется до advance. Состав не фильтруется автоматически; существующие guards требуют Minions обеих сторон без defeated и согласованные placements. Сохранённый side_order не заменяется выбором actor_order.

Provider следующего раунда не вызывается после достижения лимита или блокирующего outcome. Входные pending/defeated/complete не вызывают candidate provider или RNG. Broken/Defenceless и отсутствие кандидата возвращают прежний SELECTION_BLOCKED; неисполненный slot сохраняется. Уже исполненный slot после внешнего погашения pending закрывается прежним coordinator без повторной Attack.

## Результат и возобновление

`NpcRoundsResult(source_request, rounds, advances)` хранит прежние NpcRoundResult/NpcRoundAdvanceResult. Журнал содержит от 1 до max_rounds результатов и ровно на один advance меньше. Проверяются непрерывность source snapshots, отсутствие перехода после blocking outcome и завершение только на лимите либо явной остановке. Пустой, укороченный complete, переставленный или чужой журнал отклоняется; rules/RNG при валидации не запускаются.

Views current/spatial_state возвращают последние snapshots, completed_rounds — завершённые раунды из этого журнала, включая уже complete входной раунд. Outcome: ROUND_LIMIT, PENDING_FOLLOW_UPS, SELECTION_BLOCKED либо DEFEATED_ACTOR; точная причина выбора доступна в последнем round.blocked_selection. Это результат bounded orchestration, а не новый общий battle aggregate.

Caller хранит оба snapshots и журнал. После внешнего Give Ground/defeat acknowledgement/exclusion либо обновления контекста он создаёт новый NpcRoundsRequest с возвращёнными состояниями и явным новым лимитом. Runner не очищает pending, не выбирает форму поражения, не двигает бойцов автоматически и не назначает Run/Recover. Односторонний состав не запускает следующий round и не объявляет победителя.

Полный откат caller-owned snapshots не предотвращается. Ошибки callbacks, malformed provenance или reducers пробрасываются, без фиктивного успешного/blocked результата. Входные состояния immutable; RNG/decisions и внешние эффекты callbacks, уже использованные в ранних ходах, при исключении не откатываются.

## Проверки

10 unit tests в test_m2_npc_rounds_runner.py: лимит/types/spatial, начальные pending/defeated, Conditions обеих сторон, повторная остановка, complete input, plan/result source guards, malformed journals, exceptions, запрет одностороннего состава и defeated в следующем раунде.

4 integration tests в test_m2_npc_rounds_cycle.py: два реальных раунда при обоих side_order (8 kernel/receipts, 48 RNG вызовов), другой actor_order и spatial usage reset; сохранение трёх seeded prior histories и текущих Conditions; поздний NO_CANDIDATE/resume без повторения пяти прежних Attack; реальные Give Ground/Wound во втором раунде с остановкой без третьего; явно уменьшенный следующий состав без удаления roster entries. Сквозное внешнее погашение этих pending между несколькими вызовами runner проверено отдельным integration-срезом ниже. Полный набор: 1624 tests OK на Python 3.14.

## Сквозное погашение последствий и возобновление

Проверка 2026-09-28. Сквозное возобновление run_npc_rounds проверено в test_m2_npc_rounds_follow_up_cycle.py: 1 новый integration test / 6 сочетаний обоих side_order и трёх defeat dispositions. Реальная Attack → pending Give Ground → atomic movement/consumer → runner → Wound → typed acknowledgement/exclusion → runner до ROUND_LIMIT следующего раунда 2×1. Все три histories получены от реальных действий из пустых исходных историй; pending не очищается вручную. В каждом сочетании шесть kernel/receipts, 36 RNG вызовов, один movement/consumer, одно acknowledgement и один combat/spatial advance. Свежий spatial context передаётся автоматически после возобновления и advance; Conditions, placements и persistent side_order сохраняются, usage сбрасывается. Обе pending остановки не вызывают providers/RNG. Старые Attack/Give Ground/defeat/exclusion/advance отклоняются после следующего раунда, включая новые IDs и повторное добавление pending. Исходные snapshots неизменны. Production API не менялся; автоматический выбор последствий или победителя не добавлен. Полный набор: 1625 tests OK.

Непосредственно перечитаны BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112; Giving Ground, стр. 119; BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91. Новых архитектурных решений или трактовок правил нет. Caller явно задаёт Zone, approved disposition и следующий состав; тест использует прежний MixedCandidates с актуальным supplied spatial snapshot. После ROUND_LIMIT повторный вызов с complete input и лимитом 1 не исполняет действия.

Аудит 2026-09-28: [готовность M2](../audits/m2-readiness.md). Контракт runner не менялся. Зафиксирована необходимость отличать число complete snapshots от новых завершений и длину всей consumed history от Attack данного вызова. Следующий summary сохраняет эти различия; ни победа, ни конкретная форма defeat не выводятся из NpcRoundsOutcome.
