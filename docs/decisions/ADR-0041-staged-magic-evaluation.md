# ADR-0041: поэтапная оценка явного magic-списка

Статус: контракт подготовлен в согласованном направлении M8, 2026-10-27. **Pure continuation helper, frozen staged models и application service реализованы; [общий аудит](../audits/m8-staged-evaluation-readiness.md) и самостоятельный production example завершены.** [Finite probe](../examples/m8/staged_contract_probe.py) использует existing bounded models для синтетических примеров; он не заменяет production tests и аудит исполнения этапов.

## Основание и граница

[Общий аудит ADR-0040](../audits/m8-evaluation-readiness.md) закрыл bounded magic evaluation. Caller теперь задаёт конечный список готовых сценариев, возрастающие размеры пакетов, keep этапов, общий seed, окно и полный верхний бюджет. Контракт следует [M7 / ADR-0032](ADR-0032-staged-mixed-evaluation.md), сохраняя строгие magic types/sequence/error conventions ADR-0040. Generic staged framework или перенос прежних классов не вводятся.

Single-run scope ADR-0037 неизменен: один authored Champion-Wizard/Curse, allied/enemy numeric Shooting Minions, explicit frames/facts/policies и mandatory continuations. Отбор не меняет source, IDs, roster/Wizard/spell, histories, objective, scene frames/routes, policies, perspective_side/max_rounds или окно. Это новые полные прогоны исходного боя, не resume текущего owner/раунда.

Непосредственно сверены локальные BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр.112; Conditions / Broken, стр.122; Magic in the Old World / Casting a Spell / Interrupted Casting, стр.156; Spell Potency / Miscasts and the Rule of Nine, стр.157; Battle Magic / Curse of Cowardly Flight, стр.162; Wounds Table, стр.190–191; BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions и Champions, стр.91–92. Broken/другая Zone не defeat, Champion не Minion, mandatory pending не исчезает ради оценки. Этапы/окно/отбор/бюджет — технический контракт, не house rule; новых Rule IDs нет.

## Pure typed API

Реализованы [balance/magic_staged_evaluation.py](../../src/towr/balance/magic_staged_evaluation.py) и [magic_staged_evaluation_models.py](../../src/towr/balance/magic_staged_evaluation_models.py):

| Тип / функция | Поля или результат |
| --- | --- |
| MagicBalanceStage | trials_per_candidate: int, keep: int |
| MagicStagedEvaluationRequest | candidates: tuple[MagicBalanceCandidate, ...], master_seed: int, stages: tuple[MagicBalanceStage, ...], max_total_trials: int, window: ObjectiveRateWindow; derived planned_trials |
| magic_continuation_candidate_ids(report: MagicBalanceEvaluationResult) | tuple[str, ...] для следующего этапа в исходном порядке |
| MagicStagedEvaluationStatus | COMPLETED="completed", NO_ELIGIBLE_CANDIDATES="no_eligible_candidates" |
| MagicStagedEvaluationResult | source_request: MagicStagedEvaluationRequest, stage_reports: tuple[MagicBalanceEvaluationResult, ...]; derived status, selected_candidate_ids, planned_trials, total_trials, seed_scheme |

Модели frozen/slotted. Ordered candidates/stages/reports принимаются **только tuple/list** и копируются в tuple; generator/set/dict/str не потребляются. Неверные family/type/Enum или bool вместо int → TypeError; пустота/диапазон/неполнота/несогласованность → ValueError. Эти strict magic conventions не меняют исторические исключения M5/M6/M7. Другие scenario/stage/request/report families не принимаются даже при равных строках/полях.

Stage trials — exact int в [1,2**64−1], keep/max_total_trials — positive exact int. Stages непусты, trials строго возрастают; keep может расти или превышать число кандидатов, но не возвращает отсеянных. Один этап допустим. Отдельного top_k у staged request нет: keep последнего этапа задаёт final top_k.

До RNG/runner/pool проверяются **все** stages, включая потенциально недостижимые, весь исходный список, exact IDs, общий uint64 seed, perspective_side и scenario.max_rounds, окно и полный верхний бюджет. Candidate/seed admission переиспользует MagicBalanceEvaluationRequest первого этапа, без матрицы C×S requests. Pure models/helper не исполняют бой и не читают JSON.

Переиспользуются existing MagicBalanceCandidate/Request/Result, MagicAssessmentStatus и **тот же** ObjectiveRateWindow из balance.ranged_assessment_models. Balance принимает только input/aggregate reports, не records/journals. Domain/engine/rules/simulation не зависят от balance/application; shared class/import/pickle paths и старые APIs сохраняются.

