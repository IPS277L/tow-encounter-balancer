# ADR-0104: NPC Help для настоящего Shooting Test

Дата: 2026-11-07. Статус: **принят пользователем; M62 реализована**. Выбраны четыре loadout и Attack fallback при будущем Reload.

## Источники и задача

M61 разрешает Official/Pistol и Imperial Ogre/Ogre Pistol, но отклоняет их как beneficiary в npc_help_policies: нынешние owner requests/applications фиксируют Melee. Общий K1 automatic Help уже связывает конкретные actor/Skill/Test и поддерживает нужный bonus die; требуется полноценная интеграция в PC бой, а не замена строки в receipt.

Адресно прочитаны BOOK-GM-GUIDE1.1, VII Allies and Antagonists: Free Company Militia113, Goblin Warrior156, Night Goblin157, Orc Boy158, Empire Peasant96 и Sigmarite Cultist121. Переиспользованы Big ’Un159 и согласованный M34. BOOK-PLAYER-GUIDE1.4 V Helping With a Test108 прочитан, Conditions123/Attack118–119 и принятые M33/M34/M61 переиспользованы.

- Strength in Numbers Militia: Help союзнику within Medium Range для **attack**, без Test; +1d, который может превысить обычный cap. Close удовлетворяет within Medium.
- Horde Goblin Warrior: Help союзной **attack**, без Test; +1d с превышением cap. Night Goblin использует правила Goblin Warrior, включая Horde; Nasty Skulker их автоматически не наследует.
- Torches and Pitchforks Peasant/Cultist и Power of the Waaagh! Orc Boy/Big ’Un прямо требуют **Melee attack**. Их bonus/free success не распространяются на Shooting.

Книга задаёт допустимый эффект, но не выбирает вместо NPC между полезным Help, собственным Attack и ожиданием Reload. Эта тактика должна остаться явной и согласованной.

## Принятая законченная граница

Разрешить existing npc_help_policies пары от **четырёх существующих canonical loadouts**: Free Company Militia/Improvised Blades, Goblin Warrior/Spear, Night Goblin/Spear+Shield и Night Goblin/Net+Spear — к любому из двух M61 стрелков. Разные виды NPC могут быть allies в явно заданной сцене; отдельного ограничения «гоблины помогают только гоблинам» источник не содержит. Новых NPC profiles/Abilities, generic authored helpers, PC Shooting Help или Help для Reload не добавлять.

Для этих пар source admission принимает Militia/Horde и отклоняет Peasant/Cultist/Orc/Big ’Un → Pistol до RNG. Не выдавать Melee-only Ability за обычный generic Help Test. Прежние разрешённые Melee пары остаются прежними, включая Orc free success/Drained тактику. Полный template проверяется до исключения actors; subset не должен скрывать неправильную пару.

Текущие инварианты M33 сохраняются: helper действует раньше beneficiary, один helper имеет одну пару; несколько helpers могут помогать одному Test; self/duplicate helper/chains запрещены. Policies не переназначаются при потере actor, source/round order не меняются.

## Тактика на ходу помощника

1. Применить прежние guards helper/beneficiary: living/present/not Broken/Defenceless, более поздний незавершённый ход, пригодность Help и Drained beneficiary. Drained dice-beneficiary по прежнему вызывает собственный Attack helper; Drained helper сам не делает Test.
2. Для Pistol beneficiary проверить actual loaded weapon bank. Если оружие пусто, получатель будет Reload; helper выполняет собственную Attack. Не помогать Dexterity, не ждать завершения Reload и не переносить помощь на будущий round/выстрел.
3. Если Pistol загружен, выполнить настоящий no-Test Help action для будущего **Shooting** Test этого actor в этом раунде. Это один standard slot/обычный TurnEnd и existing NPC Help cost; дополнительных RNG нет.
4. Между Help и выстрелом scene может измениться. Если beneficiary погиб/ушёл/получил Broken или больше не исполняет назначенный Test, Help остаётся потраченным, но не применяется другой цели/Skill/раунду/Reload. Если beneficiary стал Drained после Help, bonus dice подавляются; counts не отменяются. Нельзя бесплатно заменить уже исполненный Help собственной атакой задним числом.

Для melee receivers, Net/Flagellant Recover и прочих прежних fallbacks сохранить M33/M34/M47/M52. Night Goblin с Net как helper не бросает/не расходует Net при Help; его собственный Attack fallback использует обычную M52 Net/Spear тактику. Не заставлять helper выполнять дальнюю атаку: все четыре helper loadouts остаются прежними выбранными боевыми profiles.

## Конкретный source и исполнение

Используется прежний current PC JSON1 список пар, например:

```json
"npc_help_policies": [
  {"helper_id": "militia1", "beneficiary_id": "ogre1"},
  {"helper_id": "goblin1", "beneficiary_id": "ogre1"}
]
```

