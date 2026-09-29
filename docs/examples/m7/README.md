# M7: смешанный ближний и дальний бой

[ADR-0028](../../decisions/ADR-0028-mixed-minion-scenario.md) описывает отдельный неподвижный numeric Minion-сценарий с Melee/Close и Shooting/Medium. Production-вход, исполнитель и результат готовы в этой границе; [аудит](../../audits/m7-readiness.md) завершён.

## Полный сценарий через публичный API

[mixed_scenario.py](mixed_scenario.py) строит полный NpcMixedScenario и вызывает run_npc_mixed_scenario. Он не импортирует tests/private builders или provider старого probe. Профили, пары/дальности, факты и решения ведущего заданы явно. Глобальный RNG не используется движком; каждый запуск получает свой источник бросков.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m7/mixed_scenario.py
```

[Сохранённый вывод](mixed_scenario.output.txt) содержит пять scripted случаев: победа после выстрела и Melee с новым бонусом; два раунда промахов; поражение стороны; потеря последней Close-цели; пропуск первой недоступной цели при выборе следующей. Для них проверяются точные Attack/RNG/round counts и неизменность источников. Дополнительный seeded replay сравнивает полные результаты двух Random(42), без требования конкретного победителя или процента успеха.

В примере сторона players_and_allies также состоит из Minions. Обычный бонус считается по текущей Zone; стрелок в другой Zone его не создаёт. Defeat в terminal suffix снимает pending без фиктивного нового runner call: последняя observation и окончательный outcome сценария могут отличаться. Посещённые раунды включают незавершённый последний, completed — только завершённые наблюдаемые runner раунды.

Потеря всех доступных целей означает unsupported_path, даже если удалённый враг жив и другой союзник мог бы стрелять. Slot остаётся неисполненным; автоматических Wait, движения, смены оружия и Recover нет. Эти примеры не являются оценкой баланса. [Последовательные прогоны и summary](../../decisions/ADR-0029-independent-mixed-simulations.md) реализованы; process, подбор и JSON/CLI для mixed пока отсутствуют.

## Первоначальный probe композиции

[mixed_contract_probe.py](mixed_contract_probe.py) проверяет совместимость existing public K1/M2 APIs на трёх фиксированных примерах. Оба fixture сначала проходят NpcMixedScenario admission. Пример явно задаёт пары/дальности, осведомлённость, видимость, отсутствие применимых дополнительных правил, решения GM и недоступность отхода. Close не вычисляется по общей Zone.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m7/mixed_contract_probe.py
```

Проверки: Medium shot → Close attack с пулами 3/4 и 13 RNG calls; пять промахов с 30 RNG calls и Staggered только у Close-атакующих; после поражения последней Close-цели — NO_CANDIDATE без повторного RNG и исполнения slot. Это детерминированная проверка композиции, не Monte Carlo и не новый wire API.

Источники: BOOK-PLAYER-GUIDE 1.4, Equipment / Ranged Weapons, стр. 94; Rules / Range, стр. 114; Attack Tests / Failed Attacks / Attack Modifiers, стр. 118–119. BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91; Understanding NPC Profiles, стр. 93; Brigands & Footpads, стр. 97. Используются числовые проекции Footpad Dagger и Brigand Warbow; полный Brigand Melee с Craven Opportunist не поддержан.

Probe передаёт два фиксированных fixture production admission, затем исполняет прежнюю композицию K1/M2. Он сохраняется для проверки одного раунда. Полный runner используется новым примером выше. Всего M7 проверяют 60 tests: 25 admission, 8 candidates, 17 result/runner, 9 cycle и [один subprocess test](../../../tests/integration/test_m7_example.py) самостоятельного примера вне repo.

## Контракт независимых прогонов

[ADR-0029](../../decisions/ADR-0029-independent-mixed-simulations.md) задаёт отдельную mixed seed scheme, компактные записи четырёх исходов и сводку без боевых журналов. Production request/result/summary и последовательный simulation API реализованы; ниже сохранён первоначальный probe контракта.

