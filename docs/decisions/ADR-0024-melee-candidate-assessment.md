# ADR-0024: оценка Melee-кандидатов и ограниченного списка

Статус: принято, 2026-09-28. **Pure Melee assessment, list models и application evaluator реализованы (service — 2026-09-29).** Направление и метрика уже подтверждены пользователем.

## Основание и граница

[Аудит массовой Melee-симуляции](../audits/m6-simulation-readiness.md) закрывает [ADR-0022](ADR-0022-independent-melee-simulations.md) и [ADR-0023](ADR-0023-process-melee-simulations.md). Готовы typed input, sequential/process, четыре исхода и aggregate-only summary. Этот контракт переносит подтверждённую метрику [ADR-0017](ADR-0017-ranged-candidate-assessment.md) на отдельные Melee-типы.

Книги не задают данное окно сложности или алгоритм top_k. Это продуктовый/технический контракт, не house rule. Непосредственно перечитаны BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112 и BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91: visited round не обязательно завершён, defeat не обязательно означает смерть. Оценка относится к caller-supplied цели за заданный бюджет в допущенном сценарии, не к полноценной группе PC или неограниченному бою.

Сохраняется [ADR-0021](ADR-0021-melee-minion-scenario.md): неподвижные Minions, отдельно утверждённые Close/awareness/прочие facts, текущий outnumbering и явные фиксированные GM policies. Кандидат уже должен быть допущенным сценарием. Assessment не генерирует состав, не исправляет facts, не меняет правила ради попадания в окно.

## Переиспользование и зависимости

Переиспользовать существующий **тот же класс** [ObjectiveRateWindow](../../src/towr/balance/ranged_assessment_models.py): frozen/slotted minimum/target/maximum, только Fraction, `0 <= minimum <= target <= maximum <= 1`. Его имя файла историческое; сам класс не зависит от ranged input/outcome. В первом срезе импортировать его непосредственно из `balance.ranged_assessment_models`, без копии, переноса, subclass или новой generic hierarchy. Существующие M5 imports, class identity и pickle path сохраняются. Никаких новых defaults/presets или преобразования float в Fraction.

Melee request/summary/counts/assessment/status/result остаются отдельными типами. Нельзя пропускать ranged summary по совпадению полей или строк enum. Домен, движок и simulation не зависят от balance. Pure balance получает только simulator input и aggregate summary; application исполняет runner, проверяет result и проецирует summary. Full records/journals не сохраняются в balance result.

Application service переиспользует существующие [SimulationExecutionMode/Options](../../src/towr/application/ranged_simulation_models.py), без RangedSimulationCommand и JSON adapters. Sequential требует workers/batch_size=None; process требует явные exact integer workers в [1,61] и batch_size > 0. Это ограничение application options уже существует; прямой Melee process API ADR-0023 сохраняет собственную проверку положительности и платформенные ограничения executor. Перенос options, новый wire format и изменение ranged API не входят в этот контракт.

## Первый срез: pure assessment одного кандидата

Реализованы [balance/melee_assessment_models.py](../../src/towr/balance/melee_assessment_models.py) и [balance/melee_assessment.py](../../src/towr/balance/melee_assessment.py):

```python
class MeleeAssessmentStatus(str, Enum):
    ELIGIBLE = "eligible"
    UNSUPPORTED_OBSERVATIONS = "unsupported_observations"

@dataclass(frozen=True, slots=True)
class MeleeCandidateAssessment:
    source_request: NpcMeleeSimulationRequest
    summary: NpcMeleeSimulationSummary
    window: ObjectiveRateWindow

def assess_melee_candidate(
    source_request: NpcMeleeSimulationRequest,
    summary: NpcMeleeSimulationSummary,
    window: ObjectiveRateWindow,
) -> MeleeCandidateAssessment: ...
```

Это реализованные API. Constructor требует соответствующие typed inputs; неподходящий тип — TypeError. `summary.source_request == source_request` по полному immutable значению, иначе ValueError. Равная копия request допустима; идентичность Python-объекта не требуется для проверки. Assessment сохраняет именно переданные source/summary/window. `dataclasses.replace` повторяет guards; frozen derived properties нельзя передать в init или изменить независимо.