## Бюджет полных повторных пакетов

Для C исходных кандидатов и stage specs (N[i],K[i]):

```text
U[0] = C
U[i+1] = min(U[i], K[i])
planned_trials = sum(U[i] * N[i])
```

Это exact Python integer без искусственного uint64 cap на произведение/сумму. Если planned_trials > max_total_trials, request отказывает **до исполнения**, даже если реальные unsupported могли бы сократить работу. Не сокращать stages/keep/N автоматически.

Общая private `_stage_request` в models используется и service, и result guards: текущая упорядоченная подпоследовательность candidates, исходные master_seed/window, trials_per_candidate=N[i], top_k=K[i], **локальный** max_total_trials=len(current candidates)×N[i]. Внешний cap не подставляется вместо точного локального бюджета.

Каждый этап заново исполняет полный пакет с абсолютного index0 и прежней scheme `towr:npc-magic-trial:v1`. При одинаковых input/RNG/runtime предыдущий prefix воспроизводится, но вычисляется повторно. Переход 10→100 расходует 110 trials, не 100 или 90; prefix reuse отсутствует. Номер этапа/IDs/размер N/backend не входят в seed. Оценки этапов не независимы и не складываются как уникальные observations. Общие seeds разных сценариев не гарантируют одинаковых action draws или уменьшения статистической ошибки.

Total_trials — сумма report.total_trials выполненных этапов, включая повторную работу; total_trials <= planned_trials <= max_total_trials. Неиспользованный бюджет не создаёт дополнительные trials. Ошибка не даёт partial success или надёжный счётчик потраченных trials. Budget — не RSS quota; inputs всего списка и aggregate stage reports сохраняются, full records/journals — нет.

## Промежуточный отбор и финальный выбор

Helper требует typed MagicBalanceEvaluationResult. Исключить rows со status UNSUPPORTED_OBSERVATIONS, остальные **включая outside-window и ROUND_LIMIT** стабильно отсортировать по exact Fraction abs(goal_rate−target), взять до report.source_request.top_k, затем вернуть выбранные IDs **в порядке исходных rows**. Следующий input — соответствующая подпоследовательность текущих candidates; порядок по расстоянию не переносится в следующий tie-break.

Bounded selected_candidate_ids по-прежнему требует window_match is True; использовать его как continuation нельзя. Outside/unsupported строки сохраняются в полном report. Любой наблюдавшийся unsupported запрещает продолжение всего кандидата, даже при goal в окне: не удалять trials, не перенормировать знаменатель, не подбирать другой seed ради результата. Отсутствие unsupported в N не доказывает полноту тактики.

| После полного этапа | Действие / derived status |
| --- | --- |
| Непоследний, continuation непуст | Выполнить следующий stage spec |
| Непоследний, continuation пуст | NO_ELIGIBLE_CANDIDATES, selected=(); не создавать пустые reports последующих этапов |
| Последний выполнен | COMPLETED, даже при all-unsupported/пустом selection; выбор только из последнего bounded report |

При одном этапе сразу действует последнее правило. Ранние попадания не возвращаются при позднем отсеве, outside не становится финальным выбором. Все четыре rates сохраняют все N; native perspective_defeated/round_limit_reached и три totals actions/started/completed берутся из magic summary без новой интерпретации.

## Полная source/report chain

Result требует typed root request и непустую tuple/list typed magic reports не длиннее числа stages. Первый report — по всем root candidates, каждый следующий — ровно continuation предыдущего. Full report.source_request должен равняться `_stage_request` по immutable значению: exact candidate IDs/order/full scenarios (Wizard/roster/spell/facts/frames/policies/objective/histories/max_rounds), seed/N/window/local budget/top_k. Equal immutable copies допустимы; чужой source не исправляется rebinding.

Пропущенные/дублированные/переставленные/лишние reports, возврат отсеянных IDs, иной порядок/источник и reports после пустого continuation запрещены. Короткая цепочка допустима только после непоследнего этапа с пустым continuation. Prefix при оставшихся пригодных кандидатах не является завершённым result. Полная цепочка всегда COMPLETED, в том числе при all-unsupported в финале.

Status/selection/budgets/seed_scheme — derived, не init fields. Сохраняется исходный parent request успешного application result. Result не удерживает simulation results/records/journals/RNG/execution options. Structural guards проверяют согласованность supplied aggregates, не происхождение dice или истинность вероятностей.

## Application API и ошибки

