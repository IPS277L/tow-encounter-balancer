# Hazards

Источник: `BOOK-PLAYER-GUIDE`, страницы 68, 115–116. Статус: модель экспозиции и разрешение последствий `implemented` в K1.

## RULE-HAZARD-001 — проверка экспозиции

Персонаж, подвергшийся Hazard, делает Test указанного GM или правилом Skill. Обычный Hazard избегается хотя бы одним успехом. Hazard с рейтингом требует не меньше успехов, чем его рейтинг.

## RULE-HAZARD-002 — провал рейтингового Hazard

При недостатке успехов персонаж получает Wound. Число кубов Wounds Table равно разнице между рейтингом Hazard и успехами Test, плюс обычные дополнительные кубы за untreated Wounds. Hazard может дополнительно наложить указанное Condition.

Для не-физических Hazards GM может заменить неподходящий результат Wounds Table ближайшим подходящим результатом или специальной раной.

## RULE-HAZARD-003 — граница K1

`HazardImpactSpec` хранит рейтинг, Skill избегания, наличие Wound, дополнительные failure Conditions и Rule ID. При успешной replacement-атаке kernel не подставляет фиктивный Damage, а возвращает `HazardExposureRequest`. Orchestration строит обычный Test указанного Skill и передаёт его результат вместе с состоянием цели в `resolve_hazard`.

`HazardResolutionResult` явно хранит успехи, рейтинг и shortfall. При `successes >= rating` состояние не меняется. При провале:

- для Player/Champion shortfall становится `base_dice`, после чего добавляются untreated Wounds и обычные модификаторы таблицы;
- для Minion/Brute/Monstrosity shortfall становится базовым числом профильных Wounds;
- Wound проходит общую отмену и специализированный Wound-effect reducer;
- failure Conditions применяются независимо от того, была ли Wound отменена через Near Miss.

Опциональная `RepeatedConditionReplacement` задаёт книжную замену именно для повторного применения указанного failure Condition. Проверка выполняется после Wound-фазы на актуальном состоянии цели. Поэтому Condition, уже имевшееся до Hazard или только что полученное из Wounds Table, считается повторным; исходное Condition сохраняется, а фактически добавленное replacement Condition записывается в `HazardResolutionResult.failure_conditions` и `condition_applications`. Replacement обязан ссылаться на одно из failure Conditions источника, а для одного Condition допускается не более одной замены.

Рейтинг в модели всегда положительный; обычный Hazard, для которого книга требует хотя бы один успех, представлен рейтингом `1`. Hazard без Wound обязан содержать хотя бы одно failure Condition. Неподходящий результат таблицы для не-физического Hazard по умолчанию не заменяется; будущая GM/simulation policy сможет использовать книжную опцию замены.

Выбор всех существ в Zone для Blasting Charge, его срабатывание в Zone атакующего при промахе и прочие area-правила относятся к конкретному `SecondaryEffectSpec`, а не к универсальной семантике Hazard.

Общий `ZoneHazardRequest` фиксирует параметры Hazard, но не выбирает Zone или существ. Spatial orchestration передаёт уже выбранные разные цели, их актуальные Test-профили и injury contexts в стабильном порядке через `ZoneHazardResolutionRequest`. `resolve_zone_hazard` слева направо создаёт для каждой цели обычную `HazardExposureRequest`, выполняет общий Test и передаёт результат в `resolve_hazard`. Все цели используют один внедрённый RNG, но сохраняют собственные `TestResult`, `HazardResolutionResult`, состояния и решения Test/Wound. Executor отклоняет повторные target/Test IDs и не знает карты Zones.

Unsteady Giant сохраняет более узкий `ReactorZoneHazardRequest` и `ReactorZoneHazardResolutionRequest`: эта обёртка дополнительно требует включить самого реагирующего Giant, после чего делегирует общему Zone executor. Soporific Breath использует общий запрос, поскольку выбранная Zone находится в Medium Range и не обязана содержать Forest Dragon.

Troll Vomit (GM Guide, страница 180) является одиночной Endurance-экспозицией Hazard (3), а Swamp Breath Troll Hag (страница 181) — тем же Hazard (3) для каждого существа выбранной Zone. Оба источника используют стандартную Wound по shortfall без failure Conditions. Требования Staggered/дальности и расход действия проверяются до Hazard pipeline.

## Психологическая классификация и иммунитет

`HazardImpactSpec`, одиночная `HazardExposureRequest` и `ZoneHazardRequest` переносят явную `EffectClassification`. Если вся экспозиция классифицирована как `PSYCHOLOGICAL`, совпавший `EffectImmunity` блокирует Hazard целиком до Test: цель не бросает кубы, не получает Wound или failure Conditions, а результат сохраняет Rule ID источника и иммунитета.

Классификация относится к источнику целиком и не выводится из Skill проверки либо будущего Condition. Это подтверждает профиль Vampire (Gamemaster’s Guide, страница 168): он иммунен к психологическим эффектам, но солнечный свет остаётся Hazard (2), накладывающим Ablaze и сопротивляемым через Willpower. Поэтому один лишь `Willpower` не превращает Hazard в психологический.

В Zone Hazard каждая цель проверяет собственный снимок иммунитетов до своего Test. Заблокированная цель остаётся в упорядоченном результате с `avoidance_test=None` и `hazard=None`, не потребляет RNG и не вызывает decision providers; следующие цели продолжают обычный детерминированный pipeline.
