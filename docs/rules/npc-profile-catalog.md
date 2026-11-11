# Каталог NPC profiles и Special Abilities

## NPC Help к Shooting (M62)

<a id="npc-shooting-help-m62"></a>

Статус `implemented`: RULE-PROFILE-IMPERIAL-001:strength-in-numbers / RULE-PROFILE-GREENSKIN-001:horde, GM1.1 VII113/156–157 и PG1.4 V108/123. Melee-only границы — GM96/121/158 и Big ’Un159. [Принятый ADR-0104](../decisions/ADR-0104-pc-npc-shooting-help.md), [JSON/CLI](../examples/m62/README.md).

Четыре canonical helper loadouts — Militia/Improvised Blades, Goblin Warrior/Spear, Night Goblin/Spear+Shield и Net+Spear — могут использовать existing npc_help_policies к Official/Pistol и Ogre/Pistol. Strength in Numbers и Horde относятся к любой attack; within Medium включает нынешний Close. Peasant/Cultist/Waaagh! Orc требуют Melee: их Shooting pairs отвергаются до RNG. Nasty Skulker не наследует Horde, generic authored helper не получает Ability по имени.

Пользователь выбрал loaded → no-Test Help конкретному Shooting Test; empty/partial Reload → собственный Attack helper. Никакого Help Dexterity/ожидания/предсказания completion. Сохраняются более поздний получатель, несколько helpers, отсутствие chains/self/duplicate helper и фильтрация обеих сторон пары без retarget. Drained receiver вызывает прежний dice-helper Attack fallback; Drained helper без собственного Test может помочь. Net helper при Help не расходует stock, при Attack fallback действует по M52.

Каждый Help занимает standard slot/TurnEnd и existing NPC Help count; даёт отдельный +1d bypass без RNG. Request/bonus/application связывают actual actor/Shooting/round/Test ID; source не задаёт Skill или величину бонуса. Разные receipts складываются, но один не применяется повторно и не переходит на Reload/следующий выстрел. Later Drained подавляет bonus dice, не отменяя уже исполненный Help. Terminal battle до выстрела сохраняет потраченный Help без application.

Shooting build применяет receipts до броска, сохраняет npc_help_applications и полный shot preparation/effective PC Fate prefix. Loaded/cycle/Prone/armour-ignore/Wounds прежние. PC Protection Help остаётся адресованным первому текущему NPC без предсказания его будущего Help: unused receipt не переносится на другого стрелка. Общий K1 effect/application, JSON1 fields/schema/метрики/catalog59 не менялись;212прежнихJSON сохранены побайтно.

## NPC Pistol и Reload (M61)

<a id="npc-pistol-reload-m61"></a>

Статус `implemented`: RULE-NPC-003/006/007/009/010 и RULE-EQUIPMENT-004. Источники — BOOK-GM-GUIDE1.1, VII Allies and Antagonists92–93, Empire Official98, Imperial Ogre103; BOOK-PLAYER-GUIDE1.4 III68/70, IV94–95, V107/110/123. [Принятый ADR-0103](../decisions/ADR-0103-pc-npc-pistol-and-exacting-reload.md), [JSON/CLI](../examples/m61/README.md).

| Canonical loadout | Attack | Reload | Protection / Resilience | Раны |
|---|---|---|---|---|
| `empire_official_pistol` | Shooting2d/3, cap4, Damage5,1H, ignores armour, optimum Close–Short | Dexterity3d/3, cap6;3successes | Athletics3d/3, cap6; T3/Res3 | Brute2; W1Broken, W2defeat |
| `imperial_ogre_pistol` | Shooting3d/2, cap6, Damage5,1H, ignores armour, optimum Close–Medium | Dexterity2d/2, cap4;3successes | Athletics3d/3, cap6; T5/Res6 armoured | Brute3; W1–2Normal Speed, W3defeat |

Reload dice — printed Initiative, threshold — Default Skill по GM93. Attack pool_cap=null: implicit cap равен удвоенному printed BS, поскольку эти Shooting dice не уменьшены штрафом. Ogre Pistol имеет отдельный shared ranged/reload profile по GM103; Typical Trappings с handgun не подменяет строку Attacks и не сокращает optimum доShort.13PG ranged rows сохранены; вместе с GM записью каталог ranged profiles содержит14weapons.

Пользователь выбрал fixed initially loaded Shoot→Exacting Reload3→Shoot, без shield/carried melee/смены оружия у этих NPC. Full source требует explicit Lore Blackpowder/kit/supplies и two_available_hands policy. Loaded и свободная вторая рука — начальные условия; две руки Reload — GM/scenario конкретизация, не цитата RAW. Один Reload Test занимает один Improvise/Skill action, failure сохраняет progress, completion не стреляет. HIT/MISS расходует заряд ровно один раз; actor/instance/cycle независимы от других NPC и PC Pistol. Нет автоматического Recover от Staggered или дозарядки при Wound/TurnEnd.

Official сохраняет Heard It All Before (не триггерится без Persuade/Distract), W1Broken и полный M23/M24 own-turn stop/exit до Shoot/Reload. W2 до выхода — обычный defeat. Ogre сохраняет Speed bands и metadata Charge/Fearsome/Mighty Throw; в Pistol-only/noMove сцене нет Rough Shove/Charge/Melee Give Ground, способность не применяется к Shooting по сходству имени. Прежние Dagger/Greathammer definitions не переписаны.

