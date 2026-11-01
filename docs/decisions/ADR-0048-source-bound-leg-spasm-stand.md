# ADR-0048: source-bound self-stand после Leg Spasm

Дата: 2026-10-31; обновление: 2026-11-01. Статус: **пункты1–3 завершены; ADR закрыт в low-level границе**. Следует за закрытым [ADR-0047](ADR-0047-opt-in-generation-and-magic-json-v2.md) и [актуализированной инвентаризацией](../audits/m8-continuation-inventory.md). Это узкий низкоуровневый переход, не включение всей Wound9 в автоматический runner.

## Книжное основание

Непосредственно прочитаны локальные постраничные тексты, не changelog:

| Источник | Следствие |
| --- | --- |
| BOOK-PLAYER-GUIDE1.4, приложение / Wounds Table, стр.190, строка9 Leg spasm | Prone снимается free move или Recover; все движения остаются Difficult Terrain до treatment. Снятие Condition не означает treatment/healing. |
| Та же книга, гл.V Rules / Free Actions116, Prone123 | Self-stand заменяет free movement, требует отсутствия enemy Close и расходует этот ресурс один раз за ход. Ни Zone transition, ни отдельный action/Test не создаются. |
| Та же книга, Conditions122 | Сохраняющиеся причины нельзя обойти общим снятием Condition. Явное разрешение строки9 применяется только к её собственному Prone, не к любой ране. |
| Та же книга, Difficult Terrain115, Recover118 | Crossing требует Athletics либо специального разрешения. Stand выполняется вместо перемещения, crossing отсутствует. Recover отдельно позволяет снять Prone даже при enemy Close; это не выбранный здесь путь. |
| Та же книга, Wounds Table190, строки10/13/17 | Crushed rib требует next-Test Grim; Torn leg — Critical при преждевременном снятии Prone; Shattered knee имеет другие persistent Conditions. Общая whitelist Prone/UNTIL_REMOVED ошибочно объединила бы разные строки. |
| BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / Champions92 | Champion использует Wounds Table, не Minion defeat. |

Это уточнение применения существующих RULE-HEALTH-005/008 и RULE-COMBAT-014, не house rule. Нет новой трактовки отсутствующих source facts или незакрытых Miscast ambiguities.

## Почему выбран этот переход

K1 уже завершает Leg Spasm без follow-up: создаёт `WoundConditionEffect(PRONE, UNTIL_REMOVED)` и `WoundRestrictionEffect(MOVEMENT_IS_DIFFICULT_TERRAIN, UNTIL_TREATED)` с одним `wound_sequence`. Daily registration и Wound resolution выполнены. Ни Endurance profile, ни inventory, ни дополнительный RNG не нужны.

Текущий scoped stand ADR-0046 сознательно отвергает active Wound restrictions. Его projection удаляет только Condition; простое ослабление whitelist оставило бы активный Prone effect либо разрешило бы Wound13. Отдельная граница должна сохранить полный source и удалить только действительно погашенные причины.

После такого stand текущие Casting/Protection/end-turn guards всё ещё не допускают retained Difficult Terrain restriction. **Их нельзя ослабить в этом ADR.** Перемещение, Broken escape и последующая автоматическая stationary integration потребуют собственного согласованного контракта. Поле `miscast_continuation` не переопределяется как общее разрешение всех Wounds; JSON v1/v2 и None traces/stops остаются прежними.

## Реализованный публичный API

Новые узкие модули `domain/npc_roster_leg_spasm_models.py` и `rules/npc_roster_leg_spasm_resolution.py`:

```python
NpcRosterLegSpasmStandRequest(
    id, state, actor_id,
    actor_has_enemy_in_close_range,
    underlying_cause_allows_removal,
)
NpcRosterLegSpasmStandResult(source, stand)
stand_npc_roster_leg_spasm(request)
apply_npc_roster_leg_spasm_stand(state, result)
```

