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

## Сводка одного вызова runner

Уточнение 2026-09-28. Источники непосредственно перечитаны: BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112; BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91. Нового игрового правила нет.

domain/npc_rounds_summary_models.py содержит frozen/slotted NpcRoundsSummary(source_result) и NpcRoundsParticipantSummary(actor_id, side, wounds, defeated, conditions). engine/npc_rounds_reporting.py предоставляет summarize_npc_rounds(result); модуль зависит только от domain и не вызывает runner/rules/RNG.

Source_result обязан быть готовым NpcRoundsResult. Метрики сводки — вычисляемые read-only properties, а не независимо supplied поля: outcome, blocked_reason, pending_follow_up_count, initial_round_number, final_round_number, visited_round_count, newly_completed_round_count, executed_attack_count, participants. Поэтому нельзя подставить метрику от другого source; replace(source_result=...) создаёт проекцию нового результата. Повторное чтение/построение разрешено и ничего не погашает.

Visited — число round results; newly_completed — только COMPLETE результаты, source которых ещё не round_complete. Это учитывает завершение частичного входного раунда, но исключает уже complete input. Executed Attack — число NpcRosterAttackExecutionResult в steps данного вызова, без подсчёта прежних consumed IDs. Точные outcome/blocked reason и размер последней pending queue сохраняются; счётчик не означает число unique видов последствий.

Participants объединяет IDs из source round participants всех посещённых раундов в порядке первого появления в этих tuples, а не actor_order/порядке ходов. Значения side/Wounds/defeated/Conditions берутся из последнего roster. Defeated/excluded сохраняются; extra roster entries, не участвовавшие ни в одном посещённом раунде, исключаются. Wounds — конечное число, не delta. Record проверяет ID, типы и неотрицательный integer wounds; исходный M2 journal гарантирует Minion policy участников. Победа, смерть, survived и выбранная форма поражения не выводятся.

7 новых unit tests: оба side_order, два раунда с абсолютными номерами 7–8 и старой history, complete input, все остановки/точные причины, новый/исключённый участник, стабильный порядок и неучаствующие entries, source/type/immutable guards. Расширены два integration tests: partial resume даёт 5/3 Attack и 1/1 новых завершений; реальный mixed cycle — 1/1/4 Attack, 0/0/2 новых завершений, обе стороны × три dispositions, без дополнительных RNG/kernel/receipt. Полный набор: 1632 tests OK на Python 3.14. Общий отчёт цепочки внешних переходов остаётся следующим срезом.

## Отчёт цепочки возобновлений

Уточнение 2026-09-28. Непосредственно перечитаны BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112; Giving Ground, стр. 119; BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91. Новых игровых правил нет.

`NpcRoundsChainSummary(source_steps)` в domain/npc_rounds_chain_summary_models.py и `summarize_npc_rounds_chain(steps)` в engine/npc_rounds_reporting.py принимают конечный ordered tuple из пяти существующих типов: NpcRoundsResult, NpcGiveGroundConsumptionResult, MinionDefeatAcknowledgementResult, NpcRoundExclusionResult, NpcRoundAdvanceResult. Это закрытый набор completed результатов, не универсальная шина событий. Вход преобразуется в tuple; источники сохраняются полностью.

Непустая цепочка начинается и заканчивается NpcRoundsResult. Начальные current/spatial берутся из первого source_request. До выдачи метрик конструктор проверяет каждый следующий source на точное равенство current (включая roster/history/round/pending/ID/order); runner, Give Ground и advance также требуют точный spatial. Acknowledgement и exclusion spatial не меняют. Следующие снимки читаются из existing result views; exclusion проецирует round_state в прежний current. Rules, apply-consumers, runner и RNG не вызываются. Пропуск, перестановка, повтор state-changing перехода или чужой source отклоняется. Повторный no-op допустим: он не добавляет Attack/новых завершений. Подлинность внешнего исполнения или полный откат всех caller-owned снимков этот read-only контракт не доказывает.

`call_summaries` сохраняет порядок NpcRoundsSummary; `final_summary`, current/spatial_state, outcome/blocked_reason/pending_follow_up_count относятся к последнему runner result. Поэтому хвост из внешних переходов без повторного наблюдения runner не принимается: старая остановка не выдаётся за текущую. `initial_round_number`/`final_round_number` — абсолютные номера, `visited_round_count` — число разных номеров среди вызовов, а не сумма посещений при resume. `executed_attack_count` и `newly_completed_round_count` — суммы соответствующих call summaries; старые histories и complete input не учитываются заново. Новые завершения означают завершения **runner**, не внешним exclusion; если exclusion сам завершил раунд, следующий complete input не добавляет завершение runner.

`participants` — union посещённых составов в порядке первого появления с состояниями из конечного roster, включая участников только ранних вызовов и defeated/excluded; не участвовавшие roster entries не добавляются. `defeat_acknowledgements` возвращает полные MinionDefeatAcknowledgementResult в порядке цепочки: disposition, attacker/target, GM approval и исходная Attack доступны через source_request. Старые acknowledged IDs без результата не восстанавливаются в решения. Нет winner/draw/survived, автоматического выбора целей или погашения pending.

7 unit tests в test_m2_npc_rounds_chain_summary.py проверяют explicit advance, обе стороны, предыдущие истории/complete input, непрерывность current/spatial, replay, no-op/blocked resume, точные причины остановки, участников ранних составов и immutable/source guards. Existing mixed integration дополнен отчётом 1/1/4 Attack, 2 новых завершений, 2 уникальных раундов и одним явным defeat acknowledgement для обеих сторон × трёх dispositions; каждый внешний переход обязателен, source snapshots и прежние kernel/consumer/RNG counts сохранены. Полный набор: 1639 tests OK на Python 3.14.
