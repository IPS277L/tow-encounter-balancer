# M8: balance JSON v2 — ADR-0047 этап3

Дата: 2026-10-31. Сквозной balance v2 transport реализован и проверен; общий installed audit остаётся этапом4. [Контракт](../decisions/ADR-0047-opt-in-generation-and-magic-json-v2.md), [предыдущий simulation-срез](m8-simulation-v2-readiness.md), [актуальный статус](../project-status.md).

Это перенос ранее утверждённой policy ADR-0046, не новая механика. Domain/engine/rules/simulation/balance и seed schemes не менялись; книги заново не читались, Rule IDs/house rules не добавлялись. Рабочая копия перед задачей была чистой, HEAD `39792f6 M8 P17`. Commit/push выполняет пользователь.

## Реализация и guards

| Граница | Реализация / проверенный контракт |
| --- | --- |
| Command | Append-last `MagicBalanceCommand.schema_version='1'`: closed string1/2, positional/frozen/slots/current pickle сохранены; native opted command с default1 допускается, encoder отказывает |
| Policy | Required nullable `reserve.scenario.miscast_continuation` и `generation.miscast_continuation`. Оба читаются независимо; shared narrow mapper создаёт полные typed values. Нет default/inference/копирования reserve policy в family |
| Equality | Полное равенство policy проверяется до generation preflight; mismatch pointer `/generation/miscast_continuation`. Shape/enum/fact errors указывают свой reserve/family path; при required/unknown keys pointer — containing object |
| Schemas/registry | Три новые balance-v2 schemas, local refs на simulation-v2 scenario/policy и неизменные v1 fragments. Cache family/kind/version12. Все12 registries компилируются; публичный validator default1, explicit keyword-only2 |
| Strict decode | Existing magic-only reader. До complete lexical decode error1/requestIDnull; после распознанной2 shape/admission errors2. Unknown string version — fallback1/unsupported_version; missing/wrong type — fallback1/invalid_input |
| Source/result | Полная command→generation→staged source chain и все candidates/reports сохраняют policy. Reconstruct-check включает version/definition order. Каталог/rates/counters/unsupported denominator прежние; нет policy stripping или временного v1 source |
| Service | Обе phase errors получают keyword-only version default1; service выставляет собственную command version, не version чужого cause. Candidate/counts либо stage/candidate принадлежат active phase; generic causes не создают вымышленный context |
| Error encoder | Временный отказ metadata2 заменён полным versioned encoding. Generic safe messages/context/null slots прежние; cause/notes остаются Python-only, partial reports/retry/fallback не добавлены |
| CLI | Прежний `balance-magic INPUT` принимает1/2; help обновлён. Encode-before-output и exit0/2/3/4 прежние. Simulation v2 не изменил semantics; шесть nonmagic routes по-прежнемуv1 |
| Compatibility | Все шесть magic v1 schemas неизменны; policy field запрещён даже null. V2null сохраняет полный legacy native result и seeds, но echo/envelopes остаются2 |

Admission резерва не гарантирует допустимость каждого subset: actual поздний invalid projection даёт generation_failed без пропуска кандидата и без partial family. Удалённые reserve actors отсутствуют в generated scenario, а не становятся внешними Short-range creatures. Assertions остаются ответственностью caller.

## Evidence

