# Покрытие боевых возможностей

Дата: 2026-11-18. Инвентаризация текущего допуска на базе `624522d`: нормализованные правила сопоставлены с моделями, владельцами боя, входом генератора и имеющимися проверками. Новые игровые правила и runtime-контракты этим документом не вводятся. Код и репрезентативные тесты просмотрены; тесты и Monte Carlo в этой задаче не запускались.

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
| Семь двуручных оружий (Weapons,2H): Pickaxe/Flail/Billhook/Halberd/Glaive/Greataxe/Greathammer; PG IV92–93, Wounds190–191 | PC: BOTH grip, drop/Recover, повреждение рук, Critical, запасное1H | **Есть**, включая2H→1H backup | **Нет** | Подключить общий component source/derived Damage/Traits/2H/совместимость со щитом; named2H NPC не заменяют это |
| Двуручный меч (Greatsword), PG IV93 | Каталог прочитан; профиль исключён из исполнения | Нет | Нет | Не разрешена запись `+1 to Defence` без `d`; [открытый вопрос](open-questions.md#бонус-greatsword) |
| Копья и древковое оружие (Foot Spear/Polearm/Cavalry Spear/Lance), PG IV93 | Есть нормативные таблицы и отдельные named loadouts | Нет как общих предметов | Нет | Общий переменный хват, натиск (Charge) и верховой бой (Mounted Combat) |
| Безоружный бой и кастеты (Unarmed/Knuckledusters), PG IV93 | Есть отдельные primitives, включая замену на Staggered | Нет полного предмета/автоматической Brawn Attack | Нет | Соединить источник атаки, последствия и реальный выбор действия |
| Pistol/Repeater Pistol/Repeater Handbow, PG IV94–95/98–99 | Настоящие Shooting/Reload, режимы и цена Repeater | Есть: щит и один backup, обратимая смена | Есть: без щита/backup | Другие сочетания инвентаря не выводятся из наличия стрелкового профиля |
| Остальные10стрелковых оружий (Ranged Weapons), PG IV94–95 | Всего13PG profiles; scripted PC Short opening обычно исполняет залп→backup. Aim/Blunderbuss имеют свои границы | Нет | Нет | Пространство, диапазоны, движение и тактика повторных выстрелов; полный цикл всех13не заявляется |
| Метательное оружие (Throwing Weapons), PG IV96 | Generic preparation; Weighted Net исполняется у canonical Night Goblin с Spear fallback | Нет | Нет | Общие предметы/конечный запас/подбор/автоматическая тактика; спорный Net→Defenceless путь не разрешён |
| Лёгкая броня, щит и шлем (Light Armour, Shield, Helmet), PG IV97–98 | Отдельные Resilience sources; руки/drop/Recover; shield Defence против стрельбы | Есть; Helmet сохраняет факт ношения брони без выдуманного дополнительного бонуса | Light Armour у melee/ranged; Shield только melee; отдельного Helmet-компонента нет | Запасные щиты, shield bash и общий инвентарь NPC не исполнены |
| Тяжёлая броня (Heavy Armour), PG IV97 | Правила нормализованы; общего typed исполнения штрафа Agility и Burdened нет | Draft/save; расчёт отвергает | Нет | Бонус `armour_bonus=2` у authored source не является полной реализацией Heavy Armour |
| Два активных оружия и переноска (Dual Wielding, Carrying Weapons), PG IV92 | PC inventory owner хранит положения; исполняется одно активное оружие и допустимый один backup | Более широкий draft сохраняется, неподдержанный loadout отвергается | Нет общего инвентаря | Совмещение Traits, несколько carried items, ограничения переноски/рук; нельзя молча выбрать один из двух мечей |
| Лечебное и усиливающее зелья (Healing Potion, Enhancement Potion), GM VI88–90 | PC Recover, конечный запас и consumption proofs; лечение одной поддержанной раны1–23 | Есть; усиление WS/S/T/Ag | Нет | Остальные характеристики, расходники NPC и иные зачарованные предметы (Enchanted Items) |
| Прочие предметы и бардинг (Trappings, Barding), PG IV97–101 | Нормативные данные и отдельные consumers | Нет общего исполнения | Нет | Социальные, местностные и mounted эффекты вводить вместе с использующей их функцией |

Основное описание: [снаряжение](rules/equipment.md), [магические предметы](rules/magic-items.md). Исполнение: [PC Damage/Traits](../src/towr/domain/pc_weapon_models.py), [inventory admission](../src/towr/application/encounter_inventory.py), [generated equipment bridge](../src/towr/domain/pc_generated_equipment.py), [weapon inventory](../src/towr/domain/pc_weapon_inventory.py), [shield owner](../src/towr/domain/pc_shield_models.py), [зелья](../src/towr/domain/pc_potion_models.py). Проверки: [dynamic character](../tests/unit/test_encounter_character.py), [inventory](../tests/unit/test_encounter_inventory.py), [2H Traits](../tests/unit/test_m19_pc_weapon_traits.py), [generated equipment](../tests/unit/test_generated_npc_equipment.py), [dynamic potions](../tests/integration/test_dynamic_potions.py).

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
| Зоны/дистанции/местность (Zones, Range, Battlefield Features), PG V114–115 | Spatial state, adjacency, speed, difficult terrain/hazards, movement guards | Ограниченные NPC/M8 сцены; PC Short opening в одной Zone | Одна неподвижная сцена: все Close, открытая местность, без засады (Ambush), выхода/преследования |
| Перемещение, бег и натиск (Free Movement, Run, Charge), PG116–117 | Есть typed executors, включая составные пути через terrain | Есть отдельные chains; PC Short→Close approach перед Melee без Charge | Нет свободного выбора движения/Charge/kiting; Short opening не подключён к dynamic request |
| Прицеливание, скрытность и отступление (Aim, Hidden, Give Ground, Retreat), PG116–120 | History/provenance, потери Aim, movement и отдельные последствия | Scripted Aim/Hochland, hidden chains, ограниченный выход Broken NPC | Нет общего пространственного выбора. Повторный Staggered PC выбирается в нынешней сцене без выхода; кампанийные последствия не становятся автосимуляцией |

Основания: [бой](rules/combat.md) и [kernel orchestration](architecture/resolution-kernel.md). Evidence: [пространство](../src/towr/domain/spatial_models.py), [free movement](../src/towr/rules/free_movement_resolution.py), [Charge](../src/towr/rules/charge_action_execution.py), [динамический admission](../src/towr/application/dynamic_encounter.py), [Short opening](../src/towr/domain/pc_melee_models.py). Проверки: [spatial](../tests/unit/test_k1_spatial_resolution.py), [terrain Charge](../tests/unit/test_k1_difficult_terrain_charge_action_execution.py), [Aim/Charge chain](../tests/integration/test_k1_aim_charge_cycle.py).

## Что считается завершённой областью

Пользователь выбрал целые области для всех применимых сторон: всё двуручное оружие, вся броня, все таланты, вся магия. Для всей области нужны полный книжный перечень и учёт зависимостей; для каждого применимого элемента нужны вместе: книжное правило и условия применения; полные факты источника/совместимость; реальное исполнение и состояние; доступность через dynamic input/generation; автоматический выбор применимых действий; актуальные JSON/UI/character files; детерминированные проверки и небольшой сквозной пример. Новое поле, каталожная запись, несколько готовых предметов или ещё один fixed NPC не завершают всю область. Нерешённые строки и неподключённые эффекты сохраняются в остатке. Внутренние небольшие изменения/проверки допустимы; вся веха может продолжаться в нескольких сессиях.

Тактика остаётся явной стратегией симулятора и учитывает новые легальные действия; она не должна превращать отсутствующее правило в no-op. Существенные неоднозначности и изменения согласованного контракта оформляются до реализации. Нет потребности заранее создавать универсальный DSL, шину событий или декартов каталог всех сочетаний.

Актуальная очередь функций и ближайший чанк находятся в [roadmap](roadmap.md#очередь-расширения-боевых-возможностей). Текущий статус и точка продолжения — в [project-status](project-status.md#следующий-шаг). Точная настройка поиска отложена; корректность, воспроизводимость, небольшие сквозные проверки и устранение измеренных performance-проблем сохраняются.
