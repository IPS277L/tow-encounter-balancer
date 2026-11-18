# Покрытие боевых возможностей

Дата: 2026-11-18. Исходная инвентаризация выполнена на базе `624522d`; строки двуручного оружия и пространственного исполнения обновлены по рабочей реализации [ADR-0138](decisions/ADR-0138-all-two-handed-weapons.md). Нормализованные правила сопоставлены с моделями, владельцами боя, входом генератора и проверками. Фактическая приёмка и незавершённый остаток находятся в [статусе](project-status.md); таблица сама не расширяет допуск.

Нормативные источники: Player’s Guide1.4 (PG) и Gamemaster’s Guide1.1 (GM), по [политике источников](source-policy.md). Страницы ниже взяты из существующих нормализованных разделов; это не заявление о повторном полном чтении книг. Здесь фиксируется покрытие групп механик, а не процент готовности всей книги. Подробные каталоги и определения остаются в `docs/rules/`.

## Как читать матрицу

- **Ядро**: есть типизированная модель и resolver либо composite для конкретного правила. Наличие enum или описания эффекта само по себе не считается исполнением.
- **Отдельный бой**: действие и последствия соединены с непрерывным owner/runner в указанной scripted-сцене. Это может быть PC family либо отдельная M8 Magic family.
- **Динамический PC**: факты персонажа принимаются текущим генератором и используются автоматической тактикой в бою.
- **Генерируемый NPC**: компонент выбирается генератором, проходит проверку совместимости, выводит настоящий combat source и исполняется. Книжный пресет этого статуса не даёт.

«Есть» в таблице всегда ограничено указанной границей. Сохранение предмета/таланта в редактируемом черновике без допуска к расчёту отмечено отдельно. Исторические успешные проверки не являются новым зелёным прогоном текущего полного набора тестов.

## Основа боя и факты участников

| Область / источник | Ядро | Отдельный бой | Динамический PC / генерируемый NPC | Оставшаяся граница |
| --- | --- | --- | --- | --- |
| Характеристики и навыки (Characteristics & Skills), PG III67–72; проверки (Tests), V106–110 | Basic/Opposed/Exacting, модификаторы, Grim/Glorious, caps; есть все16 Skill identifiers | Профили конкретных действий, включая помощь (Help) и перезарядку (Reload) | PC: WS/S/T/Ag и Melee/Defence/Athletics/Endurance; условно BS/I/Shooting/Dexterity для стрельбы и Re/Willpower для магии. NPC: WS/S/T/Ag, Melee/Defence/Athletics и условные стрелковые факты | Полный лист персонажа не компилируется автоматически. Неиспользуемые UI-плейсхолдеры не являются входными характеристиками; новые факты добавляются вместе с использующей их механикой |
| Раунды и действия (Rounds, Combat Actions), PG V111–112/116–118 | Очередность, action slots, grants и запрет лишних действий | PC/Minion/Brute loop; отдельный M8 owner | PC выбирает Attack/Recover/Help, Shooting/Reload/Casting в действующих границах. Generated NPC атакует/перезаряжается и применяет поддержанные таланты | Нет общего автоматического выбора всех Manoeuvre/Improvise; перечисление шести действий не равно их полному исполнению |
| Атака, защита и урон (Attack, Protection, Damage), PG V118–119; GM VII91–93 | Opposed attack, damage/stagger/injury, основные и вторичные цели | Melee/ranged и профильные эффекты | PC и NPC используют реальные Tests, Traits и защиту (Defence/Athletics; PC также Melee против Close Shooting) | Автоматическая тактика ограничена текущими действиями/сценой; универсальная AoE-подстановка отсутствует, цели задаёт конкретный эффект |
| Раны и состояния (Wounds & Conditions), PG V119–123, Appendix190–191 | Таблица ран,11состояний, lifecycle и отдельные consumers; generic ConditionState не исполняет все ограничения сам | PC продолжает после1–23, учитывает24+смерть, руки/предметы/ongoing causes. M8 имеет отдельные ограниченные continuations | PC наследует этот путь; generated NPC сейчас Minion и побеждается одной принятой раной | Повторная невозможная анатомическая потеря и неподключённые последствия сохраняют stop; нет общего лечения кампании или всех путей NPC Recover |
| Судьба (Fate) и Удачливый (Lucky), PG III78/V111–112/120 | Session funding, spend/burn, Glorious/Near Miss и другие typed consumers | Glorious/Near Miss у PC; Second Action в ограниченном Hochland-пути | PC: настоящий расход и Lucky, текущие автоматические пороги. NPC: Fate не применяется | Нет общего оптимального выбора всех Fate options; повествовательные результаты остаются с явным GM-контекстом |
| Типы NPC (Minion, Brute, Champion, Monstrosity), GM VII91–93; PG191 | Разные injury policies и отдельные реакции | PC family допускает Minions/Brutes и профильные способности; M8 — ограниченного Champion-Wizard | Генератор создаёт только Minions | Общие generated Brutes/Champions/Monstrosities и выбор их способностей ещё отсутствуют;59каталожных loadouts не заменяют эту интеграцию |

