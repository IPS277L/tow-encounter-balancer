# ADR-0031: оценка mixed-кандидатов и ограниченного списка

Статус: контракт принят в согласованном направлении M7, 2026-09-29. **Pure mixed assessment реализован; list models и application evaluator ещё не реализованы.** Подготовлен конечный проверочный пример. Направление и метрика уже подтверждены пользователем.

## Основание и граница

[Общий аудит массовой mixed-симуляции](../audits/m7-mass-simulation-readiness.md) закрывает ADR-0029/0030: typed input, sequential/process, четыре исхода и aggregate summary готовы. Переносим принятую метрику [M5 / ADR-0017](ADR-0017-ranged-candidate-assessment.md) и контракт [M6 / ADR-0024](ADR-0024-melee-candidate-assessment.md) на отдельное семейство mixed.

Книги не задают окно сложности, квоту прогонов или top_k. Это продуктовый/технический контракт, не house rule. Напрямую перечитаны BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112 и BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91: посещённый раунд не обязательно завершён, поражение Minion не обязательно означает смерть. Нормализованные RULE-COMBAT-001 и RULE-NPC-002 сохраняются; новых правил нет.

Кандидат — уже допущенный [NpcMixedScenario по ADR-0028](ADR-0028-mixed-minion-scenario.md): неподвижные numeric Minions, фиксированные Melee/Close и Shooting/Medium роли, явные pairs/facts/GM policies. Assessment не исправляет состав, позиции, цели или тактику ради попадания в окно. Потеря доступной цели очередного actor остаётся реальным unsupported_path. Нельзя пропускать ход, менять оружие, исключать такой trial или повторять его до игрового исхода.

## Переиспользование и зависимости

Переиспользовать **тот же** [ObjectiveRateWindow](../../src/towr/balance/ranged_assessment_models.py): frozen/slotted minimum/target/maximum, только Fraction, `0 <= minimum <= target <= maximum <= 1`. Исторический файл не делает окно зависимым от ranged request/outcome. Импорт напрямую из balance.ranged_assessment_models без копии, переноса, subclass или generic hierarchy; прежние class identity/import/pickle paths сохраняются. Float coercion, defaults и Easy/Medium presets не вводятся.

Mixed request/summary/counts/assessment/status/result — отдельные типы. Ranged/Melee inputs и Enum с равными строковыми значениями не принимаются как mixed. Domain/engine/simulation не зависят от balance. Pure balance получает только simulator input и aggregate summary; application исполняет runner и удаляет full records после проекции.

Application переиспользует [SimulationExecutionMode/Options](../../src/towr/application/ranged_simulation_models.py), без RangedSimulationCommand и JSON adapters. Sequential требует workers/batch_size=None; process требует явные exact int workers в [1,61] и batch_size > 0. Это existing application limit; прямой mixed process API сохраняет своё правило положительности и ограничения executor. Options не перемещаются, wire formats не меняются.

## Первый срез: pure assessment

Реализованные модули: [balance/mixed_assessment_models.py](../../src/towr/balance/mixed_assessment_models.py) и [balance/mixed_assessment.py](../../src/towr/balance/mixed_assessment.py):

```python
class MixedAssessmentStatus(str, Enum):
    ELIGIBLE = "eligible"
    UNSUPPORTED_OBSERVATIONS = "unsupported_observations"

@dataclass(frozen=True, slots=True)
class MixedCandidateAssessment:
    source_request: NpcMixedSimulationRequest
    summary: NpcMixedSimulationSummary
    window: ObjectiveRateWindow

def assess_mixed_candidate(
    source_request: NpcMixedSimulationRequest,
    summary: NpcMixedSimulationSummary,
    window: ObjectiveRateWindow,
) -> MixedCandidateAssessment: ...
```

Это реализованные API первого среза. Constructor проверяет соответствующие typed inputs (иначе TypeError) и `summary.source_request == source_request` по полному immutable значению (иначе ValueError). Одного scenario ID недостаточно. Равная копия request допускается; Python identity не требуется при проверке. Assessment сохраняет именно переданные source/summary/window. Frozen/slotted свойства не допускают независимого изменения; replace повторяет guards.

