# ADR-0017: агрегаты и ограниченная оценка кандидатов M5

Статус: aggregate-only summary/projection, pure single-candidate assessment и bounded evaluation конечного списка кандидатов **реализованы**, 2026-09-28. Метрика подтверждена пользователем: цель за лимит, отдельные round_limit/unsupported_path и явное окно без пресетов. Исполнение списка и точный выбор top_k готовы; поэтапная оценка прежнего списка реализована по [ADR-0018](ADR-0018-staged-ranged-evaluation.md). [Аудит M4](../audits/m4-readiness.md) завершён.

## Основание и решения разного уровня

AGENTS.md требует, чтобы балансировщик получал только вход симулятора и агрегированный результат. Нынешний NpcRangedSimulationResult хранит ещё и per-trial records; передавать его целиком новому balance evaluator не следует. Нужна отдельная неизменяемая проекция счётчиков с исходным NpcRangedSimulationRequest. Она не зависит от определения сложности.

Исходный дизайн, разделы 19–22, предлагает player victory rate, приблизительные окна Easy/Medium/Hard/Impossible, желаемую длительность и многоэтапный поиск. Это продуктовые ориентиры прототипа, не нормативные правила книги и не готовый контракт первого M5. Текущий [NpcRangedScenario](ADR-0013-ranged-minion-scenario-input.md) допускает только Minions; objective перечисляет всех противников perspective_side. OBJECTIVE_ACHIEVED означает поражение противоположной стороны в данном сценарии, а не утверждение о смерти всех NPC или победе полноценной группы PC.

Пользователь подтвердил ограниченный первый M5: оценка достижения заданной цели за явный round budget, отдельные shares round_limit/unsupported_path, числовое окно без именованных пресетов. Это продуктовый выбор метрики, не house rule и не повод менять engine. Реализованы aggregate-only сводка и чистый оценщик, использующий её без исполнения боя.

## Первый implementation-срез: только сводка M3

Реализованные публичные API:

- [simulation/npc_ranged_summary_models.py](../../src/towr/simulation/npc_ranged_summary_models.py): frozen, slots `NpcRangedSimulationSummary`.
- [simulation/npc_ranged_summary.py](../../src/towr/simulation/npc_ranged_summary.py): `summarize_npc_ranged_simulation(result) -> NpcRangedSimulationSummary`.

Сводка хранит только `source_request`, typed `outcome_counts`, `total_attack_count`, `total_visited_round_count`. Число прогонов берётся из `source_request.trials`; mean_attack_count и mean_visited_round_count вычисляются из сумм, как в M3, а не передаются независимо. Ни trial records, ни seed на каждый trial, ни журналы, terminal injury snapshots или ссылка на полный result не удерживаются. Сам input simulator разрешён архитектурной границей и остаётся неизменяемым.

`summarize` принимает только завершённый NpcRangedSimulationResult, переносит его exact source и счётчики без runner/RNG/JSON. Не происходит повторной оценки outcomes или проигрывания боя. Конструктор сводки проверяет typed source/counts, exact int без bool, неотрицательные totals, сумму четырёх outcomes == trials, допустимые суммарные границы числа атак и посещённых раундов по source. Для раундов учитывается нижняя граница: каждый ROUND_LIMIT использует весь budget, остальные outcomes посещают хотя бы один раунд; для атак — минимум по одному на terminal outcome и не больше slots за посещённые раунды. Guards проверяют непротиворечивость агрегатов, а не восстанавливают утраченные trial records и не доказывают происхождение данных.

Средние вычисляются с тем же смыслом, что сейчас: visited rounds включают посещённый последний раунд, даже если он не завершён; unsupported/round_limit записи не отбрасываются. Это не средняя длительность только выигранного или полностью завершённого боя. Rates и difficulty labels в первый срез не входят. M3 result, CLI/JSON v1 и существующие service APIs сохраняются; отдельного endpoint или сериализации сводки пока нет.

[9 unit tests](../../tests/unit/test_m3_npc_ranged_summary.py) проверяют точные четыре outcome counts и totals, совпадение means с M3, frozen inputs/summary, неверные types/count sums/budgets, отсутствие trial/result references в графе полей и отсутствие RNG/runner при проекции. [Integration test](../../tests/integration/test_m3_npc_ranged_summary.py) сравнивает сводки настоящих sequential/spawn с injected deterministic RNG, тремя исходами и exact source. Это не Monte Carlo-тест на конкретную вероятность. Набор с четырьмя outcomes отдельно проверяет, что unsupported observation с нулём атак остаётся в общем знаменателе means.

