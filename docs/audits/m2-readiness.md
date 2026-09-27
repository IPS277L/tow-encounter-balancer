# Аудит готовности M2

Дата: 2026-09-28. Основание: [roadmap](../roadmap.md), [аудит K1](k1-readiness.md), [ADR-0008](../decisions/ADR-0008-npc-roster-boundary.md), [ADR-0009](../decisions/ADR-0009-npc-attack-selection-policy.md), [ADR-0010](../decisions/ADR-0010-single-minion-round.md), [ADR-0011](../decisions/ADR-0011-bounded-minion-rounds.md), [трассировка](../rule-traceability.md). На начало аудита рабочее дерево чистое. Production-код и тесты не менялись.

## Вывод

**M2 в полном объёме roadmap не завершён; переход к M3 пока не подтверждён.** Работает ограниченный numeric Melee/Shooting Minion-сценарий: несколько участников и целей, обычная Attack, остановки на последствиях, внешние Give Ground/defeat acknowledgement/exclusion, явные следующие составы и несколько раундов. Сквозные детерминированные тесты доказывают перенос состояний и однократность действий в этой границе.

Из пяти пунктов roadmap два готовы в данном срезе, два частично готовы, multi-target/area orchestration в M2 не реализована. K1 содержит необходимые части, но их наличие не доказывает подключение к roster, controller и runner. Наличие Brute/Champion в определении roster также не означает возможность их исполнения.

Следующий production-срез — **типизированная сводка одного NpcRoundsResult**. Он закрывает первый самостоятельный пробел отчётности, не меняет боевую механику и не объявляет весь M2 завершённым. Полный набор при аудите: **1625 tests OK**, Python 3.14; Python 3.12 отсутствует.

## Непосредственно проверенные источники

Чтение выполнено по локальным extracted pages, не по changelog. Обозначения ниже включают редакцию; номера — печатные страницы.

| Источник | Глава и страницы | Что проверено |
| --- | --- | --- |
| BOOK-PLAYER-GUIDE 1.4 | Rules / Combat, 112 | Один полный ход каждому участнику, стороны и выбор порядка внутри стороны |
| BOOK-PLAYER-GUIDE 1.4 | Rules / Attack Tests / Giving Ground, 119 | Отход в соседнюю Zone от атакующего, один раз за раунд, Broken при враге в destination |
| BOOK-PLAYER-GUIDE 1.4 | Rules / Retreat, 120 | Явное решение группы, timing, Fate/цена и pursuit; отсутствие подходящей Attack не равнозначно Retreat |
| BOOK-PLAYER-GUIDE 1.4 | Rules / Conditions, 122–123 | Broken/Defenceless, ограничения и modifiers, prompted/end-turn Tests; Condition storage не исполняет все эффекты |
| BOOK-PLAYER-GUIDE 1.4 | Equipment / Ranged Weapons / Blunderbuss, 95 | Secondary Staggered вокруг поражённой цели, собственные range/bonus/reload; это конкретная модель, не общий AoE |
| BOOK-GM-GUIDE 1.1 | Allies and Antagonists / Types of NPC / Minions, 91 | Один Wound побеждает Minion; killed/knocked out/disarmed and forced to surrender выбирает атакующий с усмотрением GM |
| BOOK-GM-GUIDE 1.1 | Allies and Antagonists / Brutes, Champions, Monstrosities, 92 | Различные injury policies; Champion Wounds Table, Brute несколько Wounds, Monstrosity отдельные атаки/реакции |
| BOOK-GM-GUIDE 1.1 | Allies and Antagonists / Understanding NPC Profiles, 93 | Одна обычная атака из доступных, Range/Protection/equipment, изменения профиля по Wounds |
| BOOK-GM-GUIDE 1.1 | Allies and Antagonists / Brigands & Footpads / Brigand, 97 | Numeric Axe/Warbow/Protection и отдельная Craven Opportunist Ability |

