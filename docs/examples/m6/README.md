# Примеры ближнего боя M6

[ADR-0021](../../decisions/ADR-0021-melee-minion-scenario.md) реализован для неподвижного Melee Minion-сценария. [Аудит](../../audits/m6-readiness.md) сопоставляет контракт, книги, production API и тесты.

## Полный запуск через public API

[melee_scenario.py](melee_scenario.py) самостоятельно собирает typed NpcMeleeScenario и вызывает run_npc_melee_scenario с внедрённым Random(42). Никаких imports tests/private API или собственного боевого цикла.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m6/melee_scenario.py
```

Вход: четыре здоровых Footpad Minions, P1/P2 против E1/E2, общий budget 3. Обе стороны состоят из NPC, название players_and_allies не означает PC-персонажей. Обычный порядок сторон, внутри стороны порядок IDs; каждый выбирает первого живого врага из своей полной policy. Все решения defeat — knocked_out с явным GM approval, обычный outnumbering разрешён каждому actor. При повторном Staggered выбран SUFFER_WOUND. Физически выход в соседнюю Zone доступен (`can_leave_zone=True`), но эта тактика не выбирает Give Ground.

Общая arena не доказывает Close: все вражеские пары отдельно объявлены Close, aware, с LOS на протяжении боя. Полный состав Zone, отсутствие mounts, высоты, дополнительных правил и иных modifiers также заданы явно. Footpad Lurker действует вне боя, поэтому не влияет на этот осведомлённый сценарий. Эти утверждения описывают подготовленный пример; конструктор не доказывает их по имени профиля.

[Сохранённый вывод](melee_scenario.output.txt), CPython 3.14.5: objective_achieved, 6 Attack, 3 visited_rounds, 2 completed_rounds, 3 defeat acknowledgements. Последняя runner observation — pending_follow_ups, но scenario.current после terminal suffix уже без pending. Счётчики посещённых раундов, завершённых runner раундов и вызовов runner имеют разный смысл; итоговый исход берётся из scenario result.

Именно в этом seed все Attack имеют 3 dice: после поражений преимущество не успевает превратиться в атаку большинства. Бонус 3→4 проверяется production cycle tests и probe ниже. Это воспроизводимый пример одного боя, не оценка вероятности или равновесия сторон. Replay требует того же input, правил и совместимого RNG/runtime; seed сам по себе этого не гарантирует. Stdout — поясняющий текст, не JSON/wire contract; CLI/подбор Melee пока отсутствуют. Последовательные массовые прогоны и aggregate summary реализованы отдельно по [ADR-0022](../../decisions/ADR-0022-independent-melee-simulations.md); этот скрипт по-прежнему запускает один бой.

## Низкоуровневая композиция

Первоначальный [contract_probe.py](contract_probe.py) сохранён: он использует только public K1/M2 constructors и executors, без импорта tests, и проверяет композицию компонентов отдельно от production M6 runner.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m6/contract_probe.py
```

Ожидаемый вывод:

```text
Footpad 2x2: attack dice 3 -> 4 after defeat; 2 attacks, 13 RNG calls; 4 rejections OK
```

Источник профиля: BOOK-GM-GUIDE 1.1, Allies and Antagonists / Brigands & Footpads / Footpad, стр. 97: Dagger Close 3d/3, Damage 2, Athletics 3d/3, RES 3. Lurker относится к Awareness вне боя. В примере явно заданы Close всех вражеских пар, осведомлённость, отсутствие высоты/прочих эффектов и решение GM применять обычный бонус численного преимущества (BOOK-PLAYER-GUIDE 1.4, Rules / Attack Tests / Attack Modifiers, стр. 118–119). Физическая возможность Give Ground здесь задана False; её не выводят из выбора Wound или неподвижной тактики.

Две настоящие атаки и два подтверждения GM/exclusion меняют 2:2 на 2:1, затем 2:0. Следующий actor/раунд после последнего поражения не запускается. Проверены неизменность входа, ровно два execution IDs и 13 RNG calls. Отклоняются acknowledgement с чужой Attack, повторное acknowledgement, нулевой и boolean бюджет.

