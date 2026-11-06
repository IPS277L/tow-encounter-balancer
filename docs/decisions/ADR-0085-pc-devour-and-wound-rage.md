# ADR-0085: раненные Brutes и Devour the Fallen в PC melee

Дата: 2026-11-06. Статус: **принято и реализовано**. Выбор Axe loadouts — граница реализации, новых тактик или house rules пользователь не вводил.

## Источники и граница

BOOK-GM-GUIDE1.1, Allies and Antagonists / Razorgor138 / Minotaur147; BOOK-PLAYER-GUIDE1.4, Dice Pools107 / Wounds121/190 / Conditions123. Продолжение M36 добавляет общую механику и три loadouts: natural Razorgor, Minotaur с одним Axe и Minotaur с двумя Axes. Все Brutes3Wounds, T5/Res6 armoured; W1/W2 дают+1d Melee за каждую свою Wound, W3 defeats. Раны сами по себе не добавляют Drained.

Это ordinary Attack Test bonus: cap и Drained filter сохраняются. Minotaur dual loadout использует printed Axe4d/5 Damage5,1H плюс отдельный DamageModifier+1 за выбранные два топора, как существующий Gor. Fixed loadout занимает обе руки и не имеет щита; не добавлять PC Axe Traits.

Fearsome требует Give Ground, которого текущая SUFFER_WOUND policy не выбирает. Razorgor Charge и отдельный Minotaur Charging Bull action не исполняются fixed Attack policy, но полные triggers/effects остаются в metadata. NPC Recover, смена стратегии, движение и дополнительные действия не добавляются.

## Снимок Devour the Fallen

Правило даёт один+1d Wounds Table, когда **фактическая цель перед атакой** Staggered, Prone или Wounded. Это объединение условий, не отдельный куб за каждый Condition/Wound. Новая рана от этой же атаки не делает изначально здоровую цель подходящей. Если pre-Attack Staggered затем снимается раной по PG121/190, бонус уже связан с этой атакой и сохраняется.

Owner выводит WoundDiceModifier из canonical NPC definition и pre-Attack CharacterInjuryState и передаёт в существующий KernelAttackRequest.wound_dice_modifiers. Kernel/Wound lifecycle/Fate используют этот точный source без нового mutable банка и без повторной проверки post-Damage Conditions. Применение не переносится на другую атаку/получателя и не увеличивает будущие untreated-Wound dice само по себе.

Wounded конкретизируется как наличие незажившей Wound. PG121 различает treatment и healing: treatment снимает обычный дополнительный куб за untreated injury, но не превращает Wound в healed. В admitted family все персонажи начинают здоровыми, лечение/заживление внутри боя не исполняется, поэтому для всех достижимых состояний эти различия не меняют scope. Перед расширением treatment/campaign перепроверить эту конкретизацию.

Wounds Table — сумма d10, не Skill Test. Drained/Grim/Glorious/Characteristic dice cap не меняют дополнительный table die. Сохраняется обычная формула минимум1, base1+prior untreated Wounds+явные WoundDiceModifier. Extra die не означает дополнительную Wound. Direct hit, repeated Staggered→Wound, Defenceless и Near Miss проходят прежние typed ветви и однократную проверку источника.

## Почему Greataxe остаётся unselected

GM147 печатает WS4 и Greataxe3d/5. PG107 даёт максимум8 от Characteristic4; InlineProfile(3,5) по умолчанию выводил бы6 из printed attack dice. Повторное применение штрафа Greataxe тоже неверно. На момент M37 модель InlineProfile и wire profile уже содержали pool_cap, но PC source admission запрещал non-null cap, а схема разрешала только null. Ранее здесь ошибочно утверждалось, что wire передаёт только dice/threshold; проверка M38 исправила описание. M37 выбирает два Axe loadouts4d/5 с корректным cap8; Greataxe unselected в этих loadouts. [Реализованное M38](ADR-0086-pc-minotaur-greataxe-pool-cap.md) добавляет отдельную canonical Greataxe с cap8/readmission без новых полей или миграции старых JSON.

## Контракт и проверка

Current PC JSON1 остаётся прежним: canonical definition identity выбирает дополнительные профильные правила, source fields/метрики/версия не меняются. Общие K1 модели WoundDiceModifier/Kernel уже существуют. Нужны явные PC helpers, actual attacker wounds/target state и canonical replay, без универсального языка Ability.

Адресная приёмка: три printed source/gear/type graphs; W0/W1/W2/W3 Melee pools и Drained/cap; отдельный dual Damage; pre-Attack eligibility каждого условия и union; direct/repeated-Staggered/Defenceless/Near Miss table dice с full source; cached/alias/once-only guards; current JSON/trials/count search/CLI examples. Ближайшие PC Attack/Wound/Fate/Help consumers; full project/wheel/process matrix без изменения этих механизмов не требуются. Успешные проверки не повторять без влияющего изменения.

Реализация: [catalog](../../src/towr/domain/pc_npc_catalog.py), [явные modifiers](../../src/towr/domain/pc_npc_ability_models.py), [pre-Attack binding в owner](../../src/towr/domain/pc_melee_result_models.py). Проверки: [catalog/source](../../tests/unit/test_m37_pc_devour_catalog.py), [native rage/Devour/Fate/guards](../../tests/unit/test_m37_pc_devour_execution.py), [JSON/trials/search](../../tests/integration/test_m37_pc_devour_chunk.py), [CLI-примеры](../examples/m37/README.md). Адресный контроль19модулей/217tests прошёл за11.849s. Текущие результаты — в [статусе](../project-status.md); очередь — [roadmap](../roadmap.md).