Четыре производных свойства objective_achieved_rate, side_defeated_rate, round_limit_rate, unsupported_path_rate возвращают Fraction соответствующего count / **все N trials**. Средние Attack/visited остаются описательными свойствами summary. Нет RNG/runner/kernel/JSON, пересчёта из журналов или нового simulation result.

| Условие | status | window_match |
| --- | --- | --- |
| unsupported_path > 0 | UNSUPPORTED_OBSERVATIONS | None, даже если objective rate внутри окна |
| unsupported_path = 0 и minimum <= objective rate <= maximum | ELIGIBLE | True |
| unsupported_path = 0 и objective rate вне окна | ELIGIBLE | False |

ELIGIBLE означает пригодность наблюдений к сравнению, а не попадание в окно. Обе границы включены, точечное окно допустимо. ROUND_LIMIT не становится поражением/ничьёй; все trials на лимите дают пригодную долю цели 0, которая может соответствовать явно заданному окну 0. Любой unsupported делает выбор непригодным без фильтрации или renormalization. Отсутствие unsupported в конечной выборке не доказывает полноту тактики. Структурная валидация summary не доказывает происхождение вручную собранных наблюдений; точечная оценка не гарантирует истинную вероятность, confidence policy не добавляется.

## Второй срез: модели конечного списка

Предлагаемый `balance/mixed_evaluation_models.py`, отдельные frozen/slotted модели:

| Модель | Поля и производные значения |
| --- | --- |
| MixedBalanceCandidate | candidate_id: str, scenario: NpcMixedScenario |
| MixedBalanceEvaluationRequest | candidates: tuple[MixedBalanceCandidate, ...], master_seed: int, trials_per_candidate: int, max_total_trials: int, window: ObjectiveRateWindow, top_k: int; derived simulation_requests и planned_trials |
| MixedBalanceCandidateResult | candidate_id: str, assessment: MixedCandidateAssessment |
| MixedBalanceEvaluationResult | source_request: MixedBalanceEvaluationRequest, candidates: tuple[MixedBalanceCandidateResult, ...]; derived selected_candidate_ids, total_trials, seed_scheme |

Request копирует конечную последовательность candidates в tuple, требует непустой список typed candidates и точную уникальность непустых строковых IDs. IDs не нормализуются; str, содержащий только whitespace, отклоняется. Неверные IDs дают ValueError, чужие typed inputs — TypeError. Все сценарии имеют общие perspective_side и initial.max_rounds; несовпадение даёт ValueError. Цель каждого сценария уже проверена его admission; альтернативы не обязаны отличаться только численностью.

Общие seed/trials проверяются существующим NpcMixedSimulationRequest: uint64 seed, положительное uint64 trials, без bool/coercion. max_total_trials/top_k — положительные exact int без bool; неверные значения этих двух полей дают ValueError, как в M5/M6. До любого RNG/runner/pool проверяются весь вход и `planned_trials = len(candidates) * trials_per_candidate <= max_total_trials`; превышение даёт ValueError. Список/trials не сокращаются, top_k может превышать число подходящих кандидатов.

Derived simulation_requests — tuple исходных scenarios с общими seed/trials, поле init=False/repr=False/compare=False; replace пересобирает его. Seed scheme остаётся **towr:npc-mixed-trial:v1**. Candidate ID и порядок не входят в seed; rename/reorder не меняют наблюдения самого сценария при том же runtime/RNG. Равные trial seeds разных составов не означают равные броски соответствующих действий или доказанное уменьшение статистической ошибки: ветвления и число бросков отличаются.

Result требует typed source и все rows ровно один раз в исходном порядке. Для каждой строки проверяются candidate ID, полный simulation request и window assessment. Partial/reordered/duplicate/foreign rows дают ValueError, чужие типы — TypeError. Rows копируются в tuple. Selected IDs, total_trials и seed_scheme — только производные; total_trials завершённого результата равен planned_trials, seed_scheme берётся из mixed simulation.

