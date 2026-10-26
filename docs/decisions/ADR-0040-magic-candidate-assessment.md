# ADR-0040: оценка magic-кандидатов и ограниченного списка

Статус: контракт подготовлен в согласованном направлении M8, 2026-10-27. **Pure assessment и list models реализованы; application service ещё не реализован.** Конечный probe проверяет арифметику и existing simulation APIs; он не заменяет будущие модели/guards/evaluator.

## Основание и граница

[Общий аудит массовой magic simulation](../audits/m8-mass-simulation-readiness.md) закрыл ADR-0038/0039: typed input, sequential/process, full-source compact records и aggregate summary готовы. Применяется уже принятая метрика [M5 / ADR-0017](ADR-0017-ranged-candidate-assessment.md), [M6 / ADR-0024](ADR-0024-melee-candidate-assessment.md) и [M7 / ADR-0031](ADR-0031-mixed-candidate-assessment.md): доля достижения явно заданной цели среди **всех N trials** при общем лимите раундов, явное окно и отдельные другие outcomes.

Книги не задают окно сложности, квоту прогонов, Fraction ranking или top_k. Это продуктовый/технический контракт, не house rule. Напрямую сверены BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр.112; Conditions / Broken, стр.122; Magic in the Old World / Spell Potency / Miscasts and the Rule of Nine, стр.157; Battle Magic / Curse of Cowardly Flight, стр.162; Wounds Table, стр.190–191. BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions и Champions, стр.91–92. Broken/другая Zone не defeat, Champion не Minion, mandatory pending не исчезает при агрегации. Новых игровых Rule IDs нет.

Кандидат — уже допущенный NpcMagicScenario [ADR-0037](ADR-0037-magic-scenario-runner.md): один authored Champion-Wizard с Curse, allied/enemy numeric Shooting Minions и полные явные scene facts/policies. Assessment не меняет профили, objective, frames, пути, тактику или порядок ради попадания в окно. Обязательные неподдержанные Wound/Miscast/chronology, обычный Attack Give Ground и неизвестные scene/route остаются UNSUPPORTED_PATH. Их нельзя исключать из N, считать поражением/ничьёй, повторять до игрового исхода или пропускать ради продолжения.

## Переиспользование и зависимости

Переиспользовать **тот же класс** [ObjectiveRateWindow](../../src/towr/balance/ranged_assessment_models.py): frozen/slotted minimum/target/maximum, только Fraction, `0 <= minimum <= target <= maximum <= 1`. Историческое имя модуля не добавляет зависимости окна от ranged scenario/outcome. Импорт напрямую из balance.ranged_assessment_models; без копии, переноса, subclass или generic hierarchy. Class identity/import/pickle paths сохраняются; float coercion, defaults и difficulty presets не добавляются.

Application переиспользует существующие [SimulationExecutionMode/Options](../../src/towr/application/ranged_simulation_models.py), без RangedSimulationCommand, JSON adapters и нового общего simulator API. Sequential требует workers/batch_size=None; process требует явные exact int workers в [1,61] и batch_size>0. Это существующий application limit, а не изменение прямого magic process runner, который сохраняет ADR-0039. Options/class paths и wire formats прежних семейств не меняются.

Magic request/summary/counts/assessment/status/list/result — отдельные типы. Ranged/Melee/mixed types или Enum с равными строками не подменяют magic. Balance получает только simulator input и aggregate summary; application исполняет runner и освобождает full result после проекции. Domain/engine/rules/simulation не зависят от balance/application. Нового scheduler/event bus/cache не вводится.

## Первый срез: pure assessment

Реализованы [balance/magic_assessment_models.py](../../src/towr/balance/magic_assessment_models.py) и [balance/magic_assessment.py](../../src/towr/balance/magic_assessment.py):

```python
class MagicAssessmentStatus(str, Enum):
    ELIGIBLE = "eligible"
    UNSUPPORTED_OBSERVATIONS = "unsupported_observations"

@dataclass(frozen=True, slots=True)
class MagicCandidateAssessment:
    source_request: NpcMagicSimulationRequest
    summary: NpcMagicSimulationSummary
    window: ObjectiveRateWindow

def assess_magic_candidate(
    source_request: NpcMagicSimulationRequest,
    summary: NpcMagicSimulationSummary,
    window: ObjectiveRateWindow,
) -> MagicCandidateAssessment: ...
```

