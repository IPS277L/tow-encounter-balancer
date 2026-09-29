# ADR-0032: поэтапная оценка явного mixed-списка

Статус: контракт принят в согласованном направлении M7, 2026-09-29. **Pure continuation helper, frozen staged models/status и application service/error реализованы; аудит завершён.** Направление и метрика подтверждены ранее; решение продолжает [аудит ADR-0031](../audits/m7-evaluation-readiness.md) по образцу [ADR-0025](ADR-0025-staged-melee-evaluation.md).

## Основание и граница

Caller задаёт конечный список готовых mixed-сценариев, возрастающие размеры пакетов, keep каждого этапа, общий seed, окно и бюджет. Малый пакет позволяет выбрать кандидатов для более подробного повторного прогона. Сохраняется граница ADR-0028: неподвижные numeric Minions, явные pair ranges/facts/GM decisions, фиксированное оружие и приоритеты. Отбор не меняет scenario, IDs, пары, политики, objective, perspective, round budget или window.

Прямо перечитаны BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112 и BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91. Visited round не обязательно завершён; defeat не означает обязательную смерть. Этап оценки запускает новые экземпляры исходного боя, а не продолжает прежний раунд. Окно/отбор/бюджет — технический контракт; RULE-COMBAT-001/RULE-NPC-002 и книжная механика не меняются, новых house rules нет.

## Реализованный pure typed API

Реализованы отдельные [balance/mixed_staged_evaluation_models.py](../../src/towr/balance/mixed_staged_evaluation_models.py) и [balance/mixed_staged_evaluation.py](../../src/towr/balance/mixed_staged_evaluation.py):

| Тип / функция | Поля или результат |
| --- | --- |
| MixedBalanceStage | trials_per_candidate: int, keep: int |
| MixedStagedEvaluationRequest | candidates: tuple[MixedBalanceCandidate, ...], master_seed: int, stages: tuple[MixedBalanceStage, ...], max_total_trials: int, window: ObjectiveRateWindow; derived planned_trials |
| mixed_continuation_candidate_ids(report: MixedBalanceEvaluationResult) | tuple[str, ...] для следующего этапа в исходном порядке |
| MixedStagedEvaluationStatus | COMPLETED="completed", NO_ELIGIBLE_CANDIDATES="no_eligible_candidates" |
| MixedStagedEvaluationResult | source_request: MixedStagedEvaluationRequest, stage_reports: tuple[MixedBalanceEvaluationResult, ...]; derived status, selected_candidate_ids, planned_trials, total_trials, seed_scheme |

Модели frozen/slotted; входные sequences копируются в tuple, replace повторяет guards. Ranged/Melee stages, candidates, requests и reports отклоняются даже при одинаковых полях. Переиспользуются существующие mixed bounded models и тот же ObjectiveRateWindow из balance.ranged_assessment_models, без переноса shared classes или универсальной иерархии.

Stage trials — exact int в [1, 2**64−1]; keep/max_total_trials — positive exact int. Bool/coercion запрещены, неверные числа дают ValueError, неверные typed objects — TypeError. Stages непусты, trials строго возрастают; keep может расти и превышать число кандидатов, но не возвращает отсеянных. Отдельного top_k нет: keep последнего этапа задаёт итоговый top_k. Один этап допустим.

Preflight проверяет все stages, включая потенциально недостижимые, весь исходный список, точные непустые уникальные IDs, общий uint64 seed, perspective/round budget, окно и полный верхний бюджет до RNG/runner/pool. Admission кандидатов и seed переиспользует MixedBalanceEvaluationRequest первого этапа; матрица всех C×S requests не нужна. Модели не читают JSON и не исполняют simulation.

## Бюджет и повторные пакеты

Для N кандидатов и этапов (t[i], k[i]): U[0]=N, U[i+1]=min(U[i], k[i]); `planned_trials = sum(U[i] * t[i])`. Exact int без overflow/coercion. Если planned превышает max_total_trials, весь request отклоняется заранее, даже если ранний unsupported мог бы уменьшить работу. Нет автоматического сокращения trials, keep или stages.

