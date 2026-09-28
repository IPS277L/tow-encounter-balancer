# Контрактные примеры Melee JSON v1

Контракт [ADR-0027](../../../decisions/ADR-0027-melee-json-cli-v1.md) подготовлен. **Simulation Schema, command, parser, service, summary/error encoder и simulate-melee реализованы. Balance Schema/command/result, parser/result/error encoder, service и balance-melee также реализованы.** Оба семейства документов проверены production adapters; они не являются входом существующих ranged simulate/balance.

| Пример | Содержание |
| --- | --- |
| [Simulation request](melee-simulation-v1.request.json) | Numeric Footpad 2×2, seed 42, 8 trials, три раунда, sequential; явные facts/GM policies и Protection Athletics/Attack 1h |
| [Simulation result](melee-simulation-v1.result.json) | Проекция фактической summary; полный echo, seed scheme/runtime, четыре counts, sums/means; без trial records |
| [Balance request](melee-balance-v1.request.json) | Пять составов из явного резерва P1,P2/E1,E2,E3, groups A=(E2,E1) 0..2 и B=(E3) 0..1; family facts отдельно, P2 outnumbering=False, stages 2/4 keep 2/1, полный budget 18 |
| [Balance result](melee-balance-v1.result.json) | Каталог count vectors и фактические aggregate reports обоих этапов, exact Fraction rates, local/continuation/final selection |

[json_contract_probe.py](../json_contract_probe.py) читает только эти два authored request через стандартный json.loads, явно отображает поля в public constructors и сверяет полное равенство с прежними typed examples. Он исполняет simulation и generation→staged в sequential и real process (workers=2,batch_size=3), сравнивает полные typed results и вручную проецирует предложенную форму результата. Simulation: 8 trials на backend; balance: 18 на backend; всего 52 trials. Outputs получены из этих прогонов, не из заранее выбранных вероятностей. Runtime metadata относится к текущему encoder/probe, не доказывает идентичность кода/RNG.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m6/json_contract_probe.py
```

Обычный запуск не перезаписывает JSON fixtures. Для явного обновления наблюдаемых result files на текущем runtime:

```powershell
.venv/Scripts/python.exe docs/examples/m6/json_contract_probe.py --write-examples
```

Семь проверенных отказов public constructors: Close=False, неполный состав Zone, обратный side_order, отсутствие GM approval defeat, cap 4 при C=5, другая family Zone и budget 17 при planned=18. Case False outnumbering одобрен контрактом и присутствует в положительном balance fixture; это не отсутствие GM решения. Источники после проверки неизменны. Доли/победитель сохранённых outputs не являются статистическим test oracle.

Probe **не реализует strict wire admission**: unknown/missing fields, duplicate keys, UTF-8/surrogates/nonfinite, lexical float/exponent, canonical seeds, error JSON/paths и Schema result validation для simulation проверены production tests; simulation error encoder/CLI и balance pure adapters проверены отдельными tests; balance service/error encoder/CLI также проверены unit/integration tests; общий installed аудит остаётся завершающим срезом ADR-0027. Fixture mapper нельзя использовать вместо production parser. Он не проверяет lossless сериализацию произвольных low-level snapshots и не является универсальным codec. Файлы result созданы контрактной проекцией; production simulation encoder воспроизводит её для той же typed summary. Полные typed reports в обоих backend совпадают; production balance encoder воспроизводит сохранённый result из той же полной typed source/report chain.

Будущие ошибки иллюстрируются формами:

```json
{"schema_version":"1","kind":"melee_simulation_error","request_id":"example:melee","error":{"code":"invalid_input","path":"/scenario/facts/targets_aware","message":"targets_aware must be true"}}
```

```json
{"schema_version":"1","kind":"melee_balance_error","request_id":"example:melee:balance:json","error":{"code":"generation_failed","path":null,"message":"Balance candidate generation failed","candidate_id":"footpads:counts:1,0","counts":[1,0],"stage_index":null}}
```

Это формы контракта, не искусственно вызванные production wire errors. Нормативные правила остаются в книгах и typed Melee APIs; формат не создаёт новые игровые решения или Abilities.

Production simulation API: `parse_melee_simulation_request(str|bytes)` → immutable `MeleeSimulationCommand`; `encode_melee_simulation_result(command, summary)` → UTF-8-совместимый JSON str+LF. Summary — существующий `NpcMeleeSimulationSummary`, связанный с exact request. Эти функции не исполняют simulation, RNG или pool. Проверка: `python -m unittest tests.unit.test_m6_melee_json tests.integration.test_m6_melee_json -q` (при PYTHONPATH=src). `execute_melee_simulation(command)` выбирает existing backend и возвращает summary; `encode_melee_simulation_error(error)` кодирует собственные typed input/execution failures. Service сначала получает полный trial result, затем summary; aggregate wire не означает streaming или ограниченную память.

## Production simulate-melee

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m towr simulate-melee docs/examples/m6/json/melee-simulation-v1.request.json
```

