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

Проверяются включённые границы/середина окна [1/4,1/2,3/4], отдельные четыре shares, all-round-limit/all-unsupported, stable ties, общий бюджет пяти observations по четыре trials и большое N без float rounding. Наблюдения заданы вручную и не характеризуют баланс Footpad-состава. Probe не реализует source/budget/error guards будущего evaluator; матрица его будущих тестов в ADR. Запускать без `-O`, чтобы assertions выполнялись.

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

Границы этого примера заданы явно и не являются preset сложности. Имя модуля окна историческое: используется тот же ObjectiveRateWindow, без преобразования Melee в ranged. Четыре rates — Fraction со знаменателем все trials; при unsupported > 0 window_match=None, иначе включённое сравнение minimum/maximum. ELIGIBLE может находиться вне окна, target используется ranking моделей списка. Оценщик не запускает бой и не хранит per-trial records; source summary должен целиком совпасть с переданным input. List models реализованы по ADR-0024; service исполнения списка и CLI для Melee assessment ещё не реализованы.

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

Конструктор проверяет полный вход и бюджет, но не исполняет прогоны. `MeleeBalanceCandidateResult(candidate_id, assessment)` связывает готовый assessment со строкой, `MeleeBalanceEvaluationResult(request, rows)` требует полный исходный порядок, exact IDs/sources/window и хранит только агрегаты с входами. `selected_candidate_ids`, `total_trials`, `seed_scheme` вычисляются; среди rows с window_match=True выбираются ближайшие к target, равенство сохраняет порядок входа. Outside/unsupported остаются в отчёте, пустой выбор допустим. Сервис, который получит эти строки из симулятора, — следующий шаг; этот пример не подменяет его собственным боевым циклом.