[simulation_contract_probe.py](simulation_contract_probe.py) использует публичный builder одиночного примера и existing mixed runner; локальные Observation служат только проверке будущего контракта.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m7/simulation_contract_probe.py
```

[Вывод](simulation_contract_probe.output.txt): четыре scripted trial одного 2×2 input дают по одному каждому исходу, 17 Attack/6 visited rounds и 24/24/48/6 RNG calls. Это не оценка вероятности: броски заданы вручную. Доля цели 1/4 включает техническую остановку в знаменателе; будущий assessment такой кандидат не выберет из-за unsupported. Ещё 22 seeded вызова проверяют repeat/reverse/expanded prefix и изоляцию дополнительных бросков одного индекса. Проверены три golden vectors, отличие от ranged/Melee seed schemes, неизменность initial/global RNG и проекция terminal suffix. Probe работает из временного каталога с src в PYTHONPATH.

Проверки constructors, ошибок/неполного пакета, source substitution и чистого production summary перечислены в ADR и реализованы в 25 новых tests; этот probe их не заменяет.

## Python API независимых прогонов

Для готового допущенного `scenario: NpcMixedScenario`:

```python
from towr.simulation.npc_mixed_models import NpcMixedSimulationRequest
from towr.simulation.npc_mixed_simulation import run_npc_mixed_simulation
from towr.simulation.npc_mixed_summary import summarize_npc_mixed_simulation

request = NpcMixedSimulationRequest(scenario, master_seed=42, trials=100)
result = run_npc_mixed_simulation(request)
summary = summarize_npc_mixed_simulation(result)
print(summary.outcome_counts)
print(summary.total_attack_count, summary.total_visited_round_count)
```

`result.trials` хранит упорядоченные index/seed/outcome/Attack/visited записи. `summary` содержит только source request, четыре counts и суммы; готовый result и боевые журналы в ней не удерживаются. Каждый trial начинает с исходного immutable scenario, получает новый RNG и полный round budget. Свой источник передаётся через `rng_factory(seed)`; фабрика отвечает за отдельные потоки.

Terminal suffix учитывается в исходе, resume не добавляет раунд, неподдержанный путь сохраняется отдельно. Ошибка фабрики/runner/source прерывает пакет без partial result. Mean properties описывают число Attack и посещённых раундов; неподдержанные trials не исключаются. Sequential API проверен 25 unit/integration tests; [аудит simulation](../../audits/m7-simulation-readiness.md) завершён. Профилирование и эксперимент continuation завершены; контракт следующего process-среза описан ниже.

## Самостоятельный пример simulation/summary

[mixed_simulation.py](mixed_simulation.py) вызывает готовые production APIs и публичный builder одиночного примера, без tests/private imports. Он исполняет два разных состава — 3×2 с одним лучником и 2×2 с двумя лучниками — с master_seed=42, trials=8 и budget=2. Каждый пакет повторяется для проверки полного равенства result/summary; всего 32 trials, но отчёты сохраняют N=8 каждый.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m7/mixed_simulation.py
```

[Сохранённый вывод](mixed_simulation.output.txt) содержит явные facts/placements/pair ranges/GM policies, четыре counts, Attack/visited totals, средние и компактные index/seed/outcome records. Источники и global RNG неизменны. Доля цели использует все trials; в observed 2×2 пакете семь технических остановок остаются unsupported, а не поражениями. Наблюдения этой маленькой выборки не являются оценкой баланса, отсутствия unsupported в другой выборке недостаточно для доказательства полной тактики.

[Subprocess test](../../../tests/integration/test_m7_simulation_example.py) запускает пример дважды из временного каталога и сравнивает stdout, не закрепляя конкретный случайный процент. Вместе с ним последовательный simulation-слой покрыт 26 tests. Mixed process API реализован ниже; mixed balance/CLI остаются дальнейшими расширениями.

## Контракт process backend: конечный probe

