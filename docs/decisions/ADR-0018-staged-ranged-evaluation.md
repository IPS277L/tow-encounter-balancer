# ADR-0018: поэтапная оценка конечного списка M5

Статус: typed staged API реализован, 2026-09-28; 14 model + 7 service unit и 2 integration tests. Основа — готовый [bounded evaluator](ADR-0017-ranged-candidate-assessment.md) и подтверждённая пользователем метрика цели за лимит с явным окном. Новых игровых правил и house rules нет.

## Основание и граница

[Исходный дизайн](../TOWR_Combat_Simulator_&_Encounter_Balancer_—_Context_and_Technical.md), раздел 21, предлагает сначала оценить много кандидатов малым числом прогонов, затем уточнить лучших большими пакетами. Примеры 1 000 / 10 000 / 100 000 не становятся defaults. Разделы 19–20 о пресетах и взвешенной длительности и раздел 22 о генерации остаются за границей этого решения.

Оценивается прежний явно переданный конечный список допущенных Minion-сценариев. Сценарий каждого кандидата, его ID, общий master_seed, окно, perspective_side и round budget неизменны между этапами. Различаются только подмножество кандидатов и число trials. Balance работает с inputs/aggregates; application вызывает существующий bounded evaluator. Domain/engine/simulation и M4 JSON/CLI не меняются.

## Реализованный typed API

Модели входа/отчёта ниже — frozen/slots dataclasses с tuple-normalization и повторной validation при replace. Ошибка исполнения — отдельный RuntimeError; состояние завершения задаёт enum RangedStagedEvaluationStatus.

| Модель / операция | Контракт |
| --- | --- |
| RangedBalanceStage(trials_per_candidate, keep) | Явный размер полного пакета и верхнее число сохраняемых кандидатов |
| RangedStagedEvaluationRequest(candidates, master_seed, stages, max_total_trials, window) | Прежние RangedBalanceCandidate, непустые ordered tuples candidates/stages, один общий seed/window и верхний бюджет всей работы |
| ranged_continuation_candidate_ids(report) | Чистая функция над RangedBalanceEvaluationResult: до report.source_request.top_k пригодных кандидатов для уточнения, в исходном порядке отчёта |
| RangedStagedEvaluationResult(source_request, stage_reports) | Непустая цепочка полных RangedBalanceEvaluationResult; остановка, final selected IDs, total_trials и seed_scheme производные |
| evaluate_ranged_candidates_staged(request, execution) | Application orchestration над evaluate_ranged_candidates; прежние явные SimulationExecutionOptions для всех этапов |
| RangedStagedEvaluationError(stage_index, candidate_id) | Application error с индексом этапа от нуля, ID при известном кандидате и сохранённым __cause__ |

Stages могут содержать один этап: это bounded evaluation с дополнительной оболочкой отчёта. Trials — exact int от 1 до 2**64 − 1, строго возрастают между этапами. Keep и max_total_trials — positive exact int, bool/float/строки не преобразуются. Keep может превышать число входных кандидатов; это лимит «до keep», а не требование дополнить список. Отдельного top_k в staged request нет: keep последнего этапа задаёт итоговый top_k. Равные или убывающие trials отклоняются; увеличение keep допустимо, но не возвращает ранее отсеянных кандидатов.

До первого runner проверяются **все** stage specs, включая потенциально недостижимые, прежние ограничения кандидатов/уникальных ID, typed window, uint64 seed, общие perspective/round budget и полный верхний бюджет. Не требуется держать N × stages simulation requests: прежний bounded request строится для реально исполняемого этапа. Неверные input/options отклоняются до работы.

## Продолжение и окончательный выбор

На каждом непоследнем этапе кандидаты со status=UNSUPPORTED_OBSERVATIONS исключаются из продолжения. Их строки остаются в полном отчёте; retry для них отсутствует. Все остальные, **включая outside-window**, ранжируются по точному Fraction-расстоянию abs(objective_achieved_rate − target). Берутся до keep ближайших; при равенстве решает исходный порядок входного списка. Это отбор для уточнения наблюдаемой оценки, без обещания соответствия окну или статистической гарантии.

Выбранное подмножество передаётся следующему этапу в **исходном порядке кандидатов**, а не в порядке расстояния. Поэтому tie-break следующих этапов не зависит от предыдущего ranking. Helper возвращает IDs именно в этом порядке; область выбора определяется расстоянием и keep. Вход каждого этапа является упорядоченной подпоследовательностью первоначального списка.

`stage_report.selected_candidate_ids` сохраняет прежнее значение bounded API: только window_match=True. На промежуточном этапе оно описывает локальное попадание в окно и **не используется** как список продолжения. Например, отсутствие попаданий при наличии пригодных outside-window оценок не останавливает уточнение.

