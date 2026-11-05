# Каталог NPC profiles и Special Abilities

Источник: `BOOK-GM-GUIDE`, версия 1.1, глава Allies and Antagonists, страницы 94–187. Статус области: `draft/partially implemented`. Этот документ индексирует профильные правила; точные Characteristics, Skills, Protection, Damage и Wound bands перед реализацией загружаются из указанной страницы в типизированный profile data layer.

## RULE-PROFILE-TALABEC-001..011 — Grand Duchy of Talabec

| Страница | Profile | Type | Нормативные profile effects |
|---:|---|---|---|
| 96 | Empire Peasant | Minion | `Torches and Pitchforks`: Help союзной Melee attack без Test даёт `+1d` и может превысить обычный предел bonus dice |
| 96 | Artisan | Minion | `Professional Pride`: одна extra Coin при прямой покупке у Artisan даёт `+1d` следующему Test с этим trapping |
| 96 | Empire Townsfolk | Minion | `Streetwise`: `+1d Awareness` при opposition попытке pickpocket |
| 97 | Brigand | Minion | `Craven Opportunist`: при численном превосходстве Melee получает `+2d` вместо `+1d` |
| 97 | Footpad | Minion | `Lurker`: вне battle Awareness Tests для обнаружения затаившегося Footpad Grim |
| 97 | Town Watch | Minion | `Whistleblower`: Recover action вызывает подкрепление на следующий turn и делает Athletics Tests для Retreat от них Grim |
| 98 | Empire Official | Brute (2 Wounds) | на 1 Wound получает Broken; `Heard It All Before`: Persuade/Distract против Official Grim, если не включает взятку |
| 98 | Empire Noble | Champion | `Look Out Sir!`: пока ally меньшего Status в Close Range, все attacks по Noble Grim |
| 100 | Empire State Trooper | Minion | `Supporting Action`: при входе врага в Close Range один Trooper/Free Company ally в соседней Zone, сам не в Close Range врага, немедленно Charge либо делает ranged attack |
| 101 | Empire Knight | Brute (2 Wounds) | на 1 Wound Drained; mounted `Noble Steed` даёт `+1 Resilience`, Fast и successful non-Monstrosity Charge накладывает Prone до Give Ground; `For the Order`: Charge Attack Tests Glorious, пока Knight не Staggered |
| 102 | Priest of Taal | Champion | `Taal’s Favour`: hunt/track/wilderness stealth Tests Glorious, woodland Difficult Terrain игнорируется, преследователь в wilderness всегда обнаруживается; `Tanglefoot`: action создаёт Difficult Terrain в vegetated Zone в Long Range для существ без Taal’s Favour |

Поля faction goals, gossip, names и adventure hooks на страницах 94–102 являются `LORE/GUIDANCE`. Таблица `A Noble Vendetta` страницы 95 — опциональная d10 campaign consequence, а не автоматически срабатывающая Ability этих profiles.

<a id="brigand-craven-m22"></a>

## RULE-PROFILE-TALABEC-004 — Brigand / Craven Opportunist (M22)

Статус среза: `verified` в PC family. BOOK-GM-GUIDE1.1, Allies and Antagonists / Brigands & Footpads97; выбор carried weapons — Understanding NPC Profiles93. Четвёртая запись таблицы Talabec выше — Brigand, пятая — Footpad. [ADR-0077](../decisions/ADR-0077-pc-brigand-craven-opportunist.md), [factory/JSON/CLI](../examples/m22/README.md).

`PcBookNpcProfile.BRIGAND_AXE` — явный Axe-only loadout: Minion1Wound, Toughness3/Resilience4 armoured, Axe Close3d/3 Damage3,1H и Athletics3d/2. `ResilienceProfile(3,1)` сохраняет броню. Warbow из полной карточки указан как unselected, а не скрыт под названием полного Brigand profile. NPC Axe не получает PC `+1 Damage` против брони без указанного Trait.

Craven Opportunist при Melee атаке с численным превосходством даёт **+2d вместо +1d**. Считаются все пригодные союзники в Zone, включая самого атакующего, а не только Brigands. Defeated/Defenceless/noncombatants исключаются, Staggered и закончившие ход продолжают считаться. Состав проверяется заново перед каждой Attack. GM withholding через outnumbering approval убирает весь modifier, включая эту замену.

Единственный modifier имеет Rule ID `RULE-PROFILE-TALABEC-004:craven-opportunist`; обычный +1d с ним не складывается. Остальные NPC и PC сохраняют обычный бонус. Higher-ground modifier отдельный. Drained удаляет положительный +2d в существующей preparation цепи; нынешний fresh physical Minion native path не вызывает Drained у Brigand до defeat, поэтому эта граница проверяется pure.

Каталог хранит active Ability name/scope/effect и unselected weapon metadata; текст metadata не исполняется как программа. Runtime helper выбирает правило только после canonical definition validation. Fact `no_additional_abilities` исключает неподдержанные применимые effects, сохраняя реализованный Craven. Current JSON1 уже выражает full definition/source/gear: новых полей/version/метрик и миграции старых пар нет.

Реализация: [catalog/loadout](../../src/towr/domain/pc_npc_catalog.py), [явный modifier helper](../../src/towr/domain/pc_npc_ability_models.py), [actual count preparation](../../src/towr/domain/pc_melee_result_models.py). Проверки: [данные/metadata](../../tests/unit/test_m22_pc_brigand_catalog.py), [native/pure/forgery](../../tests/unit/test_m22_pc_craven_opportunist.py), [process/full-source JSON/подбор](../../tests/integration/test_m22_pc_brigand.py).

<a id="official-broken-m23"></a>

## RULE-PROFILE-TALABEC-007 — Empire Official / первая рана (M23)

Статус среза: `verified` в PC family. BOOK-GM-GUIDE1.1, Allies and Antagonists / Empire Official98, Brutes92 / NPC Profiles93; BOOK-PLAYER-GUIDE1.4, Conditions / Broken122. Official — седьмая запись группы Talabec001..011. [ADR-0078](../decisions/ADR-0078-pc-official-first-wound-broken-boundary.md), [factory/JSON/CLI](../examples/m23/README.md).

`EMPIRE_OFFICIAL_DAGGER` — явный Dagger-only loadout: Brute2, Toughness3/Resilience3, Dagger Close2d/3 Damage2,1H; Athletics3d/3. Pistol сохранён как unselected. Heard It All Before делает Persuade/Distract Grim, если попытка не включает bribe; нынешняя family таких действий не исполняет, поэтому способность сохранена в inactive metadata.

| Profile Wounds | Последствие |
|---|---|
| 0 | Нет дополнительного эффекта |
| 1 | Suffer Broken |
| 2 | Defeated |

