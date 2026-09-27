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
