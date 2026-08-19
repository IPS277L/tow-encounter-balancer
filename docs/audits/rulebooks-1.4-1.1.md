# Полный аудит Player’s Guide 1.4 и Gamemaster’s Guide 1.1

Дата начала: 2026-08-19.

## Цель и критерий завершения

Аудит проверяет актуальные локальные книги напрямую, а не только по changelog. Каждый диапазон страниц должен быть прочитан целиком и классифицирован как `RULE`, `DEFINITION`, `OPTION`, `EXAMPLE`, `LORE`, `GUIDANCE` или `AMBIGUITY` по `docs/source-policy.md`.

Диапазон считается `reviewed`, только когда:

- прочитан весь извлечённый текст каждой страницы;
- нормативные утверждения сопоставлены с `docs/rules/`, `docs/rule-traceability.md`, кодом и тестами;
- найденные расхождения записаны ниже и, при необходимости, в `docs/contradictions.md`;
- лор и примеры не превращены в правила;
- указана точная версия, глава и страница.

Статусы: `pending` — ещё не прочитан; `in_progress` — чтение начато; `reviewed` — критерии выше выполнены; `recheck_visual` — нужен просмотр верстки/изображения PDF.

## Зафиксированные источники

| Source ID | Версия | Last Edited | Страниц | SHA-256 |
|---|---:|---|---:|---|
| BOOK-PLAYER-GUIDE | 1.4 | 29 January 2026 | 192 | `3090B91DD7B414B10C4D9F9A3BAC50CAEA1E5787CF3F86490BA4540C38EE127F` |
| BOOK-GM-GUIDE | 1.1 | 29 January 2026 | 192 | `A920C1893D75A38E569D33153D74EB5735410685BA3ADEEAE23E24239AFC7055` |

Версии подтверждены пользователем 2026-08-19. Имена файлов, метаданные и состояние извлечения находятся в `docs/source-index.md`.

## Player’s Guide 1.4

