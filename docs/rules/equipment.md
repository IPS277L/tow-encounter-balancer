# Equipment, Coin и Assets

Источник: `BOOK-PLAYER-GUIDE`, версия 1.4, глава Equipment, страницы 90–105. Статус области: `draft`; числовые профили проверены, существует только минимальный carried-inventory snapshot для Retreat, а полный inventory/economy/action model отсутствует. Боевые Traits реализованы лишь точечно.

## RULE-EQUIPMENT-001 — Coin и покупки

Персонаж начинает с тремя Coin своего Status. Coin — абстрактное число существенных покупок, а не точный подсчёт монет:

- покупка своего tier расходует 1 Coin;
- покупки более низкого tier обычно бесплатны, но GM может объединить множество мелких покупок в одну более высокую expense;
- покупка более высокого tier недоступна без дополнительного Coin, обмена или успешного barter;
- в каждый Downtime Coin сбрасывается к 3: недостаток восполняется Career, избыток теряется, если не инвестирован Endeavour.

Barter — Opposed Charm против Willpower. Он либо заменяет Coin при покупке своего tier, либо снижает expense на один tier; Brass не может таким способом купить Gold. Успех всегда несёт один скрытый GM-chosen cost: низкое качество, stolen goods или будущая услуга. Провал не запрещает обычную покупку, если она доступна.

Источник: страницы 90–91.

## RULE-EQUIPMENT-002 — перенос и владение

Персонаж может носить outfit и armour, число weapons до Strength (не более одного two-handed), а прочие trappings — в согласованном с GM разумном количестве. Превышение либо особо тяжёлый/громоздкий груз накладывает Burdened.

В руках помещается одно `2H` melee weapon либо по одному `1H` на каждую руку. При dual wield Traits обоих weapons могут применяться к одной Attack Test, а бонусы к одной Test складываются.

Источник: страница 92. Общая carried-weapon вместимость и число занятых рук — разные ограничения.

Полный inventory/carry-capacity reducer ещё не реализован. Первый минимальный immutable контракт `CarriedInventoryState` хранит только владельца и stable ordered `TrappingSnapshot`; каждая запись содержит instance/definition identity и внешнюю оценку `is_valuable`. Эта оценка не выводится автоматически из Cost tier: она нужна узкому materiel-price consumer Retreat страницы 120. Consumer удаляет выбранный carried item и возвращает его отдельным dropped fact, но пока не размещает предмет в Zone и не обслуживает equip/hand/capacity rules.

## RULE-EQUIPMENT-003 — melee weapon profiles

Damage `S` использует Strength; `S±N` модифицирует её. Таблица воспроизводит нормативные поля страницы 93.

| Weapon | Cost | Range | Damage | Hands | Traits |
|---|---|---|---|---|---|
| Unarmed | n/a | Close | n/a | n/a | Brawn; success даёт Staggered вместо Damage |
| Knuckledusters | Brass | Close | S-1 | 1H | `+1d` Stealth conceal; Brawn |
| Dagger | Brass | Close | S-1 | 1H | `+1d` Stealth conceal |
| Staff | Brass | Close | S | 1H | `+1d` Athletics при crossing Difficult Terrain |
| Foot Spear | Brass | Short | S | 1H | `+1d` Defence против Charge; `+1 Damage` в 2H |
| Cavalry Spear | Brass | Short | S | 1H | `+1d` Melee на mounted Charge |
| Axe | Brass | Close | S | 1H | `+1 Damage` против armoured |
| Pickaxe | Brass | Close | S+1 | 2H | `+1d` Toil при harvesting resources |
| Sword | Silver | Close | S | 1H | `+1d` Defence, если не Staggered |
| Warhammer | Silver | Close | S | 1H | `+1d` Melee против Staggered |
| Morning Star | Silver | Close | S+1 | 1H | `-1d` Melee при Staggered; нельзя dual wield |
| Polearm | Silver | Short | S | 1H | `+2 Damage` в 2H |
| Flail | Silver | Close | S+3 | 2H | `-2d` Melee при Staggered |
| Billhook | Silver | Close | S+2 | 2H | `+1d` Melee против mounted |
| Halberd | Silver | Close | S+2 | 2H | `+1 Damage` против armoured |
| Glaive | Silver | Close | S+2 | 2H | `+1d` Defence, если не Staggered |
| Greataxe | Silver | Close | S+3 | 2H | `-1d` Melee; `+1 Damage` против armoured |
| Greatsword | Gold | Close | S+3 | 2H | `-1d` Melee; `+1 to Defence` если не Staggered |
| Greathammer | Gold | Close | S+3 | 2H | `-1d` Melee; `+1d` Melee против Staggered |
| Lance | Gold | Close | S+1 | 1H | `+1d` Melee и `+1 Damage` на mounted Charge; нельзя dual wield |