Конкретные guards: N = source.trials, B = source.scenario.initial.max_rounds, A = len(source.scenario.initial.current.actor_order), L = counts.round_limit, T = counts.objective_achieved + counts.side_defeated. Требуются сумма counts = N, `L * B + (N - L) <= total_visited_round_count <= N * B` и `T <= total_attack_count <= A * total_visited_round_count`. `trials` и обе means — свойства; dataclasses.replace повторяет validation. Равенство summary включает source: одинаковые totals другого master_seed не дают равный summary. При прямом конструировании допустимые агрегаты всё равно не являются доказательством исполнения; M3 result и projector — штатный путь их получения.

## Реализованная оценка одного кандидата

[balance/ranged_assessment_models.py](../../src/towr/balance/ranged_assessment_models.py) содержит frozen, slots ObjectiveRateWindow(minimum, target, maximum) и RangedCandidateAssessment(source_request, summary, window). [assess_ranged_candidate(source_request, summary, window)](../../src/towr/balance/ranged_assessment.py) создаёт проверенную оценку. В этом срезе кандидат задан полным NpcRangedSimulationRequest; отдельные candidate_id, список сценариев и batch request появятся на следующей границе, а не дублируются здесь.

Window принимает только явные Fraction, включая Fraction(0)/Fraction(1); int/bool/float/строки автоматически не преобразуются. Требуется `0 <= minimum <= target <= maximum <= 1`; точечное окно допустимо. Target сохраняется для будущего ранжирования, сейчас он только проверяется внутри границ, отдельного score нет. Оценщик требует typed input/aggregate summary/window и точное равенство summary.source_request == source_request. Равный immutable snapshot допускается; другой seed, число trials или scenario отклоняются. Full M3 result вместо summary недопустим.

Свойства objective_achieved_rate, side_defeated_rate, round_limit_rate, unsupported_path_rate возвращают Fraction(count, summary.trials). Знаменатель включает все прогоны, даже round_limit/unsupported. Доли всегда наблюдаемые: при наличии unsupported их нельзя выдавать за пригодную оценку вероятности. Счётчики и descriptive means доступны в сохранённой summary без повторного расчёта боя.

RangedAssessmentStatus — ELIGIBLE либо UNSUPPORTED_OBSERVATIONS, производный от counts.unsupported_path. `window_match` равен True/False только при ELIGIBLE; границы включены и сравниваются точно, без float epsilon. При unsupported возвращается **None**, чтобы отличать непригодную оценку от достоверно вычисленного попадания/непопадания точечной оценки в окно. Даже если все прогоны достигли round limit, оценка пригодна для этой ограниченной по времени метрики: objective rate = 0 и отдельная round_limit_rate = 1. Это не переименование остановки в defeat/draw.

Rates/status/match — свойства, их нельзя независимо передать в конструктор или dataclasses.replace. Оценка хранит только input/summary/window, без trial records, engine/runner/RNG/JSON. Guards проверяют согласованность источника, но не доказывают происхождение вручную сконструированных aggregate counts. ELIGIBLE и window_match не являются confidence guarantee, difficulty preset или гарантией будущей победы.

[9 unit tests](../../tests/unit/test_m5_ranged_assessment.py) проверяют точные доли и знаменатель, включённые/точечные границы 0/1, unsupported/все round_limit, типы/порядок window, source mismatch, frozen/derived поля, отсутствие records/RNG/runner/JSON. Проверка с числом trials больше 2**60 показывает различие двух значений, сливающихся при float rounding. [Integration](../../tests/integration/test_m5_ranged_assessment.py) использует настоящие sequential/spawn и injected deterministic RNG: три исхода дают равные source-bound assessments и точное попадание в окно 1/3. Existing simulation/application/CLI APIs не изменены.

## Граница bounded evaluation M5

Для подтверждённой метрики отдельный `balance` слой зависит только от simulation input/summary contracts. Никаких JSON, CLI, engine calls, игровых журналов, RNG или знания Attack/Wound resolution внутри evaluator. Application orchestration исполняет прежний runner, создаёт aggregate summary и передаёт его оценщику. UI/JSON для balance появятся отдельным решением, а не расширением simulation v1 без версии.

| Реализованная модель | Содержание |
| --- | --- |
| RangedBalanceCandidate | Непустой candidate_id и готовый допущенный NpcRangedScenario; сценарий не генерируется и не исправляется оценщиком |
| RangedBalanceEvaluationRequest | Упорядоченный непустой tuple уникальных candidates, общие master_seed/trials_per_candidate/max_total_trials, одно явное окно цели, top_k |
| ObjectiveRateWindow (реализовано) | Точные Fraction minimum/target/maximum в [0,1]; без defaults Easy/Medium и без весов |
| RangedCandidateAssessment (реализовано) | Exact request/summary source, производные доли/status/window_match; candidate_id привяжет внешний batch result |
| RangedBalanceEvaluationResult | Все assessments в порядке входа, выбранные candidate IDs, фактический бюджет и параметры воспроизведения; не содержит per-trial records |

