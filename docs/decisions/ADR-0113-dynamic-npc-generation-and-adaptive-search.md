# ADR-0113 — динамическая сборка NPC и адаптивный Monte Carlo поиск

Статус: реализованы ограниченный Python-путь и JSON/CLI, 2026-11-12. Основание — подтверждённая пользователем исходная цель генератора и указание продолжить реализацию. Прежние JSON-контракты не меняются.

## Решение

Вход поиска содержит фиксированную партию PC и пространство допустимых компонентов, а не reserve готовых NPC. `GeneratedNpc` хранит WS/Strength/Toughness/Agility, Melee/Athletics, оружие, лёгкую броню и список явно допущенных abilities. Builder выводит обычные Inline Tests/caps, Damage и Resilience и создаёт свежий Minion state. Имя/ID не выдают способности. Домен не зависит от генератора, RNG или балансировщика.

Первый набор: Staff/Dagger, отсутствие брони/Light Armour и optional authored `drained_on_hit`. [PG93/97–98](../rules/equipment.md#rule-equipment-003--melee-weapon-profiles) задаёт числовые weapon/armour правила; обычная защита — Athletics. Небоевые Stealth conceal Dagger и Athletics terrain Staff не используются в неподвижной сцене без terrain. Drained использует прежний typed ConditionOnHitSpec/owner: это явно разрешённый авторский компонент, а не утверждение, что произвольному существу положен книжный талант Poisonous Fangs. По умолчанию его нет. Неподдерживаемые weapons/abilities и неверные значения отвергаются до trials; чужие книжные способности не отбрасываются при конвертации, поскольку книжный NPC вообще не является входом builder.

Application выполняет bounded random restarts (30%) и мутации элиты (70%). Мутация меняет один компонент одного NPC либо численность. Уникальность проверяется по упорядоченному полному составу: порядок определяет активацию и имеет значение. Полный декартов product не создаётся. Ограничение proposals = 30×max_candidates предотвращает зависание в маленьком пространстве; достижение лимита сообщается и не объявляется доказанным исчерпанием пространства.

Ранжирование лексикографическое: отсутствие observed unsupported, расстояние до target PC win rate, затем расстояние до target mean started rounds, затем порядок предложения. Лучшие eligible кандидаты проходят отдельные finalist trials с независимыми stage/index seeds. В выдаче сохраняются все screening/validation observations, включая unsupported; рекомендации исключают unsupported финалистов. Более ранние проигравшие кандидаты после validation не подменяют финалиста без новой проверки.

Seed derivation использует SHA256 с отдельными stage namespaces для proposals/explore/validate. Результаты сохраняют полный executable request и исходные компоненты. Стоимость admission ограничена формулой max_candidates×exploration_trials + top_k×finalist_trials ≤ max_total_trials. Дубликаты не потребляют trials. Ошибка simulator или несовпадение полного source прерывает вызов; частичный успех не маскируется.

## Границы и альтернативы

Использован существующий stationary all-Close PC melee simulator с Minions, обычной тактикой и журналом. PC act/target priority и NPC target priority задаются порядком входной партии/слотов; GM defeat disposition обязателен. Minion здоровье не является свободным числом. Раны PC/Fate/Recover сохраняют действующие правила и честные unsupported stops. Другие типы NPC, shield/ranged, реальные talent prerequisites, XP/cost модели и перенос всех ID-dispatched книжных Abilities в capabilities этим срезом не реализованы.

Выбран additive Python API и executable example, чтобы проверить продуктовый путь без ещё одного большого wire family. JSON CLI генератора добавлен поверх этого же application поиска; семейство dynamic_encounter_search JSON1, команда generate-encounter. Existing JSON1 используется для replay конкретного найденного боя. Прежний count-grid API сохраняется как отдельная возможность, не используется новым поиском. Общий DSL, переписывание battle engine и полный каталог до первого генератора отклонены.

Wilson95 описывает marginal uncertainty win probability фиксированного финалиста. Hoeffding95 для started rounds использует известный диапазон 1..max_rounds; это консервативная оценка, включающая round-limit/unsupported префиксы. Интервалы не являются simultaneous гарантией ранжирования и не доказывают глобальный оптимум. Target — критерий близости, а не гарантия найденного попадания в желаемую сложность. Метрика длительности и приоритет difficulty→duration явны.

## Адресная проверка

`tests.integration.test_dynamic_encounter`: вывод производных параметров и нулевого Dagger Damage, независимость механики от ID, варианты при фиксированном числе, изменение числа, мутация, seed replay, отдельные validation seeds, бюджет, маленькое пространство, фактический Drained/source и отказ от чужого aggregate. Ближайшие зависимости: M9 simulation/balance integration и M29 hit conditions. Проверить executable example и JSON replay через текущий parser. Shared kernel/backend/package discovery не менялись; full regression/wheel для этой функции не требуются.

## JSON/CLI граница

Вход не содержит готовых enemies и enemy-specific полей партии. Shared PC/facts/Fate/политики сохраняются; adapter связывает target-neutral party с первым generated slot для имеющейся concrete participant модели, а builder затем создаёт полный состав. Новое пространство явно перечисляет допустимые значения, authored effects и общий defeat disposition. Цели передаются сокращёнными рациональными значениями, проверяются точно до преобразования в числовые targets существующего Python API. Seed — uint64 decimal string. Closed schemas используют local registry с текущими PC common/replay definitions. Первый wire backend sequential; package entry point/discovery не меняются.

Result содержит полный source_request, screening/independent validation observations, selected IDs, фактические trials/proposals и full PC JSON1 replay. Application validator перед выдачей проверяет полные источники/компоненты/стадийные seeds, допустимость состава, выбор/порядок validation и бюджет без повторной симуляции. Source echo проверяется отдельно. Ошибки input/unsupported version дают exit2, execution — exit3 без partial result, I/O — прежний exit4. Прежние family contracts и mechanics неизменны.

Адресная проверка JSON слоя: новый integration test_dynamic_encounter_json (closed/lexical/semantic admission, exact echo, malformed budget/components, forged report, file/stdin CLI, replay), прежний dynamic generator, общие CLI I/O/ошибки и representative PC CLI input errors. Новые схемы доставляются существующим *.json discovery: source/offline refs проверяются сейчас, wheel — по политике проекта при packaging checkpoint.
