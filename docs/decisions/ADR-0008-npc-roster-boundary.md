# ADR-0008: состав NPC отдельно от общего состояния боя

Статус: принято, 2026-09-27.

## Контекст

K1 проверяет выбранную numeric Melee/Shooting атаку, Protection и injury pipeline. M2 должен различать несколько экземпляров одного NPC и несколько целей. Модели P1 не соответствуют книжным injury policies. Общий владелец всех состояний боя для этого первого шага не требуется.

Источники: BOOK-GM-GUIDE 1.1, Allies and Antagonists / Types of NPC, стр. 91–92; Understanding NPC Profiles, стр. 93; Brigands & Footpads, стр. 97. BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112; The Battlefield, стр. 114; Attack Tests, стр. 118. Сценка Skirmish in the Great Forest на стр. 113 — пример, не основание новых правил. Книга задаёт типы, стороны и профили; структура хранения ниже — архитектурное решение.

## Решение

- `NpcDefinition` — переиспользуемый supplied numeric профиль: ID и source Rule ID, injury policy/лимит, базовая Resilience, возможные `NpcAttackProfile` и `NpcProtectionProfile`. Это не полный каталог Special Abilities/Trappings.
- `NpcParticipantState` — отдельный immutable snapshot экземпляра: actor/definition IDs, существующая `CombatSide`, typed injury, фактически доступные attack IDs, текущая Resilience, явные weapon/shield facts.
- `NpcParticipantSnapshot` связывает definition/state; проверяет definition ID, доступные атаки, вид injury и совпадение лимита Wounds. `NpcRoster` хранит упорядоченный tuple таких пар, запрещает дубли actor IDs и разные определения с одним ID. Два участника могут использовать один и тот же definition, не разделяя изменения своего состояния.
- Первый срез принимает Minion, Brute, Champion и существующие numeric Melee/Shooting профили. Player и Monstrosity здесь отклоняются: для их включения нужны отдельные contracts. Поддержка kernel для этих policies от этого не меняется.
- Проекции `attack_snapshot(id)` и `protection_options(test_id_prefix)` создают существующие входы preparation без RNG. Test IDs защиты содержат actor ID и Skill. Definition/source Rule IDs остаются в roster; существующие preparation results caller сохраняет рядом. Нового executor, Rule ID для архитектурной операции или универсального языка правил нет.
- `turn_participant`/`turn_participants` используют `CombatTurnParticipant`, сохраняют порядок и не фильтруют участников. Roster может быть пустым или содержать одну сторону; требования запуска раунда остаются у `CombatRoundState`. Побеждённые участники могут оставаться в снимке. Проекция доступности не разрешает действие и не расходует slot.

## Границы

Текущая Resilience передаётся явно: она может отличаться от базовой после изменения shield/armour/effects. Контракт проверяет тип, но не вычисляет и не доказывает согласованность equipment facts. Protection экспортируется как базовый профиль; модификаторы Conditions, Wounds и ситуации обязан применить caller до preparation. Awareness, расстояния, Special Abilities, выбор цели/Skill и пригодность участника к действию также внешние. Сторона не задаёт автоматический запрет friendly fire.

IDs связывают значения внутри supplied snapshot, но не доказывают его актуальность относительно иной копии. Здесь нет result consumer, глобальной истории исполнения или защиты от отката snapshots. Для изменения состояния caller строит новую пару/roster, сохраняя остальные экземпляры. Slot, spatial, reload, Fate, daily Wounds и иные histories этим контрактом не объединяются.

Первый integration-сценарий использует четыре Brigand numeric профиля на двух сторонах, Axe/Warbow и Athletics 3d/2; Craven Opportunist не срабатывает. Проверяется выбор конкретной цели и независимость соседей после реального kernel result. Это не утверждение поддержки полного поведения Brigand.

## Проверка

`tests/unit/test_m2_npc_roster.py` — 10 тестов: independent instances, actor/source binding, injury policies, availability, immutable collections, unsupported inputs, explicit equipment/Resilience и проекция сторон.

`tests/integration/test_m2_npc_roster_preparation.py` — 3 теста: четыре участника → выбранная Attack/Protection → kernel, актуальная доступность и отказ подмены цели однотипным NPC. Основной сценарий проверяет Axe/Warbow × opposed/unopposed. Автоматическое применение kernel result в roster не реализовано.

## Уточнение: одно исполнение Minion Attack

