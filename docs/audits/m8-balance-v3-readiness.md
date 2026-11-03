# M8 / ADR-0051: balance JSON/CLI v3

Дата: 2026-11-01. **Пункт3 [ADR-0051](../decisions/ADR-0051-stationary-wound-generation-and-magic-json-v3.md) реализован и проверен; balance3 этап закрыт.** [Native generation](m8-stationary-wound-generation-readiness.md) и [simulation3](m8-simulation-v3-readiness.md) — закрытые prerequisites. Общий installed/schema/console audit пункта4 ещё предстоит, весь ADR не закрыт.

**Последующий пункт4 и весь ADR закрыты:** [общий audit](m8-stationary-wound-transport-readiness.md). Новый source candidate-facts guard, finalwheel465/36schemas/383refs,269transportcommands и installed native spawn проверены; финальный full3987/33known/0failures. Ниже сохранена evidence этапа3 до общего аудита, её ограничения на installed proof заменены новым отчётом.

## Реализованная граница

`balance-magic` принимает1/2/3. В версии3 `reserve.scenario` и `generation` содержат **оба независимых required nullable поля**: stationary string `leg_spasm_stand_and_continue`/null и прежний полный Miscast object/null. Caller подтверждает permission отдельно для резерва и всех generated subsets. Missing не заменяется null или значением другого поля. Exact typed equality проверяется до generation preflight; stationary mismatch указывает `/generation/stationary_wound_continuation`, Miscast mismatch — прежний pointer.

Новых игровых переходов, Rule IDs/house rules или чтения книг нет. PG1.4/GM1.1 и native scope ADR-0050 прежние: canonical first9 stand/context49, active/expired6, no external causes, normal Tests; остальные mandatory effects дают honest unsupported. Fresh-only JSON не save/resume, unsupported остаётся в denominator.

| Граница | Реализация / evidence |
| --- | --- |
| Schemas | Новые [request](../../src/towr/adapters/schemas/magic-balance-request-v6.schema.json)/[result](../../src/towr/adapters/schemas/magic-balance-result-v6.schema.json)/[error](../../src/towr/adapters/schemas/magic-balance-error-v6.schema.json) с собственными IDs, closed reserve/generation и exact request3 echo. Scenario/stationary refs — bundled simulation3, Miscast — simulation2, остальное — неизменные1/2 fragments |
| Registry | [Обе magic families](../../src/towr/adapters/magic_json_schema.py) допускают1/2/3, cache18;18magic/36total schemas. Default1, unknown4 отвергается до загрузки файлов, transitive refs разрешаются без network retrieval |
| Strict reader/errors | [Adapter](../../src/towr/adapters/magic_balance_json.py) использует explicit magic tuple1/2/3. Balance command/input/generation/evaluation errors допускают3; default/positional compatibility прежние. Шесть nonmagic routes по-прежнему1 |
| Input | Shared mapper устанавливает обе typed policies до fresh scenario admission; family fields читаются отдельно и сверяются до groups/frame/budget/generation. В1/2 stationary key запрещён даже null |
| Command/source | [Модели](../../src/towr/application/magic_balance_models.py) re-admit исходный generation request до дальнейшей обработки. Полные facts/policies/frames/IDs/seeds/budgets остаются частью источника |
| Result/source chain | Явно проверяются generation, staged request, reports, candidate/assessment/summary sources и собственные typed facts/permissions до equality. Проверка bounded/pure, не выполняет trials или generator entrypoint и не является общим recursive validator |
| Service | [Фазы execution](../../src/towr/application/magic_balance_service.py) проверяют command перед generator, generated source до evaluator и evaluated source перед публикацией. Ошибка сохраняет собственные command version/ID и candidate/counts либо stage/candidate; cause/notes остаются приватными |
| Encoder | Полная result chain проверяется до source comparison, затем command encode→parse reconstruct-check включает definition order, версию и обе policies. Catalog/stages/reports прежней формы; явная версия3 не понижается при null |
| CLI | Существующий `balance-magic` сохраняет stdin/file/Unicode и explicit sequential/process, exit0/2/3/4 и отсутствие partial/retry/backend fallback. Input error не превращается в игровой unsupported |

Read-only ревью выявило конкретный обход в `report.source_request.simulation_requests`, поле `compare=False`. Повреждённый cached request с другой stationary policy раньше не участвовал в full dataclass equality, а rebuild мог скрыть подмену. Теперь **исходный ordered cache** сравнивается с ожидаемым до использования rebuilt report source; mismatch даёт ValueError, исходный tuple/None policy не нормализуется. Отдельный regression проверяет encoder и evaluation service publication. Других блокеров ревью не выявило.

## Детерминированная evidence

