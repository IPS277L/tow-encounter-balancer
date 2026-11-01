# M8 / ADR-0051: simulation JSON/CLI v3

Дата: 2026-11-01. **Пункт2 [ADR-0051](../decisions/ADR-0051-stationary-wound-generation-and-magic-json-v3.md) реализован и проверен; simulation3 этап закрыт.** [Native generation](m8-stationary-wound-generation-readiness.md) остаётся закрытым prerequisite. Balance3 и общий installed audit — пункты3–4; весь ADR ещё не закрыт.

## Реализованная граница

`simulate-magic` принимает JSON1/2/3. Только simulation3 добавляет обязательный nullable `scenario.stationary_wound_continuation`: строка `leg_spasm_stand_and_continue` либо null. Независимое `miscast_continuation` из v2 также обязательно и nullable; choice/facts/prone_policy не сокращаются. Все четыре сочетания допустимы, missing не означает null или permission другой policy. Scope — fresh-only ADR-0050, без новых игровых переходов/save-resume/house rules. PG1.4/GM1.1 и Rule IDs прежние, нового чтения книг нет.

| Граница | Код / проверенное поведение |
| --- | --- |
| Schemas/registry | Три [request](../../src/towr/adapters/schemas/magic-simulation-request-v3.schema.json)/[result](../../src/towr/adapters/schemas/magic-simulation-result-v3.schema.json)/[error](../../src/towr/adapters/schemas/magic-simulation-error-v3.schema.json) с собственными IDs. Closed scenario имеет собственный properties/required, nullable enum задан oneOf. Только bundled v1/v2 fragments, без сетевого resolver |
| Family version selection | [Registry](../../src/towr/adapters/magic_json_schema.py) допускает simulation1/2/3 и balance1/2, cache15; packaged33schemas/15magic. Default validator1. Balance3 отвергается до files/Schema load |
| Strict decoder | [_json_common](../../src/towr/adapters/_json_common.py) получает explicit magic-only family tuple. Прежний magic_v2=True остаётся1/2 для balance; шесть nonmagic routes — только1. Версия/ID доверены лишь после полного strict lexical decode |
| Command/errors | Append-last command metadata остаётся с default1, simulation closed set расширен до1/2/3. Simulation input error subclass и execution error допускают3; base/balance input и balance phase errors пока1/2 |
| Scenario mapping | [Shared mapper](../../src/towr/adapters/_magic_scenario_json.py) устанавливает обе typed policies до final scenario admission. Serialization выводит required поля также при null. V1/v2 lossless отказ stationary policy сохраняется |
| Полный encoder source | [Simulation adapter](../../src/towr/adapters/magic_simulation_json.py) re-admit request metadata и проверяет typed policies/собственные facts у command и summary до equality. Reconstruct-check сохраняет полный source, definition order и выбранную версию |
| Service | [Execution](../../src/towr/application/magic_simulation_service.py) re-admit source request/scenario/facts/permission до runner и на result/summary границах. Runtime error использует собственные command version/ID, не metadata cause. Нет retry/fallback/partial result |
| CLI | [Существующий route](../../src/towr/cli.py) сохраняет exit0/2/3/4, Unicode/stdin/file, explicit sequential/process и encode-before-write. Balance route3 явно unsupported, не превращается в игровой stop |

Для недоверенных строк lexical errors — fallback error1/null ID, даже при видимом3. После полного decode поддерживаемого simulation3 shape/semantic ошибки имеют error3 и decoded nonblank ID. Missing/non-string/unknown version остаётся fallback1; unknown string даёт unsupported_version `/schema_version`. Нельзя извлекать metadata tolerant reparse. В runtime только собственная версия command; причины/notes не публикуются.

Read-only ревью обнаружило отдельный source gap: во frozen scenario facts integer1 сравнивается равным True, поэтому одного full equality или `replace(Scenario)` недостаточно. Теперь собственные facts повторно проходят constructor перед equality в encoder и service; два targeted tests проверяют повреждение command/result/summary и отказ до runner/summarize. Это узкая проверка собственных моделей границы, не universal recursive validator всех K1 объектов.

## Детерминированная evidence

- [8 schema tests](../../tests/unit/test_m8_magic_simulation_schema_v3.py): null/four combinations, strict required/type/closed shape, version3 echo/error, old default1/v2 refusal, новые local refs,15magic/33total, balance3 отказ до loader.
- [13 wire/service unit tests](../../tests/unit/test_m8_magic_json_v3.py): полный source/order/seed round-trip без RNG, обе required nullable policies, точный stationary pointer, strict lexical trust/fallback table, version/error/phase contexts, enum и int1 facts laundering, same-ID source substitution, собственная версия service и неизменяемость источников.
- [9 integration tests](../../tests/integration/test_m8_magic_json_v3.py): actual parsed9→stand→Casting/end→incoming6→expiry48d10 и None7/Wound10 controls, four policy combinations/default native sequential/spawn records/source, denominator2 и unsupported rates без probability presets. Real CLI8combination/backend runs, Unicode/stdin, null/file/external cwd, trusted/lexical/runtime/private-output/closed-pipe/usage и balance/шесть nonmagic routes isolation.