| Страницы | Раздел | Основной тип | Статус | Результат |
|---:|---|---|---|---|
| 1–3 | обложка, credits, contents | DEFINITION | reviewed | Версия/дата/структура подтверждены; механик нет |
| 4–9 | An Empire Divided; Streets of Talagaad | LORE | reviewed | Нормативных правил нет; страницы 5–6 являются иллюстративным разворотом |
| 10–11 | Introduction; Using this Book | GUIDANCE/DEFINITION | reviewed | `RULE-DICE-001`; остальное — назначение книги и setting guidance |
| 12–23 | Character Creation; Origins | RULE/DEFINITION | reviewed | `RULE-CHARACTER-001..004`, `RULE-TEST-007`; страницы 16–21 — лор Origins, 22–23 — нормативные опции |
| 24–55 | Careers | RULE/DEFINITION/LORE | reviewed | `RULE-CAREER-001..004`; отделены framework, 30 профилей/талантов и flavor-вставки |
| 56–60 | Contacts | RULE/DEFINITION/GUIDANCE | reviewed | `RULE-CONTACT-001..002`; четыре Talagaad tables отделены от ненормативных описаний склонности к помощи |
| 61–65 | Final Steps; Grim Portent | RULE/OPTION/GUIDANCE | reviewed | `RULE-CHARACTER-006`; производные значения/boon отделены от опциональных detail tables и campaign guidance |
| 66–72 | Advancement; Characteristics & Skills | RULE/DEFINITION/GUIDANCE | reviewed | `RULE-ADVANCEMENT-001..003`, `RULE-SKILL-001..006`; suggested consequences оставлены GM policy |
| 73–81 | Talents | RULE | reviewed | `RULE-TALENT-001..003`; проиндексированы 59 Talents и 9 Familiar effects, отмечено реальное покрытие |
| 82–89 | Lores; Status | RULE/DEFINITION/EXAMPLE | reviewed | `RULE-LORE-001..004`, `RULE-STATUS-001..002`; примеры конкретности не обобщены в скрытые бонусы |
| 90–105 | Equipment | RULE/DEFINITION/GUIDANCE | reviewed | `RULE-EQUIPMENT-001..008`; зафиксированы economy, все combat profiles, tools/services и Assets |
| 106–111 | Rolling Dice; Tests; Fate | RULE/DEFINITION/OPTION | reviewed | `RULE-TEST-001..007`, `RULE-FATE-001..003`; актуальный K1 Test kernel сверён, Exacting расширен |
| 112–120 | Fate continuation; Combat | RULE/DEFINITION/EXAMPLE | reviewed | `RULE-COMBAT-001..016`; example не использован как самостоятельное правило |
| 121–123 | Wounds & Conditions | RULE/DEFINITION | reviewed | `RULE-HEALTH-001..010`; 11 Conditions, treatment/healing, Infection и Surgery сверены с кодом |
| 124–130 | Mounts, Vehicles, Investigation, Social Encounters | RULE/DEFINITION/GUIDANCE | reviewed | `RULE-MOUNT-*`, `RULE-VEHICLE-*`, `RULE-INVESTIGATION-*`, `RULE-SOCIAL-*` |
| 131–136 | Between Adventures | RULE/OPTION/GUIDANCE | reviewed | `RULE-DOWNTIME-001..003`; все 17 Endeavours и persistent dependencies зафиксированы |
| 137–151 | Religion & Belief | RULE/LORE/GUIDANCE | reviewed | `RULE-FAITH-001..004`; 10 Stricture sets, Favours и 30 Prayers отделены от lore/Miracle guidance |
| 152–155 | Magic foundations | RULE/DEFINITION/LORE | reviewed | `RULE-MAGIC-005`; механической является spell schema страницы 155, остальное setting context |
| 156–160 | Casting, Miscasts, corrected Miscast Table | RULE/EXAMPLE | reviewed | `RULE-MAGIC-002..004`; `AMBIGUITY-003` закрыта; Miscast pipeline обновлён |
| 161–174 | Lores of Magic and spell rules | RULE/LORE/EXAMPLE | reviewed | `RULE-SPELL-001..005`; 42 formal spells и improvised categories проиндексированы |
| 175–188 | The Old World | LORE | reviewed | Весь диапазон прочитан; самостоятельных механик не найдено |
| 189–192 | Index, Wounds Table, NPC summary, back matter | DEFINITION/RULE | reviewed | Index проверен; актуальные границы Wounds `1–27+` и четыре NPC types совпадают с кодом/тестами |

## Gamemaster’s Guide 1.1