Общая внутренняя `_stage_request` в models собирает request для service и result guards: текущая упорядоченная подпоследовательность candidates, общий seed/window, trials=t[i], top_k=k[i], **локальный** max_total_trials=len(current candidates)×t[i]. Внешний лимит не подставляется вместо локального бюджета.

Каждый этап исполняет полный пакет с index 0, используя прежнюю схему `towr:npc-mixed-trial:v1`. При одинаковых scenario/RNG/runtime прежний prefix воспроизводится, но вычисляется повторно. Переход 10→100 оплачивает 110 trials, не 100 и не 90. ID/номер этапа не входят в seed. Prefix reuse отсутствует; оценки этапов не являются независимыми выборками и не складываются как уникальные observations. RNG внедряется на прежней simulation boundary. Общий seed разных составов не гарантирует сопоставимых бросков действий или уменьшения статистической ошибки.

`total_trials = sum(report.total_trials for report in stage_reports)` включает повторную работу; total_trials <= planned_trials <= max_total_trials. Остаток бюджета не порождает дополнительные trials. При ошибке нет частичного успешного результата или счётчика потраченных trials. Бюджет не является квотой памяти; успешный результат хранит inputs и aggregates каждого выполненного этапа.

## Промежуточный отбор и завершение

На непоследнем этапе исключить UNSUPPORTED_OBSERVATIONS. Остальные rows, включая outside-window и ROUND_LIMIT, сортировать по exact Fraction abs(goal_rate−target), stable при равенстве. Взять до report.source_request.top_k ближайших, затем вернуть их IDs **в порядке исходных rows**. Следующий input — соответствующая подпоследовательность текущих candidates. Порядок по расстоянию не переносится в следующий tie-break.

Helper требует typed MixedBalanceEvaluationResult; не запускает бой и не меняет report. Bounded selected_candidate_ids по-прежнему означает только попадание в окно: использовать его как continuation нельзя. Все outside/unsupported строки сохраняются в полном report. Любой наблюдавшийся unsupported запрещает продолжение, даже при попадании goal rate в окно. Отсутствие unsupported не доказывает полноту тактики или точность вероятности.

| После полного этапа | Действие / derived status |
| --- | --- |
| Непоследний, continuation непуст | Выполнить следующий stage spec |
| Непоследний, continuation пуст | NO_ELIGIBLE_CANDIDATES, selected=(); следующие пустые reports не создавать |
| Последний выполнен | COMPLETED, даже если все unsupported или selected пуст; выбор только из последнего bounded report |

При одном этапе сразу действует последнее правило. Ранние попадания не возвращаются при позднем отсеве; outside не становится итоговым выбором. Все четыре доли сохраняют знаменатель N: round_limit не поражение/ничья, unsupported не удаляется и не перезапускается.

## Полная цепочка источников

Result требует typed source и непустую tuple typed mixed reports, длиной не больше числа stages. Первый report содержит всех исходных candidates; каждый следующий — ровно continuation предыдущего. Полный report.source_request равен `_stage_request` по значению: ID/scenario/pairs/facts/policies/objective/seed/window/trials/local budget/top_k и порядок, равная копия допустима.

Пропущенные/повторные/переставленные reports, возвращённые отсеянные IDs, чужие источники и reports после пустого continuation запрещены. Укороченная цепочка допустима только после непоследнего этапа с пустым continuation. Произвольный prefix при наличии пригодных кандидатов не является завершённым результатом. Полная цепочка всегда COMPLETED, в том числе при all-unsupported в финале.

Status/selected/budgets/seed_scheme производные, не init fields. Успешный result не хранит per-trial records, full simulation results, RNG, execution options или JSON. Guards проверяют согласованность ручных aggregates, а не доказывают их происхождение.

## Application и ошибки

Реализованы [application/mixed_staged_evaluation_service.py](../../src/towr/application/mixed_staged_evaluation_service.py) и [application/mixed_staged_evaluation_errors.py](../../src/towr/application/mixed_staged_evaluation_errors.py):

```python
def evaluate_mixed_candidates_staged(
    request: MixedStagedEvaluationRequest, execution: SimulationExecutionOptions,
) -> MixedStagedEvaluationResult: ...

class MixedStagedEvaluationError(RuntimeError):
    stage_index: int  # from zero
    candidate_id: str | None
```