Выбор: только window_match is True, stable sort по `abs(objective_achieved_rate - window.target)` в Fraction, затем первые top_k. При точном равенстве сохраняется входной порядок. Outside-window и unsupported остаются в полном отчёте; если никто не подходит, выбор пуст. Не возвращать ближайшего outside-window как подходящего. Генерация семейства сценариев и перенос facts между составами требуют отдельного контракта.

## Третий срез: application orchestration

Предлагаются `application/mixed_evaluation_service.py` и `mixed_evaluation_errors.py`:

```python
def evaluate_mixed_candidates(
    request: MixedBalanceEvaluationRequest,
    execution: SimulationExecutionOptions,
) -> MixedBalanceEvaluationResult: ...

class MixedBalanceEvaluationError(RuntimeError):
    candidate_id: str
```

Typed request/execution проверяются до первого runner. Кандидаты исполняются последовательно, каждый один раз полным пакетом через existing sequential либо process API. Process получает явные workers/batch_size. Фабрика RNG остаётся на existing simulation границе; production service использует обычные fresh Random(seed), pure assessment RNG не требует. Никаких вложенных pools, auto backend/CPU count, persistent pool или нового scheduler.

После каждого вызова проверить typed NpcMixedSimulationResult и полный source request до summary projection. Затем existing summary projector → pure assessment → candidate row; освободить full result до следующего runner. Финальный result сохраняет исходный parent request. Успешный aggregate report хранит inputs/summary, без full records/journals; max_total_trials не является RSS quota.

Exception внутри кандидата (runner/pool/pickle/source/projection/assessment/row) оборачивается в MixedBalanceEvaluationError(candidate_id) через `raise ... from error`; original cause и worker index/seed notes сохраняются. Остановить список без следующих кандидатов, partial success, retry или fallback. Preflight и final result constructor errors распространяются напрямую, без вымышленного candidate ID. KeyboardInterrupt/SystemExit не перехватываются как ordinary failures; cleanup выполняет existing process backend. Traceback ошибки может удерживать объекты, запрет records относится к успешному отчёту, не обещает очистки traceback.

## Конечный probe и план проверки

[assessment_contract_probe.py](../examples/m7/assessment_contract_probe.py) и [вывод](../examples/m7/assessment_contract_probe.output.txt) используют existing public mixed builder, simulation/summary, ObjectiveRateWindow и execution options. Новых assessment/list/service API в probe нет; конечная арифметика не реализует их guards или evaluator.

Синтетическая часть: окно [1/4,1/2,3/4], пять summaries N=4 с долями 1/4,3/4,1/2,1,1/2; последняя имеет unsupported. Matches True/True/True/False/None, top_k=2 выбирает C,A; при перестановке A/B — C,B. Бюджет 20 сравнивается с caps 20 и 19 арифметически, **без production preflight**. Проверены point-zero/all-limit/all-unsupported и N=2**60+1, когда exact rate < 1/2, но float == 0.5. Синтетические counts не являются результатом симуляции.

Реальная часть: один 2×2 input, B=2, N=4, заданные d10 через отдельную top-level factory. Existing sequential и production spawn workers=2/batch_size=3 исполняют по четыре trial: полные results/summaries равны, counts=1/1/1/1, 17 Attack/6 visited. Observed goal=1/4 входит в окно, но реальный unsupported=1/4 требует будущего window_match=None. Всего восемь реальных trials на запуск; parent source/global RNG неизменны, дети завершены. Это scripted примеры, не Monte Carlo оценка баланса.

