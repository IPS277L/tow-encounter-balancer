# Текущий статус проекта

Дата обновления: 2026-11-03.

## Текущий этап

**ADR-0058 закрыт в согласованной границе.** Crushed Rib generation family и обе Magic JSON5 families реализованы. Simulation и balance CLI сохраняют полный typed source/result/error echo; balance отдельно проверяет matching Crushed Rib policy в reserve и generation до enumeration. [ADR](decisions/ADR-0058-crushed-rib-generation-and-magic-json-v5.md), [итоговый аудит](audits/m8-crushed-rib-transport-readiness.md), [public requests](examples/m8/json/README.md).

## Последняя проверка

Полная регрессия: **4223 tests, 33 errors, 0 failures, 0 skipped**. Ровно 33 прежних Python 3.12 expectation errors: 32 subcase errors при assignment в frozen/slotted `.state` и один M5 `dataclasses.replace(init=False simulation_requests)` expectation. Новых errors/failures нет; набор не объявляется полностью зелёным. Исправленный ADR-0054 transport probe с unknown v6 прошёл.

Свежий offline wheel установлен в отдельный venv. Source/wheel/installed parity: **484 Python/Schema files**. Schema closure: **48 schemas / 30 Magic / 507 local refs**. Обе v5 CLI проверены sequential и process через source, `python -I -m towr` и installed console script: **12 точных сравнений**, полный request echo сохранён. `pip check` прошёл. Markdown link check: 189 files, 4615 local links, 0 missing.

Проверенная команда полного набора:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

## Ограничения

Crushed Rib transport разрешает только `NEXT_TEST_WITH_JOURNAL_WITNESSES` и несёт только fresh source permission. Native ограничение прежнее: одна canonical resolved/untreated/unhealed rolled10, optional prior superficial1–3, только Drained. Coexistence с9/6/Wind, лечение/Fate/Lucky/Talents, current owner/journal/history, receipts и save/resume не открыты. Книги и gameplay scope ADR-0057 не менялись.

## Точный следующий шаг

ADR-0058 завершён; новых открытых вопросов по этому срезу нет. Перед новой feature-вехой выбрать следующий пункт roadmap с учётом текущего приоритета и подтвердить правила-источники для него. Первые ориентиры — актуальные [open questions](open-questions.md) и [roadmap](roadmap.md).

Изменения остаются незакоммиченными. Commit/push выполняет пользователь; книги и `.gitignore` не менялись.
