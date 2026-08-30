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
| 73 | Acrobatic | 3 / Ag 4+ | Враги не блокируют движение; fall Hazard вдвое, вниз, минимум 0 | нет |
| 73 | Allies in Arms | 3 / Fel 4+ | При Help один из двух участников снимает Staggered | нет |
| 73 | Armour Bane | 3 / — | Подходящее anti-armour weapon после проверки Wound снижает Resilience на 1, но не ниже T | нет |
| 73 | Bash Attack | 4 / S 5+ | После Staggered через Brawn немедленная бесплатная Melee attack | нет |
| 73 | Back in the Saddle | 2 / Ag 4+ | Mount остаётся Close после dismount; stand+mount одним move/Recover | нет |
| 73 | Battlefield Musician | 3 / Musician’s Gear | Free signal либо action Leadership; вдохновлённым союзникам отдаются defensive ties до следующего хода | нет |
| 74 | Blessings of the Lady | 3 / Bretonnian, High Society, Honour Bound | Ранняя action даёт одну Near Miss Wound-negation на бой; Broken/нарушение vow снимает blessing | нет |
| 74 | Careful Aim | 3 / Re 4+ | Успешный Aim снимает Staggered | нет |
| 74 | Cleaving Blow | 4 / S 5+ | Wound two-handed weapon накладывает Staggered на остальных врагов Close | нет |
| 74 | Combat Surgeon | 3 / Anatomy Lore | Recall временно подавляет ongoing Wound effect; battle surgery — Exacting Dexterity 8, Test за action | обе rules-boundaries, suppression aggregate/view и battle-proof healing consumer реализованы |
| 74 | Deep Formation | 2 / — | Spear/Short weapon даёт `+1d` союзнику в Zone против Charge Melee | нет |
| 74 | Defensive Stance | 2 / WS 3+ | После успешной Defence opposition можно не Stagger атакующего и снять свой Staggered | нет |
| 74 | Dispeller | 3 / Wizard | Раз/round Willpower против Casting; превышение даёт врагу Miscast die; Exacting dispel ongoing spell; все такие 9 создают Miscast dice | частично: есть общие opposed/Miscast primitives, Talent lifecycle нет |
| 75 | Exceptional Hearing | 2 / I 4+ | Расширенные слуховые Awareness; Blinded не штрафует Melee/opposition, если не Deafened | нет |
| 75 | Faith | 4 / Empire Human | Последовательные покупки дают Favour, Prayers, Miracle и новые Miracle uses | нет |
| 75 | Familiar | 3 / Wizard | Повторные покупки выбирают новый Familiar effect; familiar остаётся Long и восстанавливается Endeavour+Willpower | нет |
| 76 | Feigned Flight | 2 / — | После успешной opposition можно добровольно Give Ground, не чаще общего лимита | нет |
| 76 | Fight As One | 3 / — | Mounted Attack разрешает второе действие другой атакой mount по другой цели, иногда третье | нет |
| 76 | Frightening | 4 / — | Give Ground от Melee/Brawn накладывает Broken; Fearsome immune | частично: condition primitives есть, Talent не подключён |
| 76 | Golden Voice | 2 / Fel 4+ | Имитирует слышанный звук/голос; Music не требует gear | нет |
| 76 | The Grail Vow | 4 / Questing Vow + завершённый quest | Broken immunity, magical attacks, постоянная Lady blessing, Fate для повторной Near Miss, maxima `+2` | нет |
| 76 | Hardy | 3 / T 4+ | Wounds Table бросает на 1 die меньше, минимум 1 | нет |
| 76 | Hatred | 3 / — | `+1d` Melee против выбранной группы; при её видимости Distracted | нет |
| 76 | Hold the Line | 3 / Fel 4+ | Recovery+Leadership снимает Staggered с союзника/успех в Medium; несовместимо с Treat/condition Test той же action | нет |
| 77 | Honour Bound | 3 / — | Раз/session oath Test Glorious либо Fate вместо burn для Unmitigated Success; нарушение блокирует до penance | нет |
| 77 | Intense Scrutiny | 3 / I 4+ | Scrutinise заменяет обычный вопрос одним из шести и требует правдивого раскрытия внутреннего ответа | нет |
| 77 | Interceptor | 4 / Ag 5+ | Раз/round перехватывает Give Ground в/из своей Zone: перемещение Close и немедленная Melee; есть запреты | нет |
| 77 | Iron Gut | 2 / не High/Wood Elf | Пища/вода не вызывают болезнь; ingested poison Tests Glorious | нет |
| 78 | Keen Eyed | 2 / I 4+ | Расширенные зрительные Awareness и lip-reading, если не Blinded | нет |
| 78 | Lightning Reflexes | 3 / I 5+ | Если не Defenceless, всегда Athletics opposition; первый ход раньше врагов даже в ambush | нет |
| 78 | Longbeard | 3 / Dwarf, только creation | `+1d` к снятию conditions; задаёт social expectations среди Dwarfs | нет |
| 78 | Lucky | 4 / — | Первый Fate/session бесплатен даже при Fate 0; gambling Tests Glorious | нет |
| 78 | Magic Resistance | 3 / — | Затрагивающий spell получает Potency `-1`; при 0 нет эффекта | реализован target-scoped Potency primitive |
| 79 | Mighty Blow | 3 / S 4+ | Игнорирует dice penalties самого two-handed weapon на Melee | нет |
| 79 | Night Dweller | 2 / — | Видит Long в темноте; `+1d` против не видящей цели и Broken при Wound/Give Ground | нет |
| 79 | Polymath | 2 / Re 4+ | Несколько Lore bonus dice можно все обменять на Glorious | нет |
| 79 | The Questing Vow | 3 / Blessings of the Lady | Honour Bound к quest; Distracted immunity; Fate/Honour Bound снимает Broken и сохраняет blessing | нет |
| 79 | Quick Change | 3 / Grooming Kit | Минута+Dexterity для маскировки личности и временного Status | нет |
| 79 | Quick Throw | 4 / WS 4+, BS 4+ | Charge с throwing attack разрешает второй action Melee | нет |
| 79 | Rapid Reload | 3 / BS 4+ | Успешный Dexterity reload разрешает сразу Aim/Attack; запрещено при Staggered/движении | нет |
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
| 81 | Wild Attack | 3 / S 4+ | Если не Staggered, делает следующую Melee Glorious ценой Staggered до броска | нет |
| 81 | Wizard | 4 / не Dwarf/Halfling, Magic Lore | Разрешает improvised/memorised/formalised spells; до четырёх покупок задают Wizard Level | частично: magic state/pipeline есть, Talent ownership нет |

