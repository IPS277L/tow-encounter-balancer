# Hazards

Источник: `BOOK-PLAYER-GUIDE`, страницы 68, 115–116. Статус: модель экспозиции `implemented` в K1; разрешение Test и последствий `draft`.

## RULE-HAZARD-001 — проверка экспозиции

Персонаж, подвергшийся Hazard, делает Test указанного GM или правилом Skill. Обычный Hazard избегается хотя бы одним успехом. Hazard с рейтингом требует не меньше успехов, чем его рейтинг.

## RULE-HAZARD-002 — провал рейтингового Hazard

При недостатке успехов персонаж получает Wound. Число кубов Wounds Table равно разнице между рейтингом Hazard и успехами Test, плюс обычные дополнительные кубы за untreated Wounds. Hazard может дополнительно наложить указанное Condition.

Для не-физических Hazards GM может заменить неподходящий результат Wounds Table ближайшим подходящим результатом или специальной раной.

## RULE-HAZARD-003 — граница K1

`HazardImpactSpec` хранит рейтинг, Skill избегания и Rule ID. При успешной replacement-атаке kernel не подставляет фиктивный Damage, а возвращает `HazardExposureRequest`. Следующий resolver должен принять профиль соответствующего Skill и `TestResult`, вычислить нехватку успехов и передать Wound в существующую Player/Champion либо NPC injury policy.

Выбор всех существ в Zone для Blasting Charge, его срабатывание в Zone атакующего при промахе и прочие area-правила относятся к конкретному `SecondaryEffectSpec`, а не к универсальной семантике Hazard.
