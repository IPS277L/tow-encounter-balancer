# M8: simulation JSON v2 — ADR-0047 этап2

Дата: 2026-10-31. Реализован сквозной simulation v2 transport; balance v2 и общий installed audit ещё не выполнены. [Контракт](../decisions/ADR-0047-opt-in-generation-and-magic-json-v2.md), [предыдущий generation-срез](m8-opt-in-generation-readiness.md), [актуальный статус](../project-status.md).

Это архитектурный transport ранее утверждённой policy ADR-0046, не новое игровое правило. Domain/engine/rules/simulation, seed scheme и native aggregates в этом срезе не менялись. Книги заново не читались, Rule IDs/house rules не добавлялись. Ниже указаны проверки именно этапа2; исторический installed audit ADR-0046 не считается проверкой текущей сборки.

## Реализация и guards

| Граница | Реализация и проверяемое свойство |
| --- | --- |
| Command | `MagicSimulationCommand.schema_version='1'` добавлен последним; frozen/slots/positional compatibility, closed string1/2, pickle current objects. Domain request не содержит wire version |
| Input errors | `MagicInputError` принимает keyword-only version default1. Доверенная версия/ID устанавливаются только после полного strict decode; nested mapper/constructor/seed errors сохраняют эту metadata |
| Lexical reader | `_json_common.read_request(..., magic_v2=True)` разрешён только magic error family; default всех прежних callers — v1. Float/exponent, duplicate, nonfinite, UTF-8/JSON/surrogate failures происходят до metadata extraction |
| Schemas | Три новые `magic-simulation-*-v2.schema.json`, URNs оканчиваются `:2`. Required nullable policy с тремя exact fields, facts — пять strictTrue booleans. Local refs на неизменные v1 fragments; remote retrieval отсутствует |
| Registry | Cache key family/kind/version, default validator v1. Explicit keyword-only `schema_version='2'`; unsupported API version — ValueError. Balance validator пока отвергает2 |
| Scenario | `parse_scenario`/`scenario_document` принимают keyword-only version default1. Typed policy передаётся в полный final admission. В том числе противоречивая cross-Zone Close geometry не проходит. Нет inference/default facts |
| Result | Summary full source equality; полный command reconstruct-check включает policy/version/definition order. V2null не превращается в v1; complete policy сохраняется в echo. Нет очистки policy для обхода guard |
| Service/error | Service запускает прежний explicit backend; runtime failure получает версию своего command независимо от cause. Error encoder сохраняет safe message/path/request ID, не раскрывает cause/notes |
| CLI | Прежний `simulate-magic INPUT` принимает1/2, help обновлён. Семь других routes пока принимают только1. Exit0/2/3/4, encode-before-output и отсутствие fallback/retry прежние |
| Balance interim | Shared input error допускает metadata2, но balance encoder явно отвергает такой native error до этапа3, не выводит misleading v1. Parser/command/runtime balance остаются v1 |
| Compatibility | Старые шесть magic schemas не изменены. V1 запрещает policy field даже null, native opted source нельзя вывести v1. V2null сохраняет полный legacy request/records/seed/summary при той же execution |

Для required/unknown errors JSON pointer указывает содержащий object; неверное значение choice/prone/fact — exact field. При полном lexical decode неизвестная string version даёт fallback1/unsupported_version по `/schema_version`, wrong type/missing — fallback1/invalid_input. У valid supported2 дальнейшая shape/admission failure —2, даже если kind неверен. До полного lexical decode request ID всегда null.

## Проверки