`Greatsword` намеренно записан как `+1 to Defence`, без `d`, как в актуальном источнике. Тип модификатора требует отдельной сверки с контекстом/версткой перед кодированием.

## RULE-EQUIPMENT-004 — ranged weapon profiles и reload

`1H` ranged имеет Max Range Long, `2H` — разумный предел GM. Вне Optimum Range применяется `-1d`. При враге Close ranged weapon запрещён, кроме weapon с Close в Optimum; тогда цель может Oppose через Melee, а miss накладывает на атакующего Staggered как в Melee. Два shooting weapons не объединяются в одну attack.

Reload — Exacting Dexterity Test, одна Test за action. Если target successes не указан, reload бесплатен в составе attack. Ammunition считается достаточным после Downtime в месте снабжения либо при явном предварительном запасе.

| Weapon | Cost | Optimum | Damage | Hands | Traits |
|---|---|---|---|---|---|
| Sling | Brass | Medium | S | 1H | — |
| Shortbow | Brass | Short–Medium | 3 | 2H | `+1d` Shooting по Short |
| Warbow | Brass | Medium–Long | 3 | 2H | — |
| Longbow | Silver | Medium–Long | 4 | 2H | — |
| Crossbow | Silver | Short–Long | 4 | 2H | `+1 Damage` armoured; reload 2 |
| Pistol | Silver | Close–Short | 5 | 1H | ignores armour; reload 3 |
| Handgun | Silver | Medium–Long | 5 | 2H | ignores armour; reload 3 |
| Blunderbuss | Silver | Short | 4 | 2H | Max Medium; `+2d` Short; hit Staggers creatures Close к цели; reload 3 |
| Hochland Long Rifle | Gold | Medium–Extreme | 6 | 2H | must Aim; ignores armour; `+1d` Wounds Table; reload 4 |
| Repeater Handbow | Gold | Close–Short | 4 | 1H | можно `+1d` к одной Shooting, затем reload 3 |
| Repeater Crossbow | Gold | Short–Medium | 4 | 2H | можно `+1d`, затем reload 3 |
| Repeater Pistol | Gold | Close–Short | 5 | 1H | ignores armour; можно `+2d`, затем reload 3 |
| Repeater Handgun | Gold | Short–Long | 5 | 2H | ignores armour; можно `+3d`, затем reload 5 |

Все blackpowder firearms требуют Blackpowder Lore.

## RULE-EQUIPMENT-005 — throwing weapon profiles

Throwing используется в Charge вместо Melee и тогда считается в Optimum Range. При Strength 4+ верхняя граница Optimum увеличивается на одну range step. За пределами Optimum атаковать нельзя.

| Weapon | Cost | Optimum | Damage | Hands | Traits |
|---|---|---|---|---|---|
| Rock | n/a | Short–Medium | n/a | n/a | не Wounds, кроме repeated Staggered |
| Throwing Spear | Brass | Close–Medium | S | 1H | — |
| Throwing Axe | Brass | Short | S+1 | 1H | `+1 Damage` armoured |
| Weighted Net | Brass | Close–Short | n/a | 2H | Burdened вместо Damage |
| Throwing Knives | Silver | Short | S | 1H | набора хватает на бой |
| Oil Flask | Silver | Short–Medium | n/a | 1H | hit даёт Ablaze цели и всем Close к ней |
| Blasting Charge | Gold | Short–Medium | n/a | 1H | hit: Endurance Hazard (3) всей target Zone; miss: то же в attacker Zone |

Обычные throwing weapons можно подобрать при наличии возможности; Oil Flask и аналогичные расходные — нельзя.

