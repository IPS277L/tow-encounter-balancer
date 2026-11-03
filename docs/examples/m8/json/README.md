# Magic JSON: simulation/balance v6, v5, v4, v3, v2, v1 fixtures

## V6 — Battered Leg с authored Endurance profile

[Simulation request](magic-simulation-v6.request.json) и [balance request](magic-balance-v6.request.json) содержат required nullable `battered_leg_continuation`: `null` либо `{"endurance_profile":{"dice":2,"threshold":5}}`. Оба objects закрыты, без custom cap; четыре прежних permissions также обязательны. Balance требует независимый matching reserve/family profile целиком. Это только fresh source, без current battle history/save-resume и без нового consumer снятия Prone5.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-magic docs/examples/m8/json/magic-simulation-v6.request.json
.venv/Scripts/python.exe -m towr balance-magic docs/examples/m8/json/magic-balance-v6.request.json
```

Explicit6 сохраняется в полном echo/result/errors даже при пятиnull; default1 прежний. Lexical failures даютfallback1/null, неизвестная7 остаётсяunsupported. JSON1–5 отвергают новый key дажеnull и nonNone приencode доprojection. [Контракт62](../../../decisions/ADR-0062-battered-leg-generation-and-magic-json-v6.md), [production proof](../battered_leg_transport_contract_probe.py), [приёмка](../../../audits/m8-battered-leg-transport-readiness.md).

## V5 — Crushed Rib fresh-source permission

[Simulation request](magic-simulation-v5.request.json) и [balance request](magic-balance-v5.request.json) добавляют required `crushed_rib_continuation`: `null` либо точную строку `next_test_with_journal_witnesses`. Simulation хранит его в `scenario`; balance требует независимые одинаковые значения в `reserve.scenario` и `generation`. Miscast2, stationary3 и repeated4 fields также остаются обязательными. Это только fresh source permission: бой, Wound history/journal и save/resume не передаются.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-magic docs/examples/m8/json/magic-simulation-v5.request.json
.venv/Scripts/python.exe -m towr balance-magic docs/examples/m8/json/magic-balance-v5.request.json
```

Обе families сохраняют v5 в полном request echo, result и input/phase errors; malformed lexical input и неизвестная v7 сохраняют fallback v1 по strict-reader контракту. Balance требует точного reserve/family match до генерации. JSON1–4 продолжают отказывать при наличии нового ключа даже со значением null. Проверки: [simulation unit/schema](../../../../tests/unit/test_m8_magic_json_v5.py), [balance unit/schema](../../../../tests/unit/test_m8_magic_balance_json_v5.py), [CLI integration](../../../../tests/integration/test_m8_magic_json_v5.py), [ADR-0058](../../../decisions/ADR-0058-crushed-rib-generation-and-magic-json-v5.md).

## V4 — independent repeated Leg Spasm permission

[Simulation request](magic-simulation-v4.request.json) / [result](magic-simulation-v4.result.json) и [balance request](magic-balance-v4.request.json) / [result](magic-balance-v4.result.json) содержат обязательный nullable `repeated_leg_spasm_continuation`: null либо `stand_once_with_journal_witnesses`. У balance reserve и generation имеют отдельные matching assertions. Поле требует selected stationary policy; Miscast независим. Все3 поля обязательны даже при null. Версия остаётся4 в request/result/error; default version1, gameplay scope native53 прежний.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-magic docs/examples/m8/json/magic-simulation-v4.request.json
.venv/Scripts/python.exe -m towr balance-magic docs/examples/m8/json/magic-balance-v4.request.json
```

Для процессов задать `execution` как `{"mode":"process","workers":2,"batch_size":1}`. Saved results получены на CPython3.12.4 и являются finite observations; сравнение Monte Carlo bytes допустимо только на том же runtime. JSON1/2/3 новое поле запрещают даже null. Семантическая dependency error указывает на scenario repeated field, family mismatch — `/generation/repeated_leg_spasm_continuation`; unknown5 даёт fallback1 с decoded ID, lexical failure — fallback1/null ID. Контракт — [ADR-0054](../../../decisions/ADR-0054-repeated-leg-spasm-generation-and-magic-json-v4.md).

[Общий source/wheel/installed audit ADR-0051](../../../audits/m8-stationary-wound-transport-readiness.md) завершён: обе families1/2/3 и6legacyroutes, module/console/stdin/file/actualprocess,18magic/36schemas/383localrefs. На текущем CPython3.12.4 публичные v2/v3 results совпали с saved bytes; v1 snapshots3.12.15 имеют другую runtime metadata, non-runtime JSON fields совпали при отдельном finite сравнении. Все repository fixtures оставлены неизменными. Эта evidence не означает универсальную cross-runtime вероятность.

## Balance v3 — separate reserve/family assertions

[Request](magic-balance-v3.request.json) явно содержит `reserve.scenario.stationary_wound_continuation` и `generation.stationary_wound_continuation`: обе null либо одна и та же enum string. Miscast object/null также обязателен отдельно в reserve/generation. Mismatch — input error3 по `/generation/stationary_wound_continuation`; missing не заменяется null/наследованием. Native family assertion остаётся обязательным.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr balance-magic docs/examples/m8/json/magic-balance-v3.request.json
```