Первый evaluator не проверяет, что два сценария являются одним и тем же encounter с изменённым ровно одним параметром. Caller явно подаёт разрешённый конечный список альтернатив; отчёт сохраняет каждый полный input. Общими обязаны быть perspective_side и round budget. Более сильные ограничения на неизменную группу/геометрию и генерация допустимых вариантов требуют отдельного контракта. Нельзя автоматически менять composition, свойства профиля, awareness, policies или GM decisions ради попадания в окно.

## Предложение метрик и фильтрации

Для N = trials публикуются четыре наблюдаемые доли: objective_achieved/N, side_defeated/N, round_limit/N, unsupported_path/N. Знаменатель никогда не заменяется суммой только terminal outcomes. При отсутствии unsupported вероятность цели трактуется только как оценка достижения цели **в пределах заданного бюджета**, а не победы при неограниченной длительности. ROUND_LIMIT остаётся собственным исходом и не объявляется поражением или ничьей.

При unsupported_path > 0 реализован статус `UNSUPPORTED_OBSERVATIONS`: счётчики и observed shares сохраняются, window_match = None. Selector исключает такую оценку из selected. Нет подмены unsupported поражением, исключения таких trials из знаменателя или скрытого rerun. Это ограничение достоверности инструмента, а не новое игровое правило. Ошибка исполнения вообще не создаёт assessment с игровым outcome.

Для пригодных кандидатов сравнение с включёнными границами окна и расстоянием до target выполняется по точным отношениям counts/N; typed window использует stdlib Fraction, без неоднозначного float epsilon. Внутри окна выбираются до top_k по abs(objective_rate − target), равенство сохраняет исходный порядок candidates. Кандидаты вне окна остаются в отчёте; если никто не подходит, selected пуст, а «ближайший» не выдаётся за подходящий. Формула не сочетает разные показатели с выдуманными весами.

Длительность и Attack counts пока только описательные. Target rounds, условные средние по исходам, confidence intervals, доверительная пригодность малого N и именованные difficulty presets требуют отдельного продуктового/статистического контракта. Попадание точечной оценки в окно не является гарантией истинной вероятности. Прежние приблизительные Easy/Medium/Hard/Impossible границы не включаются по умолчанию.

## Seeds, бюджет и исполнение

Preflight request строит для каждого candidate прежний NpcRangedSimulationRequest с одним явно заданным master_seed и trials_per_candidate; seed scheme/index M3 не меняются. Candidate ID/порядок не входят в derivation; перестановка кандидатов не меняет наблюдения каждого. Один и тот же trial index имеет один seed у разных сценариев, но разные ветвления могут расходовать RNG по-разному — равенство seed не означает тождественность бросков соответствующих действий или доказанное снижение ошибки сравнения.

Все candidates, окно, positive exact int trials/top_k/max_total_trials и общие поля проверяются до первого runner. `len(candidates) * trials_per_candidate <= max_total_trials` — явный бюджет исполнения; при превышении полный request отклоняется до работы, без неявного уменьшения списка или trials. Каждый candidate оценивается один раз полным пакетом. Несколько candidates исполняются последовательно; опциональный process backend применяется только внутри одного кандидата с явно переданными options. Вложенные pools, автоматический подбор режима и бюджет времени не вводятся.

При runner failure/source mismatch вычисление заканчивается типизированной ошибкой с candidate_id и исходной причиной. Уже вычисленные summaries не выдаются как complete evaluation result. Никаких retries/checkpoints или продолжения после исключения. UNSUPPORTED_OBSERVATIONS — assessment по готовому результату, а не исключение runner. Отчёт хранит общий seed/trials, полный source каждого кандидата и seed scheme; runtime/code provenance остаётся обязанностью application/report adapter, как в M4.

Staged evaluation реализован по [ADR-0018](ADR-0018-staged-ranged-evaluation.md) поверх этого API. Первый evaluator не обещает reuse prefix или адаптивное увеличение N; бюджет будущего повторного полного запуска должен учитывать все реально исполненные trials, пока не появится отдельный контракт incremental evaluation. Universal optimizer, изменение правил, общий battle aggregate и PC/Minion смешанная модель вне решения.

## Порядок продолжения

