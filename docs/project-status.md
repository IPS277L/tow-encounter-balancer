# Текущий статус проекта

Дата обновления: 2026-11-01.

## Текущий этап

**M8 / ADR-0051 закрыт в принятой границе.** [Контракт](decisions/ADR-0051-stationary-wound-generation-and-magic-json-v3.md), [итоговый audit](audits/m8-stationary-wound-transport-readiness.md), [public JSON](examples/m8/json/README.md). Native generation и обе magic JSON/CLI families1/2/3 проверены в source/wheel/installed/module/console/spawn.

Independent nullable stationary/Miscast permissions и matching reserve/family assertions сохраняются. Full generation→staged→report→assessment→summary sources и original derived cache проверяются до equality. Audit нашёл/исправил detached candidate facts int1=True gap public generation-result;1newregression + installed negative прошли, facts не нормализуются.

## Ограничения

- PG1.4/GM1.1 / ADR-0050 прежние: canonical first9 stand/context49, superficial1–3 и active/expired6, normal Tests, no external causes; terrain/history сохраняются, Give Ground=False.
- None сохраняет legacy; repeated9/Wind-Prone с terrain/прочие неподдержанные обязательные effects остаются stop и входят в denominator. Новых gameplay/house rules нет.
- JSON3 fresh-only, не save/resume.1/2 stationary field запрещён даже null.6nonmagic routes — только1. Registry18magic/36total, default1.
- 33 прежние expectations errors Python3.12 — отдельная задача; полный suite с ними не зелёный.

## Последняя проверка

Windows/CPython3.12.4 вне sandbox: **3987tests /33known errors /0failures /0skipped,906,227с**.20generation tests, включая новый detached-facts regression, прошли; все33 exact ERROR headers совпали с предыдущим baseline. Log `.cache/adr0051-final-audit-regression.log`.

Финальный wheel `.cache/adr0051-final-installed-audit/wheels/towr_encounter_balancer-0.1.0-py3-none-any.whl`, SHA256 `9ba0b5433efcb3f99bd8e5a098236a5cfaf358231781023b8231aa6edd388b35`.465package .py/.json source/wheel/installed paths+hashes совпали,36schemas/383local refs/18magic разрешены.269transport childcommands/28backendcases/3copiedexamples прошли; отдельно installed native220d10/actual9→6expiry иseq/spawn fullrecordparity.

Current source/module/console stdout exact. Saved v2/v3 bytes совпали на одинаковом runtime; v1 snapshots3.12.15 отличаются от3.12.4, все non-runtime JSON fields совпали в finite сравнении, raw bytes не объявляются равными. Source/fixture manifests после full suite неизменны. Evidence в final-installed-audit/transport/evidence.json, native/evidence.json и candidate-facts-guard.log.

Первичная `.cache/adr0051-installed-audit` сборка ДО facts fix не используется. Production/tests/helpers/probes после финальных проверок не менялись; Markdown-пути (без anchors) и git diff --check проверены.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

## Точный следующий шаг

[Continuation inventory](audits/m8-continuation-inventory.md) технически актуализирован по13labels/runner/diagnosis и закрытому transport. Сравнить минимальные оставшиеся scopes (Wound10/repeated9/Wind-Prone), выбрать один следующий source-bound consumer и подготовить ADR-0052 + finite proof с адресной книжной сверкой. Новое поведение до этого не реализовать; конкретный следующий consumer пока не назначен.

Изменения пункта4: audit helper, narrow facts guard,1regression и docs; предшествующие незакоммиченные изменения пункта3 сохранены. Commit/push выполняет пользователь.
