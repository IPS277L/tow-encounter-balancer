# Раны и состояния

Источник: `BOOK-PLAYER-GUIDE`, преимущественно страницы 119–123 и 190–191. Статус: Staggered, базовая Wound policy и эффекты строк таблицы `implemented` в K1; исполнение внешних последствий и Recover остаются `draft`.

## RULE-HEALTH-001 — Resilience

Resilience обычно равен Toughness с добавлением защиты брони, щитов и других Abilities. Эффект, игнорирующий броню, уменьшает Resilience до Toughness для конкретной атаки.

Источник: страницы 97, 119.

## RULE-HEALTH-002 — результат Damage

- `Damage > Resilience` наносит Wound.
- `Damage <= Resilience` накладывает Staggered.

Источник: страница 119.

## RULE-HEALTH-003 — повторный Staggered

Если уже Staggered персонаж снова должен получить это состояние, он выбирает один допустимый результат:

- Give Ground в соседнюю Zone, не чаще одного раза за раунд;
- получить Prone;
- получить Wound.

Если персонаж уже Prone, повторно выбрать Prone нельзя. Ограничения позиции могут запретить Give Ground. Если допустимым остаётся только Wound, персонаж получает Wound.

Источник: страницы 119–120, 122–123.

## RULE-HEALTH-004 — взаимодействие Wound и Staggered

Получение Wound немедленно удаляет Staggered. Если Wound позднее отменён через Near Miss, ранее имевшийся Staggered сохраняется.

Источник: страницы 112 и 121.

## RULE-HEALTH-005 — Wounds игроков и Champions

При каждом Wound бросается один d10 плюс ещё один d10 за каждую уже имеющуюся untreated Wound; результаты суммируются и определяют эффект по таблице Wounds. Результат может создать временные или постоянные последствия, состояние Critically Injured, Defenceless либо смерть.

Источник: страницы 121, 190–191.

## RULE-HEALTH-006 — типы NPC

- Minion побеждён после одного Wound.
- Brute имеет профильное число Wounds и собственные последствия, не используя общую таблицу.
- Champion получает Wounds как персонаж игрока и использует таблицу.
- Monstrosity имеет профильное число Wounds и профильные реакции на них.

Источник: страница 191. Полные правила NPC находятся в Gamemaster’s Guide и отсутствуют в текущем источнике.

## RULE-HEALTH-007 — Treatment и Healing

Treatment помечает Wound treated: она больше не добавляет `+1d` к будущей Wounds Table, а её эффекты `until treated` прекращаются. В бою Recover лечит одну Wound персонажа или союзника Close через Recall; Anatomy Lore даёт auto-success, а специальный Lore может сделать то же для конкретной Wound. Нужны подходящие trappings; поиск импровизированных supplies может потребовать Survival/Awareness. После боя при безопасной передышке все Wounds автоматически treated.

Healing удаляет все непостоянные эффекты Wound после указанной длительности: Catch Your Breath, A Night’s Respite либо Rest and Recovery; surgery-required Wound не начинает recovery до операции. При существенном deadline GM может разрешить Endurance для досрочного healing.

Источник: страницы 118, 121–123.

## RULE-HEALTH-008 — общая семантика Conditions

Одновременно бывает не более одного экземпляра каждого Condition. Если effect предлагает выбор нескольких Conditions, уже имеющееся выбрать нельзя. Повторное получение обычно ничего не добавляет, кроме прямо описанных исключений: Staggered запускает выбор последствий, Distracted заменяет прежний объект отвлечения новым.

Condition от ongoing cause нельзя снять, пока не устранена причина. Test на снятие выполняется как Recover; за один Recover можно Test снять только одно Condition либо Treat одну Wound.

| Condition | Effect | Removal |
|---|---|---|
| Ablaze | end turn Endurance против fire Hazard (2) | Athletics stop/drop/roll либо water |
| Blinded | visual Tests Grim; полностью sight-only Tests auto-fail | Awareness либо удалить blindfold/source Wound |
| Broken | turn тратится на максимально быстрое движение в Zone без врага; Recover только там | Willpower либо Leadership другого |
| Burdened | Manoeuvre запрещён | Brawn либо убрать груз/причину |
| Critically Injured | end turn Endurance; провал даёт Defenceless, повтор при Defenceless убивает | Treat source Wound через Recall |
| Deafened | не слышит, Help запрещён, hearing-only Tests auto-fail, hearing abilities не действуют | Awareness либо убрать источник/подождать |
| Defenceless | нет movement/actions/opposition; только prompted Tests; successful attack всегда Wound | зависит от источника |
| Distracted | `-1d` ко всему, не сфокусированному на объекте отвлечения | Willpower в бою либо исчезновение/поражение объекта; повтор заменяет объект |
| Drained | нельзя получать bonus dice; Glorious только от Fate; penalties/Grim сохраняются | Endurance для краткого либо отдых/устранение причины |
| Prone | Melee по цели `+1d`, Shooting `-1d`, dismount, нельзя покинуть Zone | Recover либо free move без enemy Close |
| Staggered | повтор запускает Give Ground/Prone/Wound | Recover либо получение Wound |

