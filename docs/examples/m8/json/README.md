# Magic JSON: v1 fixtures и simulation v2

## Simulation v2 — ADR-0047

[Вход v2](magic-simulation-v2.request.json) явно включает полную Miscast/Prone policy в прежний authored сценарий. `scenario.miscast_continuation` обязателен: `null` сохраняет legacy gameplay, полный object включает ограниченный runner ADR-0046. V1 это поле запрещает даже с `null`. Наличие policy не выбирает версию автоматически.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m towr simulate-magic docs/examples/m8/json/magic-simulation-v2.request.json
```

Для process изменить только `execution` на `{"mode":"process","workers":2,"batch_size":1}`. Request echo/result/error после complete strict decode сохраняют `schema_version='2'`; malformed JSON/UTF-8, duplicate keys, lone surrogates, nonfinite/float/exponent tokens возвращают fallback error v1 и null request ID. Runtime failure имеет версию admitted command. Public validators требуют явного `schema_version='2'`; default остаётся v1. [Полный контракт](../../../decisions/ADR-0047-opt-in-generation-and-magic-json-v2.md), [аудит/tests](../../../audits/m8-simulation-v2-readiness.md).

Этот пример — finite standard-RNG observation, не probability preset; incomplete future frames/прочие Miscast effects остаются unsupported и входят в trials. [Integration test](../../../../tests/integration/test_m8_magic_json_v2.py) проверяет файл и sequential/process CLI. Balance v2 ещё не поддержан. Installed audit обоих v2 families и stored result fixtures предусмотрены общим этапом4; прежние v1 результаты ниже не заменяют новую проверку.

## V1 fixtures и первоначальный контракт

[ADR-0043](../../../decisions/ADR-0043-magic-json-cli-v1.md) задаёт реализованные `simulate-magic` и `balance-magic`. **Оба семейства parser/service/result+error encoder, шесть Schema и CLI проверены [общим аудитом](../../../audits/m8-external-readiness.md).** Здесь зафиксированы шесть документов и ручное отображение двух конкретных входов в существующий public Python API. Это не универсальный JSON importer и не проверка строгой лексики.

| Назначение | Simulation | Balance |
| --- | --- | --- |
| Request | [Вход](magic-simulation-v1.request.json) | [Резерв и этапы](magic-balance-v1.request.json) |
| Result | [Агрегат](magic-simulation-v1.result.json) | [Каталог и полные reports](magic-balance-v1.result.json) |
| Error | [Неверная pair table](magic-simulation-v1.error.json) | [Ошибка проекции subset](magic-balance-v1.error.json) |

Вход simulation: authored Wizard/Minions, seed42, N4, round budget4. Balance: две prefix-count группы, C4, stages2/4 с keep2/1 и полным верхним budget16, round budget1. Reserve и family содержат одинаковый initial frame; future coverage намеренно неполная. Отсутствующая сцена сохраняет `unsupported_path`, не достраивается автоматически. Stored results — наблюдение CPython3.12.15, не вероятность сложности или preset выбора. Error documents иллюстрируют форму; фактические runtime messages задаются константами production encoder, input message зависит от ошибки admission.

## Матрица отображения

Все перечисленные поля обязательны; `null` и пустые массивы явные. Нормативные поля — в ADR, полная матрица реализованных guards/tests — в аудите. Оба encoder отклоняют source, который нельзя представить fresh-only форматом без потери информации.

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

Порядок definitions хранится отдельно в MagicSimulationCommand и MagicBalanceCommand; production tests проверяют его перестановку независимо от roster. Ручной inverse в probe использует только порядок definitions этих известных fixtures. Он не реализует общий lossless guard или отказ для всех произвольных неподдержанных источников.

## Запуск probe

Из корня репозитория после установки зависимостей:

```sh
PYTHONPATH=src python docs/examples/m8/json_contract_probe.py
```

Для копирования нужны четыре Python-файла: `json_contract_probe.py`, `magic_balance.py`, `magic_simulation.py`, `magic_scenario.py`, а также этот каталог `json` с шестью fixtures. [Probe](../json_contract_probe.py) запускает реальные public simulation/generation/staged APIs: полное sequential/process равенство, round-trip известных request/scenario/execution, 13 semantic constructor rejects и реальную generation failure `(1,0)` после успешного C4/budget16 preflight. Проверяются неизменность raw/typed inputs, глобального RNG и отсутствие оставшихся children. [Stored stdout](../json_contract_probe.output.txt) проверяется [subprocess test](../../../../tests/integration/test_m8_magic_json_contract_probe.py) из внешнего cwd.

Обычный запуск не перезаписывает fixtures и не использует saved results как oracle. Явный `--write-results` обновляет только оба result JSON текущим runtime; error fixtures остаются иллюстрациями. Simulation production tests проверяют лексические отказы, unknown/required/nullable fields, version dispatch, enum/order mappings и lossless source. Simulation error encoder/service/CLI также проверены. Balance pure wire также проверен production tests. Balance execution/CLI также проверены; общий аудит обеих families завершён.

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

Stdout — один result/error object и newline, stderr — краткая диагностика. Exit0 включает все native outcomes,2 — input/usage,3 — simulation_failed с generic message и path=null,4 — I/O. Read/usage failure оставляет stdout пустым; при output failure нет второго error write. Python cause/notes доступны вызывающему service, но не попадают в JSON. Error encoder отвергает другие families; balance-magic также доступна. Общий аудит обоих magic commands завершён.

## Чистый balance API

```python
from pathlib import Path
from towr.adapters.magic_balance_json import parse_magic_balance_request, encode_magic_balance_result
from towr.application.magic_balance_models import MagicBalanceResult
from towr.application.magic_candidate_generation import generate_magic_candidates
from towr.application.magic_staged_evaluation_service import evaluate_magic_candidates_staged

