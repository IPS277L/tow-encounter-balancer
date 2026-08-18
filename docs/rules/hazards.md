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

Рейтинг в модели всегда положительный; обычный Hazard, для которого книга требует хотя бы один успех, представлен рейтингом `1`. Hazard без Wound обязан содержать хотя бы одно failure Condition. Неподходящий результат таблицы для не-физического Hazard по умолчанию не заменяется; будущая GM/simulation policy сможет использовать книжную опцию замены.

Выбор всех существ в Zone для Blasting Charge, его срабатывание в Zone атакующего при промахе и прочие area-правила относятся к конкретному `SecondaryEffectSpec`, а не к универсальной семантике Hazard.

Unsteady Giant использует отдельный `ReactorZoneHazardRequest`: он фиксирует Hazard (3), Athletics и область «сам реагирующий Giant и все остальные существа в его Zone». Spatial orchestration выбирает конкретные разные цели и создаёт для каждой обычную `HazardExposureRequest`; дальнейшие Test и injury policy остаются общими.
