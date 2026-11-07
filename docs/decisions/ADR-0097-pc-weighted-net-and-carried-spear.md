# ADR-0097: Weighted Net, конечный запас и carried Spear

Дата: 2026-11-07. Статус: **принято пользователем и реализовано, M52 завершена**. Выбраны Net + Spear с прежней тактикой PC и Spear по Defenceless с сохранением Net. Brawn Recover PC и Net→Wound трактовка не входят в реализацию.

## Источники и задача

Адресно сверены BOOK-GM-GUIDE1.1, гл.VII Allies and Antagonists / NPC Profiles93 / Goblin Warrior156 / Night Goblins157; BOOK-PLAYER-GUIDE1.4, гл.III Skills68–69, гл.IV Equipment92/94/96/97, гл.V Actions116 / Recover и Attack118 / Conditions123. Лор о захвате живьём не задаёт отдельного cannot Wound. Это адресное чтение, не перечитывание книг целиком. [Предыдущая сверка](../open-questions-details.md#weighted-net-после-m31).

PG96: Weighted Net — Throwing, Close–Short, 2H; successful Attack накладывает Burdened вместо Damage. GM157 печатает2d/3. Burdened запрещает Manoeuvre, но не Attack/Protection/free draw/standard Recover. В нынешнем неподвижном бою Condition обычно не ухудшит атакующие Tests PC. Net — подготовка нового вида атаки и расходуемого снаряжения; не обещать улучшение оценки сложности от самого Burdened.

## Принятая законченная граница M52

Один новый fixed combat loadout **Night Goblin / Weighted Net + carried Jagged Spear**, без shield. Одна Net в начале боя, без подбора/повторного использования в этом срезе. После настоящего броска, независимо от HIT/MISS, Net недоступна; NPC free draw carried Spear и далее использует обычную Melee. Он может не бросать Net и выбрать Spear по тактике ниже. Это authored выбор снаряжения/действий книжного существа, не бесконечный запас и не новое правило Net.

| Часть | Точный источник/профиль |
|---|---|
| Weighted Net | Throwing2d/3, explicit pool_cap6 отBS3; Close–Short,2H; primary Burdened, Damage отсутствует |
| Jagged Spear | Melee2d/3, cap4 отWS2; maximum Short,1H; Damage3 |
| Protection | Athletics3d/2, cap6; без shield |
| Тело/тип | T3, Resilience3 **armoured**, Normal Minion, Initiative3 |

Net2d не превращается в3d по BS3 и не ограничивается cap4 по удвоенному printed base: actual base2 и cap6 от Characteristic хранятся раздельно. Обе руки свободны для Net; Strength3 допускает перенос одной2H Net и одной1H Spear (PG92). Первоначально NPC держит Net, Spear переносит. Draw/swap — явный free transition по PG116; dropped Net не подбирается бесплатно. Если решено временно взять Spear, неброшенная Net остаётся в переносимом запасе.

Melee продолжается в Close. Charge, Short spatial targeting, pickup в Close врага, новый inventory framework и поиск оптимального действия не входят в функцию.

## Armoured отдельно от числового бонуса

GM157 задаёт printed Res4 (armoured), GM93 требует вычесть1 при отсутствии shield: получается Res3 (armoured) приT3. Повторно начислять light armour из Typical Trappings нельзя. Называть этот профиль unarmoured только потому, что Resilience=Toughness, тоже неверно: PG97 отдельно относит носящего armour к armoured targets.

Сейчас `ResilienceProfile.is_armoured` вычисляется как bonus>0, поэтому такой loadout не представим корректно. Реализован явный необязательный typed `armoured` metadata в ResilienceProfile: при отсутствии сохраняется прежний вывод, при наличии используется точный bool. В PC source explicit true при bonus0 разрешается только полному новому canonical loadout. Это сохраняет Axe/Halberd bonuses против armoured; ignores-armour по-прежнему уменьшает Resilience доToughness. Другие families не получают новый неотображаемый wire state молча: неподдерживаемый explicit metadata должен отклоняться их mapper/admission.

Текущий PC JSON1: дополнительный `definition.resilience.armoured:true` required только этому loadout; у прежних profiles поле не добавляется. Базовые числовые поля toughness/bonus сохраняются. Расширение публичной границы согласовано пользователем.

## Выбор Net и взаимодействие с Defenceless

**Принятая тактика:** в свой обычный Attack NPC использует оставшуюся Net по первой цели текущего priority, только если она не Burdened и не Defenceless. Иначе выбирает Spear, сохраняя неброшенную Net для возможной будущей цели. После расхода Net всегда Spear. Fixed `spear_only` позволяет явно отказаться от её использования при том же carried loadout.

Это caller-owned выбор оружия. Он не объявляет Net безопасной для Defenceless и не запрещает книжную атаку сетью вне данного сценария. Forced manual Net по такой цели не проходит owner admission; разрешение этой комбинации в generic kernel в M52 не заявляется.

PG123 говорит, что любая successful Attack по Defenceless причиняет Wound вместо обычного результата. PG96 заменяет Damage на Burdened; отдельной precedence этих двух замен и указания о совместном Burdened нет. У Rock есть явный cannot Wound, у Net его нет. Сильное буквальное чтение — одна Wound без Damage/Resilience. **Альтернатива для согласования:** разрешить Net по Defenceless и выбрать Wound вместо Burdened; тогда добавить узкий подтверждённый Net→Wound путь, обычный PLAYER Wound/Fate/body и отдельные проверки. Нельзя получить это поведение, просто присвоив Net Damage0, или распространить выбор на все Condition/Hazard attacks.

## PC и освобождение

**Принято:** PC сохраняет нынешние Attack/standard Recover/Help policies. Net сама по себе не становится новым основанием Recover и не меняет приоритеты. Brawn для него не выводится из Melee/Strength/default Skill. Это осознанно выбранная тактика в неподвижном бою, а не запрет книжного освобождения.

PG123 позволяет снять Burdened Brawn Test либо уменьшением груза; PG118 relevant Test требует альтернативного Recover **вместо всех** standard benefits. **Большая альтернатива:** добавить явную optional `net_recover_policy` участника с authored Brawn rating и режимом self-before-attack. Strength уже есть; Brawn rating необходимо передать. Такая policy сначала использует нынешний self-required standard Recover для Staggered/Prone, затем при собственной Net-причине — альтернативный self Recover до обычной Attack/Help/ally Recover. Defenceless не действует. Success снимает только Net-причины, failure их сохраняет; standard benefits одновременно не выдаются. Optional Glorious требует отдельного разрешения Skill.BRAWN в caller criteria. Это больший source/action/Fate контракт; без выбора он не реализуется.

Независимые Net-причины Burdened надо хранить отдельно от Wound/inventory причин и подтверждать actual Attack receipt/target/rule. Обычный standard Recover их не снимает; повторный HIT не создаёт механики двух стаков. При выбранной большей альтернативе успешное освобождение от сетей не удаляет ongoing injury Burdened и не возвращает выброшенные Net NPC.

## Source, JSON и границы слоёв

- Native definition хранит два полных профиля: primary Spear и Net. NpcAttackProfile расширяется конечной альтернативой numeric Damage либо primary ConditionImpactSpec с отсутствующим Damage; exactly one. Net — не secondary ConditionOnHit поверх фиктивного Damage. Throwing preparation проверяет optimum/cap/hands и не переносит Melee outnumbering/higher-ground.
- New canonical loadout допускает conditional `definition.net_attack`: полный id/source/skill=throwing/test_profile/range_min/range_max/hands и явный primary impact `{kind:condition, condition:burdened, rule_id:...}`. Закрытый объект, без Damage и без восстановления пропущенных данных по ID. У остальных definitions поле запрещено. Great Stag trample_attack сохраняет собственный gate.
- У нового NPC required `net_policy:{initial_count:1, mode:throw_once_then_spear|spear_only}`. Native policy связывает actor и точный stock; wire хранит её рядом с этим enemy. У остальных NPC поля нет. Это позволяет сохранить прежние172JSON M9–M51 без миграции; projection подбора удаляет policy вместе с её actor, без переназначения.
- Owner подтверждает выбор профиля, расход одной Net, available IDs и free draw/swap отдельными типизированными proofs. На промахе с Close исполняется обычный own Staggered; уже имеющийся Staggered не удваивается. До RNG/мутации проверяются stock/руки/target/full source. Нельзя повторить расход receipt, вернуть Net через equality с fresh snapshot или сбросить stock новым раундом.
- Dirty Coward сохраняет точное поражение при повторном incoming Staggered. Horde допускает прежнюю явную Help policy: Help имеет приоритет над Attack и не расходует Net. Бонус Melee Help нельзя привязать к будущей Throwing; если получатель сейчас выбирает Net, helper использует Attack fallback. После выбора Spear применим прежний binding конкретного Melee Test. Это часть новой согласуемой тактики, не бесплатный Help в одном действии с Net.
- PC без shield защищается от Throwing через Athletics; наличие Sword/Staff не даёт Defence (PG68). Нынешнюю допустимую fixed Protection policy достаточно сохранить через Athletics; автоматически лучшее Melee opposition в Close не выбирается.
- Clock остаётся обычным: бросок — один Attack action, draw — free transition. Вторая Attack/ability grant не создаётся. Trials/search получают прежние action/Fate/loss aggregates; отдельные Net counters/wire version не вводятся. Подробные Net transitions проверяются в native journal.

## План адресной проверки принятой границы

1. Printed sources/skills/caps/armoured-with-zero-bonus; full canonical guard, source clones/unknown fields/typed aliases до RNG. Прежние56profiles/172JSON сохранены.
2. HIT даёт Burdened без Damage/Stagger/Wound; MISS не накладывает Condition, тратит Net и исполняет own Close-miss. Расход/draw/следующая Spear Attack, retained Net при отказе, repeated/source-bound Conditions.
3. Выбранная Defenceless ветвь; уже Burdened/другая priority цель; Dirty Coward, Horde Help→Net delay, Melee Help binding/fallback, pending Wound/Fate и unsupported prefix.
4. PC сохраняет выбранную тактику; если выбрана большая альтернатива — actual Brawn success/failure/Fate, отсутствие standard benefits, независимые causes и action costs.
5. Current JSON1 conditional fields, full root/candidate echoes, subset policy filtering, sequential CLI simulation/balance. Изменение Resilience metadata требует проверки ближайших Axe/Halberd/ignores-armour consumers и границ других families; один process representative при изменении transported models. Full/wheel — только при основании по AGENTS.md.

## Согласование и результат

Пользователь выбрал Net + Spear при прежней PC тактике и Spear по Defenceless. Полный conditional source, finite stock/free draws, отдельные Net causes, Horde/Dirty Coward и current JSON1 реализованы. Более широкие альтернативы выше сохранены для сравнения; они не являются текущим контрактом. Net→Defenceless не объявляется безопасной и не разрешается через Damage0.

Источники независимо сверены; независимое ревью core/owner не выявило дефектов. Детерминированные проверки, actual service/CLI results, cross-family metadata guards и один настоящий sequential/process Net representative выполнены. Точные команды/результаты — в [статусе](../project-status.md), пользовательский вход — в [примерах](../examples/m52/README.md). [Очередь](../roadmap.md).