Основания: [проверки](rules/core-tests.md), [бой](rules/combat.md), [раны/состояния](rules/wounds-and-conditions.md), [Судьба](rules/fate.md), [NPC](rules/npcs.md). Реальные границы: [профили Tests](../src/towr/domain/test_models.py), [PC admission](../src/towr/domain/pc_melee_models.py), [compiler фактов](../src/towr/application/encounter_character.py), [generated source](../src/towr/domain/generated_npc_models.py), [automatic controller](../src/towr/domain/pc_tactical_models.py). Репрезентативные проверки: [PC battle](../tests/integration/test_m9_pc_melee_battle.py), [тяжёлые раны](../tests/integration/test_m12_pc_heavy_wounds.py), [автоматическая тактика](../tests/integration/test_automatic_melee_tactics.py), [динамический JSON](../tests/integration/test_dynamic_encounter_json.py).

## Снаряжение и расходники (Equipment & Consumables)

<a id="equipment-and-consumables"></a>

| Группа / источник | Ядро и отдельный бой | Динамический PC | Генерируемый NPC | Оставшаяся граница |
| --- | --- | --- | --- | --- |
| Шесть одноручных оружий (Weapons,1H): Staff/Dagger/Axe/Sword/Warhammer/Morning Star; PG IV92–93 | Урон и применимые боевые свойства (Traits), Help/Defence, текущие Conditions | Есть | Есть | Пространственные и внебоевые свойства не становятся доступными без соответствующей сцены |
| Восемь fixed2H оружий (Weapons): Pickaxe/Flail/Billhook/Halberd/Glaive/Greataxe/Greatsword/Greathammer; PG IV92–93, Wounds190–191 | Общие Damage/Traits/BOTH grip; drop/Recover, руки, Critical и запасное1H PC | Есть | Есть | Общая область проверена; добыча ресурсов Pickaxe/Toil не относится к бою |
| Двуручный меч (Greatsword), PG IV93 | +1d Defence без Staggered по явной трактовке пользователя | Есть | Есть | Это решение пользователя, не подтверждённая официальная errata; [решение](decisions/ADR-0138-all-two-handed-weapons.md) |
| Пешее копьё и древковое оружие (Foot Spear/Polearm), PG IV93 | Переменный1H/2H хват одного предмета, Short reach, настоящий Charge | Есть | Есть | Cavalry Spear/Lance — напечатанные1H предметы вне перечня2H, их named loadouts не дают общего компонента |
| Безоружный бой и кастеты (Unarmed/Knuckledusters), PG IV93 | Есть отдельные primitives, включая замену на Staggered | Нет полного предмета/автоматической Brawn Attack | Нет | Соединить источник атаки, последствия и реальный выбор действия |
| Pistol/Repeater Pistol/Repeater Handbow, PG IV94–95/98–99 | Настоящие Shooting/Reload, режимы и цена Repeater | Несколько held/carried предметов, отдельные заряды и обратимая смена | Генерация нескольких предметов, actual equip, раздельные заряды/Reload, Shield drop/paid Recover | Полный каталог и все новые предметные эффекты остаются области Weapons |
| Девять Shooting2H, PG IV94–95 | Общие Free Reload/Exacting2–5, Optimum/GM maximum, Aim/Extreme/Hochland, nearby Blunderbuss | Есть | Есть | Повторяемый пространственный бой проверен; одноручная Sling остаётся вне перечня2H и без generated компонента |
| Утяжелённая сеть (Weighted Net), PG III68/IV96/V123 | BS/Throwing; конечный предмет, только Burdened даже по Defenceless; одна сеть за Brawn Recover, настоящий подбор | Есть | Есть | Остальные Throwing Weapons не входят в область2H; [общий владелец](../src/towr/domain/pc_weighted_net_models.py) |
| Лёгкая броня, щит и шлем (Light Armour, Shield, Helmet), PG IV97–98 | Общий ArmourLoadout, отдельные Resilience sources, фактический held Shield | Есть; Helmet сохраняет физическую броню без дополнительного бонуса | Есть, включая1H Shooting Shield→Reload→paid Recover | Запасные carried items сохраняются описанием; dual wield и shield bash как атака остаются области Weapons |
| Тяжёлая броня (Heavy Armour), PG IV97 | T+2, −1d Agility, независимый Burdened при S<3 | Подключена; Strength Enhancement пересчитывает только armour cause | Подключена в sampling/mutation/native execution | Общая область [ADR-0139](decisions/ADR-0139-all-armour-and-protection.md) реализована; проверки — в статусе |
| Полный латный доспех (Full Plate Armour), PG IV105 | T+3, −1d Agility, независимый Burdened при S<4 | Подключён как реальный предмет | Подключён, без подмены Light/Heavy skin | Bretonnian Warhorse не отменяет его penalty; Demigryph отменяет Agility penalty, но не требования Strength |
| Магическая броня (Magic Armour), GM VI85–86: Armour of Agilulf, Armour of Meteoric Iron, Briarroot Shield, Helm of the Hunt, Mantle of Ithilmar | Typed sources пяти предметов, layering, Test qualities/modifiers, damage ward, независимые bindings | Подключены source/traits, actual owners и character files | Подключены при явном разрешении видов предметов | Общая область реализована: [статус и проверки](project-status.md). Не объявлять весь Magic Items раздел завершённым |
| Конская броня (Barding), PG IV97–98/124, GM135/175–176 | Отдельные mount/rider bonuses и penalties; реальные mount variants, forced dismount/landing | Подключена к shared mounted owner | Доступна через отдельную ось поиска при совместимом маунте | Fly только при явном airspace; actual падение/атаки маунта и Barding проверены по ADR-0139 |
| Два активных оружия и переноска (Dual Wielding, Carrying Weapons), PG IV92 | Общий конечный инвентарь, реальные руки, один основной Damage и выбранные Traits; два Sword дают +2d Defence; отдельный заряд каждого gun | Несколько held/carried предметов прежних исполняемых видов; общий ввод/подготовка по всему набору, индивидуальный Loaded в UI; Carrying даёт независимый Burdened | Source/генерация нескольких предметов, все item/grip profiles и actual выбор/equip, независимые Net units и Carrying | Полный frozen intent и новые применимые эффекты остаются в работе; выбор NPC ограниченный, без гарантии оптимальной тактики |
| Лечебное и усиливающее зелья (Healing Potion, Enhancement Potion), GM VI88–90 | PC Recover, конечный запас и consumption proofs; лечение одной поддержанной раны1–23 | Есть; усиление WS/S/T/Ag | Нет | Остальные характеристики, расходники NPC и иные зачарованные предметы (Enchanted Items) |
| Прочие предметы и одежда (Trappings, Outfits), PG IV97–101 | Нормативные данные и отдельные consumers | Нет общего исполнения | Нет | Не относятся к Armour автоматически; социальные/местностные эффекты вводить с соответствующими consumers |

