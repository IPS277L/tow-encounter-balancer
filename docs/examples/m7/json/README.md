# Конечные примеры Mixed JSON v1

[ADR-0034](../../../decisions/ADR-0034-mixed-json-cli-v1.md) задаёт внешнюю границу. **Simulation JSON/CLI реализован, включая service и error encoder.** `simulate-mixed` принимает simulation fixture. Balance Schema/command/result/pure parser/result encoder также реализованы; balance service/error encoder и `balance-mixed` также реализованы; [общий аудит](../../../audits/m7-external-readiness.md) завершён. Существующие ranged/Melee команды их не принимают.

| Вход | Пример результата | Содержание |
| --- | --- | --- |
| [Simulation request](mixed-simulation-v1.request.json) | [Simulation result](mixed-simulation-v1.result.json) | Pbow/P1/P2 против E1/E2; 8 trials, seed 42, два раунда |
| [Balance request](mixed-balance-v1.request.json) | [Balance result](mixed-balance-v1.result.json) | Fixed Pbow/P1/P2; A=(E2,E1) 1..2, B=(E3) 0..1; четыре состава, stages 2/4 keep 2/1, budget 16 |

Профили и source IDs взяты из public [mixed_scenario](../mixed_scenario.py) и [mixed_balance](../mixed_balance.py): Footpad Dagger/Brigand Warbow, только numeric Minions. BOOK-PLAYER-GUIDE 1.4, Equipment / Ranged Weapons, стр. 94; Rules / The Battlefield / Range, стр. 114; Attack Tests / Attack Modifiers, стр. 118–119. BOOK-GM-GUIDE 1.1, Allies and Antagonists / Minions, стр. 91; Understanding NPC Profiles, стр. 93; Brigands & Footpads, стр. 97. Source ID — ссылка caller на выбранный профиль, не автоматическая загрузка из каталога.