Brute не бросает PC Wounds Table. Broken применяется один раз при фактическом living0→1 profile ACK, после raw Attack; обычные authored static Brutes не получают этот эффект. На W2 действует прежний defeat/GM disposition. Metadata wound_bands описательна, runtime helper явный для данного профиля.

Broken требует тратить **свой ход** на движение в безопасную Zone, при необходимости Manoeuvre. Он не запрещает Athletics Protection и не накладывает Grim на обычную защиту. Пользователь выбрал M23: завершить все последствия/предыдущие end phases, позволить другим участникам продолжить, затем остановиться перед TurnStart живого Broken Official, когда именно он следующий actor. W2 до окна даёт нормальный defeat; party death и final budget сохраняют свой обычный приоритет.

`PcNpcBrokenTurnUnsupported` сохраняет actor, exact PC Attack execution ID, Brute0→1 change и источник `RULE-PROFILE-TALABEC-007:first-wound-broken:{actor}:{attack_id}`. Причина `npc_broken_turn` не использует фиктивные PC table_total. Очередь уже завершена, ход Official не начат; дальнейшие steps запрещены. Подмена receipt/actor или одинаковых изменений разных Officials не проходит full replay.

Без exit policy сохраняется граница M23: собственное бегство не исполняется, unsupported trials остаются в знаменателе и исключают кандидата из выбора. Поддержанное продолжение M24 описано ниже; Willpower/Leadership Recover и поведение после ухода не включены.

Реализация: [catalog/wound bands](../../src/towr/domain/pc_npc_catalog.py), [effect/stop cause](../../src/towr/domain/pc_npc_wound_models.py), [profile ACK projection](../../src/towr/domain/_pc_melee_projection.py). Проверки: [данные](../../tests/unit/test_m23_pc_official_catalog.py), [native order/source/guards](../../tests/unit/test_m23_pc_official_wounds.py), [actual process/JSON/подбор](../../tests/integration/test_m23_pc_official.py).

<a id="official-exit-m24"></a>

### Продолжение M24: свободный выход Broken NPC

BOOK-PLAYER-GUIDE1.4, Rules / The Battlefield114–115 / Free Actions116–117 / Broken122: свободное движение с Normal Speed позволяет перейти в соседнюю Zone. Broken требует наиболее быстрого допустимого пути в Zone без врагов; Run/Manoeuvre нужны, когда одного свободного движения недостаточно. Окружение и препятствия нельзя игнорировать.

[ADR-0079](../decisions/ADR-0079-pc-broken-npc-adjacent-exit.md) допускает один явно подтверждённый clear/fastest adjacent exit. Source содержит nullable npc_broken_exit_policy и can_leave_zone=true; все PC остаются в arena, закрытая сцена не содержит скрытых внешних врагов. Actual own-turn FreeMovement receipt переносит Official, сохраняя W1/Broken/not defeated. Выход не расходует standard action или RNG. Вышедший actor исключается из дальнейших целей, ходов, outnumbering и новых Help choices; прежний адресованный ему Help не переносится.

Пользователь выбрал objective «все NPC побеждены или ушли». Это цель сценария; уход учитывается отдельными счётчиками trials/summary и не считается defeat. Преследование, возврат и Recover за пределами arena не моделируются. Снятие Broken при сохраняющейся Wound остаётся открытым вопросом. Current JSON1 требует явную nullable policy и exit metrics; прежние примеры мигрированы с null/нулями без изменения старых результатов. [Исполняемый пример](../examples/m24/README.md).

<a id="state-trooper-m25"></a>

## RULE-PROFILE-TALABEC-009 — Empire State Trooper / Halberd и Defence (M25)

Статус: `verified` в текущей PC family. BOOK-GM-GUIDE1.1, Allies and Antagonists / Empire State Trooper100 и Understanding NPC Profiles93. Это девятая запись Talabec001..011; [factory/JSON/CLI-пример](../examples/m25/README.md).

`EMPIRE_STATE_TROOPER_HALBERD` фиксирует Halberd-only loadout и Defence Protection: Minion1, Toughness3/Resilience4 armoured → ResilienceProfile(3,1), Normal Speed, Halberd Close3d/3 Damage5,2H и Defence3d/4. Напечатанная Athletics3d/3 сохранена как числовой unselected Protection в metadata; Spear/Crossbow/Handgun явно unselected. Это выбранный боевой подпрофиль, не автоматический выбор лучшей Protection в каждом Test и не полная карточка со всеми weapons. Вооружённая2H Defence допустима; shields нет. GM93 позволяет выбирать снаряжение до боя и не переносит PC Traits оружия на NPC автоматически: Halberd сохраняет Damage5 без PC-бонуса против брони.

**Supporting Action:** когда враг входит в Close Range State Trooper, один союзный State Trooper либо Free Company Militia (GM112) из соседней Zone, который сам не находится в Close Range врага, может немедленно Charge либо сделать ranged attack. В текущей aware Close arena все PC уже находятся в Close и не перемещаются, внешних участников нет; обязательное PC Giving Ground не подставляется вместо выбранного SUFFER_WOUND. Способность inactive с сохранённым полным trigger/effect. Уход союзного Official не является входом врага. Расширение scene/движения требует исполнения способности, а не игнорирования metadata.

Canonical admission связывает весь фиксированный профиль с root/attack/Protection identities, включая сохранённый unselected Athletics source. Подмена Damage, рук, брони или Defence→Athletics под тем же identity отклоняется, даже после переименования root с сохранением книжных nested sources; cached bool/enum aliases не становятся observation. Прежние четыре definitions/snapshots не меняются. У PcBookNpcEntry добавлен descriptive unselected_protection tuple; у прежних записей он пуст.

Реализация следует существующему каталогу и выбранной NPC Protection, без нового owner/kernel/AI. Current JSON1/схемы/метрики прежние, старые32request/result pairs не мигрируются. [Catalog/native/guards tests](../../tests/unit/test_m25_pc_state_trooper.py), [JSON/trials/count search](../../tests/integration/test_m25_pc_state_trooper.py).

## RULE-PROFILE-PEOPLES-001..008 — Ogres, Halflings, Dwarfs, Elves и Bretonnia

