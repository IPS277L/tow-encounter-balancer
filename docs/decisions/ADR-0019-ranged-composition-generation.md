# ADR-0019: ограниченная генерация составов M5

Статус: генератор реализован, 2026-09-28. Добавлены 10 model + 7 construction unit и 2 integration tests. Основа — [вход сценария](ADR-0013-ranged-minion-scenario-input.md), [bounded evaluation](ADR-0017-ranged-candidate-assessment.md) и [поэтапная оценка](ADR-0018-staged-ranged-evaluation.md).

## Основание и источники

[Исходный дизайн](../TOWR_Combat_Simulator_&_Encounter_Balancer_—_Context_and_Technical.md), разделы 22–24, предлагает поиск по характеристикам, численности и поведению, предупреждает о нежелательных произвольных профилях и отделяет AI от характеристик. Первый срез ограничивает поиск **численностью явно заданных групп** при фиксированной стороне perspective. Подбор характеристик, тактики и размещения — отдельные будущие задачи.

Непосредственно проверен локальный извлечённый текст:

| Источник | Значение для контракта |
| --- | --- |
| BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91 | Wound побеждает Minion; disposition выбирает атакующий с учётом решения GM. Генерация не создаёт одобрение GM |
| BOOK-GM-GUIDE 1.1, Allies and Antagonists / Understanding NPC Profiles, стр. 93 | Готовые Attack/Protection и свойства NPC-профиля сохраняются; название оружия не даёт автоматически свойства PC-оружия |
| BOOK-GM-GUIDE 1.1, Allies and Antagonists / Brigands & Footpads / Brigand, стр. 97 | Numeric ranged excerpt пригоден для прежнего fixture; он не означает автоматическую поддержку полного каталога или удаление применимых Abilities |
| BOOK-PLAYER-GUIDE 1.4, Rules / The Battlefield / Zones, Position, Range, стр. 114 | Соседние Zones согласуются с Medium, но сами по себе не доказывают видимость, положение внутри Zone или осведомлённость |

Новых Rule IDs и house rules нет. Правила [NPC](../rules/npcs.md), source hierarchy и admission ADR-0013 сохраняются. Численность, порядок перебора, ограничения бюджета и выбор подмножества — техническая область поиска, не предписания книги о сложности боя.

## Шаблон полного резерва

Caller передаёт уже допущенный `NpcRangedScenario` с **полным резервом потенциальных участников**. Он содержит определения, свежие состояния, позиции, порядок ходов, приоритеты всех целей, существующие одобренные defeat decisions и общий round budget. Все участники perspective_side сохраняются во всех кандидатах. Участники противоположной стороны разбиваются на непересекающиеся группы; для каждой задан конечный диапазон численности.

Для численности n выбираются первые n actor IDs группы. Это явный порядок включения резервистов, **не** перестановка ходов или тактический подбор. Сами actor IDs и их определения не создаются заново. Шаблон обязан содержать достаточно участников для верхней границы; генератор не клонирует недостающих, не читает каталог и не повышает максимальную численность самостоятельно.

Такой источник нужен, чтобы с изменением численности не приходилось выдумывать позиции, target priorities, dispositions или gm_approved. Свойства существующего профиля никогда не переписываются ради достижения target. Полный резерв может быть больше выбранных maximum_count; лишние участники остаются только в источнике.

Caller отдельно передаёт обязательные `facts: NpcRangedScenarioFacts`, утверждая их для **каждого состава** заданной области поиска в течение его round budget. Поле не имеет default и не подставляется автоматически из template.facts. В частности, `no_additional_rules`, awareness, LOS, stationary и достаточность боеприпасов должны сохраняться при каждой численности. Допуск полного резерва сам по себе не доказывает это для его подмножеств: численность может влиять на применимость иных правил. Если caller не может подтвердить общий контекст, эта область поиска не поддержана.

Передавая шаблон как источник семейства кандидатов, caller задаёт одни и те же priorities/GM decisions для каждой сохранившейся attacker/target пары во всех составах. Генератор только фильтрует уже существующие полные `MinionDefeatDecision` с неизменными attacker_id, target_id, disposition и gm_approved; новых решений или подтверждений не создаёт. Подбор зависимых от численности policies вне первого среза.

