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