Основное описание: [снаряжение](rules/equipment.md), [магические предметы](rules/magic-items.md). Исполнение: [PC Damage/Traits](../src/towr/domain/pc_weapon_models.py), [inventory admission](../src/towr/application/encounter_inventory.py), [generated equipment bridge](../src/towr/domain/pc_generated_equipment.py), [weapon inventory](../src/towr/domain/pc_weapon_inventory.py), [shield owner](../src/towr/domain/pc_shield_models.py), [зелья](../src/towr/domain/pc_potion_models.py). Проверки: [dynamic character](../tests/unit/test_encounter_character.py), [inventory](../tests/unit/test_encounter_inventory.py), [2H Traits](../tests/unit/test_m19_pc_weapon_traits.py), [generated equipment](../tests/unit/test_generated_npc_equipment.py), [dynamic potions](../tests/integration/test_dynamic_potions.py).

### Полная область Weapons/Equipment после Armour

[ADR-0140](decisions/ADR-0140-all-weapons-and-shared-inventory.md), PG IV92–96 и GM VI82–84/VII93/103:50каталожных строк, включая нематериальный Unarmed. Уже исполняемые ordinary-компоненты из таблицы выше переиспользуются. Ниже — полный остаток этой области, а не выбранный чанк. Контракт принят; новый публичный допуск появится вместе с полным исполнением. Каталог и общие предметные модели уже проверены, но не закрывают область.

