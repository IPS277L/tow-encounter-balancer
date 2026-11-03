# ADR-0060: ручной Battered Leg переход в полном M8 owner

Дата: 2026-11-03. Статус: **закрыт в ручной full-owner границе**. [Приёмка](../audits/m8-battered-leg-owner-readiness.md). Основа — закрытый [K1 ADR-0059](ADR-0059-battered-leg-endurance-test.md).

## Источники и scope

PG1.4 Abilities / Characteristics & Skills68–70; Rules / Wounds & Conditions121, Prone123; Appendix / Wounds Table190, строка5. GM1.1 Allies and Antagonists / Champions92. Правила59 сохранены: первая resolved/untreated/unhealed rolled5, пустые Conditions/effects, normal Endurance без modifiers, explicit unmounted actor. Числовой NPC Endurance profile предоставляет caller; из Casting/Protection/default он не выводится.

Это ручной post-Attack переход. Source — полный `NpcRosterChampionAttackResult`, уже применённый к `NpcRosterCastingState`. Его child pending содержит ровно один Endurance follow-up. До RNG проверяются source/current equality, Wizard target, actual Attack/Protection traces, accepted Wound lifecycle, daily registration и execution/roll histories. Текущий ход принадлежит завершившему Attack Minion; положение Wizard в очереди раунда не ограничивается. Другие pending, injury combinations и Miscast-origin Wound5 исключены.

## Контракт

`NpcRosterBatteredLegRequest` содержит id, current state, полный bound Attack, authored `InlineProfile`, strict-True `unmounted` и `no_external_condition_sources`. K1 request выводится из actual effect/follow-up; свободно передать другой Test ID нельзя. Executor один раз вызывает59, Result проецирует только Wizard injury, очищает child pending и синхронизирует оба child roster.

Append-last nullable `NpcRosterCastingState.battered_leg_receipt` хранит bounded `NpcBatteredLegCompletionWitness(attack, endurance, no_external_condition_sources)`. Witness не содержит собственного projected owner и не создаёт циклической истории. Root storage сохраняет его при последующих transitions и проверяет stable Wound identity, profile/actor anchors и ordered execution/daily/roll history prefixes. Для продолжения current injury должен точно совпадать с результатом59; новое unsupported последствие можно сохранить, но следующий normal consumer его отвергает.

Полный owner может хранить unsupported state без receipt. Admission обычных Casting/Attack и scheduling/end-turn требует receipt для Wound5 после снятия pending: простое stripping pending/receipt не разрешает продолжение. Чистый apply требует exact request state; повторное применение отвергается даже при Endurance success без injury delta.

Combat/spatial/magic, action receipts, daily Wounds и consumed IDs не меняются этим follow-up. Success допускает прежние normal consumers в текущей узкой границе. Failure сохраняет Wound-sourced Prone; его снятие и специальные дальнейшие consumers не добавляются.

## Ограничения

Witness проверяет локальную совместимость полного источника, а не глобальную достижимость произвольно сконструированного боя. Native Step union, runner policy/permission, journal membership, fresh scenario/generation и JSON1–5 не расширяются. Отдельные будущие milestones: native runner/journal, затем transport. Хранение caller Endurance profile в manual request не добавляет новый numeric profile во все NPC definitions.

## Проверка

Детерминированные проверки: обе Test branches, once-only apply, source/profile/clock/history substitution до RNG, stripped pending/receipt admission, сохранность всех owner projections, success → actual Casting и failure → честный запрет неподдержанного Prone consumer. Full regression и installed package audit выполняются на границе вехи.

Итог:129targeted OK (15new+114affected), installed15new OK,488source/wheel/installed Python/JSON files совпали. Полный набор **4254 tests, OK**,1791.097s, Windows x64/Python3.12.4. Источники и ограничения не расширялись ради прохождения проверок.
