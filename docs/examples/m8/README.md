# Примеры магии M8

[ADR-0035](../../decisions/ADR-0035-cowardly-flight-casting-boundary.md) реализован и закрыт [аудитом](../../audits/m8-casting-readiness.md) в границе одного Casting-действия с Curse of Cowardly Flight. [Input](../../../src/towr/domain/cowardly_flight_casting_models.py), [result](../../../src/towr/domain/cowardly_flight_casting_result_models.py) и [executor](../../../src/towr/engine/cowardly_flight_casting.py) доступны через typed Python API. Существующие mixed JSON/CLI не принимают мага или spell.

## Самостоятельный production-пример

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m8/casting_action.py
```

[casting_action.py](casting_action.py) использует execute_cowardly_flight_casting и public models/scheduler, без imports tests или private helpers. [Сохранённый вывод](casting_action.output.txt) проверяется [subprocess test](../../../tests/integration/test_m8_casting_example.py) из временного cwd. Запуск с отдельно установленным wheel также проверен: код загружен из installed target, stdout совпал, stderr пуст.

Шесть supplied activations расходуют ровно 24 scripted d10:

- WAIT с одним успехом → следующая активация с двумя успехами → CAST CV3/Potency2; first сопротивляется, second получает Broken.
- Pool == Wizard Level оставляет WAIT; следующая активация с pool > Level возвращает MISCAST_REQUIRED, даже при достаточных successes. Сохраняются pool, successes, receipt и pending source; preparation, desperate spell и таблица не выполняются.
- Удержанные ранее 3 successes и последний roll 0 дают Potency0, два target records без Willpower Tests.
- Пустая Zone даёт CAST без target Tests.

Проверяются один receipt на действие, unchanged inputs/spatial/global RNG и отказ повторного returned slot, чужого actor и обязательного pending Miscast до RNG. Числа caster `3d/3`, Level2 и Minion-целей `3d/3` — authored inputs, не профиль Hermit Witch. Caster не получает Minion injury policy. Изолированная Zone объясняет невозможность Give Ground; дальность и факты задаются явно.

Переходы между activations поставляет caller; пример не симулирует промежуточные ходы, следующий ход Broken, полный бой или objective/Monte Carlo. Настоящий переход раунда отдельно покрыт [integration tests](../../../tests/integration/test_m8_cowardly_flight_casting.py). Broken сохраняется как Condition, не defeat.

## Предварительный probe K1

[casting_contract_probe.py](casting_contract_probe.py) сохранён как пример ранней композиции отдельных K1 reducers; он не вызывает новый M8 executor:

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m8/casting_contract_probe.py
```

Для использования production API выбирайте casting_action.py. Probe остаётся исторической проверкой составимости нижних фаз.

Источники: **BOOK-PLAYER-GUIDE 1.4**, Rules / Combat Actions / Improvise, стр. 117; Conditions / Broken, стр. 122; Magic in the Old World / Casting a Spell / Interrupted Casting, стр. 156; Spell Potency / Miscasts and the Rule of Nine, стр. 157; Formal Spells, стр. 160; Battle Magic / Curse of Cowardly Flight, стр. 162. **BOOK-GM-GUIDE 1.1**, Allies and Antagonists / Champions, стр. 92; Hermit Witch, стр. 130.

[Контракт интеграции ADR-0036](../../decisions/ADR-0036-magic-encounter-integration.md) и standalone Give Ground completion реализованы. Пример casting_action.py сохраняет исходную границу без движения. MOVEMENT_REQUIRED и completion уже перенесены в roster/Champion owner; первый Broken Recover (safe/free move) с Casting interruption также реализован. Обычный Broken Run также реализован отдельно; первый end-turn Stomach Blow → expiry Drained также реализован. Другие timed effects, terrain/Athletics и обязательные Miscast continuations остаются отдельными consumers. Одиночный runner заявленной границы реализован ниже.

## Контракт первого encounter

[ADR-0037](../../decisions/ADR-0037-magic-scenario-runner.md) задаёт один authored Champion-Wizard, союзный и вражеский Minion, актуальные scene facts, objective/лимит и полные unsupported stops. Production [scenario/facts/policies](../../../src/towr/domain/npc_magic_scenario_models.py) и [scene models](../../../src/towr/domain/npc_magic_scene_models.py) с pure admission реализованы. [encounter_contract_probe.py](encounter_contract_probe.py) проверяет этот вход и композицию прежних компонентов; result и runner реализованы в следующих разделах.

