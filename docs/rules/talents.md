# Talents

Источник: `BOOK-PLAYER-GUIDE`, версия 1.4, глава Abilities — Talents, страницы 73–81. Статус области: `draft`; весь каталог прочитан, большинство эффектов ещё не подключено к character/battle orchestration.

## RULE-TALENT-001 — получение Talent

Talent выбирается при создании персонажа либо покупается за указанную XP Cost. Для покупки за XP нужны все Requirements; Talent, бесплатно полученный при создании, Requirements игнорирует. Talent нельзя приобрести повторно или улучшить, если его собственный текст явно не разрешает обратное.

Источник: страница 73.

## RULE-TALENT-002 — каталог общих Talents

Сокращённый реестр ниже нужен для трассировки и планирования. При реализации точным нормативным источником остаётся текст указанной страницы.

| Стр. | Talent | Cost / Requirements | Ключевой эффект | Статус реализации |
|---:|---|---|---|---|
| 73 | Accelerated Recovery | 4 / T 5+ | При catch breath лечит Wound уровня night respite; раз до downtime | нет |
| 73 | Acrobatic | 3 / Ag 4+ | Враги не блокируют движение; fall Hazard вдвое, вниз, минимум 0 | PC/generated NPC: typed path witness, native GM blockers/C9 Fly и настоящий fall Hazard0 с Test/replay; C9/C10 приняты |
| 73 | Allies in Arms | 3 / Fel 4+ | После окончательного Help Test один из двух участников снимает Staggered, даже при0успехов | PC/generated NPC: обычный Help, один removable target, actual acquisition/Test/clock; постоянные причины сохраняются, C7 принято |
| 73 | Armour Bane | 3 / — | Подходящее anti-armour weapon после проверки Wound снижает Resilience на 1, но не ниже T | PC/generated NPC:11реальных weapon Traits, атомарный HIT после Damage comparison; actor-owned потеря до конца боя, приняты C5/C6 |
| 73 | Bash Attack | 4 / S 5+ | После Staggered через Brawn немедленная бесплатная Melee attack | PC/generated NPC: actual first-Stagger grant, physical Melee/Shield readiness, K1/Fate/раны/Traits/replay, без ordinary slot и наследования Charge; C8 принято |
| 73 | Back in the Saddle | 2 / Ag 4+ | Mount остаётся Close после dismount; stand+mount одним move/Recover | PC/generated NPC, шесть настоящих mount profiles, отдельные HP/Conditions/turns, landing/periodic/departure и source-bound counters |
| 73 | Battlefield Musician | 3 / Musician’s Gear | Free signal либо action Leadership; вдохновлённым союзникам отдаются defensive ties до следующего хода | PC/generated NPC: физический инструмент/Music Lore, настоящий Leadership/Fate, сигналы, слышимость/Medium, срок по своему TurnStart, общий defensive tie/advice; C17 принято |
| 74 | Blessings of the Lady | 3 / Bretonnian, High Society, Honour Bound | Ранняя action даёт одну Near Miss Wound-negation на бой; Broken/нарушение vow снимает blessing | PC/generated NPC, молитва/настоящая отмена Wound, GM-контекст и once/battle replay; C18–C20 приняты |
| 74 | Careful Aim | 3 / Re 4+ | Успешный Aim снимает Staggered | PC/generated NPC: общий I/Awareness, Shooting/Throwing, окончательный Test/Fate/Honour, automatic Aim/Attack/Recover, ongoing/critical preservation, replay/current JSON/UI; C21 исполнен |
| 74 | Cleaving Blow | 4 / S 5+ | Wound two-handed weapon накладывает Staggered на остальных врагов Close | PC/generated NPC: actual weapon/grip, accepted primary/secondary Wounds, ordered actor-centred waves, обычные Wound/Fate/Lady/companion последствия, без нового действия; C22B |
| 74 | Combat Surgeon | 3 / Anatomy Lore | Recall временно подавляет ongoing Wound effect; battle surgery — Exacting Dexterity 8, Test за action | обе rules-boundaries, suppression aggregate/view и battle-proof healing consumer реализованы |
| 74 | Deep Formation | 2 / — | Spear/Short weapon даёт `+1d` союзнику в Zone против Charge Melee | PC/generated NPC обеих сторон: actual held source, Zone/Charge, +1d к конкретной защите; Drained получателя подавляет бонус |
| 74 | Defensive Stance | 2 / WS 3+ | После успешной Defence opposition можно не Stagger атакующего и снять свой Staggered | generated NPC и automatic melee PC: обмен фактически доступного нового Staggered; ongoing Staggered не снимается |
| 74 | Dispeller | 3 / Wizard | Раз/round Willpower против Casting; превышение даёт врагу Miscast die; Exacting dispel ongoing spell; все такие 9 создают Miscast dice | частично: есть общие opposed/Miscast primitives, Talent lifecycle нет |
| 75 | Exceptional Hearing | 2 / I 4+ | Расширенные слуховые Awareness; Blinded не штрафует Melee/opposition, если не Deafened | нет |
| 75 | Faith | 4 / Empire Human | Последовательные покупки дают Favour, Prayers, Miracle и новые Miracle uses | нет |
| 75 | Familiar | 3 / Wizard | Повторные покупки выбирают новый Familiar effect; familiar остаётся Long и восстанавливается Endeavour+Willpower | нет |
| 76 | Feigned Flight | 2 / — | После успешной opposition можно добровольно Give Ground; принято раз/round по явной трактовке PG76/119 | исполнение пока не подключено; ADR-0141 принят |
| 76 | Fight As One | 3 / — | Mounted Attack разрешает второе действие другой атакой mount по другой цели, иногда третье | нет |
| 76 | Frightening | 4 / — | Give Ground от Melee/Brawn накладывает Broken; Fearsome immune | частично: condition primitives есть, Talent не подключён |
| 76 | Golden Voice | 2 / Fel 4+ | Имитирует слышанный звук/голос; Music не требует gear | нет |
| 76 | The Grail Vow | 4 / Questing Vow + завершённый quest | Broken immunity, magical attacks, постоянная Lady blessing, Fate для повторной Near Miss, maxima `+2` | нет |
| 76 | Hardy | 3 / T 4+ | Wounds Table бросает на 1 die меньше, минимум 1 | PC/Champion Attack и PC Hazard/fall/fire/repeated Staggered/Miscast; fixed results и profile Wounds не меняются |
| 76 | Hatred | 3 / — | `+1d` Melee против выбранной группы; при её видимости Distracted | нет |
| 76 | Hold the Line | 3 / Fel 4+ | Recovery+Leadership снимает Staggered с союзника/успех в Medium; несовместимо с Treat/condition Test той же action | нет |
| 77 | Honour Bound | 3 / — | Раз/session oath Test Glorious либо Fate вместо burn для Unmitigated Success; нарушение блокирует до penance | PC/generated NPC, общий once/session; только PC имеет Fate и явный C20 exceptional scope |
| 77 | Intense Scrutiny | 3 / I 4+ | Scrutinise заменяет обычный вопрос одним из шести и требует правдивого раскрытия внутреннего ответа | нет |
| 77 | Interceptor | 4 / Ag 5+ | Раз/round перехватывает Give Ground в/из своей Zone: перемещение Close и немедленная Melee; есть запреты | нет |
| 77 | Iron Gut | 2 / не High/Wood Elf | Пища/вода не вызывают болезнь; ingested poison Tests Glorious | нет |
| 78 | Keen Eyed | 2 / I 4+ | Расширенные зрительные Awareness и lip-reading, если не Blinded | нет |
| 78 | Lightning Reflexes | 3 / I 5+ | Если не Defenceless, всегда Athletics opposition; первый ход раньше врагов даже в ambush | нет |
| 78 | Longbeard | 3 / Dwarf, только creation | `+1d` к снятию conditions; задаёт social expectations среди Dwarfs | нет |
| 78 | Lucky | 4 / — | Первый Fate/session бесплатен даже при Fate 0; gambling Tests Glorious | реализовано: free-first funding для трёх общих spends и proof-bound gambling Test preparation; Drained удаляет Talent Glorious |
| 78 | Magic Resistance | 3 / — | Затрагивающий spell получает Potency `-1`; при 0 нет эффекта | target-scoped primitive и generated NPC против двух PC Elementalism spells реализованы; не сопротивление Miscast |
| 79 | Mighty Blow | 3 / S 4+ | Игнорирует dice penalties самого two-handed weapon на Melee | PC/generated NPC: actual2H Attack, Melee Help/Protection; внешние штрафы сохраняются |
| 79 | Night Dweller | 2 / — | Видит Long в темноте; `+1d` против не видящей цели и Broken при Wound/Give Ground | нет |
| 79 | Polymath | 2 / Re 4+ | Несколько Lore bonus dice можно все обменять на Glorious | нет |
| 79 | The Questing Vow | 3 / Blessings of the Lady | Honour Bound к quest; Distracted immunity; Fate/Honour Bound снимает Broken и сохраняет blessing | нет |
| 79 | Quick Change | 3 / Grooming Kit | Минута+Dexterity для маскировки личности и временного Status | нет |
| 79 | Quick Throw | 4 / WS 4+, BS 4+ | Charge с throwing attack разрешает второй action Melee | нет |
| 79 | Rapid Reload | 3 / BS 4+ | Успешный Dexterity reload разрешает сразу Aim/Attack; запрещено при Staggered/движении | PC/generated NPC: actual Reload→slot2 Aim/Attack, same item/target/mode, partial Aim, максимум2actions; source/replay/statistics/current JSON проверены |
| 79 | Resistance to Corruption | 4 / — | Willpower против Chaos exposure всегда Glorious | нет |
| 79 | Resolute | 3 / Re 4+ | Give Ground может уйти на Short; Broken от входа во вражескую Zone только при Close к врагу | нет |
| 79 | Riposte | 4 / WS 5+ | Раз/round успешная Defence opposition заставляет атакующего выбрать Give Ground, Prone или Wound | нет |
| 80 | Secret Bloodline | 3 / только creation | Наследие задаёт social expectations после раскрытия | нет |
| 80 | Short Size | 2 / только creation | Побеждает равенство Agility opposition, проигрывает Strength tie с Marginal Success цели; особая Stealth; two-handed даёт Burdened | нет |
| 80 | Snake Charmer | 3 / — | Против Distracted цели Oppose тем же Skill; против beast/monster opposition Glorious | нет |
| 80 | Spiteseer | 3 / Wood Elf | Чувствует spites Medium, Awareness против illusion, Persuade с обязательной странной платой | нет |
| 80 | Stand and Shoot | 3 / I 4+ | Против Charge от ранее Aimed цели делает Shooting до её attack с Aim dice и выбирает момент range | нет |
| 80 | Steer Clear | 3 / — | Успешное управление в Manoeuvre снимает Staggered с одного пассажира | нет |
| 80 | Taunter | 4 / — | Distracted вами враг делает Grim attack по другой цели | нет |
| 81 | Thirst for Knowledge | 2 / Re 4+ | Lore dice работают при Drained; Drained/Distracted penalties игнорируются для Insights; Clue снимает оба | нет |
| 81 | Touched by the Winds | 2 / не Dwarf/Halfling | Чувствует magic, определяет item; Petty improvised выбранной Lore; Wizard дешевле, Study Lore `+2d` | нет |
| 81 | Unbreakable | 3 / Resolute | Broken immunity | нет |
| 81 | Valour of Ages | 3 / High Elf | Союзник во вражеской Zone предотвращает Broken от Give Ground и разрешает Recover там | нет |
| 81 | Vanguard | 3 / Ag 4+ | Move Quietly/Carefully в Manoeuvre также перемещает в соседнюю Zone | нет |
| 81 | Vouch For Them | 3 / Silver/Gold, Fel 4+ | NPC применяет ожидания вашего Status к представленному союзнику; disgrace отражается на вас | нет |
| 81 | Wild Attack | 3 / S 4+ | Если не Staggered, делает следующую Melee Glorious ценой Staggered до броска | generated NPC и automatic melee PC Attack/Melee Help: source-bound цена, committed intent и one-use Glorious; PC сравнивает пользу/риск/Fate |
| 81 | Wizard | 4 / не Dwarf/Halfling, Magic Lore | Разрешает improvised/memorised/formalised spells; до четырёх покупок задают Wizard Level | частично: PC ownership/profile Wizard1–4 и две memorised Elementalism spells исполняются; общий источник приобретения/уровня реализован, improvised spell execution ещё нет |

