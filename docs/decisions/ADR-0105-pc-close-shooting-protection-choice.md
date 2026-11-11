# ADR-0105: явный выбор PC Protection против Close Shooting

Дата: 2026-11-07. Статус: **принят пользователем; M63 реализована 2026-11-08**. Выбран полный путь с Melee Protection Help и описанной hand-use тактикой.

## Правило и конечная функция

M61/M62 умеют NPC Pistol против PC, но PC пока выбирает Defence с рабочим shield, иначе Athletics. BOOK-PLAYER-GUIDE1.4 IV Ranged Weapons94 прямо разрешает Oppose Close ranged Attack через Melee. Следующая функция — явный выбор PC Skill со всеми Traits/руками/Fate/Help, через native/trials/search/current JSON1/CLI.

Адресно прочитаны PG1.4 III Characteristics & Skills/Melee/Defence68, IV Ranged Weapons94, V Recover/Attack Tests118, Wounds190; переиспользованы Weapons93, Helping108, Conditions123 и M12/M16/M18–M20/M53/M60–M62 owners. Нормативный scope среза — incoming **Shooting в Close**. Throwing/Net, Brawn и incoming Melee сохраняют прежнюю защиту; остальные ranges не добавляются.

PG68 требует weapon/shield для Defence и shield против Shooting. Специальная Melee opposition PG94 не содержит такого equipment gate; описание Melee attack с dedicated close weapon не является запретом любого Melee Opposed Test без оружия. Существующий K1 protection eligibility уже допускает Close Melee opposition без defender_wields_weapon. Не объявлять новый weapon-only запрет книжным правилом.

## Принятый текущий source

Optional поле participant текущего PC JSON1:

```json
"close_shooting_protection_skill": "melee"
```

Допустимы только `melee` или `athletics`. Отсутствие сохраняет текущую fixed policy: Defence с working shield, иначе Athletics. Null/прочие Skills/числа/неизвестные поля не допускаются. Отдельное значение defence не нужно: оно дублировало бы нынешнюю shield/fallback тактику. Native — exact Skill либо None в immutable participant source, не состояние оружия и не global список actor IDs.

Поле можно задавать у любого существующего PC loadout, включая Pistol/shield/2H/backup; это не добавляет возможности самому стрелку выполнять Help. Настройка может оставаться неиспользованной в melee-only сцене или когда count search исключил всех shooters. Party/source policy при подборе сохраняется, NPC filtering не удаляет настройку PC.216прежнихJSON M9–M62 не мигрируются, current version1 и метрики прежние.

## Выбранный Skill и физический способ защиты

- Explicit Athletics: использовать Agility/Athletics, даже когда shield held. Shield остаётся held и сохраняет собственные equipment/Resilience facts; выбор Skill не сбрасывает предмет.
- Explicit Melee: использовать WS/Melee против actual Close Shooting; нет automatic best-Skill/Defence fallback из-за Staggered/Drained/потери предмета. PG94 permission сохраняется без оружия.
- Без поля: прежние Defence/working shield либо Athletics.
- Unaware/Defenceless precedence не создаёт opposition/Test/Fate/Help/использования руки. Current public сцена остаётся aware; проверка unaware относится к K1 boundary, не новой сцене.

Предлагаемая фиксированная **тактика физического применения** Melee: если actual active weapon пригодно и held, PC использует его текущим grip (включая Pistol; charge не расходуется); если нет, он уклоняется/контролирует дистанцию без использования рук. Это способ выбора hand-use facts сценария, не дополнительное требование RAW или новое Brawn Attack. Shield сам по себе не заменяет active weapon в этом Melee способе. Weapon-first/self Recover/backup draw на собственном ходу сохраняются: выбор opposition не подбирает оружие и не выполняет swap раньше времени.

При использовании actual injured12 hand/grip применяется прежний Critical source, BOTH использует обе руки. Без использования рук новый Critical12 не выдумывается. Утрата руки/clutch18 не снимаются ради opposition. Для Defence physical use — working shield; для Athletics hand use отсутствует. W14/15 не превращают opposition в дополнительное действие: сохраняется прежнее различие Test и action. Невозможная повторная анатомия/существующий2H unsupported не обходятся новой policy.

## Traits, Fate и Help

Melee opposition не является Attack: нет counterattack/Damage/shot consumption/action slot/outnumber/higher-ground/Charge или Attack-only Warhammer target bonus. Общие Melee Test modifiers actual held оружия действуют: Greataxe/Greathammer−1d, Staggered Flail−2d, Staggered Morning Star−1d. Sword/Glaive +1d Defence не превращается в Melee bonus. Если weapon dropped/unusable, его Traits не участвуют. После настоящего M20/M60 draw используется backup, не immutable primary. Наличие owned Pistol не превращает защитный Melee в Shooting и не меняет его loaded/progress/cycle.

Actual selected Skill определяет Glorious window/ресурс, Drained/Blinded/W10 и PC Test source. Grim/W10 расходуется только на настоящий Test, один раз; Fate prefix и Near Miss/Wounds/body/mandatory tails сохраняются. NPC Shooting/Help/cycles M61/M62 остаются прежними.