Если после непоследнего этапа нет пригодных кандидатов, работа штатно заканчивается с производным status=NO_ELIGIBLE_CANDIDATES. Последующие пустые reports не создаются, final selected_candidate_ids=(). Промежуточные попадания предыдущих этапов не возвращаются как окончательные результаты.

Если последний этап выполнен, status=COMPLETED, даже когда никто не попал в окно или все получили unsupported. Итоговые selected_candidate_ids равны selected_candidate_ids **только последнего** bounded report: до keep подходящих по расстоянию и исходному порядку при равенстве. Если подходящих нет, итог пуст; возврата к более грубому этапу или ближайшего outside-window кандидата нет. В одноэтапном запросе сразу действует это правило.

ROUND_LIMIT по-прежнему пригоден для ограниченной по времени метрики, остаётся отдельным исходом и входит в знаменатель. Unsupported не превращается в defeat или exception. Counts/means предыдущих этапов не складываются с финальными для новой оценки.

## Seeds и бюджет

Каждый этап вызывает bounded evaluator заново, с тем же master_seed и схемой towr:npc-ranged-trial:v1, начиная с trial index 0. При неизменных scenario/RNG/runtime предыдущий prefix воспроизводится, но **исполняется повторно**. Prefix reuse, incremental runner, независимость наблюдений разных этапов и confidence intervals не обещаются. Общий seed разных кандидатов не доказывает снижение ошибки сравнения.

Для N кандидатов и S этапов с trials t[i], keep k[i] верхнее число кандидатов задаётся U[0]=N, U[i+1]=min(U[i], k[i]). Производное planned_trials = сумма U[i] × t[i]. Если planned_trials > max_total_trials, весь запрос отклоняется до исполнения, даже если фактическое раннее отсеивание могло бы уложиться. Бюджет не уменьшает stages/trials/keep автоматически.

Фактический total_trials полного staged result равен сумме total_trials сохранённых stage reports; он не превышает planned_trials. Это количество повторно исполненных прогонов, а не число уникальных seeds. Каждый bounded stage request получает candidates текущего этапа, общий master_seed/window, trials_per_candidate=t[i], top_k=k[i] и точный локальный max_total_trials=len(candidates) × t[i]. Неиспользованный лимит не расходуется на дополнительные прогоны. Ошибка исполнения не возвращает отчёт о фактическом числе частично завершённых trials.

## Проверяемая цепочка отчётов

Staged result хранит source_request и tuple полных bounded reports, включая outside/unsupported строки каждого выполненного этапа. Никаких per-trial records/full simulation result, RNG, runtime options или JSON внутри balance result. Seed scheme и бюджеты производные; runtime/code provenance остаётся обязанностью внешнего caller.

Конструктор проверяет typed source/reports и точное равенство каждого report.source_request ожидаемому bounded stage request, включая локальный бюджет/top_k. Первый этап обязан содержать всех исходных кандидатов; каждый следующий — ровно результат continuation предыдущего, в исходном порядке, с неизменными ID/scenario/seed/window и trials своего stage spec. Пропуски, повторы, перестановки, чужие источники и отчёты после исчерпания списка запрещены.

Цепочка может завершиться только после последнего stage spec либо после непоследнего отчёта с пустым continuation. Пустая цепочка или произвольно укороченный prefix не являются результатом. Status, selected IDs, total_trials, planned_trials и seed_scheme не принимаются как независимые поля. Эти guards проверяют согласованность, но не доказывают происхождение вручную созданных агрегатов.

## Исполнение и ошибки

Этапы и кандидаты внутри них исполняются последовательно; process backend применяется только внутри текущего кандидата по прежним options. Нет вложенных pools, смены backend между этапами или изменения low-level injectable RNG контракта. Сохраняются требования guarded importable main и cleanup прежнего runner.

RangedBalanceEvaluationError оборачивается в RangedStagedEvaluationError с текущим stage_index и тем же candidate_id; цепочка __cause__ сохраняет исходное исключение и notes. При неверном типе/source возвращённого stage report либо другой ошибке этапа candidate_id=None: нельзя приписывать сбой конкретному кандидату без основания. Проверка результата выполняется до запуска следующего этапа. Следующих вызовов, partial complete report, retry/fallback/checkpoint нет. KeyboardInterrupt/SystemExit не оборачиваются. Синтаксические/типовые ошибки запроса и options остаются preflight errors без stage index.

## Детерминированные примеры границ

