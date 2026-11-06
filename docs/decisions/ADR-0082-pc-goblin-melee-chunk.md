# ADR-0082: ближний чанк гоблинов и поражение без раны

Дата: 2026-11-05. Статус: **принято**. Пользователь выбрал три melee-профиля; Weighted Net отложена.

## Задача и источники

После M30 рассмотрены Goblin Warrior, Nasty Skulker и Night Goblin. Это не только данные: Dirty Coward задаёт поражение без раны, Backstabba меняет урон unopposed атаки, а Jagged Spear и щиты расширяют прежнюю публичную границу Close-only/noShield.

Нормативные источники: BOOK-GM-GUIDE1.1, Allies and Antagonists / NPCs91 / Profiles93 / Goblin Warrior156 / Nasty Skulker и Night Goblins157; BOOK-PLAYER-GUIDE1.4, Skills / Defence68, Equipment / Melee Weapons92 / Throwing Weapons96 / Armour97, Rules / Opposing an Attack и Recover118 / Staggered119 / Conditions123. Чтение адресное, не полное перечитывание книг. Лор и сюжет Burz Klinkclaw не используются как правила.

## Согласованная граница M31

Законченный чанк из трёх fixed melee loadouts в существующей неподвижной aware Close-сцене:

| Loadout | Атака | Protection | Resilience / тип |
|---|---|---|---|
| Goblin Warrior / Jagged Spear + shield | Close–Short maximum,2d/3 Damage3,1H | Athletics3d/2 | printed5 armoured,T3,Normal Minion |
| Nasty Skulker / Long knives | Close4d/4 Damage3,1H | Defence4d/4 | printed4 armoured,T3,Normal Minion |
| Night Goblin / Jagged Spear + shield | Close–Short maximum,2d/3 Damage3,1H | Athletics3d/2 | variant printed4 armoured,T3,Normal Minion |

В таблице Close–Short для Spear означает **все расстояния до напечатанного Short**, а не Throwing optimum. Бой остаётся в Close; дальняя атака, перемещение и spatial AI не добавляются. Shortbow Warrior, Weighted Net/Shortbow Night Goblin и Athletics3d/3 Skulker сохраняются unselected.

Night Goblin наследует правила Warrior с Initiative3 и явной заменой Resilience5→4. Щит сохраняется, дополнительный +1 поверх printed4 не начисляется. Бонус между Toughness3 и итогом4 хранится агрегированно; не восстанавливать поверх карточки ещё одну light armour из Typical Trappings. NoShield Night variant не входит в срез: он потребовал бы отдельно учитывать printed armoured при Resilience=Toughness. Оба shield loadouts должны передавать настоящий holds_shield в Protection, не только увеличенную Resilience.

## Dirty Coward

У Warrior и наследующего Night Goblin уже Staggered цель, которая получает ещё один Staggered, автоматически defeated, бросает оружие и бежит. Это **не Wound**, не выбор killed/knocked_out/surrendered и не соседний Broken exit M24. Нельзя использовать прежний SUFFER_WOUND, затем переименовать результат в бегство.

Реализация использует отдельные MinionStaggerDefeatSpec/Cause/Result: фактический kernel resolution ID, target и Rule ID связывают результат с повторным Staggered. ProfileInjuryState получает nullable defeat_cause; прежний инвариант defeated по Wound limit сохраняется для None. Только явная типизированная причина разрешает defeated Minion при0Wounds/limit1. K1 возвращает причину в mandatory follow-ups без обычного Staggered выбора и без RNG, Profile Wound или GM disposition.

PC независимо восстанавливает canonical результат, применяет PcMinionStaggerDefeatProof один раз, снимает wields_weapon/available attacks, сохраняя shield, и исключает NPC из ходов. До ACK он уже defeated, но оружие ещё не сброшено; очередь обязательна до обычного продолжения. Source bank связывает изменение оборудования с actual Attack/причиной/ACK, отвергая произвольный drop или пропуск причины. Обычный быстрый путь для сцен без Dirty Coward не сканирует историю ради такого банка. Generic Condition/Hazard projections сохраняют причину; перенос Minion cause в другую injury policy запрещён.

Это defeated для существующей цели сценария, без фиктивной раны, Broken, pathfinding, смены зоны, exit counter или GM выбора, которого книга здесь не даёт. Поражение как причина бегства не смешивается с безопасным выходом живого Broken Official.

Прямой damaging Wound по Minion сохраняет обычный результат и caller-owned disposition. Промах уже Staggered атакующего не накладывает новый Staggered и Dirty Coward не вызывает. Nasty Skulker эту способность не наследует.

## Backstabba и остальные способности

