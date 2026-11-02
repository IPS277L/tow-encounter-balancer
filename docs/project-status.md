# Текущий статус проекта

Дата обновления: 2026-11-02.

## Текущий этап

**ADR-0056 закрыт: ручной typed Crushed Rib bridge для полного M8 owner реализован и проверен.** [Контракт](decisions/ADR-0056-source-bound-crushed-rib-owner-bridge.md), [приёмка](audits/m8-crushed-rib-owner-readiness.md), [actual63d10](examples/m8/crushed_rib_owner.py), [roadmap](roadmap.md).

Ручной typed M8 bridge связывает actual Protection/Casting с полным owner и первым consuming witness. Protection расходует NEXT_TEST до Stagger/Wound consequences; Casting — до pool/follow-ups. Drained сохраняется, последующие normal Tests используют первый witness без нового completion. Новые раны регистрируются полностью, затем ограничивают context. Wizard action/end-turn gap для stripped10 и missing-context Result/apply закрыт; original aliases отклоняются до RNG. Source compatibility не объявляется journal membership.

## Последняя проверка

**62 targeted tests OK/4,031с**, CPython3.12.4, outside-sandbox runner.39new unit,7actual integration,2copied56 и14old end-turn. Installed audit прошёл:477source/wheel/site package paths+SHA,2exports,42schemas/444refs,8child commands; actual owner63/historical25/K1actual33/K1historical40d10. Evidence `.cache/adr0056-installed-audit/checks/evidence.json`.

**Составное4158покрытие:551integration OK; все3607unit повторены после исправления устаревшего message assertion —33known errors/0failures/0skipped,105,099с.** Full4158/1059,911с до этого fixture fix имел33known errors и1failure; единый full run без failures не заявляется. Production/integration/examples после него не менялись.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m unittest discover -s tests/unit -v
```

Exact sorted33ERROR headers full run совпали с baseline55; отдельный unit loader отличается только package prefix. Evidence `.cache/adr0056-regression-comparison.json`, logs `adr0056-full-regression.log`/`adr0056-final-unit-regression.log`.33старых Python3.12 expectation errors — отдельная задача; весь набор не объявляется зелёным. После suite477package hashes совпали с installed evidence, все97example files прежние. Проверены1786local Markdown paths/17документов, broken paths0 (без anchors), diff/whitespace чистые.

## Ограничения

Одна canonical resolved/untreated/unhealed rolled10, optional prior superficial1–3, только Drained. Несколько10,9/6/Wind, treatment/healing/Fate/Lucky/Talent proofs исключены. Authoritative caller предоставляет настоящий current owner; произвольная достижимость/глобальный журнал не доказываются. Automatic dispatcher/runner/policy/mass/generation/JSON1–4 и schemas не расширены; automatic Wound10 сохраняет прежние stops. Новых house rules нет.

## Точный следующий шаг

Подготовить ADR-0057 для native Crushed Rib dispatcher/journal/permission: вывести pending/consumed context из собственного actual prefix, установить порядок Protection/Casting и mandatory follow-ups, сохранить прежние stops/RNG/denominator controls. Начать с diagnosis/step/source admission и конечного публичного proof. Generation/JSON/wire5 не подключать до отдельного контракта.

60незакоммиченных файлов, включая31предшествующий: реализация, deterministic tests, actual example, installed audit и общие документы. Commit/push, `.gitignore` и книги не менялись.
