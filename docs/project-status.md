# Текущий статус проекта

Дата обновления: 2026-08-19.

## Текущий этап

K1 — реализация книжного resolution kernel. Прототип P1 (`1 на 1`) сохранён как исследовательская реализация, но больше не является нормативной основой.

## Зафиксировано

- прочитан исходный дизайн-док;
- уточнены правила промаха, диапазона кубов, ничьей, выбора целей и лимита раундов;
- определены архитектурные границы и порядок будущих этапов;
- создан протокол передачи контекста между сессиями;
- разделены неизменяемые определения бойцов и изменяемое состояние боя;
- реализованы stat/inline источники броска, d10, встречная проверка, damage/RES, два режима stagger, раны и выбывание;
- реализованы фазы игроков и монстров, заданный порядок нескольких атак, стабильный выбор цели, ничья и предел раундов;
- добавлены внедряемый RNG и отключаемый структурированный журнал событий;
- старый прототипный алгоритм AoE явно отменён и удалён из целевой документации;
- установлено, что Player’s Guide и Gamemaster’s Guide имеют приоритет над дизайн-доком, документацией, кодом и тестами прототипа;
- создана структура для индекса источника, нормализованных правил, лора, противоречий и трассировки.
- создано приватное постраничное извлечение всех 191 страниц;
- прочитаны и первично нормализованы базовые проверки, бой, атаки, Resilience, Wounds и Conditions;
- выявлены ключевые расхождения книги с P1 и добавлена начальная трассировка правил.
- добавлен и полностью извлечён Gamemaster’s Guide;
- нормализованы базовые типы NPC, формат профиля, особенности Monstrosity и книжные ориентиры encounter design;
- пользователь подтвердил удаление временного AoE и подход resolution-kernel-first;
- принято ADR-0002 о замене P1 через книжный resolution kernel.
- проверены боевые Talents, свойства обычного оружия и репрезентативные специальные NPC-правила;
- зафиксированы классы специальных эффектов и точный фазовый контракт K1.
- реализованы новые неизменяемые `TestProfile`, `InlineProfile`, `TestRequest` и модификаторы K1;
- реализованы книжные Basic/Opposed Tests, Grim/Glorious, contextual tie-break и детальный `RollTrace`;
- добровольные Glorious-перебросы вынесены в явный `TestDecisionProvider`;
- найдено и исправлено в K1 расхождение P1 по естественному пулу из одного куба.
- реализован чистый resolver одной opposed/unopposed атаки;
- реализованы книжные attack tie, Damage по разнице успехов, Resilience, игнорирование брони и последствия промаха в Close Range;
- Attack resolver возвращает обычный `ImpactOutcome` без преждевременной мутации боевого состояния.
- реализованы неизменяемое множество Conditions и чистый reducer Staggered;
- повторный Staggered учитывает Prone, доступность Give Ground и лимит одного Give Ground за раунд;
- выбор Give Ground/Prone/Wound вынесен в явный `StaggerDecisionProvider`, а единственный допустимый Wound выбирается автоматически.
- реализована полная карта Wounds Table `1–27+`, записи исходных d10 и untreated Wounds;
- реализованы Player/Champion, Minion, Brute и Monstrosity injury policies;
- реализована отмена Wound после броска, включая правильное сохранение Staggered при Near Miss;
- реализован владелец выбора Wound/Reaction для обоих случаев Damage по Monstrosity;
- правило Monstrosity о неудачной Melee-атаке добавлено как явное трассируемое исключение;
- создан единый `KernelAttackRequest → ResolutionResult`, возвращающий новое состояние цели и типизированные follow-up.
- реализованы спецификации уникальных эффектов всех строк Wounds Table `1–27+`;
- Conditions и ограничения раны сохраняют номер источника и точный срок действия;
- kernel применяет непосредственный `WoundEffectResult`, а Endurance, инвентарь, анатомия и обязательный выбор возвращаются типизированными запросами;
- реализованы успешная/неуспешная ветви Endurance и обе ветви `Spilling guts` без скрытых решений.
- добавлен полный книжный enum из 16 Skills для типизированных ссылок правил;
- обычный Damage, Condition вместо Damage и Hazard вместо Damage разделены вариантами `ImpactSpec`;
- replacement impact не требует фиктивных Damage/Resilience и не применяется при промахе;
- прямой Staggered использует общую repeated-Stagger policy, а Hazard создаёт `HazardExposureRequest` с рейтингом и Skill.
- реализован `HazardResolutionRequest → HazardResolutionResult` с проверкой принадлежности `TestResult`;
- shortfall Hazard задаёт базовое число кубов Wounds Table либо профильных Wounds, отдельно от untreated/modifier effects;
- поддержаны Wound-only, Condition-only и Wound+Condition Hazards для всех четырёх injury policies;
- Near Miss отменяет Wound от Hazard, но не отменяет его независимые failure Conditions.
- добавлен закрытый `SecondaryEffectSpec` с первыми фазовыми и multi-target вариантами;
- `ProneBeforeGiveGroundSpec` применяется до repeated-Staggered decision и поддерживает книжное исключение Monstrosity;
- эффект Blunderbuss создаёт `NearbyTargetsStaggerRequest` только при попадании и после результата основной цели;
- применённые secondary Rule ID сохраняются в `ResolutionResult`.
- выделен общий `StaggerImpactRequest → StaggerImpactResult`, используемый основной и вторичными целями;
- реализован `NearbyTargetsStaggerResolutionRequest` с запретом основной/повторных целей и уникальными impact IDs;
- executor обрабатывает вторичные цели слева направо, сохраняя target IDs, общий RNG и явные решения;
- вторичные цели проходят Player/Champion либо профильную NPC injury policy, включая Near Miss и Wound effects.
- добавлен `ConditionAfterGiveGroundSpec` для Troublemakers Out!/Fearsome;
- общий Stagger impact ставит Condition follow-up строго после `GiveGroundRequest` и только при выборе Give Ground;
- `resolve_condition_after_give_ground` применяет отложенное Condition без преждевременного изменения состояния;
- after-Give-Ground эффекты работают для основной и явно выбранных вторичных целей.
- добавлен `ConditionOnHitSpec`, допустимый только с обычным `DamageImpactSpec`;
- Damage, Staggered/Wound и injury policy завершаются до применения on-hit Condition;
- Near Miss отменяет Wound, но не дополнительный Condition успешного попадания;
- фазовый trace сохраняет порядок on-hit Condition до отложенных Give Ground/secondary-target follow-ups.
- добавлен `ConditionOnGiveGroundOrWoundSpec` для Terrifying у Dragon/Wyvern;
- Broken ставится после принятой Wound либо откладывается строго после `GiveGroundRequest`;
- Near Miss, первый Staggered и альтернативный repeated-Staggered исход Terrifying не запускают;
- тот же условный эффект работает в общем Stagger impact для профильной вторичной цели.
- `KernelAttackRequest` теперь принимает типизированный `MonstrosityReactionSpec`, а не исполняемую строку Rule ID;
- реализованы `MonstrosityReactionRequest → MonstrosityReactionResolutionResult` и первый конкретный `MonstrousFlightReactionSpec` для Griffon/Dragon/Wyvern;
- Monstrous Flight возвращает Give Ground с предпочтением vertical midair либо профильную Wound, если Monstrosity уже давала Ground в текущем ходу;
- дополнительные профильные Wounds и Terrifying проходят через результат Reaction с сохранением Rule ID;
- невозможный Give Ground зафиксирован как книжная неоднозначность без скрытого default.
- добавлен `UnsteadyReactionSpec` для Giant и исходы `FALL_PRONE`/`ALREADY_PRONE`;
- новое падение Giant накладывает Prone, сохраняет Staggered и создаёт `ReactorZoneHazardRequest` с Athletics Hazard (3);
- запрос Zone Hazard явно включает самого Giant и всех остальных существ в его Zone, но не выполняет spatial-выбор;
- уже Prone Giant не создаёт Hazard повторно, а Terrifying не реагирует на исход Unsteady.
- добавлен `MonstrousRegenerationReactionSpec` для Ghorgon/Troll Hag и исход `REGENERATION_SUPPRESSED`;
- Reaction сохраняет injury state и создаёт один `SuppressRegenerationNextTurnRequest` с Rule ID источника;
- добровольное end-turn лечение, огненный источник Wound и однократное потребление suppression оставлены будущему turn orchestration;
- Terrifying не реагирует на suppression, поскольку Give Ground/Wound не произошли.
- добавлены `UndeadMonstrosityReactionSpec` и отдельный mounted context для Bone Dragon;
- без всадника Reaction детерминированно наносит профильную Wound, включая дополнительные профильные Wounds и Terrifying;
- Liche/Tomb King открывает внешний выбор владельца `MONSTROSITY` между доступными Wound, Give Ground и Prone;
- resolver заранее исключает Give Ground после уже выполненного в раунде перемещения, при невозможном перемещении или Prone и исключает повторное падение Prone;
- общий request теперь принимает закрытый union профильных Reaction contexts вместо необязательных Give Ground флагов.
- реализован `ReactorZoneHazardResolutionRequest` для уже выбранного стабильного порядка существ в Zone;
- batch обязан включать реагирующего и отклоняет повторные target IDs и Test request IDs;
- `resolve_reactor_zone_hazard` слева направо проводит каждую цель через общие Test/Hazard resolvers на одном RNG;
- результат каждой Zone-цели сохраняет exposure, полный Test trace, собственный injury state и Hazard result;
- Test/Wound decision providers, Near Miss, четыре injury policy и failure Conditions переиспользуются без отдельной area-логики.
- добавлены `EffectClassification.PSYCHOLOGICAL` и source-aware `EffectImmunity` для undead-профилей страниц 166–172;
- реализован общий `ConditionApplicationRequest → ConditionApplicationResult`, сохраняющий source Rule ID и blocking immunity Rule ID;
- неклассифицированные эффекты не считаются психологическими по значению Condition;
- `ConditionImpactSpec` передаёт классификацию, а `KernelAttackRequest` — иммунитеты цели;
- Bone Dragon блокирует психологический replacement Condition до прямого или Staggered reducer;
- остальные secondary/Hazard/non-Condition пути пока намеренно не считают подключёнными к иммунитету.
- психологическая классификация добавлена в `ConditionOnHitSpec`, `ConditionOnGiveGroundOrWoundSpec` и `ConditionAfterGiveGroundSpec`;
- непосредственные secondary Conditions используют общий resolver и сохраняют `condition_applications` в resolution result;
- after-Give-Ground follow-up переносит classification и immunity snapshot через границу движения;
- Stagger impact и Monstrosity Reaction сохраняют блокировки outcome Conditions без отмены Give Ground или Wound;
- Fearsome/Terrifying с явной психологической классификацией не накладывают Broken на undead-профиль.
- общий `EffectApplicationRequest → EffectApplicationResult` выделен как source-level preflight без мутации состояния;
- `HazardImpactSpec`, одиночная exposure и Zone Hazard переносят явную psychological classification;
- совпавший иммунитет блокирует весь психологический Hazard до Test, поэтому не расходует RNG и не создаёт Wound/failure Conditions;
- `Willpower` и значение failure Condition не используются для неявной классификации; Vampire sunlight Hazard остаётся применимым контрпримером страницы 168.
- нормализован `RULE-MAGIC-001` для `Curse of Cowardly Flight` со страницы 162 Player’s Guide;
- один source-level psychological preflight блокирует для undead и forced Give Ground, и последующий Willpower/Broken;
- незаблокированный spell создаёт строгую очередь `GiveGroundRequest → CowardlyFlightWillpowerRequest`;
- невозможность Give Ground удаляет только movement follow-up, но не отменяет книжный Willpower Test;
- импровизированные Illusion Control, `Shackles of Truth` и Necromancy Control не обобщены без конкретного детерминированного правила.
- нормализован `RULE-NPC-017` для Foul Stench Wyvern со страницы 178 GM Guide;
- добавлен `DecisionOwner.TARGET` и явный выбор между сбросом удерживаемого предмета и Distracted;
- инвентарная ветвь возвращает `DropHeldHandItemRequest`, не выбирая предмет и не мутируя отсутствующее inventory state;
- свободная рука закрывает нос без решения, а невозможность освободить руку автоматически применяет Distracted;
- вход в Zone остаётся фактом внешнего spatial orchestration, а Condition проходит общий reducer с Rule ID Ability.
- добавлен общий `ZoneHazardRequest → ZoneHazardResolutionResult` для уже выбранных существ произвольной Zone;
- Giant-специфичный `ReactorZoneHazardResolutionRequest` сохранил проверку присутствия реагирующего и теперь делегирует общему Zone executor;
- `RepeatedConditionReplacement` задаёт валидируемую замену повторного failure Condition и проверяется после Wound-фазы на актуальном состоянии;
- нормализован `RULE-NPC-018` для Soporific Breath Forest Dragon со страницы 177 GM Guide;
- Endurance Hazard (2) наносит обычную Wound по shortfall и накладывает Drained, а повторный Drained фактически добавляет Defenceless, не удаляя существующий Drained;
- порядок Wound → failure Condition покрывает случай, когда Drained появился из Wounds Table того же Hazard;
- доступность действия без Staggered, Medium Range, выбор Zone и её обитателей оставлены внешнему action/spatial orchestration.
- нормализованы `RULE-NPC-019` Troll Vomit и `RULE-NPC-020` Troll Hag Swamp Breath со страниц 180–181 GM Guide;
- Vomit создаёт одиночную Endurance-exposure Hazard (3), а Swamp Breath — тот же Hazard (3) для уже выбранной Zone;
- оба источника используют общую Wound по shortfall без дополнительных Conditions и отдельной injury-логики;
- требования Staggered цели/действующей, Close/Medium Range, расход действия и spatial selection явно оставлены action orchestration.
- нормализован `RULE-NPC-021` Troll Stupidity со страницы 180 GM Guide и общего Distracted со страницы 123 Player’s Guide;
- отдельный `TrollStupidityState` хранит source Rule ID и подавление до конца текущего боя;
- начало боя применяет Distracted через общий Condition reducer, а активная Ability выдаёт –1d на любой Test Troll;
- фактически нанесённая профильная Wound и успешный Leadership Test снимают Distracted и подавляют его возврат;
- отдельный typed entry point синхронизирует suppression после обычного или иного внешнего снятия Distracted с сохранением Rule ID причины;
- провал Leadership и повторная обработка уже подавленной Ability детерминированно сохраняют состояние, а новый бой требует нового несдержанного Ability-state.
- нормализованы `RULE-MAGIC-002` Magic Resistance (Player’s Guide, страницы 78 и 157) и `RULE-NPC-022` Stone Troll (GM Guide, страница 180);
- добавлены `SpellPotencyModifier`, target-scoped `SpellPotencyRequest` и чистый reducer между завершённым Casting Test и spell effect;
- reducer сохраняет base Potency, delta, effective Potency и Rule IDs, ограничивает итог снизу нулём и явно возвращает `has_effect=False` при нуле;
- Stone Troll фиксирует профильный Resilience 6 и source-aware –1 Potency, а Talent Magic Resistance использует тот же общий контракт;
- multi-target Potency временно считается отдельно для каждой защищённой цели; неоднозначность формулировки записана как `AMBIGUITY-002`.
- добавлен `RULE-NPC-023` для обычной Troll Regeneration со страницы 180 GM Guide;
- новый `DecisionOwner.ACTOR` обозначает контроллера существа, чей добровольный end-turn эффект разрешается;
- Staggered, отсутствие Wounds и отсутствие допустимой неогненной Wound закрывают Regeneration без обращения к decision provider;
- доступная Regeneration требует явного выбора Regenerate/Skip, а выбранное лечение применяет source-aware Staggered и уменьшает профильные Wounds ровно на 1;
- результат лечения возвращает `ProfileStateChangeRequest`, а provenance огненных Wounds пока поступает явным `has_non_fire_wound`.