```sh
PYTHONPATH=src python docs/examples/m8/encounter_contract_probe.py
```

[Сохранённый вывод](encounter_contract_probe.output.txt): production admission расходует 0 d10, action chains — 38 scripted d10 (6 дополнительных для оставшегося хода союзника перед реальным advance/start). Public helper admitted_scenario() собирает полный frozen вход из authored initial(), с explicit GM flags/routes/defeat choices. Lookup ещё не заданного будущего frame возвращает None. Probe не импортирует tests/private helpers, сохраняет исходные snapshots и global RNG. Все activations запускают full-owner wrappers над существующим scheduler, порядок сторон обычный; отдельные fixtures меняют сторону Wizard, без фиктивных промежуточных ходов.

- 10 d10: обычная incoming Shooting → Stomach Blow/daily receipt → Wizard Casting → target-turn expiry Drained, с сохранением Wound/магии/histories.
- 7 d10: Nicked Arm сохраняет полный Endurance follow-up и блокирует end-turn.
- 6 d10: Curse → обязательный Give Ground → Willpower/Broken → end-turn; один Casting receipt, обновлённые позиции, Broken не defeat.
- 3 d10: Miscast сохраняет весь pool/source/receipt и останавливается до preparation/table/desperate choice.
- 6 d10: bound Minion Attack переносит defeat/full pending в magic owner. End-turn блокируется, затем explicit knocked-out decision/GM approval закрывает pending и исключает ожидающую цель без новых d10; после этого caller явно завершает ход атакующего.

Принятый scenario.initial далее используется в реальной Curse → Give Ground цепочке; после движения новый key отсутствует в supplied frames, без выдуманного контекста. [31 deterministic test](../../../tests/unit/test_m8_npc_magic_scenario.py) дополнительно проверяет frozen/source/type/role/partition/Range/Speed/route guards, обе Wizard/perspective стороны и independent orders. Все 238 M8 tests проходят.

`scenario.initial_runtime_state` присоединяет пустой Minion ledger до первой активации; сам scenario.initial остаётся fresh admitted source. Probe использует этот runtime в Curse, incoming Champion Wound и Minion handoff. [Bound models](../../../src/towr/domain/npc_roster_minion_attack_models.py) и [executor/application](../../../src/towr/rules/npc_roster_minion_attack_resolution.py) сохраняют полный source/pending без второго Attack. 19 unit + 6 integration tests покрывают перенос/блокировки/оба ledgers, все 263 M8 tests проходят.

Bound defeat [models](../../../src/towr/domain/npc_roster_minion_defeat_models.py)/[functions](../../../src/towr/rules/npc_roster_minion_defeat_resolution.py) добавлены; пример сохраняет source/decision, exact acknowledgement ID и полный roster/round. Replay закрытого результата отвергается. Это не narrative inventory/death engine: equipment и injury повторно не меняются. 10 unit + 4 integration tests, все 277 M8 tests проходят.

Probe не выбирает маршруты/тактику автоматически, не выполняет полный бой и не проверяет четыре будущих outcomes. [Full-owner start/advance](../../../src/towr/domain/npc_roster_turn_models.py) реализованы: 17 новых tests, 294 M8 суммарно; фазы расходуют 0 d10, сверяют pending/таймеры и сохраняют архив/оба ledgers. Typed encounter steps/result/unsupported с pure chain validation реализованы ниже; следующий срез — runner. Raw M2 round API остаётся Minion-only; общие чистые defeat/exclusion helpers переиспользуются без фиктивного round с Champion.

## Typed encounter journal

[Журнал/result/unsupported](../../../src/towr/domain/npc_magic_scenario_result_models.py) и [step models](../../../src/towr/domain/npc_magic_step_models.py) реализованы; single-run runner реализован в следующем разделе. [journal_contract_probe.py](journal_contract_probe.py) собирает только явно исполненные bound results, используя public authored fixture предыдущего probe.