Модели frozen/slotted; `state` — полный `NpcRosterCastingState`, `stand` — существующий `FreeMoveProneRemovalResult`. Нет нового универсального effect dispatcher, Wound language или независимой копии action/spatial state. Result хранит исходный request и K1 result; projected state и removed-effect views вычисляются, не принимаются от caller.

### Preflight до исполнения

- Непустые ID, точные typed state/result, оба required bool без defaults. Enemy Close запрещён; `underlying_cause_allows_removal=True` подтверждает отсутствие внешней неснимаемой причины, но **не обходит Wound validation**. Геометрия не выводится из same Zone/adjacency; caller обязан передать проверенный факт.
- Actor — живой Wizard/Champion этого owner, active turn содержит единственный ещё не исполненный STANDARD slot; free movement actor ещё не израсходован. Action declaration сохраняется и не исполняется.
- Existing pending/owner/round/clock guards действуют. Нет pending Wound/attack/Give Ground/Casting/Miscast continuation. Нельзя обходить mandatory фазу, конструируя stand.
- Первый scope намеренно узкий: Conditions Wizard — Prone и опциональный Staggered; без Broken/Drained/other Conditions. Все его Wounds resolved, untreated и unhealed; entries только Superficial Injury или Leg Spasm. Требуется минимум один Leg Spasm.
- Для **каждой** Leg Spasm должна присутствовать ровно canonical пара Prone/UNTIL_REMOVED + Difficult Terrain/UNTIL_TREATED того же `wound_sequence`. Для Superficial Injury активных effects нет. Набор/порядок исходных effects сохраняется; дубликаты, missing/foreign effects, подмена entry/sequence/duration, другие restrictions и treated/healed states отвергаются. Table-roll записи проверяются на canonical entry/total; fixed-entry provenance не превращается в выдуманный roll.
- Несколько Leg Spasm допустимы только с полной проверкой каждой пары; снимается один общий Condition, расходуется одна free move. Удаляются все его canonical Leg Spasm Prone causes, а не произвольная первая запись.

Эти ограничения — техническая область первого consumer, не утверждение, что с иной травмой невозможно встать по книге. Existing standalone stand, Minion support и treatment APIs не меняются.

### Переход и полное состояние

Один вызов existing `resolve_free_move_prone_removal` без RNG снимает Prone и отмечает free movement used. Ни position/Zone, ни round/action receipts, ни action count не меняются. Использование free-move resource вместо crossing не требует Athletics Test и не снимает restriction.

Projected injury удаляет Condition.PRONE и только доказанные canonical Prone/UNTIL_REMOVED effects Leg Spasm. Все Difficult Terrain effects сохраняются в исходном порядке, как и WoundRecord/rolls/origin, treatment/healing flags, Staggered и daily receipts. Magic Pool/progress, consumed execution/roll IDs, другие actors/placements, archived dead participants, expiries и журналы не меняются.

Новый roster синхронизируется с обоими существующими `champion_attack`/`minion_attack` owners; old full state не мутируется. Result валидирует точный K1 transition/source/rule trace, не только совпадение target ID или конечного Condition. Apply требует equality полного текущего state с source; повторное применение к уже изменённому state запрещено. Преднамеренное восстановление старого immutable snapshot не является внешней защитой от replay и не обещается.

## Исходный finite proof границы (contract stage)

[Probe](../examples/m8/leg_spasm_contract_probe.py), [stdout](../examples/m8/leg_spasm_contract_probe.output.txt), [copied-bundle test](../../tests/integration/test_m8_leg_spasm_contract_probe.py). Двухфайловый bundle с `magic_scenario.py`, только existing public APIs.

Реальный fresh runner получает Wound9, полностью регистрирует её и останавливается с ACTOR_INJURY без pending follow-up; legacy None даёт тот же честный stop. Отдельный K1 self-stand показывает допустимое снятие Condition/расход ресурса с неизменными positions. **Он не является новым full-owner result**: исходная injury всё ещё содержит оба эффекта, а текущий bound stand её отвергает. Controls для10 и13 сохраняют Grim/Critical restrictions и не маскируются под9. Всего45scripted d10; это finite path evidence, не вероятность.