При N = source.trials четыре свойства `objective_achieved_rate`, `side_defeated_rate`, `round_limit_rate`, `unsupported_path_rate` возвращают Fraction соответствующего count/N. Denominator — **все trials**, включая round_limit и unsupported. Уже готовые counts/totals не пересчитываются из журналов, kernel/RNG/JSON не вызываются. Means остаются свойствами summary и имеют прежний описательный смысл.

| Условие | status | window_match |
| --- | --- | --- |
| unsupported_path > 0 | UNSUPPORTED_OBSERVATIONS | None, даже если observed objective rate внутри окна |
| unsupported_path = 0 и minimum <= objective rate <= maximum | ELIGIBLE | True |
| unsupported_path = 0 и objective rate вне окна | ELIGIBLE | False |

ELIGIBLE означает пригодность наблюдений для сравнения, не попадание в окно. ROUND_LIMIT не считается поражением/ничьей; даже все trials на лимите дают пригодную долю цели 0, которая может попасть в явно заданное окно 0. Unsupported counts и shares остаются видимыми без rerun/renormalization. Guards summary проверяют согласованность, не происхождение вручную собранных наблюдений. Попадание точечной доли в окно не является гарантией истинной вероятности; confidence policy здесь не вводится.

## Второй срез: модели конечного списка

Реализованный [balance/melee_evaluation_models.py](../../src/towr/balance/melee_evaluation_models.py) содержит отдельные frozen/slotted модели:

| Модель | Поля и производные значения |
| --- | --- |
| MeleeBalanceCandidate | candidate_id, scenario: NpcMeleeScenario |
| MeleeBalanceEvaluationRequest | candidates, master_seed, trials_per_candidate, max_total_trials, window, top_k; derived simulation_requests и planned_trials |
| MeleeBalanceCandidateResult | candidate_id, assessment: MeleeCandidateAssessment |
| MeleeBalanceEvaluationResult | source_request, candidates: tuple[MeleeBalanceCandidateResult, ...]; derived selected_candidate_ids, total_trials, seed_scheme |

Request копирует finite candidates в tuple, требует непустой список typed candidates, непустые строковые IDs без нормализации и их точную уникальность. Scenario не конвертируется из ranged. Все candidates имеют общие perspective_side и initial.max_rounds. Общие master_seed/trials проверяются прежним NpcMeleeSimulationRequest: uint64 seed и положительное uint64 trials без bool/coercion. max_total_trials/top_k — положительные exact int без bool; неверные значения этих двух полей дают ValueError, как в M5. Ошибки типов typed inputs дают TypeError; пустые/дублированные IDs, несовпадающие общие поля и превышение бюджета — ValueError.

До любого runner/RNG/pool проверяется полный вход и `planned_trials = len(candidates) * trials_per_candidate <= max_total_trials`. Не сокращать список или trials, чтобы уложиться в бюджет. top_k может быть больше числа подходящих кандидатов. Derived simulation_requests строятся из каждого исходного scenario с общими seed/trials, `init=False, repr=False, compare=False`; replace request пересобирает их. Это входы прежнего симулятора, не новые sources или перенос continuation между боями.

Seed scheme остаётся `towr:npc-melee-trial:v1`. Candidate ID и порядок не входят в seed. Переименование/перестановка не меняют наблюдения сценария при тех же input/RNG/runtime. Одинаковый seed у разных составов не означает одинаковые броски соответствующих действий: число атак, текущий outnumbering и ветвления могут различаться. Не обещается статистическое уменьшение ошибки сравнения.

Result требует typed source, всех rows ровно один раз в исходном порядке, точные candidate IDs, соответствующие simulation requests и window. Partial/reordered/duplicate/foreign source или window отклоняются. Rows копируются в tuple. Ни selected IDs, ни budget, ни rates нельзя независимо подать как готовые поля: они производные. `total_trials` полного result равен planned_trials; seed_scheme берётся из Melee simulation.

Выбираются только rows с window_match is True: stable sort по `abs(objective_achieved_rate - window.target)` в Fraction, затем первые top_k. Точное равенство сохраняет входной порядок. Outside-window и unsupported остаются в полном отчёте, но не выбираются. Если никто не подходит, selected пуст; ближайший outside-window не выдаётся за подходящий. Первый список — явно поданные альтернативы: он не доказывает, что сценарии отличаются только численностью или что facts применимы к семейству автоматически. Генерация требует отдельного контракта.

