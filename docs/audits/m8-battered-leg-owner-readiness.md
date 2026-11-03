# M8 Battered Leg full-owner bridge: ADR-0060

Дата: 2026-11-03. **ADR-0060 закрыт в указанной ручной M8 границе.**

## Контракт и источники

[ADR-0060](../decisions/ADR-0060-battered-leg-owner-bridge.md) связывает полный post-Attack owner и его единственный pending Wound5 с authored normal Endurance InlineProfile. Используется прежний K1 consumer59, explicit unmounted/no-external-Conditions facts; success сохраняет injury, failure добавляет sourced Prone. Test не расходует отдельный action slot.

PG1.4 Characteristics & Skills68–70, Wounds121, Prone123, Wounds Table190/5; GM1.1 Champions92. Повторно проверены локальные extracted123/190/GM92; новый PDF/hash/Rule ID/house rule не вводится.

## Подтверждённое поведение

- Actual bound enemy Attack → Wound roll5 → accepted lifecycle/daily registration → одно59 Endurance execution.
- Root/champion/minion roster синхронны; combat/spatial/magic, action/daily/roll ledgers сохранены.
- Bounded receipt содержит исходный bound Attack и K1 completion без собственного projected state; рекурсия ограничена source с receipt=None.
- Receipt storage сохраняет actor/profile/scene/day anchors и ordered history prefixes. Удаление Minion child, его ledgers и end-turn histories не допускается.
- Success → actual normal Casting сохраняет witness. Failure сохраняет Wound-sourced Prone и не проходит неподдержанный normal Casting consumer.
- Повторное apply, stale current source, mismatched profile, corrupt Attack trace и raw facts отклоняются. Stripped pending/receipt не разрешают Casting/Attack/scheduling/end-turn.
- Wizard может уже завершить свой ход: это immediate Wound Test, не его новая action.

Current root остаётся storage для unsupported состояний; witness доказывает локальную согласованность источника, а не произвольную journal reachability. Native runner/permission/Step union и JSON1–5 не расширялись. Весь profile — manual caller input.

## Проверки

Source targeted: **129 tests, OK** —15новых unit/integration и114существующих affected tests. Независимое ревью повторно проверило fixes и ограниченную receipt recursion.

Fresh offline wheel/installed venv: **488 Python/JSON paths + SHA-256 совпали**; new modules/public exports и append-last receipt доступны в installed package. `pip check` OK. Copied15new tests через installed Python `-I`: **15 tests, OK**. Wheel SHA-256: `528913150b72fe6b3b76e82dfde019bb78505f74a8463d3c13e519dd78604653`. Private PDF/references в wheel отсутствуют.

Полная регрессия:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Полный набор: **4254 tests, OK**, 0 errors/failures/skips, Windows x64/Python3.12.4, **1791.097s**. Следующий этап — native permission/profile/journal contract с сохранением default None stop; Prone5 removal и generation/wire требуют следующих отдельных границ.

После full run source/wheel/installed488paths/hashes прежние. Проверка путей локальных Markdown-ссылок:192files/4645links/0missing. `git diff --check` OK. Изменения оставлены для пользовательского commit/push; исходные книги и `.gitignore` не менялись.