| Страница | Profile | Type | Нормативные profile/attack effects |
|---:|---|---|---|
| 103 | Imperial Ogre | Brute (3 Wounds) | при 1–2 Wounds Speed Normal; Rough Shove hit накладывает Prone; успешный Charge Rough Shove позволяет второй action другой attack; `Fearsome` даёт Broken после Give Ground от Melee; Rough Shove против уже Staggered через `Mighty Throw` перемещает цель в Long Range, наносит Wound и Prone |
| 103 | Halfling Thief | Minion | может Stealth Oppose замеченную attack; Stealth позволяет исчезнуть без cover; во время Move Quietly может Dexterity против Awareness владельца украсть не удерживаемый trapping/Asset/Coin в Close Range |
| 104 | Dwarf Brewguard | Brute (2 Wounds) | при 1 Wound attacker накладывает Distracted; action Leadership, каждый success снимает Distracted с одной выбранной цели в Medium Range |
| 105 | Dwarf Miner | Minion | Blasting Charge: все существа target Zone получают Endurance Hazard (3), а missed attack взрывает Zone Miner; при встрече grudge-цели Miner получает Distracted и `+1d Melee`; игнорирует underground Difficult Terrain и enemy high-ground bonus |
| 107 | Elf Merchant | Brute (2 Wounds) | при 1 Wound получает Staggered; Tests торговли с ним получают `-1d` |
| 107 | Elf Militia | Minion | `+1d` при opposition Melee, если другой Elf Militia в той же Zone не находится в Close Range врага |
| 108 | Bretonnian Questing Knight | Champion | mounted Warhorse+barding: `+2 Resilience`, Fast, successful non-Monstrosity Charge даёт Prone до Give Ground; attacks до первого turn Knight в battle Grim; прямая immunity к Broken и Distracted |
| 109 | Bretonnian Squire | Minion | `+2d` к Help Tests, когда помогает обслуживаемому Knight |

`Paragons` Questing Knight — value-level immunity к двум Conditions независимо от психологической классификации источника. Она отличается от source-level psychological immunity undead и требует отдельного typed condition-immunity contract.

<a id="catalog-chunk-m26"></a>

## M26 — Artisan, Bretonnian Squire и Elf Merchant

Статус чанка: `verified` в текущей PC family. RULE-PROFILE-TALABEC-002 и RULE-PROFILE-PEOPLES-005/008; BOOK-GM-GUIDE1.1, Allies and Antagonists96/107/109 и Understanding NPC Profiles93. [Общий factory/JSON/CLI-пример](../examples/m26/README.md). Это три fixed Close loadouts, не полные карточки со всеми действиями/оружием.

| Profile ID | Книга/страница | Выбранная атака | Protection | Injury/Resilience |
|---|---|---|---|---|
| ARTISAN | GM96 | Make-Shift Weapons Close2d/2 Damage2,1H | Athletics3d/2 | Minion1, Toughness3/Resilience3 |
| BRETONNIAN_SQUIRE_SWORD | GM109 | Sword Close3d/3 Damage3,1H | Athletics3d/4 | Minion1, Toughness3/Resilience3 |
| ELF_MERCHANT_JEWELLED_BLADE | GM107 | Jewelled Blade Close4d/3 Damage3,1H | Athletics4d/3 | Brute2, Toughness3/Resilience4 armoured |

Armour Merchant представлен ResilienceProfile(3,1). У всех Normal Speed; Protection берётся из напечатанного профиля, не из атаки/Agility по догадке. Longbow Squire явно unselected; PC Sword Traits к NPC не добавляются. Все root/nested book identities резервируют полный fixed loadout, сохраняя exact types и независимые свежие graphs.

Professional Pride Artisan: дополнительная Coin при покупке trapping прямо у Artisan-изготовителя даёт +1d следующему Test с этим trapping. Способность inactive только в сцене без такой покупки/отложенного бонуса; no_external_effects исключает и полученный **до боя** неиспользованный бонус. Noble Service Squire даёт +2d Help Tests обслуживаемому Knight; нынешняя NPC-стратегия Help не выполняет. Hard Bargain Merchant даёт -1d Tests торговли с ним; торговли в сцене нет. Полные условия/эффекты сохранены в inactive metadata, не удалены из карточек.

### Первая рана Merchant

GM107 задаёт bands0No effect /1Suffer Staggered /2Defeated. PG1.4 Conditions/Staggered123 и Wounds190: получение раны снимает прежний обычный Staggered. Raw profile Wound сначала увеличивает счётчик и очищает старый Staggered, затем обязательный Profile Wound ACK при actual living0→1 накладывает **один новый** Staggered профиля. Уже Staggered Merchant не получает от этого ACK немедленную вторую рану. Другие Conditions сохраняются; W1 не перечитывается на каждом snapshot и не применяется заново на W2.

Три отдельных слабых попадания при прежней fixed SUFFER_WOUND policy дают: первый Staggered; второй repeated-Staggered→W1, removal старого→один новый Staggered; третий repeated-Staggered→W2defeat. Прямой damaging Wound0→1 тоже накладывает один новый Staggered. Следующий собственный ход Merchant — обычная атака, без Broken stop; промах не складывает Staggered. Будущее удаление profile Staggered через NPC Recover при сохраняющемся W1 не выбрано, текущая стратегия его не делает.

[Explicit helper](../../src/towr/domain/pc_npc_wound_models.py) применяется только на existing [profile ACK projection](../../src/towr/domain/_pc_melee_projection.py); общей injury rule, owner, proof shape и DSL не добавлено. Прежние пять definitions/snapshots/metadata и34request/result pairs сохранены. Current JSON1/схемы/метрики прежние, миграции нет. [Catalog/native tests](../../tests/unit/test_m26_pc_catalog_chunk.py), [Wound/sequence/replay tests](../../tests/unit/test_m26_pc_merchant_wounds.py), [общий JSON/trials/count search/process](../../tests/integration/test_m26_pc_catalog_chunk.py).

<a id="brute-chunk-m30"></a>

## M30 — Empire Knight, Knight of the White Wolf и Big ’Un

Статус: `verified` в PC family. Источники: BOOK-GM-GUIDE1.1, Allies and Antagonists / Profiles92–93 / Empire Knight101 / Knight of the White Wolf116 / Orc Boy158 / Big ’Uns159; BOOK-PLAYER-GUIDE1.4, Equipment / Melee Weapons93–94. Rule IDs: RULE-PROFILE-TALABEC-010, RULE-PROFILE-IMPERIAL-003, RULE-PROFILE-GREENSKIN-005. [Общие factory/JSON/CLI-примеры](../examples/m30/README.md).

| Profile ID | Выбранная атака | Выбранная Protection | Injury/Resilience |
|---|---|---|---|
| EMPIRE_KNIGHT_LANCE | unmounted Lance Close4d/4 Damage4,1H | Defence4d/4 | Brute2,T3/Res5 armoured,noShield |
| KNIGHT_WHITE_WOLF_HAMMER | unmounted Wolf Hammer Close4d/4 Damage5,2H | Defence4d/3 | Brute2,T3/Res5 armoured |
| BIG_UN_CHOPPAS | Couple of Choppas Close3d/4 Damage5,2H | Defence3d/4 | Brute2,T4/Res5 armoured,noShield |

