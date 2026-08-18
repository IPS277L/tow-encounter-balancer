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

## Проверено

- 140 unit/integration тестов успешно проходят на Python 3.12, из них 120 относятся к K1;
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
- spatial-выбор вторичных целей/существ для Zone Hazard, разные последствия hit/miss и остальные профильные Reactions ещё не имеют общего orchestration;
- для Monstrous Flight при полностью невозможном Give Ground книга не задаёт fallback; K1 требует внешнего ruling;
- Monte Carlo, JSON, CLI и балансировщик ещё не входят в текущий срез.

## Следующий шаг

Реализовать Monstrous Regeneration Reaction для Ghorgon и Troll Hag (GM Guide, страницы 151 и 181): создать source-aware запрет регенерации на следующий ход. Само end-turn лечение оставить будущему action/turn orchestration; старый battle loop пока не подключать.

## Последняя проверка

2026-08-19:

```powershell
$env:PYTHONPATH = "src"
py -3.12 -m unittest discover -s tests -v
```

Результат: `Ran 140 tests ... OK`.

```powershell
py -3.12 -m compileall -q src tests tools
```

Результат: успешно.