## Реализованные API и расположение

Генерация находится в `application`, поскольку собирает вход симулятора из domain snapshots. `balance` продолжает получать только готовые simulation inputs/aggregates; engine/domain не зависят от генератора. Все входы/результат — frozen/slots, ordered collections нормализуются в tuple, replace повторяет validation. Ошибка исполнения — отдельный RuntimeError.

| API | Содержание |
| --- | --- |
| RangedCompositionGroup(group_id, actor_ids, minimum_count, maximum_count) | Явный ordered резерв однотипных противников и включённые границы численности |
| RangedCandidateGenerationRequest(template_scenario, groups, facts, candidate_id_prefix, max_candidates, master_seed, stages, max_total_trials, window) | Полный источник семейства и параметры прежнего staged evaluator; candidate_count/planned_trials производные |
| RangedCandidateGenerationResult(source_request, evaluation_request) | Полный источник генерации и точный RangedStagedEvaluationRequest с готовыми кандидатами; candidates доступны через evaluation_request |
| generate_ranged_candidates(request) | Чистая application-операция, создающая полный проверенный result без runner/RNG/pool/IO |
| RangedCandidateGenerationError(candidate_id, counts) | Ошибка materialization/admission конкретного состава; исходная причина сохраняется в __cause__ |

Модели — `application/ranged_candidate_generation_models.py`; pure construction — `application/ranged_candidate_generation.py`; ошибка — `application/ranged_candidate_generation_errors.py`. После успешной генерации caller явно передаёт result.evaluation_request в `evaluate_ranged_candidates_staged` с прежними execution options. Объединённая команда, CLI/JSON wire и автоматический запуск симуляций не добавляются.

## Проверки до материализации

Template обязан быть typed NpcRangedScenario. Groups — непустой ordered tuple typed RangedCompositionGroup; group_id и candidate_id_prefix — непустые строки, group IDs уникальны. Actor IDs непустые, без повторов внутри группы и между группами. Их объединение должно совпадать **ровно** со всеми противниками template.perspective_side; unknown, friendly и пропущенные actors запрещены.

В каждой группе непустой резерв; все его actors имеют одинаковый полный NpcDefinition, включая ID, Attack/Protection, Resilience и injury policy. Разные группы могут ссылаться на одинаковое определение: это разные явно заданные резервы с собственным порядком включения/позициями. Числовое совпадение профилей не повод объединять группы или удалять кандидатов. Участники/состояния уже удовлетворяют fresh Minion admission шаблона.

Границы — exact int, `0 <= minimum_count <= maximum_count <= len(actor_ids)`, без bool/float/строковых преобразований. Max_candidates/max_total_trials — positive exact int. Facts и window типизированы; seed, stages/trials/keep и строгий рост trials проходят прежние guards ADR-0018, включая потенциально недостижимые этапы. При любом отказе никакие кандидаты или trials не создаются. Не требуется строить фиктивный staged request из C копий шаблона ради preflight.

Число составов вычисляется до декартова перебора: `C = product(maximum_count - minimum_count + 1)`. Если у всех групп minimum_count=0, из C вычитается один полностью нулевой вектор. Пустая противоположная сторона недопустима для текущего сценария и не превращается в автоматическую победу. Если C=0 или C>max_candidates, запрос отклоняется целиком. Ни случайной выборки, ни первых max_candidates, ни урезания диапазонов нет.

Для simulation budget применяется ровно формула ADR-0018, начиная с U[0]=C: `planned_trials = sum(U[i] * stages[i].trials_per_candidate)`, `U[i+1] = min(U[i], stages[i].keep)`. Превышение max_total_trials отклоняется **до материализации кандидатов**, а не только до runner. Все прогоны этапов считаются полностью; early stop и предполагаемое отсеивание не уменьшают необходимый верхний бюджет. Candidate-count cap ограничивает число выходных сценариев, но не является лимитом байт уже переданного шаблона или временем исполнения.

## Порядок, IDs и проекция сценария