Constructor требует соответствующие typed inputs (иначе TypeError) и `summary.source_request == source_request` по полному immutable значению (иначе ValueError). Одного scenario ID/master_seed недостаточно: сравниваются seed/N и полный scenario, включая Wizard/injury/magic state, spell, roster, facts, actor policies, objective, frames, histories и max_rounds. Равная immutable копия request допустима; identity не является условием admission. Assessment сохраняет именно переданные source/summary/window. Frozen/slotted поля и dataclasses.replace повторяют guards; status/rates/window_match не передаются независимо.

| Производное свойство | Точный источник |
| --- | --- |
| objective_achieved_rate | Fraction(summary.outcome_counts.objective_achieved, summary.trials) |
| perspective_defeated_rate | Fraction(summary.outcome_counts.perspective_defeated, summary.trials) |
| round_limit_rate | Fraction(summary.outcome_counts.round_limit_reached, summary.trials) |
| unsupported_path_rate | Fraction(summary.outcome_counts.unsupported_path, summary.trials) |

Native magic names не заменяются Minion-only side_defeated/round_limit. Три totals actions/started/completed сохраняются в summary без добавления means, новых simulation properties или пересчёта из журнала. Сумма четырёх rates равна 1. Assessment не вызывает RNG/runner/kernel/pool и не удерживает compact records/final owners/journals.

| Наблюдения | status | window_match |
| --- | --- | --- |
| unsupported_path > 0 | UNSUPPORTED_OBSERVATIONS | None, даже если objective rate внутри окна |
| unsupported_path = 0, minimum <= objective rate <= maximum | ELIGIBLE | True |
| unsupported_path = 0, objective rate вне окна | ELIGIBLE | False |

ELIGIBLE означает пригодность наблюдений, а не попадание в окно. Границы включены, точечное окно допустимо. Все ROUND_LIMIT_REACHED дают пригодную долю цели 0 и могут соответствовать явно заданному окну 0; они не объявляются ничьей. Все unsupported дают None, в том числе zero-action observations. Отсутствие unsupported в конечной выборке не доказывает полноту тактики. Полный независимый request N=3 может не наблюдать unsupported, который появился на trial3 в N=4; это иной размер выборки, а не разрешение удалить неудобную запись из законченного пакета.

Summary проверяет необходимые арифметические bounds, не происхождение вручную собранных observations. Это точечная оценка, без confidence policy, гарантии истинной вероятности или оценки player-side victory независимо от выбранной perspective.

## Второй срез: модели конечного списка

[balance/magic_evaluation_models.py](../../src/towr/balance/magic_evaluation_models.py) содержит реализованные frozen/slotted модели:

| Модель | Поля и производные значения |
| --- | --- |
| MagicBalanceCandidate | candidate_id: str, scenario: NpcMagicScenario |
| MagicBalanceEvaluationRequest | candidates: tuple[MagicBalanceCandidate, ...], master_seed: int, trials_per_candidate: int, max_total_trials: int, window: ObjectiveRateWindow, top_k: int; derived simulation_requests и planned_trials |
| MagicBalanceCandidateResult | candidate_id: str, assessment: MagicCandidateAssessment |
| MagicBalanceEvaluationResult | source_request: MagicBalanceEvaluationRequest, candidates: tuple[MagicBalanceCandidateResult, ...]; derived selected_candidate_ids, total_trials, seed_scheme |

Ordered candidates/rows принимаются только как tuple/list и копируются в tuple; generator/set/dict/str не принимаются. Request требует непустой список typed candidates и точную уникальность непустых строковых IDs. IDs не trim/нормализуются; whitespace-only отклоняется. Неверный тип ID/input/sequence/Enum или bool вместо integer → TypeError, пустота/диапазон/неполнота/несогласованность → ValueError, как в magic simulation. Это явный strict type contract новых моделей, а не изменение исторических M5/M6/M7 exceptions.

Сценарии имеют общие perspective_side и **scenario.max_rounds**, а не initial.max_rounds из Minion-only моделей. Цель каждого сценария проверена его admission; конкретные target IDs, состав/frames/policies могут различаться и остаются полным source соответствующего кандидата. Caller отвечает за смысл сравниваемых authored альтернатив. Повтор scenario.id или одинаковый scenario у разных candidate IDs допустим; уникальны labels кандидатов, не ID сценариев. Facts/approvals/frames между альтернативами автоматически не переносятся.

Общие seed/trials проверяет existing NpcMagicSimulationRequest: uint64 seed, положительный uint64 N, без bool/coercion. max_total_trials и top_k — положительные exact int (wrong type → TypeError, <=0 → ValueError). До любого RNG/runner/pool проверяются весь список и `planned_trials = len(candidates) * trials_per_candidate <= max_total_trials`. Превышение → ValueError. Размер списка/N не сокращается; budget — Python integer без искусственного uint64 cap на произведение. top_k может превышать число подходящих кандидатов.

