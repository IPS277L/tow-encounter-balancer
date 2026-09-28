# ADR-0025: поэтапная оценка явного Melee-списка

Статус: принято, 2026-09-29. **Pure continuation helper, frozen stage/request/result/status и staged application service/error реализованы.** Направление и метрика подтверждены ранее. Это техническое продолжение [аудита ADR-0024](../audits/m6-evaluation-readiness.md), по образцу [ADR-0018](ADR-0018-staged-ranged-evaluation.md).

## Основание и граница

Сначала оценить явно заданные альтернативы небольшим пакетом, затем уточнить оставшиеся большим. Число этапов, trials, keep и окно задаёт caller; presets/defaults и confidence policy не вводятся. Игровая граница ADR-0021 сохраняется: неподвижные numeric Minions с явными facts/GM decisions. Отбор не меняет scenario, ID, цель, perspective, round budget, seed или окно кандидата.

Непосредственно проверены BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112 и BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91: visited round не обязательно завершён, defeat не обязательно означает смерть. Этап оценки — повторный набор независимых боёв, а не продолжение боевого раунда. Окно и алгоритм отбора не являются правилами книги или house rule. Новых Rule IDs нет.

## Реализованный pure typed API

Реализованы [balance/melee_staged_evaluation_models.py](../../src/towr/balance/melee_staged_evaluation_models.py) и [balance/melee_staged_evaluation.py](../../src/towr/balance/melee_staged_evaluation.py):

| Тип / функция | Поля или результат |
| --- | --- |
| MeleeBalanceStage | trials_per_candidate: int, keep: int |
| MeleeStagedEvaluationRequest | candidates: tuple[MeleeBalanceCandidate, ...], master_seed: int, stages: tuple[MeleeBalanceStage, ...], max_total_trials: int, window: ObjectiveRateWindow; derived planned_trials |
| melee_continuation_candidate_ids(report: MeleeBalanceEvaluationResult) | tuple[str, ...] для следующего этапа в исходном порядке |
| MeleeStagedEvaluationStatus | COMPLETED="completed", NO_ELIGIBLE_CANDIDATES="no_eligible_candidates" |
| MeleeStagedEvaluationResult | source_request: MeleeStagedEvaluationRequest, stage_reports: tuple[MeleeBalanceEvaluationResult, ...]; derived status, selected_candidate_ids, planned_trials, total_trials, seed_scheme |

Все модели frozen/slotted, входные sequences копируются в tuple; replace повторяет guards. Melee stages/request/result/status отдельные: ranged objects не принимаются по совпадению полей/enum values. Переиспользуются те же ObjectiveRateWindow и существующие Melee bounded candidates/reports, без переноса shared classes и generic hierarchy.

Stage trials — exact int в [1, 2**64−1], keep/max_total_trials — positive exact int, без bool/coercion. Ошибочные числовые значения дают ValueError; неверные typed objects — TypeError. Stages непусты и trials строго возрастают; keep может расти или превышать число кандидатов, но не возвращает отсеянных. Отдельного top_k нет: keep последнего этапа задаёт финальный top_k. Один этап допустим.

Preflight проверяет **все** stages (в том числе потенциально недостижимые), непустые typed candidates, точные непустые уникальные IDs, общий uint64 master_seed, perspective_side и initial.max_rounds, typed window и полный верхний бюджет. Admission кандидатов/seed переиспользует MeleeBalanceEvaluationRequest. Можно построить bounded request первого этапа, но не матрицу requests C×S. Ни runner/RNG/pool, ни JSON не вызываются моделями.

## Бюджет и seeds

При N кандидатах и этапах (t[i], k[i]): U[0]=N, U[i+1]=min(U[i], k[i]); `planned_trials = sum(U[i] * t[i])`. Считать exact int без overflow/coercion. Превышение max_total_trials отклоняет весь request до исполнения, даже если ранний unsupported мог бы сократить работу. Нет автоматического урезания этапов, trials или keep.

Каждый bounded request получает текущую упорядоченную подпоследовательность candidates, общий seed/window, trials=t[i], top_k=k[i], **локальный** max_total_trials=len(current candidates)×t[i]. Общая внутренняя `_stage_request` в models собирает одинаковый request для result guards и service. Внешний max_total_trials не подставляется вместо локального бюджета.