## Третий срез: application orchestration

Реализованы [application/melee_evaluation_service.py](../../src/towr/application/melee_evaluation_service.py) и [melee_evaluation_errors.py](../../src/towr/application/melee_evaluation_errors.py):

```python
def evaluate_melee_candidates(
    request: MeleeBalanceEvaluationRequest,
    execution: SimulationExecutionOptions,
) -> MeleeBalanceEvaluationResult: ...

class MeleeBalanceEvaluationError(RuntimeError):
    candidate_id: str
```

Проверить request и execution до первого runner; сервис не принимает JSON/callable или неявный режим. Кандидаты исполняются последовательно, каждый один раз полным пакетом. Внутри кандидата выбранный existing sequential/process получает его simulation request, process — явные workers/batch_size. По умолчанию existing runners используют свежий Random(seed); внедрение RNG остаётся на их существующей границе, pure assessment не нуждается в RNG. Не вводятся вложенные pools, автоматическое определение CPU/backend или persistent pool.

После каждого вызова проверить typed NpcMeleeSimulationResult и равенство полного source request, затем вызвать existing summary projector и pure assessment. Сохранить только candidate row; освободить ссылку на full result до следующего кандидата. В конце построить полный MeleeBalanceEvaluationResult с parent request. Общая память не ограничивается max_total_trials как RSS quota: один текущий result хранит compact records, итог хранит все inputs/aggregates.

Exception во время конкретного кандидата (runner, pool/pickle, source check, projection, assessment/row construction) оборачивается в MeleeBalanceEvaluationError(candidate_id) через `raise ... from error`: исходные cause и worker index/seed notes сохраняются. Остановить список, не исполнять следующих кандидатов; не возвращать partial result. Ошибки preflight до кандидатов и итогового result constructor распространяются напрямую, без выдуманного candidate ID. KeyboardInterrupt/SystemExit не перехватываются как обычные candidate failures. Cleanup process принадлежит existing backend; retry/fallback/checkpoint/продолжение после ошибки не добавляются. Exception может удерживать traceback; запрет хранения full records относится к успешному aggregate report, не обещает очистки объектов traceback.

## Проверяемые примеры и матрица тестов

[assessment_contract_probe.py](../examples/m6/assessment_contract_probe.py) использует existing Melee summary и ObjectiveRateWindow, без вызова assessment API. Он был подготовлен до реализации; это конечные синтетические примеры точной арифметики и совместимости входа, **не реализация assessment/evaluator** и не доказательство наблюдаемой вероятности. В нём нет runner/RNG и tests/private imports.

Окно [1/4, 1/2, 3/4], N=4: A=1/4 и B=3/4 лежат на включённых границах, C=1/2 в центре, D=1 вне окна, E=1/2 с одним unsupported непригоден. При top_k=2 выбор C,A; при перестановке A/B — C,B. Все пять rows сохраняются, полный бюджет 20. Для N=2**60+1 доля floor(N/2)/N строго меньше 1/2 даже когда float округляет её к 0.5. All-round-limit и all-unsupported проверяются отдельно; последний остаётся непригодным и при observed goal rate 0.

| Срез | Проверки после реализации |
| --- | --- |
| Pure assessment | Typed Melee/отказ ranged/full result, foreign seed/trials/scenario/budget, равная копия source, immutable inputs; четыре Fraction rates, inclusive/point windows, unsupported=None, all-limit, большие N без float rounding; no RNG/runner/pool/records |
| Existing shared window | Тот же класс/import/pickle path, strict Fraction/order guards, без изменения прежних M5 tests и wire v1 |
| List models | IDs/types/tuple copy, common fields, budget до исполнения, derived rebuild; complete ordered source/window rows, ranking/ties/top_k/empty selection, большие N и отсутствие trial records |
| Service | Exact one call per candidate, выбранный backend/options, source check до projection, освобождение прошлого result; invalid preflight до runner; failure после первого кандидата с ID/cause/notes, отсутствие partial success/fallback, BaseException passthrough |
| Integration | Заданные d10 → existing sequential/spawn summaries → равные Melee assessments; real list replay/reorder/rename и равные aggregate reports обоих backend, error/cleanup. Не ожидать конкретного Monte Carlo процента |

