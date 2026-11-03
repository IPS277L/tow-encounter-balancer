# ADR-0059: source-bound Endurance Test for Battered Leg

Дата: 2026-11-03. Статус: **закрыт в K1 границе**. [Приёмка](../audits/k1-battered-leg-readiness.md), [M8 continuation inventory](../audits/m8-continuation-inventory.md).

## Нормативная база

Player’s Guide 1.4, Abilities / Characteristics & Skills, стр. 67–72: Endurance обычно использует Toughness; GM может заранее назначить другую Characteristic. Rules / Wounds & Conditions, стр. 121 задаёт обработку Wound Table; Appendix / Wounds Table, строка5, стр. 190 требует Endurance Test после Battered Leg, провал вызывает Prone, а строка относится к Catch Your Breath. Conditions / Prone, стр. 123 задаёт обычные последствия и снятие Prone. [Source index](../source-index.md) подтверждает выбранную книгу. Новый Rule ID или house rule не вводится.

## Решение и граница

Добавить отдельный K1 consumer для уже существующего `WoundEnduranceTestRequest` строки Battered Leg. Первая граница принимает одну canonical rolled5: `(5,)`, effect resolved, untreated и unhealed; без Conditions и других активных Wound effects. Обязательное strict-True `unmounted` утверждает отсутствие mount/vehicle, поскольку Prone иначе требует dismount (PG1.4, стр.123). Эти ограничения задают поддержанный срез, а не изменяют книжные правила сочетаний.

Запрос связывает actor ID, exact injury snapshot, полный `WoundEffectResult` witness и его единственный canonical Endurance follow-up, caller-supplied `TestRequest`, semantic skill `ENDURANCE` и выбранную до броска Characteristic. По умолчанию используется Toughness/Endurance; явные альтернативы ограничены текущим enum `Characteristic`. Weapon Skill/Ballistic Skill этот enum пока не охватывает. Числовой profile остаётся явным authored input. Допускается только normal Test без dice/quality/success modifiers и reroll locks. Drained, Distracted, Crushed Rib и другие сочетания требуют отдельного preparation/consumption contract.

Consumer выполняет существующий `resolve_test` с внедрённым RNG, затем переиспользует `resolve_wound_endurance_test`. Успех сохраняет injury snapshot; неуспех добавляет только source-scoped Prone. Проверка является немедленным Wound follow-up; K1 не меняет combat action/receipt.

Constructor и executor проверяют согласованность переданного источника до RNG. Result через `InitialTestRoll` сверяет pool/threshold относительно профиля, normal quality, отсутствие rerolls, исходные/итоговые d10, successes и applied rule IDs. Совпадение Test ID не скрывает несовместимые параметры или арифметику. Проверяется точное injury delta. Это проверка совместимости witness, а не доказательство происхождения фактических бросков: actor/profile authority, battle chronology и journal membership остаются у caller.

## Не входит

- M8 Wizard profile/JSON schema или generated family changes.
- NPC Endurance profile inference, balance defaults, alternate characteristic policy beyond caller input.
- Полный battle owner, action receipt, turn scheduling, replay/journal membership.
- Другие Endurance Wound follow-ups (Nicked Arm, Gashed Brow и другие таблицы/эффекты).
- Другие Wounds/Conditions, modifiers, Fate/Lucky/Talent proofs, mounts/vehicles и dismount.
- Изменение лечения, expiry, Wound roll, Near Miss, Condition removal, Combat Surgeon или иных правил.

После K1 consumer сначала нужен отдельный ручной full-owner bridge, затем native runner/journal и generation/wire milestones.

## Проверка

Source/installed targeted: **26 tests, OK**. Full regression: **4239 tests, OK**. Source/wheel/installed parity: **486 Python/JSON files**. [Приёмка](../audits/k1-battered-leg-readiness.md) фиксирует команды, ограничения и результаты.