Разрешить `help_policy.target=first_incoming_protection` с protection_skill=melee. Это существующая physical PC Help, не новое no-Test правило. Helper делает собственный Melee Help Test со своим active weapon/Traits/Fate/Critical; recipient получает dice к конкретному incoming Protection Test. `target=melee_attack` остаётся отдельной стратегией: intended ID выбирается по **target**, а не одному Skill.MELEE, иначе receipt ошибочно адресовался бы Attack. Публичных новых Help fields нет, расширяется enum текущего protection_skill.

Прежняя тактика first current NPC без предсказания его будущего Help/Reload сохраняется. Если выбранный Skill или actual intended Test позже изменился, Help остаётся unused и не переназначается. Helper продолжает прежний Attack/Recover fallback при недоступном получателе/неподходящем Skill. Собственные Help/ally Recover роли Pistol-PC не расширяются, но он может получать чужую Protection Help.

## Реализация по слоям

Source/codec/schema подтверждают optional Skill и обновлённый Protection Help enum вместе. Pure selection использует actor source policy и actual runtime equipment. Один выбранный Skill должен поступать в attack preparation, PC Help eligibility/application, hand-use/Critical и canonical projection; нельзя объявить Melee в eligibility, а бросить Defence либо применить чужой Test receipt.

Переиспользовать existing Melee Test profile/K1 Close ranged permission и proof types. Opposed Melee не создаёт PcAttackProof от PC или reload event. Engine передаёт actual selected Skill в существующий Fate resolver. Публичные summaries/counters прежние; root/candidate echoes сохраняют optional field/Help policy. Общий Test/Attack kernel и NPC source catalog менять не требуется.

## Адресная приёмка

1. Source roundtrip всех13melee/Pistol/shield/backup вариантов с optional Melee/Athletics/absence, exact type/enum/closed fields, malformed cached source до RNG;216старыхJSON/59NPC definitions без изменений.
2. Настоящий NPC Pistol Test против Melee/Athletics/default shield Defence; explicit Athletics при held shield, dropped/unusable weapon и Pistol-only Melee permission. Defenceless без Test, no counterattack/extra action/shot расхода PC Pistol. Своевременный NPC Shoot/Reload/Help остаётся прежним.
3. Общие Melee Traits против Attack-only/Sword Defence, Drained/Grim/Glorious/W10; настоящий hand12/BOTH Critical и потеря руки/backup/Recover без раннего использования dropped предмета. Focused body/equipment setup не выдавать за публичный свежий бой.
4. Protection Help Melee через actual Test ID, отдельно от Melee Attack Help; helpers/receivers/unused receipts, Skill change/actor/round/source/replay guards, Fate/hand consequences. First-current-NPC не предсказывает NPC Help/Reload.
5. Native journal/trials/summary/search/current JSON1/offline schemas/full root/candidate echoes и полезный CLI пример. Source party/policy сохраняется после удаления последнего Shooter из состава. Прежние Melee/Net/Brawn/shield/Fate/Help paths проверяются адресно.

Проверки — новые native/source/JSON-service cases и ближайшие K1 Protection, M12/M16/M18–M20/M53/M60–M62 по затронутым ветвям. Не включать старый M33spawn случайно: M62 уже зафиксировал sandbox WinError5. Full project/wheel/process matrix без нового основания не требуются; runtime proof types/enum Skill/доставка не меняются, optional wire values проверяются source/offline.

## Меньшая альтернатива и согласование

Меньший вариант — новый PC выбор Skill без Melee Protection Help, оставив Help только Defence/Athletics. Source/hand/Traits/Fate границы сохраняются, но функция не закрывает взаимодействие нового Skill с существующей Help системой. Рекомендован полный путь с Melee Protection Help и описанным hand-use способом, без weapon-only ограничения PG94.

Пользователь выбрал **«Полный путь с Melee Protection Help»**, включая optional Melee/Athletics, default без поля, PG94 weaponless permission и actual usable grip/иначе no-hand способ. Дополнительных вопросов для реализации M63 нет.

## Реализация и проверка

Source/codec/common schema расширены вместе. Pure selection получает actual actor choice, Help intended ID зависит от target, общий hand helper используется подготовкой и projection. Pistol/weaponless Melee не расходует charge и не создаёт PC Attack. K1/proof types/метрики не менялись.

15новых tests прошли (9native,6source/JSON/services); ближайшие checkpoints61 и180tests — OK. Native проверяет Skills/shield/default/weapon drop/общие Traits/Pistol/Fate/W10 и настоящий Melee Protection Help с exact intended ID/replay. Critical12/BOTH/непригодный grip/Drained/Defenceless boundary setup явно отделён от публичного fresh journal. Старые M9/M16 отрицательные MELEE Help fixtures обновлены на действительно неподдержанные Skills, позитивные loops включают Melee.

Оба [CLI-примера](../examples/m63/README.md) исполнены sequential,216прежнихJSON byte-identical/110request-result pairs и59NPC definitions сохранены. Независимый read-only review новых блокеров не обнаружил. Точные команды/результаты — в [статусе](../project-status.md). Full project/wheel/spawn не запускались; старый M33process намеренно не включён, delivery/runtime types не менялись.