Каждый этап запускает полный пакет с index 0 и прежней схемой `towr:npc-melee-trial:v1`. При одинаковом scenario/RNG/runtime прежний prefix воспроизводится, но **вычисляется повторно**. Например, переход 10→100 оплачивает 110, не 100 и не 90. Candidate ID и этап не добавляются в seed. Prefix reuse/incremental runner отсутствуют; оценки этапов нельзя считать независимыми выборками или складывать как уникальные observations. RNG внедряется на прежней simulation boundary. Общий seed разных составов не гарантирует сопоставимых бросков действий или уменьшения статистической ошибки.

`total_trials = sum(report.total_trials for report in stage_reports)` — реально выполненные полные пакеты, включая повторные seeds; `total_trials <= planned_trials <= max_total_trials`. Неизрасходованный лимит не порождает дополнительную работу. Ошибка не возвращает счётчик частично выполненных trials. Бюджет не является RSS-квотой: результат сохраняет inputs и агрегаты всех исполненных этапов.

## Промежуточный отбор и завершение

На непоследнем этапе исключить только UNSUPPORTED_OBSERVATIONS; прочие rows (включая outside-window и ROUND_LIMIT) сортировать по exact Fraction abs(goal_rate−target), stable при равенстве. Взять до report.source_request.top_k ближайших, затем вернуть IDs **в порядке исходных rows**. Следующий input — эта подпоследовательность текущих candidates, поэтому tie-break не зависит от расстояний предыдущего этапа.

Helper проверяет typed MeleeBalanceEvaluationResult, не запускает бой и не меняет report. `stage_report.selected_candidate_ids` по-прежнему означает только попадания в окно; использовать его как continuation нельзя. Все outside/unsupported строки сохраняются в полном отчёте этапа. Пригодность не доказывает истинной вероятности и не гарантирует попадания после уточнения.

| Состояние после полного этапа | Действие / производный status |
| --- | --- |
| Этап непоследний, continuation непуст | Запустить следующий stage spec |
| Этап непоследний, continuation пуст | NO_ELIGIBLE_CANDIDATES; итоговые selected=(); пустые следующие reports не создавать |
| Последний этап исполнен | COMPLETED, даже если selected пуст или все observations unsupported; selected только из последнего bounded report |

Промежуточный успех не возвращается при позднем отсеве; ближайший outside-window не становится итоговым выбором. В одноэтапном request сразу действует последнее правило. Четыре Fraction rates и denominator всех trials сохраняются: round_limit не поражение/ничья, unsupported не удаляется из знаменателя и не перезапускается.

## Проверяемая цепочка

Result требует typed source и непустую tuple typed Melee reports длиной не более числа stages. Первый report обязан иметь всех исходных кандидатов; каждый следующий — ровно continuation предыдущего, в прежнем порядке и с неизменными ID/scenario/seed/window. Сравнивать весь report.source_request по значению с `_stage_request`, включая trials, local max_total_trials и keep/top_k; равная копия допустима.

Запрещены пропуски/повторы/перестановки, чужой source/window/scenario, возвращённые ранее отсеянные IDs, reports после пустого continuation. Укороченная цепочка допустима только после непоследнего этапа с пустым continuation. Произвольный prefix при наличии пригодных кандидатов не является complete result. Полная цепочка заканчивается COMPLETED, в том числе при all-unsupported последнем этапе.

Status/selected IDs/budgets/seed_scheme производные, не независимые init fields. В графе successful result нет per-trial records, full simulation results, RNG, execution options или JSON. Source guards проверяют согласованность ручных агрегатов, а не доказывают их происхождение; runtime/code provenance остаётся у caller.

## Application и ошибки

Реализованы [application/melee_staged_evaluation_service.py](../../src/towr/application/melee_staged_evaluation_service.py) и [melee_staged_evaluation_errors.py](../../src/towr/application/melee_staged_evaluation_errors.py):

```python
def evaluate_melee_candidates_staged(
    request: MeleeStagedEvaluationRequest, execution: SimulationExecutionOptions,
) -> MeleeStagedEvaluationResult: ...

class MeleeStagedEvaluationError(RuntimeError):
    stage_index: int  # from zero
    candidate_id: str | None
```

Проверить typed request/options до работы. Один вызов existing evaluate_melee_candidates на каждый реально достигнутый этап, один и тот же объект execution. Этапы и candidates последовательны, process применяется только внутри текущего candidate. Новых pools/scheduler/автовыбора backend нет. Сохраняются importable guarded main и cleanup existing runner.

