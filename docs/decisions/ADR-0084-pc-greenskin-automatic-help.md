# ADR-0084: Horde и Power of the Waaagh! в NPC Help

Дата: 2026-11-05. Статус: **принято и реализовано**. Пользователь выбрал Help орков для Drained beneficiary при сохранении Attack fallback у dice helpers. Продолжение M33 для четырёх существующих loadouts, без увеличения каталога.

## Источники и задача

BOOK-GM-GUIDE1.1, Allies and Antagonists: Goblin Warrior156, Night Goblin157, Orc Boy158, Big ’Un159. BOOK-PLAYER-GUIDE1.4, Rules: Dice Pools107, Helping With a Test108, Opposed Tests109, combat actions116–119, Conditions123.

Horde даёт союзной attack один bonus die без Help Test, с превышением обычного bonus cap. Night Goblin наследует способность Goblin Warrior; Nasty Skulker не наследует её. Power of the Waaagh! даёт союзной Melee attack один free success без Help Test; Big ’Un наследует способность Orc Boy. Получатель не обязан быть Goblin/Orc. Текущий melee/Close сценарий удовлетворяет обоим условиям.

Free success прибавляется к итоговым successes и не заменяет бросок. Ноль успехов на кубах плюс один free success дают один итоговый успех: против одного успеха защиты это попадание с margin0, против двух — промах. Grim/Glorious перебрасывают кубы, а не free success. Drained запрещает bonus dice, включая bypass, но не free successes. Drained helper может применять no-Test Help, поскольку собственного Test нет.

Разные реальные Help actions дают отдельные складываемые источники; книжного ограничения одним помощником или одним эффектом данного имени не найдено. Каждый receipt применяется однократно к назначенному Test. Успех против Defenceless по-прежнему даёт одну Wound, без умножения ран на число free successes.

## Принятая граница M34

Сохранить required npc_help_policies, явные пары, нескольких helpers одному более позднему ordinary NPC attacker, запрет chains/self/duplicate helper, порядок применения receipts и проекцию обоих endpoints из [ADR-0083](ADR-0083-pc-npc-automatic-help-policy.md). Расширить helper admission на Goblin Warrior/Spear, Night Goblin/Spear, Orc Boy/Choppas и Big ’Un/Choppas. Peasant/Militia остаются поддержаны.

В no-Test модели ввести конечный тип эффекта: один uncapped bonus die либо один free success. Application содержит соответствующий DiceModifier либо SuccessModifier, полный source action и точный beneficiary Test ID. Не представлять free success дополнительным кубом или фиктивным TestResult. Canonical book definition определяет Rule ID и тип эффекта; caller не выбирает произвольные бонусы. Replay/readmission проверяют оба вида модификаторов, их порядок и источник.

Настоящий Help занимает standard action slot, проходит обычный TurnEnd и учитывается прежними NPC Help costs. Catalog definitions, printed attacks/protection, shields, Dirty Coward, W1 Drained/W2 defeat сохраняются. Четыре Help Abilities переходят в active capability metadata; Charge и другие неподходящие triggers не включаются. При пустой policy поведение остаётся прежним.

## Выбор тактики при Drained beneficiary

В M33 пользователь выбрал Attack fallback при Drained получателе: все прежние способности давали бесполезные для него bonus dice. Это тактика симуляции, а не запрет книги помогать Drained.

Пользователь выбрал сохранить fallback для dice helpers, но разрешить Orc Boy/Big ’Un выполнить назначенную Help для Drained beneficiary: free success сохраняется и полезен. Отклонённая альтернатива — сохранить единый Attack fallback для всех помощников, включая орков. Остальные guards/fallback M33 сохраняются.

## Публичный контракт

Остаётся current PC JSON1: новых полей, версии и метрик не требуется. Эффект однозначно следует из canonical helper definition. Native action/effect/application модели расширяются вместе с tests; отдельная compatibility branch для прежнего внутреннего snapshot не нужна. Required source fields сохраняют обязательность. Прежние JSON-примеры и результаты не мигрируются.

## Адресная приёмка

1. Оба no-Test эффекта, настоящий slot/TurnEnd/no RNG, exact source/type/receipt и однократное применение.
2. Четыре новых helper loadouts, смешанные multiple helpers, обычный cap отдельно от Horde bypass, free successes при нуле rolled successes, tie/miss и Grim.
3. Drained helper/beneficiary, сохранение прежних Peasant/Militia и согласованного fallback; отсутствие rollover и подмены dice/success источников в native replay.
4. Current JSON admission/roundtrip, trial costs/summary/count projection и исполняемый смешанный пример через CLI. Прежние definitions/snapshots и JSON values сохраняются; меняется только metadata четырёх Help Abilities.
5. Ближайшие Test/Help/PC consumers. Полный project regression, wheel и повторная backend matrix без изменения соответствующего механизма не требуются.

Реализация: [effect/action/application models](../../src/towr/domain/automatic_help_models.py), [PC policy/mixed applications](../../src/towr/domain/pc_npc_help_models.py), [Test trace validation](../../src/towr/domain/pc_melee_result_models.py), [catalog](../../src/towr/domain/pc_npc_catalog.py). Проверки: [K1](../../tests/unit/test_k1_automatic_help.py), [native/cap/Drained/forgery](../../tests/unit/test_m34_greenskin_help_execution.py), [JSON/trials/count search](../../tests/integration/test_m34_greenskin_help_json.py). [Фактические CLI-примеры](../examples/m34/README.md). Адресный контроль30модулей/319tests прошёл за15.446s; process/wheel не повторялись, соответствующие механизмы не менялись. Текущее состояние — [project-status](../project-status.md); очередь — [roadmap](../roadmap.md).

Историческая дополнительная проверка после319suite: восьмой native test — два Orc free successes при нуле rolled successes у Skulker против actual Defenceless PC дают Backstabba Damage7 и ровно одну forced Wound. Отдельный test прошёл1OK/0.189s, production не менялся; не объявлять это единым320run. При завершении M34 проверены52current JSON request/result pairs и full source echoes;100прежнихJSON documents/25definitions/snapshots/Ability texts сохранены, кроме четырёх ожидаемых Help capability promotions.