| Страницы | Раздел | Основной тип | Статус | Результат |
|---:|---|---|---|---|
| 1–6 | обложка, credits, contents, introduction | DEFINITION/GUIDANCE/LORE | reviewed | Last Edited и структура подтверждены; mechanics нет, страницы 4–5 — in-world handouts |
| 7–18 | Adventures in Talagaad; Grim Portents | LORE/GUIDANCE/RULE | reviewed | Setting и три готовых Grim Portents отделены от единственной переносимой механики `RULE-TALAGAAD-001` |
| 19–41 | Contacts | RULE/LORE | reviewed | Извлечены общий Contact contract, Primary Skill modifier, создание новых Contacts и полный каталог 20 профилей; Favours/Needs оставлены GM guidance |
| 42–55 | Being the GM; campaigns; Grim Portents; Dark Threads | GUIDANCE/RULE | reviewed | Почти весь диапазон — GM guidance; нормативно дополнена cadence Endeavours, а Grim Portent/Dark Threads не превращены в автоматические mechanics |
| 56–65 | Designing an Adventure; Using the Rules | GUIDANCE/RULE/OPTION | reviewed | Уточнены Clues/Insights/Leads, encounter guidance, Test policy, Complications и опциональная Magical Panic table |
| 66–69 | Events in Talagaad | RULE/LORE | reviewed | Извлечены d100 Event procedure и duplicate policy; выявлен пропуск Wander the Wilds в summary table |
| 70–80 | Corruption | RULE/DEFINITION | reviewed | Полностью нормализованы Exposure Test, стадии/detection/redemption и пять Paths с точными boons/drawbacks |
| 81–90 | Magic Items | RULE/DEFINITION | reviewed | Нормализованы Asset/stacking contracts, 33 item profiles, wyrdstone и potion crafting; clocks/charges отмечены как persistent state |
| 91–93 | NPC types and profile format | RULE/DEFINITION | reviewed | Четыре injury policies и format fields перепроверены по 1.1; добавлен точный mounted Monstrosity action/injury split |
| 94–102 | Grand Duchy of Talabec profiles | RULE/LORE | reviewed | 11 profiles и их Abilities проиндексированы; faction text и Noble Vendetta table отделены от боевых rules |
| 103–109 | Ogres, Halflings, Dwarfs, Elves, Bretonnia | RULE/LORE | reviewed | 8 profiles и attack/Ability effects проиндексированы; выявлена отдельная value-level Condition immunity Questing Knight |
| 110–125 | Osterlund and Reikland profiles | RULE/LORE | reviewed | 8 profiles с Wound bands, detachments, reload/Aim, Charge, faith и immunity effects проиндексированы |
| 126–138 | Witches, Warlocks, Pets, Mounts | RULE/LORE | reviewed | 4 Wizard и 10 creature profiles проиндексированы; casting resource, pet turn/targeting, swarm и rider contracts извлечены |
| 139–153 | Beastmen | RULE/LORE | reviewed | 10 profiles проиндексированы; пять разных multi-target/timing моделей и Swallow Whole отделены от общего attack pipeline |
| 154–164 | Orc & Goblin Tribes | RULE/LORE | reviewed | 11 profiles/variants проиндексированы; Help/free successes, swarms/vehicle, Wizard group power и Boss actions извлечены |
| 165–173 | The Undead | RULE/LORE | reviewed | 5 undead profiles и все immunity/reanimation/aura/weakness/spell effects проиндексированы |
| 174–187 | Monsters of the Great Forest | RULE/LORE | reviewed | Bone Dragon и 11 forest monster profiles проиндексированы; все Reactions/Hazards/rider benefits/random attacks перепроверены |
| 188–192 | Index and Rules Reference | DEFINITION/RULE | reviewed | Index не содержит новых rules; reference pages повторяют основные contracts, обнаружена и закрыта опечатка Failure outcome |

## Находки и влияние