| Срез | Обязательные проверки реализации |
| --- | --- |
| Pure assessment | Mixed types, отказ ranged/Melee/full result, foreign seed/trials/scenario/pairs/facts/budget и равная копия source; frozen/replace guards, четыре Fraction, inclusive/point windows, unsupported=None, all-limit, большие N; без RNG/runner/pool/records |
| Shared classes | Те же ObjectiveRateWindow и execution options, identity/import/pickle paths, strict Fraction/options guards; M5/M6 tests и wire formats неизменны |
| List models | IDs/tuple copies/types, общие поля, полный бюджет до execution, derived rebuild; complete ordered rows/source/window, Fraction ranking/ties/top_k/empty selection, большие N без float rounding, без full records |
| Service | Один полный вызов на кандидата, порядок/backend/options, source до projection, освобождение result; preflight без runner, failure второго кандидата с ID/cause/notes без третьего/partial/retry/fallback, BaseException и final constructor failures |
| Integration | Заданные d10 → sequential/spawn → равные assessments всех четырёх исходов; реальный NO_CANDIDATE непригоден при доле внутри окна. List replay/reorder/rename, input/global RNG/cleanup, ошибки. Не фиксировать ожидаемый Monte Carlo процент |

Порядок реализации: (1) pure assessment + deterministic/integration tests; (2) list models/preflight/ranking; (3) application service/errors и real-backend integration; (4) аудит bounded evaluation и самостоятельный production-пример. Подбор/генерация составов, staged execution, JSON/CLI, confidence/presets, новые действия/магия/PC и общий battle aggregate — последующие отдельные задачи. Правила, simulation и existing ranged/Melee APIs этим ADR не меняются.

## Проверка контрактного среза

2026-09-29, Windows / Python 3.14.5: probe прошёл из корня и отдельного временного cwd с абсолютным PYTHONPATH к src; stderr пуст, output сохранён. Два запуска выполнили 16 реальных scripted trials суммарно. **81 existing test OK (22,130 с)**: mixed simulation/summary/process, M6 assessment/list/service/integration и M5 assessment/window. Compileall, 1827 локальных Markdown-путей, public imports probe, неизменный source/harness hash и diff/whitespace успешны. Src/tests/tools не менялись, полный набор повторно не запускался (последняя полная проверка 2414 OK). Все 15 исходных dirty/untracked файлов сохранены; добавлены ADR/probe/output и обновлена документация. Commit/push не выполнялись. Python 3.12/другие ОС, installed wheel и performance не проверялись.

## Реализация pure assessment

2026-09-29: MixedCandidateAssessment, MixedAssessmentStatus и assess_mixed_candidate реализованы. Тот же ObjectiveRateWindow импортируется без переноса; mixed input/summary и полный source обязательны, равная копия request допустима. Доли/status/window_match производные, assessment не исполняет trials и не удерживает records/journals.

[9 unit tests](../../tests/unit/test_m7_mixed_assessment.py): четыре Fraction rates, inclusive/point windows, all-limit/all-unsupported, большой N без float rounding, wrong family/full result, foreign seed/trials/budget/escape facts/GM approval/pair order, frozen/replace, class/pickle identity и отсутствие RNG/runner/pool/JSON. [1 integration test](../../tests/integration/test_m7_mixed_assessment.py) выполняет две выборки на заданных d10 через sequential/spawn: все четыре исхода дают 1/1/1/1 и 17 Attack/6 visited, rate=1/4 точно попадает в окно, но status=UNSUPPORTED_OBSERVATIONS/window_match=None. Отдельный supported prefix из трёх trials даёт 1/1/1/0, 16 Attack/5 visited и ELIGIBLE/True для point window=1/3. Full results/summaries/assessments равны, source/global RNG/cleanup сохраняются. Ни один тест не фиксирует Monte Carlo процент.

Следующий срез — модели конечного списка из второго раздела контракта: preflight общего бюджета, complete ordered source/window report и stable Fraction ranking без исполнения. Application service/errors и аудит следуют отдельно. Исторический contract probe не вызывает новые assessment APIs и не заменяет их tests.

Проверка implementation-среза: **28 профильных tests OK (2,629 с)**, включая 10 новых и M5/M6 assessment regression; **2424 tests полного набора OK (259,355 с)**. Compileall, 1843 локальных Markdown-пути, AST import boundaries и diff/whitespace успешны. Новый API snippet проверен из отдельного cwd. Все 18 исходных dirty/untracked файлов сохранены; добавлены два balance модуля и два test-файла, документация обновлена. Domain/engine/simulation/tools и игровые правила не менялись. Python 3.12/другие ОС, installed wheel и performance не проверялись; commit/push не выполнялись.
