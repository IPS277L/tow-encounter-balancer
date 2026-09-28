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
