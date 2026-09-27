# ADR-0009: выбор NPC Attack по явно заданному порядку

Статус: принято, 2026-09-27.

## Контекст

Roster M2 и executor одной Minion Attack уже отделяют профиль от экземпляра, проверяют source/slot и сохраняют follow-ups. Следующий контроллер должен выбрать одну атаку и цель среди нескольких supplied вариантов. Оптимизация урона, вывод awareness и общий battle loop для этого не требуются.

Источники: BOOK-GM-GUIDE 1.1, Allies and Antagonists / Understanding NPC Profiles, стр. 93; BOOK-PLAYER-GUIDE 1.4, Equipment / Ranged Weapons, стр. 94; Rules / Combat, стр. 112; Range, стр. 114; Attack Tests, стр. 118–119. Эти страницы ограничивают доступные атаки/защиту и порядок исполнения, но не задают рейтинг целей по эффективности. Первый допустимый вариант в порядке caller — политика контроллера, не house rule или нормативное правило книги.

## Решение

`domain/npc_attack_selection_models.py` содержит immutable `NpcAttackCandidate`, `NpcAttackSelectionRequest/Result`, типизированные причины глобального отказа и пропуска кандидата. `engine/npc_attack_controller.py` реализует `select_npc_attack` и проверку актуальности перед передачей результата исполнителю. Домен не импортирует engine/rules; controller зависит от прежних preparation functions. RNG у выбора отсутствует.

Кандидат задаёт attack profile ID, target ID, Range, any-enemy-Close, GM range approval, awareness, выбранный Protection Skill, готовые Protection Test options, attack DiceModifiers и факты Give Ground. Defenceless, текущая Resilience, Staggered actor и equipment берутся из переданного roster. Кандидаты передаются в порядке предпочтения; состав/порядок списка — решение caller. Одноимённые NPC не заменяют друг друга; исходный список не сортируется.

Request связывает roster/history, текущий round, active actor, уже резервированный slot и явно переданную очередь pending follow-ups. Неизвестные actor/target/profile IDs, чужая Protection, подменённый базовый Test profile, дубли и некорректные типы — ошибки входа, даже если они находятся после первого допустимого кандидата. Пригодность всех supplied snapshots вне этой boundary не доказывается.

Глобальные блокировки проверяются до подготовки: pending follow-ups, отсутствующий/чужой активный ход, unsupported или defeated actor, отсутствующий/неподходящий/уже исполненный slot, предыдущий незавершённый slot и consumed execution ID. Непустая pending queue — предусловие этого контроллера, не новое книжное запрещение действий. Controller не подтверждает последствия и не очищает очередь самостоятельно.

Кандидаты проверяются последовательно: доступность атаки, distinct target, Minion policy, defeated/отсутствующая в текущем round цель, отсутствие secondary attack effects. Дальность и Protection проверяют существующие constructors/preparations. `ValueError` только от двух известных context constructors превращается в `ATTACK_CONTEXT`/`PROTECTION_CONTEXT` с диагностикой. `TypeError`, ошибки provenance и неожиданные ошибки preparation functions не маскируются под отсутствие атаки. Диагностический текст не разбирается программно; enum определяет категорию отказа.

Первый допустимый вариант даёт `NpcRosterAttackExecutionRequest`, пригодный для прежнего `execute_npc_roster_attack`. Результат хранит исходный запрос, выбранного кандидата, отвергнутый префикс списка и обе preparation traces внутри executable request. ID исполнения — selection request ID с суффиксом `:execution`; один ID выбора обозначает одно исполнение, не новую попытку. Без подходящего варианта возвращается `NO_CANDIDATE`, без executable request и без расхода slot/RNG. Никаких fallback Recover/skip-turn нет.

`require_current_npc_attack_selection` перед передачей в executor требует exact текущие roster/history, round и pending queue. После изменения любого из них нужен новый выбор. Сама функция не исполняет атаку и возвращает уже подготовленный request. Caller сохраняет result.state, execution.state и pending follow-ups старого executor. Повторный выбор с returned history/исполненным slot блокируется; откат всех внешних snapshots по-прежнему вне локальной защиты. Прямое использование низкоуровневого executor не заменяет проверку актуальности выбора.

## Границы

Поддержаны обычные numeric Melee/Shooting Minion-versus-Minion атаки. Extra effects/Abilities, Player/Brute/Champion/Monstrosity execution, reload lifecycle, автоматическая геометрия, awareness и effective modifiers не добавлены. Protection Tests сохраняют supplied dice/quality/success/reroll inputs; attack preparation пока принимает только свой существующий DiceModifier contract. Selection не выбирает Skill защиты вместо caller. Сторона сама по себе не запрещает friendly fire: caller задаёт список разрешённых целей. Проверка defeated не заменяет всю книжную eligibility по Conditions и сценарию.

## Проверка

13 unit tests в `test_m2_npc_attack_controller.py`: порядок вопреки большей Damage альтернативы, причины пропуска/отказа, pending/slot/history, source/type guards, exact handoff, modifiers/quality и propagation неожиданных ошибок.

3 integration tests в `test_m2_npc_attack_controller_execution.py`: восемь сочетаний Axe/Warbow × opposed/unopposed × hit/miss при нескольких целях, единственный kernel/receipt и целевой injury; реальная returned history после ranged miss; сохранение настоящего Give Ground и блокировка следующего выбора. Полный набор: 1532 tests OK на Python 3.14.

## Запрет Attack по Conditions атакующего

Уточнение 2026-09-28. Источники непосредственно перечитаны: BOOK-PLAYER-GUIDE 1.4, Rules / Conditions / Broken, стр. 122; Defenceless, стр. 123; Giving Ground, стр. 119.

Общий domain helper npc_attack_blocking_condition в npc_roster_attack_models.py проверяет текущие actor Conditions. select_npc_attack возвращает ACTOR_DEFENCELESS либо ACTOR_BROKEN до подготовки кандидатов, включая пустой список. При сочетании выбирается Defenceless; это только приоритет диагностики, оба состояния запрещают Attack. Прежние pending/turn/unsupported/defeated guards имеют приоритет. Target Conditions не блокируют actor: Defenceless цели по-прежнему обрабатывается прежней Protection preparation.

validate_npc_roster_attack использует тот же helper при создании NpcRosterAttackExecutionRequest и повторно перед execute_attack_action. Явная preparation/candidate не обходит запрет. Отказ прямого запроса — ValueError до RNG, decisions, kernel и receipt. Проверка актуальности selection продолжает сравнивать весь snapshot: изменение Conditions требует нового выбора.

Coordinator возвращает SELECTION_BLOCKED с новым typed reason; резервированный slot остаётся неисполненным, state/history/Conditions не меняются. Повторный запуск без снятия Condition снова останавливается без повторной reservation. Это ограничение обычной Minion Attack; автоматический Run/Recover, поиск безопасной Zone и другие Condition modifiers не добавлены. Снятие Condition и актуальность внешнего состояния остаются ответственностью caller.

6 новых unit tests в test_m2_npc_attack_conditions.py покрывают оба Conditions/сочетание, обе стороны, пустые/явные candidates, pending/defeated priority, direct request/executor revalidation, stale selection, новые допустимые snapshots после внешнего снятия, target Conditions и повторную остановку coordinator. Три прежних integration tests Give Ground теперь используют provider без фильтра Broken: отказ делает controller, один movement и прежние числа kernel/RNG сохранены. Полный набор: 1610 tests OK на Python 3.14.