Реализованы [application/magic_staged_evaluation_service.py](../../src/towr/application/magic_staged_evaluation_service.py) и [magic_staged_evaluation_errors.py](../../src/towr/application/magic_staged_evaluation_errors.py):

```python
def evaluate_magic_candidates_staged(
    request: MagicStagedEvaluationRequest,
    execution: SimulationExecutionOptions,
) -> MagicStagedEvaluationResult: ...

class MagicStagedEvaluationError(RuntimeError):
    stage_index: int  # from zero
    candidate_id: str | None
```

Typed root request и existing SimulationExecutionOptions проверяются до работы. Один existing evaluate_magic_candidates на реально достигнутый этап, **тот же объект execution**. Этапы/кандидаты последовательны; process только внутри текущего кандидата по ADR-0039/0040. Shared options/path/лимиты прежние, importable main guard и cleanup остаются у existing backend. Новый rng_factory, pools/scheduler/auto backend/persistent pool не добавляются.

После bounded evaluator проверить typed MagicBalanceEvaluationResult и полный source до следующего вызова; затем определить continuation. MagicBalanceEvaluationError оборачивается в MagicStagedEvaluationError(index, candidate_id), сохраняя полную __cause__ chain до исходного worker error/notes. Прочие Exception при построении/исполнении/проверке этапа или continuation получают candidate_id=None. Preflight/options и final staged result constructor errors проходят напрямую, без вымышленного stage. KeyboardInterrupt/SystemExit не оборачиваются.

После сбоя нет следующего stage, partial success, retry/fallback/checkpoint. Traceback может удерживать объекты, внешние side effects не откатываются, мгновенный kill running work не обещается.

## Finite probe и примеры

[staged_contract_probe.py](../examples/m8/staged_contract_probe.py) и [вывод](../examples/m8/staged_contract_probe.output.txt) используют existing magic bounded models и два authored сценария с B4. Только синтетические structurally valid summaries, без battle/RNG/pool execution, staged classes/service или production chain/budget guards.

Окно [9/20,1/2,11/20], кандидаты A,B,C,D, stages=(10,2),(100,1):

| ID | Goals из10 | Unsupported | Continuation |
| --- | --- | --- | --- |
| A | 4 | 0 | Да, distance1/10 |
| B | 7 | 0 | Нет, distance1/5 |
| C | 5 | 1 | Нет, unsupported при goal1/2 |
| D | 6 | 0 | Да, distance1/10 |

Bounded selection пуст, continuation=(A,D). Финальные49/100 и51/100 дают selection(A), total240, future COMPLETED. Inclusive45/100/55/100 тоже оставляютA при tie; outside40/100/60/100 дают пустой final selection. Если D ближе, порядок survivors всё равно(A,D).

Полный budget4×10+2×100=240, cap239 должен отказать; incremental4×10+2×90=220 исключён. Для (10,2),(100,5),(1000,1) bound2240 без возврата отсеянных. ТолькоA после первого этапа даёт actual140; unsupported у каждого кандидата в первом — actual40/future NO_ELIGIBLE; unsupported у каждого финального кандидата — future COMPLETED с пустым selection. All-limit continuation пригоден, point window0 допускает goal0; all-unsupported/zero-action не выбираются. N=2**60+1 сохраняет exact Fraction, float может смешивать разные distances. Проверяются stable ties, исходный порядок и indexed-seed prefix.

Эти суммы/status labels — конечная арифметика, не исполнение/валидация staged request/result. Синтетические counts не доказывают достижимость исходов; они не являются Monte Carlo oracle.

## Матрица реализации и порядок

| Срез | Обязательные проверки |
| --- | --- |
| Pure helper | Magic typed report, отказ других families; outside continuation против final selection; unsupported/all-limit; exact Fraction/ties/cutoff/original order/large N |
| Stage/request | Strict tuple/list/int/types без consumption/coercion, frozen/replace, все stages до исполнения, uint64 N/positive keep/cap, возрастающий N и растущий keep, общий full input/window/seed/perspective/max_rounds, bound240/2240/one-stage, big integers |
| Result | Полная или законно оборванная chain, early/final/one-stage unsupported и empty selection; actual/planned budgets240/140/40, no early-match fallback; exact source/order/seed/N/window/local cap/keep и foreign same-ID scenarios; partial/extra/restored IDs/equal copies; derived/frozen/no records |
| Service | Exact bounded calls и identity execution, полные повторные пакеты index0, outside continuation/early stop, typed full-source до следующего stage; stage/candidate/cause/notes или None, no partial/retry/fallback; preflight/final constructor/BaseException boundaries |
| Real integration | Full sequential/spawn reports/selection равны, source/global RNG/cleanup, rename/reorder/ties; реальные четыре magic outcomes и unsupported внутри окна; stage/candidate startup failure chain; без закрепления Monte Carlo процента/победителя |
| Аудит | Матрица контракта, public production example, late error без partial stdout, external cwd/installed parity, сохранение boundaries предыдущих APIs |