### Combat Surgeon: treatment-effect boundary

После успешного применения treatment к одной Wound с активными effects `UNTIL_HEALED` владелец Combat Surgeon выполняет отдельную Recall Test. При успехе `CombatSurgeonEffectSuppression` связывает все такие effects и stable record выбранной Wound с точными treatment application/result, Test, surgeon, target и `battle_id`; suppression действует только до конца этого battle. Сама `CharacterInjuryState` не меняется: Wound не становится healed, Conditions и `ActiveWoundEffect` не удаляются.

`CombatSurgeonSuppressionAggregate` однократно регистрирует successful suppression в совпадающем battle. Effective view сверяет target, stable Wound identity и полный ordered набор активных `UNTIL_HEALED` effects, затем исключает их только из вычисляемых последствий. Для Wound Conditions используется explicit source snapshot: известный другой wound-effect или внешний источник сохраняет Condition. Healing делает регистрацию неактивной, не стирая audit history; повтор, другой battle/target и подмена Wound отклоняются.

Провал не создаёт suppression. В обоих исходах treatment-result ID погашается один раз, поэтому один treatment не даёт повторять Talent Test. Если у выбранной Wound несколько `UNTIL_HEALED` effects (например, `Spilling guts` одновременно даёт Burdened и Drained), они считаются единым ongoing-результатом раны и подавляются вместе. Requirements Talent не являются отдельным runtime-gate Anatomy Lore: по общему правилу страницы 73 Talent, полученный бесплатно при создании, может игнорировать Requirements; request поэтому требует подтверждённое владение самим Combat Surgeon.

Battle surgery представлена `CombatSurgeonBattleSurgeryActionRequest → Result` как non-attack Ability Improvise. Каждая action выполняет одну Basic Dexterity Test и добавляет её successes в общий `ExactingTestProgress`; нулевой вклад не уменьшает итог и возвращает GM-owned `SurgeryFailureRiskRequest`. Progress привязан к одному battle, surgeon, target, Wound и точному injury snapshot. На `8+` successes создаётся immutable proof, но Wound немедленно не исцеляется и injury state не меняется.

Combat Surgeon явно отменяет specialist medical facilities, поэтому operating theatre не является входом battle adapter. Узкая временная политика `AMBIGUITY-010` пока сохраняет отдельно названные specialist medical tools и recovery supports, а достаточную цену времени доказывает action receipt каждой Test. Владелец Talent может оперировать себя либо союзника в Close Range. Completed progress нельзя продолжать или повторно использовать.

Completed `CombatSurgeonBattleSurgeryProof` может заменить ordinary surgery proof при последующем `Rest and Recovery` для той же цели и Wound категории `SURGERY_AND_RECOVERY`. Consumer сверяет стабильную identity Wound (`sequence`, entry, total, rolls и origin), но допускает изменение несвязанных ран/Conditions между battle и downtime; сама выбранная Wound должна оставаться treated/resolved и не healed. Proof ID погашается один раз перед Endeavour ID.

Источник: Player’s Guide 1.4, страницы 74, 110 и 122. Обе непосредственные rules-boundaries, suppression aggregate/effective view и использование completed battle-surgery proof последующим healing implemented; конкретные battle modifiers ещё должны получать effective view от orchestration.

## RULE-TALENT-003 — повторяемые и расходуемые Talents

Явные исключения из общего запрета повторной покупки:

- `Faith` покупается повторно для перехода Favour → Prayers → Miracles и затем для следующего использования Miracle;
- `Familiar` покупается несколько раз, каждый раз добавляя новый эффект из списка на странице 75;
- `Wizard` покупается до четырёх раз, а число покупок является Wizard Level.

Однократность «раз за session/round/battle/downtime» относится к runtime-состоянию конкретного Talent и не должна моделироваться как повторная покупка.

## Familiar effects

Страница 75 задаёт девять вариантов: Armoured, Babbler, Bookrest, Chaos Sink, Combatant, Flight, Linked, Poison Tongue и Skulker. Это самостоятельные выбранные эффекты. Особенно важно, что Chaos Sink перебрасывает ровно один die Miscast Table и требует принять новый результат, а Combatant может заменить Wound смертью Familiar; ни один из них пока не подключён к Miscast/injury pipeline.