| ID | Источник | Классификация | Находка | Влияние/действие | Статус |
|---|---|---|---|---|---|
| AUDIT-001 | обе книги | DEFINITION | Актуальные версии — Player’s Guide 1.4 и Gamemaster’s Guide 1.1 | Версии закреплены в реестре и этом журнале | resolved |
| AUDIT-002 | Player’s Guide 1.4, 157–159 | RULE | Miscast теряет накопленные Casting successes; немедленное заклинание перед таблицей добавляет `+1d`; диапазоны `21–22` и `23–24` не пересекаются | Реализован pipeline до typed table-effect request; `AMBIGUITY-003` закрыта | resolved |
| AUDIT-003 | Gamemaster’s Guide 1.1 | DEFINITION | Новая пагинация отличается от прежнего локального файла | Все ссылки и весь диапазон 1–192 семантически перепроверены по текущему файлу | resolved |
| AUDIT-004 | Player’s Guide 1.4, 11 | DEFINITION/RULE | Определены d10, сумма `Nd10` и d100 с `00 = 100` | Добавлен `RULE-DICE-001`; d100 пока не реализован | recorded |
| AUDIT-005 | Player’s Guide 1.4, 12 | DEFINITION/RULE | Exacting Test накапливает успехи нескольких Tests во времени | Добавлен draft `RULE-TEST-007`; общий lifecycle отсутствует | recorded |
| AUDIT-006 | Player’s Guide 1.4, 13, 22–23 | RULE | Origin и случайность задают стартовые Characteristics, Skills, Talents, Lores, Fate и XP | Добавлены `RULE-CHARACTER-001..004`; будущий application/data слой | recorded |
| AUDIT-007 | Player’s Guide 1.4, 24–55 | RULE | Career задаёт Status, Favoured Characteristics, Skills, Lores, Trappings, Assets, Contacts и один из 30 уникальных Career Talents; случайный выбор даёт `1 XP` | Добавлены `RULE-CAREER-001..004` и полный реестр Career Talents; большинство требует будущих typed reducers/orchestration | recorded |
| AUDIT-008 | Player’s Guide 1.4, 24–25 | RULE | Life in Disgrace и смена Career зависят от ещё не проверенных Status, Advancement и Endeavour правил | Отложена окончательная application-семантика до страниц 66–72, 88–89 и 131–136 | pending_dependency |
| AUDIT-009 | Player’s Guide 1.4, 56–60 | RULE/GUIDANCE | Персонаж получает два Contacts без XP за случайность; четыре Talagaad tables задают NPC и отношения, но описания групп не дают числовых гарантий помощи | Добавлены `RULE-CONTACT-001..002`; фактическая эксплуатация Contacts отложена до GM Guide 19–41 | recorded |
| AUDIT-010 | Player’s Guide 1.4, 56, 61–65 | RULE/OPTION/GUIDANCE | Final Steps даёт один из трёх boons, после чего вычисляются Speed/Resilience и тратится bonus XP; внешность/отношения и Grim Portent преимущественно направляют повествование | Добавлены `RULE-CHARACTER-005..006`; механика Grim Portent отложена до GM Guide | recorded |
| AUDIT-011 | Player’s Guide 1.4, 66 | RULE | XP повышает Characteristics/покупает Talents, Skills используют Improvement Track, а максимумы Characteristics зависят от Origin | Добавлены `RULE-ADVANCEMENT-001..003`; Downtime dependencies отмечены явно | recorded |
| AUDIT-012 | Player’s Guide 1.4, 67–72 | RULE/GUIDANCE | Skills задают конкретные opposition/weapon/action restrictions; suggested complications/effects являются примерами | Добавлены `RULE-SKILL-001..006`; выявлены пробелы Brawn, stealth sequencing и action orchestration | recorded |
| AUDIT-013 | Player’s Guide 1.4, 73–81 | RULE | Каталог содержит 59 Talents, включая repeatable Faith/Familiar/Wizard и множество battle/session lifecycle эффектов | Добавлены `RULE-TALENT-001..003` и полный реестр; только отдельные magic/effect primitives уже существуют | recorded |
| AUDIT-014 | Player’s Guide 1.4, 74–75 | RULE | Dispeller распространяет Rule of Nine на disruption, ongoing dispel и spell maintenance; Familiar Chaos Sink меняет Miscast Table roll | Существующий Miscast pipeline требует будущих entry points для этих player-owned эффектов | recorded |
| AUDIT-015 | Player’s Guide 1.4, 82–88 | RULE/EXAMPLE | Lore может давать automatic knowledge, Test eligibility, `+1d` или прямой эффект; Monster Slayer явно разрешает Attack bonus | Добавлены `RULE-LORE-001..004`; каталоги и исключения отделены от illustrative examples | recorded |
| AUDIT-016 | Player’s Guide 1.4, 89 | RULE/GUIDANCE | Status имеет только Brass/Silver/Gold и влияет на расходы/ожидания, но описания lifestyle не являются автоматическим penalty engine | Добавлены `RULE-STATUS-001..002`; зависимости от equipment/social sections оставлены открытыми | recorded |
| AUDIT-017 | Player’s Guide 1.4, 90–105 | RULE | Coin — per-adventure abstract expense; reload — Exacting Test; inventory, dual wield, ranged/throwing, armour и Assets имеют разные lifecycle | Добавлены `RULE-EQUIPMENT-001..008` и нормативные numeric profiles; существующий kernel покрывает только часть impact traits | recorded |
| AUDIT-018 | Player’s Guide 1.4, 93 | AMBIGUITY | Greatsword в актуальном текстовом слое имеет `+1 to Defence`, тогда как родственные defensive traits используют `+1d` | Не исправлять догадкой; визуально/контекстно перепроверить перед реализацией profile | recheck_visual |
| AUDIT-019 | Player’s Guide 1.4, 106–110 | RULE | Реализованные Basic/Opposed/Grim/Glorious правила совпадают с актуальным текстом; Exacting также поддерживает multi-contributor, opposed net progress и costs | `RULE-TEST-007` дополнен; общий Exacting lifecycle остаётся gap | verified |
| AUDIT-020 | Player’s Guide 1.4, 111–112 | RULE | Fate разделяет session spends и permanent burn; Near Miss применяется после Wounds Table, Last Stand требует уже имеющуюся Wound | Добавлены `RULE-FATE-001..003`; текущий kernel реализует лишь wound-negation часть | recorded |
| AUDIT-021 | Player’s Guide 1.4, 112–120 | RULE | Книжный battle loop использует side initiative, максимум 2 разных actions, graph-like Zones, Speed, four Manoeuvres и campaign Retreat table | `RULE-COMBAT-001..016` дополнены; прототипный `engine/battle.py` не является полной реализацией | recorded |
| AUDIT-022 | Player’s Guide 1.4, 121–123 | RULE | Домен перечисляет все 11 книжных Conditions, но большинство их turn/action/removal effects ещё не исполняется | Расширены `RULE-HEALTH-007..010`; generic presence не считается полной реализацией condition | recorded |
| AUDIT-023 | Player’s Guide 1.4, 122 | RULE | В конце дня с новыми Wounds обязательна Infection Test; Festering Wound untreated, неизлечима treatment и требует Rest and Recovery | Выявлен отсутствующий day/campaign lifecycle; добавлен `RULE-HEALTH-009` | recorded |
| AUDIT-024 | Player’s Guide 1.4, 124–127 | RULE | Mount+rider обычно единая сущность; vehicle использует отдельные unopposed hit/Fault/wreck правила и immune ко всем Conditions кроме Ablaze | Добавлены mount/vehicle rules и profiles; нужен отдельный typed aggregate/pipeline | recorded |
| AUDIT-025 | Player’s Guide 1.4, 128–130 | RULE/GUIDANCE | Clue никогда не закрывается Test; три social actions и Status expectations дают конкретные Tests/modifiers | Добавлены investigation/social rules; интерпретация речи/ожиданий остаётся GM/policy input | recorded |
| AUDIT-026 | Player’s Guide 1.4, 131–136 | RULE | Downtime даёт до трёх Endeavours, развивает Skills failure dice и содержит 17 процедур для Contacts/Coin/Career/craft/magic/recovery | Добавлены `RULE-DOWNTIME-001..003`; выявлена потребность в campaign clock и persistent Exacting state | recorded |
| AUDIT-027 | Player’s Guide 1.4, 133 | RULE | Полный Change Career сохраняет старые Talent/Lores/trappings/Contacts и не выдаёт новые Lores/trappings/Contacts | Исправлен `RULE-CAREER-003`, ранее записанный только по краткому тексту страницы 25 | resolved |
| AUDIT-028 | Player’s Guide 1.4, 137–149 | RULE | Faith выбирает одного god, несовместима со spellcasting и прогрессирует Favour → Prayers → расходуемые Miracles | Добавлены `RULE-FAITH-001..004` и полный каталог 10/30; ни один effect пока не реализован end-to-end | recorded |
| AUDIT-029 | Player’s Guide 1.4, 150–151 | LORE/DEFINITION | Elven и Dwarf priests прямо не используют Human miracle model; Lady of the Lake связана с отдельными Talents | Не синтезировать механики для иных pantheons из setting text | recorded |
| AUDIT-030 | Player’s Guide 1.4, 152–155 | LORE/RULE | Нормативный общий контракт здесь ограничен Wizard terminology и CV/Target/Range/Duration; Hexenguilde/Dhar/persecution описывают мир | Добавлен `RULE-MAGIC-005`; setting claims не стали modifiers/corruption rules | recorded |
| AUDIT-031 | Player’s Guide 1.4, 160–174 | RULE/EXAMPLE | Improvised spell имеет Level/CV/damage scale и cumulative modifiers; Lore tables дают examples, не закрытый spell list | Добавлен `RULE-SPELL-001`, policy boundary сохранена | recorded |
| AUDIT-032 | Player’s Guide 1.4, 162–174 | RULE | Каталог содержит 42 formal spells: Battle 10, Elementalism 11, Illusion 10, Necromancy 11 | Добавлены `RULE-SPELL-002..005`; текущая программа полностью исполняет только один узкий spell effect | recorded |
| AUDIT-033 | Player’s Guide 1.4, 175–188 | LORE | Setting chapter не содержит самостоятельных mechanics/options | Диапазон отмечен только в lore index; текст мира не перенесён в simulator | verified |
| AUDIT-034 | Player’s Guide 1.4, 190–191 | RULE/REFERENCE | Wounds Table использует границы `1–3`, затем `4..26`, `27+`; NPC summary подтверждает Minion/Brute/Champion/Monstrosity policies | `wound_table.py` и boundary tests совпадают с актуальной 1.4 | verified |
| AUDIT-035 | Gamemaster’s Guide 1.1, 1–6 | DEFINITION/GUIDANCE | Last Edited 29 January 2026 и трёхчастная структура книги подтверждены напрямую; первые handouts не являются rules | Диапазон закрыт без создания Rule ID | verified |
| AUDIT-036 | Gamemaster’s Guide 1.1, 7–18 | LORE/GUIDANCE/RULE | Сюжетные зацепки и три Grim Portents не являются универсальными процедурами; страница 13 содержит отдельную Ability Favoured of Ahalt | Добавлен `RULE-TALAGAAD-001`; сюжетный текст не превращён в simulator rules | recorded |
| AUDIT-037 | Gamemaster’s Guide 1.1, 19–21 | RULE/GUIDANCE | Совпадение Primary Skill даёт ровно `+1d` к Endeavour независимо от числа Contacts; новый Contact требует Exacting Test с 4 успехами и одним броском за Endeavour | Добавлены `RULE-CONTACT-003..005`; нужен общий Exacting/campaign lifecycle | recorded |
| AUDIT-038 | Gamemaster’s Guide 1.1, 20, 22–41 | RULE/LORE/GUIDANCE | Все 20 Contacts имеют Archetype и Primary Skill и используют изменяемые Champion NPC profiles; Favours/Needs не задают унифицированной числовой процедуры | Добавлен каталог `RULE-CONTACT-006`; narrative services не превращены в безусловные actions | recorded |
| AUDIT-039 | Gamemaster’s Guide 1.1, 42–46 | GUIDANCE | Campaign structure, pacing, NPC portrayal и threat introduction не задают обязательного алгоритма симуляции | Диапазон классифицирован без новых Rule ID | verified |
| AUDIT-040 | Gamemaster’s Guide 1.1, 47 | RULE/OPTION | Рекомендована одна Endeavour за weekly session, больше при редкой игре, группировка по 2–3 и три способа downtime on the road | Добавлен `RULE-DOWNTIME-004`; cadence отнесена к campaign state | recorded |
| AUDIT-041 | Gamemaster’s Guide 1.1, 47–55 | GUIDANCE | Grim Portent имеет четыре design goals; Grim Reminders и изменяемая сеть Dark Threads — инструменты кампании, не источники автоматических modifiers | Синхронизирован раздел Grim Portent; новых simulator rules не создано | verified |
| AUDIT-042 | Gamemaster’s Guide 1.1, 56–59 | GUIDANCE/RULE | Для mystery рекомендуются 3–4 гарантированно найденных Clues; обычный social dialogue не требует Test, пока не возник значимый impasse | Расширены `RULE-INVESTIGATION-001` и `RULE-SOCIAL-005` | recorded |
| AUDIT-043 | Gamemaster’s Guide 1.1, 60 | OPTION/GUIDANCE | Публичная магия может вызвать d10 Magical Panic reaction, но таблица применяется только когда GM нужна быстрая реакция | Добавлен `RULE-MAGIC-006` как optional campaign event | recorded |
| AUDIT-044 | Gamemaster’s Guide 1.1, 60–63 | GUIDANCE/RULE | Battle objectives, NPC retreat и качественные encounter tiers подтверждены; combat summary не изменяет Player 1.4 contracts | Существующие `RULE-ENCOUNTER-001..003` подтверждены без ложной формулы баланса | verified |
| AUDIT-045 | Gamemaster’s Guide 1.1, 64–65 | RULE/GUIDANCE | Test нужен только при сомнительном, достижимом и значимом исходе; типовые penalties `-1d/-2d`; marginal success обычно несёт не отменяющую успех Complication | Добавлен `RULE-TEST-008`, уточнён `RULE-TEST-002` | recorded |
| AUDIT-046 | Gamemaster’s Guide 1.1, 66 | REFERENCE | Endeavour Summary Table пропускает Wander the Wilds, хотя основной Player’s Guide 1.4 содержит 17 Endeavours | Закрыто как `AMBIGUITY-004`: summary неполна, нормативен полный раздел Player’s Guide | resolved |
| AUDIT-047 | Gamemaster’s Guide 1.1, 67–69 | RULE/GUIDANCE | Downtime начинает d100 Talagaad Event; прежний результат можно перебросить либо эскалировать, а сюжетные записи не имеют автоматических числовых эффектов | Добавлен `RULE-DOWNTIME-005`; будущему campaign state нужна history Events | recorded |
| AUDIT-048 | Gamemaster’s Guide 1.1, 70–73 | RULE/DEFINITION | Corruption использует один end-of-day Willpower Test по худшей exposure, отдельный persistent state Vulnerable→Tarnished→Tainted→Damned и редкое narrative redemption | Добавлены `RULE-CORRUPTION-001..003`; Corruption не сведена к Condition | recorded |
| AUDIT-049 | Gamemaster’s Guide 1.1, 74–80 | RULE/GUIDANCE | Пять Paths содержат конкретные automatic successes, characteristic/Resilience/Skill modifiers, spell/Miscast, injury suppression и session/downtime lifecycle вперемешку с решениями GM | Добавлены `RULE-CORRUPTION-004..008`; точные effects отделены от fuzzy narrative predicates | recorded |
| AUDIT-050 | Gamemaster’s Guide 1.1, 81–88 | RULE/DEFINITION | Magic items — непокупаемые обычным способом Assets; armour/talisman stacking различаются; оружие, armour, talismans и arcane items имеют phase-specific effects | Добавлены `RULE-MAGIC-ITEM-001..006`; каталог хранит точные profiles/effects | recorded |
| AUDIT-051 | Gamemaster’s Guide 1.1, 88–90 | RULE | Wyrdstone меняет Casting successes и Miscast Pool; десять Enchanted Items используют Recover, Zone, time clocks, spell profiles и Exacting craft | Добавлен `RULE-MAGIC-ITEM-007`; future item state отделён от fighter state | recorded |
| AUDIT-052 | Gamemaster’s Guide 1.1, 91–93 | RULE/DEFINITION | Minion/Brute/Champion/Monstrosity policies, profile schema и ограничение одной attack обычного NPC совпадают с нормализованными contracts; mounted Monstrosity имеет отдельный выбор attacks | Исправлены ссылки на текущую пагинацию, добавлен `RULE-MOUNT-003`; реализованная injury policy подтверждена | verified |
| AUDIT-053 | Gamemaster’s Guide 1.1, 94–102 | RULE/LORE/GUIDANCE | Диапазон содержит 11 reusable profiles с Help, purchase, social, reinforcement, immediate attack, mount и terrain effects; faction schemes и d10 vendetta — campaign material | Добавлен `RULE-PROFILE-TALABEC-001..011`; profile effects не смешаны с hooks | recorded |
| AUDIT-054 | Gamemaster’s Guide 1.1, 103–109 | RULE/LORE | Восьми profiles нужны forced movement, Zone Hazard/backfire, Help, direct Condition immunity и rider effects; `Paragons` блокирует Broken/Distracted независимо от source classification | Добавлен `RULE-PROFILE-PEOPLES-001..008`; отмечен новый immunity contract, не подменённый undead policy | recorded |
| AUDIT-055 | Gamemaster’s Guide 1.1, 110–125 | RULE/LORE/GUIDANCE | Восемь profiles используют cap-breaking Help, immediate detachment attack, Aim/reload state, chained Charge actions, direct Broken immunity и массовое снятие Conditions | Добавлен `RULE-PROFILE-IMPERIAL-001..008`; faction d10 tables оставлены campaign policy | recorded |
| AUDIT-056 | Gamemaster’s Guide 1.1, 126–133 | RULE/LORE | Четыре Level 2 Wizard profiles имеют одинаковый обмен bonus Casting dice на Miscast dice и round opposition, но разные memorised/grimoire spell sets | Добавлен `RULE-PROFILE-WIZARD-001..004`; ownership отделён от общего casting pipeline | recorded |
| AUDIT-057 | Gamemaster’s Guide 1.1, 134–138 | RULE | Pets могут не иметь turn и быть untargetable, Swarm использует Exacting defeat вместо Wounds, mounts передают только явно названные benefits | Добавлен `RULE-PROFILE-CREATURE-001..010`; нужен отдельный pet/rider/swarm state | recorded |
| AUDIT-058 | Gamemaster’s Guide 1.1, 139–153 | RULE/LORE/GUIDANCE | 10 Beastmen profiles используют Wound-band effects, voluntary Staggered, Charge/Zone/Close Range sweeps, per-target attacks, Wizard state и internal swallowed location | Добавлен `RULE-PROFILE-BEASTMEN-001..010`; подтверждено отсутствие универсального AoE | recorded |
| AUDIT-059 | Gamemaster’s Guide 1.1, 154–164 | RULE/LORE/GUIDANCE | 11 Greenskin profiles различают cap-breaking bonus die, free success, replacement defeat, swarm Exacting progress, vehicle coupling, group-powered Casting и forced group movement | Добавлен `RULE-PROFILE-GREENSKIN-001..011`; faction event table оставлена campaign policy | recorded |
| AUDIT-060 | Gamemaster’s Guide 1.1, 165–174 | RULE/LORE/GUIDANCE | 6 undead profiles используют source immunity, разные replacement repeated-Staggered, Wounds Table modifiers, weaknesses, auras, defeat Hazard и rider-specific Bone Dragon benefits | Добавлен `RULE-PROFILE-UNDEAD-001..006`; существующий undead/Bone Dragon slice подтверждён, полный profile layer отсутствует | recorded |
| AUDIT-061 | Gamemaster’s Guide 1.1, 175–187 | RULE/LORE | 11 monster profiles подтверждают отдельные rider inheritance, flight/landing bands, Reactions, Hazards, random Giant attacks, disguise и regeneration pulse; реализованные K1 slices совпадают с 1.1 | Добавлен `RULE-PROFILE-MONSTER-001..011`; оставшиеся effects явно отмечены draft | recorded |
| AUDIT-062 | Gamemaster’s Guide 1.1, 188–192 | REFERENCE | Index новых mechanics не добавляет; pages 190–191 являются сокращённой reference, а строка Failure содержит очевидно ошибочное `do achieve` | Добавлена закрытая `AMBIGUITY-005`; detailed chapter rules сохраняют приоритет | resolved |

## Итог полного аудита

Все страницы Player’s Guide 1.4 (`1–192`) и Gamemaster’s Guide 1.1 (`1–192`) прочитаны напрямую из текущих PDF и классифицированы. Открытые `draft`, `partially implemented`, `pending implementation` и `recheck_visual` означают пробел реализации/неоднозначность, а не непрочитанный текст.

## Следующий шаг после аудита

Аудит сверен с traceability, roadmap и project status. Следующий минимальный implementation slice — детерминированные эффекты Miscast Table (`11–12`, `31–32`, `35–36`, `39+`) и очистка Miscast Pool после полностью разрешённого эффекта. Пространственные, случайные и GM-choice строки должны пока возвращать отдельные typed follow-up без скрытых defaults.