## План реализации и приёмки

Contract-only проверка: `$env:PYTHONPATH="src"; .venv/Scripts/python.exe -m unittest tests.integration.test_m8_leg_spasm_contract_probe -v` — **1 test OK,0,843с**, Windows/CPython3.12.4, вне sandbox. Первая sandbox-попытка получила TEMP PermissionError, не assertion failure. Probe также выполнен напрямую. Независимое ревью контракта/инвентаризации блокеров не оставило. Полная регрессия повторно не запускалась: production не менялся, добавлен только один subprocess test; последний полный результат3796/33known errors/0failures остаётся исторической проверкой прежнего набора.

1. Выполнено: frozen request/result и canonical Leg Spasm admission/projection; deterministic tests полного owner и canonical sources. Existing whitelists не расширены.
2. Выполнено: один K1 executor + exact-source apply; tests one/multiple Leg Spasm, superficial histories, strict bools/types, before/after/replay, Close/spent move, чужие actor/source/turn/pending, no treatment/healing/RNG. Полный side-effect contract и обе owner projections.
3. Выполнено: public actual-bound example, isolated installed package и полная регрессия. Прежние unsupported labels и v1/v2 результаты сохранены; итог — в [аудите](../audits/m8-leg-spasm-stand-readiness.md).

После закрытия низкоуровневого consumer отдельно проектируется stationary continuation: Casting и Protection, Wound6 expiry coexistence, end-turn, authoritative injury/source helper, no movement/Give Ground bypass и explicit runtime policy. Нельзя объявить весь Wound9 supported или менять Miscast policy/внешний формат в рамках текущего stand-only ADR.

## Проверка реализации пунктов1–2 — 2026-11-01

[Модели](../../src/towr/domain/npc_roster_leg_spasm_models.py), [executor/apply](../../src/towr/rules/npc_roster_leg_spasm_resolution.py), [25 unit tests](../../tests/unit/test_m8_leg_spasm_stand.py), [2 integration tests](../../tests/integration/test_m8_leg_spasm_stand.py). Integration получает настоящую Wound9 из fresh runner при None и explicit policy, выполняет новый full-owner stand и проверяет сохранение Difficult Terrain, daily/roll history и обеих child references. Controls10/13 отвергаются. Runner по-прежнему останавливается на retained injury; новый result не добавлен в automatic journal.

Релевантный набор:149 tests за1,139с,148 прошли; единственная ошибка — sandbox WinError5 при TEMP cleanup существующего subprocess example. Этот один тест отдельно прошёл вне sandbox:1 test OK за0,768с. Assertion failures нет. Независимое read-only review production блокеров не выявило. На этапе пунктов1–2 полный suite и installed package не проверялись; evidence следующего пункта3 хранится отдельно ниже.

## Пункт3: публичный пример и аудит

[Actual-bound example](../examples/m8/leg_spasm_stand.py), [stdout](../examples/m8/leg_spasm_stand.output.txt), [copied-bundle test](../../tests/integration/test_m8_leg_spasm_stand_example.py). Два публичных файла, actual registered Wounds9/10/13 и новый stand/apply; полный source immutability и обе child references проверены. Исходный contract probe выше сохраняется как историческая evidence K1-only границы.

[Аудит](../audits/m8-leg-spasm-stand-readiness.md) содержит точные команды, installed/source parity457files, новый isolated copied example,95transport child commands и baseline comparison полной регрессии:3825tests/33known errors/0failures/0skipped за657,616с. Exact ERROR headers совпали с baseline, новых ошибок нет; suite с известными errors не зелёный. Stationary integration остаётся следующим отдельным контрактом ADR-0049.