- [18 unit tests](../../tests/unit/test_m8_magic_balance_json_v2.py): exhaustive required/unknown request/result/error objects; оба nullable policy objects и пять strictTrue facts/enum/types/paths; mismatch before projection; semantic errors и Zone geometry; complete-decode version table; schemas/default validator; appended/frozen/pickle metadata; same-ID policy substitution в каждом candidate и обеих source directions; command reconstruction/version/order; own-version error wrapping и known phase context; реальная поздняя generation failure; no RNG/generator/process/fake simulation envelope при parsing/encoding.
- [6 integration tests](../../tests/integration/test_m8_magic_balance_json_v2.py): actual sequential/process full generation/staged results для null/opted, exact source на каждом report row, v1null native equality; CLI Unicode/stdin оба backend/policy; public input file; lexical fallback vs semantic2; поздний real subset failure с counts; process failure с stage/candidate без private/partial output. Inputs/global RNG/active children сохраняются.
- [Public proof](../examples/m8/opt_in_transport_contract_probe.py) теперь вызывает оба public v2 parser/service/encoder: null/full policy, отдельные assertions, full echo/candidates. Temporary legacy views/manual inverse удалены. V1 refusal и missing family opt-in guards сохранены. [Copied-bundle test](../../tests/integration/test_m8_opt_in_transport_contract_probe.py) проверяет [сохранённый stdout](../examples/m8/opt_in_transport_contract_probe.output.txt).
- [Public v2 input](../examples/m8/json/magic-balance.request.json), [инструкция](../examples/m8/json/README.md): прежний authored резерв C4/stages2/4/upper16 с двумя explicit policy objects. Это конечное наблюдение standard RNG, не difficulty preset или вероятность.
- Прежние balance tests unsupported-version2 переведены на3, поскольку2 реализован. Interim simulation test «balance error2 refused» теперь требует exact error2. Из isolation test удалён только balance route; шесть nonmagic остаются negative2. V1 rejection/unknown/source tests сохранены.

Focused commands, Windows x64/CPython3.12.4:

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m unittest tests.unit.test_m8_magic_balance_json tests.unit.test_m8_magic_balance_service tests.unit.test_m8_magic_balance_cli tests.unit.test_m8_magic_json_v2 -q
.venv/Scripts/python.exe -m unittest tests.unit.test_m8_magic_balance_json_v2 -v
.venv/Scripts/python.exe -m unittest tests.integration.test_m8_magic_balance_json_v2 -v
.venv/Scripts/python.exe -m unittest tests.integration.test_m8_opt_in_transport_contract_probe -q
```

78 adjacent unit — OK/17,767с. 18 new unit — OK/14,533с; после уточнения fixture geometry соответствующий метод повторно OK/0,393с. 6 integration — OK/46,373с вне sandbox; copied public proof — OK/2,873с вне sandbox. Independent schema/reader/service review блокеров не выявил; узкая проверка всех12 local registries, null/opted synthetic result и wrong-version echo прошла. Installed wheel пока не проверялся.

Полная регрессия: **3796tests/33 известных errors/0failures/0skipped,766,473с**, Windows x64/CPython3.12.4, вне sandbox. Команда `$env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest discover -s tests -v`; log `.cache/adr0047-balance-v2-regression.log`. Все24новых tests прошли. Sorted33error headers побуквенно совпали с baseline этапа2 `.cache/adr0047-simulation-v2-regression.log` (3772tests):16+16 K1 Aim-loss frozen/slotted TypeError и один M5 replace(init=False) ValueError. Новых ошибок нет; набор с errors не считается зелёным, исправление expectations остаётся отдельной задачей.

1199 local Markdown paths в13актуальных документах — OK; `git diff --check` — OK. Read-only Git comparison подтвердил неизменность всех magic v1 schemas. Исходники/тесты не менялись во время полной регрессии; после неё обновлена только документация результата. Новый wheel/installed audit здесь не заявляется.

## Следующий шаг и ограничения

Последующее завершение: этап4 выполнен в [общем installed-аудите ADR-0047](m8-opt-in-transport-readiness.md). Ниже сохранён следующий шаг на момент окончания этапа3, а не текущая очередь работ.

**Этап4 ADR-0047: общий аудит.** Полная field/guard matrix, свежий wheel/offline install и exact source/wheel/installed parity; все12 magic schemas/local refs; public stored v2 simulation/balance outputs и copied examples; installed module/console для обеих magic и шести прежних CLI routes; dependency/runtime context и полная регрессия с отдельным учётом известных Python assertions. Current source-only checks не заменяют installed evidence; весь ADR пока не закрыт.

Gameplay остаётся прежним: fresh-only input, Wind21–22 и scoped Prone; другие Miscast effects, desperate cast/abandonment, ongoing Prone Wounds/unsafe Broken/Run-after-spent-free-move и неизвестные facts не достраиваются. Unsupported trials остаются в denominator; window eligibility не доказывает полноту тактики. Performance/cross-platform claims нет.