Typed request/options до работы. Один existing evaluate_mixed_candidates на каждый реально достигнутый этап, тот же объект execution; последовательные этапы/кандидаты, process только внутри текущего кандидата. Используются existing SimulationExecutionOptions без переноса; новых pools/scheduler/auto backend нет. Сохраняются importable guarded main и cleanup existing runner.

Typed MixedBalanceEvaluationResult и полный source проверяются до следующего этапа. MixedBalanceEvaluationError оборачивается в MixedStagedEvaluationError(index, candidate_id), сохраняя всю цепочку __cause__ до исходной ошибки и worker notes. Другие Exception при построении/исполнении/проверке этапа или continuation дают candidate_id=None. Preflight/options и финальная ошибка staged result constructor распространяются напрямую, без вымышленного stage index. KeyboardInterrupt/SystemExit не оборачиваются. Нет следующего вызова после сбоя, partial success, retry/fallback/checkpoint; traceback может удерживать промежуточные объекты.

## Конечные примеры и матрица

Синтетические aggregates, не Monte Carlo ожидания: окно [9/20,1/2,11/20], порядок A,B,C,D, stages=(10,2),(100,1), planned=4×10+2×100=240.

| ID | Целей из 10 | Unsupported | Продолжение |
| --- | --- | --- | --- |
| A | 4 | 0 | Да, расстояние 1/10 |
| B | 7 | 0 | Нет, расстояние 1/5 |
| C | 5 | 1 | Нет, unsupported при goal rate 1/2 |
| D | 6 | 0 | Да, расстояние 1/10 |

Bounded selected=(), continuation=(A,D). Финал 49/100 и 51/100: selected=(A), total=240, COMPLETED. При 45/100 и 55/100 обе границы включены, равенство оставляет A. При финальных 40/100 и 60/100 selected пуст; ранние оценки не возвращаются.

- Если D ближе A, следующий input всё равно (A,D). Пригоден только A: total=40+100=140. Все unsupported в первом report: total=40, NO_ELIGIBLE_CANDIDATES. Все unsupported только в финале: COMPLETED и пустой выбор.
- Бюджет 239 отклоняется, 240 допускается; расчёт 4×10+2×90=220 исключён. Для (10,2),(100,5),(1000,1) planned=2240: рост keep не возвращает отсеянных. Один этап (10,10): planned=40.
- N=2**60+1 требует Fraction: float может смешать разные расстояния. All-round-limit пригоден с goal=0; all-unsupported не выбирается даже в point window 0.

[staged_contract_probe.py](../examples/m7/staged_contract_probe.py) и [вывод](../examples/m7/staged_contract_probe.output.txt) проверяют конечную арифметику на existing mixed bounded reports, включая две разные формы сценария 3×2/2×2. Probe не реализует staged models/service/chain guards, не исполняет бой/RNG/pool и не доказывает достижимость синтетических observations.

| Срез | Обязательные проверки реализации |
| --- | --- |
| Helper | Mixed type, отказ ranged/Melee; outside continuation против bounded selected; unsupported/round_limit; Fraction, ties/cutoff, восстановление порядка, большие N |
| Stage/request | Frozen/tuple copy/replace; uint64/exact positive ints без bool/coercion; все stages до исполнения, рост trials/keep; общий seed/perspective/round budget/window, бюджет 240; один/три этапа; отказ ranged/Melee |
| Result | Полная или законно оборванная цепочка; complete/no-eligible/final unsupported; бюджеты 240/140/40; нет возврата ранних попаданий; full source/seed/trials/window/local budget/top_k, pair order/facts/GM approvals; пропуски/лишние/возвращённые IDs; равная копия, derived/frozen/no records |
| Service | Exact bounded calls/options; полный повтор с index 0; outside continuation/early stop; type/source до следующего вызова; stage/candidate/cause/notes; неизвестный candidate=None; preflight/final constructor/BaseException boundaries; no partial/retry/fallback |
| Integration | Real sequential/spawn reports/selected равны, input/global RNG/cleanup; rename/reorder с намеренным tie-break; pool startup error chain; scripted mixed unsupported при goal внутри окна, четыре исхода сохраняются; без точного Monte Carlo процента |