## Матрица пяти пунктов roadmap

| Пункт | Реализация и свидетельство | Статус | Книжная граница |
| --- | --- | --- | --- |
| Несколько бойцов с обеих сторон | [NpcRoster](../../src/towr/domain/npc_roster_models.py), [NpcRoundRequest](../../src/towr/domain/npc_round_models.py), [runner](../../src/towr/engine/npc_rounds_runner.py); [roster tests](../../tests/unit/test_m2_npc_roster.py), [2×2 → 2×1 и внешние последствия](../../tests/integration/test_m2_npc_rounds_follow_up_cycle.py) | **Готово для Minion-среза.** Независимые экземпляры, persistent side order, завершённые/excluded ходы и явный следующий состав. Не все injury policies исполняются | PG 1.4, Rules / Combat, 112; GM 1.1, Allies and Antagonists / Types of NPC, 91–93 |
| Контроллеры выбора действия и цели | [select_npc_attack](../../src/towr/engine/npc_attack_controller.py), [round coordinator](../../src/towr/engine/npc_round_coordinator.py); [controller tests](../../tests/unit/test_m2_npc_attack_controller.py), [Condition guards](../../tests/unit/test_m2_npc_attack_conditions.py) | **Частично.** Первый допустимый Attack/target по supplied порядку. Нет выбора между Attack/Recover/Manoeuvre и др., автоматической оценки тактики или полного набора eligibility/modifiers | GM 1.1, Allies and Antagonists / Understanding NPC Profiles, 93; PG 1.4, Rules / Combat, 112; Conditions, 122–123. Порядок предпочтения — policy, не правило книги |
| Несколько различных целей | [source-bound roster Attack](../../src/towr/domain/npc_roster_attack_models.py); [подготовка четырёх участников](../../tests/integration/test_m2_npc_roster_preparation.py), [mixed cycle](../../tests/integration/test_m2_mixed_round_cycle.py), [runner cycle](../../tests/integration/test_m2_npc_rounds_cycle.py) | **Готово для последовательных одиночных Attack.** Actor/target IDs связаны с snapshots, несвязанные участники сохраняются. Это не одновременное поражение нескольких целей | GM 1.1, Allies and Antagonists / Understanding NPC Profiles, 93; Brigands & Footpads, 97 |
| Книжные multi-target и area через конкретные профили/Hazards/secondary effects | K1: [secondary targets](../../src/towr/rules/secondary_target_resolution.py), [Zone Hazard](../../src/towr/rules/zone_hazard_resolution.py), [secondary tests](../../tests/unit/test_k1_secondary_target_resolution.py), [effects](../rules/special-effects.md). M2 controller выдаёт UNSUPPORTED_EFFECTS, roster executor запрещает secondary_effects; [negative test](../../tests/unit/test_m2_npc_attack_controller.py) test_extra_attack_effects_are_skipped_instead_of_silently_dropped | **Не реализовано в M2**, K1-части готовы. Нет M2 batch application в roster с единым источником и последующими pending. Нельзя снять guard без подключения потребителей | PG 1.4, Equipment / Ranged Weapons / Blunderbuss, 95; GM 1.1, Allies and Antagonists / Monstrosities, 92. Каждый эффект задаёт свой target set/Tests/order |
| Расширенные результаты одного боя | [NpcRoundsResult](../../src/towr/domain/npc_rounds_models.py) хранит source, rounds/advances, snapshots и stop reason; [journal tests](../../tests/unit/test_m2_npc_rounds_runner.py). [BattleResult](../../src/towr/domain/results.py) и [BattleEngine](../../src/towr/engine/battle.py) относятся к P1 | **Частично.** Есть проверенный журнал одного bounded вызова; нет компактной сводки его метрик, полного отчёта через external resume и контрактов завершения книжного боя/целей сценария. Нет оснований использовать P1 survived/winner как M2 данные | PG 1.4, Rules / Combat, 112; Retreat, 120; GM 1.1, Allies and Antagonists / Minions, 91. Лимит симулятора — техническая настройка |