### Три таланта generated NPC

[ADR-0122](../decisions/ADR-0122-generated-npc-combat-talents.md) реализует Magic Resistance/Defensive Stance/Wild Attack как проверенные компоненты current Minions, с Requirements WS3+/S4+ и единственным приобретением. Генератор выбирает допустимый поднабор из разрешённого пула; Character Creation waiver и XP progression не моделируются. Это ограничение пространства генерации, не отмена исключения RULE-TALENT-001.

По выбранной пользователем трактовке PG74/119 Defensive Stance заменяет только фактически доступное новое наложение Staggered атакующему. Требуются собственный Staggered и Defence с большим числом успехов против Melee;0v0/Athletics/уже Staggered атакующий обмена не дают. Снятие происходит через обязательную реакцию до обычного miss-Staggered consumer, а не поверх уже изменённого состояния.

Wild Attack использует настоящее состояние до следующей Melee: получение Staggered меняет применимые Sword/Morning Star modifiers. Drained запрещает обычный Glorious, поэтому выбранная тактика не платит цену при Drained; уже Staggered источник недопустим по тексту. Ни price, ни Defensive Stance не дают нового действия или Fate spend. Пассивные Magic Resistance и снятие состояния через Defensive Stance при Drained сохраняются: PG123 запрещает bonus dice/обычный Glorious, не все Talents.

