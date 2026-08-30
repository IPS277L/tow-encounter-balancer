# Раны и состояния

Источник: `BOOK-PLAYER-GUIDE`, преимущественно страницы 74, 110, 119–123, 136 и 190–191. Статус: Staggered, базовая Wound policy, эффекты строк таблицы, Recover treatment, три healing tiers, ordinary downtime surgery и Combat Surgeon battle proof для строк `20–23`, обе rules-boundaries Combat Surgeon и suppression aggregate/effective view implemented в K1; остальные внешние последствия, Infection state и применение риска остаются partial/draft.

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

Если правило вместо броска прямо назначает конкретную строку Wounds Table, K1 сохраняет `FIXED_ENTRY` без синтетических d10. Такая Wound всё равно проходит отдельную pending → completion границу, чтобы сначала попасть в дневной журнал и лишь затем применить эффект. Near Miss для неё не открывается: правило Fate на странице 112 требует решения после фактического броска по Wounds Table.

Источник: страницы 112, 121, 159, 190–191.

## RULE-HEALTH-006 — типы NPC

- Minion побеждён после одного Wound.
- Brute имеет профильное число Wounds и собственные последствия, не используя общую таблицу.
- Champion получает Wounds как персонаж игрока и использует таблицу.
- Monstrosity имеет профильное число Wounds и профильные реакции на них.

Источник: страница 191. Полные правила NPC находятся в Gamemaster’s Guide и отсутствуют в текущем источнике.

## RULE-HEALTH-007 — Treatment и Healing

Treatment помечает Wound treated: она больше не добавляет `+1d` к будущей Wounds Table, а её эффекты `until treated` прекращаются. В бою Recover лечит одну Wound персонажа или союзника Close через Recall; Anatomy Lore даёт auto-success, а специальный Lore может сделать то же для конкретной Wound. Нужны подходящие trappings; поиск импровизированных supplies может потребовать Survival/Awareness. После боя при безопасной передышке все Wounds автоматически treated.

Healing удаляет все непостоянные эффекты Wound после указанной длительности: Catch Your Breath, A Night’s Respite либо Rest and Recovery; surgery-required Wound не начинает recovery до операции. При существенном deadline GM может разрешить Endurance для досрочного healing.

K1 хранит treated и healed раздельно. `EndEncounterHealingOpportunity` открывает Catch Your Breath после окончания непосредственной опасности, а `NightsRespiteHealingOpportunity` — после спокойного периода, завершённой ранней ночи и наступления утра. Оба reducers требуют treated/resolved Wounds, сверяют их категорию с Wounds Table, снимают все non-permanent effects и сохраняют permanent/другие источники. Точное число часов и optional досрочная Endurance-проверка не входят в обычную Night’s Respite boundary.

`RestAndRecoveryEndeavourRequest` привязывает Endurance Test к конкретному downtime, target и точному injury snapshot. Только успешный результат может быть источником `RestAndRecoveryHealingRequest`; он исцеляет одну выбранную ready Wound, а не полный набор. Строки `16–19` не принимают лишний surgery proof, а `SURGERY_AND_RECOVERY` (`20–23`) требуют либо успешный `DowntimeSurgeryResult` для той же Wound/цели/state/downtime, либо completed `CombatSurgeonBattleSurgeryProof` для той же цели и стабильной identity Wound. Battle snapshot может отличаться от актуального Endeavour state несвязанными ранами и Conditions; подмена sequence, table entry, roll history или origin запрещена. Application погашает proof перед Endeavour ID и сохраняет permanent consequences. Успех Endeavour также создаёт отдельный `FesteringWoundsRecoveryRequest`; его application consumer погашает именно follow-up ID и удаляет все Festering Wounds цели независимо от ordinary-Wound healing consumer.

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