[ADR-0030](../../decisions/ADR-0030-process-mixed-simulations.md) определяет отдельный `run_npc_mixed_simulation_parallel`, теперь реализованный в production; этот раздел сохраняет исторический probe контрактного шага. [process_contract_probe.py](process_contract_probe.py) проверяет сериализацию существующего mixed request/trial/result через настоящий ProcessPoolExecutor со spawn и конечными заранее заданными partitions. Он использует public builder соседнего примера, без tests/private imports.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m7/process_contract_probe.py
```

[Вывод](process_contract_probe.output.txt): 3×2/2×2, 5 trials, seed=42, budget=2, workers 1/2 и partitions 3+2/2+2+1/5; полные result/summary равны sequential при обратном порядке получения. Отдельные четыре scripted trials на одном 2×2 input дают все четыре outcome, 17 Attack/6 visited, включая настоящий NO_CANDIDATE. Проверены parent source identity, child PID, pickle, отдельные RNG/input/cleanup и ошибка фабрики с index/seed note. 49 завершённых trials и один отказ factory на запуск; статистического oracle и обещания ускорения нет.

Probe **не** является новым simulation backend: он не проверяет будущие public preflight/options, lazy refill, общую bound очереди, cancellation/submission/wait failures. Они покрываются tests готового backend ниже; результаты probe сами по себе их не доказывают. Движение, смена оружия, auto approvals, balance и JSON/CLI не добавлены.

## Готовый Python API: optional process

[run_npc_mixed_simulation_parallel](../../../src/towr/simulation/npc_mixed_parallel.py) возвращает тот же NpcMixedSimulationResult, что и sequential. `workers` задаётся явно; `batch_size=32` — default, не рекомендация о скорости. Пример для скрипта рядом с mixed_scenario.py; запускать с PYTHONPATH=src:

```python
from mixed_scenario import build_scenario
from towr.simulation.npc_mixed_models import NpcMixedSimulationRequest
from towr.simulation.npc_mixed_simulation import run_npc_mixed_simulation
from towr.simulation.npc_mixed_parallel import run_npc_mixed_simulation_parallel
from towr.simulation.npc_mixed_summary import summarize_npc_mixed_simulation


def main():
    request = NpcMixedSimulationRequest(build_scenario(two_archers=True), 42, 8)
    result = run_npc_mixed_simulation_parallel(request, workers=2, batch_size=3)
    assert result == run_npc_mixed_simulation(request)
    print(summarize_npc_mixed_simulation(result).outcome_counts)


if __name__ == "__main__":
    main()
```

Импортируемый main и guard обязательны для spawn; stdin/REPL не обещаны. Custom `rng_factory` должна быть top-level/picklable и создавать независимый RNG только по seed. Все четыре outcomes сохраняются, unsupported не отбрасывается. Pool закрывается на каждый вызов, при ошибке ожидает уже начатую работу; partial result/retry/fallback отсутствуют. Bounded очередь не ограничивает суммарное хранение всех compact records. [11 unit tests](../../../tests/unit/test_m7_npc_mixed_parallel.py) и [6 real-spawn tests](../../../tests/integration/test_m7_npc_mixed_parallel.py) проверяют API. [Сравнение sequential/process](../../benchmarks/README.md#mixed-sequential-и-spawn) выполнено на 100/1000 trials; локальные результаты не обещают универсального ускорения. Автоматического backend нет. [Общий аудит массовой mixed-симуляции](../../audits/m7-mass-simulation-readiness.md) завершён; [контракт оценки mixed-кандидатов ADR-0031](../../decisions/ADR-0031-mixed-candidate-assessment.md) подготовлен. Pure mixed assessment, list models и application evaluator реализованы; следующий шаг — аудит bounded mixed evaluation.

## Контракт оценки mixed-кандидатов

[ADR-0031](../../decisions/ADR-0031-mixed-candidate-assessment.md), [assessment_contract_probe.py](assessment_contract_probe.py) и [сохранённый вывод](assessment_contract_probe.output.txt). Запуск из корня:

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m7/assessment_contract_probe.py
```

Probe использует только existing public constructors/APIs и builder mixed_scenario.py. Синтетическая часть проверяет Fraction/inclusive windows, stable ties, арифметику бюджета, all-limit/all-unsupported и большой N без float rounding; это не simulation observations и не будущие production guards. Реальная часть исполняет один scripted 2×2 input в sequential и production spawn: по четыре trials, одинаковые results/summaries, counts=1/1/1/1, 17 Attack/6 visited. Goal=1/4 внутри окна, но unsupported=1/4 делает будущую оценку непригодной. Parent source/global RNG/cleanup проверены; всего восемь реальных trials на запуск. Пример работает и из отдельного cwd при абсолютном PYTHONPATH к src. Пример не реализует assessment/list/evaluator API. Pure assessment, list models и application evaluator реализованы отдельно и проверены своими tests; исторический probe не подменяет их проверки.