После каждого вызова проверить typed MeleeBalanceEvaluationResult и полный exact source **до следующего этапа**. MeleeBalanceEvaluationError оборачивается в MeleeStagedEvaluationError(index, candidate_id); цепочка `__cause__` до исходного исключения и worker notes сохраняется. Другая Exception при построении/исполнении/проверке этапа даёт candidate_id=None, без вымышленного виновника. Preflight request/options и финальная ошибка конструктора staged result распространяются напрямую, без вымышленного stage index. KeyboardInterrupt/SystemExit не оборачиваются. Нет последующих вызовов, partial successful result, retry/fallback/checkpoint. Traceback может удерживать промежуточные объекты.

## Конечные примеры

Это синтетические агрегаты, не Monte Carlo-ожидания. Окно [9/20,1/2,11/20], исходный порядок A,B,C,D; stages=(10,keep=2),(100,keep=1); planned=4×10+2×100=240.

| ID | Целей из 10 | Unsupported | Промежуточный отбор |
| --- | --- | --- | --- |
| A | 4 | 0 | Да, расстояние 1/10 |
| B | 7 | 0 | Нет, расстояние 1/5 |
| C | 5 | 1 | Нет, unsupported при observed rate 1/2 |
| D | 6 | 0 | Да, расстояние 1/10 |

У bounded report selected=(), но continuation=(A,D). Финал A=49/100, D=51/100 без unsupported: selected=(A), total=240, COMPLETED. При A=45/100,D=55/100 обе границы включены, точное равенство снова оставляет A.

- Если в первом report A=4/10,D=5/10, D ближе, но следующий input всё равно (A,D).
- Только A пригоден на первом этапе: фактический total=40+100=140, planned=240.
- Все unsupported на первом: один report, total=40, NO_ELIGIBLE_CANDIDATES. Все unsupported только в финале: COMPLETED с пустым выбором.
- Финал A=40/100,D=60/100: оба пригодны, selected=(), прежние попадания не используются.
- max_total_trials=239 отклоняется заранее, 240 допускается. Этапы не оплачиваются как 4×10+2×90=220.
- Один этап (10,keep=10): planned=40, COMPLETED; keep не добавляет кандидатов. Для трёх этапов (10,2),(100,5),(1000,1) planned=2240, рост keep не возвращает B/C.
- При N=2**60+1 exact Fraction отличает расстояния, даже когда float их смешивает; all-round-limit пригоден с goal_rate=0, all-unsupported непригоден и в point window 0.

[staged_contract_probe.py](../examples/m6/staged_contract_probe.py) проверяет конечную арифметику и совместимость existing Melee bounded reports. Он не реализует staged models/service/chain guards, не вызывает runner/RNG и не доказывает достижимость синтетических наблюдений боем.

## Матрица тестов и порядок реализации

| Срез | Обязательные проверки |
| --- | --- |
| Helper | Typed Melee/отказ ranged, outside continuation против bounded selected, unsupported исключён, Fraction/ties/cutoff, восстановление исходного порядка, большой N без float |
| Stage/request | frozen/tuple copy/replace, uint64/positive exact ints без bool, весь stage preflight, рост trials/keep, общий seed/perspective/round budget/window, верхний бюджет 240 до RNG/runner/pool; один/три этапа |
| Result | Полная или законно оборванная цепочка; complete/no-eligible/финальный all-unsupported, 240/140/40, пустой выбор без возврата к ранним попаданиям; source/seed/trials/window/local budget/top_k/сценарий/order, пропуски/лишние/возвращённые IDs, равная копия, derived/frozen/no records, отказ ranged |
| Service | Exact bounded calls/options, полный повтор с index 0, ранний stop и outside continuation, type/source check до следующего вызова, ошибка второго этапа с index/candidate/cause/notes, неизвестный candidate=None, preflight и финальная ошибка без staged wrapper, BaseException, no partial/retry/fallback |
| Integration | Реальные sequential/spawn stage reports/selected равны, rename/reorder (с учётом намеренного tie-break), input/global RNG/cleanup, pool startup failure; без точного Monte Carlo процента |

Первый срез реализован: pure `melee_continuation_candidate_ids` и frozen stage/request/result/status с общей внутренней `_stage_request`. Application service/error и deterministic/real-backend tests реализованы. Аудит и самостоятельный staged пример завершены; следующий срез — контракт ограниченной генерации Melee-составов по явному резерву. Existing [M5 model tests](../../tests/unit/test_m5_ranged_staged_evaluation.py), [service tests](../../tests/unit/test_m5_ranged_staged_evaluation_service.py) и [integration](../../tests/integration/test_m5_ranged_staged_evaluation.py) задают технический образец, но не заменяют Melee tests.

