# Magic JSON v1: конечные примеры контракта

[ADR-0043](../../../decisions/ADR-0043-magic-json-cli-v1.md) задаёт будущие `simulate-magic` и `balance-magic`. **Simulation parser/service/result+error encoder/три Schema и команда `simulate-magic` реализованы; balance wire/команда ещё не реализованы.** Здесь зафиксированы шесть документов и ручное отображение двух конкретных входов в существующий public Python API. Это не универсальный JSON importer и не проверка строгой лексики.

| Назначение | Simulation | Balance |
| --- | --- | --- |
| Request | [Вход](magic-simulation-v1.request.json) | [Резерв и этапы](magic-balance-v1.request.json) |
| Result | [Агрегат](magic-simulation-v1.result.json) | [Каталог и полные reports](magic-balance-v1.result.json) |
| Error | [Неверная pair table](magic-simulation-v1.error.json) | [Ошибка проекции subset](magic-balance-v1.error.json) |

Вход simulation: authored Wizard/Minions, seed42, N4, round budget4. Balance: две prefix-count группы, C4, stages2/4 с keep2/1 и полным верхним budget16, round budget1. Reserve и family содержат одинаковый initial frame; future coverage намеренно неполная. Отсутствующая сцена сохраняет `unsupported_path`, не достраивается автоматически. Stored results — наблюдение CPython3.12.15, не вероятность сложности или preset выбора. Simulation error document соответствует production encoder; balance error document пока иллюстрирует формат будущего encoder.

## Матрица отображения

Все перечисленные поля обязательны; `null` и пустые массивы явные. Полная нормативная полевая матрица и будущие guards — в ADR. Поля, не представленные fresh-only форматом, simulation encoder отклоняет при потере информации.

| JSON path | Python / проверяемая граница |
| --- | --- |
| `/request_id` | Отдельный command ID; не заменяет scenario ID или Wizard day ID |
| `/simulation` | `NpcMagicSimulationRequest`: decimal-string seed, trials, scenario round budget |
| `/execution` | Прежние execution options: sequential или process с explicit workers/batch_size |
| `/scenario` или `/reserve/scenario` | `NpcMagicScenario`, канонический fresh roster/round/spatial/Champion daily owner |
| `scenario_id`, `definitions`, `actors` | ID сценария, полные numeric definitions с source IDs, отдельный ordered roster |
| `battlefield`, `placements`, `side_order`, `activation_order` | Полный graph, независимые placements и порядок активаций; стороны explicit |
| `perspective_side`, `objective_target_ids` | Explicit перспектива и ordered все её противники |
| `wizard`, `spell` | Actor/caster/level/profile/day; полная canonical Curse definition |
| `facts`, `actor_policies`, `repeated_stagger_choice` | Все20 facts; Willpower/speed/targets/full GM decisions/attack/casting/Zone policy; suffer_wound |
| `scene_frames[].key` | Полный placement archive и ordered live IDs, включая допустимый пустой live snapshot |
| `pair_ranges`, `zone_ranges` | Explicit диапазоны, orientation и оба directed GM approval flags |
| `give_ground_plans`, `broken_plans`, `attack_departures` | Все routes, flags, nullable destinations и ordered subsets; никаких inferred defaults |
| `/generation` | `MagicCandidateGenerationRequest`: groups, отдельные exact facts/frames, prefix/cap |
| `/evaluation` | Seed, все stages/keep, max_total_trials, exact Fraction window |
| `summary` | Четыре native outcome counts и три totals; means/trial records отсутствуют |
| `/candidates`, `/stage_reports` | Все vectors и исполненные aggregate rows; separate continuation/final selection |
| `rates.round_limit_reached` | Python `round_limit_rate`; все N, включая unsupported, в знаменателе |
| `/error` | Input либо phase-specific code/path/message; у balance внутри error также nullable candidate_id/counts/stage_index |

Порядок definitions хранится отдельно в MagicSimulationCommand; production tests проверяют его перестановку независимо от roster. Ручной inverse в probe использует только порядок definitions этих известных fixtures. Он не реализует общий lossless guard или отказ для всех произвольных неподдержанных источников.

## Запуск probe

Из корня репозитория после установки зависимостей:

```sh
PYTHONPATH=src python docs/examples/m8/json_contract_probe.py
```

Для копирования нужны четыре Python-файла: `json_contract_probe.py`, `magic_balance.py`, `magic_simulation.py`, `magic_scenario.py`, а также этот каталог `json` с шестью fixtures. [Probe](../json_contract_probe.py) запускает реальные public simulation/generation/staged APIs: полное sequential/process равенство, round-trip известных request/scenario/execution, 13 semantic constructor rejects и реальную generation failure `(1,0)` после успешного C4/budget16 preflight. Проверяются неизменность raw/typed inputs, глобального RNG и отсутствие оставшихся children. [Stored stdout](../json_contract_probe.output.txt) проверяется [subprocess test](../../../../tests/integration/test_m8_magic_json_contract_probe.py) из внешнего cwd.

Обычный запуск не перезаписывает fixtures и не использует saved results как oracle. Явный `--write-results` обновляет только оба result JSON текущим runtime; error fixtures остаются иллюстрациями. Simulation production tests проверяют лексические отказы, unknown/required/nullable fields, version dispatch, enum/order mappings и lossless source. Simulation error encoder/service/CLI также проверены. Далее идут balance pure wire, balance execution/CLI и общий аудит.

## Чистый simulation API

```python
from pathlib import Path
from towr.adapters.magic_simulation_json import parse_magic_simulation_request, encode_magic_simulation_result
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation

command = parse_magic_simulation_request(
    Path("docs/examples/m8/json/magic-simulation-v1.request.json").read_bytes())
result = run_npc_magic_simulation(command.request)
print(encode_magic_simulation_result(command, summarize_npc_magic_simulation(result)), end="")
```

Здесь вызывающий код явно выбирает sequential runner. Pure parser/encoder не исполняют `execution` и не запускают RNG/процессы; готовый `execute_magic_simulation(command)` делает dispatch по options и возвращает summary. Вход process уже допускается и сохраняется losslessly. Для ручного process вызова используйте public `run_npc_magic_simulation_parallel` с явными options и importable main guard. Валидация формы доступна через `validate_magic_simulation_document(document, kind)`; числа с float/exponent tokens отклоняет именно strict parser, Schema не заменяет эту проверку.

## Simulation CLI

```sh
PYTHONPATH=src python -m towr simulate-magic docs/examples/m8/json/magic-simulation-v1.request.json
```

Установленный `towr simulate-magic INPUT` принимает relative file или `-`/stdin. Для process задайте `"execution": {"mode": "process", "workers": 2, "batch_size": 3}`. Полный input echo сохраняет independent external request ID/scenario ID/day ID; runtime metadata не гарантирует воспроизводимость между Python versions.

Stdout — один result/error object и newline, stderr — краткая диагностика. Exit0 включает все native outcomes,2 — input/usage,3 — simulation_failed с generic message и path=null,4 — I/O. Read/usage failure оставляет stdout пустым; при output failure нет второго error write. Python cause/notes доступны вызывающему service, но не попадают в JSON. Error encoder отвергает другие families; balance-magic ещё отсутствует. Полный installed audit обоих magic commands будет после balance implementation.
