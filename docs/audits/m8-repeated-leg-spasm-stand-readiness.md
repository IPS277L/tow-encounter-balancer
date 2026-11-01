# M8: аудит повторного Leg Spasm stand, ADR-0052

Дата: 2026-11-01. **ADR-0052 закрыт в принятой low-level границе.** [Контракт](../decisions/ADR-0052-source-bound-repeated-leg-spasm-stand.md), consumer, адресные/public/installed проверки и полная регрессия завершены. Это не расширение automatic runner/policy/wire.

## Реализованная граница

[Frozen request/result](../../src/towr/domain/npc_roster_repeated_leg_spasm_models.py), [executor/apply](../../src/towr/rules/npc_roster_repeated_leg_spasm_resolution.py). Только новые модули; прежние48/49 validators и runtime dispatch не изменены.

Request сохраняет полный current owner, предыдущий stand48 и outer bound Champion Attack с одной новой rolled9. Pure admission проверяет обоих свидетелей, canonical old/new causes, actor/definitions/caster/spatial anchors, exact daily/consumed Wound roll histories и execution prefixes. Новая атака добавляет собственную Wound/daily/roll регистрацию. Current owner должен точно соответствовать end-attacker/start-Wizard в том же новом round, без иных intervening transitions; эта scheduler delta проверяется существующими чистыми domain-моделями, без reducers/RNG.

Исторический интервал между первым stand и новым Attack не объявляется полностью воспроизведённым. Typed witnesses подтверждают снятие конкретных старых causes и одну новую рану, anchored prefix и текущий полный owner; это finite lineage, не общий replay или внешняя защита от намеренного восстановления immutable snapshot.

Один `resolve_free_move_prone_removal` снимает Condition и только Prone cause новой9, расходуя одну free move. Старые и новый terrain, wounds/flags/d10/origin, daily/roll/consumed histories, positions, action/round и Magic Pool/progress сохраняются. Оба child roster синхронизированы. Apply повторно проверяет complete typed result/current state, stale/repeated application отвергается до проекции. Treatment/healing,6/Wind, subsequent repeat после нового consumer и arbitrary movement отсутствуют.

## Детерминированная проверка

- [21 unit tests](../../tests/unit/test_m8_repeated_leg_spasm_stand.py): exact projection и один K1 вызов; pure constructors/apply; frozen/pickle; full-source guards, facts/clock/receipts/rolls; missing/duplicate/reactivated/reordered causes;6/10/13/17/extra Wound; pending/executed/spent move; crafted bool/int/enum witnesses; stale apply. Tests пройдены адресными запусками, затем входят в полный набор ниже.
- [3 integration tests](../../tests/integration/test_m8_repeated_leg_spasm_stand.py): actual first9/stand/second9 → новый stand → context49 → bound Casting/end; foreign owner/stale apply; unchanged legacy/old stand/journal boundaries. Все прошли адресно.
- Multiple-prior9/superficial case использует явно authored older prefix, включая fixed-entry старую9, и настоящие новый stand48, Attack с четырьмя Wound dice, scheduler и repeated stand. Это не fresh encounter provenance для искусственно подготовленного префикса. Сохраняется исходный порядок terrain.
- Независимое review нашло обход nested RollTrace: raw quality string и bool вместо initial d10 проходили через equality полного Attack. Исправлено narrow pure admission normal Attack/Protection traces через existing `InitialTestRoll`, strict quality/dice/success counts, exact final values/no rerolls и modifier trace. Один новый test с6subcases для attacker/defender закрывает raw quality/initial bool/final bool. Отдельно reviewer проверил Wound roll `(True,8)` вместо `(1,8)` — отвергается strict d10 guard. Источники не нормализуются.

Не выполняется повторный RNG roll для валидации. Normal Test может сохранить уже подготовленный штатный range dice modifier; типы/параметры проверяются по original prepared source, а quality/success/reroll modifiers исключены принятой stationary границей.

## Public и installed evidence

[Actual-bound example](../examples/m8/repeated_leg_spasm_stand.py), [stdout](../examples/m8/repeated_leg_spasm_stand.output.txt), [copied test](../../tests/integration/test_m8_repeated_leg_spasm_stand_example.py). Bundle из3файлов: example, `stationary_wound_runner.py`, `magic_scenario.py`.

Actual fresh runner24d10 регистрирует first9 → stand48 → second9 и честно останавливается. Новый manual bound consumer снимает новый Prone cause, сохраняет оба terrain и обе child refs; context49 выполняет normal Casting/end с3d10. None control7d10 сохраняет первую остановку. Всего34scripted d10, source/global RNG неизменны; это конечные пути, не вероятности. Copied-bundle1test OK,0,909с вне sandbox; первая sandbox-попытка дала TEMP PermissionError.

[Installed helper](../../tools/audit_m8_repeated_leg_spasm_install.py) запущен свежим installed Python3.12.4 с `-I`. `.cache/adr0052-installed-audit/checks/evidence.json`: **467 package .py/.json paths+SHA256** совпали между source/wheel/installed;2child commands исполнили copied bundle из отдельной папки, source/installed stdout byte-identical и соответствует public output. Scoped modules импортированы из audit site-packages; source PYTHONPATH не попал в installed process. Public bundle/expected stdout и source package hashes до/после одинаковы. PDF/references в wheel нет, `pip check` успешен. Schema/CLI/process consumers этим новым аудитом отдельно не переобъявляются: они не менялись.

Wheel: `.cache/adr0052-installed-audit/wheels/towr_encounter_balancer-0.1.0-py3-none-any.whl`, SHA256 `4717fd50497b1f18a769fc56452d938918a21ceacab0728311fec4a20fa72b3c`. Runtime: Windows11/CPython3.12.4; dependencies jsonschema4.26.0, referencing0.37.0, jsonschema-specifications2025.9.1, attrs26.1.0, rpds-py2026.9.1, typing-extensions4.16.0. Рабочая `.venv` не заменялась.

## Полная регрессия

Windows11/CPython3.12.4 вне sandbox: **4013tests /33known errors /0failures /0skipped,949,929с**. Log `.cache/adr0052-full-regression.log`. Все33 sorted `ERROR:` headers точно совпали с `.cache/adr0051-final-audit-regression.log` (прежний набор3987tests); новых errors нет. Все26 repeated-stand/contract/public test lines завершились OK:21unit +3integration +2copied examples. Полный suite не зелёный из-за прежних33 expectations errors; они не исправлялись под видом нового consumer.

После полного прогона повторно сравнены manifest467package .py/.json и4public fixture files с installed audit evidence, SHA256 wheel: изменений нет. Production/tests/public fixtures после успешных проверок не менялись. Markdown-пути проверены отдельно, anchors не проверялись; `git diff --check` чист.

## Источники и следующий контракт

BOOK-PLAYER-GUIDE1.4, гл.V Free Actions116, Conditions122/Prone123, приложение Wounds Table190; BOOK-GM-GUIDE1.1, гл.VII Champions92. Сверка выполнена при подготовке ADR-0052, новых страниц/полного чтения при реализации не добавлено. Rule IDs/house rules и версии книг прежние.

Следующий шаг — подготовить ADR-0053 с finite proof: native scenario permission/history witnesses и journal/diagnosis/runner для нового result. До отдельного контракта не расширять смысл прежней stationary policy и закрытый journal union. Generation/wire следуют только после отдельного решения native API; JSON1/2/3 и None остаются прежними.