Этот probe не проверяет `NpcMeleeScenarioFacts` (их допуск покрыт unit/integration tests), не является автономным Melee runner, не поддерживает произвольные профили/раскладку и не доказывает факты GM. Матрица реализованного admission/execution находится в ADR и аудите; оба примера сохраняют границы ranged v1.

## Python API массового прогона

Для уже построенного `scenario = build_scenario()` из примера выше:

```python
from towr.simulation.npc_melee_models import NpcMeleeSimulationRequest
from towr.simulation.npc_melee_simulation import run_npc_melee_simulation
from towr.simulation.npc_melee_summary import summarize_npc_melee_simulation

request = NpcMeleeSimulationRequest(scenario, master_seed=42, trials=100)
result = run_npc_melee_simulation(request)
summary = summarize_npc_melee_simulation(result)
print(summary.outcome_counts)
print(summary.mean_attack_count, summary.mean_visited_round_count)
```

Здесь master_seed порождает отдельный seed каждого trial: trial 0 не является одиночным запуском Random(42) выше. `result.trials` хранит compact observations для replay, `summary` — только input/aggregate. По умолчанию каждый trial получает новый Random, для детерминированных fixtures можно передать `rng_factory=`. Это Python API без CLI/JSON или оценки сложности; точная доля исходов малого примера не является гарантией баланса.

## Python API запуска в процессах

В импортируемом скрипте рядом с `melee_scenario.py`:

```python
from melee_scenario import build_scenario
from towr.simulation.npc_melee_models import NpcMeleeSimulationRequest
from towr.simulation.npc_melee_parallel import run_npc_melee_simulation_parallel
from towr.simulation.npc_melee_summary import summarize_npc_melee_simulation

if __name__ == "__main__":
    request = NpcMeleeSimulationRequest(build_scenario(), master_seed=42, trials=100)
    result = run_npc_melee_simulation_parallel(request, workers=2, batch_size=32)
    print(summarize_npc_melee_simulation(result).outcome_counts)
```