Старые unsupported-version negatives simulation используют4 вместо теперь поддерживаемой3; проверки запрета stationary field у1/2 остаются. Native policy не выбирает версию автоматически. Старые schemas и v1/v2 JSON fixtures не менялись.

## Публичные данные

[Request](../examples/m8/json/magic-simulation-v3.request.json) явно задаёт обе policies, seed42/N4/round budget4 и sequential execution. [Stored result](../examples/m8/json/magic-simulation-v3.result.json) получен текущим CLI/CPython3.12.4, содержит точный полный echo и общий denominator. Это finite authored observation, не вероятность/preset и не oracle Monte Carlo для другого Python. Test сравнивает текущий CLI с текущим direct API, а saved result — со schema/exact request/metadata/trials.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-magic docs/examples/m8/json/magic-simulation-v3.request.json
```

Для process изменить только `execution` на `{"mode":"process","workers":1,"batch_size":1}`. Nullable stationary/Miscast поля обязательны и при обоих null; output/error остаётся3 после trusted decode.

[Public probe](../examples/m8/stationary_wound_transport_contract_probe.py)/[stdout](../examples/m8/stationary_wound_transport_contract_probe.output.txt) теперь выполняет8 настоящих simulation3 round-trips и8 finite manual balance3 mappings,20native generated projections и4staged rows. Прежние8scripted trials/138d10 сохранены. Balance3 часть явно fixture-bound; opted source не очищается ради старого parser/encoder. [Copied test](../../tests/integration/test_m8_stationary_wound_transport_contract_probe.py) использует те же пять Python-файлов из отдельного cwd.

## Проверки и граница аудита

База: commit `e842f48 M8 P20`, Windows x64 / CPython3.12.4. Локальные новые schema/wire/CLI срезы прошли:8schema tests/2,655с; первые8integration/47,196с плюс public-file case/2,269с. После устранения bool/int source gap два новых unit cases и связанный service case прошли3tests/0,331с. Пять прежних version-negative methods после перехода unsupported3→4 прошли/0,778с; copied probe и прежний v2 CLI error table —2tests/15,052с вне sandbox.

Полная регрессия:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

**3956tests /34errors /0failures /0skipped,885,280с**, вне sandbox. Все30новых tests и обновлённый copied probe прошли. Log `.cache/adr0051-simulation-v3-regression.log`. Из34 errors:

- 33 отсортированных exact `ERROR:` headers совпали с baseline `.cache/adr0051-generation-regression.log`:32Aim frozen/slotted property expectations и1`dataclasses.replace(init=False)`. Причины — в [открытых вопросах](../open-questions.md#проверки-dataclasses-на-python-312).
- 1 старый CLI negative-case `test_invalid_json_version_and_admission_have_input_exit_code` ещё считал string3 неизвестной версией. Единственное изменение после полного прогона — literal3→4 в этом negative-case; целевая перепроверка **1test OK/6,507с**, log `.cache/adr0051-simulation-v3-corrected-cli.log`.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest tests.integration.test_m8_magic_cli.M8MagicCliIntegrationTests.test_invalid_json_version_and_admission_have_input_exit_code -v
```

Production, public probe и новые tests после полного прогона не менялись. Полный suite после test-only исправления **не повторялся**: остальные checks уже прошли, исправленный case перепроверен отдельно. Нерешённых новых errors/failures нет, но полного лога3956/33 после этой правки не заявляется. Полный suite с прежними33errors не считается зелёным.

Saved v2 outputs совпали с прежним generated baseline при нормализации переводов строк; локальные Markdown-пути (без anchors) и `git diff --check` проверены отдельно.

Новый installed wheel/console/hash parity — пункт4. Текущие проверки относятся к source/module CLI и настоящему spawn; source schema closure проверена unit tests. Historical `tools/audit_m8_transport_install.py` требует12magic schemas и ещё не покрывает interim15/new3; его обновление/новый helper входит в общий audit, прежний installed отчёт не считается v3 evidence. В итоговой границе после balance3 будет18magic/36total.

## Следующий шаг

Пункт3 ADR-0051 целиком: balance3 — ещё три schemas, independent required reserve/family stationary assertions, exact typed equality до generation, closed command/errors/reader support3, полный generation→staged→reports/request echo и parser/service/encoder/CLI с actual backends. Не допускать v3 input с output/error старой версии; preserve1/2 losses/refusals. Затем общий installed/schema/local-ref/module/console/spawn audit и full regression.

Commit/push выполняет пользователь. Новые файлы:3schemas,3test modules, public request/result и этот audit; изменены simulation boundary/strict helper, CLI help, public probe/stdout и старые negative-version tests. Общая документация/статус обновлены главным агентом.
