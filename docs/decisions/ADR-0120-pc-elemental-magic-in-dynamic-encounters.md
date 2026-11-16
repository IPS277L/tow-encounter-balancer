# ADR-0120: магия PC в динамическом генераторе

Дата: 2026-11-16. Статус: принято пользователем и реализовано. Выбраны два заклинания (Spells), боевые последствия магических ошибок (Miscasts) и одна пригодная рука для сотворения (Casting).

## Проверенные источники

Player’s Guide1.4: гл.III Wizard81/Magic Lores87, IV Tools98–99, V action116–118, VI Memorise Spell135, VIII155–159/Elementalism165. Wizard Talent имеет1–4ранга, запрещён Dwarf/Halfling Origin и требует Magic Lore. Любой Wizard Level с нужной Lore допускает формальное заклинание любого CV; formal CV2 не требует Wizard Level2. Memorisation принимается как факт готового персонажа, downtime не моделируется.

Casting — Exacting Willpower Test, каждый бросок занимает действие; заранее выбирается Lore, spell/target можно выбрать после броска. Potency равна успехам последнего броска, не накопленной сумме. Armour/Shield делают Casting Grim. Девятки не перебрасываются, добавляют Miscast dice; срабатывание только при pool>Wizard Level. Пропуск Casting при активной попытке добавляет die, Recover уменьшает pool на один; активная попытка не исчезает бесплатно. При достаточных успехах перед Miscast можно выпустить spell за дополнительный Miscast die. Последствия Miscast обязательны даже после победного spell.

Правильные Arcane Paraphernalia позволяют проводить Spellcasting Tests без штрафа за makeshift tools, но не дают автоматического бонусного куба. Для memorised spells не требуется открытый grimoire, literacy или придуманное ограничение CV по Level. Книга не задаёт отдельное число свободных/используемых рук для memorised Casting.

## Принятый срез

Одна и та же партия melee PC получает optional факты мага и участвует в существующем поиске/Monte Carlo. Немагические PC не меняются. NPC остаются создаваемыми из компонентов обычными Minions; каталог именных Wizard-NPC не расширяется. Начало — новая сессия, здоровые PC, нулевой Casting/Miscast state, все участники одной Close-сцены.

Вход добавляет Reason/Willpower, Wizard Level, Origin для проверки допуска Wizard, известную Magic Lore и memorised spells, действующие Arcane Paraphernalia. Wizard описывается как настоящий ranked Talent с проверенными prerequisites. Source содержит факты, а не ручные Casting/target/Miscast policies. Первые два spells принадлежат Elementalism:

| Spell | CV / target / range / duration | Полный печатный эффект PG165 |
|---|---|---|
| Lightning Blast | 2 / Creature / Long / Instant | 4+Potency Damage; armoured получает5+Potency |
| Fire Breath | 2 / Zone / Medium / Instant | до Potency foes выбранной Zone, каждому3Damage или4при unarmoured |

Оба эффекта исполняются как прямой Damage, без выдуманного Attack/Protection Test, weapon Traits или hit-only бонусов оружия. Учитываются фактическая броня, Resilience, Staggered/Wound и defeat Minion. Fire Breath выбирает разных врагов, не задевает союзников; это свойство именно данного spell, не общее правило AoE. Общие consumers связываются с типом spell effect, а не с ID бойца.

PC автоматически выбирает Casting, Attack, Help, Recover и допустимые зелья по текущему состоянию. После броска выбирает доступный spell/цели по ожидаемому эффекту; в первом срезе не ждёт дополнительной Potency при уже полезном доступном cast. Накопление, прерывание, обязательные последствия, фактический Fate/Rule of Nine сохраняются; extra Second Action, Mixing the Winds, Dispelling/opposition, импровизация и чтение grimoire вне границы. Отказ от Mixing/ожидания — добровольная тактика, не запрет книги. Выбор не читает будущие броски и не запускает вложенные Monte Carlo-бои.

## Покрытие магических ошибок (Miscasts)

Принятый вариант исполняет последствия, выражаемые нынешним общим боем: Staggered, следующий Test−1d, daylight blindness/другие конкретно напечатанные Test modifiers, Prone всем затронутым, прямую/fixed Wound и смерть. Немеханические для текущего боя проявления сохраняются как фактические эффекты без придуманных штрафов. Для Arcane Spill выбирается малое проявление Elementalism без дополнительного урона/изменения terrain; дневное освещение и отсутствие пригодного выхода для Give Ground задаются явно. Это GM/scenario-конкретизация, не скрытая настройка бросков.

