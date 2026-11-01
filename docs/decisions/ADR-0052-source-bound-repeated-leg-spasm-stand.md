# ADR-0052: повторный Leg Spasm после подтверждённого stand

Дата: 2026-11-01. Статус: **пункты1–3 выполнены, ADR закрыт в принятой low-level границе**. [Итоговый аудит](../audits/m8-repeated-leg-spasm-stand-readiness.md). Prerequisites: [stand48](ADR-0048-source-bound-leg-spasm-stand.md), [stationary context49](ADR-0049-stationary-leg-spasm-continuation.md), [native policy50](ADR-0050-native-stationary-wound-policy.md), [закрытый transport51](../audits/m8-stationary-wound-transport-readiness.md).

## Выбор и нормативное основание

После [сравнения continuations](../audits/m8-continuation-inventory.md) выбран один низкоуровневый consumer: снова встать после новой Leg Spasm, когда предыдущая Leg Spasm уже потеряла Prone cause посредством действительного stand48. Wound10 требует нового расхода next-Test Grim, включая Protection на чужом ходу; готового consumer расхода нет. Wind-Prone при terrain требует отдельного Miscast provenance. Оба направления отложены.

Адресно перечитаны локальные BOOK-PLAYER-GUIDE1.4: гл.V Rules / Grim & Glorious Tests108 (сопоставление Wound10), Free Actions116, Giving Ground119, Conditions122 и Drained/Prone123; приложение Wounds Table190. BOOK-GM-GUIDE1.1: гл.VII Allies and Antagonists / Champions92. Это выбранные страницы, не новое полное чтение книг. Версии и хэши прежние.

RULE-HEALTH-005/008 и RULE-COMBAT-014 сохраняют смысл: одна Condition каждого вида; строка9 явно позволяет снять Prone посредством free move либо Recover, а Difficult Terrain остаётся до treatment. Self-stand требует отсутствия enemy Close и расходует одну free move вместо перемещения. Он не создаёт Test, не лечит раны и не расходует action. Champions используют Wounds Table как PC. Книжного ограничения «встать можно только после первой9» нет: нынешний stop — техническая граница consumer48, не house rule.

## Отдельный явный контракт

Не ослаблять validators48/49 и не считать отсутствие эффекта доказательством его законного снятия. Добавить отдельные frozen/slotted модели `NpcRosterRepeatedLegSpasmStandRequest` и `NpcRosterRepeatedLegSpasmStandResult`, отдельные executor/apply в domain/rules. Домен и rules не зависят от runner, CLI или application. Нового поля Scenario, enum permission или JSON версии в этом ADR нет.

Реализованные модули: [domain models](../../src/towr/domain/npc_roster_repeated_leg_spasm_models.py) и [rules executor/apply](../../src/towr/rules/npc_roster_repeated_leg_spasm_resolution.py); публичные функции `stand_npc_roster_repeated_leg_spasm` и `apply_npc_roster_repeated_leg_spasm_stand`. Result содержит `source`, `stand`, вычисляемые `removed_effects` и `state`, аналогично stand48, с новым admission выше. [Unit tests](../../tests/unit/test_m8_repeated_leg_spasm_stand.py) и [integration](../../tests/integration/test_m8_repeated_leg_spasm_stand.py).

Request содержит `id`, полный текущий `state: NpcRosterCastingState`, `actor_id`, strict bool `actor_has_enemy_in_close_range` и `underlying_cause_allows_removal`, полный `previous_stand: NpcRosterLegSpasmStandResult` и `wound_attack: NpcRosterChampionAttackResult`. Последние два — обязательные typed witnesses, не одни IDs/sequence и не вручную восстановленный injury. Повторная pure admission исходников выполняется до equality/проекции, без исполнения reducers и RNG.

Граница первого consumer:

- Живой owner Wizard, один активный неисполненный STANDARD slot, unused free movement; pending Attack/Miscast/movement/interruption исключены существующим full-owner phase validation. Conditions только Prone и optional Staggered. Enemy Close=False, underlying cause permits removal=True; caller обязан подтвердить отсутствие внешних причин. Zone сама по себе не доказывает дальность.
- Ровно один предыдущий stand48, допустимый по его неизменённому контракту. Его исходник может содержать несколько9 и superficial1–3; прежние wounds уже resolved/untreated/unhealed. Все ранее удалённые Prone causes доказаны `previous_stand.removed_effects`; все прежние terrain должны остаться.
- После этого stand — ровно одна новая canonical **rolled** Leg Spasm9 от completed bound `wound_attack`, без pending follow-ups. Scope исключает6, Wind, иные новые Wounds, treatment/healing и внешние Condition causes; подтверждаются exact текущие causes и explicit no-external assertion, а не отсутствие любых событий в произвольной истории. Новая рана имеет следующий sequence, точные d10 и сумму9; fixed-entry suffix в этот срез не входит.
- Injury перед новым Attack в точности совпадает с injury после previous stand; injury текущего owner — с завершённым Attack. Current effects — прежние terrain в исходном порядке плюс ровно canonical Prone/UNTIL_REMOVED и terrain/UNTIL_TREATED новой9. Нельзя разрешать ещё одну отсутствующую причину по whitelist, повторно активировать старую или принимать иной duration/sequence/duplicate.
- Связать witnesses с одним actor, его definition/caster, ordered Wound records, daily owner/day/receipts, consumed execution/roll provenance и исходным spatial anchor. Pre-Attack daily receipts и consumed Wound roll IDs **точно равны** output previous stand: новых ран в интервале нет. Consumed execution IDs допускают только ordered extension прежнего prefix из-за прошедших actions. Новый Attack добавляет именно свою Wound/daily/roll регистрацию. Current histories совпадают с завершённым Attack; start/end turns не могут менять их. Полный pre-Attack stationary context сохраняется и проверяется, а не заменяется совпадением target ID.
- Attack round строго позже previous stand round; Wizard ещё не завершил свой ход в Attack round. Current round равен Attack round. Между завершённым Attack и current разрешена только точная scheduler delta: end attacker → start Wizard в том же round, включая один соответствующий пустой end receipt и синхронизацию child round. Полные roster, wizard/magic, graph/placements, consumed histories и остальные поля совпадают с Attack output; их нельзя подменить, сравнив один injury. Проверка этой delta чистая, по существующим моделям scheduler, без исполнения reducers. Старые owner anchors — exact ordered actor IDs/definitions/sides, caster, daily owner/day и graph/placements — совпадают с pre-Attack source; прочие прошедшие actions между первым stand и новым Attack не объявляются восстановленными.
- Строгие типы, canonical records и full-owner guards обязательны, включая detached witnesses с `1 == True` и строками вместо enum. Daily receipt хранит запись до разрешения effect: сравнивать её с current Wound через явно проверяемый lifecycle transition, а не требовать неверного equality `effect_resolved` или молча нормализовать исходный receipt.