| Элемент / источник | Необходимое исполнение обеими сторонами | Текущее состояние |
| --- | --- | --- |
| Безоружный бой (Unarmed), PG69/92–93 | Brawn против Athletics/Endurance; Staggered, shove/спешивание; фактический доступ к Defence от другого предмета | Общего режима нет; не физический предмет и не carrying slot |
| Кастеты (Knuckledusters), PG92–93 | Brawn/DamageS−1, пригодная рука, conceal Trait, сами не дают Defence | Нет общего предмета |
| Кавалерийское копьё (Cavalry Spear), PG93 | Short/S/1H; mounted Charge+1d Melee, пешее применение остаётся законным | Только неполные профильные пути |
| Пика (Lance), PG93 | Close/S+1/1H; mounted Charge+1d/+1Damage; нельзя Dual Wield | Есть canonical NPC, нет общего компонента |
| Праща (Sling), PG94–95 | Strength Damage, optimum Medium, maximum Long, free Reload/Close restriction и общий инвентарь | PC/K1 есть; generated отсутствует |
| Камень (Rock), PG96 | BS/Throwing, только Staggered с Wound лишь при повторении, конечный подбираемый предмет | Одна пригодная рука принята как GM-конкретизация; общего throw owner нет |
| Метательное копьё (Throwing Spear), PG96 | S, Close–Medium, физический расход/подбор | Нет |
| Метательный топор (Throwing Axe), PG96 | S+1/Short, +1Damage против armoured с mundane provenance, расход/подбор | Нет |
| Метательные ножи (Throwing Knives), PG96 | S/Short, самодостаточный комплект на бой, не бесконечные Spear/Axe | Нет |
| Масляная склянка (Oil Flask), PG96 | Одноразовый throw, actual Close splash/Ablaze всех целей, Endurance Hazard2/end phase и тушение | Нет полного owner |
| Подрывной заряд (Blasting Charge), PG96 | HIT target Zone/MISS own Zone, немедленный Hazard3/Endurance всех существ с реальными Wounds/Fate/GM defeat | K1 Hazard/Zone reducers есть; weapon owner отсутствует |
| Dragon Bow, GM82 | Magical Damage6/2H/Medium–Extreme; отмена penalties/Grim с реальной видимостью; огненная стрела раз за бой | Нет общего предмета |
| Duellist Blades, GM83 | Один2Hпредмет, S+2/+2dDefence; второе Attack отдельным действием/качества/общий предел двух действий | Нет; не два обычных Sword |
| Grotargg’s Hammer, GM83 | S+3/2H; higher ground Glorious, только такой MISS застревает, настоящий Brawn−2d/возврат экземпляра | Нет; Prone нормативно даёт higher ground |
| Headsman’s Axe, GM83 | S+3/2H; optional Grim против Prone, замена фактической Wound на Decapitation | Kernel Wound lifecycle есть, предметного owner нет |
| Morning Star of Fracasse, GM83 | S+3/1H/−1d при Staggered; HIT выбивает конкретный held magic item, конечный возврат | Нет; скрытое наследование ordinary Traits запрещено |
| Scarab Knife, GM84 | S+1/1H, HIT Drained, charge за actual Wound, расход3charges на лечение, sunset lifetime | Цены/момент/получатель приняты в ADR-0140; runtime ещё отсутствует |
| Sword of Justice, GM84 | S+1/1H, +1dWoundsTable; Glorious в single combat против PC/Champion | Нет; Count1v1 не подменяет согласованное определение |
| Trickster Blade, GM84 | S+1/1H/+1dDefence без Staggered; иллюзорный облик с GM-фактами формы/размера | Нет; облик не создаёт автоматическую засаду |
| Unwavering Spear, GM84 | S+1/2H/Short, реальный запрет Give Ground и Glorious против already Given Ground в раунде; downtime regrowth/burn facts | Нет; нужны actual reaction movement и события раунда |
| Ogre Pistol, GM93/103 | Собственные BS/Shooting владельца,5Damage/1H/ignore/Reload3, optimum Close–Medium, maximum Long; GM fit | Shared ranged и canonical NPC есть; общий item PC/generated отсутствует |
| Общие экземпляры/руки/переноска, PG92/94/118 | Несколько held/carried, выбранный WeaponUse/Skill, индивидуальные Reload/stock/charges, независимый carrying Burdened, два готовых gun без объединённой Attack | PC/NPC source и runtime общие, Skills/Lore/Kit по всему набору; NPC sampler/mutation/JSON/UI сохраняют несколько предметов и конечные Net units. Фактические native/transport проверки — в статусе; новые Magic charges/Throwing owners ещё подключаются |
| Все actual drops/pickups | Физический marker любого предмета, source-bound ACK, Fly/Close/руки/опутывания, без refill/телепорта | Ordinary spatial drop теперь имеет marker/ACK/платный подбор; общий multi-item lifecycle ещё в работе |
| Dual Wield/Traits, PG92–93 | Основной Damage/Skill, реальные contributors/руки, stacking, запреты предметов, effect-local magic provenance | Native PC использует реальные Attack/Protection implements, включая два Sword; полный общий intent и generated multi-item исполнение ещё в работе |
| Особенности сцены и обязательные последствия, PG115/122–123 | Staff/Difficult Terrain, actual visibility/cover, Blast/Oil targets, Ablaze и очередь end phase, single combat/реальный Give Ground | Открытая линия и Flying/Falling есть; новые зависимости входят в эту область |