## Границы, которые нельзя потерять при расширении

| Область | Что фактически есть | Что остаётся |
| --- | --- | --- |
| Brute/Champion | NpcDefinition/NpcParticipantSnapshot допускают обе policy. K1 [injury tests](../../tests/unit/test_k1_injury_resolution.py) проверяют Brute Wounds/extra dice и Champion Wounds Table | M2 request/controller/round требуют MINION. Нужны перенос injury/effects, изменение профильных свойств, completion/следующие последствия и guards для выбранного расширяемого среза. GM 1.1, Allies and Antagonists / Brutes, Champions, 92; Understanding NPC Profiles, 93 |
| Player/Monstrosity | K1 имеет injury/action/reaction primitives | NpcDefinition их явно отклоняет. Multi-attack Monstrosity нельзя выдать как несколько обычных STANDARD Attack. GM 1.1, Allies and Antagonists / Monstrosities, 92 |
| Conditions | Actor Broken/Defenceless запрещают обычную Attack; Staggered и target Defenceless участвуют в текущем path. K1 имеет другие reducers | M2 не выводит все modifiers из Conditions, не выполняет end-turn Ablaze/Critically Injured, Run/Recover или их выбор. Переданный Prone/Drained/Blinded не доказывает корректность Test без supplied effects. PG 1.4, Rules / Conditions, 122–123 |
| Range/awareness/Abilities | Provider получает свежие roster/round/spatial; проверяется source, а не истинность всех facts | Нет общего расчёта awareness/outnumbering/equipment. Numeric Brigand fixtures не подтверждают полную Craven Opportunist; GM 1.1, Brigands & Footpads, 97. Профильная Ability не появляется от совпадения имени оружия; Understanding NPC Profiles, 93 |
| Внешние решения | Give Ground, acknowledgement, exclusion и новый состав имеют typed границы и replay guards; [сквозной тест](../../tests/integration/test_m2_npc_rounds_follow_up_cycle.py): 6 сочетаний, 6 Attack, 36 RNG, одно движение/advance | Нужны явно заданные воспроизводимые policies для самостоятельной симуляции. Текущие остановки корректны; автоматически подставлять skip/Recover или очищать очередь нельзя. PG 1.4, Rules / Giving Ground, 119; GM 1.1, Allies and Antagonists / Minions, 91 |
| Defeat и исход боя | defeated отражает принятую Wound; [acknowledgement result](../../src/towr/domain/minion_defeat_models.py) хранит disposition. Roster history хранит ID подтверждения | defeated не означает killed. NpcRoundsResult сам не содержит внешних acknowledgement results и не восстановит выбранный disposition по ID. Отсутствие обеих сторон запрещает advance; победителя этот отказ не определяет. GM 1.1, Allies and Antagonists / Minions, 91; PG 1.4, Rules / Retreat, 120 |
| Возобновление и счётчики | completed_rounds включает complete input; consumed histories могут содержать действия до вызова. Начальные pending не исполняют действий | Длина истории не равна числу Attack данного вызова; число complete snapshots не равно числу вновь завершённых раундов. Полный откат snapshots не защищён, RNG при исключении не откатывается. Это границы API, не правила книги |

## Остаток M2 и критерии перехода к M3

Порядок M2 → M3 → M4 → M5 сохраняется. Ни полный каталог книг, ни новые комбинации Aim не становятся дополнительным условием. Для каждого заявленного сценария вход должен либо иметь реализованный путь всех обязательных правил, либо явно отклоняться; supplied facts допустимы, их обязательства нужно перечислить.

До подтверждения перехода остаются следующие конечные критерии:

