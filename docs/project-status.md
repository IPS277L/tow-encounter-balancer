# Текущий статус проекта

Дата обновления: 2026-11-03.

## Текущий этап

**Контракт ADR-0061 подготовлен; native реализация ещё не начата.** Он задаёт отдельное разрешение с authored Wizard Endurance profile, exact recorded completion и диагностику нового injury вне scope60. [Контракт](decisions/ADR-0061-native-battered-leg-continuation.md), [actual39d10 probe](examples/m8/battered_leg_native_contract_probe.py).

Ручной full-owner bridge [ADR-0060](decisions/ADR-0060-battered-leg-owner-bridge.md) закрыт; его [приёмка](audits/m8-battered-leg-owner-readiness.md) остаётся базой. Production domain/engine/adapters и schemas на шаге подготовки61 не менялись.

## Последняя проверка

Подготовка61: **77 tests, OK** — новый copied public probe и76 existing owner/Scenario/Result checks. Probe прошёл source и copied installed `python -I` execution;39scripted d10, sources/global RNG неизменны. Независимое read-only ревью проверило actor/source/history, scope mismatch и death boundary.

Последний полный regression — после0060: **4254 tests, OK**, 0 errors/failures/skips, Windows x64/Python3.12.4,1791.097s. Лог `.adr60-full.log`. Полный набор с новым probe не запускался; повторный full/новый wheel audit предусмотрены при реализации native61.

Повторная сверка прежнего offline wheel60: **488 Python/JSON files** source/wheel/installed совпали по путям/SHA-256. Markdown file links:193files/4672links/0missing; `git diff --check` OK. Свежий wheel для документационного шага не собирался; последний pip check — OK из аудита60.

Проверенные команды текущего шага:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest tests.unit.test_m8_battered_leg_owner tests.integration.test_m8_battered_leg_owner tests.unit.test_m8_npc_magic_scenario tests.unit.test_m8_npc_magic_scenario_result tests.integration.test_m8_npc_magic_scenario_result -v
.venv/Scripts/python.exe -m unittest tests.integration.test_m8_battered_leg_native_contract_probe -v
```

## Ограничения

Первая rolled5 от ordinary wounding enemy Attack, resolved/untreated/unhealed; normal Test без modifiers, explicit unmounted/no-external-Conditions facts. Сейчас Endurance profile предоставляет manual caller; native Step union всё ещё отвергает completion60. Failure сохраняет sourced Prone без removal consumer. После success новое actual Staggered/Wound сохраняется, но выходит за exact-injury scope60: существующий native diagnosis может вернуть None, затем normal factory отказывает.61 должен диагностировать эту ветвь до factory, сохранив mandatory tails/receipt. Native permission/runner/journal и generation/wire пока не реализованы.

## Точный следующий шаг

Реализовать этап1 ADR-0061: append-last `battered_leg_continuation` с authored InlineProfile, shared admission, bounded history, completion60 в Step union и exact predecessor/journal/None guards. Затем самостоятельно пройти runner/diagnosis → native integrations/refusals → полный аудит по roadmap. Профиль не выводить из Casting; Test actor — Wizard при активном Minion turn. Prone5 removal и generation/wire — отдельные этапы.

Изменения остаются незакоммиченными. Commit/push выполняет пользователь; книги и `.gitignore` не менялись.
