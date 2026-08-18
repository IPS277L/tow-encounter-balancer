# NPC и профили противников

Основной источник: `BOOK-GM-GUIDE`, страницы 89–91. Дополнительный источник: `BOOK-PLAYER-GUIDE`, страница 191. Статус: базовые injury policies `implemented`; каталог профильных Special Abilities `partially implemented`.

## RULE-NPC-001 — типы NPC

NPC относятся к одному из четырёх типов: Minion, Brute, Champion или Monstrosity. Тип главным образом определяет поведение в бою и модель Wounds.

## RULE-NPC-002 — Minion

Minion побеждён сразу после получения одного Wound. Атакующий при участии GM определяет, убит ли NPC, оглушён, обезоружен или принуждён сдаться.

## RULE-NPC-003 — Brute

Brute выдерживает профильное количество Wounds и может менять свойства при их накоплении. Он не бросает по Wounds Table. Если эффект добавил бы дополнительный куб к броску Wounds Table, Brute вместо этого получает дополнительный Wound.

## RULE-NPC-004 — Champion

Champion получает Wounds по модели персонажа игрока и бросает по Wounds Table.

## RULE-NPC-005 — Monstrosity

Monstrosity использует профильное количество Wounds и Reactions вместо Wounds Table. Дополнительный куб Wounds Table превращается в дополнительный Wound.

Особые правила:

- может проходить сквозь меньших существ и сопоставимые препятствия;
- при Attack action может использовать все атаки профиля;
- каждая Attack Test и каждая Opposed Test выполняются отдельно в выбранном Monstrosity порядке;
- обычно старается выбирать разные цели, но конкретные атаки и доступные цели определяются профилем и контекстом;
- не получает Staggered за неудачную Melee-атаку;
- Give Ground в Zone с меньшим противником не создаёт Broken;
- при Damage, не превышающем Resilience, получает Staggered; если уже Staggered, выбирает Wound либо Reaction;
- при Damage выше Resilience атакующий выбирает Wound либо Reaction.

## RULE-NPC-006 — обычное число атак

NPC может иметь несколько атак или вариантов оружия, но без специального правила использует только одну атаку при выполнении Attack action. Наличие атаки в профиле не гарантирует, что NPC несёт соответствующее оружие в каждом столкновении.

## RULE-NPC-007 — профиль атаки

Профиль атаки содержит Range, готовый dice/target профиль, Damage, требование к рукам и специальные свойства. Значения броска выводятся из Characteristic и Skill, но хранятся в профиле NPC для удобства GM.

## RULE-NPC-008 — Protection

Protection задаёт готовый профиль встречной защиты. Обычно он выводится из Athletics; вооружённый NPC может использовать лучший Defence против ближней атаки. Профиль также указывает наличие щита и возможность Defence против дальних атак.

## RULE-NPC-009 — Default Skill

Default Skill применяется ко всем навыкам, для которых профиль не задаёт отдельного значения. Явные навыки переопределяют default.

## RULE-NPC-010 — свойства оружия

NPC не получает автоматически все свойства одноимённого оружия игрока. Применяются только эффекты, явно указанные в NPC-профиле или общем правиле.

## RULE-NPC-011 — area и multi-target эффекты

Универсального AoE-правила нет. Число атак, цели и вторичные эффекты определяются конкретным профилем атаки, оружия, Special Ability или Monstrosity. Старый прототипный алгоритм AoE отменён пользователем.

## RULE-NPC-012 — Monstrous Flight Reaction

Griffon, Dragon и Wyvern при срабатывании Monstrous Flight дают Ground, предпочитая вертикальное перемещение в midair Zone, если оно доступно. Если Monstrosity уже давала Ground в текущем ходу, вместо этого она получает Wound. Источник: GM Guide, страницы 175, 177–178.

В K1 kernel переносит конкретный `MonstrousFlightReactionSpec`, дополнительные профильные Wounds исходной атаки и условные эффекты в `MonstrosityReactionRequest`. После добавления актуального spatial-контекста `resolve_monstrosity_reaction` возвращает типизированный `GIVE_GROUND` либо `SUFFER_WOUND`. В первой ветви `GiveGroundRequest` сохраняет предпочтение `VERTICAL_MIDAIR_IF_ABLE`; во второй используется общая профильная injury policy. Terrifying применяется после подтверждённого исхода тем же правилом, что и для обычного impact.

## RULE-NPC-013 — Unsteady Reaction

При срабатывании Unsteady Giant получает Prone. Когда Giant действительно падает Prone, все существа в его Zone, включая самого Giant, проверяют Athletics против Hazard (3). Источник: GM Guide, страница 183.

