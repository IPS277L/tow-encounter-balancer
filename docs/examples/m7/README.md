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

Импортируемый main и guard обязательны для spawn; stdin/REPL не обещаны. Custom `rng_factory` должна быть top-level/picklable и создавать независимый RNG только по seed. Все четыре outcomes сохраняются, unsupported не отбрасывается. Pool закрывается на каждый вызов, при ошибке ожидает уже начатую работу; partial result/retry/fallback отсутствуют. Bounded очередь не ограничивает суммарное хранение всех compact records. [11 unit tests](../../../tests/unit/test_m7_npc_mixed_parallel.py) и [6 real-spawn tests](../../../tests/integration/test_m7_npc_mixed_parallel.py) проверяют API. [Сравнение sequential/process](../../benchmarks/README.md#mixed-sequential-и-spawn) выполнено на 100/1000 trials; локальные результаты не обещают универсального ускорения. Автоматического backend нет. [Общий аудит массовой mixed-симуляции](../../audits/m7-mass-simulation-readiness.md) завершён; [контракт оценки mixed-кандидатов ADR-0031](../../decisions/ADR-0031-mixed-candidate-assessment.md) подготовлен. Pure mixed assessment реализован; list models/evaluator ещё впереди.

## Контракт оценки mixed-кандидатов

[ADR-0031](../../decisions/ADR-0031-mixed-candidate-assessment.md), [assessment_contract_probe.py](assessment_contract_probe.py) и [сохранённый вывод](assessment_contract_probe.output.txt). Запуск из корня:

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m7/assessment_contract_probe.py
```

Probe использует только existing public constructors/APIs и builder mixed_scenario.py. Синтетическая часть проверяет Fraction/inclusive windows, stable ties, арифметику бюджета, all-limit/all-unsupported и большой N без float rounding; это не simulation observations и не будущие production guards. Реальная часть исполняет один scripted 2×2 input в sequential и production spawn: по четыре trials, одинаковые results/summaries, counts=1/1/1/1, 17 Attack/6 visited. Goal=1/4 внутри окна, но unsupported=1/4 делает будущую оценку непригодной. Parent source/global RNG/cleanup проверены; всего восемь реальных trials на запуск. Пример работает и из отдельного cwd при абсолютном PYTHONPATH к src. Пример не реализует assessment/list/evaluator API. Pure assessment уже реализован отдельно и проверен своими tests; list models/evaluator — следующие срезы.

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

Сам assessment не запускает симуляцию: её вызов выше нужен только для получения summary. Все четыре доли сохраняют denominator=N; любое unsupported даёт window_match=None. ELIGIBLE с False означает пригодные наблюдения вне окна. Равная копия полного input допустима, чужие facts/seed/budget и ranged/Melee summary отклоняются. Окно/метрика не утверждают истинную вероятность или полноту тактики. [9 unit](../../../tests/unit/test_m7_mixed_assessment.py) и [1 real sequential/spawn integration test](../../../tests/integration/test_m7_mixed_assessment.py) проверяют готовые API. Следующий шаг — модели списка, пока без application execution/JSON/CLI.