Для process заменить execution на `{"mode":"process","workers":1,"batch_size":1}`. [Stored result](magic-balance-v3.result.json) получен CLI на CPython3.12.4: C4/planned16/actual12 и полные catalog/stages/request3. Это finite observation, не preset/вероятность для другого runtime. При обоих null версия остаётся3. Ошибки после full decode recognized3 имеют3; malformed lexical input — fallback1/null ID. Runtime errors сохраняют собственный candidate/counts либо stage/candidate без cause/notes/partial report. [Contract](../../../decisions/ADR-0051-stationary-wound-generation-and-magic-json-v3.md), [audit/tests](../../../audits/m8-balance-v3-readiness.md).

## Simulation v3 — независимая stationary policy

[Request](magic-simulation-v3.request.json) содержит обязательный `scenario.stationary_wound_continuation`: `"leg_spasm_stand_and_continue"` либо null, и независимый required nullable Miscast object прежней формы. Нельзя опускать ни одно поле даже при обоих null. [Stored result](magic-simulation-v3.result.json) получен CLI на CPython3.12.4 с полным request3 echo и denominator4; это finite observation, не probability preset для другого runtime.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-magic docs/examples/m8/json/magic-simulation-v3.request.json
```

Для process заменить execution на `{"mode":"process","workers":1,"batch_size":1}`. После полного strict decode simulation3 shape/semantic errors имеют версию3; malformed UTF-8/JSON, duplicate keys, surrogate, float/exponent/nonfinite — fallback1/null ID. Runtime error сохраняет собственную версию command. Null policies не понижают версию. [Контракт](../../../decisions/ADR-0051-stationary-wound-generation-and-magic-json-v3.md), [аудит/tests](../../../audits/m8-simulation-v3-readiness.md), [public proof](../stationary_wound_transport_contract_probe.py).

Native generation использует separate matching family opt-in; обе v3 families реализованы. Приведённые ниже production v1/v2 fixtures не меняются и не разрешают stationary policy даже null. Не удалять policy из native opted source ради старого encoder. Fresh-only JSON3 не является save/resume.

## Simulation v2 — ADR-0047

[Вход v2](magic-simulation-v2.request.json) явно включает полную Miscast/Prone policy в прежний authored сценарий. `scenario.miscast_continuation` обязателен: `null` сохраняет legacy gameplay, полный object включает ограниченный runner ADR-0046. V1 это поле запрещает даже с `null`. Наличие policy не выбирает версию автоматически.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m towr simulate-magic docs/examples/m8/json/magic-simulation-v2.request.json
```

Для process изменить только `execution` на `{"mode":"process","workers":2,"batch_size":1}`. Request echo/result/error после complete strict decode сохраняют `schema_version='2'`; malformed JSON/UTF-8, duplicate keys, lone surrogates, nonfinite/float/exponent tokens возвращают fallback error v1 и null request ID. Runtime failure имеет версию admitted command. Public validators требуют явного `schema_version='2'`; default остаётся v1. [Полный контракт](../../../decisions/ADR-0047-opt-in-generation-and-magic-json-v2.md), [аудит/tests](../../../audits/m8-simulation-v2-readiness.md).

Этот пример — finite standard-RNG observation, не probability preset; incomplete future frames/прочие Miscast effects остаются unsupported и входят в trials. [Integration test](../../../../tests/integration/test_m8_magic_json_v2.py) проверяет файл и sequential/process CLI. Balance v2 также реализован и описан ниже. [Installed audit обоих v2 families](../../../audits/m8-opt-in-transport-readiness.md) завершён. [Сохранённый result](magic-simulation-v2.result.json) получен реальным sequential CLI на CPython3.12.4; полный вывод совпал с source/installed module/console.

## Balance v2 — отдельное family assertion

[Вход](magic-balance-v2.request.json) содержит два обязательных nullable поля: `reserve.scenario.miscast_continuation` и `generation.miscast_continuation`. Оба — null либо одинаковые полные policy objects; caller подтверждает scope отдельно для резерва и каждого generated subset. Несовпадение — input error по `/generation/miscast_continuation`. Отсутствующее поле не заменяется null или значением из другого места.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m towr balance-magic docs/examples/m8/json/magic-balance-v2.request.json
```

Для process: `"execution":{"mode":"process","workers":2,"batch_size":1}`. Полный reserve/generation echo, каталог, stages, rates и unsupported denominator прежние. Version2 сохраняется также при policy=null. Успешная проверка входа не гарантирует допустимость всех subsets: поздний generation failure даёт exit3 с known candidate/counts, evaluation failure — со stage/candidate; cause/notes не выходят на wire. До complete strict decode fallback error1/null ID, после распознанной2 — error2; правила совпадают с simulation выше. Pure validators требуют explicit `schema_version='2'`, default остаётся1.

[Аудит balance](../../../audits/m8-balance-v2-readiness.md), [integration tests](../../../../tests/integration/test_m8_magic_balance_json_v2.py). Пример C4/stages2/4/upper budget16 — finite authored observation, не difficulty preset. [Installed audit](../../../audits/m8-opt-in-transport-readiness.md) завершён; [сохранённый result](magic-balance-v2.result.json) получен реальным sequential CLI на CPython3.12.4. V1 fixtures ниже неизменны.

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