Это finite lineage между двумя явными переходами, а не доказательство достижимости произвольного snapshot, не общий journal replay и не защита от намеренного восстановления старого immutable state. Полный current state остаётся authoritative для нового перехода; historical witnesses доказывают конкретное снятие старого cause и происхождение новой раны.

## Результат и apply

Executor вызывает один existing `resolve_free_move_prone_removal`, без RNG. Result хранит полный request и K1 result; pure result validation проверяет точный переход. Удаляются одна Condition.PRONE и только canonical Prone cause **новой**9. Все старые и новый terrain остаются; Wound records, flags, d10/origin, daily/roll/expiry/consumed histories, позиции, round/action receipts, Magic Pool/progress и остальные участники сохраняются.

Проекция roster синхронна с обоими `champion_attack`/`minion_attack` owners. Изменяются только injury owner и free-move used resource. Apply требует equality полного current source с result.source.state, stale/repeated application отвергается. Result не вводит persisted generic event history. Последующий повтор после **нового** consumer требует отдельного расширения witness-контракта; этот consumer принимает именно prior stand48, не рекурсивную цепь собственных results.

Post-stand context49 уже допускает несколько retained terrain9. Проверить его на настоящем новом результате и выполнить stationary Casting/end через existing APIs, сохранив запрет Give Ground. Это не разрешение для arbitrary Prone/Drained, Recover, ordinary movement или лечения.

## Исполняемый finite proof

[Probe](../examples/m8/repeated_leg_spasm_contract_probe.py), [stdout](../examples/m8/repeated_leg_spasm_contract_probe.output.txt), [copied-bundle test](../../tests/integration/test_m8_repeated_leg_spasm_contract_probe.py). Bundle: probe, `stationary_wound_runner.py`, `magic_scenario.py`; только существующие публичные APIs.

Настоящий fresh opted runner получает9, выполняет stand48, затем получает вторую9 двумя Wound dice. В stop сохранены реальный previous stand и полный новый Attack, old terrain и new Prone+terrain. Stand48 обязан отвергнуть такую историю. Отдельный K1 self-stand показывает доступный primitive; он **не проецируется в owner** и не выдаётся за новый bound consumer. None остаётся отдельным отрицательным control. Другие Wounds проверяются при реализации пункта2. Это конечные детерминированные пути, не вероятности и не готовый runner continuation.

## План реализации и приёмки

1. **Выполнено:** frozen request/result, strict source/canonical/provenance admission и exact projection. Tests witnesses обоих owners, ordered prefix и old/new cause distinctions; другой actor/day/definition/roll/receipt/clock, missing/duplicate effects и crafted detached sources отвергаются до RNG. Source не нормализуется молча.
2. **Выполнено:** один K1 executor + exact-source apply; действительный full-owner второй stand и post-stand Casting/end. Проверены source immutability, free move/action/positions, both child refs, no treatment/healing/RNG, stale apply, Close/spent move и неподдержанные injuries/extra Wound/Conditions.
3. **Выполнено:** public actual-bound example34d10, copied bundle, isolated installed package467file parity и полная регрессия4013tests/33known errors/0failures/0skipped. Все33 exact ERROR headers прежние; новых ошибок нет. [Итоговая evidence](../audits/m8-repeated-leg-spasm-stand-readiness.md).

Историческая contract-only проверка: `$env:PYTHONPATH='src'; .venv/Scripts/python.exe -m unittest tests.integration.test_m8_repeated_leg_spasm_contract_probe -v` — **1 test OK,1,194с**, Windows/CPython3.12.4 вне sandbox после TEMP PermissionError в первой sandbox-попытке. Независимое read-only review контракта/probe блокеров не оставило; exact pre-Attack daily/roll histories и конечная граница provenance уточнены. На этом шаге production не менялся, full suite не повторялся; ориентиром был baseline3987/33known ADR-0051. Реализация и новая полная проверка приведены выше и в итоговом аудите.

Automatic runner/diagnosis/journal dispatch, расширение stationary policy, generation и wire — **после закрытия low-level consumer отдельным контрактом**. None traces/stops/RNG, первая9 и существующие JSON1/2/3 остаются прежними.