Все Normal Speed. GM93 требует вычесть shield+1 из printed Resilience Empire Knight6 и Orc/Big ’Un6, когда shield не выбран. Armour сохраняется отдельно от Toughness. Noble Steed даёт дополнительный mounted+1, который эти пешие loadouts не получают. Printed Protection не пересчитывается по характеристикам; Athletics2d/3 обоих рыцарей и3d/3 Big ’Un сохранена как unselected.

PG93 определяет Lance как Close/1H с +1d Melee/+1 Damage при mounted Charge и запретом dual wield. Запрета обычной пешей атаки нет; данный fixed loadout использует только одну Lance. Big ’Un наследует Orc Boy158, меняя Strength3→4, тип на Brute и Wound bands; printed Choppas Damage4 становится5, WS3/Melee4 прежние. Дополнительный bonus за dual wield не добавляется. Jagged Spear/Warbow не выбраны.

У всех трёх bands0No effect /1Drained /2Defeated. Existing mandatory Profile Wound ACK применяет Drained только при actual living Brute0→1; raw Damage/Attack предшествует ему. Повторное наложение Staggered, которое действительно создало первую рану, проходит тем же ACK. Другие Conditions сохраняются; получение W2 не перечитывает band1. Drained самого NPC не становится on-hit эффектом для PC и не требует нового secondary_effects descriptor. Ordinary own turn продолжается, положительные bonus dice подавляются, base dice/Damage остаются прежними.

Полные inactive triggers: Empire Knight — Noble Steed при mounted+1Res/Fast/Prone от successful Charge против non-Monstrosity до Give Ground; Lance bonus только mounted Charge; For the Order делает Charge Attack Tests Glorious, если Knight не Staggered. Knight of the White Wolf — тот же Noble Steed; Wolf Hammer bonus+1d/+1Damage при любом Charge; Furious Charge после successful Charge позволяет вторым action атаковать **другого** enemy Close Range. Big ’Un наследует Power of the Waaagh!: Help союзной Melee attack без Test даёт1free success; Choppas Charge даёт+1Damage. Эти triggers отсутствуют в выбранной неподвижной unmounted Attack-сцене, а не отключаются при применимости.

Исполнение: [canonical catalog](../../src/towr/domain/pc_npc_catalog.py), [конечный список W1Drained profiles](../../src/towr/domain/pc_npc_wound_models.py), [actual ACK/replay](../../src/towr/domain/_pc_melee_projection.py). White Wolf из M29 сохраняет прежний эффект через тот же helper. Никакого нового owner/DSL/ADR/wire version. Будущее снятие profile Condition через NPC Recover при сохраняющейся ране не определено; текущая NPC-стратегия Recover не делает.

Проверки: [данные/metadata/identities](../../tests/unit/test_m30_pc_brute_catalog.py), [native Wounds/bonus filter/defeat/replay](../../tests/unit/test_m30_pc_brute_wounds.py), [JSON1/full source/trials/8составов](../../tests/integration/test_m30_pc_brute_chunk.py). Старый M27 metadata test ограничен собственными Wolf/Boar, вместо требования отсутствия variants у любых будущих записей каталога.

## RULE-PROFILE-IMPERIAL-001..008 — Osterlund и Reikland

| Страница | Profile | Type | Нормативные profile/attack effects |
|---:|---|---|---|
| 113 | Free Company Militia | Minion | Help attack союзника в Medium Range без Test даёт `+1d` сверх обычного cap; как `Detachment` может быть выбран для немедленного Charge/ranged attack при входе врага к State Trooper |
| 114 | Hochland Sharpshooter | Brute (2 Wounds) | 1 Wound отменяет Aim; Long Rifle без Aim Grim, ignores armour, `+1d Wounds Table`; успешный reload Dexterity позволяет сразу Aim либо Attack вторым action, если не Staggered и не двигался в turn; woodland Difficult Terrain игнорируется |
| 116 | Knight of the White Wolf | Brute (2 Wounds) | 1 Wound даёт Drained; обычный mounted Noble Steed; successful Charge attack позволяет вторым action атаковать другую цель в Close Range |
| 117 | Warrior Priest of Ulric | Champion | cold penalties отсутствуют; после полученной в combat Wound следующая Melee attack Glorious; successful Charge attack позволяет издать howl, после которого слышащие allies делают все Tests своих Charge actions в этом round Glorious |
| 121 | Sigmarite Cultist | Minion | Help союзной Melee attack без Test даёт `+1d` сверх обычного cap |
| 122 | Flagellant | Brute (2 Wounds) | immune to Broken; при Staggered может выбрать Wound вместо Condition; Recover action автоматически лечит одну Wound; Flails получают `-2d Melee`, пока Staggered |
| 124 | Witch Hunter | Champion | пока не Staggered, нанесённые Wounds получают `+1d Wounds Table`; affected spell теряет `1 Potency`, при `0` не действует |
| 125 | Priest of Sigmar | Champion | раз за battle в свой turn снимает собственный Staggered без action; action снимает Broken с себя и всех allies в Short Range, затем Willpower Test снимает по одному Staggered с выбранной цели в Short Range за success |

Десятичные tables `The Hunt is On` и `Fight Fire with Fire` являются campaign consequence generators. Они не создают автоматические Conditions или encounters при встрече с одним из profiles.

## RULE-PROFILE-WIZARD-001..004 — NPC Wizards

Все четыре profiles являются Level 2 Champion Wizards. Их `Spellcaster` разрешает перед Casting Test добавить bonus dice, одновременно добавив столько же dice в собственный Miscast Pool. Раз за round они могут Willpower Oppose Casting Test в Long Range; финальные `9` opposition добавляются в их Miscast Pool.

| Страница | Profile | Подготовленные spells и особые эффекты |
|---:|---|---|
| 128 | Court Astronomer | grimoire: Hammerhand, Fireball, Oaken Shield |
| 130 | Hermit Witch | memorised: Glittering Robe, Mind Razor, Shimmering Twin |
| 131 | Daemonologist | grimoire: The Summoning, Gathering Darkness, Daemonic Vessel |
| 133 | Necromancer | memorised: Invocation of Nehek, Vanhel’s Danse Macabre, The Dwellers Below |

Profile spell list определяет grimoire/memorised ownership, но сами spell effects остаются `RULE-SPELL-002..005`: среди них есть Damage по группе, Prone до Give Ground, Resilience на battle, иллюзорная отдельная фигура, Hazard Zone, resurrection defeated undead Minion и multi-target buffs.

## RULE-PROFILE-CREATURE-001..010 — Pets и Mounts