Реализовано исполнение одной подготовленной Attack Minion по Minion через существующий execute_attack_action: npc_roster_attack_models.py и npc_roster_attack_execution.py. Source-bound request связывает roster/history, оба preparation results и полный AttackActionExecutionRequest. Preflight проверяет actor/side, доступность, Resilience, injury, Protection/equipment и отсутствие неподдержанных эффектов; turn/slot guards existing executor срабатывают до RNG. Единственный kernel/receipt возвращает новый roster: target injury перенесён, Close miss добавляет Staggered атакующему без эскалации. Result хранит полный executed_request, preparation/execution trace и разделяет handled AttackerStaggerRequest и pending follow-ups; Give Ground и ProfileStateChange остаются явными. Consumer требует exact предыдущий snapshot/history и дополняет consumed execution IDs; повтор с returned state отклоняется.

13 unit tests (включая 48 сочетаний Axe/Warbow × opposed/unopposed × miss/Staggered/Wound × исходный Staggered actor/target) и 2 integration tests последовательных ходов. Проверены единственный RNG/receipt, явные modifiers, повторный Staggered/Prone/Give Ground, stale inputs, replay при неизменном injury, чужой actor/slot/result, defeated участник и независимость соседей. Полный набор: 1516 tests OK.

Источники непосредственно сверены: BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112; Combat Actions, стр. 116; Attack Tests, стр. 118; Failed/Successful Attacks и Giving Ground, стр. 119; BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91; Understanding NPC Profiles, стр. 93; Brigands & Footpads, стр. 97.

`NpcRosterAttackState` хранит roster, ordered consumed execution IDs и acknowledged_defeat_execution_ids (подмножество consumed IDs для однократного подтверждения формы поражения Minion). Это не общий battle aggregate: round/slot остаётся отдельным `CombatRoundState`, spatial/reload/Fate/Aim histories не объединяются.

Caller заранее выполняет чистые NPC Attack и Protection preparations, затем передаёт их вместе с `AttackActionExecutionRequest`. Новый `NpcRosterAttackExecutionRequest` проверяет полное значение Attack, исходную доступность/профили, target injury и факты equipment/Defenceless из roster. Базовый Protection profile должен совпадать с definition; modifiers/quality остаются явными Test inputs. Выбор awareness/range и тактики не выводится автоматически. Резервирование и окончание хода выполняются прежними turn reducers; исполнение не закрывает ход автоматически.

`execute_npc_roster_attack` вызывает existing executor ровно один раз, сохраняет его result/receipt без пересоздания и записывает полный executed request. Одинаковые IDs не позволяют заменить source Axe на Warbow. Target injury уже применён kernel; roster переносит его без второго Wound/Condition исполнения. Промах в Close обрабатывает только собственный AttackerStaggerRequest, добавляя Staggered без repeated-Stagger policy. Исходный список follow-ups сохранён в execution.resolution.

`apply_npc_roster_attack_result(current, result)` возвращает result.state только для exact предыдущего roster/history. Результат также предоставляет `.state` как immutable view; чтение этого свойства не является ещё одним исполнением. Caller хранит одновременно returned roster/history и execution.state (round). Повтор исполнения блокируется consumed ID либо исполненным slot; повтор consumer — consumed ID. Откат обоих внешних snapshots этим локальным механизмом не предотвращается. При исключении входные immutable значения сохраняются, RNG/решения не откатываются.

Побеждённые участники исключены. Другие правила допуска к действию и контекстные модификаторы остаются caller-owned. Срез запрещает не-Minion actor/target, secondary attack effects, дополнительные kernel wound modifiers/negations/immunities/reactions; базовый ignores-armour из profile допустим. Defenceless цели берётся из roster, но наличие состояния не подменяет всю систему eligibility.

`pending_follow_ups` содержит все follow-ups, кроме уже перенесённого attacker Staggered. В частности, GiveGroundRequest ещё требует spatial исполнения и обновления usage; ProfileStateChangeRequest сохраняет уведомление о defeat и решение caller/GM о его форме. Нельзя интерпретировать готовый receipt как завершение всей очереди последствий. Автоматического исполнения или удаления pending requests нет.

Продолжение: [ADR-0009](ADR-0009-npc-attack-selection-policy.md) добавляет выбор одного подготовленного Minion Attack по явному порядку кандидатов. Контроллер не расширяет roster aggregate и не исполняет kernel; сохраняет pending consequences и сверяет актуальность снимков перед передачей прежнему executor.

Уточнение 2026-09-28: новый Attack result обновляет NpcRosterAttackState через replace и сохраняет acknowledged_defeat_execution_ids. Решение о форме поражения хранится в отдельном MinionDefeatAcknowledgementResult; caller сохраняет этот результат, а roster/history использует для следующего действия. [Контракт](ADR-0010-single-minion-round.md#подтверждение-формы-поражения-minion).