При enemy_activation_order militia1 → goblin1 → ogre1 загруженный Ogre получает два отдельных +1d bypass receipts. У него printed Shooting3d/2 cap6; обычные modifiers/cap вычисляются отдельно от каждого Help bonus. Пустой Ogre вместо этого Reload, а оба helpers выбирают собственные Attack. Источник не принимает caller-specified Skill/bonus/range/эффект: они выводятся из canonical Ability и actual выбранной attack.

Новых полей/wire version/метрик/schema fragments не требуется. Каталог59 и definitions/metadata сохраняются,212прежнихJSON M9–M61 не мигрируются. Generation фильтрует обе стороны прежних пар без retarget; full root/candidate echoes включают их как раньше. Old Melee sources и их outcomes не должны измениться.

Owner Help selection должен отличать будущий Shoot от Reload без симуляции будущих бросков. В request/result/bonus/application actual beneficiary_skill — Shooting либо прежний Melee, с exact intended Test ID. Application принимает только matching actor/Skill/Test и source receipt; source-based skill не должен переписываться вручную ради совпадения ID. Однократность/replay проверяются canonical projection.

NPC Shooting build должен применять разрешённые receipts **до броска** и сохранить npc_help_applications в PcAttackProof. NPC shot proof связывает исходную preparation и effective Attack после PC Protection Fate; positive help dice не превращаются в modifier PC opposition или Dexterity Reload. Обычный K1 cap/Drained/Grim и loaded/cycle guards остаются прежними. K1 automatic Help не требует нового effect kind или универсальной шины событий.

## Адресная приёмка

1. Все четыре helpers → оба M61 shooters; mixed/multiple helpers; Melee-only source pairs/unknown actors/chains/forged Ability и full excluded-template rejection до RNG. Прежние melee pairs и Orc free success сохранены.
2. Literal loaded Shoot получает actual Shooting bonus/application и правильный cap bypass; HIT/MISS расходует заряд один раз. Empty/partial Reload вызывает helper Attack, без Help/Dexterity bonus/rollover. После завершения Reload следующий round снова разрешает Help.
3. Helper Night Goblin/Net при Help не расходует stock; при Attack fallback сохраняет M52 selection/stock/draw/Burdened. Drained helper/beneficiary, broken/exit/death после Help и unused receipts, чужой round/actor/Skill/Test/replay/повторное application.
4. Настоящий NPC shot с PC Protection Help/Fate/Grim/Glorious/Near Miss и canonical loaded/cycle prefix; help cost остаётся, даже если later attack не состоялась. K1/test-bound boundary cases проверять детерминированно; не объявлять искусственный setup полноценным публичным сценарием.
5. Trials/summary/existing NPC Help counts, subset generation/current JSON1/full root/candidate echoes; полезный CLI пример нескольких помощников к стрелку и собственного Attack во время Reload.212прежнихJSON byte-identical,59definitions без изменений.

Проверки — новые native/source/JSON-service cases и ближайшие M33/M34/M35/M52/M61, общий K1 automatic Help/границы dice/Drained. Full project/wheel не требуются автоматически. Новых runtime types/enum/wire fields/process mechanism нет, M61 actual process уже проверил текущий firearm path; повторную process matrix без нового риска не запускать. Точные команды/результаты записать в статусе после реализации.

## Альтернатива и согласование

Меньший вариант — только Militia → оба стрелка с той же тактикой, отложив Horde/Net helper integration. Основное Skill-bound request/application исправление необходимо в обоих вариантах. Рекомендованы четыре совместимых loadouts общим чанком; catalog не расширяется.

Пользователь выбрал **«Четыре loadout и Attack fallback»**. Militia-only альтернатива не выбрана; дополнительных вопросов для реализации M62 нет.

## Реализация и проверка

Изменены только три production-файла: source/selection/application в pc_npc_help_models, снят общий запрет Pistol beneficiary при сохранённых Ability/Skill guards, Shooting build теперь применяет разрешённые Help receipts. K1/schema/wire/types/метрики/catalog не изменены.

15новых tests прошли:9native и6JSON/services. При проверке исправлены две предпосылки fixtures: PC side действует целиком до NPC, а Protection Help не предсказывает будущий NPC Help. Это не изменение тактики PC. Проверены реальные капы/Reload fallback/Net stock/Glorious/Near Miss/unused receipts и смерть PC до загруженного shooter turn; Drained/unavailable подготовка отдельно обозначена как focused setup.

Ближайший48suite — OK. Составной58suite дал57успешных и1ошибку окружения: старый M33process test попал в команду по ошибке и не смог создать Windows Pipe в sandbox (WinError5). Это не зелёный58/full run; spawn не повторяли, новый process path/types не менялись и M61 representative уже проверен. Точные команды/результаты — в [статусе](../project-status.md).

Оба [CLI-примера](../examples/m62/README.md) исполнены sequential;212прежнихJSON byte-identical,108request/result pairs M9–M62 проходят текущие source/offline schema checks. Независимый read-only review новых блокеров не обнаружил. Full project/wheel не запускались.
