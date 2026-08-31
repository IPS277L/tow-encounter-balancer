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

Готово ядро Test/Opposed/Attack/Staggered/Wound, специализированные эффекты всех строк Wounds Table, заменяющие Damage `ImpactSpec`, Hazard resolver, первые фазовые/multi-target `SecondaryEffectSpec`, Damage плюс Condition, executors выбранных вторичных/Zone Hazard целей, упорядоченные последствия Give Ground, Terrifying и все найденные явно именованные профильные Reactions: Monstrous Flight, Unsteady, Monstrous Regeneration и Undead Monstrosity. Source-classified психологическая иммунность undead-профилей покрывает боевые Condition/Hazard-фазы, `Curse of Cowardly Flight` и `Fascinating Rift`; реализованы Foul Stench, Soporific Breath, Troll Hazards, Stupidity, Stone Troll/Magic Resistance Potency, обе Regeneration-ветви, NPC Wizard opposition через Mother Knows Best, Casting Test accumulation, общий Exacting Basic-contribution progress, normal CAST/WAIT с общим `SpellCastRequest`, первый typed spell-schema/Range preflight, target-scoped Potency/execution boundary, stable Zone context batch, movement-completion gate, минимальные Zone graph/placement state, общий Give Ground executor, обе ветви free move, standalone Difficult Terrain traversal и его free-move/base-Run adapters, обе фазы Run, Medium/Long Charge, Move Carefully с optional Awareness search, Move Quietly с conditional hiding и одноразовым hidden Attack/loss follow-up, Aim с одноразовым ranged-attack bonus, Help со связанным Test bonus, Recover с тремя закрытыми ветвями, одноразовым применением успешного treatment, automatic end-battle treatment всех ран, source-aware `CATCH_YOUR_BREATH`, `A Night’s Respite`, `Rest and Recovery`, отдельный Festering Wound state/recovery consumer, daily Wound tracking и обе ветви end-of-day Infection, ordinary surgery proof, обе Combat Surgeon boundaries, suppression aggregate/effective view, полная `Drained` Test preparation с исключением Fate, session Fate resource с Glorious spend до/после initial roll, атомарными Second Action и Tactical Retreat spends, typed group Retreat, оба proof-bearing cover path, все три alternative-price consumers, pursuit с ordered Athletics/Lore/opposition/failure/Complication facts, Run For Your Lives rolls/aggregate, outcome-bound campaign registration, `Robbed` inventory batch, `Surrounded` conflict-opportunity hook, `Hunted` threat/activation aggregate, `Marked` enemy-readiness/activation aggregate, `Exposed` intelligence aggregate, `Trapped` cost routing, последовательное применение его Wounds branch и active-captivity aggregate Capture branch, а также battle-proof healing bridge, Skill Improvise с basic/opposed Test и одноразовым immunity-aware применением Prone/Distracted к актуальному target state, конкретные Ability Improvise Troll Vomit, Troll Hag Swamp Breath и Forest Dragon Soporific Breath поверх общего Hazard/Wound pipeline, сквозное подключение `Curse of Cowardly Flight`, полный Miscast lifecycle, отдельные reducers для каждой строки таблицы, typed round/side/turn state, базовый action budget, исполнение обычного Attack slot через kernel, normal/triggered spell Improvise pipeline, общий skipped Casting Test для всех non-Casting action receipts и добровольное прекращение Casting. Spatial target discovery, definitions большинства spells, полные inventory/mount effects, исполнение golden opportunity и Surrounded/Hunted/Marked/Exposed hooks, Other/captivity-aftermath эффекты `Trapped` и специализированные эффекты остальных трёх Run For Your Lives outcomes, остальные Condition/effective-view modifiers и surgery-failure follow-up, прочие Ability и attacking Skill Improvise остаются будущему battle loop. Новые конкретные эффекты подключаются фазово без универсального языка правил.

Непосредственно связанные Talents, свойства оружия и классы специальных NPC-правил проверены. Полный каталог конкретных Abilities будет наращиваться по профилям, не меняя фазовый контракт K1.

R1 завершён; round/side/turn state, базовый action budget, обычный и Move-Quietly-hidden Attack adapters, casting pipeline, общий interrupted-Casting consequence, общий Exacting Basic progress, обе ветви free move, standalone Difficult Terrain с free-move/base-Run/Medium-Charge consumers, обе фазы Run, обе дальности Charge, Move Carefully, Move Quietly, Aim, Help, Recover вместе с successful-treatment application, automatic end-battle treatment, независимым end-encounter `CATCH_YOUR_BREATH`, `A Night’s Respite`, успешным `REST_AND_RECOVERY`, persistent Festering Wound state/recovery consumer, day-scoped Wound receipts, Endurance и Anatomy-proof ветви end-of-day Infection, ordinary и Combat Surgeon surgery healing строк `20–23`, обе Combat Surgeon boundaries вместе с suppression aggregate/effective view, полная `Drained` Test preparation, session Fate state, обе части Lucky, GM refresh, Glorious consumer до/после initial roll, proof-bound Second Action/Tactical Retreat, permanent burn и application consumers всех трёх видов, rolled и fixed two-phase Wound lifecycles вместе с kernel/Stagger/Hazard/Internal Damage/Ears Ringing adapters, alternative-price proof и все три его application consumers, общий pursuit, Run For Your Lives aggregate, campaign registration, `Robbed` inventory boundary, `Surrounded` conflict-opportunity hook, `Hunted` threat/activation aggregate, `Marked` enemy-readiness/activation aggregate, `Exposed` intelligence aggregate, `Trapped` cost routing, Wounds sequencer и Capture active-captivity consumer, Skill Improvise с Prone/Distracted application-фазой и Ability Improvise Troll Vomit/Swamp Breath/Soporific Breath реализованы. До M2 продолжается K1: следующий срез — outcome `Indebted` как typed campaign-debt aggregate с explicit rescuer/creditor, debt и repayment references, без автоматического выбора цены или услуги; прочие heterogeneous последствия сохраняют отдельные boundaries.

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