- [9 schema tests](../../tests/unit/test_m8_magic_balance_json_v6_schemas.py): four policy combinations, required nullable/strict type/unknown/closed objects, own3 request echo и phase error contexts, default1/old1/2 refusal, все transitive local refs реального registry,18/36 counts и unknown4 до loader.
- [13 wire/service unit tests](../../tests/unit/test_m8_magic_balance_json_v3.py): полный reserve/family/source round-trip без RNG, both-direction mismatch до generation, old1/2 lossless guards, strict lexical trust table, own version/phase privacy, same-ID source substitution, detached summary facts1=True/raw enum laundering и отдельный compare=False cache regression.
- [8 integration tests](../../tests/integration/test_m8_magic_balance_json_v3.py): genuine variable3/4actor subsets с actual parsed9→stand→Casting/end→6expiry48/66d10, four policy combinations native/staged sequential/spawn и CLI, unsupported denominator и полные reruns/seed prefix. Actual late projection failure на втором counts(1,1) сохраняет candidate/counts после успешного первого subset; actual stage1 evaluation failure после двух first-stage candidates сохраняет stage/candidate и исключает partial/private output. Также Unicode/trusted errors/nonmagic isolation и публичный fixture.

Все исходные None/native states/seed schemes/порядки сохраняются. Старые unknown-version negatives balance используют4 вместо поддерживаемой3; прежние simulation3 tests теперь проверяют обе доступные families и cache18/36. Проверки отказа stationary source в JSON1/2 остаются.

## Публичные данные

[Request](../examples/m8/json/magic-balance.request.json) — явный резерв, independent reserve/family permissions, seed42, C4/stages2/4 и upper budget16. [Stored result](../examples/m8/json/magic-balance.result.json) получен CLI на CPython3.12.4: полный request3, catalog и reports, actual12/planned16. Это finite observation, не difficulty preset или Monte Carlo oracle для другого runtime. Test сравнивает текущий CLI с текущим native API; saved evidence проверяет schema/exact request/catalog/budget/denominator/runtime.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr balance-magic docs/examples/m8/json/magic-balance-v3.request.json
```

Для process изменить только `execution` на `{"mode":"process","workers":1,"batch_size":1}`. Null policies не понижают версию. После полного strict decode recognized3 ошибки shape/semantics имеют3 и decoded nonblank ID; malformed UTF-8/JSON, duplicate keys, surrogate, float/exponent/nonfinite — fallback1/null ID. Unknown version — fallback1/unsupported_version. Runtime errors используют только собственную metadata command, не cause.

[Public probe](../examples/m8/stationary_wound_transport_contract_probe.py)/[stdout](../examples/m8/stationary_wound_transport_contract_probe.output.txt) теперь выполняет **16 actual public round-trips**:8simulation3+8balance3, четыре сочетания policies и обе perspectives.20actual generation projections сравниваются с независимым manual project;4generated staged rows и8scripted trials/138d10 сохранены. Manual inverse служит finite oracle известных полных fixtures, а decoded execution/encoding обоих families — production APIs. Ни opted source, ни policy не удаляются ради старого codec.

## Проверки и граница аудита

База commit `cfc694e M8 P21`; Windows x64 / CPython3.12.4. Новые9schema tests OK/6,880с;12wire unit OK/5,200с +cache regression1OK/0,570с;7integration OK/162,420с +public fixture1OK/4,194с вне sandbox.68existing unit OK/38,485с; updated copied probe и два старых CLI negative tables —3tests OK/40,788с. Всего30новых tests.

Полная регрессия на границе этапа:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

**3986tests /33known errors /0failures /0skipped,1860,416с**, вне sandbox. Все30новых tests и updated copied probe прошли; все33 отсортированных exact `ERROR:` headers совпали с `.cache/adr0051-generation-regression.log`. Нерешённых новых errors/failures нет. Log `.cache/adr0051-balance-v3-regression.log`.

32errors относятся к прежним Aim frozen/slotted property expectations,1 — к `dataclasses.replace(init=False)`, см. [открытые вопросы](../open-questions.md#проверки-dataclasses-на-python-312). Этот полный прогон также проверил ранее исправленный simulation3 CLI negative-case; дополнительной ошибки предыдущего snapshot3956/34 больше нет. Полный suite с известными33errors не считается зелёным. Production/tests/probe после полного прогона не менялись.

Saved v2 outputs совпали с прежним generated baseline при нормализации переводов строк; локальные Markdown-пути (без anchors) и `git diff --check` проверены отдельно.

Новый installed wheel/module/console/hash audit относится к пункту4. Здесь проверены source/module CLI, schema closure и настоящий spawn. Historical `tools/audit_m8_transport_install.py` ещё требует12magic schemas; его обновление до18/36 и обеих families1/2/3 — следующий этап. Прежний installed отчёт не выдаётся за доказательство v3.

## Следующий шаг

Пункт4 ADR-0051: общий field/guard audit и source/wheel/installed path+hash parity, все18magic schemas/36total/transitive refs, module/console/stdin и actual spawn, simulation/balance1/2/3 с независимыми null/opted policies, прежние6routes и saved v1/v2 parity. Обновить historical audit helper либо сделать текущий version-aware helper. Затем закрыть весь ADR только при выполненных критериях, не вводя gameplay/save-resume.

Изменения этапа оставлены незакоммиченными. Новые файлы:3schemas,3test modules, public request/result и этот audit; изменены balance boundary/service/source guards, CLI help, registry/version metadata, public probe/stdout и прежние version/counter tests. Общие docs обновляет главный агент. Commit/push выполняет пользователь.