`DrainedTestPreparationRequest → Result` является отдельной чистой pre-Test фазой. Она принимает канонический `ConditionState`, готовый `TestRequest` после накопления modifiers и optional проверенный `CombatSurgeonEffectiveEffectsResult`. При effective `Drained` reducer удаляет все положительные `DiceModifier`, включая cap-bypassing, и все обычные источники Glorious, но сохраняет penalties, Grim, fixed-success modifiers, reroll locks и Glorious от Fate. Исключение Fate требует `FateGloriousProof`, привязанный к session/actor/Test/spend и выпускаемый `FateGloriousSpendResult`; строковый Rule ID без proof его не подделывает. Если Combat Surgeon подавил единственный источник `Drained`, Test остаётся неизменным; известный другой wound-effect или explicit внешний источник сохраняет ограничения. Исходные Conditions, injury state и Test не мутируются. Интерактивный момент траты после первоначального броска пока не моделируется.

## RULE-HEALTH-009 — Infection и Festering Wounds

В конце дня, когда персонаж получил хотя бы одну Wound (даже уже treated/healed), он делает Endurance Test. Если successes меньше числа Wounds, полученных в этот день, добавляется Festering Wound. Она считается untreated для `+1d`, не может быть treated и лечится только Rest and Recovery.

Перед этой Test персонаж с Anatomy Lore может сделать Recall; каждый success позволяет ему выбрать себя или союзника для автоматического успеха против Infection.

K1 хранит их в отдельном target-bound `FesteringWoundState`, не смешивая с историческими `WoundRecord`. Каждая активная запись предоставляет один дополнительный untreated die через агрегированный `WoundDiceModifier`; пустое состояние не создаёт нулевой modifier. Успешный Rest and Recovery применяет typed follow-up один раз, очищает весь Festering state и не меняет обычную injury history.

`DailyWoundState` регистрирует только фактически принятые `CharacterWoundResult`/`FixedCharacterWoundResult` с day/target/stable Wound identity; Near Miss не считается. End-of-day request требует непустой незакрытый журнал, актуальную историческую injury state и Endurance Test. Он сравнивает successes с полным дневным количеством независимо от позднейших treatment/healing, добавляет не более одной Festering Wound и закрывает день ровно один раз. Обычный Basic `succeeded=True` не заменяет этот порог.

Профилактика представлена тремя явными фазами. `AnatomyInfectionRecallRequest` требует подтверждённую Anatomy Lore и выполняет Recall через общий RNG; число successes становится capacity, а не результатом Endurance. `AnatomyInfectionAllocationRequest` один раз расходует этот source и по упорядоченному выбору разных self/allied day-targets создаёт по одному target-bound proof. `AutomaticInfectionSuccessApplicationRequest` один раз применяет выбранный proof к точно тому же открытому `DailyWoundState`, закрывает дневную проверку без Endurance RNG и оставляет `FesteringWoundState` неизменным. Неиспользованные successes допустимы; перерасход, повтор цели, неверное отношение self/ally, чужой день, изменённая Wound history и повторное применение отклоняются.

Источник: страницы 122 и 136.

## RULE-HEALTH-010 — Surgery

Surgery для отмеченных Wounds требует Anatomy Lore, подходящие facilities/tools/time и Dexterity Test; провал рискует disfigurement/death, а даже успех оставляет указанное Wound permanent consequence. Обычная процедура происходит во время Rest and Recovery; Talent Combat Surgeon отдельно задаёт battle Exacting Dexterity (8), одна Test за action.

K1 `DowntimeSurgeryRequest → DowntimeSurgeryResult` проверяет treated/resolved Wound категории `SURGERY_AND_RECOVERY`, qualified surgeon, theatre, specialist tools, time и recovery supports до RNG. Success является immutable proof и сам не мутирует injury state. Failure возвращает GM-owned `SurgeryFailureRiskRequest` с возможными рисками permanent disfigurement/death, но не выбирает и не применяет outcome (`AMBIGUITY-009`). Combat Surgeon treatment branch создаёт source-aware suppression после treatment; battle aggregate регистрирует её один раз и возвращает non-mutating effective effects/Conditions. Battle surgery branch накапливает 8 Exacting Dexterity successes по одной action/Test и возвращает proof без немедленного healing. Completed battle proof применяется последующим Rest and Recovery по стабильной identity той же Wound; paid NPC/campaign cost и supernatural replacements остаются отдельными adapters.