В K1 `UnsteadyReactionSpec` добавляет Prone к состоянию Giant и возвращает `ReactorZoneHazardRequest`. Этот запрос означает всех существ в Zone реагирующего Giant, но не выбирает их без spatial state. После внешнего выбора `ReactorZoneHazardResolutionRequest` требует включить Giant и исполняет общий Test/Hazard pipeline для каждой уникальной цели в переданном порядке. Если Giant уже Prone, Condition не накладывается повторно и Hazard не создаётся: результат явно получает исход `ALREADY_PRONE`. Staggered при падении не снимается. Условие Terrifying не срабатывает, поскольку Unsteady само по себе не создаёт Give Ground или Wound.

## RULE-NPC-014 — Monstrous Regeneration Reaction

Ghorgon и Troll Hag в конце своего хода могут выбрать восстановление одной Wound, получая Staggered, если этого Condition ещё нет. Wound от огня восстановить нельзя. Если их Reaction срабатывает, они не могут регенерировать на следующем ходу. Источник: GM Guide, страницы 151 и 181.

Текущий K1-срез реализует только немедленное последствие Reaction: `MonstrousRegenerationReactionSpec` возвращает исход `REGENERATION_SUPPRESSED` и source-aware `SuppressRegenerationNextTurnRequest`. Состояние, Wounds и Conditions при этом не меняются. Future turn orchestration должно сохранить запрет, применить его к следующей возможности регенерации и однократно погасить. Добровольное end-turn лечение, Staggered и проверка огненного источника Wound пока не исполняются без turn/wound-source state.

## RULE-NPC-015 — Undead Monstrosity Reaction

Когда срабатывает Reaction немонтированного Bone Dragon, он получает Wound. Если на нём находится Liche или Tomb King, Bone Dragon может вместо Wound дать Ground или упасть Prone. Источник: GM Guide, страница 172.

В K1 `UndeadMonstrosityReactionSpec` без mounted-контекста детерминированно применяет общую профильную Wound policy. `UndeadMonstrosityReactionContext` явно называет допустимый тип всадника и сообщает актуальную доступность Give Ground. При наличии всадника resolver передаёт владельцу `MONSTROSITY` только доступные варианты: Wound доступна всегда, Give Ground исключается после уже выполненного в раунде Give Ground, при невозможном перемещении или Prone, а повторное падение Prone исключается. Give Ground создаёт обычный spatial follow-up, Prone меняет состояние непосредственно, Wound поддерживает дополнительные профильные Wounds. Terrifying реагирует только на фактические Give Ground или принятую Wound.

Указанная в той же Ability невосприимчивость Bone Dragon к психологическим эффектам и Conditions не является частью самой Reaction: входящий источник проходит общий source-level preflight в собственной фазе. Одна строка Condition для классификации по-прежнему недостаточна.

## RULE-NPC-016 — невосприимчивость к психологическим эффектам

Skeleton, Wight, Vampire, Liche, Tomb King и Bone Dragon невосприимчивы к психологическим эффектам и Conditions. Источник: GM Guide, страницы 166–172.

Психологическая природа принадлежит источнику эффекта, а не значению `Condition`: например, Broken может возникнуть от явно описанного воздействия на страх, но одно наличие Broken не доказывает психологический источник. В K1 источник маркируется `EffectClassification.PSYCHOLOGICAL`, а профиль передаёт `EffectImmunity` с Rule ID своей Ability. Неклассифицированный эффект не блокируется по догадке.

Общий `EffectApplicationRequest → EffectApplicationResult` сохраняет Rule ID заблокированного источника и сработавшей иммунности. На эту policy переведены replacement Condition, Condition-on-hit, Condition после принятой Wound и отложенный Condition после Give Ground. Путь Staggered проверяет иммунитет до repeated-Stagger policy. Fearsome/Terrifying должны создаваться с явной психологической классификацией; тогда undead-профиль не получает Broken, а исходные Damage, Wound или Give Ground сохраняются. Та же source-level policy блокирует явно психологический Hazard до Test и весь `Curse of Cowardly Flight` до forced Give Ground. Остальные non-Condition эффекты требуют отдельной явной интеграции.

## RULE-NPC-017 — Foul Stench

Когда Wyvern входит в Zone врага, этот враг должен освободить одну руку, чтобы закрыть нос, либо получить Distracted. Источник: GM Guide, страница 178. Способность также передаётся Orc Boss, находящемуся верхом на Wyvern.

Spatial orchestration определяет факт входа и создаёт отдельный `FoulStenchRequest` для каждого затронутого врага с актуальным снимком доступности рук. Если свободная рука уже есть, цель закрывает нос без решения и потери предмета. Если обе руки заняты и предмет можно отпустить, `DecisionOwner.TARGET` явно выбирает `DROP_HELD_HAND_ITEM` либо `SUFFER_DISTRACTED`. Если освободить руку невозможно, Distracted применяется автоматически.