Порядок реализации: (1) pure helper и frozen models/status с общей внутренней `_stage_request`, deterministic tests; (2) application service/error, deterministic и real-backend tests; (3) аудит и самостоятельный production-пример. Существующие [Melee model tests](../../tests/unit/test_m6_melee_staged_evaluation.py), [service tests](../../tests/unit/test_m6_melee_staged_evaluation_service.py) и [integration](../../tests/integration/test_m6_melee_staged_evaluation.py) — технический образец, не замена mixed tests.

Domain/engine/simulation, existing bounded API, ranged/Melee formats и правила не меняются. Generation, prefix reuse, JSON/CLI, confidence/presets, новые действия, движение/смена оружия, PC/магия и общий battle aggregate вне контракта.

## Проверка контрактного среза

2026-09-29, Windows / Python 3.14.5: finite probe прошёл из корня и отдельного cwd с абсолютным PYTHONPATH, stdout равен, stderr пуст; вывод сохранён. Отдельный запуск с запрещёнными RNG/runner/evaluator/pool calls прошёл, global RNG неизменен. **60 existing tests OK (10,789 с)**: 32 mixed assessment/list/service и 28 Melee staged tests, включая real sequential/spawn. Это проверка existing APIs и образца; tests будущего mixed staged API ещё не добавлены.

Compileall src/tests/tools/docs/examples/m7, 1941 локальный Markdown-путь, public imports probe и diff/whitespace успешны. SHA-256 всех 652 файлов src/tests/tools совпали со снимком начала среза. Полный набор не повторялся; последняя полная проверка предыдущего аудита — 2446 OK. Все 20 исходных dirty/untracked файлов сохранены; добавлены ADR, probe/output и обновлена документация. Python 3.12/другие ОС, installed wheel и performance не проверялись; commit/push не выполнялись.

## Реализация helper и моделей

2026-09-29: pure mixed_continuation_candidate_ids и frozen/slotted MixedBalanceStage/Request/Result/Status реализованы с общей внутренней `_stage_request`. Все stages/common fields и верхний бюджет проверяются до исполнения; результаты требуют полную цепочку либо законный early stop при пустом continuation. Exact Fraction отбор допускает outside-window для уточнения, восстанавливает исходный порядок и исключает любой unsupported. Итоговый выбор только из последнего этапа; full final с all-unsupported имеет COMPLETED и пустой выбор.

[19 deterministic tests](../../tests/unit/test_m7_mixed_staged_evaluation.py): outside/unsupported/round_limit, ties/большие N, 1–3 этапа/рост keep, бюджеты 240/140/40/1140, partial/extra/reordered/foreign chain, exact seed/trials/window/local budget/keep. Две mixed-формы 3×2/2×2 сохраняют свои sources; изменение pair order, GM outnumbering approval, escape facts или порядка objective отклоняется на первом и последнем этапе при тех же observations. Frozen/tuple copy/replace и pickle сохраняют class identities; ranged/Melee families отклоняются. Models/helper не запускают RNG/runner/pool/JSON и не удерживают full results/records/journals.

Следующий срез — application/mixed_staged_evaluation_service.py и mixed_staged_evaluation_errors.py по разделу выше: existing bounded call на каждый этап, полный source до продолжения и stage/candidate/cause/notes без partial/retry/fallback. Затем real-backend проверки и отдельный аудит; правила и simulation не менялись.

Проверка среза моделей: **61 профильный test OK (0,203 с)** с M5/M6 staged и mixed bounded regression; **2465 tests полного набора OK (267,398 с)**, Windows / Python 3.14.5. Compileall, 1962 локальных Markdown-пути, AST import boundaries и diff/whitespace успешны. Public request planned=48 и прежний probe проверены из отдельного cwd. Все 23 исходных dirty/untracked файла сохранены, SHA-256 всех 652 существовавших файлов src/tests/tools прежние; добавлены два balance модуля и один test-файл, обновлена документация. Application service ещё не реализован. Python 3.12/другие ОС, installed wheel и performance не проверялись; commit/push не выполнялись.

## Реализация application service

