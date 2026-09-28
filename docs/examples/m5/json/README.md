# JSON/CLI balance v1

[ADR-0020](../../../decisions/ADR-0020-ranged-balance-json-v1.md) реализован: Schema, parser, result/error encoders, application service и команда balance. Это внешний запуск существующего ограниченного M5: фиксированная perspective-side и численность противников из явно заданного резерва. [Python-пример](../README.md) остаётся самостоятельной демонстрацией typed API.

## Запуск

Из корня репозитория после установки зависимостей:

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m towr balance docs/examples/m5/json/balance-v1.request.json
```

После установки текущего проекта также доступна `.venv/Scripts/towr.exe balance INPUT`. INPUT обязателен: путь к UTF-8 файлу относительно cwd либо `-` для stdin. Backend, seed, окно и бюджеты задаются только в JSON. Для process замените execution на `{"mode":"process","workers":2,"batch_size":4}`; CLI имеет защищённую точку входа для spawn.

Stdout содержит один UTF-8 JSON с LF, stderr — диагностику. Exit 0 означает полный результат, включая no_eligible_candidates, unsupported observations или пустой итоговый выбор; 2 — input/usage, 3 — generation/execution failure, 4 — I/O. При usage/read failure stdout пуст; при write failure может быть доставлена часть bytes, второго JSON не будет. Нужно учитывать exit code. Cause/traceback и частичные reports при сбое не сериализуются.

## Файлы

- [balance-v1.request.json](balance-v1.request.json) — полный резерв P1/P2 против A1/A2/B1, отдельные family facts, группы A=0..2/B=0..1, окно [1/4,3/4] с target 1/2, seed 42, stages 8/keep 3 и 32/keep 2. C=5, верхний бюджет 136. Outer request_id и reserve.initial_request_id различаются.
- [balance-v1.result.json](balance-v1.result.json) — результат реальных generation/staged APIs в формате готового encoder, с полным echoed request, каталогом составов и всеми aggregate reports. Исходный runtime: CPython 3.14.5, random.Random; sequential/process дали равные typed results. Сохранённые наблюдения используются как explicit aggregate fixtures для проверки кодирования, а не как статистическое ожидание будущих прогонов.
- [balance-v1.input-error.json](balance-v1.input-error.json) — образец invalid_input для denominator=0. Сам сохранённый request корректен; wording сообщения Schema может отличаться. Текст message не является стабильным API.
- [balance-v1.generation-error.json](balance-v1.generation-error.json) — образец сбоя materialization состава (1,0) после preflight; stage_index=null, partial output отсутствует.
- [balance-v1.execution-error.json](balance-v1.execution-error.json) — образец сбоя кандидата (1,1) на этапе с индексом 1; counts=null, partial reports отсутствуют.

Три error examples проходят Schema и воспроизводятся encoder из явных typed errors. Они не заявляют реальные сбои сохранённого корректного запроса. Ошибки materialization второго состава, позднего trial и создания pool отдельно проверяются через настоящие application boundaries. I/O failure не имеет wire error code.

Наблюдения первого этапа для (0,1)/(1,0)/(1,1)/(2,0)/(2,1) дают objective counts 8/8/2/2/0 из 8. В уточнение проходят (0,1), (1,1), (2,0): промежуточный outside-window кандидат допустим. На втором этапе objective counts 31/13/13 из 32; final selection — (1,1), (2,0). Последний continuation пуст, поскольку третьего этапа нет. Эти данные иллюстрируют seed/runtime и не являются гарантией вероятности. Между backend сравниваются aggregates/selection; echoed execution закономерно различается.

## Python API и проверки

[parse_ranged_balance_request](../../../../src/towr/adapters/ranged_balance_json.py) принимает str/UTF-8 bytes и возвращает immutable command. [execute_ranged_balance(command)](../../../../src/towr/application/ranged_balance_service.py) вызывает существующие generation/staged APIs и возвращает source-bound RangedBalanceResult. encode_ranged_balance_result(command, result) создаёт полный output; encode_ranged_balance_error обрабатывает только известные typed input/generation/execution errors. Для вызова process service напрямую нужен importable guarded main.

[JSON integration tests](../../../../tests/integration/test_m5_ranged_balance_json.py) проходят parse → service → encode → parse в sequential/process с сохранением источников и независимых порядков. [CLI tests](../../../../tests/integration/test_m5_balance_cli.py) проверяют file/stdin/Unicode, real spawn, input/usage/I/O/pool failures и exit codes. [Service failure tests](../../../../tests/integration/test_m5_ranged_balance_service.py) проверяют остановку после первого состава и после успешно выполненного этапа без partial result. Полная [матрица](../../../decisions/ADR-0020-ranged-balance-json-v1.md#матрица-проверки-и-порядок-реализации) закрыта [конечным аудитом](../../../audits/m5-external-readiness.md) в заявленном scope.