## RULE-EQUIPMENT-006 — armour и outfits

Resilience равна Toughness плюс armour/trapping bonus. Armoured — любой, у кого armour, shield или иной эффект поднял Resilience выше Toughness. `Ignores armour` временно использует Toughness вместо Resilience для этой attack.

| Item | Cost | Resilience | Traits |
|---|---|---|---|
| Peasant’s Garb | Brass | T | `+1d` Charm выглядеть harmless |
| Burgher’s Apparel | Silver | T | `+1d` Charm при haggling с Silver |
| Lordly Attire | Gold | T | `+1d` Leadership при orders Brass/Silver |
| Uniform | Brass | T | `+1d` Leadership civilians; под armour |
| Worker’s Leathers | Brass | T | `+1d` против physical Hazards; поверх outfit |
| Travelling Clothes | Brass | T | `+1d` против environmental Hazards/conditions |
| Concealing Clothing | Brass | T | `+1d` Stealth в одном environment; поверх outfit |
| Stage Costume | Brass | T | `+1d` attract attention |
| Shield | Silver | +1 | carried; Defence против Shooting |
| Light Armour | Silver | T+1 | — |
| Heavy Armour | Gold | T+2 | `-1d` Agility; Burdened при S < 3 |
| Barding | Gold | +1 | horse; `-1d` Agility mount/rider; также `+1 Resilience` rider |

Источник: страницы 97–98.

## RULE-EQUIPMENT-007 — tools, kits и услуги

Нужный kit разрешает Tests/actions, иначе невозможные. Импровизация возможна с GM permission и всегда получает difficulty penalty. Сам toolkit обычно не даёт bonus dice; Required Lore остаётся обязательным. Trade Lore не позволяет craft без соответствующих Trade Tools.

Полный data-каталог страниц 99–101 включает Game Set, Arcane Paraphernalia, Lighting/Hunting/Climbing kits, Traveller’s Pack, Thief Tools, Writing/Grooming/Physicker’s/Cartography kits, Monster Slayer’s Arsenal и девять Trade Tools, а также General Assistance, Food & Lodging, Transportation и Specialist Labour по трём Status tiers.

NPC service обычно стоит tier NPC; time-consuming, costly, illegal или dangerous повышает expense на tier. Нерутинная услуга требует Persuade, opposed Willpower. NPC может запросить favour вместо Coin.

## RULE-EQUIPMENT-008 — Assets

Asset может открыть Test, дать bonus dice или иметь собственные правила. Его нельзя купить обычным Coin: он приходит из creation/reward/narrative либо Invest Money Endeavour; обмен обычно связан с Change Career. Repair стоит по 1 Coin tier Asset за каждый Fault/issue.

Каталог:

- Animals/Vehicles: A Small but Vicious Dog, Hand Cart, Trade Cart, Travelling Stage, Rowboat, River Barge, Ship’s Passage, Horse and Stables, Coach;
- Buildings: Farm and Grazing Herd, Market Stall, Shop, Armoury, Workshop, Laboratory, Brewery, Tavern, Theatre, Secret Hideout, Religious Shrine, Temple, Barracks, Library, Luxurious Apartments, Chapterhouse, Noble Estate;
- Other: Secret Identity, Map of the Underground, Mark of Honour, Symbol of Office, Enchanted Arrows, Map of the Worldroots, Secret Society Membership, Printing Press, Trustworthy Banker, Full Plate Armour, Heirloom Wargear.

Особые числовые эффекты страниц 103–105:

- Small but Vicious Dog при отсутствии Staggered у хозяина запрещает Give Ground цели его Melee/Brawn attack;
- Enchanted Arrows: Hagbane даёт Drained, Moonfire — Ablaze, Trueflight игнорирует cover/concealment penalties; по одной стреле каждого типа/session без replenishment Endeavour;
- Trustworthy Banker отменяет Bank Money Endeavour для доступного lodge/withdraw;
- Full Plate: `T+3`, `-1d` Agility, Burdened при S < 4;
- Heirloom Wargear без конкретного magic item раз/session делает Test с ним Glorious.

Остальные описания Assets предоставляют доступ/ресурсы и campaign permissions, но не должны получать выдуманные числовые бонусы.