Это синтетические агрегаты для проверки контракта, а не измеренные вероятности или пресеты. Общее окно [9/20, 11/20], target=1/2. Исходный порядок A, B, C, D; stages=(10 trials, keep=2), (100 trials, keep=1). Верхний бюджет: 4×10 + 2×100 = **240**, а не 220.

| Кандидат | Целей из 10 | Unsupported из 10 | Продолжение |
| --- | --- | --- | --- |
| A | 4 | 0 | Да: расстояние 1/10, первый при равенстве |
| B | 7 | 0 | Нет: расстояние 1/5 |
| C | 5 | 1 | Нет: непригоден, хотя observed rate равен target |
| D | 6 | 0 | Да: расстояние 1/10 |

У первого отчёта selected=(), но continuation=(A,D). На последнем этапе A достигает цели 49/100, D — 51/100, unsupported нет: итог selected=(A), total_trials=240, status=COMPLETED. Обе границы 45/100 и 55/100 включены; при таком равенстве расстояний также победил бы A.

- Если на первом этапе пригоден только A, следующий report содержит только A; actual total=40+100=140, верхний бюджет остаётся 240.
- Если все четыре имеют unsupported, сохраняется один полный report: status=NO_ELIGIBLE_CANDIDATES, actual=40, selected=(). Если только финальный этап имеет все unsupported, status=COMPLETED и selected=().
- Если в финале A=40/100 и D=60/100 без unsupported, оба пригодны, но selected=(); промежуточный отбор не означает итогового попадания.
- Если на первом этапе A=4/10, D=5/10 (B дальше, C unsupported), по расстоянию D лучше A, но следующий input всё равно (A,D). Финальное равенство решается в пользу A.
- При max_total_trials=239 запрос отклоняется до RNG; при 240 допускается. Нельзя принять 239, рассчитывая на раннее отсеивание.
- Для одного этапа (10, keep=10) верхний бюджет равен 40; действуют только окончательные window_match правила. Keep не создаёт недостающие кандидаты.

## Реализация и проверки

Реализованы [balance/ranged_staged_evaluation_models.py](../../src/towr/balance/ranged_staged_evaluation_models.py) (stage/request/result/status), [ranged_staged_evaluation.py](../../src/towr/balance/ranged_staged_evaluation.py) (pure continuation helper), [application service](../../src/towr/application/ranged_staged_evaluation_service.py) и [error](../../src/towr/application/ranged_staged_evaluation_errors.py) поверх неизменного bounded evaluator. _stage_request — внутренняя общая сборка точного локального request для service и result guards; новый runner или RNG не добавлен. Общий optimizer и CLI/JSON balance отсутствуют.

14 [model tests](../../tests/unit/test_m5_ranged_staged_evaluation.py) покрывают примеры и бюджеты 240/140/40, точные ties и float-collapse, 1–3 этапа, рост keep без возврата кандидатов, ROUND_LIMIT, preflight, frozen/replace, source/order/chain guards и отсутствие records. 7 [service tests](../../tests/unit/test_m5_ranged_staged_evaluation_service.py) проверяют exact requests/options, полные повторные пакеты с index 0, раннюю остановку, продолжение outside-window, сбой второго этапа с полной cause/notes chain, чужой report до следующего вызова и interrupts. 2 [integration tests](../../tests/integration/test_m5_ranged_staged_evaluation.py) сравнивают реальные sequential/process отчёты, переименование IDs и pool startup failure без fallback. Конкретная Monte Carlo-вероятность не ожидается.

Генератор численности по [ADR-0019](ADR-0019-ranged-composition-generation.md) реализован: явный резерв участников, неизменные профили/решения, предел составов и полный staged budget. Первый M5 закрыт [аудитом](../audits/m5-readiness.md) в текущем scope; [typed пример](../examples/m5/README.md) проверен в sequential/process. Контракт [JSON balance v1 / CLI balance](ADR-0020-ranged-balance-json-v1.md) реализован на уровне packaged Schema и pure adapters с frozen command/result; следующий срез — application service, кодирование ошибок и CLI balance.

Проверка реализации: **1899 tests OK**, Python 3.14.5, 51,479 с; compileall/pip check/diff check успешны. На старте уже имелись незакоммиченные изменения документации и этот ADR; они сохранены. Domain/engine/simulation, bounded evaluator и M4 не менялись. Prefix reuse, performance gains, генерация составов и CLI balance не заявляются.

При реализации ADR-0019 stage admission и расчёт planned_trials выделены в общие внутренние _validate_stages/_planned_trials того же models-модуля. Это переиспользование прежних guards/формулы при preflight ещё не материализованного семейства; публичный staged API и исполнение не изменены.