## Таланты (Talents)

Существующий [реестр59талантов](rules/talents.md), PG III73–81, остаётся основным списком. Прочитанный каталог не равен59исполненным эффектам. Общей системы покупок/рангов/развития пока нет.

| Возможность | Ядро / отдельный бой | Динамический PC | Генерируемый NPC | Оставшаяся граница |
| --- | --- | --- | --- | --- |
| Удачливый (Lucky), PG78; Волшебник (Wizard), PG81 | Lucky funding и gambling primitive; Wizard Casting owners | Lucky; Wizard1–4/Elementalism с двумя memorised spells | Ни Lucky/Fate, ни общего caster | Wizard profile не является полной progression/improvised magic; gambling не выбирается боевой тактикой |
| Оборонительная стойка и Дикая атака (Defensive Stance, Wild Attack), PG74/81 | Общий source-bound lifecycle цены/реакции и однократность | Есть, Attack/Melee Help, автоматический выбор и acquisition facts | Есть, constrained generation и принятая тактика | Не расширять этот факт до общего автоматического использования всех Talents |
| Сопротивление магии (Magic Resistance), PG78/157 | Target-scoped Potency−1; не защита от Miscast | Текущий talent admission не допускает | Есть против двух PC spells | Подключение к PC должно сопровождать реального вражеского caster |
| Боевой хирург (Combat Surgeon), PG74/110/122 | Подавление Wound effects/Exacting surgery/healing consumers | Нет выбора операции в общем battle owner | Нет | Action-bound primitive не равен готовому поведению участника боя |
| Остальные группы | Нормализованные определения; местами общие modifiers/Tests | Нет общего допуска | Нет общего допуска | Подключать совместимыми группами: Attack/Protection/Help; лечение; Aim/Reload/реакции; психология; магические Talents |