| Страница | Profile | Type | Нормативные profile/attack effects |
|---:|---|---|---|
| 134 | Dog | Minion | обычно без собственного turn и не targetable; если не Staggered, при Melee/Brawn attack хозяина запрещает цели Give Ground |
| 134 | Hunting Bird | Minion | flight через vertical Zones с обычным запретом выхода в midair из Close Range ground enemy; обычно без turn и недоступен attacks; Awareness может Oppose Move Carefully врага |
| 134 | Rat Swarm | Minion special | Bite атакует всех enemies в range по одному; всегда outnumbers, вся Zone считается Close Range, через swarm можно видеть/двигаться; immune to Wounds/Conditions; defeat — Exacting Test 5, один action/Test подходящим damaging/environment Skill, либо Hazard/full-Zone area attack |
| 135 | Horse | Minion | mounted rider: `+1 Resilience`, Fast, successful non-Monstrosity Charge даёт Prone до Give Ground; Bretonnian Warhorse игнорирует Agility armour/barding penalties для control/opposition; Elven Steed даёт `+1d Athletics` для тех же Tests; Skeletal Steed даёт rider Frightening |
| 136 | Giant Wolf | Minion | Clamping Jaws запрещает Give Ground; Goblin rider получает `+1 Resilience`, Fast и тот же запрет от своих Melee attacks |
| 136 | White Wolf | Brute (2 Wounds) | при 1 Wound Drained; Charge Clamping Jaws позволяет вторым action атаковать ту же цель Rending Claws; Give Ground от его attacks даёт Broken |
| 137 | Giant Spider | Minion | fangs hit даёт Drained; игнорирует forest/ruin/vertical Difficult Terrain; Goblin rider получает `+1 Resilience`, Fast, тот же terrain ignore и Drained на successful attacks |
| 137 | Giant Boar | Minion | Charge attack `+1d Melee`, `+1 Damage`; Orc rider получает `+2 Resilience`, Fast и те же Charge bonuses |
| 138 | Razorgor | Brute (3 Wounds) | при 1–2 Wounds `+1d Melee` за каждую Wound; attack по Staggered/Prone/Wounded получает `+1d Wounds Table`; Give Ground от attacks даёт Broken |
| 138 | Bear | Brute (3 Wounds) | при 1–2 Wounds Drained; Crushing Weight hit даёт Prone до Give Ground; после successful Attack action может вторым action атаковать другую цель в Close Range; Give Ground от attacks даёт Broken |

Не-targetable pet относится к обычным enemy attacks; Zone/Hazard и иные эффекты без выбора отдельной цели требуют явного правила применения. Книга не говорит, что pet полностью отсутствует на battlefield.

<a id="natural-creatures-m27"></a>

## M27 — естественные атаки Horse, Giant Wolf и Giant Boar

Статус: `verified` в PC family. RULE-PROFILE-CREATURE-004/005/008; GM1.1, Profiles93 / Horse135 / Giant Wolf136 / Giant Boar137. [ADR-0080](../decisions/ADR-0080-natural-melee-attacks-and-creature-chunk.md), [factory/JSON/CLI-примеры](../examples/m27/README.md).

| Profile ID | Естественная атака | Protection | Resilience |
|---|---|---|---|
| HORSE | Hooves Close3d/3 Damage3 | Athletics4d/4 | Toughness3/Resilience3 |
| GIANT_WOLF | Clamping Jaws Close3d/3 Damage3, цель не может Give Ground | Athletics4d/4 | Toughness3/Resilience3 |
| GIANT_BOAR | Goring Tusks Close3d/4 Damage3 | Athletics3d/3 | Toughness3/Resilience5 armoured |

Все — Fast Minions, самостоятельные unmounted бойцы в уже Close-сцене. Natural profile явно задаёт hands=None; fresh state wields_weapon=false/noShield. Это напечатанная Melee-атака, не выведенный Unarmed/Brawn Test. PG68/118 разрешает вооружённому PC Defence против incoming natural Melee; при атаке по существу actual Protection request видит отсутствие оружия и выбранную Athletics. Естественная атака не становится inventory weapon или предметом для drop/pickup.

У Wolf запрет Give Ground действует без всадника. Явный helper устанавливает actual KernelAttackRequest.can_target_leave_zone=false для жертвы его атаки, даже если facts.can_leave_zone=true. Source facts не переписываются; атакованный Wolf сам не получает запрет. Canonical projection отвергает proof с подставленной доступностью Give Ground. Это исполняемый trait, а не inactive metadata из-за fixed SUFFER_WOUND стратегии.

Horse Noble Steed и Goblin/Orc rider benefits сохранены inactive только для unmounted сцены; movement/Charge/riders не исполняются. Собственный Goring Tusks Charge-бонус Boar (+1d Melee/+1Damage) сохранён отдельно от Orc Boar Boyz rider ability. Базовый Horse не получает optional Bretonnian Warhorse/Elven Steed/Skeletal Steed варианты: они явно перечислены в descriptive unselected_variant_names; у прежних восьми entries tuple пуст.

PG1.4 Clothing & Armour97 прямо определяет armoured как любое повышение Resilience над Toughness, включая свойства помимо надетой брони. Поэтому natural armour Boar представлена ResilienceProfile(3,2) и получает обычный PC Axe/Halberd/Greataxe +1Damage. По GM93 игнорирующая броню атака использует Toughness3 вместо Resilience5. House rule не вводится.

Current PC JSON1 требует прежнее обязательное attack.hands, теперь с допустимым null для natural Melee; отсутствие поля не равно null. Natural input требует Athletics и согласованного false weapon flag в native state. Старые1h/2h definitions и36прежних request/result pairs не мигрируются. Другие bounded Melee/Mixed/Magic/Ranged families сохраняют enum-only source/wire границы, включая cached None rejection до `.value`.

[Shared model/admission tests](../../tests/unit/test_m27_natural_attack_models.py), [три карточки/native/Wolf/armour tests](../../tests/unit/test_m27_pc_creatures.py), [общий JSON/trials/8составов/process](../../tests/integration/test_m27_natural_creature_chunk.py). Источники полностью связаны с canonical root/attack/Protection identities; примеси чужого оружия/Skill/брони не принимаются как книжный профиль.

<a id="on-hit-drained-m29"></a>

## M29 — on-hit Drained и White Wolf

Статус: `verified` в PC family. RULE-PROFILE-CREATURE-006/007; GM1.1 White Wolf136 / Giant Spider137 / Profiles93, PG1.4 Near Miss112 / Recover118 / Conditions122–123. [ADR-0081](../decisions/ADR-0081-pc-on-hit-drained-and-independent-condition-sources.md), [factory/JSON/CLI-примеры](../examples/m29/README.md).