```sh
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python docs/examples/m8/journal_contract_probe.py
```

[Сохранённый вывод](journal_contract_probe.output.txt): 3 d10 — Miscast с полным pending до preparation; 9 d10 — WAIT, ally Attack, supplied knockout acknowledgement и explicit end-turn до objective. Проверка chain расходует 0 d10, сохраняет исходный snapshot/global RNG, archive и оба ledgers. Current/outcome/started_rounds/completed_rounds/executed_actions выводятся из результатов, без подставленного final state. Усечённый prefix без обязательного end-turn отвергается. Это самостоятельная проверка нового public API, не автоматический encounter loop.

19 unit + 11 integration tests (324 M8 суммарно) покрывают четыре outcomes, source/phase/actor/target/GM/scene/route guards, real round advance, Wound/pending/expiry, Broken Recover/Run и missing intermediate Curse frame. Staged movements остаются в typed diagnostic, полный pending — в root. Single-run executor по ADR-0037 реализован ниже.

## Single-run runner probe

[scenario_runner_probe.py](scenario_runner_probe.py) вызывает production [run_npc_magic_scenario](../../../src/towr/engine/npc_magic_scenario_runner.py) для authored трёх участников; [вывод](scenario_runner_probe.output.txt) проверяется subprocess test из внешнего cwd.

```sh
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python docs/examples/m8/scenario_runner_probe.py
```

Пять независимых calls: objective (6 d10), independent perspective defeat (6), два полностью завершённых раунда до limit (30), Miscast до preparation (3), Curse/Give Ground/Willpower → missing future frame (6). Всего 51 scripted d10. Начатый раунд и завершённый считаются отдельно; обязательные defeat acknowledgement/end-turn предшествуют outcome. Все owners/archives, source и global RNG сохраняются.

Пример явно задаёт `NpcMagicAttackDeparture` для Wizard/ally/enemy в открытой authored сцене. Это facts ordinary Attack, отдельно от Curse away-route. Без строки для выбранной цели runner возвращает ACTION/MISSING_ROUTE до Attack Test. Прежние ручные probes сохраняют свои bound source facts и исторические budgets; они не стали автоматическими runners.

19 unit + 21 integration tests (364 M8 суммарно) также проверяют Wound/daily/expiry, архивную цель после advance, Broken Recover/Run, repeated Staggered, directed approval, checked Curse prefix и propagation ошибок без retry. Аудит одиночной границы и standalone installed-wheel проверка завершены ниже; массовые magic-прогоны/метрика/JSON/CLI не реализованы.

## Самостоятельный пример одиночного encounter

[magic_scenario.py](magic_scenario.py) строит полный authored scenario через public domain APIs и вызывает production runner. Импорты других examples/probes/tests и private helpers отсутствуют. Его можно скопировать одним файлом и запустить из любой директории с установленным пакетом.

```sh
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python docs/examples/m8/magic_scenario.py
```

[Сохранённый вывод](magic_scenario.output.txt): 9 calls/107 scripted d10. Четыре outcomes, полный Curse → Give Ground → Broken → Recover, Wound/daily через advance и снятие Drained после следующего Wizard turn, Wound pending и missing frame/departure. Каждый call получает новый scripted RNG; budgets фиксированы, это не Monte Carlo rates. Roster и spatial orders различаются. Оба ledgers, source и global RNG сохраняются; Wound expiry не лечит Wound.

[Subprocess test](../../../tests/integration/test_m8_magic_scenario_example.py) запускает один скопированный файл без siblings из временного cwd. Offline wheel установлен в отдельный target; тот же файл дважды запущен с -S, только installed target в PYTHONPATH и проверкой import origin. Stdout совпал, stderr пуст. Production src не менялся.

[Аудит одиночной границы](../../audits/m8-encounter-readiness.md) завершён: 365 M8 tests проходят. Заявленная граница не включает остальные Conditions/Champion/Wound/Miscast consumers, массовые прогоны, метрику/подбор или JSON/CLI. Следующий срез — отдельный контракт последовательных magic-прогонов над текущим runner.

## Контракт независимых magic-прогонов