Установленная команда: `towr simulate-melee INPUT`, где INPUT — относительный к cwd UTF-8 файл или `-` для stdin. Sequential/process выбирается в JSON, без CLI overrides. Stdout — один UTF-8 JSON+LF (result или error), stderr — краткая диагностика. Exit 0 означает полную summary, включая round_limit/unsupported_path; 2 — input/usage, 3 — execution, 4 — read/write/flush/diagnostic I/O. Usage и ошибка чтения не создают JSON; при обрыве output pipe доставленный префикс отбрасывается, повторной записи нет. Ошибка encoder не маскируется ошибкой исполнения. Команда сама выбирает parser/error family; ranged kind не принимается.

Проверены installed module/console × sequential/process вне repo без PYTHONPATH, UTF-8 при ASCII text streams, все три packaged Schema/local refs и прежние ranged simulate/balance. Числовые факты и решения GM по-прежнему задаёт caller; service не вычисляет Close/awareness/Protection и не добавляет house rules.

## Production balance pure API

`parse_melee_balance_request(str|bytes)` → immutable `MeleeBalanceCommand(request_id,generation_request,execution,definition_order)`. Parser проверяет полный reserve, отдельные family facts и общий staged budget до materialization/RNG. `MeleeBalanceResult(generation_result,evaluation_result)` требует точного совпадения generated evaluation source. `encode_melee_balance_result(command,result)` → JSON str+LF с полным каталогом составов, aggregate stage reports и нормализованными Fraction; trial records не выводятся. Commands/results не хранят исходный mutable JSON.

`execute_melee_balance(command)` соединяет existing `generate_melee_candidates` и `evaluate_melee_candidates_staged` с exact options и возвращает полный `MeleeBalanceResult`. `encode_melee_balance_error(error)` кодирует собственные typed input/generation/execution errors; CLI balance-melee использует эту цепочку. [Unit tests](../../../../tests/unit/test_m6_melee_balance_json.py) воспроизводят сохранённый result из typed aggregates и проверяют negative cases; [integration](../../../../tests/integration/test_m6_melee_balance_json.py) исполняет реальные sequential/process через прежние APIs. Запуск: `python -m unittest tests.unit.test_m6_melee_balance_json tests.integration.test_m6_melee_balance_json -q` при PYTHONPATH=src.

## Production balance-melee

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m towr balance-melee docs/examples/m6/json/melee-balance-v1.request.json
```

Установленная команда: `towr balance-melee INPUT`; INPUT — UTF-8 файл относительно cwd или `-` для stdin. Для process задайте в JSON `"execution": {"mode":"process","workers":2,"batch_size":3}`. Stdout получает один полный UTF-8 JSON+LF после генерации/оценки/кодирования, stderr — краткую диагностику. Коды: 0 — полный result, включая no_eligible_candidates, completed с пустым выбором или final unsupported; 2 — input/usage; 3 — generation/execution; 4 — read/write/flush/diagnostic I/O.

Generation failure сохраняет внешний request_id и известные candidate_id/counts, execution failure — request_id и известные stage_index/candidate_id; неизвестные поля явно null. Cause/notes остаются в Python exception chain, wire содержит общее сообщение. При сбое после завершённого этапа частичная сводка не возвращается; повторов и fallback нет. Ошибки encoder не переименовываются в execution_failed. При обрыве stdout pipe получатель отбрасывает доставленный префикс. Ranged simulate/balance и simulate-melee сохраняют свои parser/error families.

[Общий аудит установленной внешней границы](../../../audits/m6-external-readiness.md) завершён: обе Melee-команды и оба backend, прежние ranged-команды, шесть packaged Schema и standalone примеры проверены вне repo/PYTHONPATH. Ограничения admission, памяти и RNG provenance перечислены в отчёте.