Domain/engine/simulation, bounded evaluator, ranged APIs/wire и книги этим решением не меняются. Генерация составов, prefix reuse, Melee CLI/JSON, новые метрики/confidence/presets, PC/движение/смешанный бой и универсальный rules engine остаются вне контракта.

## Проверка контракта до реализации

2026-09-29, Windows/Python 3.14.5: finite probe прошёл, в том числе с запрещёнными runner/RNG/pool calls. **53 existing M5 staged и M6 assessment/evaluation tests OK (8,767 с)**. Compileall, 1204 локальных Markdown-пути и git diff --check успешны. Production src/tests не менялись; это не тесты ещё отсутствующего staged Melee API. Последняя полная регрессия предыдущего аудита — 2104 OK; в этом срезе не повторялась. На старте 21 dirty/untracked файл, сохранены. Добавлены этот ADR и probe, актуализирована документация; commit/push не выполнялись.

## Реализация helper и моделей

2026-09-29: [17 deterministic tests](../../tests/unit/test_m6_melee_staged_evaluation.py) проверяют outside-window continuation при пустом bounded selected, unsupported/round_limit, точные Fraction и ties/исходный порядок, финальные inclusive границы, 1–3 этапа/рост keep, бюджеты 240/140/40/1140 и отсутствие возврата к ранним попаданиям. Проверены весь stage preflight, seed/perspective/round budget/window, source/local budget/top_k/trials/scenario/order и неполные/лишние/чужие цепочки. Frozen/tuple copy/replace пересчитывают guards; равная копия source допустима, ranged stages/candidates/sources/reports отклоняются. Конструирование/отбор не вызывают RNG/runner/pool/JSON, result не хранит full records. Existing M5 APIs и simulation не менялись. Полная регрессия: **2121 tests OK (130,980 с)**; релевантные model tests — **50 OK (0,080 с)**, Windows/Python 3.14.5. Compileall, 1214 локальных Markdown-путей, documented staged request/finite probe и git diff --check успешны. 23 существовавших dirty/untracked файла сохранены; commit/push не выполнялись.

## Реализация application service

2026-09-29: [9 service tests](../../tests/unit/test_m6_melee_staged_evaluation_service.py) проверяют exact stage requests/options, равную копию source, original parent request, outside continuation/early stop/reduced budget и финальный all-unsupported COMPLETED. Проверены полные повторные пакеты с index 0 в обоих backend; ошибка второго этапа останавливает запрос из трёх этапов с сохранением stage/candidate/cause/notes. Неверный typed/source report (включая ranged) и прочие ошибки не получают вымышленный candidate; отказ ranged request/invalid options происходит до bounded call. Ошибки сборки stage/continuation оборачиваются, финальная ошибка result constructor и BaseException проходят напрямую. Partial result/retry/fallback отсутствуют.

[2 integration tests](../../tests/integration/test_m6_melee_staged_evaluation.py) проверяют реальные sequential/spawn reports и selected IDs, исходный parent request, rename/reorder observations (первый этап сохраняет обоих кандидатов; финальное равенство может зависеть от порядка), неизменные input/global RNG и завершение дочерних процессов. Pool startup failure сохраняет stage → candidate → исходную причину без fallback. Конкретная Monte Carlo вероятность не ожидается. Проверка среза: **2132 tests OK (135,184 с)**, релевантные Melee/M5 staged tests — **37 OK (7,775 с)**, Windows/Python 3.14.5. Compileall, 7 Python-фрагментов README, 1226 локальных Markdown-путей и git diff --check успешны. 26 прежних dirty/untracked файлов сохранены; существующие модели/bounded APIs/engine/simulation не менялись. Commit/push не выполнялись.

[Аудит staged Melee evaluation](../audits/m6-staged-evaluation-readiness.md) завершён 2026-09-29. [Самостоятельный пример](../examples/m6/melee_staged_evaluation.py) на двух явных Footpad-составах проверяет полные sequential/process reports/selected IDs, input/global RNG/cleanup и бюджет 2×8+1×32=48 на вызов. Обработка ошибки второго этапа проверена отдельно с сохранением cause/notes без partial report. [Контракт генерации ADR-0026](ADR-0026-melee-composition-generation.md) подготовлен и проверен конечным constructor probe; group/request preflight реализован, construction/result/error реализованы; integration генерация → staged evaluation проверена; [аудит генератора](../audits/m6-generation-readiness.md) и самостоятельный пример завершены; [контракт JSON/CLI ADR-0027](ADR-0027-melee-json-cli-v1.md) подготовлен; следующий срез — simulation Schema/command и pure adapters без CLI/JSON или новых игровых правил.