Внутри вехи всех талантов можно переиспользовать уже существующие Attack/Help/Wound owners: Armour Bane и Allies in Arms(PG73), Mighty Blow(PG79, после2H), Hardy(PG76, для PC/Champion Wounds Table). Эти четыре примера не ограничивают полный перечень59и не объявляются автоматически допустимыми у Minions. Для Recovery, пространственных реакций и магических Talents нужны соответствующие владельцы действий/событий.

Evidence: [PC tags/admission](../src/towr/application/encounter_character.py), [generated talent facts](../src/towr/domain/generated_npc_models.py), [общий lifecycle](../src/towr/domain/pc_generated_talents.py), [PC advice](../src/towr/domain/pc_talent_advice.py), [Combat Surgeon](../src/towr/rules/combat_surgeon_resolution.py). Проверки: [talent generation](../tests/unit/test_generated_npc_talent_generation.py), [NPC reactions](../tests/unit/test_generated_npc_reactions.py), [PC execution](../tests/unit/test_pc_combat_talent_execution.py), [Magic Resistance](../tests/unit/test_generated_npc_magic_resistance.py).

## Магия и вера (Magic & Faith)

<a id="magic-and-faith"></a>

| Область / источник | Ядро | Отдельный бой | Динамический PC / генерируемый NPC | Оставшаяся граница |
| --- | --- | --- | --- | --- |
| Сотворение и сила заклинания (Casting, Potency), PG VIII155–159 | Pool/Rule of Nine, CAST/WAIT, interruption/abandonment, target preflight и typed effects | Раздельные ограниченные PC и M8 owners | PC Wizard1–4/Elementalism; **generated caster отсутствует** | Общий caster/target lifecycle обеих сторон; повторное использование M8 не равно подключению generic NPC |
| Формальные заклинания (Formal Spells), PG162–174 | Нормализованы42: Battle Magic10, Elementalism11, Illusion10, Necromancy11 | M8: Curse of Cowardly Flight; PC: Lightning Blast/Fire Breath(PG165) | PC только эти два memorised spells; NPC нет | Каталог metadata не исполняет эффекты; нужны группы прямого урона/Conditions, временных эффектов, пространства/призывов |
| Импровизированные заклинания (Improvised Spells), PG160–161/164/167/171/174 | Scale/CV/GM-границы нормализованы | Общего исполнения нет | Нет / нет | Произвольный эффект не вычисляется из описания; отдельный GM-контракт необходим |
| Магические ошибки (Miscasts), PG157–159 |21typed entry; часть reducers возвращает follow-up/GM request | PC исполняет принятые боевые последствия, M8 имеет другой opt-in набор | PC имеет6неисполняемых entry IDs; NPC caster нет | Objects Transfigured5–6, Random Transport17–18, Spell Recast23–24, Zone Hazard33–34, Daemon Rift37, Fascinating Rift38 сохраняют stop. Ноль unknown в малом прогоне не означает полное покрытие |
| Вера, молитвы и чудеса (Faith, Prayers, Miracles), PG75/137–149 | Нормализованы10Favours/30Prayers, runtime отсутствует | Нет | Нет / нет | Самостоятельный блок боевых эффектов/ресурсов; повествовательные Miracles сохраняют GM-owned масштаб |