Порядок: (1) pure helper + frozen models/status с общей private `_stage_request`, deterministic tests; (2) application service/error + deterministic/real-backend integration; (3) общий аудит и standalone production example. Production staged API не объявляется готовым по этому probe. Bounded evaluator, rules/engine/simulation и прежние formats не меняются. Generation/prefix reuse/JSON/CLI, confidence presets и новые gameplay consumers — отдельные задачи.

## Проверка контрактного среза

2026-10-27, CPython3.12.15/macOS26.5.1 arm64: root probe и three-file external-cwd bundle дали stored stdout/empty stderr. [Один новый subprocess test](../../tests/integration/test_m8_magic_staged_contract_probe.py) — OK (0,259 с). Проверены finite synthetic budgets240/140/40/2240, original order/ties/windows/unsupported/all-limit/zero-action, exact large Fraction и indexed-seed prefix; будущие staged guards/service этим не реализованы.

Прежний installed wheel побайтно совпал с current src по 416 Python/Schema files. Новый probe без PYTHONPATH вне repo прошёл обычным и guarded запуском с запрещёнными RNG/runner/evaluator/pool calls. Fresh build не делался: runtime неизменен, README metadata прежнего wheel исторический. Evidence `/private/tmp/towr-m8-staged-contract-installed-report.json`.