Выбранный сброс создаёт `DropHeldHandItemRequest`: resolver не выбирает конкретную руку или предмет и не меняет ещё не существующее inventory state. Distracted проходит общий Condition reducer. Источник не классифицируется как психологический только из-за Condition; книга не задаёт отдельную продолжительность занятости руки после немедленного срабатывания, поэтому K1 не создаёт постоянное ограничение руки.

## RULE-NPC-018 — Soporific Breath

Forest Dragon без Staggered может действием выдохнуть облако в Zone на Medium Range. Все существа в этой Zone делают Endurance Test против Hazard (2), который при провале наносит обычную Wound по shortfall и накладывает Drained. Если при применении Drained уже присутствует, вместо повторного Drained цель получает Defenceless. Источник: GM Guide, страница 177. Находящийся верхом Wood Elf получает эту Ability через Dragon Rider.

`soporific_breath_hazard` нормализует точный книжный источник как общий `ZoneHazardRequest`. Spatial/action orchestration отвечает за проверку отсутствия Staggered у действующего, расход действия, Medium Range, выбор Zone и снимок всех находящихся в ней существ. K1 получает уже выбранные уникальные цели и разрешает их слева направо через общий Test/Hazard pipeline.

`RepeatedConditionReplacement` проверяется после Wound-фазы. Свежая цель получает Drained; уже Drained цель сохраняет Drained и получает Defenceless. Если Drained сначала появился из результата Wounds Table того же Hazard, последующее книжное наложение Drained тоже считается повторным и заменяется на Defenceless. Успешно сопротивляющаяся цель не получает ни Wound, ни Condition.

## RULE-NPC-019 — Troll Vomit

Обычный Troll может действием атаковать уже Staggered врага в Close Range потоком едкой рвоты. Цель делает Endurance Test против Hazard (3). Источник: GM Guide, страница 180.

`troll_vomit_hazard` создаёт одиночную `HazardExposureRequest` без дополнительного Condition. При недостатке успехов общий Hazard resolver наносит Wound по shortfall; при трёх и более успехах цель полностью избегает эффекта. Action orchestration до создания exposure обязан проверить, что цель является врагом, находится в Close Range и уже имеет Staggered.

## RULE-NPC-020 — Troll Hag Swamp Breath

Troll Hag без Staggered может действием извергнуть едкий поток в Zone на Medium Range. Каждое существо в этой Zone делает Endurance Test против Hazard (3). Источник: GM Guide, страница 181.

`troll_hag_swamp_breath_hazard` создаёт общий `ZoneHazardRequest` без дополнительных Conditions. После внешнего выбора Zone и уникального стабильного списка её обитателей общий Zone executor независимо разрешает Test и Wound каждой цели. Проверка Staggered действующей Troll Hag, расход действия, Medium Range и spatial selection не относятся к reducer последствий.

## RULE-NPC-021 — Troll Stupidity

В начале боя Troll Distracted некой несущественной деталью окружения и получает –1d на все Tests. Если Distracted снято, оно не возвращается до окончания боя. Полученная Troll Wound снимает Condition автоматически; союзник также может снять его успешным Leadership Test. Общий способ снятия Distracted, например успешный Willpower Test, также подавляет возврат Stupidity. Источник: GM Guide, страница 180; общее Distracted — Player’s Guide, страница 123.

`TrollStupidityState` отдельно хранит source Rule ID и флаг `suppressed_until_battle_end`. `start_troll_stupidity` применяет начальный Distracted через общий Condition reducer, пока Ability не подавлена. `troll_stupidity_test_modifiers` возвращает ровно один `DiceModifier(-1)` для любого Test активного Troll; это специальная формулировка Stupidity, а не дополнительный второй штраф поверх неё.

Два автоматических пути получают строгие результаты предыдущей фазы: `ProfileWoundResult` должен содержать фактически нанесённую Wound, а `TrollStupidityLeadershipRequest` — уже выполненный Leadership Test. Успех снимает Distracted и подавляет Ability, провал не меняет состояние. `TrollStupidityConditionRemovedRequest` синхронизирует Ability после другого правила, которое уже сняло Condition, и сохраняет его Rule ID. Новый battle создаёт новое несдержанное состояние; текущий K1 не определяет границу боя самостоятельно.

## RULE-NPC-022 — Stone Troll

Stone Troll получает +1 Resilience относительно обычного Troll, то есть итоговый Resilience 6. Любое заклинание, затрагивающее Stone Troll, уменьшает свою Potency на 1; при effective Potency 0 оно не оказывает на эту цель никакого эффекта. Источник: GM Guide, страница 180. Та же механика Potency встречается у Talent Magic Resistance на странице 78 Player’s Guide.