[ADR-0038](../../decisions/ADR-0038-independent-magic-simulations.md) и [simulation_contract_probe.py](simulation_contract_probe.py) готовы как технический контракт. Этот probe предшествовал production API и использует локальные illustrative observations; готовая реализация и её validators описаны ниже.

```sh
PYTHONPATH=src /private/tmp/towr-test-venv/bin/python docs/examples/m8/simulation_contract_probe.py
```

[Вывод](simulation_contract_probe.output.txt): один immutable input с B=4, четыре scripted outcomes по одному, 120 d10. Totals — 24 actions, 10 started rounds, 9 completed rounds; Miscast учитывается отдельно. Enemy сначала побеждает allied Minion, затем в других раундах может смертельно ранить Champion-Wizard; supplied archive frame сохраняется. Отдельная zero-action missing-departure остановка показывает одинаковые ID/seed при другом полном source.

Предложены magic seed namespace и три golden vectors, проверенные также struct encoding; ranged/Melee/mixed seeds не меняются. Ещё 26 seeded calls проверяют repeat/reverse/расширение prefix, extra-draw isolation и rename-ID observations. Во всём probe 31 single-run call, вход/global RNG неизменны; ожидаемые Monte Carlo-проценты не фиксируются.

Compact record хранит shared immutable input и scalars, без final owner/journal/pending. Parent проверяет полный source и derived seed/index; summary получает input и totals/counts, без records. Production models, execution и summary теперь реализованы и проверены [аудитом](../../audits/m8-simulation-readiness.md). Новая метрика/процессы/JSON/CLI не вводятся.


## Независимые последовательные прогоны — production API

```sh
PYTHONPATH=src python docs/examples/m8/magic_simulation.py
```

[magic_simulation.py](magic_simulation.py) использует public NpcMagicSimulationRequest, run_npc_magic_trial/run_npc_magic_simulation и summarize_npc_magic_simulation. Для копирования примера нужны два соседних файла: он и [magic_scenario.py](magic_scenario.py). [Stored output](magic_simulation.output.txt) проверен внешним subprocess test и на установленном wheel без PYTHONPATH.

Четыре scripted trials одного input дают все четыре исхода: totals 24 actions / 10 started / 9 completed и 120 d10. Отдельный replay проверяет 3 Champion Wounds/daily receipts/rolls, смерть Wizard и архив defeated ally. Zero-action missing-departure stop использует иной полный source при тех же ID/seed; смешивание records отклоняется. Ещё 26 seeded calls проверяют repeat/reverse/prefix/extra-draw isolation/rename; всего 32 single-run calls. Input/global RNG сохраняются. Counts и totals — наблюдения finite scripts, не Monte Carlo rates или difficulty.

[Аудит ADR-0038](../../audits/m8-simulation-readiness.md) закрывает только последовательный simulation/summary слой. Process backend, profiling, assessment/balance/generation и JSON/CLI не добавлены; single-run scope и обязательные unsupported stops сохраняются.


## Контракт magic process transport/spawn

[ADR-0039](../../decisions/ADR-0039-process-magic-simulations.md), [finite probe](process_contract_probe.py), [stored output](process_contract_probe.output.txt) и [аудит](../../audits/m8-process-contract-readiness.md) готовы. Этот probe предшествовал production API: он использует existing trial/result/summary и фиксированные маленькие partitions, без lazy/refill/cancel scheduler. Готовая реализация проверена отдельно ниже.

В активированном Python 3.12+ окружении:

```sh
PYTHONPATH=src python docs/examples/m8/process_contract_probe.py
```

Для внешнего cwd нужны три соседних файла: этот probe, [magic_simulation.py](magic_simulation.py), [magic_scenario.py](magic_scenario.py). Root и external-cwd subprocess дают одинаковый stdout и пустой stderr. 19 успешных transported trials в 10 fixed batches, отдельный failed batch и шесть закрытых spawn pools; точное число worker startups не фиксируется.

Проверены workers=1/2 и reverse collection, четыре scripted outcomes одного source (24 actions / 10 started / 9 completed, 120 d10 на полный N=4 run), отдельный zero-action stop. После проверки full source все final records разделяют исходный parent scenario; межпакетные pickle copies не накапливаются в итоговом result. 15 отрицательных post-pickle проверок покрывают source/type/index/seed/Enum/bool/counters. Factory failure index1 сохраняет обе notes, marker0/1 подтверждает отсутствие index2; partial result не выдаётся. Performance, public preflight, lazy scheduling и прочие executor failures этим не проверены.


