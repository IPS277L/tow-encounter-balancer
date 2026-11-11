# План разработки

Это очередь функций, а не журнал промежуточных шагов. Подробная [история этапов](roadmap-history.md) сохранена отдельно. Проверенные результаты и точка продолжения — в [статусе](project-status.md).

## Реализованная основа

- R1: разбор выбранных книг PG1.4/GM1.1, нормализованные правила и трассировка.
- K1: Test/Attack/Conditions/Wounds, магия и специализированные consumers; наличие consumer не означает интеграцию во все сценарии.
- M2–M7: ограниченные Minion-сценарии, независимые прогоны, подбор составов и JSON/CLI.
- M8: один Champion-Wizard/Curse, явные scene facts, opt-in continuations, native журнал, generation и текущий JSON6. Ограниченная веха завершена; [граница и приёмка](m8-completion.md).
- M9: один книжный PC/Staff или Sword против Minions, Wounds1–10, явный Fate decline, source-bound бой, trials, подбор численности и current JSON1/CLI. [Граница и приёмка ADR-0065](decisions/ADR-0065-first-pc-melee-encounter.md).
- M10: группа PC в общем owner/clock, отдельные ресурсы/раны, продолжение после частичных потерь, trials/статистика и fixed-party count search в той же PC JSON1 family. [Граница и приёмка ADR-0066](decisions/ADR-0066-pc-party-melee-encounter.md).
- M11: static numeric Brutes и mixed Minion/Brute reserve, source-bound profile Wounds до/на лимите, trials/подбор и явные policy/limit в текущем PC JSON1. [Граница и приёмка ADR-0067](decisions/ADR-0067-pc-melee-profile-brutes.md).
- M12: все PC Wounds11–23, body/hand consequences, Critical/Defenceless turns, source-aware ongoing Conditions и forced Wounds через тот же owner/trials/JSON1. [Граница и составная приёмка ADR-0068](decisions/ADR-0068-pc-heavy-wound-continuation.md).
- M13: явная Near Miss policy с порогом таблицы и резервом Fate; фактический burn в бою, независимые trials, расход ресурса в aggregate-only balance и текущем JSON1. [Контракт ADR-0069](decisions/ADR-0069-pc-near-miss-policy.md).
- M14: Glorious после actual initial roll для всех PC Test windows, отдельный session-spend резерв, совместимость с Near Miss в `configured`, новые costs в trials/balance и текущей JSON1. [Контракт ADR-0070](decisions/ADR-0070-pc-glorious-test-policy.md).
- M15: физический Melee Help для текущей атаки более позднего обычного PC, настоящие action/Test/Fate/heavy последствия, exact intended-Test applications и отдельные counts в trials/balance/JSON1. [Контракт ADR-0071](decisions/ADR-0071-pc-melee-help-policy.md).
- M16: Defence/Athletics Help для конкретного incoming Protection Test, явный target/skill, сохранение unused snapshot при смене Skill/NPC/no-Test и прежние trials/подбор/JSON1. [Контракт ADR-0072](decisions/ADR-0072-pc-protection-help-policy.md).
- M17: standard Recover выбранному союзнику, per-entity Conditions/источники/W13 consequences, mixed self/ally benefits, own pickup, реальные action counts и текущий JSON1. [Контракт ADR-0073](decisions/ADR-0073-pc-ally-standard-recover.md).
- M18: Dagger/Axe/Warhammer/Morning Star вместе со Staff/Sword, явные Damage/Traits, прежние hand/Help/Fate/Recover и fixed-party поиск через текущий JSON1. [Граница](rules/equipment.md#исполняемая-pc-граница-m18), [примеры](examples/m18/README.md).
- M19: семь двуручных Close weapons, typed BOTH grip, обе руки в drop/Recover/Critical12 и actual unsupported после завершённых ран16/18/20; прежние trials/process/поиск/JSON1. [ADR-0074](decisions/ADR-0074-pc-two-handed-close-weapons.md), [примеры](examples/m19/README.md).
- M20: явный1H backup к2H primary, own-turn incidental draw, active Damage/Traits/Help/Recover, carry/source/replay guards и прежние trials/process/search/JSON1. [ADR-0075](decisions/ADR-0075-pc-backup-weapon-policy.md), [примеры](examples/m20/README.md).
- M21: точные Footpad/Townsfolk боевые подпрофили GM1.1, независимые factories/metadata, защищённое book provenance и явный NPC Athletics/Defence через native/trials/process/подбор/JSON1. [ADR-0076](decisions/ADR-0076-first-pc-book-npc-catalog.md), [примеры](examples/m21/README.md).
- M22: Brigand Axe и применимый Craven Opportunist +2d вместо +1d, active/unselected metadata, actual superiority/GM/Drained и прежние native/trials/process/поиск/JSON1. [ADR-0077](decisions/ADR-0077-pc-brigand-craven-opportunist.md), [примеры](examples/m22/README.md).
- M23: Official Dagger Brute2, Broken на full first-Wound ACK, другие атаки/вторая рана до собственного хода и source-bound NPC stop перед неисполняемым бегством. [ADR-0078](decisions/ADR-0078-pc-official-first-wound-broken-boundary.md), [примеры](examples/m23/README.md).

## Последняя законченная функция

[M63 PC Protection choice](decisions/ADR-0105-pc-close-shooting-protection-choice.md) завершена: optional Melee/Athletics против Close Shooting, прежний default, actual hand/Traits/Fate и полный Melee Protection Help с отдельным intended ID. Source/current JSON1/trials/search/CLI проверены. [Примеры](examples/m63/README.md), [фактические результаты](project-status.md).

## M8 завершена

Ограниченная M8 прошла финальную регрессию и проверку установленного пакета. [Checklist](m8-completion.md) хранит точный scope и фактические результаты. Все Wounds/Miscasts и полный каталог spells не требуются для её закрытия: точные unsupported stops входят в исходный контракт.

Нового обязательного consumer или повторной проверки для закрытия M8 нет. Следующим направлением пользователь выбрал PC-сценарий ниже.

<a id="next-milestone-proposal"></a>

## M9 — первый книжный PC-сценарий

Направление выбрано пользователем 2026-11-04: **один немагический персонаж игрока против numeric Minions**, от заданного боя до массовой оценки и подбора численности. M9 по [ADR-0065](decisions/ADR-0065-first-pc-melee-encounter.md) завершена, включая full source и installed delivery. Это первый книжный PC-срез вместо P1 `wound_limit`; нижеследующие критерии сохраняют конечную границу M9.

Основания в коде: [NpcDefinition](../src/towr/domain/npc_roster_models.py) допускает только Minion/Brute/Champion; [Melee scenario](../src/towr/domain/npc_melee_scenario_models.py) — только Minions. M9 добавила отдельную книжную PC orchestration с [TestProfile](../src/towr/domain/test_models.py), [PLAYER injury](../src/towr/domain/injury_models.py) и [Fate kernel](../src/towr/domain/fate_models.py). PC не подменяется Champion или `wound_limit` из P1.

Граница: готовый PC с явными Characteristics/Skills, Resilience и Staff/Sword, без генерации персонажа; один обычный Melee-вариант, одна Zone, явные Close/awareness/порядок/выбор целей, конечный round budget, немагические Minions без дополнительных Abilities. Пользователь дополнительно выбрал поддержку Wounds1–10; случайный hand/drop, восстановление собственного оружия и Prone через Recover, temporary expiry и next-Test Grim входят в функцию. Treatment, campaign, mounts, общий inventory, все Talents и произвольные тактики сюда не включаются. Обязательная явно выбранная стратегия `DECLINE_OPTIONAL_FATE` сохраняет ресурс и source-bound окна PC.

Выполненные конечные критерии:

1. Самостоятельный PC definition/state, книжные профили и PLAYER injury policy; общий battle owner содержит PC и NPC, сохраняя источники и однократность переходов. Решение о владельце состояния оформлено одним ADR, без массового переименования NPC API.
2. Один непрерывный бой исполняет обычные атаки обеих сторон, PC Wound lifecycle/обязательные решения и завершение ходов. Неподдержанный эффект сохраняет фактический prefix и явный stop; victory/defeat не подменяются лимитом ран P1.
3. Детерминированные примеры показывают PC win, PC defeat, round limit, unsupported, а также фактическую PC Wound с сохранением её эффекта. Если эти исходы нельзя честно получить в выбранной границе, scope пересматривается до реализации цикла.
4. Независимые trials с source/seed parity и агрегатами; unsupported остаётся в общем знаменателе и исключает кандидата из итогового подбора. Балансировщик меняет только численность заданного enemy Minion reserve.
5. Один текущий JSON/CLI контракт, runnable пример и адресная проверка нужных слоёв. Наличие отдельных K1 reducers не считается исполнением всех PC правил; полный regression/installed audit назначаются на границе этой вехи по рискам.

Контракт PC roster, решений/Fate, initial-state admission и поддержанных Wounds закреплён и реализован через нужные слои одной функцией. Обязательного остатка для закрытия M9 нет.

Меньшая альтернатива — **объяснение unsupported в действующем Magic-балансировщике**. [Одиночный результат](../src/towr/domain/npc_magic_step_models.py) уже содержит typed reason/phase и недостающие scene facts; [trial record](../src/towr/simulation/npc_magic_models.py) и [summary](../src/towr/simulation/npc_magic_summary_models.py) теряют эту причину. Конечный срез альтернативы: current6 simulation/balance report показывает counts по причинам и воспроизводимый пример trial index/seed для каждой; сумма равна unsupported total, sequential/process диагностика совпадает, полный journal в balance не передаётся, правила/исходы/selection не меняются. Это улучшает нынешний инструмент, но не добавляет PC.

Пользователь выбрал PC-сценарий; diagnostics остаётся самостоятельной возможностью дальнейшего backlog и не добавляется в M9 автоматически.

## M10 — бой группы PC против Minions

Пользователь поручил продолжить рекомендованное направление после M9. [ADR-0066](decisions/ADR-0066-pc-party-melee-encounter.md) закрепляет конечную границу: uniform roster PC, общий бой/clock, индивидуальные Fate/раны/оружие/expiry, явные порядки и приоритеты целей, dynamic outnumbering обеих сторон. Смерть отдельного PC не завершает бой оставшейся группы. Trials сохраняют подтверждённые потери по персонажам; подбор фиксирует всю party и меняет только Minion counts. Текущие PC JSON1/CLI обновляются без поддержки прежней одиночной формы.

Веха завершена и проверена; обязательного остатка в этой границе нет. Фактические результаты и локальные logs находятся в ADR-0066.

Конечные критерии — source-bound party battle, независимые прогоны/потери, aggregate-only подбор, строгий wire и работающие примеры. Оружие, Wounds1–10, self Recover и Fate decline остаются в границе M9; новые тактики, ally Recover, активное Fate и прочие Wounds не добавляются автоматически.

## M11 — Minions и static-profile Brutes против группы PC

Завершена по [ADR-0067](decisions/ADR-0067-pc-melee-profile-brutes.md). Явные `injury_policy`/`wound_limit` каждого NPC, nonterminal Wounds без table/lifecycle PC, сохранение живого Brute в очереди и последующий defeat с GM disposition. Существующий общий бой/подбор/JSON1 принимает смешанный reserve; состав party и поддержка её ран/Fate прежние. Профили с on-Wound behaviour, Abilities и другие типы NPC не входят. Конечная функция включает typed source guards, trials/process, count search, строгий wire и runnable mixed examples. Обязательного остатка в этой границе нет.

## M12 — все тяжёлые PC-раны

Пользователь выбрал все11–23 и продолжение Attack/Recover с книжными осложнениями по [ADR-0068](decisions/ADR-0068-pc-heavy-wound-continuation.md). Функция завершена: actual mandatory follow-ups, Critical end-turn Tests/Defenceless incapacity turns, forced Wounds, source-aware ongoing Conditions и bounded hand/body facts. Единичные строки больше не останавливают бой; физически невозможная повторная анатомия сохраняет точный pending GM-stop. Текущая PC JSON1 требует `random_side_policy` и `heavy_wound_policy`, без прежнего hand-only shape. Общий риск K1 проверен checkpoint regression; обязательного остатка M12 нет.

## M13 — активный Near Miss

Завершённый срез по [ADR-0069](decisions/ADR-0069-pc-near-miss-policy.md): caller задаёт включительный порог таблицы и минимальный остаток rating. Фактический K1 burn/application разрешается до регистрации/эффектов раны и terminal defeat; supplies сохраняются, owner доказывает каждый расход. Последовательные и процессные trials/aggregate-only count search отражают новые burns отдельно от supplied истории. Текущий PC JSON1 и прежние примеры обновлены вместе. Общий AI, другие Fate options и изменение функции ранжирования сюда не входят.

## M14 — обычные траты Fate на Glorious

Завершённый срез по [ADR-0070](decisions/ADR-0070-pc-glorious-test-policy.md): явные выбранные навыки, порог собственных initial successes и session-spend резерв; все текущие PC Test windows, включая Wound/Critical Endurance. Исходные кубы не бросаются заново, выбор не смотрит на opposing outcome, Grim отменяется до rerolls. Owner хранит полный spend→burn prefix; текущий JSON1 требует обе nullable policies с общим mode `configured`. Costs отдельно проходят независимые trials/process/aggregate-only search и CLI. Другие Fate options/optimal AI не включены.

## M15 — Help между PC

Завершённый срез по [ADR-0071](decisions/ADR-0071-pc-melee-help-policy.md): роль помощника задаёт одного более позднего обычного PC; physical Melee Help предназначен для его конкретной Attack текущего раунда. Настоящий action/Test/Glorious, next-Test/hand/heavy/end-phase последствия, zero/multiple/capped applications, typed source/replay guards и unused бонус при ранней победе. Нет mutable банка и переназначения Test. Trials/process/count search и текущий JSON1 отражают actual Help отдельно от Fate; старые12JSON-пар мигрированы без смены gameplay. Clock PC-side→NPC-side сохраняется. Обязательного остатка M15 нет.

## M16 — Help защите союзника

Завершённый срез по [ADR-0072](decisions/ADR-0072-pc-protection-help-policy.md): явные target и Defence/Athletics, первый текущий live NPC при совпадении ожидаемой цели, exact beneficiary/Test/Skill applications в original Protection options до собственного Glorious. Гибель NPC, смена оружия/Skill и Defenceless не переназначают snapshot. Protection beneficiary может уже завершить ход. Новых counters/owner bank/version нет; generation сохраняет authored configuration при удалении NPC. Старые14JSON-пар мигрированы/проверены без смены gameplay. Обязательного остатка M16 нет.

## M17 — стандартный Recover союзнику

Завершённый срез по [ADR-0073](decisions/ADR-0073-pc-ally-standard-recover.md): fixed beneficiary любого порядка/роли, self-required priority, иначе ally-first по Staggered/Prone benefit, mixed recipients и own pickup. Оngoing причины не удаляются, Critical13 получает фактически поднятый PC; receiving aid не становится действием14/15. Full canonical proof и общий pure completion сохраняют источник/slot/clock; actual allied action counts проходят indexed trials/process/aggregate-only search и JSON1. Opening-round/joint support budgets и exact outer result type проверены. Старые16JSON-пар мигрированы с null/нулями без смены gameplay. Обязательного остатка M17 нет.

## M18 — первый дополнительный набор PC-оружия

Завершённый конечный срез: Dagger, Axe, Warhammer, Morning Star — все1H/Close, вместе с прежними Staff/Sword. Книжные свойства используют текущие Test/Damage modifiers, full canonical source и прежние Help/Fate/Recover/Wounds. Допуск/enum схемы расширены в том же JSON1; метрики не меняются. Отдельный ADR для повторного применения этих механизмов не требуется. Обязательного остатка M18 нет.

## M19 — двуручное Close-оружие

Завершённый конечный срез по [ADR-0074](decisions/ADR-0074-pc-two-handed-close-weapons.md): Pickaxe/Flail/Billhook/Halberd/Glaive/Greataxe/Greathammer, обе руки в Attack/Defence/weapon-assisted Help, whole-item drop и Recover/Critical12. Пользователь выбрал сохранять полную рану16/18/20 и останавливать trial при недоступном2H хвате. Перед stop выполнены Near Miss и все immediate consequences, далее journal не продолжается. Enum/grip correlation обновлены в том же JSON1; старые пары не мигрируются.

## M20 — запасное одноручное оружие

Завершённый срез по [ADR-0075](decisions/ADR-0075-pc-backup-weapon-policy.md): nullable1H backup с предпочтением руки только при2H primary/Strength≥2. Draw выполняется в свой ход после фактической утраты2H возможности, без ранней защиты или обхода Defenceless. Отдельный proof сохраняет Critical12/14/15; затем действуют Traits/Help/Recover активного backup. Вернуть primary нельзя. Если до draw не осталось рук, stop сохраняет фактический источник; после draw действует прежняя1H граница. Метрики/version неизменны, поле policy обязательно nullable в JSON1.

## M21 — первые книжные NPC в PC balance

Завершённый срез по [ADR-0076](decisions/ADR-0076-first-pc-book-npc-catalog.md): Footpad GM97 и Empire Townsfolk GM96, напечатанные боевые значения, exact identities/fresh factories и metadata Lurker/Streetwise вне текущей сцены. NPC Protection теперь явно Athletics/Defence; текущий JSON1 требует Skill. Старые24пары мигрированы с Defence без смены gameplay; версия/метрики не менялись.

## M22 — Brigand Axe / Craven Opportunist

Завершённый срез по [ADR-0077](decisions/ADR-0077-pc-brigand-craven-opportunist.md): выбранный Axe loadout с сохранённым unselected Warbow, exact printed профиль, +2d вместо +1d только при actual superiority и GM approval. Считаются все пригодные союзники, потери меняют бонус сразу. Старые NPC/PC сохраняют обычные правила, Drained filter прежний. Current JSON1/метрики не изменены; metadata Python API явно разделяет active/inactive Abilities.

## M23 — первый книжный Brute / Official Dagger

Завершённый срез по [ADR-0078](decisions/ADR-0078-pc-official-first-wound-broken-boundary.md): точный Brute2/Dagger/Athletics с unselected Pistol, Wound bands0/1/2 и Broken на living0→1 ACK. Пользователь выбрал остановку перед actual own Broken turn; другиеPC/Defence и обязательные end phases продолжаются до этого окна. W2 до окна — обычный defeat, неподдержанное бегство не подставляется. Source-bound NPC cause не использует PC Wounds Table; JSON1/метрики прежние.

## M24 — выход Broken NPC из arena

Завершённый срез по [ADR-0079](decisions/ADR-0079-pc-broken-npc-adjacent-exit.md): явный clear/fastest adjacent safe exit, actual own-turn FreeMovement, withdrawal без fake TurnEnd/action/defeat. W1/Broken сохраняются; вышедший NPC исключён из целей/численности/Help/следующих ходов. Пользователь выбрал objective «все побеждены или ушли», уход учитывается отдельными source-ordered trial/summary counts и success-with-exit count. Current JSON1 требует nullable policy и метрики, старые30пар мигрированы с null/нулями без изменения прежних значений. Преследование/Recover/возврат не включены.

## M25 — Empire State Trooper / Halberd и Defence

Завершённый срез по [правилу](rules/npc-profile-catalog.md#state-trooper-m25): пятый exact combat loadout, Minion/T3/Res4 armoured, Halberd Close3d/3Damage5/2H и фиксированная Defence3d/4. Числовая Athletics3d/3 и остальные weapons явно unselected, полный Supporting Action trigger сохранён как inactive в неподвижной Close-сцене. Factory → native → trials/count search → current JSON1/CLI проходит существующими слоями без нового kernel/owner/формата. Старые четыре definitions/snapshots и32примера неизменны; [новые примеры](examples/m25/README.md).

## M26 — чанк Artisan, Bretonnian Squire и Elf Merchant

Завершённый чанк по [правилу](rules/npc-profile-catalog.md#catalog-chunk-m26): три exact Close loadouts, printed Protection, full inactive Abilities и Merchant first-Wound Staggered на existing profile ACK. Старая Staggered снимается самой Wound до нового profile Staggered, немедленного W2 нет; следующий отдельный repeated-Staggered может дать W2. Обычный NPC turn продолжается. Общий путь factory/native/trials/8count-compositions/current JSON1/CLI проверен без нового owner/формата/метрик; [общие примеры](examples/m26/README.md). Прежние пять профилей и34пары сохранены.

## M27 — natural Melee и чанк Horse/Giant Wolf/Giant Boar

Завершённый срез по [ADR-0080](decisions/ADR-0080-natural-melee-attacks-and-creature-chunk.md), выбранный пользователем: явный required hands=null для natural Melee, unarmed fresh NPC/Athletics, actual PC equipment в Protection и исполняемый Wolf Give Ground ban. Три unmounted Fast Minions используют printed атаки/броню; riders/Charge/optional Horse variants не подставляются. PG97 подтверждает обычные PC armour bonuses по natural armour Boar. Current PC JSON1 допускает null без миграции прежних1h/2h inputs; другие bounded families сохраняют enum-only admission/codec. [Общие примеры](examples/m27/README.md).

## M28 — Gor dual axes, Chaos Warhound и Orc Boy Choppas

Завершённый совместимый чанк по [правилу](rules/npc-profile-catalog.md#beast-orc-chunk-m28): Gor fixed dual axes/noShield с +1d Melee при selfStaggered и одним отдельным dualDamage+1; Warhound printed3d/3 natural и actual GGban; Orc printed2H/Damage4/Defence3d4 без щита. GM93 shield−1 явно сохранён в definitions (GorT4/Res4,OrcT4/Res5). Terrain/Charge/Help abilities сохранены inactive в неподвижной fixed Attack сцене. Общие typed modifiers/kernel/current JSON1/trials/process/8составов используются без новой формы контракта, ADR или DSL. [Общие примеры](examples/m28/README.md); прежние11профилей/38пар сохранены.

## M29 — on-hit Drained, Giant Spider и White Wolf

Завершённый срез по [ADR-0081](decisions/ADR-0081-pc-on-hit-drained-and-independent-condition-sources.md), выбранный пользователем: независимые hit sources и два совместимых существа вместо искусственного заполнения квоты3–5. On-hit Drained сохраняется после Near Miss/W6expiry/standard Recover и не меняет прошлые Tests. Giant Spider передаёт typed descriptor в K1; White Wolf W1Drained/ClampingGGban использует existing profile ACK. PC сохраняют нынешнюю Attack/standard Recover стратегию; альтернативного Endurance решения нет. Current PC JSON1 требует явный secondary_effects[]/descriptor;80старыхJSON documents мигрированы без изменения прежних наблюдений. [Общие примеры](examples/m29/README.md).

## M30 — три Brutes с W1 Drained

Завершённый совместимый чанк по [правилу](rules/npc-profile-catalog.md#brute-chunk-m30): пешие Empire Knight/Lance и Knight of the White Wolf/Wolf Hammer, Big ’Un/Choppas. Existing W1Drained/W2defeat ACK распространяется конечным whitelist, ordinary turns/Drained bonus filter продолжаются. Printed Defence и Armour сохранены, щиты не выбраны, mounted/Charge/Help triggers отсутствуют в фиксированной сцене. Общие [factory/JSON1/CLI-примеры](examples/m30/README.md), trials и8составов проверены; новые wire поля/стратегии/ADR не понадобились.

## M31 — Goblin Warrior, Nasty Skulker и Night Goblin

Завершённый выбранный пользователем чанк по [ADR-0082](decisions/ADR-0082-pc-goblin-melee-chunk.md): Spear+shield Warrior/Night и Long knives Skulker. Dirty Coward даёт explicit defeat без Wound/GM disposition и один weapon-drop ACK; Backstabba меняет multiplier только для unopposed Melee, включая actual Defenceless. Щиты и printed maximum Short передаются через required holds_shield/range_max в current PC JSON1, бой остаётся Close. [Примеры](examples/m31/README.md) и8составов используют прежний owner/trials/метрики.88старыхJSON documents мигрированы без изменения прежних значений; Net отложена.

## M32 — Empire Peasant, Town Watch и Free Company Militia

Завершённый совместимый чанк по [правилу](rules/npc-profile-catalog.md#empire-chunk-m32): Peasant Make-Shift Weapons, Watch Polearm/maxShort и Militia Improvised Blades, printed Athletics/gear. Полные Help/Whistleblower/Detachment условия сохранены вне fixed Attack/noMove сцены; fresh/no_external_effects также исключает предбоевые bonuses/уже вызванное подкрепление. Общие [factory/JSON1/CLI-примеры](examples/m32/README.md), trials и8составов проверены без новых полей/версии/owner/ADR. Старые22profiles и92JSON documents сохранены. После Net source review использована ранее указанная каталоговая альтернатива; тактика Net не подставлялась.

## M33 — несколько явных NPC Help пар

Завершённая выбранная пользователем функция по [ADR-0083](decisions/ADR-0083-pc-npc-automatic-help-policy.md): Peasant/Militia тратят standard action без Test и создают source-bound+1d bypass для конкретной поздней Melee attack. Multiple helpers/no chains/fixed Attack fallback и filtering обоих endpoints проходят native journal/trials/count search/current JSON1. PC costs прежние, NPC Help учитывается отдельно;96старыхJSON documents мигрированы []/нулями, без новых wire versions/AI. [Примеры](examples/m33/README.md).

## M34 — Horde и Power of the Waaagh!

Завершённая функция по [ADR-0084](decisions/ADR-0084-pc-greenskin-automatic-help.md): те же явные пары доступны четырём уже имеющимся greenskin loadouts. Закрытый тип automatic Help различает uncapped die и free success; mixed receipts/replay/Test success trace/Drained проходят native/trials/подбор/current JSON1. Пользователь выбрал Orc Help для Drained beneficiary при прежнем Attack fallback у dice helpers. Новых wire fields/метрик нет, каталог25loadouts,100прежнихJSON documents сохранены. [Правило](rules/npc-profile-catalog.md#greenskin-help-m34), [примеры](examples/m34/README.md).

## M35 — Cultist, Elf Militia и Ungor

Завершённый чанк трёх новых Minions по [правилу](rules/npc-profile-catalog.md#minion-chunk-m35): Cultist Warhammer с действующим no-Test dice Help, Elf Militia Spear2H/maxShort с полным dormant back-rank trigger, Ungor Crude Spear/shield с actual target Staggered+1d. Обычный cap/Drained/printed Damage и прежний Help/search/JSON1 путь сохранены. Каталог25→28; прежние25entries и104JSON documents не меняются. [Общие примеры](examples/m35/README.md), новых полей/версии/метрик/ADR нет.

## M36 — три копейных loadouts

Завершённый чанк по [правилу](rules/npc-profile-catalog.md#spear-chunk-m36): State Trooper/Spear, Orc Boy/Jagged Spear+shield, Big ’Un/Jagged Spear+shield. Printed1H/Short/Defence3d4/Res4или6 и Damage3/3/4 сохранены. Inherited Power/W1Drained работают в прежнем owner; Supporting Action/Spear Charge не вызываются в фиксированной сцене. [Общие примеры](examples/m36/README.md), native/trials/search/current JSON1 без новых полей/версии/метрик. Каталог28→31; старые28entries/108JSON documents сохранены.

## M37 — wound rage и Devour the Fallen

Завершённый чанк трёх loadouts по [ADR-0085](decisions/ADR-0085-pc-devour-and-wound-rage.md): Razorgor natural, Minotaur Single Axe/Dual Axes. Brute3 W1/W2 дают ordinary+1/+2d Melee; Devour связывает один table die с actual pre-Attack Staggered/Prone/Wounded target через existing Kernel/Wound/Fate. Printed Damage5 и отдельный dual+1, Drained/Test cap versus table dice, direct/repeated-Staggered/Defenceless/Near Miss/source guards проверены. [Примеры](examples/m37/README.md), current JSON1 без новых полей/метрик. Каталог31→34; старые31entries/112JSON documents сохранены. Greataxe unselected до корректного cap8/source решения.

## M38 — canonical cap8 и Minotaur Greataxe

Завершена выбранная пользователем узкая граница [ADR-0086](decisions/ADR-0086-pc-minotaur-greataxe-pool-cap.md): explicit cap8 только Attack canonical Minotaur Greataxe3d5Damage8/2H, authored/прочие book/Protection profiles сохраняют null. Required поле уже было в JSON, поэтому codec/116прежнихJSON documents без миграции, версия/метрики прежние. W0–3/Rage/Devour/ordinary cap/bypass/typed source проходят native/trials/search/current JSON1. [Правило](rules/npc-profile-catalog.md#greataxe-cap-m38), [CLI-примеры](examples/m38/README.md). Каталог34→35; старые34entries сохранены.

## M39 — Bear / Enduring Strength

Завершена выбранная пользователем функция по [ADR-0087](decisions/ADR-0087-pc-bear-second-attack-policy.md): обязательный список Bears и существующий приоритет других живых PC после успешной первой Attack и всех её последствий. Canonical Sweeping Claws/W1–2Drained, реальный ability slot2/receipt/уникальные Tests, один TurnEnd, actual extra-action costs проходят native/trials/count search/current JSON1/CLI. Третьего действия и переноса Help нет. [Правило](rules/npc-profile-catalog.md#bear-second-attack-m39), [примеры](examples/m39/README.md). Каталог35→36;120старыхJSON documents мигрированы обязательными `[]`/нулями без изменения прежних значений.

## M40 — Demigryph, Centigor и White Wolf Claws

Завершён совместимый чанк по [правилу](rules/npc-profile-catalog.md#creature-chunk-m40): unmounted Demigryph/Wicked Claws, Centigor/Jagged Spear+shield и White Wolf/Rending Claws. Centigor W1Prone применяется на actual profile ACK, NPC продолжает Attack, следующие PC получают higher ground; Demi/Wolf используют existing W1Drained. Claws не наследуют Clamping GG-ban, rider double attack и Charge Abilities не подставляются. Native/trials/8count-compositions/current JSON1/CLI проходят прежними слоями без новых полей/метрик/версии/ADR. [Общие примеры](examples/m40/README.md), каталог36→39; старые36entries/124JSON documents сохранены.

## M41 — щитовые Gor и Empire Knight

Завершён чанк по [правилу](rules/npc-profile-catalog.md#shield-chunk-m41): Gor/single Crude Axe+shield и пеший Empire Knight/Lance+shield с printed Res5/6. Self-Staggered Primal Rage не переносит dual Damage; Knight W1Drained/W2defeat продолжается existing ACK. Полные forest/Charge/mounted Abilities сохранены с прежними условиями. Native/trials/4count-compositions/current JSON1/CLI проходят без новых полей/метрик/версии/ADR. [Примеры](examples/m41/README.md), каталог39→41; старые39entries и128JSON documents сохранены.

## M42 — Brewguard и source-aware NPC Distracted

Завершена выбранная пользователем функция по [ADR-0088 A](decisions/ADR-0088-pc-brewguard-distracted-focus.md): actual first-Wound attacker становится focus раненого Brewguard;−1d только против других PC, confirmed death после Wound/Fate снимает эффект, Defenceless сохраняет. Typed source bank/profile ACK/expiry proof, prepared Melee/Protection, native/trials/count search/current JSON1/CLI замкнуты; W1 не накладывает эффект повторно, expiry не расходует action/RNG. [Правило](rules/npc-profile-catalog.md#brewguard-distracted-m42), [примеры](examples/m42/README.md). Каталог41→42; старые41entries/132JSON documents без миграции. Другие Distracted sources/Recover/visibility остаются отдельно.

## M43 — Miner и явные grudge relationships

Завершена выбранная пользователем функция по [ADR-0089](decisions/ADR-0089-pc-miner-grudge-policy.md): required `npc_grudge_policies` задаёт пары Miner→PC, initial encounter proofs накладывают Distracted до первого хода без action/RNG. Melee против focus получает+1d, против других Tests действует−1d; target priority прежний. Confirmed death снимает Condition после Fate, не переназначает связь и не вызывает reapply. Down in the Dark запрещает только enemy higher-ground bonus. Native/trials/count search/current JSON1/process parity/CLI замкнуты. [Правило](rules/npc-profile-catalog.md#miner-grudge-m43), [примеры](examples/m43/README.md). Каталог42→43;136прежнихJSON documents мигрированы required пустыми arrays без изменения остальных значений, старые42entries сохранены.

## M44 — Halfling Thief и canonical Stealth Protection

Завершена выбранная пользователем функция по [ADR-0090](decisions/ADR-0090-pc-halfling-stealth-protection.md): Thief/Dagger со Stealth3d5, отдельное source-bound permission Now You See Me и прежняя unaware/Defenceless precedence. Typed preparation/actual target/replay, native/trials/count search/current JSON1/CLI замкнуты; остальные authored/book profiles сохраняют прежний допуск. Новых wire полей/версии/метрик нет. [Правило](rules/npc-profile-catalog.md#halfling-stealth-m44), [примеры](examples/m44/README.md). Каталог43→44;43прежнихentries и140JSON documents сохранены без миграции. Один профиль проверяет новую Protection механику.

## M45 — Sharpshooter/Axe и три варианта без щита

Завершён совместимый чанк по [правилу](rules/npc-profile-catalog.md#melee-loadout-chunk-m45): новый Hochland Sharpshooter/Axe, single Gor без щита, Orc Boy/Big ’Un Spear без щитов. Existing Rage/free-success Help/W1Drained сохраняют свои правила; Cancel Aim Sharpshooter не создаёт эффекта при отсутствующем Aim в fixed Axe-only сцене. Native/trials/count search16составов/current JSON1/CLI замкнуты. Новых полей/версии/метрик/тактики/ADR нет. [Общие примеры](examples/m45/README.md). Каталог44→48;44прежнихentries и144JSON documents сохранены без миграции.

## M46 — Bestigor / Blood Rage и следующая Glorious Attack

Завершена выбранная пользователем функция по [ADR-0091](decisions/ADR-0091-pc-bestigor-blood-rage-and-wound-glorious.md): required named Rage list, typed pre-Test Staggered proof, ordinary+1d от фактического Staggered независимо от списка и ровно следующая Glorious Attack после actual W1 ACK. Пользователь выбрал reroll всех доступных провалов; typed source связывает actual Wound и потребившую Attack в history без нового mutable bank. Native/trials/count search/current JSON1/process parity/CLI замкнуты; W2 до хода не создаёт фиктивного действия. [Правило](rules/npc-profile-catalog.md#bestigor-blood-rage-m46), [примеры](examples/m46/README.md). Каталог48→49;148старыхJSON documents мигрированы required пустыми arrays без изменения остальных значений,48прежнихentries сохранены. Explicit cap8 теперь только canonical Bestigor Massive Axe и Minotaur Greataxe.

## M47 — Flagellant/Flails и Hooks and Chains с Feel No Pain/Recover

Завершён полный выбранный пользователем срез по [ADR-0092](decisions/ADR-0092-pc-flagellant-feel-no-pain-and-recover.md): оба loadouts, first-Staggered→Wound при0 по явной policy, отдельный own-miss witness, настоящий standard self Recover/heal1→0 и независимые NPC costs. Flails−2/Unbreakable, Help fallback, source/replay/циклы лечения замкнуты через K1/owner/trials/search/current JSON1/process/CLI. [Правило](rules/npc-profile-catalog.md#flagellant-feel-no-pain-m47), [примеры](examples/m47/README.md). Каталог49→51;152старыхJSON мигрированы только required policies/нулевыми Recover fields,49прежнихentries сохранены.

## M48 — Skin Wolf и Warped Form end phase

Завершён полный выбранный пользователем [ADR-0093](decisions/ADR-0093-pc-skin-wolf-warped-form-end-phase.md): Blood Rage, собственный Staggered/heal1, source-ordered Close wave с отдельными PC/NPC continuation owners и одним TurnEnd. Wave-W1/Brewguard NPC focus/confirmed killed expiry, Bestigor Glorious, Dirty Coward, Feel No Pain и последующий Recover имеют настоящие причины. Current PC JSON1 требует explicit Close policies и отдельные activation counters; activation не action/Recover. Каталог51→52,156старыхJSON мигрированы только новыми полями. [Правило](rules/npc-profile-catalog.md#skin-wolf-warped-form-m48), [примеры](examples/m48/README.md).

## M49 — Imperial Ogre / Greathammer и наземный Pegasus

Пользователь выбрал оба профиля по [ADR-0094](decisions/ADR-0094-pc-imperial-ogre-cap-and-grounded-pegasus.md). Ogre сохраняет printed2d4Damage8/2H с source-bound cap6 отWS3; Pegasus naturalHooves/Athletics начинает и остаётся на земле. W1/Speed/fly bands сохраняются в неподвижной сцене без выдуманных actions. Canonical guard/schema допускают6 только Ogre Attack; прежние8/null сохранены. Каталог52→54,52прежнихпрофиля/160JSON без изменений и миграции. [Правило](rules/npc-profile-catalog.md#ogre-grounded-pegasus-m49), [примеры](examples/m49/README.md).

## M50 — Bear / Crushing Weight и ранний Prone

Выбранный пользователем полный [ADR-0095](decisions/ADR-0095-pc-bear-crushing-weight-pre-stagger-prone.md) реализован: natural3d3Damage7/cap8, typed K1 Prone-before-Stagger в PC owner/current JSON1, existing Enduring Strength для обоих Bear loadouts. Canonical effective Wound source сохраняет early Prone при Near Miss; ordinary self/ally Recover снимает его без возврата из Drained history bank. Новых полей верхнего уровня/метрик/версии нет. Каталог54→55,54прежнихпрофиля/164JSON сохранены без миграции. [Правило](rules/npc-profile-catalog.md#bear-crushing-weight-m50), [примеры](examples/m50/README.md).

## M51 — Great Stag, Crown и Trample

Завершённый срез по [ADR-0096](decisions/ADR-0096-pc-great-stag-crown-and-trample.md): два полных natural profiles, Brawn/cap10/PC Endurance Trample, отдельный typed Crown grant только после actual нового Prone от последствий первой Antlers Attack. Та же живая Prone цель без retarget, полный Wound/Fate/Endurance prefix, один TurnEnd. Conditional trample_attack только canonical Great Stag,55прежнихпрофилей/168JSON сохранены, каталог56. [Правило](rules/npc-profile-catalog.md#great-stag-crown-trample-m51), [CLI-примеры](examples/m51/README.md).

## M52 — Weighted Net и carried Spear

Завершённая выбранная функция по [ADR-0097](decisions/ADR-0097-pc-weighted-net-and-carried-spear.md): primary Throwing→Burdened, finite stock1, actual HIT/MISS расход, typed free draw/swap и дальнейшая Spear Attack. По Defenceless/уже Burdened — Spear с сохранением Net. PC сохраняет прежнюю тактику. NoShield Night Goblin сохраняет Res3 armoured через явный marker; closed conditional JSON1 сохраняет56прежнихprofiles/172JSON. Horde/Dirty Coward, полные echoes и subset filtering проверены. [Правило](rules/npc-profile-catalog.md#night-goblin-net-spear-m52), [примеры](examples/m52/README.md).

## M53 — PC со щитом

Завершённая функция по [ADR-0098](decisions/ADR-0098-pc-shield-and-hand-equipment.md):1H+shield, actual drop/body/held/unavailable hands, dynamic+1Resilience/Protection/Sword Trait, weapon-first release и отдельный Recover для dropped shield при свободной здоровой руке. Один object interaction, weapon pickup первым;16/20 не изобретают ground location,12 не возвращает shield в травмированную руку. Protection Help/Fate, canonical journal и current JSON1 сохраняют старые176JSON/NPC57. [Правило](rules/equipment.md#pc-shield-m53), [примеры](examples/m53/README.md).

## M54 — PC Pistol и Exacting Reload

Завершена выбранная пользователем функция по [ADR-0099](decisions/ADR-0099-pc-pistol-and-exacting-reload.md): initially loaded Pistol без shield/backup, явные BS/Shooting/I/Dexterity/Lore/kit/supplies, Shoot→Reload3→Shoot и принятая two_available_hands policy. Каждый Reload занимает Improvise/Skill action, HIT/MISS расходует настоящий weapon instance/cycle; раны/Fate/Recover не заряжают его автоматически. Loaded one-hand shot сохраняется до действительно недоступного Reload. Lawful NPC Protection проверяется до RNG, Melee Help даёт fallback, actual Protection Help сохраняется. Native/trials/count search/current JSON1/CLI и один actual process проверены;180прежнихJSON и каталог57 сохранены. [Правило](rules/equipment.md#pc-pistol-reload-m54), [примеры](examples/m54/README.md).

## M55 — Pistol со щитом

Завершена выбранная пользователем функция по [ADR-0100](decisions/ADR-0100-pc-pistol-shield-reload-priority.md): existing Pistol+Shield loadout, необходимый weapon/Prone Recover → release перед доступным Reload → Reload до готовности без shield pickup → отдельный shield Recover перед следующим Shoot. Incidental pickup также подавлен при empty Pistol; W12/14/15/16/18/20 сохраняют actual hand/Critical/loaded one-hand stop boundaries. Current JSON1 без новых полей/версии/counters,184прежнихJSON и каталог57 сохранены. [Правило](rules/equipment.md#pc-pistol-shield-m55), [примеры](examples/m55/README.md).

## M56 — NPC Protection против Close Shooting

Завершена выбранная пользователем функция по [ADR-0101](decisions/ADR-0101-pc-close-shooting-npc-protection-choice.md): optional actor→Melee/Athletics policy для State Trooper Halberd/Spear, unmounted no-shield Empire Knight/Lance и Knight of the White Wolf/Wolf Hammer. Melee3d3/4d4, printed Athletics3d3/2d3; Knights cap6 от Ag3 без второго armour penalty. Прежняя Defence против входящего Melee не меняется, counterattack/новый slot не появляется. Full template admission, subset filtering, native/trials/search/current JSON1/CLI и actual process проверены.188прежнихJSON и57выбранных definitions сохранены. [Правило](rules/combat.md#pc-close-shooting-protection-m56), [примеры](examples/m56/README.md).

## M57 — Greenskin Close Shooting Protection

Завершён чанк четырёх существующих loadouts по M56 образцу: Orc Boy Choppas/Spear и Big ’Un Choppas/Spear без щитов. Melee3d/4 и Athletics3d/3, оба cap6; Big ’Un S4 не увеличивает WS3. Power of the Waaagh! остаётся Attack-bound, Charge/PC Traits не становятся защитными. Изменён только canonical factory; прежние policy/source/codec/generation/Help receipts неизменны. Native/trials/search/current JSON1/CLI проверены,192прежнихJSON и каталог57 сохранены. [Правило](rules/combat.md#pc-close-shooting-protection-m57), [примеры](examples/m57/README.md).

## M58 — special NPC Close Shooting Protection

Завершён следующий чанк по прежней policy: Nasty Skulker, Brewguard/Warhammer, Miner/Pickaxe и Bestigor/Massive Axe, всего12sources. Реальная Melee protection Miner получает generic grudge против focus; Distracted/Drained ограничивают соответствующие Tests. Blood Rage/nextAttack Glorious Bestigor и Backstabba Skulker остаются Attack-only. Alternate Athletics Miner/Bestigor исправлены на cap4/cap8 по исходной Ag; все57selected definitions и196прежнихJSON сохранены. Native/trials/search/current JSON1/CLI проверены; нового wire/state/тактики нет. [Правило](rules/combat.md#pc-close-shooting-protection-m58), [примеры](examples/m58/README.md).

## M59 — Pistol против Thief Stealth

Завершена source-bound интеграция исходной Halfling Thief/Dagger Stealth3d5/cap6 в Pistol preflight по прежнему M44 permission. GM103 покрывает aware Shooting, Unaware/Defenceless precedence/полный actor/definition Test source сохранены. Новых wire fields/версии/тактики/Stealth действий нет. Actual Shoot/Reload/mixed party, source/replay, sequential services/count search/current JSON1/CLI проверены;200прежнихJSON сохранены. Protection paths теперь покрывают57selected loadouts:44обычных,12Melee/Athletics policy,1typed Stealth. [Правило](rules/combat.md#pc-close-shooting-protection-m59), [примеры](examples/m59/README.md).

## M60 — Pistol → melee backup

Завершена выбранная пользователем функция по [ADR-0102](decisions/ADR-0102-pc-pistol-melee-backup.md): carried1H backup из6существующих weapons/optional shield/Strength≥2. Только empty Pistol + одна пригодная рука запускают односторонний incidental draw на своём незанятом ходу после mandatory последствий и нужного shield release. Loaded shot/необходимый Recover и доступный Reload сохраняются. Actual Skill/Damage/Traits/Protection/Help используют backup, owned gun instance/loaded/progress/cycle не сбрасываются. Native/source/schema/services/CLI и один actual process проверены;204прежнихJSON/каталог57 сохранены. [Правило](rules/equipment.md#pc-pistol-backup-m60), [примеры](examples/m60/README.md).

## M61 — NPC Pistol + Exacting Reload

Завершена выбранная функция по [ADR-0103](decisions/ADR-0103-pc-npc-pistol-and-exacting-reload.md): два Brute loadouts Official/Pistol и Ogre/Ogre Pistol, initially loaded Shoot→Reload3→Shoot с explicit GM facts/двумя руками. Real actor/instance/cycle/progress, отдельные actions, PC Protection/Fate/Wounds, Official Broken/exit и Ogre bands сохраняются. Closed per-enemy source/current JSON1, trials/count search/CLI/один actual process проверены. Без shield/backup/NPC Help к новым стрелкам;208прежнихJSON/57definitions сохранены, каталог59. [Правило](rules/npc-profile-catalog.md#npc-pistol-reload-m61), [примеры](examples/m61/README.md).

## M62 — NPC Help к Shooting

Завершена выбранная функция по [ADR-0104](decisions/ADR-0104-pc-npc-shooting-help.md): Militia и три Goblin/Night Goblin helpers к Official/Ogre Pistol, loaded → Skill-bound no-Test Help, empty/Reload → собственный Attack. Multiple receipts/cap bypass/Drained/Net stock/costs/replay/source filtering сохраняются; Peasant/Cultist/Waaagh! остаются Melee-only. PC Protection Help не предсказывает NPC policy. Native/JSON/services/search/CLI проверены,212прежнихJSON/59definitions сохранены. [Правило](rules/npc-profile-catalog.md#npc-shooting-help-m62), [примеры](examples/m62/README.md).

## M63 — PC Protection choice против Close Shooting

Завершён полный выбранный путь по [ADR-0105](decisions/ADR-0105-pc-close-shooting-protection-choice.md): optional melee/athletics, без поля shield Defence/иначе Athletics; weaponless PG94 permission и actual usable grip/no-hand способ. Общие Melee Traits/Critical/Fate и Melee Protection Help target-bound receipts работают в едином owner/preparation/projection. Throwing/Net/Brawn/incoming Melee прежние, NPC catalog59/216старыхJSON сохранены. Native/source/schema/services/search/CLI прошли адресно. [Правило](rules/combat.md#pc-close-shooting-protection-m63), [примеры](examples/m63/README.md).

## M64 — PC Repeaters и общий ranged source

Завершён выбранный чанк Repeater Handbow/Repeater Pistol по [ADR-0106](decisions/ADR-0106-pc-repeaters-and-generic-ranged-profile.md): explicit bonus modes, conditional Reload3, shield/backup и generic PC key/native API. Drained/cap/Fate/armour/proof/source guards проверены; current PC JSON1, NPC pistol и каталог59 сохраняются.36прежнихJSON мигрированы только по PC profile key,184 побайтно прежние. Native/JSON/services/count search/CLI/один actual spawn завершены. [Правило](rules/equipment.md#pc-repeaters-m64), [примеры](examples/m64/README.md).

## M65 — Short opening, три bows и melee backup

Завершена выбранная функция по [ADR-0107](decisions/ADR-0107-pc-bows-short-opening-and-melee-backup.md): Shortbow/Warbow/Longbow,2H/free reload/actual range Traits, initial Short внутри одной Zone, own-turn free approach authored Minions и переключение на declared1H backup при любом Close enemy. Source/owner/projection/Conditions/Fate/руки/точные stops/JSON/trials/count search/CLI и один actual spawn проверены. Старые1H guns сохраняют triggers, каталог59/224прежнихJSON не мигрируются. [Правило](rules/equipment.md#pc-bows-m65), [примеры](examples/m65/README.md).

## M66 — Crossbow/Repeater Crossbow в Short opening

Завершён выбранный чанк по [ADR-0108](decisions/ADR-0108-pc-crossbows-opening-volley-and-reload-state.md):2H Exacting source, Crossbow4/+1armoured/charge2 и Repeater4/optional+1d→charge3, прежний NPC approach/backup. Full armoured bool authored NPC сохраняется в JSON, Trait не дублируется и не переносится на Sword. Native/source/JSON/trials/search/CLI проверены; focused K1 Reload отделён от fresh volley→melee trial. Старые228JSON/каталог59 прежние. [Правило](rules/equipment.md#pc-crossbows-m66), [примеры](examples/m66/README.md).

## M67 — Handgun/Repeater Handgun в Short opening

Завершён чанк по [ADR-0109](decisions/ADR-0109-pc-handguns-opening-volley.md): оба2H firearms с явными Blackpowder facts, ignores armour, Handgun Short−1d/charge3, Repeater optional+3d→charge5, прежний NPC approach→melee backup. Source/JSON/services/search/CLI и реальные shot/charge/neutral Close-stop проверены; focused Reload отделён от fresh encounter. Каталог59/shared14/старые232JSON прежние. [Правило](rules/equipment.md#pc-handguns-m67), [примеры](examples/m67/README.md).

## M68 — Sling/free reload/Close→backup

Завершён полный вариант по [ADR-0110](decisions/ADR-0110-pc-sling-free-reload-and-close-backup.md):1H Sling/Strength Damage/free reload/Short−1d, actual optimum Close restriction независимо от рук, прежний NPC approach и melee backup. Optional shield поддержан с явным weapon-first release перед draw в занятую preferred hand; Wounds/Recover/CI/Defenceless/terminal guards сохраняются. Source/JSON/services/search/CLI проверены,236старыхJSON/NPC59/shared14 прежние. [Правило](rules/equipment.md#pc-sling-m68), [примеры](examples/m68/README.md).

## M69 — Blunderbuss/initial NPC cluster/nearby completion

Завершён выбранный полный Trait по [ADR-0111](decisions/ADR-0111-pc-blunderbuss-cluster-and-nearby-stagger.md):2H/Damage4/+2dShort/обычная броня/Reload3, initial cluster source/order, HIT snapshot→primary ACK→ordered nearby impacts/GM ACK→прежний approach/backup. MISS не создаёт волну, primary Wound не требуется, primary/последнийNPC defeat не теряет completion. Source/JSON/services/search/CLI/native pickle проверены,240старыхJSON/NPC59/shared14 прежние. [Правило](rules/equipment.md#pc-blunderbuss-m69), [примеры](examples/m69/README.md).

## M70 — Hochland/Aim/Fate Second Action

Завершён выбранный путь по [ADR-0112](decisions/ADR-0112-pc-hochland-aim-and-fate-second-action.md): настоящие Initiative/Awareness Aim и spend/reserve/Lucky Second Action→Shoot до NPC approach; one-use/loss/mandatory/hand/CANNOT_AIM/CI/endphase/backup guards. Новые native/compact/capability counters, schemas/services/search/CLI и один actual process проверены.244прежнихJSON/NPC59/shared14 сохраняются. Все13PG ranged profiles доступны в принятых ограничениях, setup prelude/другие Zone не добавлены. [Правило](rules/equipment.md#pc-hochland-m70), [примеры](examples/m70/README.md).

## После M70

Следующий кандидат — пространственный PC encounter за пределами одной Zone: подготовить конкретную границу Medium/Long opening, настоящего перемещения и выбранной тактики NPC. Сверить скорость/Manoeuvre/Charge/Range и состав участников; не считать, что новая дистанция сама гарантирует безопасный Aim→Shoot, и не создавать фиктивное ожидание NPC. Public scope ещё не выбран.

Другие возможные направления — PC tactical policies/Help для ranged, новые NPC shooters и смешанные Close-группы. Сначала выбрать законченную пользовательскую функцию; не продолжать добавлять формальные вехи для каталога, где13PG ranged уже допущены. Применять адресную политику проверок AGENTS.md.
