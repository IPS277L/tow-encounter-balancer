# Magic Items и wyrdstone

Источник: `BOOK-GM-GUIDE`, версия 1.1, глава Magic Items, страницы 81–90. Статус всей области: `draft`. Боевые Magic Weapons/Magic Armour и два вида зелий подключены; остальные группы и кампания с dawn/sunset/Downtime ещё не реализованы.

## RULE-MAGIC-ITEM-001 — приобретение и классификация

Magic item считается Asset, но не покупается обычным способом: его находят, получают как исключительную награду, наследуют, крадут либо временно получают от покровителя. Книга не задаёт ему стандартную Coin price или обычный Invest Money threshold.

Каталог делится на Magic Weapons, Magic Armour, Talismans, Arcane Items и Enchanted Items. Magic Weapons считаются magical damage source, если конкретный предмет не говорит иначе. Arcane Items доступны только персонажу с Wizard Level; Enchanted Items доступны любому персонажу.

Источник: страницы 81–82, 87–88.

## RULE-MAGIC-ITEM-002 — совместное использование защиты

Персонаж в magic и mundane armour получает benefits только одного комплекта, но penalties обоих, если предмет не задаёт исключение. Одновременно действует защита только одного Talisman. Несколько Talismans дают ненадёжные перемежающиеся эффекты; конкретные mishaps GM выбирает по образцам Miscast Table, а не бросает её автоматически.

Источник: страницы 85–86.

## RULE-MAGIC-ITEM-003 — Magic Weapons

| Предмет | Профиль | Нормативный эффект |
|---|---|---|
| Dragon Bow | optimum Medium–Extreme, Damage 6, 2H | Attack не получает die penalties и не бывает Grim; видимость всё равно обязательна. Раз за battle успешная attack накладывает Ablaze |
| Duellist Blades | Close, S+2, 2H | `+2d Defence`, пока не Staggered; Attack action разрешает вторую attack вторым action; при двух атаках можно сделать одну Grim, вторую Glorious |
| Grotargg’s Hammer | Close, S+3, 2H | attack с высоты Glorious; при таком промахе оружие застревает, извлечение — Very Difficult (`-2d`) Brawn Test |
| Headsman’s Axe | Close, S+3, 2H | против Prone можно добровольно сделать Test Grim; нанесённая этой атакой Wound заменяется Decapitation |
| Morning Star of Fracasse | Close, S+3, 1H | `-1d Melee`, пока Staggered; успешная attack по владельцу magic weapon disarms его до Recover action |
| Scarab Knife | Close, S+1, 1H | успешный hit накладывает Drained; каждая нанесённая Wound даёт charge; 3 charges лечат любую одну Wound; остаток charges исчезает на закате |
| Sword of Justice | Close, S+1, 1H | `+1d Wounds Table`; attack против Champion или PC в single combat Glorious |
| Trickster Blade | Close, S+1, 1H | `+1d Defence`, пока не Staggered; по команде выглядит как обычный неуникальный предмет сходной формы/размера, но прикосновение раскрывает обман |
| Unwavering Spear | Short, S+1, 2H | цель не может Give Ground от attack и выбирает Wound либо Prone; attack по цели, уже Give Ground в этом round, Glorious; сломанная восстанавливается в следующий Downtime, сожжённая уничтожается окончательно |

Источник: страницы 82–84.

Уточнения Weapons/Equipment приняты в [ADR-0140](../decisions/ADR-0140-all-weapons-and-shared-inventory.md): основное Damage/Skill и stacking Defence при Dual Wield; расход огненной стрелы при реальном выстреле, включая MISS; один disarm от Fracasse; лечение одной собственной раны за3заряда Scarab через предметное взаимодействие standard Recover; отдельный alternate Recover/Brawn−2d для Grotargg; порядок Grim→Glorious и предел двух действий Duellist; автоматический изолированный1v1 и подтверждённые GM-пары single combat. Эти решения не требуют повторного согласования.