2026-09-29: evaluate_mixed_candidates_staged исполняет достигнутые stages через existing bounded evaluator с тем же execution options. Typed request/options проверяются заранее, typed/full source каждого report — до следующего этапа. Общая `_stage_request`, исходный parent request в result и полный повтор пакетов с index 0 сохранены. MixedStagedEvaluationError содержит zero-based stage_index и candidate_id либо None; cause chain/worker notes сохраняются без partial/retry/fallback. Preflight/final constructor/BaseException распространяются напрямую.

[9 unit tests](../../tests/unit/test_m7_mixed_staged_evaluation_service.py) проверяют exact calls/options, равную копию source, outside continuation, reduced budget/early stop, полный повтор в обоих backend, сбой второго этапа без третьего с candidate/cause/notes. Mixed source с чужими seed/pair order/GM approvals и ranged/Melee request/report отклоняются. Проверены ошибки сборки stage/continuation, финального result и interrupts.

[3 integration tests](../../tests/integration/test_m7_mixed_staged_evaluation.py): реальные sequential/spawn reports двух mixed-составов, replay/rename/reorder с учётом tie-break, input/global RNG/cleanup и pool startup failure с полной цепочкой ошибок. Scripted 2×2: prefix N=3 даёт counts=1/1/1/0 и 16 Attack/5 visited, остаётся outside point window 1/4 и продолжается; полный N=4 повтор даёт 1/1/1/1, 17 Attack/6 visited и точное попадание goal=1/4, но unsupported исключает выбор. Total=7, COMPLETED. Если первый stage уже N=4, следующий N=5 не исполняется: total=4 из planned=9, NO_ELIGIBLE_CANDIDATES. RNG внедрён на existing simulation boundary, production service нового параметра не получает. Monte Carlo процент/победитель не закреплён.

Следующий срез — аудит staged mixed evaluation: сопоставить все 31 tests ADR-0032 с контрактом, подготовить самостоятельный public пример и сохранённый вывод, проверить позднюю ошибку без partial stdout, budget/chain/source/cleanup и ограничения. Generation/JSON/CLI и новые игровые действия не входят.

Проверка application-среза: **32 профильных tests OK (16,398 с)** с M5/M6 staged service/integration regression; **2477 tests полного набора OK (270,788 с)**, Windows / Python 3.14.5. Compileall, 1981 локальный Markdown-путь, AST import boundaries и diff/whitespace успешны. Guarded public API snippet прошёл из отдельного cwd: full sequential/process reports равны, planned/actual=48 на вызов, stderr пуст. Все 26 исходных dirty/untracked файлов сохранены; SHA-256 всех 655 исходных файлов src/tests/tools прежние, добавлены два application модуля и два test-файла. Документация синхронизирована; Python 3.12/другие ОС, installed wheel и performance не проверялись. Commit/push не выполнялись.

## Аудит staged evaluation

2026-09-29: [аудит](../audits/m7-staged-evaluation-readiness.md) сопоставил все 31 tests с матрицей контракта. [Самостоятельный пример](../examples/m7/mixed_staged_evaluation.py) двух mixed-составов со stages 8/32, keep=1 проверен в sequential/process, сохранён вывод: full reports равны, planned/actual=48 на вызов, input/global RNG/cleanup сохранены. Последний report имеет unsupported внутри окна и пустой итоговый выбор при COMPLETED; assertions не фиксируют Monte Carlo процент/победителя. Ошибка второго этапа после 16 реальных trials первого сохраняет stage/candidate/cause/notes, stdout пуст, process не запускается. Production исправлений не потребовалось. Следующий контракт — ограниченная генерация mixed-составов из явного резерва, без реализации генератора или JSON/CLI в этом аудите.

Проверка аудита: **2477 tests полного набора OK (278,851 с)**, Windows / Python 3.14.5. Compileall, 2019 локальных Markdown-путей, AST import boundaries и diff/whitespace успешны. Пример проверен из корня и отдельного cwd: одинаковый stdout, пустой stderr, 192 trials суммарно. SHA-256 всех 659 файлов src/tests/tools прежние; 30 исходных dirty/untracked файлов сохранены. Добавлены аудит/пример/вывод, обновлена документация; новых unittest tests нет. Python 3.12/другие ОС, installed wheel и performance не проверялись. Commit/push не выполнялись.