## Python API оценки одного mixed-кандидата

[Реализованный первый срез ADR-0031](../../decisions/ADR-0031-mixed-candidate-assessment.md#реализация-pure-assessment) принимает input, готовую aggregate summary и явное окно. Пример с builder из этой папки:

```python
from fractions import Fraction
from mixed_scenario import build_scenario
from towr.balance.mixed_assessment import assess_mixed_candidate
from towr.balance.mixed_assessment_models import ObjectiveRateWindow
from towr.simulation.npc_mixed_models import NpcMixedSimulationRequest
from towr.simulation.npc_mixed_simulation import run_npc_mixed_simulation
from towr.simulation.npc_mixed_summary import summarize_npc_mixed_simulation

request = NpcMixedSimulationRequest(build_scenario(), master_seed=42, trials=4)
summary = summarize_npc_mixed_simulation(run_npc_mixed_simulation(request))
assessment = assess_mixed_candidate(
    request, summary, ObjectiveRateWindow(Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)),
)
print(assessment.status.value, assessment.objective_achieved_rate, assessment.window_match)
```

Сам assessment не запускает симуляцию: её вызов выше нужен только для получения summary. Все четыре доли сохраняют denominator=N; любое unsupported даёт window_match=None. ELIGIBLE с False означает пригодные наблюдения вне окна. Равная копия полного input допустима, чужие facts/seed/budget и ranged/Melee summary отклоняются. Окно/метрика не утверждают истинную вероятность или полноту тактики. [9 unit](../../../tests/unit/test_m7_mixed_assessment.py) и [1 real sequential/spawn integration test](../../../tests/integration/test_m7_mixed_assessment.py) проверяют готовые API. Модели списка и application execution реализованы следующими срезами ниже; JSON/CLI ещё не добавлены.

## Python API моделей списка mixed-кандидатов

[Модели ADR-0031](../../../src/towr/balance/mixed_evaluation_models.py) проверяют вход без запуска симуляции. Builder берётся из этой папки:

```python
from fractions import Fraction
from mixed_scenario import build_scenario
from towr.balance.mixed_evaluation_models import (
    MixedBalanceCandidate, MixedBalanceEvaluationRequest, ObjectiveRateWindow,
)

request = MixedBalanceEvaluationRequest(
    candidates=(
        MixedBalanceCandidate("one-bow", build_scenario()),
        MixedBalanceCandidate("two-bows", build_scenario(two_archers=True)),
    ),
    master_seed=42, trials_per_candidate=8, max_total_trials=16,
    window=ObjectiveRateWindow(Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)), top_k=1,
)
print(request.planned_trials, tuple(item.trials for item in request.simulation_requests))
```

Оба сценария сохраняют свой полный исходный input; общий budget=16 проверен, но эти прогоны ещё не исполнены. MixedBalanceCandidateResult связывает ID с готовым assessment; MixedBalanceEvaluationResult требует все rows в исходном порядке с matching source/window, сохраняет outside/unsupported и выбирает только window_match=True по точному расстоянию до target. При равенстве сохраняется порядок входа; если подходящих нет, выбор пуст. [11 tests](../../../tests/unit/test_m7_mixed_evaluation.py) проверяют модели и синтетическое ranking без RNG/runner. Application evaluator реализован следующим срезом ниже.

## Python API исполнения mixed-списка

[Сервис](../../../src/towr/application/mixed_evaluation_service.py) принимает готовый request и явные existing execution options. Полный пример с builder из этой папки:

```python
from fractions import Fraction
from mixed_scenario import build_scenario
from towr.application.mixed_evaluation_service import evaluate_mixed_candidates
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions
from towr.balance.mixed_evaluation_models import (
    MixedBalanceCandidate, MixedBalanceEvaluationRequest, ObjectiveRateWindow,
)


def main():
    request = MixedBalanceEvaluationRequest(
        candidates=(
            MixedBalanceCandidate("one-bow", build_scenario()),
            MixedBalanceCandidate("two-bows", build_scenario(two_archers=True)),
        ),
        master_seed=42, trials_per_candidate=8, max_total_trials=16,
        window=ObjectiveRateWindow(Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)), top_k=1,
    )
    sequential = evaluate_mixed_candidates(request, SimulationExecutionOptions(Mode.SEQUENTIAL))
    process = evaluate_mixed_candidates(request, SimulationExecutionOptions(Mode.PROCESS, workers=2, batch_size=3))
    assert sequential == process
    print(process.total_trials, process.selected_candidate_ids)


if __name__ == "__main__":
    main()
```

Для spawn необходим импортируемый script и main guard, не stdin/REPL. Один вызов исполняет 16 trials, оба режима в примере — 32; report хранит входы и aggregate assessments. Любой unsupported не выбирается, даже при goal rate внутри окна; пустой selection — допустимый полный результат. Ошибка кандидата даёт MixedBalanceEvaluationError с candidate_id и __cause__ (включая исходные worker notes), без частичного отчёта; preflight/final constructor и interrupts распространяются напрямую. [8 unit](../../../tests/unit/test_m7_mixed_evaluation_service.py) и [3 integration tests](../../../tests/integration/test_m7_mixed_evaluation.py) проверяют сервис. [Общий аудит](../../audits/m7-evaluation-readiness.md) завершён; generation/staged/JSON/CLI сюда не входят.

## Самостоятельная оценка mixed-списка

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m7/mixed_evaluation.py
```

[Скрипт](mixed_evaluation.py) и [сохранённый вывод](mixed_evaluation.output.txt): два явно заданных состава 3×2/2×2, один/два лучника, seed 42, два раунда, по 8 trials, окно [1/4,1/2,3/4], top_k=1. Planned/actual=16 на вызов; sequential и process workers=2/batch_size=3 исполняют 32 trials суммарно. Проверяются полные reports, source identity, input/global RNG и завершение процессов. Наблюдавшиеся counts/selected не являются статистической гарантией и не зашиты в assertions.

Вывод появляется после обоих успешных вызовов. Ошибка кандидата сообщает ID/cause в stderr и пробрасывается с исходными notes; частичного stdout нет. Проверена ошибка второго кандидата после успешных 8 trials первого. Пример работает из корня и отдельного cwd с абсолютным PYTHONPATH к src, без tests/private imports. [Контракт ADR-0032](../../decisions/ADR-0032-staged-mixed-evaluation.md) подготовлен; pure helper/models и application service/error реализованы; аудит staged evaluation завершён, следующий шаг — контракт генерации mixed-составов.

## Контракт поэтапной оценки mixed-списка

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m7/staged_contract_probe.py
```

[ADR-0032](../../decisions/ADR-0032-staged-mixed-evaluation.md), [probe](staged_contract_probe.py) и [сохранённый вывод](staged_contract_probe.output.txt). Это конечная проверка арифметики на существующих mixed bounded reports, без staged production API, исполнения боя или RNG. Используются два явно заданных вида сценария 3×2/2×2; counts синтетические и не доказывают достижимость исходов боем.

Окно [9/20,1/2,11/20], порядок A,B,C,D: вне окна A=4/10 и D=6/10 продолжают уточнение, C=5/10 с unsupported исключается. Следующий input сохраняет (A,D), даже если D ближе. Проверены exact Fraction/ties/границы, финальный пустой выбор, all-round-limit/all-unsupported и бюджеты полных повторных пакетов 240/140/40/2240. Seeds прежнего prefix совпадают, но service вычисляет пакет заново. Probe не вызывает production staged models и не проверяет chain/error guards. Pure helper и frozen stage/request/result/status теперь реализованы и проверены отдельными tests; application service/error также реализованы; отдельный staged аудит завершён; следующий срез — контракт генерации.

## Python API моделей поэтапной оценки

[Модели](../../../src/towr/balance/mixed_staged_evaluation_models.py) задают stages/input/aggregate result; [helper](../../../src/towr/balance/mixed_staged_evaluation.py) выбирает продолжение из готового bounded report. Пример с builder из этой папки:

```python
from fractions import Fraction
from mixed_scenario import build_scenario
from towr.balance.mixed_evaluation_models import MixedBalanceCandidate
from towr.balance.mixed_staged_evaluation_models import (
    MixedBalanceStage, MixedStagedEvaluationRequest,
)
from towr.balance.ranged_assessment_models import ObjectiveRateWindow

request = MixedStagedEvaluationRequest(
    candidates=(
        MixedBalanceCandidate("one-bow", build_scenario()),
        MixedBalanceCandidate("two-bows", build_scenario(two_archers=True)),
    ),
    master_seed=42, stages=(MixedBalanceStage(8, 1), MixedBalanceStage(32, 1)),
    max_total_trials=48,
    window=ObjectiveRateWindow(Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)),
)
assert request.planned_trials == 2 * 8 + 1 * 32 == 48
```

Конструирование не исполняет trials. `mixed_continuation_candidate_ids(report)` оставляет до top_k ближайших пригодных кандидатов, в том числе outside-window, и возвращает исходный порядок. Итоговый выбор использует только window matches последнего этапа. MixedStagedEvaluationResult проверяет всю source-bound цепочку; любой unsupported исключает продолжение, а законченный последний этап с пустым выбором остаётся COMPLETED. [19 tests](../../../tests/unit/test_m7_mixed_staged_evaluation.py) проверяют модели/helper. Application staged runner теперь реализован, пример вызова приведён ниже.

## Python API исполнения этапов

[Service](../../../src/towr/application/mixed_staged_evaluation_service.py) принимает staged request и явные execution options. Пример с готовым builder списка из этой папки:

```python
from mixed_evaluation import build_request
from towr.application.mixed_staged_evaluation_service import evaluate_mixed_candidates_staged
from towr.application.ranged_simulation_models import SimulationExecutionMode as Mode, SimulationExecutionOptions
from towr.balance.mixed_staged_evaluation_models import MixedBalanceStage, MixedStagedEvaluationRequest


def main():
    base = build_request()
    request = MixedStagedEvaluationRequest(
        candidates=base.candidates, master_seed=base.master_seed,
        stages=(MixedBalanceStage(8, 1), MixedBalanceStage(32, 1)),
        max_total_trials=48, window=base.window,
    )
    sequential = evaluate_mixed_candidates_staged(request, SimulationExecutionOptions(Mode.SEQUENTIAL))
    process = evaluate_mixed_candidates_staged(request, SimulationExecutionOptions(Mode.PROCESS, 2, 3))
    assert sequential == process
    assert sequential.source_request is request and process.source_request is request
    assert sequential.total_trials <= request.planned_trials == 48
    print(process.planned_trials, process.total_trials, process.status.value, process.selected_candidate_ids)


if __name__ == "__main__":
    main()
```

Для spawn нужен импортируемый script с main guard, не stdin/REPL. Каждый stage исполняет полный пакет с index 0; planned=2×8+1×32=48 на один вызов, оба backend оплачиваются отдельно. Reports сохраняют все агрегаты исполненных stages; unsupported исключает continuation/выбор. Ошибка даёт MixedStagedEvaluationError с zero-based stage_index, известным candidate_id или None и цепочкой __cause__ до исходных notes. Нет partial result/retry/fallback; preflight/final constructor и interrupts проходят напрямую. [9 unit](../../../tests/unit/test_m7_mixed_staged_evaluation_service.py) и [3 integration tests](../../../tests/integration/test_m7_mixed_staged_evaluation.py) проверяют реализацию; [самостоятельный пример](mixed_staged_evaluation.py) с [выводом](mixed_staged_evaluation.output.txt) и [аудит](../../audits/m7-staged-evaluation-readiness.md) теперь завершены.

## Самостоятельная поэтапная mixed-оценка

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m7/mixed_staged_evaluation.py
```

[Скрипт](mixed_staged_evaluation.py) и [сохранённый вывод](mixed_staged_evaluation.output.txt) используют прежние явные составы 3×2/2×2 с одним/двумя лучниками, seed 42, два раунда и окно [1/4,1/2,3/4]. Stages=(8,keep=1),(32,keep=1), planned=2×8+1×32=48 на вызов. Sequential и process workers=2/batch_size=3 дают одинаковые полные reports; observed actual=48 на каждый backend, всего 96 trials на запуск скрипта. Проверяются input/global RNG, parent identity и отсутствие оставшихся детей. Повторный prefix оплачивается; оценки stages не складываются как независимые observations.

В сохранённом выводе 3×2 проходит первый этап, но на втором получает unsupported и исключается из итогового выбора, даже при доле цели внутри окна. Раннее попадание не возвращается. Конкретные counts/победитель в assertions не закреплены. Печать начинается только после двух успешных вызовов и проверок; ошибка сохраняет stage/candidate/cause/notes, идёт в stderr и пробрасывается без partial stdout. Проверена инъекция ошибки второго этапа после 16 реальных trials первого. [Аудит](../../audits/m7-staged-evaluation-readiness.md) фиксирует ограничения и следующий контракт генерации.

## Контракт генерации mixed-составов

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m7/generation_contract_probe.py
```

[ADR-0033](../../decisions/ADR-0033-mixed-composition-generation.md), [probe](generation_contract_probe.py) и [вывод](generation_contract_probe.output.txt) задают конечный резерв: Pbow/P1/P2 фиксированы, A=(E2,E1) Footpad Dagger 1..2, B=(E3) Brigand Warbow 0..1. Четыре вручную заданных вектора сохраняют independent orders, snapshots, explicit Close/Medium pairs, весь graph и полные GM decisions/флаги; stages 10/100 keep 2/1 требуют 240 trials, но не исполняются.

При A.minimum=0 C=5/budget=250 включает недопустимый (0,1): P1/P2 теряют Close-цель. Отдельно показана потеря единственной Shooting-роли при противоположной perspective. Existing constructors отклоняют оба примера, missing pair, несогласованные facts и budget=239. Семейство нельзя молча сократить до четырёх допустимых кандидатов. Это проверка public constructors, не production generation/preflight/error API и не Monte Carlo-измерение. Typed group/request preflight теперь реализован; probe остаётся конечным примером public constructors. Runner/RNG/pool в нём не исполняются.

## Production preflight генерации

[MixedCompositionGroup/MixedCandidateGenerationRequest](../../../src/towr/application/mixed_candidate_generation_models.py) реализуют первый срез ADR-0033. Caller передаёт admitted mixed reserve, ordered groups, отдельные facts/pair_ranges, prefix, caps, seed, stages и окно. Family pairs должны точно совпадать с ordered template pairs; group/request принимают tuple/list и сохраняют tuple snapshots. C/planned_trials вычисляются без materialization и исполнения; при недопустимых bounds/partition/типах/парах/бюджете constructor отклоняет вход. [15 tests](../../../tests/unit/test_m7_mixed_candidate_generation_models.py) проверяют публичный контракт, включая C=2**40−1 и сохранение source/GM policies.

Этот request не строит кандидатов и не доказывает допустимость каждого subset. При bounds с потерей единственного Close-врага он учитывает соответствующий vector в C/budget; construction теперь явно отклоняет такой состав. Integration с existing staged evaluation теперь проверена (см. ниже); следующий срез — standalone production-пример и аудит.

## Production генерация составов

[generate_mixed_candidates](../../../src/towr/application/mixed_candidate_generation.py) принимает MixedCandidateGenerationRequest и возвращает immutable MixedCandidateGenerationResult с source_request/evaluation_request. Для каждого prefix-count vector строится полный initial scenario с детерминированным ID; ordered pair ranges, full snapshots/GM decisions/flags и весь graph сохраняются. Result сверяет полный ordered staged input с исходным резервом. Генерация не вызывает симуляцию или оценку; передача evaluation_request в existing staged service остаётся отдельным явным действием.

[MixedCandidateGenerationError](../../../src/towr/application/mixed_candidate_generation_errors.py) сообщает candidate_id/counts; исходная ошибка и notes доступны через __cause__. Недопустимый subset (потеря Melee/Shooting-роли или начальной цели) прерывает весь вызов, даже если предыдущие составы допущены; partial результата нет. Interrupts и финальные staged/result constructor errors не оборачиваются вымышленным candidate context. [17 tests](../../../tests/unit/test_m7_mixed_candidate_generation.py) дополняют 15 preflight tests. Самостоятельный production-пример со staged execution и его аудит ещё впереди; конечный generation_contract_probe остаётся проверкой constructor contract.

## Проверка генератора с поэтапной оценкой

[6 integration tests](../../../tests/integration/test_m7_mixed_candidate_generation.py) используют production generator/staged APIs. Четыре состава и stages=(2,keep=2),(4,keep=1) дают planned budget 16; real sequential/process reports совпадают, повтор и rename prefix сохраняют observations/selection после нормализации source IDs. Точные natural Monte Carlo проценты/победитель не закреплены. Отдельный importable RNG с промахами подтверждает полный actual=planned=16 на каждый backend и оплату повторного пакета без prefix reuse.

Scripted public runner проверяет шесть generated вариантов с локальными 2:1/2:2/2:3 и удалёнными стрелками: точные trace/pools/RNG calls, True/False GM approvals, появление бонуса после поражения врага и исчезновение после поражения союзника. Полные решения disarmed_and_surrendered сохранены. Source/global RNG/cleanup проверены; production код не менялся. Самостоятельный public пример и аудит ADR-0033 теперь завершены (см. ниже).

## Самостоятельный подбор mixed-составов

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m7/mixed_balance.py
```

[Скрипт](mixed_balance.py), [сохранённый вывод](mixed_balance.output.txt) и [аудит](../../audits/m7-generation-readiness.md) закрывают typed generator ADR-0033 в его границе. Явный резерв: Pbow/P1/P2 фиксированы, A=(E2,E1) Footpad Dagger 1..2, B=(E3) Brigand Warbow 0..1. Fixed placements и Close/Medium pairs, отдельные family facts, полные GM decisions/flags. Script строит четыре состава через production generator и сравнивает полные sequential/process reports; seed 42, два раунда, stages 8/32 keep 2/1, окно [1/4,1/2,3/4], planned=96 на вызов. Все actors — numeric Minions; код не импортирует tests/private helpers.

В сохранённом выводе actual=96 на backend (192 trials за запуск). На первом этапе варианты с E3 исключены из-за unsupported; два состава вне окна продолжаются для уточнения. На втором 1,0 имеет 15/16 целей вне окна, а 2,0 — 3/4 целей и unsupported; итог COMPLETED с пустым выбором. Это наблюдение seed/runtime, не preset/гарантия вероятности. Assertions проверяют равенство отчётов, inputs/global RNG/cleanup, не конкретный процент/победителя. Каждый этап повторяет полный пакет с index 0.

Два cwd дают одинаковый stdout и пустой stderr. Реальный generation failure и инъекция ошибки второго этапа после 32 trials сохраняют candidate/counts либо stage/candidate/cause/notes, дают пустой stdout и останавливают дальнейшее исполнение. Текстовый вывод — учебный отчёт, не wire format. Следующее направление выбрано: контракт JSON/CLI для mixed simulation/balance без новых боевых правил.


## Контракт JSON/CLI для mixed

[ADR-0034](../../decisions/ADR-0034-mixed-json-cli-v1.md), [JSON fixtures и матрица ошибок](json/README.md), [конечный mapping probe](json_contract_probe.py) подготовлены. Примеры отображаются в existing public typed APIs; simulation и staged balance полностью совпали между sequential/process. Контракт сохраняет explicit Skill/Range/Hands, enemy pairs, actor-scoped flags и отдельные family assertions. Production simulation Schema/command/pure parser/summary encoder реализованы и проверены 31 tests. Simulation service/application error/error encoder и simulate-mixed теперь реализованы; [запуск из JSON](json/README.md#запуск-simulation-cli) проверен в обоих backend. Balance Schema/models/pure adapters теперь реализованы (38 tests); [пример Python API](json/README.md#balance-json-через-python-api) соединяет их с existing generator/evaluator. Balance service/errors/error encoder и balance-mixed реализованы. [Общий аудит mixed JSON/CLI](../../audits/m7-external-readiness.md) завершён; ADR-0034 закрыт в текущей границе numeric Minions.