Источник: страницы 122–123. `ConditionState` хранит все 11 значений, но generic application не исполняет turn/action ограничения из таблицы.

## RULE-HEALTH-009 — Infection и Festering Wounds

В конце дня, когда персонаж получил хотя бы одну Wound (даже уже treated/healed), он делает Endurance Test. Если successes меньше числа Wounds, полученных в этот день, добавляется Festering Wound. Она считается untreated для `+1d`, не может быть treated и лечится только Rest and Recovery.

Перед этой Test персонаж с Anatomy Lore может сделать Recall; каждый success позволяет ему выбрать себя или союзника для автоматического успеха против Infection.

Источник: страница 122. Требует day/campaign tracking, которого сейчас нет.

## RULE-HEALTH-010 — Surgery

Surgery для отмеченных Wounds требует Anatomy Lore, подходящие facilities/tools/time и Dexterity Test; провал рискует disfigurement/death, а даже успех оставляет указанное Wound permanent consequence. Обычная процедура происходит во время Rest and Recovery; Talent Combat Surgeon отдельно задаёт battle Exacting Dexterity (8), одна Test за action.

Источник: страницы 122 и 74. Общего surgery resolver пока нет.

## Реализация Staggered в K1

- состояние и запросы: `src/towr/domain/condition_models.py`;
- чистый reducer: `src/towr/rules/stagger_resolution.py`;
- детерминированные проверки: `tests/unit/test_k1_stagger_resolution.py`.

Первое получение добавляет Staggered без решения. Повторное вычисляет только допустимые варианты с учётом Prone, возможности покинуть Zone и уже использованного Give Ground. При нескольких вариантах требуется явный `StaggerDecisionProvider`; если допустим только Wound, запрос раны создаётся автоматически. Чистый `resolve_stagger` только выбирает исход состояния, а общий `resolve_stagger_impact` передаёт Wound соответствующей injury policy и применяется как основной kernel, так и executor вторичных целей.

## Реализация Wounds Table в K1

- модели состояния, записи раны и решений: `src/towr/domain/injury_models.py`;
- нормативная карта результатов `1–27+`: `src/towr/rules/wound_table.py`;
- Player/Champion и профильные NPC policies: `src/towr/rules/injury_resolution.py`;
- сквозные проверки: `tests/unit/test_k1_injury_resolution.py` и `tests/unit/test_k1_kernel.py`.

Player и Champion используют одну policy. Для обычной Wound число кубов равно `1 + untreated Wounds + modifiers`, минимум один. Hazard передаёт вместо базовой единицы свой положительный shortfall; остальные слагаемые и минимум не меняются. Принятая Wound записывает исходные d10 и сумму, удаляет прежний Staggered и отмечает смертельные результаты `24+`. Near Miss и аналогичные доступные отмены выбираются после броска; при отмене исходное состояние, включая Staggered, сохраняется, а расход Fate или другого источника возвращается как `ConsumeWoundNegationRequest`.

Каждая принятая рана создаёт `WoundEffectRequest` с конкретным `WoundEntryId`. Специализированный reducer исполняет его ровно один раз внутри kernel и записывает `effect_resolved` в рану.

Условия и ограничения хранятся как типизированные `WoundConditionEffect` и `WoundRestrictionEffect` со ссылкой на номер раны и одним из сроков действия: до конца следующего хода, до явного снятия, до лечения, до полного заживления, до следующей проверки либо постоянно. Благодаря этому будущий Recover сможет удалить только эффекты нужного источника, не стирая такое же Condition от другой раны или способности.

Строки `4`, `5`, `7`, `11`, `12` и `19` создают `WoundEnduranceTestRequest`. Профиль Endurance берётся orchestration-слоем из определения персонажа; `resolve_wound_endurance_test` принимает обычный `TestResult` и либо сохраняет состояние, либо применяет Condition/создаёт конкретный внешний consequence. Случайные предметы, зубы, пальцы, глаза и конечности представлены `WoundConsequenceRequest`, поскольку injury state намеренно не содержит анатомию и инвентарь.

Для `Spilling guts` возвращается явный `WoundChoiceRequest`: персонаж либо роняет предмет и зажимает рану, либо становится Defenceless. Скрытого default нет. Фактическое изменение инвентаря, случайный выбор стороны тела, снятие эффектов по времени/Treat/Heal и особая Endurance-защита после заживления `Ruptured organs` требуют будущего battle/application orchestration.