1. Aggregate-only summary/projection реализованы и проверены; существующие M3 result/service/CLI v1 не менялись.
2. Метрика [подтверждена](../open-questions.md#первая-метрика-m5). Pure single-candidate assessment реализован; точные доли/window, source и unsupported guards проверены без RNG/runner.
3. Bounded evaluation реализован: конечный список соединён с existing runners, бюджетом и source-checked отчётом. [ADR-0018](ADR-0018-staged-ranged-evaluation.md) реализован: явные stages/trials/keep, отдельный selection для продолжения, полный учёт повторных запусков и проверяемая source chain. Генератор численности по [ADR-0019](ADR-0019-ranged-composition-generation.md) реализован: явный резерв участников, неизменные профили/решения, предел составов и полный staged budget. Первый M5 закрыт [аудитом](../audits/m5-readiness.md) в текущем scope; [typed пример](../examples/m5/README.md) проверен в sequential/process. Контракт [JSON balance v1 / CLI balance](ADR-0020-ranged-balance-json-v1.md) реализован полностью в текущем scope: Schema/adapters, application service, кодирование ошибок и CLI balance. Следующий срез — конечный аудит внешней границы M5 и актуализация roadmap. Генерация составов и новые игровые механики остаются отдельными задачами.

Новых Rule IDs, трактовок книг или house rules этот документ не вводит. Book-dependent semantics остаются в ADR-0013/0014; книги для технических срезов повторно не извлекались. Подтверждённая продуктовая метрика отделена от уже проверенной механики. Проверка summary-среза: 1850 tests OK, Python 3.14.5, включая real spawn; compileall/pip check/diff check успешны.

## Реализация конечного списка кандидатов

[balance/ranged_evaluation_models.py](../../src/towr/balance/ranged_evaluation_models.py) содержит frozen/slots модели:

- RangedBalanceCandidate(candidate_id, scenario): непустой ID и уже допущенный NpcRangedScenario — вход существующего симулятора, без самостоятельной генерации профилей.
- RangedBalanceEvaluationRequest(candidates, master_seed, trials_per_candidate, max_total_trials, window, top_k): tuple-normalization, уникальные IDs, typed window, positive exact int top_k/max_total_trials, общие perspective_side/round budget и существующая uint64 validation seed/trials. Производный simulation_requests строится однократно в preflight, недоступен constructor, исключён из repr/equality; replace пересобирает его. planned_trials = len(candidates) * trials_per_candidate. Превышение бюджета отклоняется; top_k больше числа кандидатов допустим и означает «не больше top_k».
- RangedBalanceCandidateResult(candidate_id, assessment) связывает stable ID с уже готовой aggregate-only оценкой.
- RangedBalanceEvaluationResult(source_request, candidates) требует ровно весь исходный список в том же порядке, точные candidate IDs, simulation input и window каждого assessment. Неполные/переставленные/повторные/чужие результаты отклоняются. selected_candidate_ids, total_trials и seed_scheme — производные свойства; их нельзя подставить независимо. Стабильная сортировка по точному расстоянию до target применяется только к window_match=True. Все оценки, включая outside/unsupported, остаются в исходном порядке отчёта.

[application/ranged_evaluation_service.py](../../src/towr/application/ranged_evaluation_service.py): `evaluate_ranged_candidates(request, execution)` принимает полностью проверенный request и явный SimulationExecutionOptions. Кандидаты исполняются последовательно через прежние M3 runners; workers/batch_size передаются без изменений. RNG — стандартный runner default; low-level injection M3 сохранён. После проверки типа/exact source результата выполняются summary projection и pure assessment. Полный compact result не переносится в balance и освобождается до следующего кандидата; application временно держит записи только текущего пакета. Результат хранит inputs и агрегаты, не полный журнал/records.

Любой Exception внутри исполнения/проверки/проекции одного кандидата оборачивается в [RangedBalanceEvaluationError](../../src/towr/application/ranged_evaluation_errors.py) с candidate_id и исходной __cause__, включая notes. Следующие кандидаты не запускаются; partial report, retry и fallback отсутствуют. Неверные типы request/execution дают TypeError до runner; KeyboardInterrupt/SystemExit не оборачиваются. Process caller по-прежнему требует guarded importable main, а cleanup выполняет прежний runner. Execution options/runtime остаются у application caller; этот typed aggregate report не является новым wire форматом или доказательством исполнения.

9 [model tests](../../tests/unit/test_m5_ranged_evaluation.py), 5 [service tests](../../tests/unit/test_m5_ranged_evaluation_service.py) и 2 [integration tests](../../tests/integration/test_m5_ranged_evaluation.py): preflight/types/budget/perspective/rounds, derived/frozen/source/result completeness, exact Fraction ranking и tie-break, outside/unsupported/empty selection, отсутствие records, explicit dispatch, сбой второго кандидата/cause/notes без partial результата, неверный runner result и interrupts. Real sequential/process отчёты совпадают; переименование/перестановка сохраняют оценки по кандидату. Staged search, генерация, CLI balance/JSON, timeout и confidence guarantees не добавлены.

Полный набор: **1876 tests OK**, Python 3.14.5, 60,342 с; compileall/pip check/diff check успешны. Domain/engine/simulation, прежний M4 service и CLI не менялись; правила и seed scheme сохранены.