Диапазоны перебираются по возрастанию, лексикографически в порядке groups, последняя координата меняется быстрее. Нулевой вектор пропускается только по правилу выше. Составы с одинаковыми характеристиками/результатами не схлопываются. Порядок кандидатов становится tie-break прежнего evaluator; изменение порядка groups может поэтому изменить выбор при точном равенстве оценок.

Для count vector `(n0, n1, ...)` candidate ID имеет вид `candidate_id_prefix + ':counts:' + ','.join(decimal counts)`, без ведущих нулей. Например, `family:counts:0,1`. Имена групп в строку не кодируются; соответствие координат хранится в source_request.groups. ID стабилен для того же prefix/vector и не зависит от seed, окна, диапазонов или позиции в списке. Он уникален **внутри одного generation request**, но не является глобальным хэшем источника: другой шаблон/порядок групп с тем же prefix требует сравнения полного source. Переименование prefix не изменяет RNG derivation или правила отбора.

Для каждого вектора retained IDs — вся perspective_side плюс первые n IDs каждой группы. Генератор строит новый вход, сохраняя отдельные исходные порядки:

1. Roster participants и их NpcParticipantSnapshot фильтруются по retained IDs в порядке исходного roster. Определения, состояния и actor IDs оставшихся не меняются.
2. CombatRoundState.participants и actor_order фильтруются **каждый в своём исходном порядке**; side_order и round 1 сохраняются. Active/completed/excluded turns, histories, pending и weapons остаются пустыми через свежие штатные constructors.
3. Spatial placements фильтруются в исходном порядке, с прежними zone_id/side_id. Весь ZoneGraph, включая теперь пустые Zones, сохраняется; никакого перемещения, укрытия или inference LOS/awareness нет.
4. Actor policies сохраняют исходный порядок actors. Для каждого оставшегося actor сохраняются только оставшиеся enemy targets и соответствующие полные defeat decisions в первоначальном target priority order. Actor order и target priority не заменяются порядком groups.
5. Objective фильтрует исходный ordered список противников до retained IDs. Повторный Staggered choice, perspective_side и max_rounds берутся из шаблона. Facts берутся из явно переданного family facts.
6. Новый initial.current.id равен `candidate_id + ':initial'`, чтобы execution prefixes относились к составу. Весь NpcRangedScenario повторно проходит существующий admission; затем создаётся прежний RangedBalanceCandidate.

Даже если структурная проекция обычно сохраняет admission, constructors нельзя обходить или заменять утверждением «template уже проверен». Неподдержанный состав не пропускается молча: любая ошибка materialization/admission прерывает генерацию без partial result, с candidate_id/count vector и исходной причиной. Input guards дают обычные TypeError/ValueError до перебора; KeyboardInterrupt/SystemExit не оборачиваются.

## Выход и границы доказуемости

Result хранит source_request и полный evaluation_request. Конструктор проверяет все общие staged параметры, точное число/порядок candidate IDs, а также точное равенство scenario каждого кандидата ожидаемой проекции соответствующего count vector. Перестановки, пропуски, повторы и подмена definition/state/позиции/policy/facts/objective/round ID отклоняются. Для validation достаточно сравнивать проекции по одной, не хранить вторую полную копию списка.

Результат не содержит outcomes, assessments, trial records, RNG или execution options. Согласованность с источником не доказывает истинность caller facts или происхождение supplied профиля из книги. Стандартный staged report хранит сами сценарии; для трассировки к резерву и диапазонам внешний caller сохраняет generation result. Его provenance не внедряется в engine или существующий simulation wire v1.

## Детерминированные примеры

Perspective-side actors P1,P2 фиксированы. Резерв другой стороны разбит на A=(A1,A2), range 0..2 и B=(B1), range 0..1. Все placements, profiles и decisions переданы явно. При stages=(10, keep=2), (100, keep=1) получаются:

| Count vector | Противники | Candidate ID при prefix=family |
| --- | --- | --- |
| (0,1) | B1 | family:counts:0,1 |
| (1,0) | A1 | family:counts:1,0 |
| (1,1) | A1,B1 | family:counts:1,1 |
| (2,0) | A1,A2 | family:counts:2,0 |
| (2,1) | A1,A2,B1 | family:counts:2,1 |