Основные каталоги: [магия](rules/magic.md), [заклинания](rules/spells.md), [религия](rules/religion.md). Реальный допуск: [PC Wizard/spells](../src/towr/domain/pc_magic_source_models.py), [исполнение PC magic](../src/towr/domain/pc_magic_models.py), [Miscast plans](../src/towr/domain/pc_magic_miscast_plan.py), [M8 canonical scenario](../src/towr/domain/npc_magic_scenario_models.py). M8 требует одного authored Champion-Wizard с canonical Curse, без оружия/брони/щита, и numeric Shooting Minions; это отдельный полезный путь. Проверки: [dynamic magic](../tests/integration/test_dynamic_pc_magic.py), [PC magic execution](../tests/unit/test_pc_magic_execution.py), [Miscast admission](../tests/unit/test_pc_magic_miscast_plan.py).

## Сцена и движение (Zones, Range & Movement)

| Возможность / источник | Ядро и отдельные composites | Непрерывный бой вне генератора | Динамический путь |
| --- | --- | --- | --- |
| Зоны/дистанции/местность (Zones, Range, Battlefield Features), PG V114–115 | Spatial state, adjacency, speed, difficult terrain/hazards, movement guards | Отдельные NPC/M8 сцены; PC battlefield с явными нетранзитивными Close pairs | Dynamic: начальные две группы в открытой линии Zones, Close–Extreme и GM максимум2H; произвольная карта/terrain/засада вне текущей области |
| Перемещение, бег и натиск (Free Movement, Run, Charge), PG116–117 | Typed executors, включая составные пути через terrain | Общие PC/NPC owners, настоящие Free Movement/Run/Charge, Speed и раны | Подключены к dynamic battlefield; Close-отход стрелков проверен, оптимальное планирование/произвольный kiting не заявлены |
| Прицеливание, скрытность и отступление (Aim, Hidden, Give Ground, Retreat), PG116–120 | History/provenance, потери Aim, movement и отдельные последствия | Scripted Aim/Hochland, hidden chains, ограниченный выход Broken NPC | Нет общего пространственного выбора. Повторный Staggered PC выбирается в нынешней сцене без выхода; кампанийные последствия не становятся автосимуляцией |

Основания: [бой](rules/combat.md) и [kernel orchestration](architecture/resolution-kernel.md). Evidence: [пространство](../src/towr/domain/spatial_models.py), [free movement](../src/towr/rules/free_movement_resolution.py), [Charge](../src/towr/rules/charge_action_execution.py), [динамический admission](../src/towr/application/dynamic_encounter.py), [Short opening](../src/towr/domain/pc_melee_models.py). Проверки: [spatial](../tests/unit/test_k1_spatial_resolution.py), [terrain Charge](../tests/unit/test_k1_difficult_terrain_charge_action_execution.py), [Aim/Charge chain](../tests/integration/test_k1_aim_charge_cycle.py).

## Что считается завершённой областью

Пользователь выбрал целые области для всех применимых сторон: всё двуручное оружие, вся броня, все таланты, вся магия. Для всей области нужны полный книжный перечень и учёт зависимостей; для каждого применимого элемента нужны вместе: книжное правило и условия применения; полные факты источника/совместимость; реальное исполнение и состояние; доступность через dynamic input/generation; автоматический выбор применимых действий; актуальные JSON/UI/character files; детерминированные проверки и небольшой сквозной пример. Новое поле, каталожная запись, несколько готовых предметов или ещё один fixed NPC не завершают всю область. Нерешённые строки и неподключённые эффекты сохраняются в остатке. Внутренние небольшие изменения/проверки допустимы; вся веха может продолжаться в нескольких сессиях.

Тактика остаётся явной стратегией симулятора и учитывает новые легальные действия; она не должна превращать отсутствующее правило в no-op. Существенные неоднозначности и изменения согласованного контракта оформляются до реализации. Нет потребности заранее создавать универсальный DSL, шину событий или декартов каталог всех сочетаний.

Актуальная очередь функций и ближайший чанк находятся в [roadmap](roadmap.md#очередь-расширения-боевых-возможностей). Текущий статус и точка продолжения — в [project-status](project-status.md#следующий-шаг). Точная настройка поиска отложена; корректность, воспроизводимость, небольшие сквозные проверки и устранение измеренных performance-проблем сохраняются.