Skulker при настоящей **unopposed Melee attack** получает дополнительный +1 Damage за success, всего коэффициент2. Opposed Test против0successes остаётся opposed, бонуса нет. Defenceless PC не может Oppose, поэтому этот trigger возможен после тяжёлых ран даже при aware initial scene. Применить коэффициент только к соответствующей фактической атаке, сохранить printed base3 и не превратить его в дополнительные Wounds против Defenceless.

Skulking Menace разрешает Stealth исчезновение без cover при наличии5других Goblins в Zone; существующая fixed NPC Attack strategy не выбирает это действие. Horde Warrior/Night Goblin даёт Help attack без Test с+1d сверх обычного bonus cap; NPC Help здесь не выбирается. Полные условия сохраняются в metadata. PC Attack/standard Recover/Fate policies не меняются.

## Публичная граница

Текущий PC JSON1 расширяется на поддержанные shield snapshots и melee maximum Short. Required enemy.holds_shield:boolean и definition.attack.range_max:close|short передаются явно. Range minimum Close и Skill.MELEE остаются константами family. Parser не выводит shield/range из имени карточки; canonical admission связывает их с full book definition/loadout. Shield с2H/natural атакой не допускается.

88прежних JSON documents получают только holds_shield:false/range_max:close во всех input/echo/template/candidate sources. Остальные значения/наблюдения и19старых loadouts сохранены. Wire version1/метрики/команды прежние, compatibility ветвей нет. Новая runtime defeat_cause не является состоянием для загрузки из JSON: публичный source по-прежнему fresh/healthy.

Backstabba меняет success_multiplier с1 на2 только для соответствующего фактического unopposed AttackRequest; printed source DamageProfile3/1 прежний. Canonical replay проверяет подготовленный request и arithmetic, а не доверяет наблюдённому Damage. Новый универсальный язык Ability или event bus не вводится.

## Альтернатива: сначала Weighted Net

Это самостоятельная функция, а не ещё один secondary ConditionOnHitSpec. GM157 / PG96 задают Throwing2d/3,2H и Burdened **вместо Damage**. Нужны primary ConditionImpactSpec, настоящий Throwing preparation, source lifetime, запас сетей и однократное расходование/фактический pickup или смена оружия. Из карточки нельзя вывести бесконечные сети.

PG123 снимает Burdened через Brawn Test либо удаление груза; Recover118 для такого Test альтернативен стандартным преимуществам. Новая стратегия автоматически не подставляется. Взаимодействие non-damaging Net с общим Defenceless «successful attack → Wound instead» отдельно уточняется перед реализацией: текущая ветка K1 только для DamageImpactSpec не является нормативным ответом.

## Адресная приёмка

1. Printed profiles/источники/полная metadata, shield и максимальная melee range; запрет canonical подмен и source aliases до RNG.
2. Dirty Coward на настоящем повторном Staggered, отсутствие раны/GM подмены/двойного применения, direct Wound и промах уже Staggered атакующего; native order/исключение участника/full replay.
3. Backstabba opposed0 против unopposed и Defenceless, отдельный Damage coefficient без дополнительных Wounds; остальные NPC без бонуса.
4. Factory → native → trials/count search → current JSON1/CLI, полное source echo и source-ordered агрегаты; прежние примеры/19loadouts неизменны.
5. Ближайшие K1/PC зависимости по фактически изменённым слоям. При изменении общего K1 defeat/stagger пути — соответствующая контрольная проверка подсистемы с названным объёмом. Wheel и полная process-матрица без изменения их механизма не нужны.

## Результат приёмки M31

2026-11-05:38новых tests (15K1/7catalog/10native/6integration) пройдены. Контроль PC M9–M31 и связанных K1 правил:89модулей/723tests,23старых process/spawn/console-matrix cases исключены. Фактический запуск `.venv/Scripts/python.exe .cache/m31_check_pc_kernel.py` при PYTHONPATH=src дал721OK/2failures/0errors за94.672s. Оба failures — M9 assertions прежнего запрета любого shield и Melee Short. После приведения тестов к согласованной границе весь18-test модуль и новый shield/hands/Short test прошли:19OK/0.032s. Итого724уникальные проверки составно, не единый зелёный full regression. Production для этих исправлений не менялся, дорогой прогон не повторялся.

46current PC request/result pairs, полные echo,88прежнихJSON values после false/close migration и19старыхcatalog entries/definitions/snapshots/metadata проверены. Оба новых requests исполнены sequential CLI; результаты сохранены в [примерах M31](../examples/m31/README.md). Full проекта/wheel/старая process-матрица не запускались. Предыдущие локальные .cache helpers/logs не являются частью репозитория.