Каждый вызов создаёт и закрывает spawn pool; даже workers=1 запускает ребёнка. Custom RNG factory должна быть импортируемой/picklable и создавать свежий RNG по seed. Lambda/локальные closures не подходят. Результат совпадает с sequential при тех же input/RNG/runtime; при ошибке частичный результат не возвращается. [Измерения 100/1000 trials](../../benchmarks/README.md#melee-sequential-и-spawn) показывают расходы spawn на малых пакетах и локальный выигрыш двух workers для 1000 trials 2×2/3×2; автоматического выбора режима нет. Подробности — [ADR-0023](../../decisions/ADR-0023-process-melee-simulations.md).

## Историческая проверка совместимости process backend

Перед реализацией [ADR-0023](../../decisions/ADR-0023-process-melee-simulations.md) был подготовлен отдельный probe совместимости. [process_contract_probe.py](process_contract_probe.py) использует builder из одиночного примера и existing public trial/result/summary через стандартный spawn pool. Нет imports tests/private APIs или переопределения боевых правил.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m6/process_contract_probe.py
```

Ожидаемый вывод:

```text
Melee contract: 3 trials; spawn workers 1/2 == sequential; pickle/source/summary OK; child failure/cleanup OK
```

Явные параметры: Footpad 2×2 из build_scenario, master_seed 20260928, 3 trials, budget 3, workers 1/2. Проверяются request/factory pickle round trip, переставленная подача/сбор records, равенство sequential, parent source identity, child PID, неизменность initial/global RNG, ошибка ребёнка и отсутствие оставшихся детей. Запускать обычным Python без `-O`, чтобы assertions выполнялись.

Probe имеет только фиксированные три задачи и не реализует batching/bounded queue/error notes. Он не является benchmark или новым CLI; production API и матрица его tests описаны в ADR. Игровые источники и facts берутся из прежнего Footpad-примера выше.

## Проверка контракта оценки кандидатов

[ADR-0024](../../decisions/ADR-0024-melee-candidate-assessment.md) подготовлен, pure Melee assessment теперь реализован, evaluator списка пока отсутствует. [assessment_contract_probe.py](assessment_contract_probe.py) использует builder из одиночного примера, существующие typed summary и ObjectiveRateWindow. Это конечный пример на синтетических агрегатах без RNG/исполнения боя и без imports tests/private API.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m6/assessment_contract_probe.py
```

Ожидаемый вывод:

```text
Melee assessment contract: exact shares/windows, unsupported, stable ties, budget 20 OK
```

Проверяются включённые границы/середина окна [1/4,1/2,3/4], отдельные четыре shares, all-round-limit/all-unsupported, stable ties, общий бюджет пяти observations по четыре trials и большое N без float rounding. Наблюдения заданы вручную и не характеризуют баланс Footpad-состава. Probe не реализует source/budget/error guards evaluator; production API и его тесты теперь реализованы по ADR. Запускать без `-O`, чтобы assertions выполнялись.

## Оценка одного Melee-кандидата

Для `result` из массового прогона выше (sequential либо process):

```python
from fractions import Fraction
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.balance.melee_assessment import assess_melee_candidate
from towr.simulation.npc_melee_summary import summarize_npc_melee_simulation

window = ObjectiveRateWindow(Fraction(1, 4), Fraction(1, 2), Fraction(3, 4))
summary = summarize_npc_melee_simulation(result)
assessment = assess_melee_candidate(result.source_request, summary, window)
print(assessment.objective_achieved_rate, assessment.status.value, assessment.window_match)
```

Границы этого примера заданы явно и не являются preset сложности. Имя модуля окна историческое: используется тот же ObjectiveRateWindow, без преобразования Melee в ranged. Четыре rates — Fraction со знаменателем все trials; при unsupported > 0 window_match=None, иначе включённое сравнение minimum/maximum. ELIGIBLE может находиться вне окна, target используется ranking моделей списка. Оценщик не запускает бой и не хранит per-trial records; source summary должен целиком совпасть с переданным input. List models и service исполнения списка реализованы по ADR-0024; CLI для Melee assessment пока отсутствует.

## Вход списка Melee-кандидатов

Для уже допущенных `scenario_a` и `scenario_b` с общей perspective_side и round budget:

```python
from fractions import Fraction
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.balance.melee_evaluation_models import MeleeBalanceCandidate, MeleeBalanceEvaluationRequest

request = MeleeBalanceEvaluationRequest(
    candidates=(MeleeBalanceCandidate("a", scenario_a), MeleeBalanceCandidate("b", scenario_b)),
    master_seed=42,
    trials_per_candidate=100,
    max_total_trials=200,
    window=ObjectiveRateWindow(Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)),
    top_k=1,
)
assert request.planned_trials == 200
assert len(request.simulation_requests) == 2
```

Конструктор проверяет полный вход и бюджет, но не исполняет прогоны. `MeleeBalanceCandidateResult(candidate_id, assessment)` связывает готовый assessment со строкой, `MeleeBalanceEvaluationResult(request, rows)` требует полный исходный порядок, exact IDs/sources/window и хранит только агрегаты с входами. `selected_candidate_ids`, `total_trials`, `seed_scheme` вычисляются; среди rows с window_match=True выбираются ближайшие к target, равенство сохраняет порядок входа. Outside/unsupported остаются в отчёте, пустой выбор допустим. Готовый request передаётся application service ниже.

## Исполнение списка Melee-кандидатов

Для `request` из предыдущего примера; process-вызов помещается в импортируемый Python-файл под main guard:

```python
from towr.application.melee_evaluation_service import evaluate_melee_candidates
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions

if __name__ == "__main__":
    execution = SimulationExecutionOptions(SimulationExecutionMode.PROCESS, workers=2, batch_size=25)
    report = evaluate_melee_candidates(request, execution)
    assert report.source_request is request
    assert report.total_trials == request.planned_trials
    print(report.selected_candidate_ids)
    for row in report.candidates:
        print(row.candidate_id, row.assessment.objective_achieved_rate, row.assessment.window_match)
```

Для sequential передать `SimulationExecutionOptions(SimulationExecutionMode.SEQUENTIAL)` без workers/batch_size. Кандидаты идут по одному; process распараллеливает trials внутри текущего кандидата. Отчёт хранит все aggregate rows в исходном порядке, включая outside/unsupported; selection может быть пустым. При ошибке `MeleeBalanceEvaluationError.candidate_id` указывает кандидата, `__cause__` сохраняет исходную ошибку и worker notes; частичного отчёта, retry или fallback нет. Полные trial records прошлого кандидата освобождаются до следующего запуска. Окно примера — явный вход, не preset сложности.

## Самостоятельный запуск оценки двух составов

[melee_evaluation.py](melee_evaluation.py) строит два допущенных состава Footpad 2×1 и 2×2 через public APIs и соседний builder, без tests/private imports. Все факты Close/awareness/Zone и GM decisions явно заданы для обоих составов. Общие параметры: seed 42, три раунда, по 16 trials, max_total_trials=32, окно [1/4,1/2,3/4], top_k=1.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m6/melee_evaluation.py
```

Запускать без `-O`: assertions проверяют равенство полных отчётов и выбранных IDs, planned/actual budget, сохранение input/global RNG и завершение дочерних процессов. Скрипт выполняет sequential и process (workers=2, batch_size=5), то есть два полных вызова по 32 trials — всего 64. Оба режима используют один typed request; вызовы независимы, повторного использования результатов нет.

[Сохранённый вывод](melee_evaluation.output.txt) получен на Windows/Python 3.14.5: 2×1 вне окна, 2×2 выбран. Это иллюстрация конкретного seed и малого пакета, не preset и не гарантия истинной вероятности. В assertions нет ожидаемого процента или победителя. Ошибка кандидата печатает ID/исходную причину и пробрасывается с ненулевым exit code; частичного отчёта нет. Полная матрица и ограничения — в [аудите](../../audits/m6-evaluation-readiness.md).

## Проверка контракта поэтапной оценки

[staged_contract_probe.py](staged_contract_probe.py) — конечные синтетические примеры [ADR-0025](../../decisions/ADR-0025-staged-melee-evaluation.md) поверх existing Melee bounded models/assessment, без tests/private imports, runner/RNG и нового production API.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m6/staged_contract_probe.py
```

Запускать без `-O`. Проверяются outside-window continuation при пустом bounded selected, исключение unsupported, восстановление исходного порядка, включённые границы/финальный пустой выбор, exact Fraction при большом N и бюджеты 240/140/40/2240. Все counts заданы вручную и не описывают измеренный баланс Footpad. Probe не реализует stage admission, report chain guards или обработку stage errors; теперь они реализованы production API и проверены отдельными model/service/integration tests.

## Готовые модели поэтапного запроса

Для двух уже допущенных кандидатов `request` из раздела входа списка выше:

```python
from towr.balance.melee_staged_evaluation_models import MeleeBalanceStage, MeleeStagedEvaluationRequest

staged = MeleeStagedEvaluationRequest(
    candidates=request.candidates,
    master_seed=request.master_seed,
    stages=(MeleeBalanceStage(10, 2), MeleeBalanceStage(100, 1)),
    max_total_trials=220,
    window=request.window,
)
assert staged.planned_trials == 2 * 10 + 2 * 100 == 220
```

Это preflight без симуляции. Для уже готового `MeleeBalanceEvaluationResult` функция `melee_continuation_candidate_ids` из `balance.melee_staged_evaluation` возвращает промежуточный отбор в исходном порядке, включая пригодные outside-window rows. `MeleeStagedEvaluationResult(staged, stage_reports)` проверяет точную цепочку local sources/budgets/keep и законное завершение, хранит только агрегаты с inputs. Финальный выбор использует только последнее окно, прежние попадания не подставляются. Staged application service реализован и принимает этот request, как показано ниже. Старый staged_contract_probe остаётся историческим арифметическим probe, новые модели покрыты отдельными unit tests.

## Исполнение этапов

Для `staged` из предыдущего раздела; вызов process должен находиться в импортируемом Python-файле под main guard:

```python
from towr.application.melee_staged_evaluation_service import evaluate_melee_candidates_staged
from towr.application.ranged_simulation_models import SimulationExecutionMode, SimulationExecutionOptions

if __name__ == "__main__":
    options = SimulationExecutionOptions(SimulationExecutionMode.PROCESS, workers=2, batch_size=25)
    result = evaluate_melee_candidates_staged(staged, options)
    assert result.source_request is staged
    assert result.total_trials <= result.planned_trials <= staged.max_total_trials
    print(result.status.value, result.selected_candidate_ids, result.total_trials)
    for index, report in enumerate(result.stage_reports):
        print(index, report.total_trials, report.selected_candidate_ids)
```

Для sequential передать `SimulationExecutionOptions(SimulationExecutionMode.SEQUENTIAL)`. Каждый этап выполняет полный пакет с index 0, прежний prefix пересчитывается и входит в бюджет. Промежуточный selected не используется как continuation: outside-window может пройти на уточнение, unsupported исключается. Окончательный выбор берётся только из последнего этапа, либо пуст при ранней остановке NO_ELIGIBLE_CANDIDATES. Все полные stage reports сохраняются.

`MeleeStagedEvaluationError` из `application.melee_staged_evaluation_errors` содержит stage_index с нуля, известный candidate_id (иначе None), а `__cause__` сохраняет цепочку bounded error → исходная причина/worker notes. Ошибка останавливает работу без partial success/retry/fallback. Preflight и финальная ошибка конструктора result проходят напрямую. Самостоятельный пример с полным построением входа и аудит готовы, см. ниже.

## Самостоятельный запуск поэтапной оценки

[melee_staged_evaluation.py](melee_staged_evaluation.py) переиспользует public builders/printer из соседнего примера: явные Footpad 2×1 и 2×2, seed 42, три раунда, окно [1/4,1/2,3/4]. Этапы: 8 trials на кандидата / keep=1, затем 32 / keep=1. Верхний бюджет на вызов — 2×8+1×32=48; финальный пакет исполняется целиком с index 0, первые 8 повторяются.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m6/melee_staged_evaluation.py
```

Запускать без `-O`: assertions сравнивают полные sequential/process reports и selected IDs, сохраняют input/global RNG и проверяют cleanup. Process использует workers=2, batch_size=5. В [сохранённом выводе](melee_staged_evaluation.output.txt) actual=48 на вызов, вместе оба режима исполняют 96 trials. Видны все строки каждого этапа, local selected, отдельные continuation IDs и финальный status/selected. В этом seed/runtime 2×2 проходит с 5/8 и уточняется до 17/32, затем выбирается; assertions не фиксируют эту вероятность или winner. Это наблюдение малого пакета, не preset и не гарантия баланса.

При сбое скрипт печатает stage/candidate/cause и пробрасывает исключение; частичного отчёта нет. Проверенная инъекция ошибки второго этапа сохраняет полную staged → bounded → root cause/notes и не запускает второй backend после сбоя. Границы готовности, матрица и следующий контракт — в [аудите](../../audits/m6-staged-evaluation-readiness.md).

## Контракт генерации из резерва

[generation_contract_probe.py](generation_contract_probe.py) проверяет конечный пример [ADR-0026](../../decisions/ADR-0026-melee-composition-generation.md): два фиксированных Footpad, резерв A=(E2,E1), B=(E3), пять вручную заданных count vectors. Public constructors проверяют согласованные начальные состояния; сохраняются snapshots/graph, исходный порядок бойцов и целей, полные defeat decisions и GM outnumbering flags (включая False у P2). Family facts подтверждены отдельно; невыбранные резервисты отсутствуют в конкретном бою.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m6/generation_contract_probe.py
```

Stages 10/100 с keep 2/1 дают полный planned budget 250. Проверены четыре отказа existing constructors: budget 249, неполные combatants Zone, другая Zone и can_leave_zone без пути. Сам probe не вызывает production preflight: арифметика max_candidates остаётся иллюстрацией. Реализованные [group/request](../../../src/towr/application/melee_candidate_generation_models.py) отдельно покрыты [13 unit tests](../../../tests/unit/test_m6_melee_candidate_generation_models.py). Скрипт не запускает симуляцию/RNG и не оценивает вероятности. Production group/request и construction/result/error реализованы; [14 новых tests](../../../tests/unit/test_m6_melee_candidate_generation.py) проверяют materialization и защиту результата. Этот исторический probe по-прежнему вручную строит конечный пример. [5 integration tests](../../../tests/integration/test_m6_melee_candidate_generation.py) уже проверяют production generator → staged evaluation и динамический outnumbering на generated scenarios. [Самостоятельный production-пример](melee_balance.py) и [аудит ADR-0026](../../audits/m6-generation-readiness.md) завершены; описание запуска ниже. Источники: PG1.4 Rules / The Battlefield / Range, стр. 114; Attack Modifiers, стр. 118–119; GM1.1 Allies and Antagonists / Minions, стр. 91; Understanding NPC Profiles, стр. 93; Brigands & Footpads / Footpad, стр. 97.

## Генерация и поэтапная оценка через production API

[melee_balance.py](melee_balance.py) собирает явный резерв Footpad P1,P2/E1,E2,E3 через public constructors и builder из melee_scenario.py, задаёт отдельные family facts и GM policies, вызывает generate_melee_candidates и передаёт его evaluation_request в existing staged evaluator. Tests/private imports отсутствуют. A=(E2,E1) 0..2, B=(E3) 0..1 дают пять составов; обычный бонус разрешён всем, кроме P2, defeat означает knocked_out. Это явно выбранные решения для всего семейства.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m6/melee_balance.py
```

Скрипт выполняет оба режима и сравнивает полные отчёты: sequential/process (workers=2,batch_size=5), seed 42, три раунда, окно [1/4,1/2,3/4], stages 8/32 keep 2/1. Верхний бюджет на один вызов 5×8+2×32=104, оба режима вместе — 208 trials в проверенном запуске. Каждый этап исполняет полный пакет с index 0. Вывод содержит исходные facts/policies, reserve/groups/IDs/actors/цели, все counts/rates/totals, continuation и final selection; формат текста не является wire API.

[Сохранённый вывод](melee_balance.output.txt): после уточнения обе оценки 26/32=13/16 превышают максимум окна 3/4; COMPLETED с пустым итоговым выбором допустим. Скрипт не требует заранее заданного процента/победителя и не добавляет fallback. Input/global RNG неизменны, дети завершены. При generation/staged error пишет контекст в stderr и пробрасывает исключение с cause/notes, без partial stdout или продолжения другим backend; этот путь проверен инъекцией ошибки. Пример выводит результат в stdout; файл с сохранённым выводом подготовлен отдельно при аудите.

Источники: BOOK-PLAYER-GUIDE 1.4, Rules / Combat, стр. 112; The Battlefield / Range, стр. 114; Attack Modifiers, стр. 118–119; Conditions / Staggered, стр. 123; BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91; Understanding NPC Profiles, стр. 93; Footpad, стр. 97. [Аудит ADR-0026](../../audits/m6-generation-readiness.md) фиксирует границы применимости и стоимости. Melee simulation JSON adapters, service и CLI simulate-melee реализованы; [контракт ADR-0027](../../decisions/ADR-0027-melee-json-cli-v1.md) и [JSON-примеры](json/README.md) подготовлены. Первый implementation-срез (simulation Schema/command и pure adapters) реализован; service/error encoder и simulate-melee также готовы. Далее — balance Schema/models и pure adapters.