Derived simulation_requests — tuple исходных scenarios с общими seed/trials; field init=False/repr=False/compare=False. replace пересобирает derived tuple. Seed scheme остаётся `towr:npc-magic-trial:v1`. Candidate/scenario labels, порядок и workers/batch не входят в seed. Reorder/rename сохраняют indexed streams соответствующего input при совместимом runtime/RNG; rename scenario меняет source/trace IDs. Равные seeds разных сценариев не означают одинаковые броски соответствующих действий или доказанное уменьшение статистической ошибки: число draws/ветвления могут отличаться.

Result требует typed source и все rows ровно один раз в исходном порядке; для каждой строки сверяются candidate ID, полный simulation request и window assessment. Missing/reordered/duplicate/foreign rows → ValueError, чужие types → TypeError. Равные immutable source copies допускаются. Total trials полного report равен planned_trials; source_request успешного application result — исходный parent request. Seed_scheme берётся из magic simulation, а не задаётся caller.

Selection — только `window_match is True`, stable sort по `abs(objective_achieved_rate - window.target)` в Fraction, затем первые top_k. При точном равенстве сохраняется входной порядок. Outside-window/unsupported остаются в полном отчёте; пустой selection допустим, fallback к ближайшему вне окна нет. Ни rows, ни assessment, ни итоговый report не удерживают simulation results/records/journals/RNG.

## Третий срез: application orchestration

Будущие application/magic_evaluation_service.py и magic_evaluation_errors.py:

```python
def evaluate_magic_candidates(
    request: MagicBalanceEvaluationRequest,
    execution: SimulationExecutionOptions,
) -> MagicBalanceEvaluationResult: ...

class MagicBalanceEvaluationError(RuntimeError):
    candidate_id: str
```

Typed request/execution проверяются до первого runner. Кандидаты идут последовательно, каждый один раз полным existing sequential или process run с derived N/master_seed. Process получает explicit workers/batch_size; каждый кандидат создаёт свой pool по ADR-0039. Фабрика RNG остаётся existing simulation boundary; production service использует default fresh Random(seed), нового rng_factory параметра у evaluator нет. Вложенные/persistent pools, parallel evaluation нескольких кандидатов, auto backend/CPU count не вводятся.

После runner проверить typed NpcMagicSimulationResult и full source_request до summary projection. Затем existing summary → pure assessment → candidate row. Full result освобождается до следующего runner; successful report сохраняет только inputs/summary. max_total_trials — execution budget, не RSS/byte quota; один полный пакет временно удерживается application. Raw process source normalization остаётся обязанностью ADR-0039, service не исправляет foreign source.

Обычный Exception внутри кандидата (runner/pool/pickle/source/projection/assessment/row) оборачивается в MagicBalanceEvaluationError(candidate_id) через `raise ... from error`; original cause и worker index/seed notes доступны через цепочку. Ошибка прерывает список без следующего кандидата, retry/fallback или partial success. Preflight и final result constructor errors проходят напрямую, без вымышленного candidate ID. KeyboardInterrupt/SystemExit не превращаются в ordinary failure/outcome; cleanup выполняет existing backend. Traceback может удерживать объекты; запрет records относится к успешному report, не обещает очистку exception traceback или мгновенный kill running tasks.

## Конечный probe и критерии проверки

[assessment_contract_probe.py](../examples/m8/assessment_contract_probe.py) и [вывод](../examples/m8/assessment_contract_probe.output.txt) используют существующие public magic simulation/summary и соседние magic_simulation.py/magic_scenario.py, shared window/options. Новых assessment/list/service API или их preflight probe не реализует.

Синтетическая часть: structurally valid summaries N=4 и окно [1/4,1/2,3/4]; goal shares 1/4,3/4,1/2,1,1/2, последний содержит unsupported. Matches True/True/True/False/None; top_k=2 выбирает C,A, при перестановке A/B — C,B. Бюджет 20 / caps 20 и 19 сравнивается арифметически, не production constructor. Point-zero/all-limit/all-unsupported, N=2**60+1 с exact rate<1/2 при float==0.5 и shared pickle/class paths проверяются отдельно. Синтетические counts не выдаются за результаты боя.

Реальная часть: один authored input B=4, request N=4 и четыре заданных d10-потока. Existing sequential/spawn workers2/batch3 дают равные full results/summary: outcomes1/1/1/1, actions24/started10/completed9, 120 заданных d10 в supplied scripts на backend. Доля цели1/4 находится внутри окна, но unsupported1/4 требует будущего window_match=None.