1. **Отчётность:** сводка bounded вызова, затем проверяемая композиция вызовов и внешних результатов без двойного счёта; terminal outcome сценария отделён от limit/pending/unsupported. Wounds, defeated и конкретная форма поражения не смешиваются. Нельзя получить вероятность победы из частоты ROUND_LIMIT.
2. **Замкнутый заявленный сценарий:** явные воспроизводимые policies для targets/порядка/повторного Staggered/Give Ground/defeat/следующего состава; обработка окончательного состава и цели столкновения. Unsupported сценарии имеют отдельный исход/отказ, а не тихую замену правил. Выбор objectives/policy нельзя вывести из книги единой формулой.
3. **Выбор действий и Conditions:** подключить необходимые для заявленных профилей non-Attack ветви и end-turn/effective effects либо ограничить входы. Нынешний Attack-only provider не считается универсальным action controller.
4. **Multi-target/area:** подключить конкретный книжный эффект к M2 roster/очереди, проверить всех затронутых участников, порядок Tests/RNG и однократное application. В матрице отдельно отметить multi-target и area; одна проверка обычного target switching не закрывает этот пункт. Универсальный AoE не требуется.
5. **Типы/профили:** задать поддержанный набор для первого M3; Brute/Champion/Monstrosity не включать в него лишь потому, что K1 или roster их знает. Для фактически заявленных типов нужны integration cycles, в остальных случаях — явный отказ. Полный каталог не требуется.

Это технические критерии проверки исходного roadmap, не новые house rules. До их закрытия допустимы измерения bounded прогонов, но они не являются завершённой массовой симуляцией исходов боя. Monte Carlo, параллелизм, CLI и балансировщик остаются последующими этапами.

## Следующий законченный production-срез

Добавить immutable `NpcRoundsSummary` и чистую `summarize_npc_rounds(result)` для **одного** проверенного NpcRoundsResult. Отдельный report module зависит от domain; он не вызывает runner/rules/RNG и не становится владельцем состояния. Точная структура нового публичного контракта документируется при реализации.

Критерии приёмки:

- Source-bound сводка сохраняет NpcRoundsOutcome, точную blocked reason при наличии и число текущих pending; не добавляет winner/draw/survived/disposition.
- Разделяет начальный/конечный номер раунда, число посещённых результатов, число вновь завершённых раундов и число Attack, реально выполненных этим вызовом. Complete input даёт 0 новых завершений/Attack. Ранее начатый, но завершённый в вызове раунд даёт одно новое завершение. Attack считаются по NpcRosterAttackExecutionResult в journal, не по длине общей history.
- Итоговые записи охватывают уникальных участников посещённых раундов в стабильном порядке первого появления, включая defeated/excluded; случайные дополнительные entries roster не объявляются участниками прогона. Для Minion выводятся actor ID, сторона, конечные Wounds/defeated/Conditions. Это конечное состояние, не число новых ран за вызов.
- Проверки на обоих side_order: два полных раунда, complete input, начальные pending/defeated, blocked/partial resume и реальные внешние последствия из existing integration. Три вызова mixed cycle дают соответственно 1, 1 и 4 новых Attack; исторические IDs не увеличивают эти значения. Само построение сводки не расходует RNG и не меняет snapshots.
- Типы и source binding проверяются. Полный encounter report через несколько вызовов, acknowledgement dispositions, статистика, JSON/CLI, winner policy и автоматическое погашение pending остаются за рамками этого среза.

Источники для семантики полей: BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112; BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91. Разделение observed/newly completed — техническое следствие ADR-0011. Полная отчётность M2 этим первым summary ещё не закрывается.

## Проверки аудита

Повторно выполнен полный `py -3.14 -m unittest discover -s tests -v` с `PYTHONPATH=src`: **1625 tests OK**. Новых тестов в документационном аудите нет. Compileall, локальные ссылки и `git diff --check` успешны. Ссылки таблиц ведут к фактическим contracts/tests, существующие отрицательные проверки использованы как доказательство границ. Новых неоднозначностей правил не найдено; прежние вопросы в [open-questions](../open-questions.md) сохраняются.
