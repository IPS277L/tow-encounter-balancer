# План разработки

## R1 — анализ полной книги правил

- проверить редакцию, язык и качество текстового слоя PDF;
- построить карту глав и страниц;
- классифицировать правила, определения, опции, примеры и лор;
- нормализовать правила с идентификаторами и ссылками на страницы;
- выявить противоречия и сравнить книгу с прототипом M1;
- обсудить неоднозначности с пользователем;
- сформировать трассировку `книга → правило → код → тест`;
- пересмотреть архитектуру и roadmap реализации.

R1 охватывает оба основных источника в актуальной локальной редакции `Last Edited: 29th January 2026`.

Статус: завершён. Player’s Guide `1.4` и Gamemaster’s Guide `1.1` прочитаны напрямую по всем страницам `1–192`; диапазоны классифицированы, каталоги правил и профилей созданы, расхождения и пробелы реализации внесены в трассировку. Журнал: `audits/rulebooks-1.4-1.1.md`.

## K1 — книжный resolution kernel

- Characteristic + Skill и готовые NPC-профили;
- Basic/Opposed Tests, модификаторы, Grim/Glorious;
- контекстный выбор Attack и Protection;
- Damage/Resilience;
- Staggered choice policy;
- injury policies для Player/Champion, Minion, Brute и Monstrosity;
- детерминированные тесты с трассировкой к Rule ID.

Готово ядро Test/Opposed/Attack/Staggered/Wound, специализированные эффекты всех строк Wounds Table, заменяющие Damage `ImpactSpec`, Hazard resolver, первые фазовые/multi-target `SecondaryEffectSpec`, Damage плюс Condition, executors выбранных вторичных/Zone Hazard целей, упорядоченные последствия Give Ground, Terrifying и все найденные явно именованные профильные Reactions: Monstrous Flight, Unsteady, Monstrous Regeneration и Undead Monstrosity. Source-classified психологическая иммунность undead-профилей покрывает боевые Condition/Hazard-фазы, `Curse of Cowardly Flight` и `Fascinating Rift`; реализованы Foul Stench, Soporific Breath, Troll Hazards, Stupidity, Stone Troll/Magic Resistance Potency, обе Regeneration-ветви, NPC Wizard opposition через Mother Knows Best, Casting Test accumulation, normal CAST/WAIT с общим `SpellCastRequest`, первый typed spell-schema/Range preflight, target-scoped Potency/execution boundary, stable Zone context batch, movement-completion gate, минимальные Zone graph/placement state, общий Give Ground executor, обе ветви free move, standalone Difficult Terrain traversal и его free-move/base-Run adapters, обе фазы Run, Medium/Long Charge, Move Carefully с optional Awareness search, Move Quietly с conditional hiding, Aim с одноразовым ranged-attack bonus, Help со связанным Test bonus, Recover с тремя закрытыми ветвями, Skill Improvise с basic/opposed Test и одноразовым immunity-aware применением Prone/Distracted к актуальному target state, первый конкретный Ability Improvise Troll Vomit поверх общего Hazard/Wound pipeline, сквозное подключение `Curse of Cowardly Flight`, полный Miscast lifecycle, отдельные reducers для каждой строки таблицы, typed round/side/turn state, базовый action budget, исполнение обычного Attack slot через kernel, normal/triggered spell Improvise pipeline, общий skipped Casting Test для всех non-Casting action receipts и добровольное прекращение Casting. Spatial target discovery, definitions большинства spells, inventory/mount/treatment effects, остальные Ability и attacking Skill Improvise остаются будущему battle loop. Новые конкретные эффекты подключаются фазово без универсального языка правил.

Непосредственно связанные Talents, свойства оружия и классы специальных NPC-правил проверены. Полный каталог конкретных Abilities будет наращиваться по профилям, не меняя фазовый контракт K1.

R1 завершён; round/side/turn state, базовый action budget, обычный Attack adapter, casting pipeline, общий interrupted-Casting consequence, обе ветви free move, standalone Difficult Terrain с free-move/base-Run/Medium-Charge consumers, обе фазы Run, обе дальности Charge, Move Carefully, Move Quietly, Aim, Help, Recover, Skill Improvise с Prone/Distracted application-фазой и Troll Vomit Ability Improvise реализованы. До M2 продолжается K1: следующий срез подключит Zone-wide Troll Hag Swamp Breath отдельным Ability action composite, затем продолжит конкретные Ability/application boundaries.

## P1 — существующий прототип: детерминированный бой 1 на 1

- доменные определения и состояние боя;
- RNG и броски;
- WS/inline attack против DEF;
- урон, RES, stagger, раны и выбывание;
- несколько атак в заданном порядке;
- предел раундов и все исходы;
- структурированные события и детерминированные тесты.

## M2 — составы и действия после анализа книги

- несколько бойцов с обеих сторон;
- контроллеры выбора действия и цели;
- несколько различных целей;
- книжные multi-target и area-эффекты через конкретные профили, Hazards и secondary effects;
- расширенные результаты одного боя.

## M3 — массовая симуляция

- независимые seed для прогонов;
- агрегированные метрики;
- воспроизводимость независимо от параллелизма;
- профилирование и только затем оптимизация.

## M4 — контракты приложения

- JSON Schema и адаптеры;
- application services;
- CLI `simulate`;
- примеры входа и выхода.

## M5 — балансировщик

- ограничения кандидатов;
- конфигурируемые окна сложности;
- этапный поиск и оценка;
- несколько лучших кандидатов.