Общая [подготовка качества Attack](../../src/towr/domain/weapon_quality_preparation.py) сохраняет конкретные источники применяемых предметов. Лук дракона (Dragon Bow) нельзя применить к невидимой цели; отмена отрицательных кубов и Мрачного (Grim) не снимает reroll locks, не удаляет потраченную Судьбу (Fate) и не меняет предел дальности. При Drained новые предметные Glorious не действуют, а добровольная Grim-цена сохраняется. Фактический Prone даёт преимущество higher ground для Grotargg по PG123. Фактические последствия исполняются [Magic Weapon owner](../../src/towr/domain/pc_magic_weapon_models.py): Dragon fire тратится один раз при выстреле; Fracasse выбивает один held magic unit; Scarab учитывает actual Wound после Fate/Near Miss и лечит за3charges настоящим Recover; Grotargg имеет alternate Recover/Brawn−2d. Headsman использует отдельный fixed Decapitation27+ source без фиктивного броска Wounds Table и без убийства от одного HIT. Duellist создаёт настоящее второе действие с общим пределом двух; Justice проверяет actual single combat; Unwavering использует фактический once-round Give Ground bank. [Покрытие и проверки](../implementation-coverage.md#полная-область-weaponsequipment-после-armour). Закат/приобретение/разрушение/Downtime и повествовательный облик не создают событий времени или бесплатную засаду в нынешнем бою.

## RULE-MAGIC-ITEM-004 — Magic Armour

| Предмет | Resilience | Нормативный эффект |
|---|---:|---|
| Armour of Agilulf | `T+2` | Weapon Skill, Melee и Defence устанавливаются ровно в `5`; Bretonnian language; доспех физически препятствует нарушению Code Chivalric/Rules of Knightly Honour и при упорстве покидает владельца |
| Armour of Meteoric Iron | `T+3` | mundane weapon effects, игнорирующие armour или дающие bonus damage против брони, отменяются |
| Briarroot Shield | `+1` | несётся, не надевается; Defence может oppose Shooting; успешная Defence против Melee накладывает Burdened, а атакующий не может покинуть Close Range с оружием до снятия Condition либо ухода владельца щита |
| Helm of the Hunt | `+1` | Charge Attack Tests и Tests преследования/выслеживания Glorious; запрещает burn Fate для Near Miss |
| Mantle of Ithilmar | `T+3` | `+1d` против environmental Hazards и Conditions; Wizard может cast spells в этой armour |

Источник: страницы 85–86.

Принятые трактовки для исполнения Magic Armour: Helm of the Hunt складывается с body armour; Briarroot Shield хранит независимые связи конкретных щита и оружия. Освобождение, фактический сброс захваченного оружия или уход shield-bearer снимают только соответствующую связь и её Burdened. Один успешный Brawn Recover освобождает от одного выбранного щита. Это решения пользователя, не официальная errata; [полный контракт](../decisions/ADR-0139-all-armour-and-protection.md).

Пользователь также подтвердил, что падение (Falling Damage) после вынужденного спешивания является environmental Hazard для Mantle of Ithilmar. Выбранная мантия даёт +1d к настоящему Athletics Test обеим сторонам; Drained подавляет положительный куб. Причина спешивания не меняет эту классификацию. Прочие Hazards не становятся environmental автоматически; погода/пожар в сцену этим решением не добавляются.

## RULE-MAGIC-ITEM-005 — Talismans

| Предмет | Нормативный эффект |
|---|---|
| Glamourweave | перед attack по владельцу враг получает Blinded; после снятия иммунен до следующего рассвета; Stealth владельца Grim |
| Luckstone | каждый рассвет даёт 3 lucky dice; любое число можно добавить к своему Test до или после roll, пока GM не описал outcome; если lucky die показывает `10`, все остальные dice pool считаются failures |
| Obsidian Lodestone | spell, затрагивающий владельца, теряет `1 Potency`; при `0` не действует |
| Runic Passkey | Difficult Terrain не действует; Brawn против неодушевлённых препятствий Glorious |
| Talisman of Protection | при любой полученной Wound бросается d10; на `1` Wound отменяется |

Источник: страницы 86–87.

## RULE-MAGIC-ITEM-006 — Arcane Items и wyrdstone

| Предмет | Нормативный эффект |
|---|---|
| Book of Ashur | literate Wizard improvises spell как из собственного grimoire, уменьшая CV вдвое; финальные `10` Casting Test добавляют Miscast dice так же, как `9` |
| Crystal Ball | Awareness Test как action; при success владелец выбирает одну enemy Attack до своего следующего turn и делает её Grim, если target — он либо ally в Medium Range |
| Dispel Scroll | одноразово даёт Wizard Talent Dispeller; при уже имеющемся Talent Test Glorious, но `9` нельзя перебросить; после применения уничтожается |
| Staff of Power | Potency каждого cast spell увеличивается на `1`; также обычный staff weapon |

Один nugget wyrdstone при Casting Test даёт `2` free successes и одновременно добавляет `2` dice в Miscast Pool. Использование всегда является Corruption exposure. Более крупный кусок может дать дополнительную силу либо несколько применений только по явно заданному сценарием размеру; универсальной шкалы книга не приводит.

Источник: страницы 87–88.

## RULE-MAGIC-ITEM-007 — Enchanted Items

| Предмет | Нормативный эффект |
|---|---|
| Clanner’s Tankard | любая пригодная для питья жидкость становится элем, пока находится в кружке или проглатывается из неё |
| Drowned Man’s Whisper | после вдоха не нужно дышать до выдоха; речь требует выдоха; до следующего нормального вдоха действует Drained |
| Enhancement Potion | Recover action полностью расходует potion и даёт `+1` к одной из восьми Characteristics до следующего заката |
| Flying Carpet | Speed становится Fast; позволяет vertical movement и игнорирует ground obstacles; из Close Range наземного врага нельзя move/Give Ground прямо в midair Zone |
| Gauntlet of the Duel | при входе в Close Range можно бросить и вызвать Champion; до поражения одного attacks дуэлянтов друг по другу Glorious и им нельзя покинуть Close Range; вмешательство других Grim; поднятие — Recover action |
| Hail of Doom Arrow | одноразовая стрела для sturdy bow; attack не Opposed; при success наносит `6 Damage` каждому существу в target Zone |
| Healing Potion | Recover action полностью расходует potion и лечит одну Wound со всеми соответствующими effects; доступно даже при Defenceless, но другие actions в этот turn запрещены |
| Platter of Peace | пока на блюде остаётся еда и участники едят поданную с него трапезу, насилие между ними невозможно: Attack Tests fail, hostile spells нельзя cast, случайный вред также блокирован |
| Ring of Taal | позволяет cast memorised Oaken Shield с профилем кольца Reason 4, Willpower 4, Wizard Level 2; Miscast действует на владельца; нарушение Stricture Taal блокирует предмет до atonement |
| Silver Horn | Music Lore; action и Leadership Test; за каждый success владелец выбирает слышащего ally или себя, и цель выбирает снять Broken либо move на одну Zone к врагу |

Healing и Enhancement Potions можно создать через Craft Trapping при Concoction Lore: Exacting Test на `8` successes, каждый входящий Test требует bespoke magical ingredients, найденных в adventure либо купленных за одну Gold Coin.

Источник: страницы 88–90.

## Зелья в динамическом melee-генераторе

Healing Potion и Enhancement Potion исполняются в [ADR-0119](../decisions/ADR-0119-pc-potions-in-dynamic-encounters.md), а не только хранятся в инвентаре. Применение занимает object interaction обычного Recover: standard benefits сохраняются, одновременного подбора оружия/щита нет. Лечебное выбирает собственную рану1–23 текущего боя, помечает её treated/healed и снимает все соответствующие effects, включая восстановимую немедленным применением анатомию; чужие источники Conditions сохраняются. Recorded dropped items требуют будущего подбора. Defenceless может только выполнить свой разрешённый Healing Recover, без второго действия.

Усиление поддерживает WS/Strength/Toughness/Agility и меняет соответствующие настоящие характеристики/caps/Damage/Resilience, сохраняя остальные правила. Предполагается короткий бой до заката; срок не превращён в произвольное число раундов. Другие Characteristics пока не исполняются и блокируют расчёт до MC. Начальное описание не меняется, каждый trial получает свой запас.

Пользователь подтвердил GM/scenario-конкретизацию рук: достаточно одной пригодной руки, в том числе занятой оружием/щитом, без отдельного сброса. При доступной здоровой выбирается здоровая, использование Injured Hand12 вызывает прежний Critical. Это не напечатанное требование книги. Once-per-Characteristic — выбранная добровольная тактика расхода, не общее книжное правило stacking.

## Архитектурная граница

Magic item должен быть типизированным Asset с собственным persistent state: charges, dawn/sunset refresh, once-per-battle use, immunity window, ownership и destruction. Его effect подключается к существующей фазе Test/attack/Wound/spell/movement, а не исполняется из строки описания. Предметы с `may` создают decision request владельцу; предметы с GM judgment получают готовый scenario input.