Второй **полный независимый request N=3** исполняет первые три indexed streams заново в обоих backend: records равны prefix N4, outcomes1/1/1/0, actions23/started9/completed9, 117 заданных d10 в supplied scripts на backend; goal1/3 в окне, future match=True. Завершённый N4 не фильтруется. Всего 14 real trials и 474 заданных d10 в supplied scripts за четыре calls (7 sequential +7 spawned); input/global RNG/parent source identity/children сохранены. Это finite scripted evidence, не Monte Carlo difficulty estimate, не production assessment и не обещание performance. Числа d10 описывают длины заданных потоков; probe не собирает отдельный журнал consumed draws из детей.

| Срез реализации | Обязательные проверки |
| --- | --- |
| Pure assessment | Native magic types; отказ ranged/Melee/mixed/full result, foreign seed/N/scenario/frames/facts/policies/spell/budget и допуск equal source copy; frozen/replace guards, четыре Fraction, inclusive/point/large-N и unsupported=None/all-limit, без runner/RNG/pool/records |
| Shared types | Сохранение identity/import/pickle paths ObjectiveRateWindow и execution options, strict Fraction/options; прежние M5–M7 tests и wire formats |
| List models | Strict tuple/list/IDs/types, общий perspective/max_rounds и полный budget до execution, derived rebuild; complete ordered rows/full source/window, stable Fraction ties/top_k/empty selection, большие N, без records/journals |
| Application | Один полный run на кандидата, order/backend/options, source до summary, освобождение result до следующего runner; preflight no-run, failure второго с ID/cause/notes без третьего/retry/partial, BaseException и final constructor boundary |
| Real integration | Четыре scripted outcomes sequential/spawn, реальный unsupported при goal внутри окна, полный N3 без unsupported; prefix/reorder/rename, full source/input/global RNG/cleanup и errors. Без закрепления Monte Carlo winner/процента |
| Аудит | Матрица контракта, public production example, source/error/aggregate-only границы и установленный package после реализации |

Порядок: (1) pure assessment + deterministic/real integration tests; (2) list models/preflight/ranking; (3) application service/errors + real backend integration; (4) аудит bounded evaluation и самостоятельный production-пример. Это отдельные небольшие срезы. Staged evaluation, generation, JSON/CLI, confidence/presets, новые spell/Wound/Miscast consumers, PC/другие NPC и общий battle aggregate сюда не входят. Прежние rules/simulation/API не меняются.

## Проверка контрактного среза

2026-10-27, CPython3.12.15/macOS26.5.1 arm64: probe выполнен из root и отдельного cwd; stored stdout совпал, stderr пуст. [Один новый subprocess test](../../tests/integration/test_m8_magic_assessment_contract_probe.py) — OK (0,784 с). 27 existing M5/M6/M7 pure assessment tests — OK (0,015 с); они проверяют прежние shared contracts, а не ещё отсутствующий magic assessor.

Installed проверка: все 411 текущих Python/Schema files равны ранее собранному wheel и installed package; новый трёхфайловый probe вне repo без PYTHONPATH дал тот же stdout/пустой stderr. Shared modules загружены из installed site. Новый wheel не собирался; его README metadata исторический, production sources неизменны. Evidence `/private/tmp/towr-m8-assessment-contract-installed-report.json`.