## Проверено

- 208 unit/integration тестов успешно проходят на Python 3.12, из них 188 относятся к K1;
- исходники и тесты успешно проходят `compileall`.

## Исходный материал

- обнаружен `warhammer_the_old_world_roleplaying_game_-_player_s_guide.pdf`;
- размер: `142493328` байт;
- SHA-256 записан в `docs/source-index.md`;
- PDF не зашифрован, содержит 191 страницу, встроенное оглавление и извлекаемый текстовый слой;
- добавлен воспроизводимый приватный экстрактор `tools/extract_rulebook.py` и optional dependency `rulebook`.
- Gamemaster’s Guide: 186 страниц, около 593820 извлечённых символов, SHA-256 записан в `docs/source-index.md`.

## Известные ограничения

- текущие правила и тесты описывают упрощённый прототип и могут противоречить книге;
- полный каталог всех NPC Abilities, магии, религии и магических предметов ещё не завершён;
- применение времени, Treat/Heal и снятие source-aware Wound effects требует будущего battle loop;
- внешние последствия Wound для инвентаря и анатомии пока являются typed follow-up;
- защита Endurance после заживления `Ruptured organs` ещё не подключена к физическому impact;
- автоматическая замена неподходящей строки Wounds Table для не-физического Hazard требует отдельной GM/simulation policy;
- spatial-поиск и стабильная сортировка secondary/Zone целей, а также разные последствия hit/miss ещё не имеют общего battle orchestration;
- для Monstrous Flight при полностью невозможном Give Ground книга не задаёт fallback; K1 требует внешнего ruling;
- `SuppressRegenerationNextTurnRequest` ещё некому сохранить и погасить без нового turn orchestration;
- `DropHeldHandItemRequest` ещё некому применить без inventory state и policy выбора конкретного удерживаемого предмета;
- K1-фабрики Soporific Breath, Troll Vomit и Swamp Breath не расходуют действие, не проверяют Staggered/дальность и не выбирают цель или Zone без battle orchestration;
- battle loop ещё должен вызывать Stupidity entry points после каждой принятой Wound/снятия Distracted и создавать свежее Ability-state в начале следующего боя;
- общий `ConditionState` пока не хранит источник или объект Distracted; Stupidity компенсирует это собственным source-aware состоянием, но полная replacement-семантика требует будущего решения;
- полный casting pipeline ещё должен вычислять base Potency из последнего Casting Test, запускать target-scoped Potency preflight и не создавать spell effects для `has_effect=False`;
- профильные Wounds пока не хранят provenance огня; Troll Regeneration получает только явный снимок наличия хотя бы одной допустимой неогненной Wound;
- психологическая иммунность undead-профилей подключена к боевым Condition/Hazard-фазам и `Curse of Cowardly Flight`; остальные конкретные non-Condition эффекты требуют отдельного анализа;
- Monte Carlo, JSON, CLI и балансировщик ещё не входят в текущий срез.

## Следующий шаг

Расширить общий end-turn Regeneration reducer на `Monstrous Regeneration` Ghorgon/Troll Hag (GM Guide, страницы 151 и 181): разрешить Monstrosity profile, учесть и однократно погасить `SuppressRegenerationNextTurnRequest`, сохранить различие Troll Hag «Staggered только если ещё нет» и Ghorgon/Troll Hag fire-Wound restriction. Не добавлять полный turn loop.

## Последняя проверка

2026-08-19:

```powershell
$env:PYTHONPATH = "src"
py -3.12 -m unittest discover -s tests -v
```

Результат: `Ran 208 tests ... OK`.

```powershell
py -3.12 -m compileall -q src tests tools
```

Результат: успешно.
