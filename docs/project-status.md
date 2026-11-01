# Текущий статус проекта

Дата обновления: 2026-11-01.

## Текущий этап

**M8 / ADR-0051, пункт1: native generation реализован и проверен, этап закрыт.** [Контракт](decisions/ADR-0051-stationary-wound-generation-and-magic-json-v3.md), [аудит этапа](audits/m8-stationary-wound-generation-readiness.md), [public probe](examples/m8/stationary_wound_transport_contract_probe.py)/[stdout](examples/m8/stationary_wound_transport_contract_probe.output.txt). Пункты2–4 ещё предстоят.

Append-last nullable stationary family assertion независима от Miscast. Typed template/family проверяются до enumeration; factory/result повторяют pure source admission без normalization. Facts/groups/stages/window проверяются собственными constructors. Каждый subset получает обе family policies; candidate types проверяются до exact expected projection. Полные source/seed/ID/budget и generation→staged→report сохраняются.

## Ограничения

- Scope прежний PG1.4/GM1.1 / ADR-0050: canonical first9 stand/context49, superficial1–3 и active/expired6, normal Tests, no external causes. Terrain/history сохраняются, Give Ground=False.
- None сохраняет legacy traces/stops. Повторная9 после stand, Wind Prone с retained terrain и прочие mandatory effects остаются stop. Miscast и stationary permissions независимы.
- Native generation требует matching family permission; JSON1/2 явно отвергают stationary source. JSON3/schema/CLI ещё нет; fresh-only формат не save/resume.
- Unsupported остаётся в denominator. Известные33 errors expectations Python3.12 — отдельная задача, полный suite с ними не зелёный.

## Последняя проверка

Windows/CPython3.12.4 вне sandbox: **3926tests /33known errors /0failures /0skipped,787,439с**. Все33 exact ERROR headers совпали с baseline, все24новых tests прошли; новых errors/failures нет. Log `.cache/adr0051-generation-regression.log`.

19new unit/5integration проверяют generated3/4actor actual9→stand→Casting/end→incoming6→expiry48/66scripted d10 и None9/Wound10 controls7. Four policy combinations, staged seq/spawn/full reruns/seed prefix/source/denominator и обе perspectives проверены. Прежние60generation/policy unit и обновлённый copied public bundle также прошли.

Public probe:20actual generator projections/16finite wire mappings/4staged rows;8scripted trials/138d10. Wire3 mapping остаётся ручным. Actual native balance result с policy явно отвергнут JSON1/2 без encoding RNG.

После полной проверки production/tests/probe не менялись. Saved v2 outputs, Markdown-пути и `git diff --check` проверены. Installed v3 audit запланирован в пункте4, новая wire версия ещё не реализована.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

## Точный следующий шаг

Пункт2 ADR-0051 целиком: simulation v3 — три packaged schemas/local registry, command/errors, magic-only family version selection, shared mapper, parser/service/result+error encoder/CLI и actual sequential/process. Required nullable stationary enum string и независимый Miscast object, full source/error version и v1/v2 lossless guards.

Balance3 до пункта3 explicit unsupported: не загружать отсутствующую Schema и не доверять3 раньше полной lexical decode/поддержки конкретной family. Затем balance3 → общий installed/schema/CLI/spawn/full audit. Не вводить новые gameplay consumers или save/resume.

Изменения текущего этапа не закоммичены. Добавлены audit и19unit/5integration tests; изменены два application файла, public probe/stdout, два прежних unit файла для positional/guard semantics и сопутствующие docs. Commit/push выполняет пользователь.