Полная регрессия: **3163 tests / 33 прежних errors (98,388 с)**. Полные error headers и exception signatures точно совпали с предыдущим baseline; новых ошибок нет, полный suite не зелёный. Причины — [известные dataclasses assertions Python3.12](../open-questions.md#проверки-dataclasses-на-python-312). Source/harness hash контрактного среза `f20131529ea476bfc61b3f37c29262b1dbe13f60cdca615b8f5c44e7dd55130d` совпадает с обоими performance reports; новых замеров нет. Команды и файловые проверки — в [статусе](../project-status.md#последняя-проверка).

Независимый read-only reviewer проверил контракт, probe/test и непосредственные книжные страницы, блокеров нет. Src/tools/старые tests/builders не менялись. Следующий законченный срез — pure MagicCandidateAssessment/assess_magic_candidate с deterministic и real-backend integration tests; list/service и их production guards следуют отдельно.

## Реализация первого среза: pure assessment

2026-10-27: MagicAssessmentStatus/MagicCandidateAssessment и assess_magic_candidate реализованы в двух отдельных balance modules. Typed request/summary/window, full-source equality без rebinding, frozen/slotted поля и четыре derived Fraction rates от всех N сохраняют контракт. Magic native counts и три summary totals не меняются; status/window_match не передаются caller. Общий ObjectiveRateWindow сохраняет прежний class path. RNG/runner/pool/JSON/records в pure API нет.

[11 unit tests](../../tests/unit/test_m8_magic_assessment.py) и [1 real-spawn integration](../../tests/integration/test_m8_magic_assessment.py) — **12 OK (0,586 с)**. Проверены wrong families/full result, восемь допустимых same-ID source variants (seed/N/budget/activation/zone priorities/Willpower/departures/Wizard Level), equal deepcopy source без перепривязки полей, frozen/replace, shared pickle paths, inclusive/point/outside/all-limit/all-unsupported и большие Fraction. Canonical spell/facts и fresh histories уже ограничены scenario admission; assessment не принимает forged snapshots для обхода этих ограничений.

Integration исполняет полные N4 и N3 заново в sequential/spawn, сверяет все records/summary/assessment, исходные parent references и child PID. Counts1/1/1/1 и 1/1/1/0, totals24/10/9 и 23/9/9; точечное окно1/N даёт None для N4 и True для N3. Input/global RNG/children сохранены. Независимый read-only reviewer проверил production/tests, блокеров нет.

Изначальные contract probe/output/test сохранены побайтно. Domain/engine/rules/simulation, прежние API и shared classes не менялись. Общий source/harness hash изменился только добавлением balance modules; historical performance reports не переснимались. Installed wheel нового assessment API и другие runtime/ОС в этом срезе не проверялись; прежняя installed evidence выше относится к контрактному probe до добавления assessment.

Следующий срез — только balance/magic_evaluation_models.py: frozen candidate/request/row/result, полный preflight списка/общего бюджета, derived simulation requests, source/window/order guards и stable Fraction ranking. Application service/errors и runtime evaluation последуют отдельно. Полная регрессия первого implementation-среза: **3175 tests / 33 прежних errors (100,539 с)**, точные error Counters равны предыдущей вехе, новых ошибок нет. Compileall, 2947 локальных Markdown-путей, 65 anchors, AST boundaries/purity и whitespace — OK. Команды — в [актуальном статусе](../project-status.md#последняя-проверка).

## Реализация второго среза: list models

2026-10-27: MagicBalanceCandidate/MagicBalanceEvaluationRequest/MagicBalanceCandidateResult/MagicBalanceEvaluationResult реализованы в отдельном magic_evaluation_models.py. Tuple/list копируются в tuple до дальнейшей работы, другие контейнеры не потребляются; IDs сохраняются без нормализации. Wrong types/bool дают TypeError, пустые значения/диапазоны/несогласованность — ValueError. Общие perspective_side и scenario.max_rounds, seed/N и полный planned_trials/max_total_trials проверяются без execution; произведение бюджета не ограничено uint64.

Derived simulation_requests сохраняют исходные scenarios и пересобираются при replace. Полный report требует все rows в исходном порядке с exact ID/full source/window; equal immutable copies допускаются. Selection только window_match=True, stable Fraction distance/top_k, без outside/unsupported fallback; rejected observations остаются в полном report. Никаких results/records/journals или RNG в графе полей нет.

[15 новых deterministic tests](../../tests/unit/test_m8_magic_evaluation.py) — **OK (0,040 с)**: strict types и непрочитанные generators, exact IDs/repeated scenarios, общий perspective/max_rounds, полный budget и произведение >uint64 без перебора trials, derived rebuild, complete source/window/order, mixed/ranged/melee type rejection, Fraction ties/reorder/rename/large-N, empty selection, frozen/pickle ownership и purity. Наблюдения для ranking синтетические, runner не запускается. Независимый read-only reviewer проверил production/tests, блокеров нет.

На старте сохранены 20 existing dirty/untracked файлов предыдущих срезов; старые Python/probe/output/test не менялись. Simulation/engine/rules и seed scheme прежние; новый общий source/harness hash обусловлен добавлением balance model, новых замеров нет. Installed wheel/новый runtime evaluator этим срезом не проверялись. Полная регрессия: **3190 tests / 33 прежних errors (99,608 с)**; точные error Counters равны предыдущей вехе, новых ошибок нет. Compileall, 2956 локальных Markdown-путей, 68 anchors, AST boundaries/purity и whitespace — OK. Команды — в [статусе](../project-status.md#последняя-проверка).

Следующий срез: application/magic_evaluation_service.py и magic_evaluation_errors.py по третьему разделу. Один полный run на кандидата, typed result/full source до summary, aggregate rows, освобождение full result до следующего runner; candidate ID/cause/notes при ordinary errors без partial/retry/fallback. Затем отдельный аудит bounded evaluation.