command = parse_magic_balance_request(
    Path("docs/examples/m8/json/magic-balance-v1.request.json").read_bytes())
generated = generate_magic_candidates(command.generation_request)
evaluated = evaluate_magic_candidates_staged(generated.evaluation_request, command.execution)
print(encode_magic_balance_result(command, MagicBalanceResult(generated, evaluated)), end="")
```

Parser делает только admission резерва/отдельных family facts/полных frames и арифметический C/полный staged budget preflight. Пример явно запускает готовые generator/staged APIs; pure encoder не выполняет эти services и не создаёт RNG/pool. Для process требуется importable main guard. Готовый execute_magic_balance(command) связывает эти две фазы с full-source checks и typed errors; команда balance-magic и boundary error encoder также реализованы.

Все supplied frames, включая архивные/unreachable/empty-live, сохраняются по порядку. Success preflight не гарантирует допустимость всех generated subsets: invalid projection позже прерывает generator, не становится input rejection и не пропускается. Каталог содержит все vectors; full stage rows сохраняют unsupported и outside-window observations. Последний requested stage всегда имеет пустую continuation, final selection не берётся из раннего этапа. Input Fraction допускает несокращённый вид, normalized echo/rates сокращаются; все numeric budgets сохраняют integer precision. Семейство формы проверяется через `validate_magic_balance_document(document, kind)`, strict token spelling — через parser.

## Balance CLI

```sh
PYTHONPATH=src python -m towr balance-magic docs/examples/m8/json/magic-balance-v1.request.json
```

Установленный `towr balance-magic INPUT` принимает UTF-8 file относительно cwd или `-`/stdin. Process задаётся через `"execution": {"mode": "process", "workers": 2, "batch_size": 3}`. Все stages/caps/window/seed остаются explicit, CLI не переопределяет их. Вывод сохраняет весь catalog и aggregate reports без records/journals.

Exit0 включает completed/no_eligible/empty selection и unsupported observations. Input/usage даёт2, generation_failed/evaluation_failed —3, I/O —4. Runtime error содержит external request ID и известные candidate/counts либо stage/candidate; пути /generation и /evaluation определяются active phase. Другие context slots=null, cause/notes остаются в Python chain. Строгий preflight и поздняя недопустимая проекция — разные ошибки; нет skip/retry/fallback/partial reports. Result/error полностью кодируется до stdout, при output failure второй error object не пишется. Семь прежних команд сохраняют собственные formats/error families; общий аудит M8 JSON/CLI завершён. Проверенная среда — CPython3.12.15/macOS arm64; ограничения остальных runtimes и источник verification evidence указаны в readiness report.


## Dead Champion exclusion ADR-0044

[Request](dead-champion-v1.request.json) / [result](dead-champion-v1.result.json) — конечный authored regression witness со стандартным RNG, master seed31/trials1/round budget1. Три enemy archers имеют явные attack1d/10 и Damage10, Wizard Protection1d/1; это диагностические числа, не именованный NPC и не оценка вероятности сложности. Wounds3/2/25 приводят к одной matching exclusion phase до attacker end-turn; outcome round_limit_reached, native totals4/1/1.

```sh
PYTHONPATH=src python -m towr simulate-magic docs/examples/m8/json/dead-champion-v1.request.json
```

Для process задать существующий execution `{"mode":"process","workers":2,"batch_size":1}`. Формат/seed scheme прежние, custom RNG fields нет. Saved result содержит runtime проверочного CPython3.12.15, текущий CLI пишет свой runtime. [Propagation test](../../../../tests/integration/test_m8_dead_champion_propagation.py) проверяет actual default-RNG trace, service и внешний CLI sequential/process; [аудит](../../../audits/m8-dead-champion-readiness.md) отдельно проверяет установленный module/console и missing-frame control.