Реализованный набор строк:1–4,7–16,19–22,25–32,35–36,39+. Для5–6 (выбор изменяемых предметов),17–18 (другая Zone),23–24 (GM target повторного spell),33–34 (новый Hazard),37–38 (Daemon/rift) сохраняются настоящий roll, entry и source prefix, затем точный `UNSUPPORTED_PATH` перед неисполняемым продолжением. Эти эффекты не превращаются в no-op и не перебрасываются.

Важное ограничение: действующий search исключает кандидат с любым observed unsupported. Поэтому магия пока может уменьшать число рекомендованных составов или давать пустой selected. Нельзя считать такие остановки победами, убирать из знаменателя или подменять их средним исходом. Альтернатива с остановкой при любом triggered Miscast отклонена: она существенно сильнее ограничивала бы подбор.

Полная поддержка пространственных последствий, произвольных GM-сущностей и всех spells не требуется для первого исполнимого пути, но остаётся отдельным ограничением продукта. Если на реальных партиях выбранная граница не даёт практически полезных результатов на характерных входах, её нужно расширить либо пересмотреть, а не объявлять генератор магии завершённым.

## Принятое использование руки

Пользователь выбрал GM/scenario policy: memorised Casting использует одну пригодную руку, здоровая выбирается первой; занятую оружием не нужно отдельно освобождать, Shield/Armour по книге дают Grim. Если используется Injured Hand12, применяется настоящий Critical; при отсутствии пригодной руки выбираются другие разрешённые действия, а Casting не производится. Это отдельная согласованная трактовка неописанного hand-count.

Альтернатива — не вводить требования руки для memorised Casting, поскольку отдельный hand-count в книге не напечатан. Тогда сам Casting не является доказательством использования конкретной травмированной руки. Эта альтернатива не выбрана.

## Реализация и адресная проверка

Reuse существующих Casting/Rule-of-Nine/decision/Miscast/target-scoped Potency и Damage/Conditions/Wound consumers; новый native PC owner связывает их с реальным общим clock и полным source. Магические Conditions сохраняют независимые причины, в том числе при лечении раны зельем. Recover использует настоящий WizardMagicState; skip-Casting die и reduction не теряются и применяются в определённом порядке.

Текущие PC/Dynamic JSON1 дополняются facts, spell/magic receipts и фактическими Casting/spell/Miscast observations; без ручного ввода накоплений/расхода или compatibility-версий. UI получает только поля фактов персонажа, включая активацию Reason/Willpower и выбор известных spells/предмета, без нового tactical editor.

Проверка: CV2 на Wizard Level1; actual accumulation/last-roll Potency, target-specific armour Damage и разные Fire Breath targets; Grim/Glorious и locked9/Fate; interruption/Recover/potion interactions; typed Miscast roll→effect→cleanup и точные неподдержанные строки; actual PC Wounds/death без пропуска pending; proof forgery и однократность; свежие независимые trials/агрегаты/current replay/один process parity; динамическая генерация и существующий UI. Перед широким subsystem/full прогоном назвать основание по реально изменённому общему Test/Recover/clock kernel. Wheel без изменения доставки не нужен.

Исполнение: `pc_magic_source_models` хранит проверенные факты и полные определения заклинаний; `pc_magic_miscast_plan` — закрытый типизированный порядок эффектов. `pc_magic_models` связывает реальные Casting/Fate/Rule of Nine, spell preflight, прямой Damage, раны (Wounds), Miscast roll и cleanup с общим PC clock. Projection повторно проверяет полные proofs по текущему source; replay не делает новых случайных бросков. Независимые причины Conditions сохраняются при лечении и истечении других источников. Смерть активного мага завершает уже начатый ход без нового действия/проверки.

В current PC/Dynamic JSON1 поле `magic_counts` присутствует только при Wizard source, содержит всех магов в source order, включая нули; счётчики Casting actions, spell casts, Miscasts и неподдержанных Miscasts раздельны. Spell/Miscast effect не является дополнительным действием. Автоматический NPC envelope учитывает ожидаемую силу Lightning Blast; ручные диапазоны остаются приоритетными. [Исполняемый пример и вход](../examples/dynamic/README.md#магия-персонажей), [фактическая последняя проверка](../project-status.md#текущий-срез-магия-персонажей-в-генераторе).