[Требования/поднаборы](../../tests/unit/test_generated_npc_talent_generation.py), [реакции/source/replay](../../tests/unit/test_generated_npc_reactions.py), [Potency/оба spells](../../tests/unit/test_generated_npc_magic_resistance.py), [native owner](../../src/towr/domain/pc_generated_talents.py), [вход/запуск](../examples/dynamic/README.md#таланты-динамических-npc).

### Боевые таланты PC в динамическом генераторе

Оборонительная стойка (Defensive Stance), PG74, и Дикая атака (Wild Attack), PG81, используют общий с generated NPC lifecycle. Вход хранит единичный Talent и приобретение: покупка `phase=advancement, funding=xp` проверяет базовые WS≥3/S≥4; `phase=creation, funding=free` явно подтверждает бесплатное Character Creation и снимает Requirements по PG73. Источник общий с другими талантами: `AcquiredTalent` и непустой список `acquisitions`, без отдельного legacy поля. Временное зелье не исправляет исходный Requirement. Для NPC этот waiver не добавлен.

Wild Attack оплачивается настоящим Staggered до собственного следующего Melee Test: Attack либо Melee Help. Действие, цель и получатель помощи фиксируются до цены; изменившиеся Conditions применяются к Sword/Morning Star и остальным modifiers. Glorious перебрасывает доступные провалы; Grim отменяет его, Fate поверх таланта не расходуется. Цена не создаёт дополнительного action/Test/использования руки. Drained и уже Staggered запрещают эту добровольную активацию.

Defensive Stance заменяет ещё не исполненное наложение Staggered промахнувшемуся атакующему снятием собственного. Нужны успешная фактическая Defence и действительно доступный новый Staggered противнику;0v0, Athletics, уже Staggered атакующий и собственный fresh state не дают обмена. Drained не отключает пассивную реакцию. Ongoing Staggered от раны15 сохраняется по PG122/190 до устранения причины; реакция не обходит последствия рук/ран и не создаёт новый Critical.

Автоматическая тактика сравнивает конечные распределения обычного и Glorious Test, действующую Fate/Lucky policy и прирост входящего риска; при равенстве не платит цену. Это эвристика без вложенного Monte Carlo и без расхода ресурса в прогнозе. После ADR-0124 граница включает mixed Melee/Shooting Minions при melee PC и all-Close. Wild Attack остаётся для собственных Attack/Melee Help; Defence против Shooting не запускает Defensive Stance. Новый PC ranged/Brute-путь не добавлен. [ADR-0123](../decisions/ADR-0123-pc-combat-talents-and-committed-melee-intent.md).

### Глубокое построение (Deep Formation)

Владелец удерживает копьё (Spear) либо другое оружие Ближнего боя (Melee) с максимальной дальностью Short. Когда союзник в той же зоне (Zone) подвергается настоящему натиску (Charge), он получает +1d к проверке, противопоставленной Melee атакующего. Это не только Defence: бонус относится к фактически выбранной защите. Сам владелец от своего таланта бонуса не получает; переносимый или выпавший предмет не подтверждает holding.

Native consumer использует полный источник приобретения, настоящий предмет/пригодный хват, сторону и текущую Zone. Один владелец даёт один бонус независимо от числа подходящих удерживаемых предметов; независимые bonus dice складываются по общему правилу PG108. Истощение (Drained) владельца само по себе не отменяет пассивную помощь, но Drained защищающегося убирает полученный bonus die. Бонус не тратит действие, не переносится на следующую атаку и не применяется к Shooting/Brawn или атаке без Charge. Источник: Player’s Guide1.4, III74; общие bonus dice/Grim/Glorious — V108. Это подключение существующего правила без нового house rule.

### Combat Surgeon: treatment-effect boundary

Native C24 сверяет PG98–99: реальный Physicker’s Kit не снимает штраф без Anatomy Lore. Без знания или набора требуется явное GM-разрешение с отрицательным makeshift_modifier; для операции сам специальный набор остаётся обязательным. Талант с законным waiver не создаёт Anatomy Lore.


После успешного применения treatment к одной Wound с активными effects `UNTIL_HEALED` владелец Combat Surgeon выполняет отдельную Recall Test. При успехе `CombatSurgeonEffectSuppression` связывает все такие effects и stable record выбранной Wound с точными treatment application/result, Test, surgeon, target и `battle_id`; suppression действует только до конца этого battle. На pure K1-границе сама `CharacterInjuryState` не меняется: результат связывает подавляемые effects с исходной Wound и не исцеляет её. Native owner C24 применяет результат к активному состоянию до конца боя; оригинальные подавленные effects остаются в квитанции, WoundRecord и постоянные последствия сохраняются.

`CombatSurgeonSuppressionAggregate` однократно регистрирует successful suppression в совпадающем battle. Effective view сверяет target, stable Wound identity и полный ordered набор активных `UNTIL_HEALED` effects, затем исключает их только из вычисляемых последствий. Для Wound Conditions используется explicit source snapshot: известный другой wound-effect или внешний источник сохраняет Condition. Healing делает регистрацию неактивной, не стирая audit history; повтор, другой battle/target и подмена Wound отклоняются.

Первый consumer этого view подключён к `Drained`: подготовка обычного `TestRequest` удаляет все положительные dice modifiers и non-Fate Glorious только при effective наличии Condition. Grim, penalties и Glorious с session/actor/Test/spend-bound `FateGloriousProof` сохраняются. Подавленный единственный wound-source временно возвращает bonuses и обычный Glorious, но independently sourced `Drained` продолжает ограничения. Каноническая injury history при этом не меняется.

Провал не создаёт suppression. В обоих исходах treatment-result ID погашается один раз, поэтому один treatment не даёт повторять Talent Test. Если у выбранной Wound несколько `UNTIL_HEALED` effects (например, `Spilling guts` одновременно даёт Burdened и Drained), они считаются единым ongoing-результатом раны и подавляются вместе. Requirements Talent не являются отдельным runtime-gate Anatomy Lore: по общему правилу страницы 73 Talent, полученный бесплатно при создании, может игнорировать Requirements; request поэтому требует подтверждённое владение самим Combat Surgeon.

Battle surgery представлена `CombatSurgeonBattleSurgeryActionRequest → Result` как non-attack Ability Improvise. Каждая action выполняет одну Basic Dexterity Test и добавляет её successes в общий `ExactingTestProgress`; нулевой вклад не уменьшает итог и возвращает GM-owned `SurgeryFailureRiskRequest`. Progress привязан к одному battle, surgeon, target, Wound и точному injury snapshot. На `8+` successes создаётся immutable proof, но Wound немедленно не исцеляется и injury state не меняется.

Combat Surgeon явно отменяет specialist medical facilities, поэтому operating theatre не является входом battle adapter. Принятый C23 ADR-0141 сохраняет отдельно названные specialist medical tools и recovery supports (`AMBIGUITY-010` закрыта), а достаточную цену времени доказывает action receipt каждой Test. Владелец Talent может оперировать себя либо союзника в Close Range. Completed progress нельзя продолжать или повторно использовать.

Completed `CombatSurgeonBattleSurgeryProof` может заменить ordinary surgery proof при последующем `Rest and Recovery` для той же цели и Wound категории `SURGERY_AND_RECOVERY`. Consumer сверяет стабильную identity Wound (`sequence`, entry, total, rolls и origin), но допускает изменение несвязанных ран/Conditions между battle и downtime; сама выбранная Wound должна оставаться treated/resolved и не healed. Proof ID погашается один раз перед Endeavour ID.

Источник: Player’s Guide 1.4, страницы 74, 110 и 122. Обе непосредственные rules-boundaries, suppression aggregate/effective view и использование completed battle-surgery proof последующим healing implemented; native C24/C25 соединяет активные Conditions/руки/снаряжение/проверки и kernel с этим результатом. PC и NPC обеих сторон могут лечить себя либо союзника с настоящими табличными ранами; optional `npc_allies` сохраняет самостоятельного союзного NPC без Fate. Автоматика сравнивает лечение с Attack/Help/Recover ограниченным прогнозом, не меняющим правила; операции выбираются явным native API без мгновенного healing.

## RULE-TALENT-003 — повторяемые и расходуемые Talents

Явные исключения из общего запрета повторной покупки:

- `Faith` покупается повторно для перехода Favour → Prayers → Miracles и затем для следующего использования Miracle;
- `Familiar` покупается несколько раз, каждый раз добавляя новый эффект из списка на странице 75;
- `Wizard` покупается до четырёх раз, а число покупок является Wizard Level.

Однократность «раз за session/round/battle/downtime» относится к runtime-состоянию конкретного Talent и не должна моделироваться как повторная покупка.

## Familiar effects

Страница 75 задаёт девять вариантов: Armoured, Babbler, Bookrest, Chaos Sink, Combatant, Flight, Linked, Poison Tongue и Skulker. Это самостоятельные выбранные эффекты. Особенно важно, что Chaos Sink перебрасывает ровно один die Miscast Table и требует принять новый результат, а Combatant может заменить Wound смертью Familiar; ни один из них пока не подключён к Miscast/injury pipeline.

## Полная область: источник приобретения и зависимости

2026-11-19 повторно сверены все59строк PG73–81: цены и перечисленные Requirements совпадают с реестром. [Доменный каталог](../../src/towr/domain/talent_catalog.py) хранит их как immutable metadata; [проверки](../../tests/unit/test_talent_catalog.py) отличают наличие записи от battle admission. Полный оставшийся перечень исполнения — в [матрице](../implementation-coverage.md#полная-матрица-талантов); [ADR-0141](../decisions/ADR-0141-all-talents-and-shared-acquisition.md) принят пользователем целиком. Общий источник приобретений/выборов/порогов реализован; runtime остальных эффектов отражён отдельно от каталога.

Для общего источника важны дополнительные нормативные границы:

- Время приобретения и бесплатное происхождение — разные факты. PG66 разрешает расход XP при завершении создания персонажа (Character Creation). Длиннобородый (Longbeard), Тайная родословная (Secret Bloodline) и Малый рост (Short Size) допускаются только в этой фазе; бесплатный waiver PG73 снимает Requirements, не превращает последующее развитие в создание.
- Обет Грааля (The Grail Vow), PG76, отдельно от строки Requirements требует завершённого поиска Грааля (Grail Quest). Вера (Faith), PG75/138–139, требует новых проявлений преданности при последующих приобретениях, выбирает одного бога и несовместима с Прикосновением Ветров (Touched by the Winds) или иной способностью колдовать. Это оперативные ограничения вне Requirements, они не исчезают от `creation_free`.
- Покупки Faith не ограничены числом3: каждая с3-й добавляет одно пожизненно расходуемое Чудо (Miracle), не session refresh. Фамильяр (Familiar) выбирает дополнительные различные эффекты из девяти; числовой максимум9не напечатан как отдельная шкала. Волшебник (Wizard) явно ограничен четырьмя покупками.
- Братья по оружию (Allies in Arms), PG73, требуют действительного Help, а не успешного Test. Рассекающий удар (Cleaving Blow), PG74, говорит о двуручном оружии (two-handed weapon), без ограничения Melee. Быстрая перезарядка (Rapid Reload), PG79, срабатывает после успешного Dexterity Test, не обязательно после завершения всей Exacting Reload; это не создаёт заряда для недопустимого Attack.
- Сражаться как один (Fight As One), PG76, прямо разрешает особый третий action при оговорённой способности маунта и другом его оружии. Снова в седле (Back in the Saddle), PG73, прямо разрешает оставить маунта Close: прежнее условие сцены «после спешивания уходит» не отменяет этот Talent.

Для Снова в седле (Back in the Saddle) приняты C11–C16 [ADR-0141](../decisions/ADR-0141-all-talents-and-shared-acquisition.md): настоящее животное своей стороны с собственным здоровьем; ожидание/собственный Recover со следующего раунда после всадника; по умолчанию без бонуса численности (Outnumbering). Свободный move тратится целиком на подъём и посадку на месте; рядом с врагом требуется Recover. Совместный Recover сохраняет отдельное неиспользованное движение. Посадка не лечит животное и не копирует на него состояния всадника. Пегас (Pegasus) отделяется в фактической воздушной позиции, а не переносится на землю вместе с падающим всадником. Талант подключён к публичному PC/generated NPC вводу и генерации. Собственные Drained/Staggered влияют на профиль животного; ongoing эффекты while mounted применяются к его HP в конце хода всадника. Раненый Пегас (Pegasus) садится на следующем фактическом ходу за free move, без нового Hazard (C16). Уход после подтверждённой гибели/выхода всадника и отдельные счётчики не подменяют исходные NPC defeats; источники/проверки — в [статусе](../project-status.md).

Вера (Faith) зависит от всех10богов PG140–149 и их реальных Favour/Prayers/Miracles. Магические таланты требуют настоящих контекстов Casting/Dispelling/Familiar, в том числе у NPC. Эти зависимости остаются частью незавершённой области, а не исключаются ради текущего узкого admission.

### Быстрая перезарядка (Rapid Reload)

Player’s Guide1.4 III79: триггер — успешная отдельная проверка Ловкости рук (Dexterity) при перезарядке (Reload), включая незавершённую Exacting. Даётся второе действие тем же оружием: прицеливание (Aim) либо атака (Attack); для выстрела нужен настоящий заряд. Пошатывание (Staggered) и движение в текущем ходу запрещают активацию. Это обычное второе действие, не разрешение третьего.

`RapidReloadGrant` сохраняет приобретение, фактический Reload/Test/первое действие, round/actor, физический предмет, цель и режим. Общий владелец PC/NPC повторно проверяет руки/дистанцию/движение и однократность. Автоматика выбирает доступный выстрел либо необходимый Aim после полной перезарядки; заведомо бесполезный Aim после partial Reload можно явно выбрать в native API. Следующий Reload расходует такой Aim по обычному правилу. Будущее обязательное Aim занимает место в прогнозе; бонусные кубы будущей Awareness не выдаются заранее. В отчётах `rapid_reload_counts` отделён от Fate Second Action/Bear/Crown, NPC Aim — от PC Fate. [Исполнение](../../src/towr/domain/pc_rapid_reload_models.py), [native проверки](../../tests/unit/test_talent_rapid_reload_execution.py), [JSON/process](../../tests/integration/test_talent_rapid_reload_json.py).


### Пробой брони (Armour Bane)

Источник: Player’s Guide1.4, III73; оружие (Weapons) IV93/95/96, Ogre Pistol — Gamemaster’s Guide1.1, VII103. Исполнено для PC и генерируемых NPC через общий источник приобретения таланта (Talent). Подходящие свойства имеют ровно11видов оружия: Axe, Halberd, Greataxe, Crossbow, Throwing Axe, Pistol, Handgun, Hochland Long Rifle, Repeater Pistol, Repeater Handgun и Ogre Pistol. Учитываются только фактически выбранные предметы и contributors двойного оружия (Dual Wield), не переносимое снаряжение и не похожее название.

Успешное попадание (HIT) сначала определяет урон (Damage) и рану (Wound) по прежней Стойкости к урону (Resilience). Затем тот же Attack proof применяет одно снижение на1, минимум до текущей Стойкости (Toughness). Два подходящих предмета не дают два снижения; повторное Пошатывание (Staggered) и его последующая рана не запускают Talent заново. Near Miss отменяет рану, сохраняя HIT и уже применённое снижение. Промах, безоружная атака (Unarmed), атака маунта (Mount) и предмет без подходящего свойства не создают применение.

Принятые пользователем трактовки [ADR-0141 C5/C6](../decisions/ADR-0141-all-talents-and-shared-acquisition.md): Доспех из метеоритного железа (Armour of Meteoric Iron, GM85) отменяет квалификацию немагического anti-armour свойства. Происхождение каждого contributor независимо: магический основной предмет не делает обычный Топор (Axe) магическим. Сумма фактически потерянных пунктов принадлежит бойцу до конца боя, сохраняется при смене/сбросе/подборе защиты, спешивании и лечении. Новые предметы дают свой физический бонус, из которого вычитается сохранённая потеря с минимумом текущегоT. При нулевом бонусе исчезает armoured-флаг, включая Шлем (Helmet); предмет, вес, другие свойства и ward остаются. Нулевое применение не создаёт скрытой потери для будущего предмета. Новый бой начинается с исходных данных.

`ArmourBaneApplication` хранит действительные приобретение, Attack ID, WeaponUse/contributors и прежний Resilience. Проекция повторно строит ожидаемое применение из реального HIT и отклоняет пропуск, повтор или подмену. PC вычисляет защиту из текущего снаряжения и журнала; NPC пересобирает тот же показатель после действительных изменений Щита (Shield) и маунта. В текущих JSON1 и UI доступен `armour_bane`; генератор выбирает его из разрешённого пула без готового statblock.


### Братья по оружию (Allies in Arms)

Источник: Player’s Guide1.4, III73; Помощь (Help) V108/117, состояния (Conditions) V122–123. Приобретение за XP требует Обаяния (Fellowship)4; бесплатное приобретение при создании персонажа (Character Creation) использует общий книжный waiver. Талант принадлежит помощнику, а не получателю.

По принятому [ADR-0141 C7](../decisions/ADR-0141-all-talents-and-shared-acquisition.md) эффект применяется **после** окончательного Help Test, включая перебросы и0успехов. Помощник либо получатель снимает одно Пошатывание (Staggered); постоянная причина от раны15 не снимается. Штрафы оружия и цена Дикой атаки (Wild Attack) сохраняются до проверки. Последующее снятие Staggered не отменяет возникший от использования травмированной руки Critically Injured и другие независимые последствия.

`AlliesInArmsApplication` хранит полную окончательную проверку/исполнение Help, приобретение, одного выбранного участника и его действительные исходные Conditions. Владелец боя повторно строит ожидаемое применение и снимает только Staggered из фактического post-Test состояния. Это часть обычной action Help, без дополнительного броска, действия или второго снятия. Автоматика предпочитает полезное снятие у союзника с предстоящим ходом; это ограниченная оценка симулятора, не новое ограничение книги.

Обычный Help с проверкой подключён генерируемым NPC, отдельно от бесплатных способностей Horde/Strength in Numbers. Бонус закрепляется за одним upcoming Attack/Protection Test, Skill и предметом; изменившаяся будущая тактика может оставить бонус неиспользованным, но не переносит его на другую проверку. NPC планируют вперёд без Help-цепочек, выбирая между собственной атакой и помощью; защита может относиться к следующему раунду. Обычный NPC Shooting Help использует готовое оружие без добровольного Repeater-бонуса и нового Reload; это выбранная тактика. Результаты используют прежние `npc_help_action_counts`, не счётчик выстрелов или NPC Fate.

Deafened запрещает Help помощнику; Drained подавляет положительные кубы, сохраняя полезность снятия состояния. Blinded даёт Grim на зависимые от зрения проверки; физическая помощь Deafened-получателю сама по себе не запрещается. Книга не задаёт общего Close/Medium радиуса Help, дополнительная дальность не придумана. Другой Skill требует подтверждённого GM соответствия по общему правилу; автоматический боевой путь использует соответствующий Skill предстоящей проверки.

Генератор хранит действительное исходное Обаяние (Fellowship) в `talent_facts.fellowship`; `search_space.fellowship` задаёт диапазон, автоматический envelope использует партию. Выборка/мутация сохраняет полные факты и отбрасывает незаконный paid Talent при снижении Fel. Старые pools без этого требования не получают лишних RNG-вызовов. UI показывает талант, требования, диапазон и реальный Fel результата. Magic/Casting Help контексты будут расширяться вместе с общим caster внутри незавершённой области всех талантов; наличие59строк каталога не означает их готовность.

### Оглушающий удар (Bash Attack)

PG1.4, III73, «Bash Attack»; Мощь (Brawn), III69, бой V117–119. Требование приобретения: Сила (Strength)5+,4XP; применяется общий источник `AcquiredTalent`. Настоящее новое Пошатывание (Staggered) от попавшей атаки Brawn разрешает немедленную бесплатную атаку Ближнего боя (Melee) по той же цели. Промах, рана вместо первого состояния, повторное Staggered и альтернативные Shove/Dismount разрешения не дают. Пригодный предмет выбирается из действительного инвентаря; Unarmed/Knuckledusters сами используют Brawn и не подменяют Melee-оружие. Held предмет может исполнить удар, даже когда основной выбор — Brawn; перенос carried предмета требует настоящего incidental/equip и доступных рук. Для2H при необходимости действительно оставляется Shield. Нет предмета/живой доступной цели — окно закрывается, без отложенного действия.

Пользовательская трактовка [C8](../decisions/ADR-0141-all-talents-and-shared-acquisition.md): это отдельная атака без +1d и Traits «при Натиске (Charge)». Обычные верховая позиция, оружие, состояния и scene modifiers сохраняются. Она исполняет полный K1/Test/Fate/Wound lifecycle, но не тратит ещё один ordinary action/следующий ход. Источник Brawn Attack и grant сохраняются и потребляются однократно. Wild Attack может оплатить собственный немедленный Melee Test, сохраняя заранее выбранные предметы и цель; новая цена меняет действующие Sword/Morning Star и другие модификаторы. Отсутствие нового ordinary slot не отменяет последствия рук/ран, защиты, Magic Weapons и Armour Bane.

Реализация обеих сторон доступна динамическому вводу и разрешённому пулу генератора; paid acquisition проверяет исходную Strength5, enhancement не подменяет Requirements. Счётчики немедленных атак в текущих отчётах отделены от обычных действий; source-ordered нули сохраняются. Полная область остальных Talents остаётся открытой.

### Акробат (Acrobatic)

PG1.4, III73, «Acrobatic»:3XP, исходная Ловкость (Agility)4+. Враги не перекрывают перемещение, включая Отступление (Give Ground). Это не снимает препятствия, Difficult Terrain, Prone/Defenceless/Burdened, Speed/once budgets, Briarroot bindings, отдельный запрет Charge из начального Close и требование настоящего Fly. Приобретение и реальный владелец удерживаются в `AcrobaticSource`; `path_entity_ids` сохраняют самих пересекаемых участников. K1 free/Run/extension/Charge/MoveCarefully/Terrain/GiveGround и native factories используют один источник, без удаления врагов из spatial snapshot.

PG114 оставляет микропозиции и физическое перекрытие за GM. ПринятоеC10 вводит optional `enemy_zone_blocking=false` для текущей сцены. `true` подтверждает узкие проходы: Close-враг у исходной позиции перекрывает выход из Zone, а враги в промежуточных Zones — проход; конечная Zone сама по себе не является пересечением. Источник учитывает фактических живых участников, смерть/уход снимают именно их присутствие. Within-Zone перемещение не выдумывает микро-траекторию. Вход в enemy Zone через GiveGround сохраняет собственное Broken. По принятомуC9 Acrobatic снимает enemy-only запрет Pegasus/Fly на взлёт/воздушный GiveGround из Close наземного врага; нужны действительные Fly и airspace.

Любой настоящий fall Hazard уменьшается вдвое вниз до0. `AcrobaticFallReduction` сохраняет положительный исходный GM rating и acquired source:3→1,1→0; повторное применение/подмена исходного рейтинга/владельца не принимаются native proof. Не всякий Athletics Hazard является падением. При0 живой участник всё равно выполняет настоящий avoidance Test; shortfall0 не создаёт Wound, а исходная Prone от dismount остаётся. Mantle of Ithilmar, Drained, Hardy, untreated Wounds и Fate применяются прежними владельцами. Player/Champion/Minion K1 и PC/generated NPC native пути проверены. [Решения](../decisions/ADR-0141-all-talents-and-shared-acquisition.md).

## Тщательное прицеливание (Careful Aim)

Источник: Player’s Guide1.4 III74; V116 — настоящее действие прицеливания (Aim). Требование — исходный Разум (Reason)4+, проверяемый общим источником приобретения; законное бесплатное приобретение при создании сохраняет общий обход Requirements. После окончательно успешного Aim владелец может снять собственное Пошатывание (Staggered). Автоматика всегда принимает полезное законное снятие; провал или отсутствие состояния эффекта не создают.

Эффект применяется после реального Awareness Test и его Fate/Honour окна. Кубы и bonus snapshot не пересчитываются; одна настоящая Aim action остаётся одним действием. Постоянная причина Staggered от раны не снимается. Истощение (Drained) не отменяет само снятие состояния, но подавляет положительные кубы Aim по общему правилу. Новая Критическая травма (Critically Injured) от использования раненой руки сохраняется.

Общие исходные Initiative/Awareness не зависят от наличия Shooting. Талант работает с законным прицеливанием для стрельбы (Shooting) и метания (Throwing), сохраняя настоящие предметы, руки, optimum/maximum и Close-ограничения оружия. Бонус сохраняется до следующего реального действия: подходящий Attack использует его один раз, другой Attack/Recover/Reload и прочие действия теряют. [Публичный пример](../examples/dynamic/careful-aim.request.json), [общий источник C21](../decisions/ADR-0141-all-talents-and-shared-acquisition.md#c21-общие-инициатива-и-внимательность-initiative-awareness-для-aim--принято).

## Благословения Леди (Blessings of the Lady)

Источники: Player’s Guide1.4 III74; III77 — Связанный честью (Honour Bound), обеты и Кодекс рыцарства (Code Chivalric); V112 — Чудесное спасение (Near Miss). Requirements проверяются по полному источнику приобретения: Бретонское человеческое происхождение (Bretonnian Human Origin), Знание высшего общества (High Society Lore) и Honour Bound. Законное бесплатное приобретение при создании персонажа (Character Creation) по общему правилу снимает перечисленные Requirements, но не условия применения.

Молитва — настоящее действие непосредственно перед боем либо в первый собственный фактический ход владельца. Последняя граница — явная пользовательская трактовка [C18](../decisions/ADR-0141-all-talents-and-shared-acquisition.md#c18-благословения-леди-blessings-of-the-lady-окно-молитвы--принято), не официальная errata. NPC после PC имеет собственное окно; номер первого раунда (Round) сам по себе его не определяет. Предварительная молитва требует подтверждения действительно совершённого действия в этой сцене.

Один раз за бой благословение позволяет отменить одну рану (Wound) как Near Miss, без расходования Судьбы (Fate). Прежние раны и Пошатывание (Staggered) сохраняются; отменённая рана не увеличивает будущие кубы таблицы, не регистрируется как новая рана и не запускает свои последствия. Отмена не преобразует тип участника и не удаляет другую одновременную рану. Ограничение раз за бой относится к отмене, а не количеству молитв: повторная молитва не восстанавливает уже использованный расход.

Новое получение Сломленности (Broken) лишает благословения. Нарушение обетов, Code Chivalric или Правил рыцарской чести (Rules of Knightly Honour) дополнительно запрещает новую молитву до согласованного GM искупления. Искупление снимает запрет, но не становится новой молитвой. Оценку произвольного сюжетного обета нельзя получать из строки его имени. Honour Bound имеет собственный предел раз за сессию (Session); это не расход благословения раз за бой и не право NPC получить Fate.

Автоматическое исполнение PC/generated NPC, журнал/replay, текущий JSON/UI и генерация подключены по принятым C18–C20. Контекст GM определяет действительность обета на начало сцены, служат ли ему боевые проверки, запрещённые Attack Skills и действительно совершённую предварительную молитву. Запрет Attack не запрещает защиту (Protection) или помощь (Help) этим навыком; дополнительные атаки и атаки маунта учитывают тот же запрет. Выбрав молитву в бою, владелец тратит настоящее обычное действие без броска. Источник приобретения и GM-факты не выводятся автоматически из имени таланта. [Публичный пример](../examples/dynamic/oaths.request.json).

## Связанный честью (Honour Bound)

Источники: Player’s Guide1.4 III77; V108 — числовые результаты проверок (Tests), V111 — Безоговорочный успех (Unmitigated Success), V112 — расход Судьбы (Fate). Раз за сессию (Session) действующий обет позволяет сделать связанную проверку славной (Glorious) либо получить Unmitigated Success за настоящий расход Fate вместо сжигания (burn). Эти режимы используют один ресурс. Нарушение блокирует применение до искупления; новая сцена не обнуляет факт использования в той же сессии.

Принятый C20 вводит **явный допуск GM**, а не универсальное число успехов из книги. Фактический `TestResult.successes`, перебросы и Trace сохраняются; отдельная квитанция предоставляет законный максимум подготовленного пула через `effective_successes`. Для базовой проверки (Basic Test) это Total Success, для Attack/Help/Exacting — отдельный числовой эффект текущей проверки. Защита отражает конкретную атаку; Reload не создаёт дополнительных действий, Help не меняет адресата. Настоящие9при Casting сохраняют Miscast. Атака не получает произвольные дополнительные раны, магическое поражение ограничено одной целью. Полный порядок и ограниченная автоматическая тактика — [C20](../decisions/ADR-0141-all-talents-and-shared-acquisition.md#c20-unmitigated-success-числовые-исходы-автоматического-боя--принято). NPC используют Glorious и не получают Fate.

## Боевой музыкант (Battlefield Musician)

Источники: Player’s Guide1.4 III73; III72/V107 — Обаяние (Fellowship) и Лидерство (Leadership); III82/88, IV98–99 — Знание музыки (Music Lore) и Инструменты музыканта (Musician’s Gear). Полный приобретённый талант (Talent) отделён от текущего инструмента, навыка и знания: историческое подтверждение prerequisites не создаёт предмет или рейтинг.

На своём ходу музыкант может бесплатно сообщить о присутствии или подать сигнал отступления, либо потратить обычное действие на проверку Лидерства (Leadership Test). Вдохновение получают разные живые союзники в пределах средней дистанции (Medium Range), которые слышат исполнителя; каждый окончательный успех даёт одного получателя. Сам музыкант себя не выбирает. Нулевой результат всё равно расходует действие. Оглушённый (Deafened) союзник эффекта не получает.

До следующего фактического начала хода музыканта положительное равенство в атакующей встречной проверке (Opposed Test) отдаёт победу вдохновлённому защитнику: атака (Attack) промахивается.0:0по-прежнему означает два провала; проверка без противодействия (unopposed) преимущества не получает. Общая конкретизация противоположных преимуществ равенства — C2 ADR-0141.

Пользователь в C17 подтвердил проверку слышимости/дистанции только при получении. Позднейшие перемещение, потеря слуха, смерть или уход музыканта не снимают уже полученный источник; без следующего фактического хода он сохраняется до конца боя. Это согласованная трактовка неописанных случаев, не официальная errata. Сигнал сам по себе не накладывает Сломлен (Broken) и не перемещает слушателей.

В бою используются физический инструмент и настоящий хват по GM-факту1/2руки; ранения, занятые руки, выпадение и платный подбор исполняются общими владельцами. Музыкант не получает бесплатного возврата оружия, зарядов или здоровья. PC может использовать обычное окно Судьбы (Fate) для этой проверки; NPC такого ресурса не получает. [Принятый контракт](../decisions/ADR-0141-all-talents-and-shared-acquisition.md#c17-боевой-музыкант-battlefield-musician--принято), [динамический ввод](../examples/dynamic/README.md#боевой-музыкант-battlefield-musician), [полные native-проверки](../../tests/integration/test_musician_native.py).


## Рассекающий удар (Cleaving Blow)

Источники: Player’s Guide1.4 III74; IV93/95/96 — фактическое двуручное оружие и его свойства; V119–123 — попадания, Пошатывание (Staggered), раны (Wounds), Беспомощный (Defenceless). Требование приобретения — Сила (Strength)5+ либо законное бесплатное приобретение с обходом Requirements.

Каждая подтверждённая рана от фактического двуручного предмета накладывает Пошатывание (Staggered) на всех остальных живых врагов в непосредственной близости (Close) от владельца таланта. Это не ограничение только Ближним боем (Melee): Стрельба (Shooting) и Метание (Throwing) используют тот же источник предмета. Копьё (Foot Spear) и Древковое оружие (Polearm) в фактическом двуручном хвате подходят; два одноручных предмета в Dual Wield не становятся двуручным оружием. Последующая смена/потеря предмета не переписывает источник уже нанесённой раны.

Принятый [C22B](../decisions/ADR-0141-all-talents-and-shared-acquisition.md#c22-рассекающий-удар-cleaving-blow-происхождение-вторичных-ран--принято) включает непосредственные вторичные свойства оружия — например, рану от повторного Staggered соседней цели Мушкетона (Blunderbuss). Каждая такая фактическая рана создаёт собственную волну. Раны самой волны имеют источник таланта и новых волн не создают. Это пользовательская конкретизация неоднозначного правила, не официальное уточнение книги.

Прямой урон (Damage), рана по Defenceless и рана от повторного Staggered основной атаки учитываются. Промах (Miss), отменённая через защиту Леди (Blessings of the Lady) или Чудесное спасение (Near Miss) рана, бегство без раны и магия без оружейной атаки источника не дают. Пока реальный lifecycle раны не завершён, срабатывание не предполагается по предварительному состоянию цели.

Обязательные последствия исходной атаки и её свойств завершаются до очереди волн. Волна фиксирует фактических Close-врагов владельца, исключая раненую цель и союзников; самостоятельное тело вражеского маунта учитывается отдельно. Нахождение в одной зоне (Zone) не доказывает Close. Цели обрабатываются по существующему приоритету и порядку исходных участников. Каждая проходит настоящий Staggered/Wound/Fate и последствия ран; нынешняя тактика сценария выбирает получение раны при повторном Staggered. Источники первой раны NPC, бегства, смерти и посадки раненого Пегаса (Pegasus) сохраняются. Волна не расходует действие, не создаёт новую атаку и не обходит очередь последствий. [Исполнение](../../src/towr/domain/pc_cleaving_blow_models.py), [реальные истории и replay](../../tests/unit/test_cleaving_blow_execution.py).