## Опциональный process backend — production API

[run_npc_magic_simulation_parallel](../../../src/towr/simulation/npc_magic_parallel.py) реализует ADR-0039; [аудит](../../audits/m8-process-readiness.md) отделяет готовый API от исторического probe. Public request/result/summary и seed scheme сохраняются, все итоговые records используют исходный parent scenario. Workers/batch_size — явные положительные int; default batch_size=32 не объявляется optimum.

```sh
PYTHONPATH=src python docs/examples/m8/magic_parallel.py
```

[Пример](magic_parallel.py) копируется вместе с соседними [magic_simulation.py](magic_simulation.py) и [magic_scenario.py](magic_scenario.py). [Вывод](magic_parallel.output.txt) совпадает в root, external cwd и installed wheel без PYTHONPATH. Шесть public calls исполняют 24 trials в spawn, включая workers=1, batch>N/workers>batches, четыре scripted outcomes и zero-action stop. Input/global RNG и parent source identity сохраняются, дети закрываются. Это correctness evidence, не throughput или difficulty measurement.

30 новых tests покрывают preflight/transport/bounded lazy scheduling, ошибки и реальные процессы; три первоначальных contract probe файла сохранены побайтно. [Performance-сравнение](../../benchmarks/README.md#m8-sequential-и-spawn) завершено отдельно с startup/serialization/normalization/shutdown; [общий аудит массовой simulation](../../audits/m8-mass-simulation-readiness.md) закрыт. Auto backend, cache, balance/generation и JSON/CLI не добавлены.

## Контракт оценки magic-кандидатов

[ADR-0040](../../decisions/ADR-0040-magic-candidate-assessment.md) задаёт отдельные assessment/list/service types; pure assessment, list models и service реализованы; [общий аудит bounded evaluation](../../audits/m8-evaluation-readiness.md) завершён. Переиспользуются существующие ObjectiveRateWindow и SimulationExecutionOptions; вся выборка N остаётся знаменателем, любой наблюдавшийся unsupported запрещает window assessment.

```sh
PYTHONPATH=src python docs/examples/m8/assessment_contract_probe.py
```

[Probe](assessment_contract_probe.py) копируется вместе с magic_simulation.py и magic_scenario.py. [Вывод](assessment_contract_probe.output.txt) проверяется external-cwd subprocess test. Синтетические summaries показывают inclusive/point windows, stable Fraction ties, бюджет 20 / cap 19 и большие N без float rounding; это арифметика, не реализованный production preflight.

Реальные полные N4 sequential/spawn дают outcomes1/1/1/1, actions24/started10/completed9: goal1/4 в окне, но unsupported требует будущего match=None. Независимый полный N3 исполняется заново в обоих backend, без фильтрации N4: outcomes1/1/1/0, totals23/9/9, goal1/3 и future match=True. Всего 14 trials за четыре calls; полные results/summary, original source identity/input/global RNG и cleanup проверены. Scripted observations не являются Monte Carlo difficulty estimate. Pure assessment реализован в production отдельно от probe; list models с preflight/report/ranking также готовы. Service/errors/integration также реализованы; общий аудит и самостоятельный production example также завершены. Staged реализован отдельным срезом ниже; production generation/JSON/CLI ещё не готовы.

Pure API: [assess_magic_candidate](../../../src/towr/balance/magic_assessment.py) принимает NpcMagicSimulationRequest, NpcMagicSimulationSummary и тот же ObjectiveRateWindow. [Frozen assessment](../../../src/towr/balance/magic_assessment_models.py) сохраняет полный source, возвращает четыре Fraction rates от всех N и status/window_match без runner/RNG/records. Любой unsupported даёт None; равная immutable копия source допускается, foreign input отклоняется.

[Magic list models](../../../src/towr/balance/magic_evaluation_models.py) принимают готовые authored scenarios, общий seed/N/round budget/perspective и полный max_total_trials до исполнения. Request не вызывает RNG/runner; report содержит все aggregate rows в исходном порядке и выбирает только window_match=True по точной Fraction distance с сохранением ties. [evaluate_magic_candidates](../../../src/towr/application/magic_evaluation_service.py) исполняет список по explicit SimulationExecutionOptions; процессный caller использует importable main guard. Ordinary candidate errors сохраняют ID/cause/worker notes, report публикуется только полный.


## Самостоятельная оценка списка — production API

```sh
PYTHONPATH=src python docs/examples/m8/magic_evaluation.py
```

[magic_evaluation.py](magic_evaluation.py) копируется вместе с magic_simulation.py и magic_scenario.py. Он вызывает public evaluate_magic_candidates для двух authored target-priority альтернатив в sequential/process (workers2/batch3): seed42/B4/N8, planned/max16 на evaluation, окно [1/4,1/2,3/4], top_k2. Полные reports/source identity/budget и input/global RNG/children проверяются до первого stdout. [Stored output](magic_evaluation.output.txt) — finite observation, не difficulty estimate; пустой selection допустим.

[Два integration tests](../../../tests/integration/test_m8_magic_evaluation_example.py) проверяют external-cwd bundle и поздний отказ второго кандидата после первых8 real trials: stdout пуст, stderr содержит ID/cause/note, процессный run не стартует. Fresh installed wheel вне repo без PYTHONPATH дал тот же успех и корректный error path; все416 Python/Schema files равны src. [Общий аудит](../../audits/m8-evaluation-readiness.md) фиксирует sources/ownership/ограничения. Staged закрыт отдельным аудитом ниже; generation развивается по ADR-0042, M8 JSON/CLI требует следующего контракта.


## Контракт поэтапной оценки magic-списка

```sh
PYTHONPATH=src python docs/examples/m8/staged_contract_probe.py
```

[ADR-0041](../../decisions/ADR-0041-staged-magic-evaluation.md), [probe](staged_contract_probe.py) и [stored output](staged_contract_probe.output.txt) фиксируют finite synthetic cases через existing bounded models. Для копирования нужны также magic_simulation.py и magic_scenario.py. Бой/RNG/pool не исполняются; production staged guards и service пример не реализует; helper/models проверены отдельно.

Continuation выбирает ELIGIBLE даже вне окна и возвращает исходный порядок; финал требует window_match=True. Проверены budgets240/140/40/2240, полный повтор10→100 вместо prefix reuse, exact Fraction/ties/point windows/all-limit/all-unsupported и indexed-seed prefix. Числа — synthetic aggregates, не Monte Carlo observations. Pure helper/frozen staged models реализованы отдельно от probe; application orchestration/error и real-backend integration также реализованы; [общий аудит](../../audits/m8-staged-evaluation-readiness.md) завершён, production example приведён ниже.

[magic_continuation_candidate_ids](../../../src/towr/balance/magic_staged_evaluation.py) принимает полный bounded report и возвращает ELIGIBLE survivors в исходном порядке, включая outside-window. [Staged models](../../../src/towr/balance/magic_staged_evaluation_models.py) проверяют upper budget и непрерывную exact source/report chain, различают early exhaustion и complete final с пустым выбором. Полные stage reports сохраняют все observations; runner/RNG/pool в этих pure APIs нет.

[evaluate_magic_candidates_staged](../../../src/towr/application/magic_staged_evaluation_service.py) принимает готовый MagicStagedEvaluationRequest и explicit SimulationExecutionOptions, исполняет полный bounded run по достигнутым этапам. [MagicStagedEvaluationError](../../../src/towr/application/magic_staged_evaluation_errors.py) хранит stage_index (с 0) и optional candidate_id, полная cause/worker-note chain сохраняется. Process требует importable main guard; retry/fallback/partial success нет. Самостоятельный staged production example появится вместе с общим аудитом.


## Поэтапная оценка magic-кандидатов

```sh
PYTHONPATH=src python docs/examples/m8/magic_staged_evaluation.py
```

[Самостоятельный пример](magic_staged_evaluation.py) использует public staged API и builder/printer из magic_evaluation.py. Для запуска вне репозитория скопируйте четыре файла: magic_staged_evaluation.py, magic_evaluation.py, magic_simulation.py и magic_scenario.py; пакет towr должен быть установлен. Process требует importable entry point с main guard.

Две authored альтернативы меняют только enemy target priority. Seed 42, B4, окно [1/4,1/2,3/4], этапы (8,keep=1),(32,keep=1), верхний бюджет 2×8+1×32=48 trials на backend. Каждый этап заново исполняет полный пакет от index0; 8→32 стоит 40 на продолжающего кандидата. Counts этапов не складываются в одну оценку.

Полные sequential/process reports, source identity, planned/actual, input/global RNG и отсутствие детей проверяются до печати. Process workers=2/batch_size=3. [Stored output](magic_staged_evaluation.output.txt) — локальные observations CPython3.12.15/macOS arm64: N8 ally-first даёт 6 goals/2 unsupported; wizard-first 8 goals/0 unsupported вне окна и продолжает. Финальный N32 wizard-first даёт 23 goals/4 round_limit/5 unsupported: goal23/32 в окне, но selected пуст, status COMPLETED. Actual48 на backend, 96 на запуск. Это наблюдение, не preset/гарантия сложности/ожидаемый победитель тестов.

При ошибке второго этапа entry point сохраняет stage_index/candidate_id и cause/notes, stdout пуст. [Два integration tests](../../../tests/integration/test_m8_magic_staged_evaluation_example.py) проверяют четыре скопированных файла из external cwd и поздний отказ после реальных 16 trials первого этапа. [Аудит](../../audits/m8-staged-evaluation-readiness.md) содержит installed-package evidence и ограничения; новых gameplay правил, generation или M8 JSON/CLI нет.


## Контракт генерации magic-составов

```sh
PYTHONPATH=src python docs/examples/m8/generation_contract_probe.py
```

[ADR-0042](../../decisions/ADR-0042-magic-composition-generation.md), [probe](generation_contract_probe.py) и [stored output](generation_contract_probe.output.txt) задают четыре конечных vectors вручную и строят public domain/staged inputs без battle/RNG/evaluator/pool. Для копирования нужен также magic_scenario.py. Wizard+ally fixed; groups A=(E2,E1)1..2 и B=(E3)0..1 дают roster sizes3/4/4/5, pair counts2/4/4/6. Stages10keep2/100keep1 требуют240. Другой perspective сохраняет Wizard вне groups; all-zero Minion vector исключён ради обязательных allied/opposing Minions.

Проекции сохраняют full snapshots/caster/day_id/whole graph, независимые orders, priorities/defeat decisions, True/False flags и seed prefix. Два source frames различаются перемещением E1: удаление E1 объединяет только полностью равные projections; конфликт оставшегося departure flag отклоняется. Удаление врага, делающее moving Broken plan недопустимым, также отвергается, без автоматического Recover. Всего шесть refusals: staged budget239, missing pair, manual frame-source mismatch, conflicting collapse, invalid Broken plan и удаление единственного Wizard ally.

Ручные arithmetic/equality/projection assertions демонстрируют будущие semantics; production group/request/C/cap/ordered frame source guards реализованы отдельно от probe; construction/result/error и generator также реализованы отдельно от ручного probe; сквозная integration проверена7tests, [общий аудит](../../audits/m8-generation-readiness.md) завершён. [Один subprocess test](../../../tests/integration/test_m8_magic_generation_contract_probe.py) проверяет two-file external-cwd/stdout parity. Empty-live/archive projection остаётся обязательной последующей production проверкой; [group/request models](../../../src/towr/application/magic_candidate_generation_models.py) и их deterministic tests проверяют preflight отдельно от ручного probe. Новых игровых правил/house rules нет.


[generate_magic_candidates](../../../src/towr/application/magic_candidate_generation.py) принимает typed MagicCandidateGenerationRequest и возвращает [MagicCandidateGenerationResult](../../../src/towr/application/magic_candidate_generation_models.py) с исходным request и готовым MagicStagedEvaluationRequest. Порядок vectors/IDs/prefixes и полные projections проверяются exact source guards; invalid subset/frame collision/route прерывает весь вызов с [candidate/counts/cause](../../../src/towr/application/magic_candidate_generation_errors.py), без skip/partial. Result хранит inputs, без observations/RNG/options. Самостоятельный production-пример генерация → evaluation приведён ниже; finite probe выше сохранён как контрактная evidence, не вызывает новый generator.


[Backend integration](../../../tests/integration/test_m8_magic_candidate_generation.py) сравнивает полные sequential/spawn reports и parent sources четырёх generated составов, repeat/rename seeds и native counters. Scripted all10 RNG через existing simulation boundary подтверждает4×2+2×4=16 trials на backend и actual child PID. [Generated encounter integration](../../../tests/integration/test_m8_magic_generated_encounters.py) исполняет Curse по1..3 retained targets в roster order, все movements до Willpower, Broken→Recover, полный supplied defeat decision и архивный placement перед следующим Casting. Missing future scene остаётся exact unsupported: один target завершает movement/Willpower, несколько сохраняют полный pending и staged movement без Willpower. Тот же missing-scene family в sequential/spawn даёт unsupported2/2 для каждого из четырёх кандидатов и early actual8/planned16, без следующего этапа. Всего7новыхtests; production и прежние examples/probes/output не менялись.


## Генерация и поэтапная оценка magic-составов

```sh
PYTHONPATH=src python docs/examples/m8/magic_balance.py
```

[Самостоятельный пример](magic_balance.py) использует только public production APIs. Для копирования нужны два файла: magic_balance.py и magic_scenario.py; пакет towr должен быть установлен. Importable main guard обеспечивает spawn. Старые examples/probes не меняются и не используются новым примером как generator implementation.

Authored Champion-Wizard Level2/Curse и allied Shooting Minion фиксированы. Резерв противоположных Minions E1/E2/E3, groups A=(E2,E1)1..2 и B=(E3)0..1; C4. Явно заданы open arena/shelter/boundary, дистанции, routes, Safe Recover, target priorities/полные GM-approved defeat decisions, departure facts и 128 finite scene keys с архивными placements. Это авторские numeric experiment inputs, не именованные книжные NPC и не общий планировщик scenes.

Seed42, B1, окно [1/4,1/2,3/4], stages=(8,keep2),(32,keep1), upper budget96 на backend. [Stored output](magic_balance.output.txt), CPython3.12.15/macOS arm64: N8 counts по goal/defeated/limit/unsupported —3/0/5/0,0/0/6/2,0/0/6/2,0/0/5/3. Продолжается только counts1,0; финальный N32 даёт9/0/23/0, goal9/32 внутри окна, selected counts1,0. Actual64 на backend (128 на запуск), planned96. Полные пакеты пересчитываются от index0; stages не складываются в одну независимую выборку. Это observation seed/runtime, не preset/гарантия вероятности или ожидаемый победитель assertions.

Пример сравнивает полные sequential/process reports, source identity, budgets, input/global RNG/children до stdout. Затем печатает весь generated catalog и все aggregate rows/counters/stages/continuation/final selection. [Три example tests](../../../tests/integration/test_m8_magic_balance_example.py) проверяют two-file external cwd/stdout parity, поздний generation failure после первого admitted scenario и evaluation failure после8real trials с ID/counts/stage/cause/notes и empty stdout. [Общий аудит](../../audits/m8-generation-readiness.md) содержит fresh installed-package parity и ограничения. M8 JSON/CLI и новые gameplay consumers не входят в пример.

## Конечный JSON/CLI-контракт

[ADR-0043](../../decisions/ADR-0043-magic-json-cli-v1.md) и [полевая матрица с шестью fixtures](json/README.md) готовы. Simulation pure wire реализован; simulation service/error encoder/CLI и balance wire ещё не реализованы. Из корня:

```sh
PYTHONPATH=src python docs/examples/m8/json_contract_probe.py
```

[Probe](json_contract_probe.py) вручную отображает два известных входа в public typed APIs и обратно, сравнивает полные sequential/process results, проверяет13semantic rejects и ошибку projected subset после preflight. [Вывод](json_contract_probe.output.txt) не содержит Monte Carlo/winner assertions. Для внешнего cwd нужны также magic_balance.py, magic_simulation.py, magic_scenario.py и каталог json с шестью fixtures. Это finite mapping evidence, не strict parser/Schema/error validation; следующий срез — simulation service/error encoder/CLI.