Все pair ranges, facts, GM decisions и actor-scoped can_leave_zone/outnumbering flags явные. В reserve P2 имеет outnumbering=false/can_leave_zone=true; остальные — true/false. Family pairs повторяют exact ordered reserve pairs; отдельно переданные family facts/policies должны действовать для каждого состава. Неиспользованная Zone остаётся в графе. Внешний balance request ID отличается от initial reserve ID.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe docs/examples/m7/json_contract_probe.py
```

[Probe](../json_contract_probe.py) отображает только эти два authored inputs через public constructors, сравнивает их с existing typed builders и обратной проекцией известных scenario fields. Он исполняет sequential/process simulation и generation → staged evaluation: workers=2, batch_size=3, одинаковые полные results/reports. Один запуск — 8+16 trials на каждый backend, всего observed 48; budget на отдельную balance evaluation равен 16. Проверяются input/global RNG/оставшиеся child processes.

На Windows/Python 3.14.5 observed balance actual=planned=16. Assertions проверяют равенство backend и границы бюджета, но не конкретный процент/победителя. Saved results содержат metadata среды и служат примерами формы; они не являются statistical oracle. Чтобы явно обновить их по текущему runtime, добавить `--write-examples`. Обычный запуск файлов не перезаписывает. В probe нет CLI dispatch, strict parser, общего lossless codec, Schema validation или production error encoder.

## Матрица допуска и ошибок

| Изменение fixture | Где отклоняется | Проверка в этом срезе |
| --- | --- | --- |
| targets_aware/all_zone_combatants_included/ammunition_sufficient=false | scenario admission → invalid_input | Три public constructor rejections |
| Обратный side_order; gm_approved=false | scenario admission → invalid_input | Два constructor rejections |
| Отсутствующая или повторная pair | scenario admission → invalid_input | Два constructor rejections |
| Shooting hands=1h; Protection skill=defence | scenario admission → invalid_input | Два constructor rejections |
| max_candidates=3; max_total_trials=15 | generation preflight → invalid_input | Два constructor rejections |
| Обратный family pair order при прежнем reserve | generation preflight → invalid_input | Один constructor rejection |
| A.minimum=0, max_candidates=5, max_total_trials=18 | Preflight проходит; construction (0,1) → generation_failed | Реальный typed generation error; потеря начальной Close-цели, без skip |
| Duplicate keys, UTF-8/BOM, NaN/Infinity/surrogates | strict reader → invalid_json | Реализовано; deterministic parser tests |
| unknown/missing fields, lexical integer/seed, wrong version/kind | Schema/parser → invalid_input/unsupported_version | Реализовано; deterministic parser tests |
| Чужой source, непредставимые orders, changed pair/GM flag | command/encoder/source guards | Реализовано для simulation/balance; deterministic codec tests |
| Runner/process/late stage failure | application → execution_failed | Реализовано для simulation/balance; service/CLI tests |
| Read/write/flush/closed stream | CLI → exit 4 | Реализовано для обеих mixed-команд; CLI tests |

[Simulation error](mixed-simulation-v1.error.json) иллюстрирует удаление последней pair из simulation request. [Balance error](mixed-balance-v1.error.json) иллюстрирует три изменения bounds/caps/budget из строки (0,1). Это авторские иллюстрации envelopes; simulation error encoder теперь реализован, но fixture не закрепляет нестабильный текст сообщения parser. Balance error encoder реализован и сохраняет phase context. Positive request files остаются допустимыми. Ошибки имеют правильное семейство даже при malformed input без kind.

Первый production-срез реализован: [parser/encoder](../../../../src/towr/adapters/mixed_simulation_json.py), immutable command, общий scenario mapper и три simulation Schema. [Unit tests](../../../../tests/unit/test_m7_mixed_json.py) проверяют строгую лексику, форму, ссылки, mixed admission и lossless/exact-source guards; [integration](../../../../tests/integration/test_m7_mixed_json.py) сравнивает реальные sequential/process results и wire aggregates. Сохранённые fixtures не изменены. Finite probe выше остаётся самостоятельной иллюстрацией typed APIs, не заменой production parser.

Через Python API: `parse_mixed_simulation_request(text)` возвращает command; caller явно передаёт command.request существующему simulator, получает summary и вызывает `encode_mixed_simulation_result(command, summary)`. Parser и encoder не исполняют бой. Service `execute_mixed_simulation(command)` с единым error boundary и simulate-mixed теперь реализованы. Balance Schema/models/pure adapters теперь реализованы; balance service/errors/error encoder и balance-mixed также реализованы; [общий installed аудит шести команд](../../../audits/m7-external-readiness.md) завершён.


## Запуск simulation CLI

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m towr simulate-mixed docs/examples/m7/json/mixed-simulation-v1.request.json
# После установки текущего проекта:
.venv/Scripts/towr.exe simulate-mixed docs/examples/m7/json/mixed-simulation-v1.request.json
```

INPUT — UTF-8 файл относительно cwd либо `-` для stdin. Для process заменить execution в simulation JSON на `{"mode":"process","workers":2,"batch_size":3}`. Flags не переопределяют seed/backend. Stdout — один JSON result либо typed mixed_simulation_error; диагностика в stderr. Exit 0 означает полный результат, включая round_limit/unsupported_path; 2 — input/usage, 3 — execution, 4 — I/O. Ошибка чтения/аргументов не выдаёт JSON; сбой после завершённого trial не выдаёт частичную сводку. Ranged/Melee requests не принимаются этой командой.

Четыре прежние команды сохраняются. Balance fixtures выше доступны через pure Python adapters; передача их в simulate-mixed даёт invalid_input. Python service принимает только MixedSimulationCommand; wrong command TypeError, execution errors сохраняют request_id/cause/notes, BaseException проходит. Pure encoder проверяет exact summary source; application service использует штатный RNG.


## Balance JSON через Python API