Существующие [M5 assessment tests](../../tests/unit/test_m5_ranged_assessment.py), [list model tests](../../tests/unit/test_m5_ranged_evaluation.py) и [service tests](../../tests/unit/test_m5_ranged_evaluation_service.py) — основание контракта. Реализованные Melee assessment, list models и application service покрыты отдельными тестами ниже.

## Реализация pure assessment

[9 unit tests](../../tests/unit/test_m6_melee_assessment.py) проверяют четыре точные доли, included/point windows, all-limit/all-unsupported, отсутствие float rounding при большом N, typed Melee inputs и отказ ranged/full results, foreign seed/trials/budget/facts и равную копию source. Проверяются frozen/derived fields, неизменные input/summary, отсутствие retained trial records и вызовов RNG/runner/pool/JSON. ObjectiveRateWindow сохраняет class identity/module/pickle path; статус Melee отдельный.

[1 integration test](../../tests/integration/test_m6_melee_assessment.py) получает реальные Melee sequential/spawn summaries на заданных d10: цель/поражение/лимит по одному, точные shares 1/3, окно [1/3,1/3,1/3], равные assessments и parent source identity. Прежние M5 window/assessment tests сохранены. Assessment не изменяет summary/counters, window.target используется реализованным ranking моделей списка.

## Реализация моделей списка

2026-09-29: [четыре frozen модели](../../src/towr/balance/melee_evaluation_models.py) реализованы. [10 model tests](../../tests/unit/test_m6_melee_evaluation.py) проверяют finite tuple copies, exact IDs без нормализации, отказ ranged/неверных типов, общие seed/trials/perspective/round budget и max_total_trials до RNG/runner/pool, rebuild derived inputs при replace. Result требует все строки в исходном порядке с exact ID/source/window; проверены partial/duplicate/reordered/foreign rows и равная копия source. Top_k использует только window_match=True, Fraction distance и входной порядок при равенстве; outside/unsupported сохраняются в полном отчёте, пустой выбор без fallback. Проверены большой N без float rounding, top_k больше числа подходящих rows, производные budget/seed_scheme и отсутствие full records в графе полей. Исполнение списка реализовано следующим срезом ниже.

## Порядок реализации

Третий срез завершён 2026-09-29. [8 service tests](../../tests/unit/test_m6_melee_evaluation_service.py) проверяют backend/order/options, typed preflight включая отказ ranged, foreign/untyped result до projection, source identity, освобождение full result через weak references до следующего runner, candidate ID/cause/notes и остановку на ошибке. Проверены ошибки projector/assessment/row, отсутствие вымышленного candidate ID при ошибке финального отчёта и BaseException passthrough.

[2 integration tests](../../tests/integration/test_m6_melee_evaluation.py) проверяют реальные sequential/spawn reports, rename/reorder invariance, неизменность input/global RNG и отсутствие оставшихся дочерних процессов; pool startup failure сохраняет причину без fallback. Ни один тест не требует конкретного Monte Carlo процента.

[Аудит bounded evaluation](../audits/m6-evaluation-readiness.md) завершён 2026-09-29: все три среза покрыты 30 тестами, [самостоятельный пример](../examples/m6/melee_evaluation.py) исполняет два допущенных состава через sequential/process с равными полными reports/selected IDs. [Отдельный контракт ADR-0025](ADR-0025-staged-melee-evaluation.md) подготовлен по образцу ADR-0018; метрика/игровые правила прежние. Pure continuation helper, staged models и application service/error реализованы; [аудит staged evaluation](../audits/m6-staged-evaluation-readiness.md) и самостоятельный пример завершены. [Контракт генерации ADR-0026](ADR-0026-melee-composition-generation.md) подготовлен; group/request preflight реализован, construction/result/error реализованы; integration генерация → staged evaluation проверена; [аудит генератора](../audits/m6-generation-readiness.md) и самостоятельный пример завершены; следующий срез — контракт JSON/CLI для Melee (ADR-0027).

Генерация составов, staged execution/prefix reuse, Melee CLI/JSON, новые метрики/пресеты/confidence, движение/PC/mixed battle и universal rules engine остаются вне контракта. Ranged models/services/wire, Melee simulation и книги не меняются этим решением.