Порядок в колонке противников показывает членство, не заменяет исходный actor_order. C=3×2−1=5; max_candidates=4 отклоняется, 5 допускается. Planned trials=5×10+2×100=250; бюджет 249 отклоняется до материализации, 250 допускается. Фактический бюджет оценки может оказаться меньше лишь после исполнения этапов.

- Если A.minimum_count=1, C=2×2=4, planned=240; нет нулевого вектора для вычитания. Range обоих групп 0..0 даёт C=0 и отказ.
- При сохранённом target priority (B1,A2,A1), состав (1,1) получает (B1,A1), а не (A1,B1). Полные decisions для этих пар сохраняются неизменными.
- При порядке резерва A=(A2,A1) состав (1,0) включает A2, но не меняет порядок ходов остальных. Перестановки и выбор всех сочетаний одного размера не выполняются.
- Если у каждой группы minimum_count=maximum_count и сумма этих чисел положительна, генерируется один состав; размер резерва не увеличивает число кандидатов. Bounds выше размера резерва, смешанные definitions внутри группы и повтор actor ID дают отказ.
- Равные definitions A и B допустимы; все пять составов сохраняются. Seed схема не использует candidate ID; смена prefix меняет ID/initial prefix, но не броски при том же сценарном поведении и runtime.

## Реализация и проверки

Реализованы [models](../../src/towr/application/ranged_candidate_generation_models.py), [pure construction](../../src/towr/application/ranged_candidate_generation.py) и [typed error](../../src/towr/application/ranged_candidate_generation_errors.py). В balance/ranged_staged_evaluation_models.py выделены общие внутренние _validate_stages/_planned_trials, используемые existing staged request и generation preflight; публичный API/формула сохранены. Seed admission использует один NpcRangedSimulationRequest, не создавая фиктивных кандидатов. Result validation сравнивает expected projections по одной через ту же pure construction, с локальным import для устранения цикла models/construction. Runner не добавлен.

10 [model tests](../../tests/unit/test_m5_ranged_candidate_generation_models.py): типы/границы/разбиение групп/definitions, C и budget до перебора/materialization, общие stage guards, frozen/replace, отсутствие records и отказы при подмене общих параметров, профилей, policies/decisions, порядка, позиции, objective или initial ID. 7 [construction tests](../../tests/unit/test_m5_ranged_candidate_generation.py): пять lexicographic vectors/IDs без dedup, оба perspective-side, независимые порядки, исходные snapshots/decisions/graph и явные facts, повторное admission, чистота без runner/RNG/pool, failure второго состава/cause/notes и interrupts. 2 [integration tests](../../tests/integration/test_m5_ranged_candidate_generation.py): все пять кандидатов исполняются прежним staged service, реальные sequential/process отчёты равны, повтор генерации детерминирован, переименование prefix сохраняет наблюдения и selected composition. Конкретная Monte Carlo-вероятность не ожидается.

Генерация PC, ближний бой/движение, полный NPC-каталог, клонирование beyond reserve, подбор характеристик/AI/позиций, named presets, CLI/JSON balance и статистические гарантии остаются вне среза. Они не объявляются завершёнными вместе с генерацией численности.

Проверка контракта: read-only probe на existing constructors построил все пять примеров и подтвердил admission, сохранение исходных порядков/решений/graph и бюджет 250/249. Полный набор повторно **1899 tests OK**, Python 3.14.5, 50,584 с. На том контрактном срезе production generator и новые tests ещё отсутствовали; изменения ограничивались документацией.

Проверка реализации: **1918 tests OK**, Python 3.14.5, 59,241 с; compileall/pip check/diff check и ссылки успешны. Существующие незакоммиченные документы контрактного среза сохранены. Domain/engine/simulation и существующие services/CLI не менялись. Первый M5 закрыт [аудитом](../audits/m5-readiness.md) в текущем scope; [typed пример](../examples/m5/README.md) проверен в sequential/process. Контракт [JSON balance v1 / CLI balance](ADR-0020-ranged-balance-json-v1.md) реализован полностью в текущем scope: Schema/adapters, application service, кодирование ошибок и CLI balance. Внешняя граница M5 закрыта [аудитом](../audits/m5-external-readiness.md); следующий этап M6 — ограниченный контракт ближнего боя Minions, выбранный пользователем.