По умолчанию PC отвечает Defence с рабочим shield, иначе Athletics; [M63](combat.md#pc-close-shooting-protection-m63) добавляет явный выбор. Defenceless без opposition. Armour-ignore использует Toughness, не стирая shield/armour source. Shooting не получает outnumber/higher-ground; Prone target даёт−1d, Close MISS — Staggered только при отсутствии. Действуют actual Protection Help/Fate/Grim/Glorious/W10 и Critical/Near Miss/Wound/body tails. Получение NPC Help новыми стрелками в первоначальном M61 было запрещено; [M62](#npc-shooting-help-m62) разрешает Militia/Horde. Для остальных helpers сохраняется отказ на admission: прежние receipts предназначены Melee, нельзя выдать их за Shooting или Reload. Остальные mixed NPC Help policies сохраняются.

Current PC JSON1 дополняет только новые canonical enemies: closed pistol facts object и explicit Shooting/range_min/ignores_armour в primary attack. Для других identities эти поля запрещены, generic authored Shooting не разрешён. Полный template проверяется до subset/RNG, generation сохраняет survivor facts и удаляет policies исключённых NPC без retarget. Отдельных новых метрик нет: Reload входит в total actions, не NPC Recover/Help. Owner/replay связывает полный source/request/slot/Test/receipt/cycle.208прежнихJSON сохранены побайтно, каталог NPC57→59.

M59 подключает Halfling Thief/Dagger с исходной Stealth3d/5/cap6 к Pistol admission через прежний typed Now You See Me permission. Это последний отдельный Protection case выбранного каталога57:44готовых Athletics/Shield Defence,12policy sources и1canonical Stealth. Melee/Athletics policy не расширена до Stealth; generic NPC/автоматическая скрытность не разрешены. [Правило](combat.md#pc-close-shooting-protection-m59), [CLI](../examples/m59/README.md).

M58 добавляет к Close Shooting policy Nasty Skulker/Long knives, Brewguard/Warhammer, Miner/Pickaxe и Bestigor/Massive Axe: всего12sources при прежнем каталоге57. Miner generic grudge усиливает defensive Melee; Bestigor Blood Rage/next-Glorious остаются Attack-only. Alternate Athletics Miner/Bestigor исправлены на cap4/cap8 по исходной Ag. Основное описание — [правило боя](combat.md#pc-close-shooting-protection-m58), [CLI](../examples/m58/README.md).

M57 добавляет к существующей Close Shooting policy Orc Boy/Big ’Un Choppas/Spear без щитов: ещё4проверенных sources, всего8, при неизменном каталоге57. У всех Melee3d/4 и Athletics3d/3, cap6; Strength4 Big ’Un не увеличивает WS. Help/Charge сохраняют Attack-only scope. Основное описание — [правило боя](combat.md#pc-close-shooting-protection-m57), [CLI-примеры](../examples/m57/README.md).

M56 разрешает явную Close Shooting Melee/Athletics policy для четырёх существующих loadouts State Trooper Halberd/Spear, Empire Knight/Lance без щита и White Wolf/Wolf Hammer. Выбранные definitions/обычная Defence не переписаны, каталог57. Неисполнявшаяся ранее Athletics metadata двух unshielded Knights исправлена на2d/3/cap6 от Ag3. Условия, числа и приёмка имеют основное описание в [правиле боя](combat.md#pc-close-shooting-protection-m56) и [ADR-0101](../decisions/ADR-0101-pc-close-shooting-npc-protection-choice.md).

## Night Goblin: Weighted Net и carried Spear (M52)

<a id="night-goblin-net-spear-m52"></a>

Источники: BOOK-GM-GUIDE1.1, гл.VII Profiles93 / Goblin Warrior156 / Night Goblins157; BOOK-PLAYER-GUIDE1.4, гл.III Skills68, гл.IV Equipment92/94/96/97, гл.V Actions116 / Recover118 / Conditions123. Выбранная граница — [ADR-0097](../decisions/ADR-0097-pc-weighted-net-and-carried-spear.md); статус implemented.

Canonical `night_goblin_net_spear`: Normal Minion/T3/Res3 **armoured** без shield, Athletics3d2/cap6. GM157 printed Res4 armoured уменьшается на1 по GM93 при отказе от shield; light armour повторно не начисляется. Явный marker сохраняет armoured при нулевом числовом bonus: Axe/Halberd и похожие Traits применяются, ignores-armour по-прежнему использует Toughness. Это отдельный fixed loadout от прежнего Night Goblin/Spear+shield.

Два профиля: Jagged Spear Melee2d3/Damage3/1H/maxShort/cap4 и Weighted Net Throwing2d3/2H/Close–Short/cap6 отBS3. У Net primary ConditionImpactSpec Burdened вместо Damage; нет фиктивного Damage0, дополнительного Staggered или автоматической Wound. Cap6 хранится явно отдельно от printed base2.

В начале NPC держит одну Net и переносит Spear. Явная policy `throw_once_then_spear` выбирает Net только по первой живой цели текущего priority без Burdened/Defenceless; иначе выбирает Spear, сохраняя Net. После actual HIT или MISS Net израсходована; отдельный free draw достаёт переносимое копьё. После временного выбора Spear неброшенную Net можно снова достать для новой допустимой цели. `spear_only` явно отказывается от броска. Pickup/повторного запаса нет; новый раунд не возвращает сеть. Close MISS исполняет обычный own Staggered без повторного наложения уже Staggered.

Burdened запрещает Manoeuvre, а не Attack/Protection/free draw/standard Recover. PC сохраняет прежнюю стратегию; Brawn освобождение не добавляется автоматически. Независимая Net-причина сохраняется через Wound/Fate/expiry/обычный Recover, не смешивается с injury Burdened и не создаёт механики стаков. Melee outnumbering/higher-ground не переносится на Throwing. PC без shield защищается Athletics; Sword/Staff не разрешает Defence против Net.

Dirty Coward сохраняется. При выбранной паре Horde Help имеет приоритет и не расходует Net. Если получатель собирается бросить Net, helper выбирает Attack fallback вместо привязки Melee Help к Throwing. После выбора Spear работает обычный Help/Test binding. Help и Attack не объединяются в одно действие.

Current PC JSON1 требует только у этого source conditional `definition.net_attack`, `definition.resilience.armoured:true` и enemy `net_policy:{initial_count:1,mode:...}`. Полные nested sources/stock/equipment readmit проверяются до RNG. Прежние56profiles и172JSON M9–M51 сохранены; каталог57, версия и агрегаты прежние. Подбор удаляет policy вместе с actor. [Factory/CLI-примеры](../examples/m52/README.md).

Net по Defenceless остаётся вне выбранной тактики: исполняется Spear с обычным Wound/Fate. Общая precedence PG96/123, новый Brawn Recover, pickup/spatial/Charge не объявлены реализованными.

## Great Stag: Crown of Antlers и Trample (M51)

<a id="great-stag-crown-trample-m51"></a>

Источник: `RULE-PROFILE-MONSTER-002`, BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / Great Stag176, NPC Profiles93; BOOK-PLAYER-GUIDE1.4, гл.III Brawn69, гл.V Dice107 / Actions116 / Attack118 и Wounds Table190–191. Три конкретизации явно приняты в [ADR-0096](../decisions/ADR-0096-pc-great-stag-crown-and-trample.md).

Canonical `great_stag` / `pc-book-npc:great_stag`: Fast Brute3, WS4/S5/T5/Ag5, Resilience5 без armour/shield/оружия. Две natural Close атаки с hands=null: `mighty_antlers` Melee4d/3 Damage6, cap8; `trample` Brawn5d/3 Damage5, cap10. У обеих pool_cap=null: cap следует из исходной Characteristic. Protection Athletics5d/4, cap10. W0–1 без Condition, W2Drained, W3defeat; actual1→2 ACK работает и для Warped Form.

Первое действие всегда Mighty Antlers. Если после всех её Wound/Fate/body/Endurance/expiry последствий та же цель впервые стала Prone из-за принятой раны этой атаки, выбранный через `npc_extra_attack_actor_ids` Stag получает второе действие Trample. Подтверждается actual переход не-Prone→Prone; уже Prone, Near Miss, successful Endurance, MISS и чужие причины разрешения не дают. Trample направлен только в эту живую всё ещё Prone цель, включая Defenceless; при смерти/недоступности пропускается без переназначения. `[]` явно отказывается от Crown. Максимум два действия и один TurnEnd после обязательных последствий.

Trample исполняет свой Brawn Test/Damage5, а PC Opposes фактическим Endurance; Defenceless не защищается. Fate/Glorious относится к этому Test, Help первой Melee/Protection не переносится. Typed Crown grant отличается от Bear different-target Enduring Strength и связывает slot1 receipt, actor/round, цель и выбранный профиль; owner доказывает причинность по журналу.

Current PC JSON1 сохраняет primary `definition.attack` и требует закрытый `definition.trample_attack` только у полного canonical Great Stag. Secondary содержит явный skill=brawn и все остальные поля Attack; частичный профиль не восстанавливается из ID. Прочие NPC по-прежнему имеют одну Melee-атаку. Каталог55→56; прежние55entries и168JSON M9–M50 сохранены. Метрики/верхнеуровневые поля/версия прежние. [Factory/CLI-примеры](../examples/m51/README.md).

Charge-Prone, destination Give Ground, Fearsome без Give Ground и Great Stag Knights/rider не исполняются в fixed Close/noMove/unmounted сцене. Не добавлять Charge descriptor к обычным Antlers; свободный выбор обычного Trample и общий spatial бой вне среза.

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

<a id="empire-chunk-m32"></a>

## M32 — Empire Peasant, Town Watch и Free Company Militia

Статус: `verified` в PC family. RULE-PROFILE-TALABEC-001/006 и RULE-PROFILE-IMPERIAL-001; BOOK-GM-GUIDE1.1, Allies and Antagonists / Profiles93 / Empire Peasant96 / Town Watch97 / Free Company Militia113. Подтверждение Detachment: State Trooper100. BOOK-PLAYER-GUIDE1.4, Melee Weapons92 / Free Actions116 / Help/Recover117–118. [Общие factory/JSON/CLI-примеры](../examples/m32/README.md).

| Profile ID | Выбранная атака | Выбранная Protection | Injury/Resilience |
|---|---|---|---|
| EMPIRE_PEASANT | Make-Shift Weapons Close2d/2 Damage2,1H | Athletics3d/2 | Normal Minion,T3/Res3 |
| TOWN_WATCH_POLEARM | Polearm Close→maxShort3d/3 Damage5,2H | Athletics3d/3 | Normal Minion,T3/Res4 armoured |
| FREE_COMPANY_MILITIA_BLADES | Improvised Blades Close3d/3 Damage3,1H | Athletics3d/3 | Normal Minion,T3/Res3 |

Все unshielded. Town Watch не получает повторный PC weapon Damage modifier поверх printed5 и не подменяет Athletics на Defence из-за2H оружия. Peasant Protection3d/2 берётся из карточки, независимо от2d атаки. Short Polearm — максимальная дальность по GM93/PG92; сцена по-прежнему Close. Unselected Attacks: Peasant **Hunting Bow**, как в Attacks, несмотря на Warbow в Typical Trappings; Militia Assorted Projectiles. У Watch других printed attacks нет.

**Torches and Pitchforks:** Peasant Helps союзной **Melee** attack без Test, target получает+1d Attack Test; может превышать обычный bonus cap. **Whistleblower:** Watch **может выбрать** сигнал как часть Recover; если подал, more Town Watch arrive next **turn**, Athletics Tests для Retreat от них Grim. Не менять turn на round и не выводить длительность Grim, отсутствующую в карточке.

**Strength in Numbers:** Militia Help союзнику **within Medium Range** сделать **любую attack**, без Test, +1d с разрешением превысить cap. Это не минимум Medium и не только Melee. **Detachment:** enemy **moves into Close Range of a State Trooper**; nominated FCM **или State Trooper** в **adjacent Zone**, сам **не Close enemy**, немедленно Charge либо ranged attack. Начальная уже-Close расстановка не считается Move-входом.

В примерах M32 npc_help_policies=[]: NPC выбирают Attack, не Help/Recover, движения нет. С M33 две Help Abilities Peasant/FCM поддержаны как active capability metadata при явной policy; Whistleblower/Detachment остаются inactive. Staggered Watch сам Recover не выбирает. Facts fresh/no_external_effects дополнительно исключают предбоевой неиспользованный Help bonus, **уже отправленный сигнал/ожидающее подкрепление**: отложенный trigger нельзя скрыть только отсутствием нового Recover. No_external_effects и all_combatants_included остаются явными caller facts.

Применяется прежний NPC definition → native/trials/generation/current JSON1 путь без нового owner/ADR/полей/метрик. Старые22definitions/snapshots/metadata и92JSON documents сохраняются. [Catalog](../../src/towr/domain/pc_npc_catalog.py), [printed/native/source tests](../../tests/unit/test_m32_pc_empire_catalog.py), [JSON/trials/8составов](../../tests/integration/test_m32_pc_empire_chunk.py). Реализация NPC Help/reinforcements и выбор новой стратегии — отдельные функции.

<a id="npc-help-m33"></a>

## M33 — NPC Help Peasant и Free Company Militia

Статус: `verified` в PC family. RULE-PROFILE-TALABEC-001 и RULE-PROFILE-IMPERIAL-001; BOOK-GM-GUIDE1.1 Peasant96/Militia113; BOOK-PLAYER-GUIDE1.4, Dice Pools107 / Helping With a Test108 / Help117 / Conditions122–123. [ADR-0083](../decisions/ADR-0083-pc-npc-automatic-help-policy.md), [публичные примеры](../examples/m33/README.md).

Torches and Pitchforks/Strength in Numbers выполняют настоящее Help action **без Test**, давая отдельный+1d для указанного Attack Test. Peasant — только Melee; Militia — любой attack союзника within Medium Range. Family остаётся melee-only/одна Close-сцена. Каждый+1d имеет bypasses_pool_cap=True; обычные outnumbering/прочие bonuses остаются capped. Несколько helpers складываются, отдельного max helper count в книге нет. Присутствие helper по-прежнему учитывается для numerical superiority.

Source содержит required npc_help_policies с явными парами helper_id/beneficiary_id; native tuple обязателен. Helper — canonical Peasant/Militia, beneficiary — другой более поздний ordinary attacker. Multiple helpers допустимы, duplicate helper/self/chains/unknown IDs/другая сторона отвергаются до RNG. Policy выбирает физическую Help при eligible recipient; при defeated/exited/законченном ходе/Broken/Defenceless/Drained делает ordinary Attack, если собственный ход её допускает. Drained fallback — согласованная тактика, не запрет книги помогать Drained.

Staggered/Drained helper не блокируют no-Test Help; Deafened helper прямо не может Help. Deafened recipient не иммунен к физической поддержке. Drained recipient не получает никакие bonus dice, включая bypass; поздний filter сохраняется. Help не создаёт TestResult/Fate/miss Stagger, не снимает Condition и тратит свой standard slot с обычным TurnEnd.

Typed no-Test action receipt адресует точный upcoming Test ID текущего раунда. Actual Attack хранит точные application receipts в порядке Help; каждый источник применяется один раз. Неиспользованный источник остаётся неиспользованным и не переадресуется на новый раунд/другую атаку. Это binding policy по образцу M15, не выдуманная общая длительность Help.

Count projection сохраняет entry только при обоих retained IDs, не выбирает замену. Отдельные source-ordered NPC Help counts/trial count/total не смешиваются с PC Help и проверяются вместе с action/round budget. Current PC JSON1 требует explicit list и metrics;96старыхJSON documents мигрированы []/нулями, остальные значения сохранены. Catalog data прежние; у Peasant/FCM ровно две ранее dormant Help Abilities переведены в active capability metadata, Detachment/Whistleblower остаются inactive. При [] обычная Attack и fresh/no_external_effects граница M32 прежние.

Исполнение: [no-Test models](../../src/towr/domain/automatic_help_models.py), [executor](../../src/towr/rules/automatic_help_resolution.py), [policy/preparation/applications](../../src/towr/domain/pc_npc_help_models.py), [PC journal](../../src/towr/domain/pc_melee_result_models.py), [projection](../../src/towr/domain/_pc_melee_projection.py), [generation](../../src/towr/application/pc_melee_balance_models.py). Проверки: [common Help](../../tests/unit/test_k1_automatic_help.py), [actual native/policy/forgery](../../tests/unit/test_m33_npc_help_execution.py), [statistics](../../tests/unit/test_m33_npc_help_statistics.py), [JSON/count search/process parity](../../tests/integration/test_m33_npc_help_json.py).

<a id="greenskin-help-m34"></a>

## M34 — Goblin Horde и Orc Power of the Waaagh!

Статус: `verified` в PC family. RULE-PROFILE-GREENSKIN-001/003/004/005; BOOK-GM-GUIDE1.1, Allies and Antagonists / Goblin Warrior156 / Night Goblin157 / Orc Boy158 / Big ’Un159; BOOK-PLAYER-GUIDE1.4, Rules / Pools107 / Help108/117 / Opposed109 / Attack118–119 / Conditions123. [ADR-0084](../decisions/ADR-0084-pc-greenskin-automatic-help.md), [примеры](../examples/m34/README.md).

Horde Warrior/Night Goblin даёт отдельный+1d сверх bonus cap для attack союзника без Help Test. Power of the Waaagh! Orc Boy/Big ’Un даёт один **free success** для Melee attack союзника без Help Test. Race получателя не ограничена; Nasty Skulker не наследует Horde. В пределах PC family все атаки Melee/Close. Помощь занимает реальный standard action с обычным TurnEnd, не требует собственного Test/RNG/Fate и не создаёт miss Stagger.

`AutomaticHelpEffectKind` различает один uncapped die и один free success. Typed snapshot хранит вид эффекта, application — соответственно DiceModifier либо SuccessModifier; вид/Rule ID выводятся из полной canonical definition helper. Источники разных исполненных actions складываются, каждый один раз, в порядке receipts и только для назначенного Test. Обычный cap остальных dice modifiers сохраняется; free success не превращается в куб, не меняет cap и не перебрасывается Grim/Glorious. Native replay сверяет как rolled successes, так и success_delta/final successes с исходным Test.

Ноль rolled successes плюс один free success дают один total success: при защите1 — hit с margin0 и base Damage; при защите2 — miss. Несколько Orc helpers дают несколько free successes; успешная attack против Defenceless по-прежнему вызывает одну forced Wound, а не рану за каждый успех.

Drained helper может делать no-Test Help. Drained recipient не получает bonus dice, включая Horde bypass, но сохраняет free successes. **Пользователь выбрал:** Orc Boy/Big ’Un выполняют назначенную Help такому recipient; Peasant/Militia/Warrior/Night Goblin сохраняют Attack fallback. Поздний Drained filter удаляет положительные dice modifiers и сохраняет success modifiers. Остальные admission/fallback/exact-Test binding/count projection/metrics [M33](#npc-help-m33) прежние, без общего AI и переназначения пар.

Current PC JSON1 не получает новых полей/версии/метрик. Required npc_help_policies и пустой opt-out сохраняются. Четыре Help Abilities переведены в active capability metadata; printed definitions/snapshots, shields/Short maximum, Dirty Coward, W1 Drained/W2 defeat и dormant Charge сохранены. [Common models](../../src/towr/domain/automatic_help_models.py), [PC policy/applications](../../src/towr/domain/pc_npc_help_models.py), [trace validation](../../src/towr/domain/pc_melee_result_models.py), [K1 tests](../../tests/unit/test_k1_automatic_help.py), [native mixed/Drained/replay tests](../../tests/unit/test_m34_greenskin_help_execution.py), [JSON/trials/search](../../tests/integration/test_m34_greenskin_help_json.py).

<a id="minion-chunk-m35"></a>

## M35 — Sigmarite Cultist, Elf Militia и Ungor

Статус: `verified` в PC family. RULE-PROFILE-IMPERIAL-005 / RULE-PROFILE-PEOPLES-006 / RULE-PROFILE-BEASTMEN-001; BOOK-GM-GUIDE1.1, Allies and Antagonists / Sigmarite Cultist121 / Elf Militia107 / Ungor143 и Understanding NPC Profiles93. [Общие factory/JSON/CLI-примеры](../examples/m35/README.md). Три новых fixed melee loadouts расширяют каталог25→28 по существующим моделям, без новых wire fields/версии/метрик или отдельного ADR.

| Profile ID | Атака | Protection | Injury/Resilience |
|---|---|---|---|
| SIGMARITE_CULTIST_WARHAMMER | Warhammer Close3d/3 Damage3,1H | Athletics3d/2 | Normal Minion1,T3/Res3,noShield |
| ELF_MILITIA_SPEAR | Spear maximum Short4d/3 Damage4,2H | Athletics4d/3 | Normal Minion1,T3/Res4 armoured,noShield |
| UNGOR_SPEAR | Crude Spear Close–Short3d/3 Damage3,1H | Athletics4d/2 | Normal Minion1,T3/Res4 armoured,shield |

Short maximum сохраняет actual Close combat; дальний бой/перемещение не добавляются. Ungor shield уже включён в printed Res4: ResilienceProfile(3,1), без повторного+1 и без выдуманной body armour. Elf printed Damage4 не получает дополнительный PC2H бонус. Cultist Warhammer/Ungor Spear тоже не приобретают PC Traits по названию оружия. Longbow Elf и Shortbow Ungor явно unselected.

**Torches and Pitchforks:** Cultist Helps союзной Melee attack без Test, давая отдельный+1d сверх bonus cap. Использует действующие named pairs, ordinary standard slot/TurnEnd, source-bound snapshot/application и позднего ordinary NPC attacker. Новый source Rule ID `RULE-PROFILE-IMPERIAL-005:torches-and-pitchforks` не подменяется Peasant ability. Multiple helpers/endpoint projection/Drained recipient Attack fallback/source-ordered NPC costs прежние; generic Help/AI не вводятся.

**Primal Spite:** Ungor получает один обычный+1d на Attack Test против **фактической Staggered цели**. Собственный Staggered Ungor, Prone/Wounded цели или Staggered другого PC не являются trigger. Состояние выбранной цели передаётся в существующий явный modifier helper при подготовке каждой attack; Rule ID `RULE-PROFILE-BEASTMEN-001:primal-spite`. Бонус не bypass и не Damage modifier, проходит обычный cap и Drained filter. После реальной Wound, снимающей Staggered цели, следующая attack больше не получает бонус. Child of the Forest сохраняет полный woodland Difficult Terrain scope и inactive в неподвижной сцене без terrain.

**Martial Prowess:** при Opposing Melee Elf получает+1d, если другой Elf Militia в **той же Zone не находится в Close Range врага**. В нынешней fixed arena все opposing pairs Close, все участники включены, движения/внешних sources нет. Help, Staggered или завершённый ход не разрывают Close; условие не достигается, способность сохранена полной в inactive metadata. Нельзя переносить карточку в spatial/back-rank сцену, продолжая игнорировать эту способность; source facts требуют текущую границу.

Исполнение: [catalog](../../src/towr/domain/pc_npc_catalog.py), [target-bound modifiers](../../src/towr/domain/pc_npc_ability_models.py), [attack preparation](../../src/towr/domain/pc_melee_result_models.py), [Help registry](../../src/towr/domain/pc_npc_help_models.py), [source gear admission](../../src/towr/domain/pc_melee_models.py). Проверки: [printed/canonical catalog](../../tests/unit/test_m35_pc_minion_catalog.py), [native target/Drained/Help/replay](../../tests/unit/test_m35_pc_minion_execution.py), [current JSON/trials/8составов](../../tests/integration/test_m35_pc_minion_chunk.py). Прежние25entries/definitions/snapshots/metadata и104JSON documents M9–M34 сохраняются.

<a id="spear-chunk-m36"></a>

## M36 — Spear loadouts State Trooper, Orc Boy и Big ’Un

Статус: `verified` в PC family. RULE-PROFILE-TALABEC-009 / RULE-PROFILE-GREENSKIN-004/005; BOOK-GM-GUIDE1.1, Allies and Antagonists / Profiles93 / State Trooper100 / Orc Boy158 / Big ’Un159. [Общие factory/JSON/CLI-примеры](../examples/m36/README.md). Три альтернативных melee loadouts расширяют каталог28→31; исходные Halberd/Choppas варианты остаются самостоятельными неизменёнными entries. Нового owner/формата/метрик/ADR не требуется.

| Profile ID | Атака | Выбранная Protection | Injury/Resilience |
|---|---|---|---|
| EMPIRE_STATE_TROOPER_SPEAR | Spear maximum Short3d/3 Damage3,1H | Defence3d/4 | Normal Minion1,T3/Res4 armoured,noShield |
| ORC_BOY_SPEAR_SHIELD | Jagged Spear maximum Short3d/4 Damage3,1H | Defence3d/4 | Normal Minion1,T4/Res6 armoured,shield |
| BIG_UN_SPEAR_SHIELD | Jagged Spear maximum Short3d/4 Damage4,1H | Defence3d/4 | Normal Brute2,T4/Res6 armoured,shield |

Все атаки исполняются в Close; Short — максимум по GM93, не минимальная дистанция. У всех трёх сохранена alternative Athletics3d/3, выбор до боя — Defence. State Trooper сохраняет printed light-armour total4, щит не указан и не добавлен. Shielded Orc/Big ’Un сохраняют printed Res6: ResilienceProfile(4,2), щит уже включён. Их старые Choppas2H варианты без щита имеют Res5. Damage6 от Staff поэтому даёт Staggered новому Orc вместо Wound старому; второй shield bonus не прибавляется.

Big ’Un наследует профиль Orc Boy с Strength4: только Melee Damage3→4, без увеличения WS/Melee/Protection. Actual первая Wound из прямого Damage либо repeated Staggered вызывает Drained на living0→1 ACK; W2 даёт обычный defeat/disposition. Drained фильтрует положительные bonus dice текущего NPC, не других участников. Once-only ACK/cached-state/source guards сохранены.

Оба копейных Orc loadouts наследуют **Power of the Waaagh!** и входят в действующий free-success Help registry. Настроенная Help расходует ordinary action без Test/RNG; один free success сохраняется при Drained получателе. Drained Big ’Un тоже может Help без собственного Test. Named pairs/точный будущий Test/endpoint projection/отдельные NPC costs и выбранная тактика [M34](#greenskin-help-m34) прежние.

Supporting Action State Trooper сохраняет полный enemy Move→Close/eligible ally adjacent Zone trigger; fixed aware all-Close/noMove scene его не вызывает. Jagged Spear у Orc/Big ’Un печатает+1Damage **на Charge**, который не исполняется; способность сохранена inactive как Spear on Charge, не перенесена ошибочно под именем Choppas. NPC Spears не получают PC Foot Spear Traits автоматически. Halberd/Crossbow/Handgun Trooper, Choppas/Warbow Orc/Big ’Un и mounted Big ’Un вариант явно unselected.

Current PC JSON1 без новых полей/версии/метрик. Canonical shield/source guards допускают две новые точные shielded identities, не произвольное изменение gear под прежним ID. [Catalog](../../src/towr/domain/pc_npc_catalog.py), [source admission](../../src/towr/domain/pc_melee_models.py), [Help registry](../../src/towr/domain/pc_npc_help_models.py), [W1 Drained registry](../../src/towr/domain/pc_npc_wound_models.py). Проверки: [printed/canonical catalog](../../tests/unit/test_m36_pc_spear_catalog.py), [native shield/Wounds/Help/receipt](../../tests/unit/test_m36_pc_spear_execution.py), [JSON/trials/8составов](../../tests/integration/test_m36_pc_spear_chunk.py). Прежние28entries/definitions/snapshots/metadata и108JSON documents M9–M35 сохраняются.

<a id="devour-chunk-m37"></a>

## M37 — Razorgor и два Minotaur Axe loadouts

Статус: `verified` в PC family. RULE-PROFILE-CREATURE-009 / RULE-PROFILE-BEASTMEN-005; BOOK-GM-GUIDE1.1, Allies and Antagonists / Razorgor138 / Minotaur147; BOOK-PLAYER-GUIDE1.4, Dice Pools107 / Wounds121/190 / Conditions123. [ADR-0085](../decisions/ADR-0085-pc-devour-and-wound-rage.md), [общие примеры](../examples/m37/README.md). Три loadouts расширяют каталог31→34 через существующие Test/Kernel/Wound lifecycle модели.

| Profile ID | Атака | Protection | Injury/Resilience |
|---|---|---|---|
| RAZORGOR | natural Razor Tusks Close3d/4 Damage5,hands=null | Athletics3d/3 | Fast Brute3,T5/Res6 armoured |
| MINOTAUR_AXE | Axe Close4d/5 Damage5,1H | Athletics4d/4 | Normal Brute3,T5/Res6 armoured,noShield |
| MINOTAUR_DUAL_AXES | те же printed Axe4d/5 Damage5,1H каждый, fixed два топора | Athletics4d/4 | Normal Brute3,T5/Res6 armoured,noShield |

Dual loadout занимает обе руки и даёт один отдельный DamageModifier+1. Printed Damage5 сохраняется, PC Axe Traits/повторный dual bonus не добавляются. Axe pools имеют обычный cap8 отWS4. В M37 Greataxe3d/5 Damage8 не выбиралась: её WS4 cap8 нельзя подменять default cap6 от printed3d. Отдельный корректный Greataxe loadout добавлен в [M38](#greataxe-cap-m38).

Оба существа при W0 не получают bonus, W1/W2 дают ordinary+1d Melee за каждую собственную Wound, W3 defeats. Бонус вычисляется перед каждой attack из actual actor injury, проходит cap и Drained filter. Сами профильные раны Drained не накладывают. Старое число ран/бонус другой особи не переносится в новую атаку.

**Devour the Fallen:** actual target **перед Attack/Damage** Staggered, Prone либо имеет незажившую Wound → ровно один WoundDiceModifier+1. Несколько флагов/ран не увеличивают modifier. Здоровая цель не квалифицируется благодаря новой Wound от того же удара; pre-Attack Staggered сохраняет eligibility, даже когда новая рана снимает Condition. Wounded конкретизируется через unhealed injury; treatment не равен healing по PG121. В нынешних fresh/noTreatment/noHealing сценах все достижимые Wounds остаются unhealed; перед расширением восстановления перепроверить scope.

Modifier связывается с точным KernelAttackRequest и проходит direct/repeated-Staggered/Defenceless/Near Miss source-путь. Table dice равны minimum1/base1+prior untreated+explicit modifiers; это не Skill Test, Drained/Grim/Glorious/Characteristic cap их не меняют. Extra die не даёт вторую Wound, не становится ongoing effect и не увеличивает будущие untreated dice после Near Miss. Другой actor/target/request не наследует receipt.

Fearsome имеет полный Give Ground→Broken trigger, который fixed SUFFER_WOUND policy не выбирает. Razorgor Charge даёт+1d Melee/+1Damage, но Charge/движения нет. Minotaur Charging Bull — отдельный Brawn action, Opposed лучшим Defence/Endurance врага в Zone within Medium; success Staggers **всех существ кроме Minotaur**, failure Staggers самого Minotaur. Fixed Attack policy его не выбирает; это не бесплатное последствие обычной атаки. Полные scope/effects и unselected Greataxe сохранены в metadata.

Current PC JSON1 без новых полей/версии/метрик. [Catalog](../../src/towr/domain/pc_npc_catalog.py), [typed modifier helpers](../../src/towr/domain/pc_npc_ability_models.py), [owner preparation](../../src/towr/domain/pc_melee_result_models.py). Проверки: [catalog/full source](../../tests/unit/test_m37_pc_devour_catalog.py), [native/pure rage/Devour/Fate/replay](../../tests/unit/test_m37_pc_devour_execution.py), [JSON/trials/8составов](../../tests/integration/test_m37_pc_devour_chunk.py). Прежние31entries/definitions/snapshots/metadata и112JSON documents M9–M36 сохраняются.

<a id="flagellant-feel-no-pain-m47"></a>

<a id="bear-crushing-weight-m50"></a>

## M50 — Bear / Crushing Weight и ранний Prone

Источник: BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / Bear138; BOOK-PLAYER-GUIDE1.4, гл.V Dice Modifiers107 / Attack118 / Conditions122 / Prone123. [Принятый ADR-0095](../decisions/ADR-0095-pc-bear-crushing-weight-pre-stagger-prone.md).

`BEAR_CRUSHING_WEIGHT`: Normal natural Brute3/T5Res6 armoured/noWeapon/noShield, Crushing Weight Close3d3Damage7/hands=null с explicit cap8 отWS4. Athletics3d3/null cap6. W1–2Drained, W3defeat; применяются настоящие profile ACK, в том числе от Warped Form. Дополнительные PC weapon penalties/Traits/Rage/Devour не добавляются. Sweeping Claws — unselected; прежний Sweeping Claws entry/metadata сохранён.

HIT накладывает Prone до Staggered choice и Wound lifecycle, независимо от того, будет ли Wound. MISS не меняет target. Уже брошенные Attack/Protection Tests не получают задним числом higher-ground. При repeated Staggered цель уже Prone; source/current choice сохраняют только допустимые возможности, выбран SUFFER_WOUND. PLAYER Wound source содержит этот early Prone, поэтому Near Miss отменяет Wound, сохраняя Condition от попадания. Нет подмены раннего эффекта поздней `ConditionOnHitSpec` application.

Prone не помещается в постоянный Spider Drained bank: ordinary self/ally Recover может снять его, а новая Attack снова наложить. Прежние ongoing Wound-Prone ограничения сохраняются. Post-Damage Drained descriptor/retention/expiry не меняются; новые histories не заставляют Prone появляться снова после Recover.

Current PC JSON1 допускает второй closed descriptor `prone_before_give_ground` с required `rule_id=RULE-PROFILE-CREATURE-010:crushing-weight-prone` и `affects_monstrosities=true`. Mapping — готовый K1 `ProneBeforeGiveGroundSpec`. Native gate разрешает его только полному canonical Crushing Weight Bear; authored/прочие book источники не получают произвольный effect. cap8 также ограничен новой canonical Attack и прежними исключениями, остальные caps прежние.

Existing `npc_extra_attack_actor_ids` допускает оба Bears. HIT и все Wound/Fate/body/expiry завершаются до optional slot2; цель — первый другой живой PC по текущему приоритету. Второй Crushing Weight использует тот же effect; третьего действия нет. `[]` отказывается только от optional второй Attack. Actual receipts/actions/extra counts и один TurnEnd сохраняются. Unsupported оставляет исполненный prefix, не считает неисполненный второй удар. Fearsome сохраняет Give Ground trigger, которого выбранная тактика не вызывает.

Каталог54→55;54прежнихprofiles/metadata и164JSON M9–M49 сохранены без миграции. Новых полей верхнего уровня/метрик/версии нет. [Factory/JSON/CLI](../examples/m50/README.md), [early projection](../../src/towr/domain/pc_hit_condition_models.py), [owner](../../src/towr/domain/_pc_melee_projection.py), [catalog tests](../../tests/unit/test_m50_pc_crushing_weight_catalog.py), [native tests](../../tests/unit/test_m50_pc_crushing_weight_execution.py), [JSON/search](../../tests/integration/test_m50_pc_crushing_weight_json.py).

<a id="ogre-grounded-pegasus-m49"></a>

## M49 — Imperial Ogre / Greathammer и наземный Pegasus

Источник: BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / Imperial Ogre103 / Pegasus176 / NPC Profiles93; BOOK-PLAYER-GUIDE1.4, гл.V Rules / Dice Modifiers107 / Speed115. Пользователь выбрал оба профиля по [ADR-0094](../decisions/ADR-0094-pc-imperial-ogre-cap-and-grounded-pegasus.md).

| Profile ID | Attack | Protection | Injury / Resilience |
|---|---|---|---|
| IMPERIAL_OGRE_GREATHAMMER | Close2d4Damage8/2H, explicit cap6 отWS3 | Athletics3d3, implicit cap6/null | Brute3/T5Res6 armoured/noShield |
| PEGASUS_GROUNDED | natural Hooves Close3d3Damage3/hands=null, implicit cap6/null | Athletics4d4, implicit cap8/null | Brute2/T3Res3/noArmour/noShield |

Printed Ogre2d не получает дополнительного PC Greathammer penalty или weapon Traits. Старые cap8 Minotaur/Bestigor сохраняются;6 допускается только Attack полного canonical Ogre definition. Authored/other book/Protection caps остаются null. Schema enum `[null,6,8]` не заменяет native source validation и не даёт caller arbitrary cap. Поле уже было required, версия/метрики/предыдущие JSON не меняются.

Ogre при0Wounds Fast, при1–2Normal, при3defeated; Speed не влияет на очередность в неподвижной сцене. Rough Shove/Ogre Pistol unselected; Mighty Throw и Ogre Charge требуют Rough Shove, а Fearsome — Give Ground, которого нынешняя SUFFER_WOUND стратегия не выбирает. Полные условия сохранены; их effects не применяются к Greathammer автоматически. Ogre не наследует Minotaur Rage/Devour.

`pegasus_grounded` — canonical loadout с **явным фактом начального положения**, не новая книжная разновидность. Pegasus начинает на земле и остаётся там в noMove/noExternal сцене. ПриW1 cannot fly/must land next turn уже выполнено наземным положением: нет выдуманного landing action/штрафа/unsupported; W2defeat. Fly и Pegasus Knights сохраняют полные triggers в metadata; всадника/Charge/полёта нет. Для будущей spatial сцены положение должно стать настоящим source/state, а не выводиться из имени этого ограниченного loadout.

Оба профиля используют прежние direct/repeated Staggered/profile-Wound/GM ACK и могут быть явными same-side Close targets Warped Form. Каталог52→54; прежние52entries/metadata и160JSON сохраняются без миграции. [Каталог](../../src/towr/domain/pc_npc_catalog.py), [source admission](../../src/towr/domain/pc_melee_models.py), [native/cap tests](../../tests/unit/test_m49_pc_ogre_pegasus.py), [JSON/search tests](../../tests/integration/test_m49_pc_ogre_pegasus_json.py), [примеры](../examples/m49/README.md).

<a id="skin-wolf-warped-form-m48"></a>

## M48 — Skin Wolf / Blood Rage и Warped Form

Источник: BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists, Skin Wolf187. Fast Brute3/T4Res5 armoured; Claws and Fangs Close5d3Damage5/natural и Athletics4d3 Protection, implicit caps10/8. W1–2 разрешают Warped Form, W3defeat. Каталог52; прежние51combat entries сохранены.

`RULE-PROFILE-MONSTER-011:blood-rage`: явный Rage list разрешает добровольный Staggered перед Attack при отсутствии Condition; любой actual Staggered даёт+1d Melee независимо от списка. Bestigor W1Glorious не переносится Skin Wolf.

`RULE-PROFILE-MONSTER-011:warped-form`: выбранная policy в конце собственного хода живого wounded unstaggered actor платит собственный Staggered, лечит1non-fireWound и затем накладывает Staggered остальным Close creatures. Heal сохраняет цену; нет action/Recover/Test/RNG лечения. В текущем fresh physical source нет огневых ран; неизвестные начальные/fire/magic producers не допускаются. Одна activation на end phase. Отдельный ordered snapshot исключает подтверждённых мёртвых/defeated/exited, сохраняет живых Defenceless PCs. Каждая цель завершает свои Wound/Fate/body/profile effects до следующей, после всей волны идёт обычный TurnEnd. Смерть последнего PC не обрывает начатую волну или собственную eligible end phase; unsupported сохраняет только исполненный prefix.

Пользователь [уточнил](../decisions/ADR-0093-pc-skin-wolf-warped-form-end-phase.md) неоднозначные self/focus cases: caster не получает второе Staggered от волны; Brewguard W1 от волны имеет typed focus=Skin Wolf. NPC focus снимается только после actual GM `killed` ACK, а не knockout/surrender. PC focus Near Miss/death semantics прежние. Wave не Attack: нет fake Test/Damage/Devour; первое Staggered живого Defenceless PC остаётся Condition. Повторный Staggered использует SUFFER_WOUND. Поддержаны profile-W1 Conditions, Dirty Coward/drop, Bestigor next-Attack Glorious и selected Flagellant Feel No Pain; его последующий Recover остаётся отдельным собственным действием.

Required `npc_warped_form_policies` задаёт всех source PCs и явные same-side NPC Close факты в полном порядке, NPC disposition rows и симметрию настроенных Wolves. `[]` отказывается от optional heal/wave. Target/causer IDs не заменяют actual receipts; replay проверяет полную историю. Compact activation counts отдельны от action costs. [Примеры](../examples/m48/README.md), [phase models](../../src/towr/domain/pc_warped_form_models.py), [проекция](../../src/towr/domain/_pc_warped_form_projection.py), [проверки исполнения](../../tests/unit/test_m48_pc_warped_form_execution.py).

## M47 — два Flagellant loadouts, Feel No Pain и Recover

RULE-PROFILE-IMPERIAL-006; BOOK-GM-GUIDE1.1, гл.VII Flagellant122 / Brutes92 / Profiles93; BOOK-PLAYER-GUIDE1.4, гл.V Recover118 / Attack-Staggered119. [Принятый контракт ADR-0092](../decisions/ADR-0092-pc-flagellant-feel-no-pain-and-recover.md), [factory/JSON/CLI](../examples/m47/README.md).

Оба loadouts — Normal Brute2/T3Res3 без брони/щита, Athletics3d3, implicit caps6. `FLAGELLANT_FLAILS` имеет Close3d4Damage6/2H и−2d Melee при собственном Staggered; `FLAGELLANT_HOOKS_CHAINS` — Close3d4Damage3/1H без этого штрафа. Protection не штрафуется, Drained не убирает отрицательный modifier. Второе оружие unselected, PC weapon Traits/повторные penalties не добавляются.

Required `npc_flagellant_policies` содержит unique actor/feel_no_pain enum/recover_when_wounded bool для canonical opposition Flagellants. `[]` отказывается от новых voluntary choices. Выбранный `wound_at_zero` заменяет первое Staggered от incoming weak physical hit либо собственного miss одной профильной Wound только при0Wounds; при1 замена добровольно не выбирается. Direct Wound не удваивается, repeated Staggered сохраняет обычную SUFFER_WOUND price/W2defeat. Это тактика в пределах добровольной Ability, не ограничение её текста только здоровыми NPC.

Incoming replacement задаёт узкий `FirstStaggerWoundSpec` до Attack: сохраняются raw HIT/Damage/impact и один actual profile-Wound/ACK, без краткого наложения Staggered. Own miss имеет отдельный typed proof с настоящим pending AttackerStaggerRequest, actor и полным profile-Wound witness; он не использует target предыдущей PC Attack. Оба пути проверяют полный prefix/точные типы/однократность.

При1Wound и recover_when_wounded actor выбирает настоящий standard self Recover вместо Attack. Generic Recover receipt снимает собственные Staggered/Prone, отдельное Feel No Pain правило лечит одну Wound1→0. Один обычный action, обычный TurnEnd, без RNG/PC Fate/второй Attack или revival. Циклы W0→W1→W0 сохраняют каждый настоящий источник. Helper использует прежний Attack fallback, если его named beneficiary будет Recover; чужая помощь не переносится на другую цель/Test.

Unbreakable блокирует только значение Broken, независимо от psychological classification. Central owner update нормализует это значение для canonical Flagellants; injected Broken state отвергается. Остальные Conditions не получают общей immunity. Нового Broken producer/общей миграции Condition provenance не добавляется.

Compact records/summary содержат source-ordered NPC Recover counts, число trials с Recover и total_npc_recover_action_count. Recover входит в total executed actions; PC self/ally costs отдельные, Feel No Pain follow-up не является действием. Current PC JSON1 остаётся1;152старыхJSON documents мигрированы policy arrays/нулевыми NPC Recover полями с сохранением остальных значений. Каталог49→51,49прежнихentries сохранены.

Реализация: [policy](../../src/towr/domain/pc_flagellant_policy_models.py), [miss/recover/Unbreakable](../../src/towr/domain/pc_flagellant_models.py), [K1 spec](../../src/towr/domain/resolution_models.py), [Stagger resolver](../../src/towr/rules/stagger_impact_resolution.py), [owner projection](../../src/towr/domain/_pc_melee_projection.py), [compact observations](../../src/towr/simulation/pc_melee_models.py). Проверки: [K1](../../tests/unit/test_k1_first_stagger_wound.py), [catalog](../../tests/unit/test_m47_pc_flagellant_catalog.py), [native](../../tests/unit/test_m47_pc_flagellant_execution.py), [JSON/statistics/search](../../tests/integration/test_m47_pc_flagellant_json.py), [process](../../tests/integration/test_m47_pc_flagellant_process.py).

<a id="bestigor-blood-rage-m46"></a>

## M46 — Bestigor, Blood Rage и следующая Glorious Attack

RULE-PROFILE-BEASTMEN-003; BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / Bestigor144 / Profiles93; BOOK-PLAYER-GUIDE1.4, гл.V Dice Modifiers107 / Grim & Glorious108 / Attack-Staggered119. [Принятый контракт ADR-0091](../decisions/ADR-0091-pc-bestigor-blood-rage-and-wound-glorious.md), [factory/JSON/CLI](../examples/m46/README.md).

`BESTIGOR_MASSIVE_AXE` — Normal Brute2/T4Res6 armoured/noShield, Massive Axe Close3d/4 Damage7/2H с explicit Attack cap8 от WS4; Defence4d/3 с ordinary cap8, alternate Athletics3d/3 unselected. NPC Axe не получает PC weapon Traits/повторный penalty. W0 запрещает выбирать Give Ground/fall Prone, не даёт общей immunity к forced Prone. Текущая fixed price strategy выбирает SUFFER_WOUND; woodland movement/Child of the Forest остаются вне сцены. W2defeat использует обычный ACK/disposition.

Required `npc_blood_rage_actor_ids` в native/current PC JSON1 задаёт включённых canonical Bestigors. `[]` явно отказывается от добровольного получения Staggered. Включённый actor с reserved/unexecuted Attack без Staggered получает его через typed proof до Test/RNG. Уже Staggered не накладывается снова и не вызывает Wound. Наложение не расходует отдельный action/TurnEnd/RNG. **Любой фактически Staggered Bestigor** получает ordinary+1d Melee независимо от списка; Defence не получает бонус. Drained фильтрует bonus dice, Help остаётся отдельным источником.

Actual living0→1 profile ACK создаёт право на ровно следующую Attack этого Bestigor, включая Wound от repeated Staggered. `PcBestigorGloriousSource` связывает actor, actual Wounding Attack и полный change. Право выводится из ACK/Attack history без нового mutable bank; W1 сама по себе не выдаёт его заново. Protection/Help/другие actors/смена раунда не расходуют право; фактическая следующая Attack расходует его при любом результате. W2 до хода не порождает фиктивного действия. Attack proof и quality trace сохраняют этот источник; replay проверяет полный prefix.

Пользователь выбрал reroll всех доступных провалов этого Glorious NPC Attack один раз. Это стратегия симулятора в пределах разрешённого книгой выбора. Test resolver сохраняет Grim cancellation/ограничения rerolls, не тратит PC Fate и не меняет его counters. Native fixed Bestigor не получает внешних quality/lock sources; общие cancellation/lock правила проверены отдельно на Test resolver.

Count search удаляет IDs исключённых Bestigors без переназначения. Required list exact/unique/opposition/canonical; прочие профили/aliases не допускаются. Explicit cap8 разрешён только новой Massive Axe и прежней Minotaur Greataxe; authored/Protection caps прежние. Новых wire версий/метрик нет.148прежнихJSON documents M9–M45 мигрированы только обязательным пустым массивом, остальные значения и48прежнихentries сохранены. Каталог48→49.

Реализация: [policy/admission](../../src/towr/domain/pc_npc_blood_rage_policy_models.py), [proof/entitlement](../../src/towr/domain/pc_bestigor_models.py), [catalog](../../src/towr/domain/pc_npc_catalog.py), [owner](../../src/towr/domain/pc_melee_result_models.py), [projection](../../src/towr/domain/_pc_melee_projection.py), [runner](../../src/towr/engine/pc_melee_runner.py). Проверки: [catalog](../../tests/unit/test_m46_pc_bestigor_catalog.py), [native](../../tests/unit/test_m46_pc_bestigor_execution.py), [JSON/trials/search](../../tests/integration/test_m46_pc_bestigor_json.py), [process](../../tests/integration/test_m46_pc_bestigor_process.py).

<a id="melee-loadout-chunk-m45"></a>

## M45 — Sharpshooter/Axe и три варианта без щита

Статус: `verified` в текущей PC family. RULE-PROFILE-IMPERIAL-002 / RULE-PROFILE-BEASTMEN-002 / RULE-PROFILE-GREENSKIN-004/005; BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / Hochland Sharpshooter114 / Gor143 / Orc Boy158 / Big ’Un159 / Understanding NPC Profiles93. [Общий factory/JSON/CLI-пример](../examples/m45/README.md). Чанк использует существующие Rage/Power Help/first-Wound Drained, без нового контракта/стратегии/ADR.

| Profile ID | Выбранная атака | Protection | Resilience / тип |
|---|---|---|---|
| HOCHLAND_SHARPSHOOTER_AXE | Axe Close3d/3 Damage3,1H | Athletics4d/4 | T4/Res5 armoured, Brute2 |
| GOR_AXE | Один Crude Axe Close4d/3 Damage3,1H | Athletics4d/3 | T4/Res4 без брони, Minion1 |
| ORC_BOY_SPEAR | Jagged Spear maxShort3d/4 Damage3,1H | Defence3d/4 | T4/Res5 armoured, Minion1 |
| BIG_UN_SPEAR | Jagged Spear maxShort3d/4 Damage4,1H | Defence3d/4 | T4/Res5 armoured, Brute2 |

Все четыре loadouts без щитов. Gor/Orcs уменьшают printed shield-inclusive Resilience на1 по GM93; подготовка защиты не вычитает её второй раз. Printed атаки/Protection не меняются из-за отказа от shield, новый Gor не получает dual Damage+1. NPC оружие не получает PC Traits. Alternate Orc Athletics3d3 и прочие unselected weapons сохранены.

Single Gor получает прежний ordinary+1d Melee при собственном Staggered. Оба копейных Orc loadouts доступны в прежних явных Help pairs: Power of the Waaagh! даёт free success без Test, включая Drained beneficiary; общий Attack fallback при недоступном получателе прежний. Big ’Un получает Drained на actual W1 ACK, затем W2defeat; Drained убирает обычные bonus dice, не free success. Sharpshooter W1 Cancel Aim сохраняется в metadata: в свежем fixed Axe-only/Attack сценарии нет Aim, поэтому отменять нечего; W2defeat исполняется обычным profile ACK. Rapid Reload требует reload выбранного оружия, rifle unselected; Sniper’s Nest и Child of the Forest требуют отсутствующего woodland movement. Orc Charge damage не вызывается обычной Attack.

Native/trials/count search/current JSON1 исполняют полный чанк. Новых wire полей/версии/метрик нет; существующие144JSON documents M9–M44 сохраняются без миграции. Каталог44→48; прежние44entries не меняются.

Реализация: [catalog](../../src/towr/domain/pc_npc_catalog.py), [Rage](../../src/towr/domain/pc_npc_ability_models.py), [Help](../../src/towr/domain/pc_npc_help_models.py), [W1 Drained](../../src/towr/domain/pc_npc_wound_models.py). Проверки: [catalog/source](../../tests/unit/test_m45_pc_melee_loadout_catalog.py), [native interactions](../../tests/unit/test_m45_pc_melee_loadout_execution.py), [JSON/trials/16составов](../../tests/integration/test_m45_pc_melee_loadout_chunk.py).

<a id="halfling-stealth-m44"></a>

## M44 — Halfling Thief и Stealth Protection

RULE-PROFILE-PEOPLES-002 / BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / Halfling Thief103, Understanding NPC Profiles93; BOOK-PLAYER-GUIDE1.4, гл.V Attack Tests118. [Принятый контракт ADR-0090](../decisions/ADR-0090-pc-halfling-stealth-protection.md), [factory/JSON/CLI](../examples/m44/README.md).

`HALFLING_THIEF_DAGGER` — Normal Minion1, T2/Res2 без брони/щита, Dagger Close2d/3 Damage1/1H, Protection Stealth3d/5. Обычные caps4/6, explicit pool_cap=null. Printed NPC numbers не получают PC Dagger Traits/повторные penalties. Throwing Knives Short4d/3 Damage2/1H сохранены unselected. Полный Thieving Blighter допускает исчезновение без cover и кражу не удерживаемого trapping/Asset/Coin в Close при Move Quietly через Dexterity против Awareness; fixed Attack/noMove сцена эти условия не вызывает.

Now You See Me позволяет Stealth для Oppose атаки, о которой Thief знает. Generic Protection умеет представить Skill, но eligibility требует отдельный `HalflingStealthProtectionPermission` с defender ID и полным canonical definition. Подмена профиля/чисел/источника либо отсутствие разрешения отвергаются. Unaware и Defenceless остаются unopposed; оружие/щит не являются требованием самого Stealth. В applied trace появляется `RULE-PROFILE-PEOPLES-002:now-you-see-me` только при фактическом выборе Stealth. Это не общий Skill override.

PC owner берёт printed Stealth для фактического Thief target, сохраняет разрешение в Protection proof и проверяет его при полном replay. Bonus cap/explicit Test modifiers, стандартные действия/цели/Conditions/подбор прежние. Current PC JSON1 допускает `protection.skill=stealth` только у canonical Thief; authored NPC и прежние loadouts сохраняют Athletics/Defence, PC/Help/Glorious выбора нового Skill не получают. Новых wire полей/версии/метрик нет. Каталог43→44;140прежнихJSON documents M9–M43 сохраняются без миграции.

Реализация: [catalog](../../src/towr/domain/pc_npc_catalog.py), [permission/eligibility](../../src/towr/domain/protection_models.py), [PC admission](../../src/towr/domain/pc_melee_models.py), [actual owner](../../src/towr/domain/pc_melee_result_models.py), [schema](../../src/towr/adapters/schemas/pc-melee-common.schema.json). Проверки: [catalog](../../tests/unit/test_m44_pc_halfling_catalog.py), [Protection](../../tests/unit/test_m44_halfling_protection.py), [native/replay](../../tests/unit/test_m44_pc_halfling_execution.py), [JSON/trials/search](../../tests/integration/test_m44_pc_halfling_json.py).

<a id="miner-grudge-m43"></a>

## M43 — Dwarf Miner и явные grudge relationships

Статус: `verified` в PC family. BOOK-GM-GUIDE1.1, гл.VII Dwarf Miner105; BOOK-PLAYER-GUIDE1.4, гл.V Distracted123. [ADR-0089](../decisions/ADR-0089-pc-miner-grudge-policy.md) принят пользователем; [общие примеры](../examples/m43/README.md).

`DWARF_MINER_PICKAXE`: Normal Minion, T4/Res6 armoured/noShield, Mining Pickaxe Close4d/3 Damage4,2H; Defence4d/3, caps8/8 с pool_cap:null. Printed числа не получают PC Pickaxe Traits или повторный weapon penalty. Athletics1d3 и полный Blasting Charge Short–Medium3d3/Endurance Hazard3 для всех creatures target Zone, при miss — Miner Zone, сохраняются unselected.

Grudges to Settle при встрече с grudge enemy накладывает на Miner Distracted и даёт ordinary+1d Melee против него. Обязательный `npc_grudge_policies` хранит explicit пары `actor_id` canonical Miner → `focus_actor_id` включённого PC. Один focus на Miner, несколько Miners могут иметь один focus. `[]` явно подтверждает отсутствие grudge в сцене, без догадки по race/name/priority. Неправильные типы/роли/дубликаты/чужие профили и cached aliases отвергаются до RNG. Count search удаляет пару при исключении Miner, без переназначения.

Initial encounter proofs исполняются в source roster order до первого TurnStart/Test, по одному на выбранного Miner. Fresh input snapshots остаются без начальных Conditions; caller не подставляет флаг Distracted вместо подтверждения встречи. Encounter не расходует action/TurnStart/TurnEnd/RNG; его нельзя пропустить, отложить или повторить. Source bank различает encounter cause Miner и first-Wound cause Brewguard.

Melee по focus: ordinary+1d, без Distracted penalty. По другому PC:−1d, без grudge бонуса. Protection против focus без штрафа и без Melee bonus; против другого−1d. Relationship и active Condition — разные факты. Target priority прежний, автоматического приоритета grudge enemy нет. Confirmed focus death после Wound/Fate снимает Distracted; Defenceless/Near Miss сохраняют, новых раундовых наложений/переназначения нет. Поддержан смешанный bank Brewguard+Miner.

Down in the Dark запрещает **enemy higher-ground bonus против Miner**, сохраняя outnumbering/прочие modifiers и собственный higher-ground bonus Miner при атаке Prone PC. Underground Difficult Terrain clause не исполняется в noMove/noTerrain сцене. Grudge+1d проходит обычный cap/Drained filter; negative penalty и независимый Help сохраняют свои правила. Recover/refocus, внешняя замена, visibility/повторные встречи и несколько grudge enemies одного Miner отдельно не моделируются.

[Policy](../../src/towr/domain/pc_npc_grudge_policy_models.py), [encounter/bonus](../../src/towr/domain/pc_npc_grudge_models.py), [bank/expiry](../../src/towr/domain/pc_npc_distraction_models.py), [higher-ground gate](../../src/towr/domain/pc_npc_ability_models.py). Проверки: [catalog](../../tests/unit/test_m43_pc_miner_catalog.py), [native](../../tests/unit/test_m43_pc_miner_grudge_execution.py), [JSON/trials/3состава](../../tests/integration/test_m43_pc_miner_grudge_json.py), [process parity](../../tests/integration/test_m43_pc_miner_process.py). Current PC JSON1 требует новое поле без defaults/compatibility;136старыхJSON documents получают `[]` при сохранении всех остальных значений. Каталог42→43, старые42entries не изменены.

<a id="brewguard-distracted-m42"></a>

## M42 — Dwarf Brewguard и source-aware Distracted

Статус: `verified` в PC family. BOOK-GM-GUIDE1.1, гл.VII Dwarf Brewguard104 / Brutes92 / Profiles93; BOOK-PLAYER-GUIDE1.4 Conditions122 / Distracted123, с аналогией Distract129. [ADR-0088](../decisions/ADR-0088-pc-brewguard-distracted-focus.md) сохраняет неоднозначность текста и **принятую пользователем трактовку A**, [примеры](../examples/m42/README.md).

`DWARF_BREWGUARD_WARHAMMER`: Normal Brute2, T4/Res5 armoured/noShield, Warhammer Close4d/3 Damage3,1H; Defence4d/3, caps8/8 без explicit override. W0 без эффекта, printed W1 «Attacker inflicts Distracted condition», W2defeat. NPC не получает PC Warhammer Traits. Bare Hands с primary Staggered и Athletics2d3 unselected. Cooler Heads Prevail — отдельный optional Leadership action, каждый success снимает Distracted у одного выбранного character в Medium; current Attack policy его не выбирает.

**Принятое разрешение неоднозначности:** actual первая Wound0→1 разово накладывает Distracted на раненого Brewguard. Focus — фактический PC, нанёсший рану, не helper и не автоматически предпочитаемая цель. Это конкретизация пользователя, не дословно указанное в GM104 уточнение focus/lifetime. Наложение идёт на source-bound profile ACK, включая repeated-Staggered Wound, после удаления старого Staggered; завершённый Test не пересчитывается.

Melee по focus и Protection против него не получают штрафа Distracted; против остальных PC применяется один ordinary−1d с обычными cap/minimum/Help правилами. NPC выбирает цели по прежнему caller priority. После подтверждённой смерти focus эффект снимается до следующего Test/действия/terminal result. Raw lethal roll до Near Miss/Fate completion не подтверждает смерть. Живой Defenceless, смена priority и завершение хода focus не снимают Condition. Убийство и Critical end-phase death поддержаны; W1 после снятия не накладывает старое отвлечение повторно.

PC owner хранит небольшой typed source/focus bank, выведенный из полного actual Attack/profile-Wound prefix; generic ConditionState остаётся флагом. Источники независимы у нескольких Brewguards, упорядочены по source roster. Снятие имеет отдельный canonical expiry proof, привязанный к завершённому death source. Это обязательное следствие без action/RNG/TurnEnd. Пропуск, повтор, подмена actor/focus/первой раны/death source и равные cached aliases отвергаются.

Произвольные новые источники Distracted, Willpower Recover, Cooler Heads, лечение/повторное наложение и потеря видимости не моделируются этой функцией. PG123 replacement сохраняется как требование будущих consumers, а не скрытое восстановление старого W1 focus. Общий Troll/Foul Stench/spell provenance остаётся шире этого owner-local решения.

[Catalog](../../src/towr/domain/pc_npc_catalog.py), [distraction bank/expiry](../../src/towr/domain/pc_npc_distraction_models.py), [Test preparation](../../src/towr/domain/pc_melee_result_models.py), [ACK projection](../../src/towr/domain/_pc_melee_projection.py). Проверки: [catalog](../../tests/unit/test_m42_pc_brewguard_catalog.py), [native Melee/Protection/Fate/death/replay](../../tests/unit/test_m42_pc_brewguard_execution.py), [JSON/trials/3состава](../../tests/integration/test_m42_pc_brewguard_json.py). Wire fields/метрики/PC JSON1 прежние; каталог41→42, прежние41entries и132JSON documents сохраняются без миграции.

<a id="shield-chunk-m41"></a>

## M41 — Gor / single Axe+shield и Empire Knight / Lance+shield

Статус: `verified` в PC family. BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / Gor143 / Empire Knight101 / Understanding NPC Profiles93. [Примеры](../examples/m41/README.md). Это два отдельных canonical loadouts по существующему образцу, без нового ADR, публичных полей, версии или тактики.

| Loadout | Attack | Protection | Injury/Resilience |
|---|---|---|---|
| GOR_AXE_SHIELD | single Crude Axe, Close4d/3 Damage3,1H | Athletics4d/3 | Normal Minion, T4/Res5 armoured с включённым щитом |
| EMPIRE_KNIGHT_LANCE_SHIELD, пеший | Lance, Close4d/4 Damage4,1H | Defence4d/4 | Normal Brute2, T3/Res6 armoured с включённым щитом; W1Drained/W2defeat |

GM93 уже включает shield в printed Resilience. Gor не получает второй shield bonus или Damage+1 двух топоров. Self-Staggered Primal Rage даёт один ordinary+1d Melee через существующий cap8/Drained filter; named Help остаётся отдельным бонусом. Старая dual Axe identity сохраняет Damage+1 и Res4 без щита. Child of the Forest требует woodland terrain, которого в сцене нет.

Пеший Knight сохраняет printed Damage4/Defence4d4 и не получает Horse Resilience+1 или mounted Charge bonuses. W1Drained применяется на actual first-Wound ACK, после которого обычный Attack продолжается с удалением положительных Test bonuses. W2 defeats. Полные Noble Steed, mounted Lance Charge+1d/+1Damage и For the Order Charge/не-Staggered trigger сохранены inactive; Athletics2d3 — unselected Protection. Старый unshielded Lance loadout сохраняет Res5.

[Catalog](../../src/towr/domain/pc_npc_catalog.py), [Primal Rage versus dual Damage](../../src/towr/domain/pc_npc_ability_models.py), [W1Drained](../../src/towr/domain/pc_npc_wound_models.py), [shield admission](../../src/towr/domain/pc_melee_models.py). Проверки: [catalog/full source](../../tests/unit/test_m41_pc_shield_catalog.py), [native Rage/Help/Resilience/Wounds](../../tests/unit/test_m41_pc_shield_execution.py), [JSON/trials/4состава](../../tests/integration/test_m41_pc_shield_chunk.py). Каталог39→41; все39прежнихentries и128JSON documents M9–M40 сохраняются без миграции.

<a id="creature-chunk-m40"></a>

## M40 — Demigryph, Centigor и White Wolf / Rending Claws

Статус: `verified` в PC family. BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / Demigryph175 / Centigor149 / White Wolf136; BOOK-PLAYER-GUIDE1.4, гл.V Attack Tests118–119 / Prone123. Чанк использует существующие natural/Short/shield/Brute/Condition пути без новых полей, версии или тактики. [Общие примеры](../examples/m40/README.md).

| Canonical loadout | Attack | Protection | Injury/Resilience |
|---|---|---|---|
| DEMIGRYPH, unmounted | Wicked Claws natural Close4d/4 Damage5 | Athletics4d/3 | Fast Brute3, T4/Res4 без брони; W1–2Drained/W3defeat |
| CENTIGOR_SPEAR | Jagged Spear1H, maximumShort4d/4 Damage4 | Athletics4d/3, shield | Fast Brute2, T4/Res5 armoured, щит включён; W1Prone/W2defeat |
| WHITE_WOLF_RENDING_CLAWS | Rending Claws natural Close3d/4 Damage6 | Athletics4d/4 | Fast Brute2, T5/Res5 без брони; W1Drained/W2defeat |

Printed характеристики/Skills сверены по полным карточкам; factory хранит выбранные боевые loadouts. Maximum dice равен обычному2×Characteristic: Attack8/8/6 и Protection8/8/8, explicit pool_cap остаётся null. Centigor не получает повторный shield bonus; выбранный Short — максимум Melee, допускающий текущий Close. Natural атаки не вооружают NPC. Отдельных дополнительных Test/Damage modifiers по названию оружия не добавляется.

**W1 Prone Centigor:** применяется только при actual0→1 profile-Wound ACK после обычного удаления Staggered раной. Сохраняются остальные Conditions; нового Staggered или второй раны нет. NPC продолжает прежний Attack лёжа, без автоматического Recover. Следующий PC Melee получает существующий+1d higher ground; Prone исключает Give Ground и повторное падение из repeated-Staggered choices. W2 — обычный defeat. При replay/пропуске/подмене ACK owner отвергает переход. Future NPC Recover при сохраняющейся profile Wound не определён.

Demigryph и White Wolf Claws получают Drained через существующий first-Wound ACK; у Demigryph Condition сохраняется при W2. Не смешивать этот путь с Centigor Prone или PC on-hit Drained от Spider. NPC Recover/лечение не вводятся.

Полные условия Abilities сохранены в metadata. Demigryph Fearsome требует Give Ground; Demigryph Knights действует только на Human rider: +2Resilience/Fast/Fearsome, игнорирование Agility penalties heavy/full plate и возможность двух атак в **одном rider Attack action**, одна из которых Grim. У самостоятельного Demigryph нет rider и этой двойной атаки; Bear slot2 ему не выдаётся. Centigor Child of the Forest требует woodland terrain; Spear bonus требует Charge; Drunken Rampage до Charge attack накладывает Staggered на всех creatures в Close, у которых его ещё нет. В fixed noMove/noCharge сцене эти условия не возникают; Javelin unselected.

White Wolf Pin and Tear требует successful Clamping Jaws как часть Charge и даёт second action по той же цели Rending Claws. У Claws-only/noCharge loadout Clamping Jaws unselected, способность не срабатывает; Fearsome также требует Give Ground, которого current PC policy не выбирает. **Clamping Jaws GG-ban не переносится на Rending Claws.** Прежний Clamping loadout не изменён. Все три новых loadouts отвергаются в Bear-only `npc_extra_attack_actor_ids`.

[Catalog](../../src/towr/domain/pc_npc_catalog.py), [profile Wound effects](../../src/towr/domain/pc_npc_wound_models.py), [actual ACK owner](../../src/towr/domain/_pc_melee_projection.py), [shield admission](../../src/towr/domain/pc_melee_models.py). Проверки: [catalog/source/metadata](../../tests/unit/test_m40_pc_creature_catalog.py), [native Prone/Drained/higher ground/receipts](../../tests/unit/test_m40_pc_creature_execution.py), [JSON/trials/8составов](../../tests/integration/test_m40_pc_creature_chunk.py). Каталог36→39; прежние36entries и124JSON documents M9–M39 сохраняются без миграции.

<a id="bear-second-attack-m39"></a>

## M39 — Bear / Sweeping Claws и Enduring Strength

RULE-PROFILE-CREATURE-010:enduring-strength; BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / Bear138; BOOK-PLAYER-GUIDE1.4, гл.V Opposed Tests109 / Near Miss112 / Combat Actions116 / Attack Tests118–119 / Conditions123. [ADR-0087](../decisions/ADR-0087-pc-bear-second-attack-policy.md) фиксирует выбранную пользователем тактику. Статус реализации и фактическая приёмка — в [project-status](../project-status.md).

`BEAR_SWEEPING_CLAWS`: natural Close4d/3 Damage5, hands=null, Athletics3d/3, Brute3/T5/Res6 armoured/noShield. Implicit caps8/6, без Greataxe-исключения. Первый профильный переход0→1 наносит Drained; при2Wounds он сохраняется,3Wounds defeats. Не выводить будущий NPC Recover из отсутствующего лечения. Полные характеристики/Skills сверены по карточке; factory хранит выбранный боевой loadout. Crushing Weight с Prone-before-Give-Ground и отдельным3d/cap8 не выбирается. Полный Fearsome trigger сохранён: Give Ground от Bear даёт Broken; PC fixed SUFFER_WOUND его не вызывает.

Enduring Strength после успешной Attack позволяет вторым действием атаковать **другого** врага в Close. HIT достаточен без раны, включая положительную ничью или Damage≤Resilience;0/0 — провал. Near Miss отменяет рану, не успех атаки. Staggered/Drained не запрещают саму способность. Общий максимум двух действий сохраняется; второй HIT третьего действия не даёт.

Сценарная тактика задаётся обязательным `npc_extra_attack_actor_ids`; `[]` явно отказывается от optional способности. Включать можно только opposition actors с полным canonical Bear/Sweeping Claws source. После всех обязательных последствий/Fate первой Attack выбирается первый другой живой PC по `enemy_target_priority`, исключая actual primary target даже после его смерти. Живой Defenceless подходит и не делает Protection Test. Если другой живой цели нет, второе действие/slot/RNG отсутствуют. Unsupported mandatory consequence останавливает бой до следующего действия.

Вторая Attack исполняется в настоящем ability slot2 с source-bound grant/receipt и отдельными action/kernel/Test IDs. TurnEnd происходит после обеих атак; Help конкретного первого Test не переносится. Clock проверяет структуру grant и first receipt, PC owner — полный первый Attack/HIT, canonical источник, policy, порядок и фактическую новую цель. Reservation, готовое состояние и Attack result проходят одинаковую проверку; один Rule ID не открывает повторную Attack.

Trial `npc_extra_attack_counts` и summary counts/trial count/total отражают только реально исполненные вторые Attack. Они входят в общий action count, grant/reservation — нет. Count search удаляет выбранные Bear IDs при исключении NPC, не переназначает их. Current PC JSON1 требует policy и метрики без defaults/compatibility; прежние120JSON documents мигрируются `[]`/нулями с сохранением остальных значений.

[Clock grant](../../src/towr/domain/turn_models.py), [PC policy projection](../../src/towr/domain/pc_npc_extra_attack_models.py), [runner](../../src/towr/engine/pc_melee_runner.py), [catalog tests](../../tests/unit/test_m39_pc_bear_catalog.py), [clock tests](../../tests/unit/test_k1_enduring_strength.py), [native targets/Fate/Help/guards](../../tests/unit/test_m39_pc_bear_execution.py), [примеры CLI](../examples/m39/README.md).

<a id="greataxe-cap-m38"></a>

## M38 — Minotaur Greataxe с canonical cap8

Статус: `verified` в PC family. RULE-PROFILE-BEASTMEN-005; BOOK-GM-GUIDE1.1, Allies and Antagonists / Minotaur147; BOOK-PLAYER-GUIDE1.4, Dice Pools107. [ADR-0086](../decisions/ADR-0086-pc-minotaur-greataxe-pool-cap.md), [примеры](../examples/m38/README.md). Это отдельная функция допуска cap и один loadout, не новый общий каталоговый чанк или произвольные authored caps.

`MINOTAUR_GREATAXE`: Close3d/5 Damage8,2H; explicit InlineProfile(3,5,8), Athletics4d/4 с cap=null, Brute3/T5Res6 armoured/noShield. Printed3d уже учитывает особенность оружия: второй штраф не добавляется. Dual Damage+1 не применяется. W1/W2 ordinary+1/+2d Melee, W3defeat и Devour сохраняются из [M37](#devour-chunk-m37); Fearsome/Charging Bull полными metadata вне fixed Attack/SUFFER_WOUND scene.

Пользователь выбрал explicit cap8 **только для attack этой canonical identity**. Остальные book/authored и все Protection profiles сохраняют null. Private admission проверяет expected cap отдельно для attack/Protection, затем полную canonical definition/source graph. Подмена ID/nested source/значений, cap=null под новым ID и равные float/string-enum/bool aliases отвергаются до RNG. None в прежних профилях означает старый implicit cap2×printed dice.

Current PC JSON1 уже имеет required pool_cap; schema расширена до enum:[null,8], объекты остаются closed. Семантический запрет чужого cap8 выполняет domain, как canonical gear/Damage guards. JSON Schema считает8.0 численно равным8, но domain требует exact int и отклоняет такой source. Codec asdict/InlineProfile(**source) не менялся; пропущенное поле не получает новый default/repair. Новых полей/версии/метрик/миграции116прежнихJSON documents нет.

Native проверки: W0/W1/W2 pools3/4/5 с maximum8, W3defeat; реальное сочетание W2/outnumber/higher ground и двух Help даёт7ordinary+2bypass=9dice (ошибочный cap6 дал бы8). Отдельный Test с большим обычным bonus capped8, затем+2bypass даёт10. Drained удаляет Test bonuses, но сохраняет Devour table die; base Damage8 без dual/PC Traits.

[Catalog](../../src/towr/domain/pc_npc_catalog.py), [cap admission](../../src/towr/domain/pc_melee_models.py), [profile rules](../../src/towr/domain/pc_npc_ability_models.py), [schema](../../src/towr/adapters/schemas/pc-melee-common.schema.json). Проверки: [catalog/full source](../../tests/unit/test_m38_pc_greataxe_catalog.py), [actual native cap/Help/Wounds/source](../../tests/unit/test_m38_pc_greataxe_execution.py), [JSON/trials/4состава](../../tests/integration/test_m38_pc_greataxe_cap.py). Каталог34→35; старые34entries/definitions/snapshots/metadata и116JSON documents M9–M37 сохраняются.

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
| 144 | Bestigor | Brute (2 Wounds) | при 0 Wounds не может выбрать Give Ground/Prone, при 1 Wound следующая attack Glorious; woodland Difficult Terrain игнорируется; перед attack может добровольно получить Staggered, если его нет; Staggered даёт `+1d к Melee attacks` |
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

Child of the Forest Gor/Warhound сохранён inactive только в неподвижной сцене без woodland terrain. Orc Choppas +1Damage на Charge — inactive, поскольку Charge не выполняется. Power of the Waaagh! при Help союзной Melee attack даёт **один free success без Test**, не bonus die; с [M34](#greenskin-help-m34) доступна при явной NPC Help policy. Все условия/эффекты сохранены в metadata. Orc использует printed Damage4 без добавочного PC dual/Charge/weapon trait.

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

<a id="goblin-chunk-m31"></a>

## M31 — Goblin Warrior, Nasty Skulker и Night Goblin

Статус: `verified` в PC family. RULE-PROFILE-GREENSKIN-001/002/003; BOOK-GM-GUIDE1.1, Allies and Antagonists / NPCs91 / Profiles93 / Goblin Warrior156 / Nasty Skulker и Night Goblins157. Дополнение: BOOK-PLAYER-GUIDE1.4, Equipment / Melee Weapons92 / Throwing96 / Armour97, Rules / Attack Tests/Recover118 / Staggered119 / Defenceless/Burdened123. [ADR-0082](../decisions/ADR-0082-pc-goblin-melee-chunk.md), [общие примеры](../examples/m31/README.md).

| Profile ID | Выбранная атака | Protection | Resilience / shield |
|---|---|---|---|
| GOBLIN_WARRIOR_SPEAR | Jagged Spear Close→maxShort2d/3 Damage3,1H | Athletics3d/2 | T3/printed5 armoured,shield |
| NASTY_SKULKER | Long knives Close4d/4 Damage3,1H | Defence4d/4 | T3/4 armoured,noShield |
| NIGHT_GOBLIN_SPEAR | Jagged Spear Close→maxShort2d/3 Damage3,1H | Athletics3d/2 | T3/variant printed4 armoured,shield |

Все Normal Minions. GM93/PG92 задают Melee range как максимум: Spear может атаковать Close без фальсификации printed Short. Night Goblin наследует Warrior с Initiative3 и явной заменой Resilience на4; shield сохраняется, поверх printed totals ничего не начисляется. Разницу между Toughness и итогом хранит ResilienceProfile.bonus; не пересчитывать variant total из Typical Trappings. Unselected: Shortbow обоих Warriors, Weighted Net Night Goblin, Athletics3d/3 Skulker. Сцена неподвижная, все участники уже Close.

**Dirty Coward (Warrior/Night):** actual repeated Staggered автоматически defeats, Goblin бросает оружие и бежит. Рана не наносится, GM не выбирает killed/KO/surrender. Typed MinionStaggerDefeatSpec/Cause/Result отделяют эффект от Profile Wound и связывают kernel ID/target/Rule ID. ProfileInjuryState с None cause сохраняет прежний invariant; только явная причина допускает defeated Minion при0Wounds/limit1. Обычный Staggered choice/RNG не вызывается. Промах уже Staggered атакующего не вызывает повторное Condition. Прямой damaging Wound сохраняет normal disposition. Skulker Dirty Coward не наследует.

Existing PC journal независимо восстанавливает canonical K1 результат; mandatory PcMinionStaggerDefeatProof один раз снимает оружие/available attacks, сохраняет shield и исключает NPC из ходов/численности/целей. Пока ACK не выполнен, injury уже defeated, но equipment ещё исходный. Source bank проверяет actual Attack/cause/drop и full replay; подмена ран/flags/IDs/повторное подтверждение запрещены. Такой NPC считается defeated для objective, без Broken/FreeMovement/смены Zone и без exit counter живого Official. Generic Condition/Hazard projections причину сохраняют.

**Backstabba (Skulker):** настоящая unopposed Melee attack имеет2Damage за success, остальные1. Opposed0success не становится unopposed. Runtime DamageProfile сохраняет base3 и меняет multiplier только для фактической атаки; canonical source остаётся3/1. Defenceless PC не Oppose, поэтому trigger применим в нынешнем owner после тяжёлой раны. Forced Wound остаётся одной, не по ране за success.

Horde позволяет Help attack без Test с+1d сверх обычного bonus cap; с [M34](#greenskin-help-m34) доступна при явной NPC Help policy. Skulking Menace позволяет Stealth исчезнуть без cover при5других Goblins в Zone; fixed NPC Attack strategy Stealth не делает. Полные условия сохранены в metadata, применимые Dirty Coward/Backstabba исполняются.

Current PC JSON1 требует explicit enemy.holds_shield и attack.range_max:close|short. Схемы/codec/readmission проверяют exact bool/enum, canonical shield/range и запрет shield с2H/natural.88старыхJSON documents мигрированы false/close с сохранением прочих значений. Другие families и текущий descriptor on-hit Drained не расширены. Weighted Net/Brawn recovery/расход предметов/новый AI не входят в M31.

Исполнение: [catalog](../../src/towr/domain/pc_npc_catalog.py), [K1 профильная причина](../../src/towr/domain/injury_models.py), [Staggered override](../../src/towr/rules/stagger_impact_resolution.py), [Kernel](../../src/towr/rules/kernel.py), [явные NPC helpers](../../src/towr/domain/pc_npc_ability_models.py), [PC cause/drop bank](../../src/towr/domain/pc_minion_defeat_models.py), [ACK/replay](../../src/towr/domain/_pc_melee_projection.py). Проверки: [K1](../../tests/unit/test_k1_minion_stagger_defeat.py), [catalog](../../tests/unit/test_m31_pc_goblin_catalog.py), [native/Defenceless/forgery](../../tests/unit/test_m31_pc_goblin_execution.py), [JSON/trials/8составов](../../tests/integration/test_m31_pc_goblin_chunk.py).

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