[Parser/encoder](../../../../src/towr/adapters/mixed_balance_json.py) и [immutable command/result](../../../../src/towr/application/mixed_balance_models.py) реализованы. Они не исполняют бой: caller явно вызывает existing generator/evaluator. Пример для отдельного `.py` файла, запущенного из корня с PYTHONPATH=src:

```python
from pathlib import Path
from towr.adapters.mixed_balance_json import parse_mixed_balance_request, encode_mixed_balance_result
from towr.application.mixed_balance_models import MixedBalanceResult
from towr.application.mixed_candidate_generation import generate_mixed_candidates
from towr.application.mixed_staged_evaluation_service import evaluate_mixed_candidates_staged


def main():
    command = parse_mixed_balance_request(
        Path("docs/examples/m7/json/mixed-balance-v1.request.json").read_bytes())
    generated = generate_mixed_candidates(command.generation_request)
    evaluated = evaluate_mixed_candidates_staged(generated.evaluation_request, command.execution)
    print(encode_mixed_balance_result(command, MixedBalanceResult(generated, evaluated)), end="")


if __name__ == "__main__":
    main()
```

Main guard нужен для process backend. Balance parser не перечисляет count vectors; arithmetic preflight может допустить request, который затем отклонит generator. Семейство не сокращается молча. Внешний request ID независим от reserve ID; explicit family pairs должны точно повторять ordered reserve pairs. Выход сохраняет полный нормализованный request, каталог counts и aggregate-only stage reports с точными дробями, без compact trials.

[36 unit tests](../../../../tests/unit/test_m7_mixed_balance_json.py) и [2 integration tests](../../../../tests/integration/test_m7_mixed_balance_json.py) проверяют source chain, strict wire и равенство реальных backend без фиксации случайного процента. Service `execute_mixed_balance(command)` соединяет эти вызовы и предоставляет общий phase-specific error boundary; CLI описан ниже.

## Запуск balance CLI

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m towr balance-mixed docs/examples/m7/json/mixed-balance-v1.request.json
# После установки текущего проекта:
.venv/Scripts/towr.exe balance-mixed docs/examples/m7/json/mixed-balance-v1.request.json
```

INPUT — UTF-8 файл либо `-` для stdin. Для process задать в request `"execution": {"mode":"process","workers":2,"batch_size":3}`. Команда возвращает один npc_mixed_balance_result с полным request, каталогом составов и aggregate reports либо mixed_balance_error. Exit 0 включает пустой итоговый выбор и unsupported_path в observations; 2 — input/usage, 3 — generation/evaluation, 4 — I/O. Прежние пять команд сохраняются.

Generation failure сообщает candidate_id/counts; evaluation failure — stage_index/candidate_id. Неизвестный контекст — null, request_id всегда внешний. Изменение A.minimum_count на 0, max_candidates на 5 и max_total_trials на 18 проходит preflight, но теряет Close-цель в составе (0,1): exit 3, generation_failed, без оценки остальных составов. Поздний сбой этапа не выдаёт частичный отчёт. Причина и notes доступны Python caller через цепочку исключений; JSON execution messages общие.

Python caller может использовать `execute_mixed_balance(command)` из `towr.application.mixed_balance_service`, затем `encode_mixed_balance_result`; `encode_mixed_balance_error` принимает MixedBalanceInputError, MixedBalanceGenerationError и MixedBalanceExecutionError. Main guard остаётся обязательным для process. Чистые parser/encoders не запускают генерацию или бой.

## Готовность внешней границы

[Аудит ADR-0034](../../../audits/m7-external-readiness.md) завершён. Оба request исполняются установленным wheel через module/stdin и console/file в sequential/process вне repo/PYTHONPATH. Агрегаты и полный нормализованный request совпадают после исключения echoed execution; шесть packaged Schema и прежние команды проверены. Примеры не расширяют numeric Minion admission и не являются пресетами вероятности.