Источник: страницы 74, 110 и 122. Ordinary downtime surgery, обе Combat Surgeon boundaries, suppression aggregate/view и healing consumer battle proof implemented; surgery-failure outcome остаётся partial/draft.

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

Player и Champion используют одну policy. Для обычной Wound число кубов равно `1 + untreated Wounds + modifiers`, минимум один. Hazard передаёт вместо базовой единицы свой положительный shortfall; остальные слагаемые и минимум не меняются. Принятая Wound записывает исходные d10 и сумму, удаляет прежний Staggered и отмечает смертельные результаты `24+`. Near Miss выбирается после броска: burn producer возвращает `ConsumeWoundNegationRequest`, а отдельный application consumer до Wound effect восстанавливает точное pre-Wound состояние, включая Staggered, не откатывая permanent расход Fate. Отменённая запись не участвует в последующих Wounds Table rolls и не должна регистрироваться в daily Wound state.

Для character-Wound пути этот порядок исполняет двухфазный lifecycle. `roll_character_wound_lifecycle` возвращает pending `CharacterWoundResult` до effects. `complete_character_wound_lifecycle` требует актуальные injury/day snapshots и явный выбор: при Near Miss сам выполняет bound burn/application и не создаёт receipt/effect; без него сначала вызывает `register_daily_wound` на pre-effect записи, затем `resolve_wound_effect`. Уже отменённая другим правилом Wound закрывается без обеих фаз. Lifecycle не выбирает Fate за игрока и ведёт отдельные ordered consumed snapshots для roll и Near Miss effect.

Kernel Attack, общий Stagger impact и Hazard используют lifecycle для Player/Champion и возвращают `pending_character_wound`; `wound_effect` и его follow-ups до completion отсутствуют. Wound-dependent Conditions атаки сохраняются как deferred и применяются только после `ACCEPTED`. Hazard failure-Conditions откладываются до того же application-вызова, но применяются и после Near Miss, потому что отмена Wound не отменяет сам провал Hazard. Это также сохраняет книжный порядок Wound effect → repeated Hazard Condition. Profile Minion/Brute/Monstrosity продолжают немедленный профильный путь.

Каждая принятая рана создаёт `WoundEffectRequest` с конкретным `WoundEntryId`. Специализированный reducer исполняет его ровно один раз внутри kernel и записывает `effect_resolved` в рану.

Условия и ограничения хранятся как типизированные `WoundConditionEffect` и `WoundRestrictionEffect` со ссылкой на номер раны и одним из сроков действия: до конца следующего хода, до явного снятия, до лечения, до полного заживления, до следующей проверки либо постоянно. Recover удаляет только `UNTIL_TREATED` effects нужного источника, а реализованные healing tiers — все его non-permanent effects; одинаковая Condition от другой раны или способности сохраняется по explicit source snapshot.

Строки `4`, `5`, `7`, `11`, `12` и `19` создают `WoundEnduranceTestRequest`. Профиль Endurance берётся orchestration-слоем из определения персонажа; `resolve_wound_endurance_test` принимает обычный `TestResult` и либо сохраняет состояние, либо применяет Condition/создаёт конкретный внешний consequence. Случайные предметы, зубы, пальцы, глаза и конечности представлены `WoundConsequenceRequest`, поскольку injury state намеренно не содержит анатомию и инвентарь.

Для `Spilling guts` возвращается явный `WoundChoiceRequest`: персонаж либо роняет предмет и зажимает рану, либо становится Defenceless. Скрытого default нет. Фактическое изменение инвентаря, случайный выбор стороны тела, прочие timed effects, применение surgery-failure follow-up, подключение Combat Surgeon effective view к конкретным modifiers и особая Endurance-защита после заживления `Ruptured organs` требуют будущего battle/campaign application orchestration.
