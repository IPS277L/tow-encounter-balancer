# Текущий статус проекта

Дата обновления: 2026-11-03.

## Текущий этап

**ADR-0059 закрыт в K1 границе.** Одна canonical rolled5 связывается с полным WoundEffect witness и caller-authored normal Endurance Test. Failure добавляет sourced Prone; success сохраняет injury. [Контракт](decisions/ADR-0059-battered-leg-endurance-test.md), [приёмка](audits/k1-battered-leg-readiness.md), [трассировка](rule-traceability.md).

## Последняя проверка

Полная регрессия после ADR-0059: **4239 tests, OK**, 0 errors/failures/skips, Windows x64 / Python 3.12.4, **1120.898 s**. Целевые source-проверки: **26 tests, OK**. Ревью закрыло Conditions admission, stale healed Wound, mounted context и Test trace substitution.

Свежий offline wheel ADR-0059: **486 Python/JSON files** source/wheel/installed совпали по путям/SHA-256, `pip check` OK, public exports доступны из site-packages. Copied targeted bundle через installed `python -I`: **26 tests, OK**. Schemas не менялись. [Аудит ADR-0059](audits/k1-battered-leg-readiness.md).

После full run package hashes прежние; пути Markdown-ссылок: 190 files / 4633 links / 0 missing. `git diff --check` OK.

Проверенная команда полного набора:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

## Ограничения

ADR-0059 допускает только первую resolved/untreated/unhealed rolled5, без Conditions/active effects; explicit `unmounted=True`; Test без modifiers/reroll locks. Caller отвечает за actor/profile authority и chronology. M8 full-owner/journal, replay application, другие сочетания, mounts и transport требуют следующих контрактов.

## Точный следующий шаг

Подготовить отдельный ADR для ручного M8 full-owner перехода Battered Leg: authored Wizard Endurance profile, exact current owner/pending Wound5, одно выполнение Test и применение injury delta с сохранением истории. После этого — native runner/journal, затем generation/wire. Numeric profile не выводится автоматически. [Основание и текущая граница](decisions/ADR-0059-battered-leg-endurance-test.md).

Изменения остаются незакоммиченными. Commit/push выполняет пользователь; книги и `.gitignore` не менялись.