| Profile ID | Атака / Protection | Injury |
|---|---|---|
| GIANT_SPIDER | Poisonous Fangs Close3d/3 Damage3,natural,on-hit Drained / Athletics4d/3 | Fast Minion,T3Res3 |
| WHITE_WOLF_CLAMPING_JAWS | Clamping Jaws Close3d/4 Damage5,natural,запрет Give Ground / Athletics4d/4 | Fast Brute2,T5Res5, W1Drained/W2defeat |

Spider Drained возникает при **попадании**, даже если Damage не дал Wound. Miss его не применяет. Сначала завершаются actual Attack/Protection и обычный Damage branch; новый Drained не меняет уже брошенные кубы/Fate. Последующие Wound Endurance и действия PC видят состояние. Near Miss отменяет рану, а не попадание, поэтому Drained остаётся.

Каждая подтверждённая application сохраняется отдельным typed hit_condition_source с actual Attack/attacker/target/application/rule, включая hit по уже Drained цели с was_already_present=true. Condition flag один, штраф не складывается и фиктивная Wound/sequence/deadline не создаётся. W6 expiry и Near Miss не удаляют независимую hit-причину; malformed state/source не чинятся до observation, full replay подтверждает once-only причинность. Для старых сцен без on-hit effects сохраняется быстрый empty-bank путь.

Пользователь выбрал нынешние Attack/standard Recover без нового Endurance решения. PG118/123 разрешает Endurance как **альтернативный** Recover вместо стандартных преимуществ; обычный Recover сам Drained не снимает. Из названия Poisonous не выведены disease, длительность или невозможность восстановления. Post-battle лечение/automatic Recover не исполняются.

White Wolf получает Drained на actual living0→1 profile ACK; его обычный own turn продолжается, bonus dice подавляются, W2 даёт defeat без повторного применения W1. Clamping Jaws запрещают actual target Give Ground, но атакованный Wolf сохраняет обычную доступность ухода. Rending Claws unselected; Pin and Tear требует Charge, Fearsome — Give Ground от его атаки, невозможного при выбранных Clamping Jaws. Spider Scitter-Scatter/rider эффекты inactive в неподвижной unmounted сцене. Напечатанный rider label Goblin Wolf Rider сохранён с фактическим scope Giant Spider.

Current PC JSON1 требует attack.secondary_effects:0–1descriptor exactkind=condition_on_hit,condition=drained,classification=unclassified,rule_id. Поддержан только этот effect; generic DSL/новый physical enum не вводятся. Все прежние40request/result pairs мигрированы явными[] в input/echo/candidate sources; старые значения/наблюдения сохраняются, version/метрики не меняются. Runtime hit bank не попадает в balance journals: перед агрегацией полностью проверяется native result.

[Cause/app projection](../../src/towr/domain/pc_hit_condition_models.py), [PC state/retention](../../src/towr/domain/pc_melee_result_models.py), [canonical attack/lifecycle](../../src/towr/domain/_pc_melee_projection.py), [PC codec](../../src/towr/adapters/_pc_melee_scenario_json.py). [Native/Fate/expiry/source tests](../../tests/unit/test_m29_pc_hit_conditions.py), [card/White Wolf tests](../../tests/unit/test_m29_pc_drained_catalog.py), [JSON/trials/4состава/process](../../tests/integration/test_m29_pc_drained_chunk.py). Другие bounded families не расширены.

## RULE-PROFILE-BEASTMEN-001..010 — Slaughtered Stag Warherd

| Страница | Profile | Type | Нормативные profile/attack effects |
|---:|---|---|---|
| 143 | Ungor | Minion | woodland Difficult Terrain игнорируется; `+1d` attacks против Staggered |
| 143 | Gor | Minion | woodland Difficult Terrain игнорируется; `+1d Melee`, пока Staggered; dual axes `+1 Damage` |
| 144 | Bestigor | Brute (2 Wounds) | при 0 Wounds не может выбрать Give Ground/Prone, при 1 Wound следующая attack Glorious; woodland Difficult Terrain игнорируется; перед attack может добровольно получить Staggered, если его нет; Staggered даёт `+1d Melee` |
| 145 | Chaos Warhound | Minion | Pinning Claws запрещают Give Ground; woodland Difficult Terrain игнорируется |
| 147 | Minotaur | Brute (3 Wounds) | при 1–2 Wounds получает `+1d Melee` за Wound; attacks по Staggered/Prone/Wounded получают `+1d Wounds Table`; Give Ground от attack даёт Broken; action Brawn Opposed лучшим Defence/Endurance врага в выбранной Zone Medium Range: победа Staggered всем остальным, поражение Staggered самому Minotaur |
| 148 | Dragon Ogre | Brute (4 Wounds) | при 2–3 Wounds теряет Raking Claws; Raking Claws атакуют каждого enemy в Close Range по одному; Give Ground даёт Broken; первый Charge battle разряжает молнию: после Charge attack все остальные в Zone получают Staggered, Dragon Ogre снимает свой; Wound от spell/magical attack перезаряжает следующий Charge |
| 149 | Centigor | Brute (2 Wounds) | при 1 Wound Prone; woodland Difficult Terrain игнорируется; перед Charge attack все существа Close Range, у которых ещё нет Staggered, получают Staggered |
| 151 | Bray-Shaman | Champion, Level 2 Wizard | woodland Difficult Terrain игнорируется; `+1d Casting`, если у него либо Wizard в Long Range есть Miscast dice; round Willpower opposition; memorised Mantle of Ghorok, Viletide, Devolve |
| 152 | Beastman Chieftain | Champion | woodland Difficult Terrain игнорируется; перед attack может добровольно получить Staggered; пока Staggered, все Melee attacks Glorious; Brayhorn action + Leadership: за success выбирается слышащий Beastman, который немедленно move на Zone, получает Staggered либо снимает Staggered |
| 153 | Ghorgon | Monstrosity (6 Wounds) | при 1–5 Wounds получает Monstrous Regeneration; Terrifying даёт Broken после Give Ground/Wound; failed opposition Swallow Whole помещает цель внутрь: start-turn Endurance Hazard (4), выход только после нанесения Ghorgon Wound, внутренние attacks Grim/unopposed/ignore armour |

`A Season for Slaughter` страницы 141 — d10 campaign generator. `Charging Bull`, `The Quickening Storm`, `Drunken Rampage`, `Brayhorn` и `Swallow Whole` имеют разные множества целей и timing; они не являются вариантами одного общего AoE resolver.

<a id="beast-orc-chunk-m28"></a>

## M28 — Gor, Chaos Warhound и Orc Boy

Статус: `verified` в PC family. RULE-PROFILE-BEASTMEN-002/004 и RULE-PROFILE-GREENSKIN-004; GM1.1, Understanding NPC Profiles93 / Gor143 / Chaos Warhound145 / Orc Boy158. [Общий factory/JSON/CLI-пример](../examples/m28/README.md).