`STONE_TROLL_RESILIENCE` фиксирует нормализованное профильное значение, а `stone_troll_spell_potency_modifier` создаёт `SpellPotencyModifier(-1)` с Rule ID Ability. Общий `resolve_spell_potency` применяется после вычисления книжной Potency Casting Test и до effect resolver конкретного заклинания. Полная загрузка NPC-профиля, Casting/Miscast и выбор целей остаются внешними слоями.

В multi-target случае K1 считает effective Potency отдельно против Stone Troll; другие цели сохраняют исходную Potency. Это локализованная временная трактовка `AMBIGUITY-002`, а не скрытое глобальное изменение результата Casting Test.

## RULE-NPC-023 — Troll Regeneration

В конце своего хода обычный Troll без Staggered может добровольно получить Staggered, чтобы вылечить 1 Wound. Wound, нанесённую огнём, регенерировать нельзя. Источник: GM Guide, страница 180.

`TrollRegenerationRequest` получает актуальное `ProfileInjuryState` и явный provenance-снимок `has_non_fire_wound`. При Staggered, нуле Wounds или отсутствии подходящей неогненной Wound resolver возвращает детерминированный unavailable-outcome и не обращается к decision provider. Если способность доступна, `DecisionOwner.ACTOR` — контроллер действующего Troll — явно выбирает `REGENERATE` либо `SKIP`; скрытого default нет.

При выборе Regenerate общий Condition reducer сначала фиксирует source-aware Staggered, затем профиль теряет ровно 1 Wound. Результат возвращает `ProfileStateChangeRequest`, чтобы внешний слой обновил диапазон характеристик Troll. Счётчик профильных Wounds пока не хранит источник каждой Wound, поэтому K1 не выбирает конкретную рану и доверяет orchestration только булев факт наличия допустимой неогненной Wound.

## Реализация injury policies в K1

- Minion получает один Wound и сразу становится defeated;
- Brute и Monstrosity считают Wounds до профильного лимита без Wounds Table;
- дополнительный куб Wounds Table преобразуется в `AdditionalProfileWound`;
- Champion использует ту же Wounds Table policy, что и персонаж игрока;
- изменение диапазона Wounds возвращается как `ProfileStateChangeRequest`, чтобы профильная Ability могла обновить характеристики без скрытой логики в общей policy;
- Monstrosity Wound/Reaction разрешается в `src/towr/rules/monstrosity_resolution.py` с правильным владельцем решения;
- прямое наложение Staggered без Damage, например вторичный эффект Blunderbuss, использует общую repeated-Staggered policy и не запускает Monstrosity Reaction;
- профильные атаки с обычным Damage и формулировкой `hits inflict Condition` используют `ConditionOnHitSpec`, не replacement impact;
- Terrifying у Dragon/Wyvern использует `ConditionOnGiveGroundOrWoundSpec`: Broken следует только после Give Ground или принятой Wound, но не после Near Miss;
- Monstrous Flight у Griffon/Dragon/Wyvern разрешается отдельным типизированным resolver и сохраняет различие между лимитом Reaction «в текущем ходу» и общим Give Ground «раз за раунд»;
- Unsteady у Giant применяет Prone и только при новом падении создаёт Hazard (3), который после внешнего spatial-выбора исполняется для самого Giant и всех остальных существ в Zone;
- Monstrous Regeneration у Ghorgon/Troll Hag создаёт source-aware запрет регенерации на следующий ход без немедленного изменения injury state;
- Undead Monstrosity у Bone Dragon различает обязательную Wound без всадника и внешний выбор Wound/Give Ground/Prone при Liche или Tomb King;
- психологическая иммунность undead-профилей блокирует явно классифицированные replacement/on-hit/outcome/after-Give-Ground Conditions, Hazards и оба последствия `Curse of Cowardly Flight`;
- Foul Stench после уже определённого входа в Zone сохраняет выбор цели между typed inventory follow-up и Distracted;
- Soporific Breath использует общий executor выбранной Zone и явную замену повторного Drained на Defenceless после Wound-фазы;
- Troll Vomit и Troll Hag Swamp Breath переиспользуют одиночный и Zone Hazard (3) без отдельной injury-логики;
- Troll Stupidity хранит battle-scoped suppression отдельно от Condition, выдаёт –1d на все Tests и принимает явные результаты Wound/Leadership/другого снятия;
- Stone Troll имеет нормализованный Resilience 6 и target-scoped –1 Potency preflight с полной блокировкой эффекта при нуле;
- обычная Troll Regeneration проверяет Staggered/наличие неогненной Wound, требует решения Actor и возвращает Staggered плюс профильное лечение;
- правило отсутствия Staggered за неудачную Melee-атаку поддерживается явным исключением в `AttackRequest` и сохраняется в trace.

Проверки находятся в `tests/unit/test_k1_injury_resolution.py`, `tests/unit/test_k1_monstrosity_resolution.py`, `tests/unit/test_k1_monstrosity_reaction_resolution.py` и `tests/unit/test_k1_kernel.py`.