- [18 новых unit tests](../../tests/unit/test_m8_magic_json_v2.py): exhaustive required/unknown objects request/result/error; null/full policy; все false/type/enum facts и pointers; lexical metadata table; default/unknown validators; frozen/positional/pickle; pure parsing/encoding; same-ID None/opted substitution; full reconstruction/version/order; bothbackend/runner+summary error phases с чужой cause version; balance no-downgrade.
- [6 новых integration tests](../../tests/integration/test_m8_magic_json_v2.py): реальные full native sequential/process records при null/opted; legacy parity; CLI Unicode/stdin и оба backend; публичный request file против native; input/error table; safe process-pool failure; все семь прежних routes отвергают2. Global RNG/inputs/active children сохраняются.
- Existing unsupported-version tests simulation заменены с2 на3, поскольку2 теперь поддержан. V1 negative/shape/source tests сохранены, не ослаблены.
- [Public proof](../examples/m8/opt_in_transport_contract_probe.py) больше не имитирует simulation v2: настоящий parser/runner/encoder для null/opted, full echo и scripted Wind-summary round-trip. Только balance portion остаётся finite manual mapping. [Copied-bundle test](../../tests/integration/test_m8_opt_in_transport_contract_probe.py) проверяет [точный stdout](../examples/m8/opt_in_transport_contract_probe.output.txt).
- [Публичный JSON-вход](../examples/m8/json/magic-simulation-v2.request.json), [инструкция](../examples/m8/json/README.md): explicit policy, стандартный seed42/trials4/round budget4. Future scene coverage неполная; это finite observation, не вероятность/пресет сложности.

Focused evidence, Windows x64 / CPython3.12.4:

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m unittest tests.unit.test_m8_magic_json tests.unit.test_m8_magic_balance_json tests.unit.test_m8_magic_simulation_service tests.unit.test_m8_magic_cli -q
.venv/Scripts/python.exe -m unittest tests.unit.test_m8_magic_json_v2 -v
.venv/Scripts/python.exe -m unittest tests.integration.test_m8_magic_json_v2 -v
.venv/Scripts/python.exe -m unittest tests.integration.test_m8_opt_in_transport_contract_probe -q
```

85 existing adjacent tests — OK/19,455с. Новые unit: первоначальные17 — OK/6,931с, после последней правки3 изменённых/новых метода — OK/0,911с; итоговый файл содержит18tests. Все6 integration — OK/31,844с; copied public proof1 — OK/2,000с. Sandbox block Windows Pipe/temporary-directory access воспроизведён; соответствующие integration/proof tests повторены вне sandbox успешно. Эти инфраструктурные попытки не включены в clean focused counts.

Independent review mapper/Schema и основного reader/parser/service выявило два исправленных edge cases: interim balance native-error downgrade и outdated CLI help. После исправления блокеров не осталось.

Полная регрессия текущего среза: **3772tests/33 известных errors/0failures/0skipped,651,243с**, Windows x64/CPython3.12.4, вне sandbox. Команда: `$env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest discover -s tests -v`; log `.cache/adr0047-simulation-v2-regression.log`. Все24новых tests прошли. Sorted33error headers побуквенно совпали с baseline этапа1 `.cache/adr0047-generation-regression.log` (3748tests):16+16 K1 Aim-loss frozen/slotted TypeError и1M5 replace(init=False) ValueError. Новых errors/failures нет; suite с errors не называется зелёным. Исправление известных expectations для поддерживаемого Python остаётся отдельной задачей.

1172 local Markdown paths в12актуальных документах — OK; `git diff --check` — OK. Read-only Git comparison подтверждает неизменность всех magic v1 schemas. Исходные файлы/тесты не менялись во время полной регрессии; после неё обновлена только документация результата.

## Оставшиеся границы и следующий шаг

Simulation transport не закрывает other Miscast rows, desperate cast/abandonment, unsafe Broken/ongoing Prone Wounds, unknown scene facts либо сохранение/возобновление боя. Fresh-only policy admission и unsupported denominator прежние. Nullable policy не выводится из `CAST_WHEN_READY`/facts.

**Следующий шаг — этап3 balance v2 целиком:** ещё три packaged schemas, versioned command/phase errors, reserve + separate family nullable policy с exact equality, полный generation/staged source chain, parser/result/error encoders/service/CLI, contexts candidate/counts/stage, real sequential/process и v1null parity. Затем этап4 — все12magic schemas/local refs, public stored results, source/wheel/installed parity, восемь routes и общий full audit. Текущий этап2 не заявляет installed readiness или завершение всего ADR-0047.

Commit/push не выполнялись. Существующие пользовательские изменения и предыдущие M8-срезы сохранены.