| Profile ID | Fixed атака | Protection | Shield-free Resilience |
|---|---|---|---|
| GOR_DUAL_AXES | Crude Axes Close4d/3, printed Damage3,1H на каждый топор; отдельный +1Damage за dual | Athletics4d/3 | Toughness4/Resilience4, shield не несётся |
| CHAOS_WARHOUND | Pinning Claws Close3d/3 Damage3,natural; цель не может Give Ground | Athletics4d/3 | Toughness3/Resilience3 |
| ORC_BOY_CHOPPAS | Couple of Choppas Close3d/4 Damage4,2H | Defence3d/4 | Toughness4/Resilience5 armoured, shield не несётся |

GM93 предписывает уменьшить напечатанную Resilience на1, если NPC не несёт указанный shield. Gor5→4, Orc6→5; Protection dice/threshold при этом не меняются. Эти значения явно сохранены в canonical definition/fresh snapshot, скрытого вычитания в бою нет. По PG97 Gor при Resilience=Toughness не armoured; у Orc остаётся light armour1. Orc может применять выбранную Defence к Melee с оружием без щита; его Athletics3d/3 сохранена unselected вместе с Jagged Spear/Warbow.

Gor заранее выбран с двумя Crude Axes, занимающими обе руки, без shield. Напечатанный1H относится к каждому топору; Orc сохраняет собственную напечатанную combined2H нотацию. Общий NPC inventory/переключение хвата не добавляются. В данном Minion-срезе не моделируются NPC hand injuries/drop/pickup: fixed loadout сохраняется до defeat.

**Primal Rage:** +1d к Melee атаке, пока сам Gor Staggered; фактическая Wound не требуется (Minion был бы defeated). Модификатор добавляется один раз вместе с обычными outnumbering/higher-ground modifiers до существующего Drained filter/cap. Он не меняет Athletics Protection и не становится бонусом другого NPC. **Dual axes:** отдельный DamageModifier+1 по GM143, printed base остаётся3. Это не два бонуса за два топора и не PC Axe armour trait. Drained подавляет bonus dice, но не этот bonus Damage.

Chaos Warhound сохраняет printed Attack3d/3, хотя WS4; Protection4d/3 не подменяет атаку. Его natural Pinning Claws запрещают actual target Give Ground независимо от facts.can_leave_zone; при атаке по Warhound чужой запрет не накладывается. Giant Wolf сохраняет прежний такой же запрет.

Child of the Forest Gor/Warhound сохранён inactive только в неподвижной сцене без woodland terrain. Orc Choppas +1Damage на Charge — inactive, поскольку Charge не выполняется. Power of the Waaagh! при Help союзной Melee attack даёт **один free success без Test**, не bonus die; нынешняя NPC-стратегия Help не делает. Все условия/эффекты сохранены в metadata. Orc использует printed Damage4 без добавочного PC dual/Charge/weapon trait.

[Явные helpers](../../src/towr/domain/pc_npc_ability_models.py) и [подготовка actual NPC Attack](../../src/towr/domain/pc_melee_result_models.py) используют существующие typed DiceModifier/DamageModifier/kernel, без DSL/нового owner/формата. Current JSON1/схемы/метрики прежние; canonical root/nested identities связывают fixed mode и выбранные значения. [Catalog/native tests](../../tests/unit/test_m28_pc_beast_orc_catalog.py), [modifiers/replay tests](../../tests/unit/test_m28_pc_beast_orc_modifiers.py), [общая integration/process/8составов](../../tests/integration/test_m28_pc_beast_orc_chunk.py). Прежние11профилей и38пар примеров сохраняются.

## RULE-PROFILE-GREENSKIN-001..011 — Red Eyez Tribe

| Страница | Profile | Type | Нормативные profile/attack effects |
|---:|---|---|---|
| 156 | Goblin Warrior | Minion | Help attack союзника без Test даёт `+1d` сверх обычного cap; уже Staggered Goblin при новом Staggered немедленно defeated, бросает оружие и бежит вместо общей repeated-Staggered choice |
| 157 | Nasty Skulker | Minion | при наличии как минимум 5 других Goblins в Zone может Stealth исчезнуть без cover; unopposed Melee даёт дополнительный `+1 Damage` за success (`+2` за success всего) |
| 157 | Night Goblin | Minion variant | Goblin Warrior с Initiative 3, armoured Resilience 4 и Weighted Net, hit которого накладывает Burdened |
| 158 | Orc Boy | Minion | Help союзной Melee attack без Test даёт `1` free success, а не bonus die |
| 159 | Big ’Un | Brute (2 Wounds) | Orc Boy variant с Strength 4; на 1 Wound получает Drained |
| 160 | Snotling Swarm | Minion special | swarm rules как Rat Swarm, но Exacting defeat требует `6` successes; Planks/Hammers атакуют всех enemies in range по одному |
| 160 | Snotling Pump Wagon | Vehicle | один Snotling Swarm как crew/occupant, Normal, armoured Resilience 6, 4 Faults, Ram 5; rider теряет They’re Everywhere; wreck автоматически defeats Swarm |
| 162 | Orc Weirdboy | Champion, Level 2 Wizard | `+1d Casting` при 3 других Orcs в Zone; round opposition; Fist of Gork, Evil Sun Shinin’, Gaze of Gork; Evil Sun bonus к следующей Melee равен Potency и может превышать cap, Gaze после Zone damage Staggers caster |
| 162 | Goblin Oddgit | Champion, Level 2 Wizard | `+1d Casting` при 5 других Goblins в Zone; round opposition; Fist of Mork, Bad Moon Rizin’, Mork’s Curse; Curse даёт Distracted и снижает armour-derived Resilience на Potency до Toughness, repair обычно только в Downtime |
| 164 | Orc Boss | Champion | successful Charge позволяет second action attack другой цели Close Range; раз за battle объявляет Waaagh! как часть Melee/Brawn attack: его Test Glorious, и Melee/Brawn всех Orcs в его Zone в этот turn Glorious |
| 164 | Goblin Boss | Champion | при outnumbering Melee становится Glorious вместо `+1d`; раз за battle в свой turn выбирает Zone Long Range, все Goblins там немедленно Give Ground от ближайшего enemy, затем в свои turns действуют свободно |

`Ruin by Red Eyez` страницы 155 — d10 campaign generator. Mounted Goblin/Orc benefits находятся в `RULE-PROFILE-CREATURE-001..010` и не возникают у пеших profiles автоматически.

## RULE-PROFILE-UNDEAD-001..006 — Dominion of Dusk

