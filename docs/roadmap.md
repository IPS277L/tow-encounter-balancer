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

Готово ядро Test/Opposed/Attack/Staggered/Wound, специализированные эффекты всех строк Wounds Table, заменяющие Damage `ImpactSpec`, Hazard resolver, первые фазовые/multi-target `SecondaryEffectSpec`, Damage плюс Condition, executors выбранных вторичных/Zone Hazard целей, упорядоченные последствия Give Ground, Terrifying и все найденные явно именованные профильные Reactions: Monstrous Flight, Unsteady, Monstrous Regeneration и Undead Monstrosity. Source-classified психологическая иммунность undead-профилей покрывает боевые Condition/Hazard-фазы, `Curse of Cowardly Flight` и `Fascinating Rift`; реализованы Foul Stench, Soporific Breath, Troll Hazards, Stupidity, Stone Troll/Magic Resistance Potency, обе Regeneration-ветви, NPC Wizard opposition через Mother Knows Best, Casting Test accumulation, общий Exacting Basic/Opposed-contribution progress, weapon-bound Reload и ranged-shot transition, normal CAST/WAIT с общим `SpellCastRequest`, первый typed spell-schema/Range preflight, target-scoped Potency/execution boundary, stable Zone context batch, movement-completion gate, минимальные Zone graph/placement state, общий Give Ground executor, обе ветви free move, standalone Difficult Terrain traversal и его free-move/base-Run adapters, обе фазы Run, Medium/Long Charge, Move Carefully с optional Awareness search, Move Quietly с conditional hiding и одноразовым hidden Attack/loss follow-up, Aim с одноразовым ranged-attack bonus, Help со связанным Test bonus, Recover с тремя закрытыми ветвями, одноразовым применением успешного treatment, automatic end-battle treatment всех ран, source-aware `CATCH_YOUR_BREATH`, `A Night’s Respite`, `Rest and Recovery`, отдельный Festering Wound state/recovery consumer, daily Wound tracking и обе ветви end-of-day Infection, ordinary surgery proof, обе Combat Surgeon boundaries, suppression aggregate/effective view, полная `Drained` Test preparation с исключением Fate, session Fate resource с Glorious spend до/после initial roll, атомарными Second Action и Tactical Retreat spends, typed group Retreat, оба proof-bearing cover path, все три alternative-price consumers, pursuit с ordered Athletics/Lore/opposition/failure/Complication facts, Run For Your Lives rolls/aggregate, outcome-bound campaign registration, `Robbed` inventory batch, `Surrounded` conflict-opportunity hook, `Hunted` threat/activation aggregate, `Marked` enemy-readiness/activation aggregate, `Indebted` debt aggregate, `Mocked` reputation aggregate, `Lost` delay aggregate, `Exposed` intelligence aggregate, `Trapped` cost routing, последовательное применение его Wounds branch, active-captivity aggregate Capture branch и opaque Other-cost aggregate, а также battle-proof healing bridge, Skill Improvise с basic/opposed Test и одноразовым immunity-aware применением Prone/Distracted к актуальному target state, конкретные Ability Improvise Troll Vomit, Troll Hag Swamp Breath и Forest Dragon Soporific Breath поверх общего Hazard/Wound pipeline, сквозное подключение `Curse of Cowardly Flight`, полный Miscast lifecycle, отдельные reducers для каждой строки таблицы, typed round/side/turn state, базовый action budget, исполнение обычного Attack slot через kernel, normal/triggered spell Improvise pipeline, общий skipped Casting Test для всех non-Casting action receipts и добровольное прекращение Casting. Все девять Run For Your Lives outcomes имеют первоначальную typed boundary. Spatial target discovery, definitions большинства spells, полные inventory/mount effects, исполнение golden opportunity и Surrounded/Hunted/Marked/Exposed/Lost hooks, погашение Indebted, social execution Mocked, исполнение конкретной Other-цены/captivity-aftermath эффекты `Trapped`, остальные Condition/effective-view modifiers и surgery-failure follow-up, прочие Ability и attacking Skill Improvise остаются будущему battle loop. Новые конкретные эффекты подключаются фазово без универсального языка правил.

Непосредственно связанные Talents, свойства оружия и классы специальных NPC-правил проверены. Полный каталог конкретных Abilities будет наращиваться по профилям, не меняя фазовый контракт K1.

R1 завершён; round/side/turn state, базовый action budget, обычный и Move-Quietly-hidden Attack adapters, casting pipeline, общий interrupted-Casting consequence, общий Exacting Basic/Opposed progress, полный combat/reload catalog страницы 95 и typed ranged Attack preparation, weapon-bound Reload, единый/hidden/Aim-bound profile-aware ranged Attack для free/reloadable states, обе ветви free move, standalone Difficult Terrain с free-move/base-Run/Medium-Charge consumers, обе фазы Run, обе дальности Charge, Move Carefully, Move Quietly, Aim, Help, Recover вместе с healing/infection/surgery boundaries, session Fate, Retreat/Run For Your Lives campaign boundaries, Skill Improvise и выбранные Ability Improvise реализованы. До M2 продолжается K1: prepared executor с direct/Aim-bound ветвями, одним kernel/receipt и полным preparation trace завершён. Explicit close-enemy preflight подготовки завершён: обязательный bool запрещает оружие без Close в Optimum при любом враге в Close, независимо от выбранной цели. Prepared+hidden composition завершена с одним исполнением и сохранением hidden/Aim consumption chains. Non-Attack continuation с `PRESERVED`/`LOST` и последовательность Move Quietly → Aim → Attack реализованы (`CODE-CONFLICT-001` закрыт). Регистрация раскрытых hiding positions и передача actor-scoped истории следующей Move Quietly реализованы. Атомарная композиция hidden execution и регистрации с проверкой истории до RNG завершена. Проверка хронологии hidden Attack по round/slot завершена. Привязка same-round Attack snapshot к точному completed slot/receipt Move Quietly завершена. Минимальное actor-scoped состояние hidden lifecycle и его continuation/registered Attack adapters завершены. Standalone hidden loss consumer подключён к lifecycle state. Атомарный Move Quietly → lifecycle adapter для inactive state завершён для всех outcomes. Source-bound потеря hidden opportunity после завершённого free movement владельца из укрытия завершена без фиктивного action receipt и регистрации укрытия. Атомарный free-movement executor поверх existing movement и loss consumer завершён. Consumer completed Give Ground владельца завершён с exact post-hiding snapshot для same-round provenance. Атомарный Give Ground executor завершён с тем же preflight и единственным movement/Condition результатом. Same-round provenance через узкую цепочку completed free-movement/Give Ground других actor завершён. Сквозная проверка Move Quietly → чужое движение → Give Ground/Broken → безопасная Zone/Recover → новая Move Quietly → Aim/prepared Attack завершена. Следующий срез — продолжение сценария через weapon-bound Crossbow Reload и второй hidden shot из нового укрытия; порядок этапов не меняется.

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
