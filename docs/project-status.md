# Текущий статус проекта

Дата обновления: 2026-11-01.

## Текущий этап

**M8 / ADR-0051, пункт2: simulation JSON/CLI v3 реализован и проверен, этап закрыт.** [Контракт](decisions/ADR-0051-stationary-wound-generation-and-magic-json-v3.md), [simulation audit](audits/m8-simulation-v3-readiness.md), [request](examples/m8/json/magic-simulation-v3.request.json)/[result](examples/m8/json/magic-simulation-v3.result.json). Native generation пункт1 закрыт; balance3/общий installed audit ещё предстоят.

`simulate-magic` принимает1/2/3. V3 требует nullable stationary enum string и независимый nullable Miscast object. Полный source/definition order/seed и request echo/version сохраняются; lexical fallback1/null ID отличается от trusted decoded3. Service использует собственную command version/ID. Typed policies/facts проверяются до equality, в том числе int1 вместо True у transported source.

## Ограничения

- PG1.4/GM1.1 / ADR-0050 прежние: canonical first9 stand/context49, superficial1–3 и active/expired6, normal Tests, no external causes. Terrain/history сохраняются, Give Ground=False; новых игровых правил нет.
- None сохраняет legacy traces/stops. Повторная9 после stand, Wind Prone с retained terrain и прочие mandatory effects остаются stop; unsupported входит в denominator.
- Generation требует отдельный matching family opt-in. JSON1/2 явно отвергают stationary policy. Fresh-only wire не save/resume.
- Balance3 пока explicit unsupported/fallback1 до Schema loader; balance command/input/phase errors1/2. Шесть nonmagic routes — только1. Registry15magic/33total, default1; новый installed/console audit в пункте4.
- Известные33 expectations errors Python3.12 — отдельная задача; полный suite с ними не зелёный.

## Последняя проверка

Добавлены30tests:8schemas,13wire/service unit,9integration. Локальные срезы прошли: four combinations, полный round-trip без RNG, strict trust/fallback, actual parsed9/6 и seq/spawn, native/CLI parity, null/file/Unicode, old routes isolation. Native actual9→stand→Casting/end→incoming6→expiry48d10, None/Wound10 controls7 и denominator2.

Public v3 CLI request/result сохранены на CPython3.12.4; текущий CLI целиком совпадает с direct API. Public copied probe выполняет8actual simulation3 round-trips/8manual balance3 mappings,20native projections/4staged rows и8scripted trials/138d10.

Full run: **3956tests /34errors /0failures /0skipped,885,280с**, Windows/CPython3.12.4 вне sandbox; все30новых tests прошли.33exact ERROR headers совпали с baseline. Ещё1старый CLI negative-case ожидал unsupported3: исправлен на4, targeted rerun **1test OK/6,507с**. Production/probe/new tests после full run не менялись, полный suite после test-only исправления не повторялся. Нерешённых новых errors/failures нет; полного лога3956/33 не заявляется.

Logs: `.cache/adr0051-simulation-v3-regression.log` и `.cache/adr0051-simulation-v3-corrected-cli.log`. Saved v2 outputs, Markdown-пути и `git diff --check` проверены; installed audit пока не проводился.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

## Точный следующий шаг

Пункт3 ADR-0051 целиком: balance3 —3schemas, independent required nullable reserve/family stationary assertions и Miscast object, exact typed equality до generation, command/input/phase errors/reader3, full generation→staged→report source, parser/service/encoder/CLI и actual sequential/process. Version3 input/output/error едины;1/2 lossless guards сохраняются.

После balance3 — пункт4 installed/schema/local refs/module/console/spawn и full audit. Не вводить новые gameplay consumers/save-resume и не удалять policy ради старого codec.

Изменения этапа не закоммичены: simulation boundary/strict reader/mapper/service/version metadata,3schemas,3newtest modules, public JSON/probe и сопутствующие docs; старые unsupported simulation version tests переведены с3 на4. Commit/push выполняет пользователь.