Полная регрессия: **3205 tests / 33 прежних errors (101,004 с)**; Counter полных error headers/signatures точно равен previous baseline, новых ошибок нет. Compileall, 3040 локальных Markdown-путей, 77 anchors, public imports и whitespace — OK. Код production/прежние Python-файлы не менялись; source/harness hash `ac055c19711c8d2f124931f3b07c3ff7dbadeb51829bf785544980cbaebb0ec1` сохранён, новых performance-измерений нет. Итоговые commands/checks — в [статусе](../project-status.md#последняя-проверка).

Независимый reviewer сопоставил ADR/probe/tests и непосредственно книжные страницы, блокеров нет. На старте 21 existing dirty/untracked файлов учтены отдельно; commit/push не выполнялись. Следующий срез — pure helper/frozen staged models с deterministic tests, затем application service/real-backend integration и аудит.

## Реализация первого среза: helper и frozen models

2026-10-27: magic_continuation_candidate_ids и MagicBalanceStage/MagicStagedEvaluationRequest/Result/Status реализованы двумя отдельными balance modules. Helper выбирает ELIGIBLE, включая outside-window, по exact Fraction distance/top_k и возвращает original order. Final selection остаётся window-only из последнего bounded report.

Strict tuple/list/type/int guards не потребляют generators и не приводят bool/float/str. Все stage specs и candidate input проверяются до execution; общий бюджет — полные повторные пакеты с Python integer без cap на сумму. Private _stage_request единообразно задаёт exact local cap/source/N/window/keep; result требует всю законную source/report chain. Early exhaustion и complete final с empty/all-unsupported selection различаются. Модели не исполняют runner/RNG/pool и не удерживают records/journals.

[21 новый deterministic test](../../tests/unit/test_m8_magic_staged_evaluation.py) — **OK (0,047 с)**. Проверены budgets240/140/40/2240/1140 и big integers, strict containers без consumption, late invalid specs/common fields, exact local requests/seed prefix, Fraction/order/ties/large-N, early/final/one-stage unsupported и literal all-unsupported/zero-action. Chain guards отвергают partial/extra/reordered/restored IDs, foreign seed/N/window/cap/keep и same-ID Wizard/profile/pair-frame source в обоих этапах. Equal copies без rebinding, frozen/replace/pickle и recursive aggregate-only purity проверены; ranking observations синтетические.

Независимый reviewer сопоставил production/tests с ADR, блокеров нет. На старте HEAD a422d25 и чистое дерево; прежние APIs/классы, domain/engine/rules/simulation/application/tools и contract probe/output/test не менялись. Общий source/harness hash изменился из-за двух новых balance modules, новых performance-измерений нет. Installed wheel новых staged models и другие runtime/ОС в этом срезе не проверялись; прежняя installed evidence выше относится к контрактному probe.

Следующий срез — application/magic_staged_evaluation_service.py и magic_staged_evaluation_errors.py: existing bounded evaluator по достигнутым этапам с тем же execution options, полные повторные пакеты и stage/candidate cause chain без partial/retry/fallback. Затем отдельный аудит/public production example. Полная регрессия: **3226 tests / 33 прежних errors (105,554 с)**, точные error Counters равны предыдущей вехе, новых ошибок нет. Compileall, 3056 локальных Markdown-путей, 75 anchors, import boundaries/purity и whitespace — OK. Команды — в [статусе](../project-status.md#последняя-проверка).

## Реализация второго среза: application staged service

2026-10-27: evaluate_magic_candidates_staged и MagicStagedEvaluationError реализованы двумя отдельными application modules. Typed root/options до работы, exact local stage request, один existing bounded evaluator на достигнутый этап с тем же объектом execution. Typed report/full source проверяется до continuation/следующего вызова; полные пакеты повторяются от index0. Early exhaustion/final-empty semantics сохраняются.

MagicBalanceEvaluationError оборачивается со stage_index/candidate_id, полная cause/worker-note chain остаётся доступна; прочие stage errors имеют candidate_id=None. Preflight/final constructor и BaseException проходят напрямую. Нет следующего этапа после ошибки, partial success, retry/fallback/checkpoint, нового rng_factory или pools/framework. Успешный staged result хранит inputs и полные aggregate stage reports.

[9 unit tests](../../tests/unit/test_m8_magic_staged_evaluation_service.py) и [3 real-backend integration](../../tests/integration/test_m8_magic_staged_evaluation.py) — **12 OK (1,720 с)**. Проверены exact local calls/options identity, outside continuation, полный повтор N10/N100 и seeds, upper/actual budgets 240/140/40, typed full source до helper, equal source copies без rebinding, second-stage candidate failure без третьего и nested cause/notes. Source guards покрывают other families и same-ID Wizard/profile/frames, seed/N/window/local cap/keep; assembly/continuation errors, interrupts и final constructor boundaries сохранены.

Real sequential/spawn reports равны для двух authored альтернатив при repeat/rename/reorder. Scripted N3→N4 даёт actual7, COMPLETED с пустым финалом: поддержанный outside-window prefix продолжает, финальный N4 содержит unsupported при goal в point window. N4→N5 останавливается после 4 trials с NO_ELIGIBLE_CANDIDATES; N5 не исполняется. Native counts/totals 23/9/9 и 24/10/9, input/global RNG/children и child PID проверены. Startup failure сохраняет staged→candidate→original error chain без fallback.

Независимый reviewer сопоставил production/tests с ADR, блокеров нет. На старте 14 existing dirty/untracked файлов pure-среза учтены отдельно; прежние Python-файлы/guards/probe/output/test не менялись. Domain/engine/rules/simulation/balance и shared classes прежние; source/harness hash меняется только из-за новых application modules, новых performance-замеров нет. Installed wheel нового staged service в этом срезе не проверялся. Полная регрессия: **3238 tests / 33 прежних errors (106,089 с)**, точные Counters ошибок равны предыдущей вехе; новых ошибок нет. Compileall, 3072 Markdown-пути, 78 anchors, import boundaries/purity, исходные Python SHA и whitespace — OK. Команды/ограничения — в [статусе](../project-status.md#последняя-проверка).

Следующий срез — общий аудит staged magic evaluation: pure models/helper/service/error, все tests и ограничения контракта; standalone production example полного sequential/process staged report со stored output, поздняя ошибка без partial stdout и installed-package parity. Generation/prefix reuse/JSON/CLI и новые gameplay consumers в аудит не входят.


## Общий аудит staged evaluation

2026-10-27: [Readiness matrix](../audits/m8-staged-evaluation-readiness.md) закрыла ADR-0041: 33 implementation tests и два новых example tests, public four-file example/stored output, late stage/candidate failure без partial stdout, external cwd и fresh installed parity420 files. Production src и прежние tests/tools не менялись; scope/источники/ошибки/границы памяти прежние. Полная регрессия: 3240 tests / 33 прежних errors (115,653 с), точные error Counters равны предыдущей вехе, новых ошибок нет. Следующий срез — контракт ограниченной генерации magic-кандидатов, без production реализации до фиксации проекций и бюджетов.


Продолжение после аудита: [ADR-0042](ADR-0042-magic-composition-generation.md) и [finite probe](../examples/m8/generation_contract_probe.py) ограниченной генерации magic-составов подготовлены. Staged helper/models/service не меняются; новый generator будет передавать полный готовый MagicStagedEvaluationRequest. Следующий implementation-срез — group/request preflight, без materialization/новых gameplay rules.