| Страница | Profile | Type | Нормативные profile/attack effects |
|---:|---|---|---|
| 168 | Skeleton Warrior | Minion | не ест/пьёт/спит/дышит; immune to psychological effects and Conditions; не выбирает Give Ground/Prone, повторный Staggered defeats; Give Ground от его Melee даёт Broken; Help attack без Test даёт `+1d` сверх cap |
| 169 | Wight Guard | Brute (2 Wounds) | та же жизненная/психологическая immunity; не выбирает Give Ground/Prone, повторный Staggered наносит Wound; Give Ground от Melee даёт Broken; successful Melee после Damage навсегда снижает Resilience цели на `1`, минимум `1`, repair обычно в Downtime |
| 170 | Vampire | Champion, Level 2 Wizard | Fangs, нанёсшие Wound, лечат 1 Wound и дают `+1d` следующему Casting; undead/psychological immunity; каждый turn в sunlight — Willpower Hazard (2) с Ablaze, fire/silver/blessed weapons/garlic также являются такими weaknesses/Hazards; Give Ground от Melee/Brawn даёт Broken; round opposition; Night’s Dark Master, Invocation of Nehek, Vanhel’s Danse Macabre |
| 171 | Liche Priest | Champion, Level 2 Wizard | не ест/пьёт/спит/дышит, immune to psychological effects/Conditions; Wounds Table `-1d`, минимум `1d`; Give Ground от Melee/Brawn даёт Broken; если не двигался в turn, `+1d Casting`; round opposition; Arise!, Djaf’s Incantation of Cursed Blades, Usekhp’s Incantation of Desiccation |
| 173 | Tomb King | Champion | та же immortal/immunity и `-1d Wounds Table`; Give Ground от Melee/Brawn даёт Broken; undead Minions/Brutes Short Range получают `+1d Melee` и opposition Melee; Slow undead ally Medium Range может Manoeuvre в/из Zone King; enemy, победивший King, немедленно получает Willpower Hazard (3) |
| 174 | Necrolith Bone Dragon | Monstrosity (5 Wounds) | при 3–4 Wounds не может fly и обязан land next turn; Wicked Claws hit даёт Prone до Give Ground; Undead Monstrosity Reaction и immunity; Fly; Terrifying; action без Staggered — всем в Zone Medium Range Willpower Hazard (3); mounted Liche/Tomb King получает `+3 Resilience`, Fast, Fly/Terrifying/Breath; Liche всегда `+1d Casting`, King расширяет My Will Be Done до Medium |

`Night’s Dark Masters` страницы 167 — d10 campaign generator. Source-level psychological immunity, Bone Dragon Reaction и rider choice уже частично реализованы; value-level последствия вроде невозможности выбрать Prone/Give Ground и Wight replacement Wound требуют профильной policy.

## RULE-PROFILE-MONSTER-001..011 — Monsters of the Great Forest

| Страница | Profile | Type | Нормативные profile/attack effects |
|---:|---|---|---|
| 175 | Demigryph | Brute (3 Wounds) | при 1–2 Wounds Drained; Give Ground от attack даёт Broken; Human rider получает `+2 Resilience`, Fast, Fearsome, игнорирует Agility penalties heavy/full plate; Attack action даёт одну rider attack и Wicked Claws, но одна из двух по выбору обязана быть Grim |
| 176 | Great Stag | Brute (3 Wounds) | при 2 Wounds Drained; successful Charge antlers даёт Prone до Give Ground; Trample только Prone; Give Ground даёт Broken и Stag выбирает destination; Prone от attack позволяет second-action Trample; Human/Elf rider получает `+2 Resilience`, Fast, Charge Prone, Fearsome и Crown of Antlers |
| 176 | Pegasus | Brute (2 Wounds) | при 1 Wound теряет flight и обязан land next turn; Fly; Human/Elf rider получает `+1 Resilience`, Fast, Fly и successful Charge Prone до Give Ground |
| 177 | Griffon | Monstrosity (4 Wounds) | при 2–3 Wounds теряет flight и обязан land; Wicked Claws hit Prone, Maw только Prone; Monstrous Flight Reaction, Terrifying; Human/Elf rider получает `+2 Resilience`, Fast и обе Abilities |
| 179 | Forest Dragon | Monstrosity (6 Wounds) | при 3–5 Wounds теряет flight и обязан land; Maw hit Drained; Stomp выбирает enemies in range, ещё не выбранных другой Dragon attack; Monstrous Flight, Terrifying, Soporific Breath; Wood Elf rider получает `+4 Resilience`, Fast и три Abilities |
| 180 | Wyvern | Monstrosity (4 Wounds) | при 3 Wounds теряет flight и обязан land; Tail hit Drained; Monstrous Flight, Terrifying, Foul Stench; Orc Boss rider получает `+3 Resilience`, Fast и Abilities, а Attack action — одну собственную attack плюс Rancid Bite; Waaagh! делает attacks Wyvern Glorious |
| 182 | Troll | Brute (3 Wounds) | при 1–2 Wounds Regeneration; Stupidity, Fearsome, end-turn Regeneration неогненной Wound ценой Staggered, action Vomit по Staggered enemy Close Range как Endurance Hazard (3); Stone/River variants меняют Resilience/Potency либо добавляют Foul Stench |
| 183 | Troll Hag | Monstrosity (6 Wounds), Level 2 Wizard | при 0 Wounds `+1d Casting`, при 1–5 Regeneration; Net hit Burdened, Embrace запрещает Give Ground; Terrifying, Monstrous Regeneration, Swamp Breath, Mother Knows Best; Big Smartz, Troll Brainz, Foetid Whirlpool |
| 184–185 | Giant | Monstrosity (6 Wounds) | при 3–5 Wounds теряет Stomp; каждая attack выбирается d10 table: Headbutt `+1d Wounds`; Devour/internal Hazard (4); Get Lost forced Long Range + Wound + Prone и Staggered существу приземления; Club Swing по каждому enemy; Jump Up & Down — всем enemies Close Range Endurance Hazard (3); Unsteady Reaction и Terrifying |
| 186 | Fhómhair the Fair | Champion | woodland Difficult Terrain игнорируется; Give Ground от attack даёт Broken; против Broken `+1d attack` и `+1d Wounds Table`; меняется в humanoid NPC profile, подготовленное Awareness раскрывает true form, обычно Grim без magic/spite/monster-hunting advantage |
| 187 | Skin Wolf | Brute (3 Wounds) | перед attack может добровольно получить Staggered, который даёт `+1d Melee`; end turn без Staggered может получить Staggered и вылечить одну неогненную Wound, одновременно накладывая Staggered на всех существ Close Range |

Все ограничения rider и inherited Abilities перечислены явно: например, Dragon Rider не получает все неназванные свойства Dragon profile. `Giant Attacks` требует RNG на каждую Attack action и дальнейший typed resolver выбранной строки; `Stomp`, breaths, Foul Stench и Skin Wolf pulse имеют разные target selectors.
