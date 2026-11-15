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

## Минимальный локальный UI

По запросу пользователя добавлены форма и редактируемый форматированный JSON, загрузка/скачивание и реальный запуск поиска: `towr ui [--request FILE] [--port PORT]`. Выбран стандартный loopback HTTP server и self-contained страница, поставляемая Python-модулем, без dependencies/build frontend. Существующий strict dynamic JSON parser и source/result validator остаются единственным путём допуска. GET initial file/POST generation — тонкий UI adapter, без новых правил и wire version. Один calculation lock защищает от повторного запуска; ThreadingHTTPServer сохраняет отзывчивость страницы. Подробный task/progress/cancellation API для прототипа не вводится.

Проверки: `test_local_ui` (страница/initial source, actual HTTP generation, malformed admission, loopback/routes, busy responsiveness и CLI dispatch), общие CLI I/O tests и optional real Edge/Chromium test `test_local_ui_browser` (JSON↔form, budget, seed precision, actual run/error). Визуальная проверка desktop screenshot; package/assets/dependencies неизменны, full/wheel не требуются.

## Карточки и JSON (2026-11-15)

По запросу пользователя добавлены независимые переключатели «Карточки / JSON» для запроса и результата. Полный JSON остаётся источником данных запроса; DOM editor записывает конкретный путь, сохраняя остальные значения и порядок массивов. Доступны PC stats/skills/equipment/grip, NPC search-space choices и раскрывающиеся дополнительные поля. Невалидные правки не запускают старый запрос и не затирают JSON при переключении.

Уточнение пользователя: пересчёт только по кнопке «Запустить генератор», при редактировании — уведомление об устаревшем результате. Последний отчёт/оценки неизменны и доступны в обоих режимах; canonical comparison с source_request снимает пометку при восстановлении входа. Результат показывает validation/screening составы, оценки и replay download. «Взять за основу запроса» переносит union значений NPC в search_space и фиксирует количество, не обещая точного сохранения каждого NPC/порядка: новый поиск может комбинировать значения. Партия и бюджет текущего запроса сохраняются, автоматического fetch нет. Wire/models/kernel прежние.

Адресная проверка: HTTP UI integration и расширенный Edge browser test — сохранение скрытых полей, PC/space editing, точность seed, roundtrip tabs, explicit runs, stale marker, composition transfer, invalid input и source echo. Визуально проверены карточки запроса и рассчитанного результата. Full/wheel не требуются для UI Python-модулей без новых ресурсов/зависимостей.

## Автоплан, производный бюджет и seed (2026-11-15)

По уточнению пользователя UI планирует поиск автоматически из состава/целевых условий, сохраняя manual override четырёх search значений. Editable budget удалён: max_total_trials всегда равен max_candidates×exploration_trials + top_k×finalist_trials, даже в ручном режиме. Current JSON1 по-прежнему хранит это число для admission/replay; wire version/CLI/Python semantics не меняются. Mode flags живут только в UI, без скрытых правил/записей в JSON.

Чистая bounded JS эвристика учитывает число alternatives (log space), диапазон NPC, партию и предполагаемый workload по длительности/cap/WS/Ag/abilities. План не является confidence guarantee или wall-clock timeout: ёмкость256–1600от базовых800, screening около40%, до64уникальных candidates с ограничением конечным пространством; до2finalists с64–256trials по p(1−p)/оставшейся ёмкости. Для прежнего рабочего примера получается24×12 +2×256=800. При ручном override derived budget единственный, без настройки пользователем. Raw JSON preview не переформатируется на каждом keystroke; derived значения фиксируются при blur/выходе к карточкам/save/Run. Невалидный план блокирует запуск.

Fresh seed включён по умолчанию. Run получает uint64 через crypto.getRandomValues и точный BigInt→decimal string, затем отправляет существующему backend; redraw/edit/tab/plan не потребляют randomness и не запускают MC. Fixed mode сохраняет воспроизводимость полного результата. GET request несёт UI-only header X-TOWR-UI-Mode: manual при --request; file picker тоже восстанавливает ручные числа. Переключатель seed независим от manual search. Фиксированный seed повторяет поиск целиком, а stage/trial seeds внутри уже различаются.

Проверка: HTTP UI/admission/defaults и browser test — auto/manual, workload/target response, finite space, derived budget, absence of editable budget, request/view preservation, no auto execution, fresh exact uint64, fixed full-report reproduction. Browser RNG в проверке детерминированно подменяется, игровые выборки малы. Полный автоплан800+trials не запускается ради UI теста.

## Фиксированный seed и отмена (2026-11-15, актуальное решение)

Пользователь отменил fresh-seed поведение: checkbox/генератор seed удалены, заданный master_seed сохраняется при любом Run/Cancel. Автоплан и computed budget остаются. Различающийся UUID используется только как transport token отмены, не входит в запрос модели и не влияет на игровые выборки.

Добавлена кооперативная отмена: optional cancel_requested callback и отдельный DynamicEncounterCancelled в application search. Checkpoints стоят до поиска/кандидатов, после simulation и перед возвратом; default simulator использует Random subclass, проверяющий сигнал перед randint. Без сигнала RNG-последовательность и полный результат прежние. Сторонний simulator обязан реализовать свои внутренние checkpoints, иначе остановка доступна на границах вызовов. Shared kernel/simulation schema не меняются.

Local UI хранит Event/finished/token под lock. Generation/cancel HTTP requests несут X-TOWR-Run-ID, POST /api/cancel ставит сигнал конкретному запуску. До регистрации generation допускается bounded early-cancel table128; чужой active token отвергается. Успех commit и cancel acceptance согласуются под state lock. Worker/slot освобождаются в finally. Отмена возвращает UI-only kind dynamic_encounter_cancelled, без partial report, новый wire version не нужен. Browser ждёт прекращения работы, показывает cancelled state, затем разрешает новый Run.

Проверки: cancellation до первого боя/внутри RNG и неизменность результата при never-cancel callback; HTTP real dice stop, release/restart, early/stale cancel и concurrent responsiveness; browser button/ack/state recovery и fixed source/result replay. Никакого полного прогона или нового worker-process backend для отмены не вводится.

## Файловые действия панелей (2026-11-15)

Внешняя toolbar оставляет только Run/Cancel. Обе панели содержат одинаковые SVG actions upload/download/format с title/aria-label; formatter виден только в JSON mode. Request widgets сохраняют прежнюю загрузку/выгрузку и auto/manual правила. Result upload — просмотр сохранённого отчёта без MC: POST /api/validate-result читает strict UTF-8 JSON с разрешёнными результатными float numbers, отвергает duplicate/nonfinite/surrogate/неподходящую структуру и использует текущую offline result schema. Это schema admission для просмотра, а не восстановление/проверка typed execution proofs; происхождение report не доказывается пересчётом. UI не подменяет исходный запрос при загрузке отчёта и сохраняет старый report при ошибке.

File load version защищает от позднего ответа импорта, если пользователь начал новый Run или выбрал другой файл. Result formatter не изменяет lastResult/его оценки. Actions блокируются на время генерации. Новые assets/dependencies/wire version не вводятся; SVG поставляются в существующем Python page code.

Проверка: HTTP validation roundtrip без вызова execute, malformed/duplicate/nonfinite/oversized family/deep JSON errors; browser file locations, JSON-only format visibility, import roundtrip, сохранение запроса/отчёта при ошибке и no auto MC. Прежние cancel/seed/card сценарии сохранены.

Уточнение пользователя: у результата остаётся только скачивание. Result upload/formatter, их обработчики, /api/validate-result и import-only проверки удалены; request actions и JSON/карточки прежние.
