# ADR-0101: явная NPC Protection против Close Shooting

Дата: 2026-11-07. Статус: **принят пользователем и реализован в M56**. Выбраны Melee + Athletics для четырёх loadouts.

## Проблема и источники

Pistol-сценарий M54/M55 требует уже выбранную законную Protection: Athletics либо Defence с настоящим shield. Многие существующие melee loadouts имеют выбранную Defence без shield. Их нельзя допускать против Shooting, просто сохранив этот Test или придумав Athletics по числам атаки.

Адресно прочитаны локальные BOOK-PLAYER-GUIDE1.4: III Skills68, IV Ranged Weapons94/Armour97, V Dice Pools107/Attack Tests118/Conditions123; BOOK-GM-GUIDE1.1: VII Reading Profiles93, State Trooper100, Empire Knight101, Knight of the White Wolf116. Выполнена независимая read-only сверка четырёх профилей. Это адресное чтение, не новая версия/полное перечитывание книг.

PG94 прямо разрешает цели Close ranged attack выбирать Melee для opposition. PG68 задаёт обычный Defence/shield/Athletics допуск, PG118 сохраняет отсутствие opposition для Unaware/Defenceless и обычное сравнение successes. Защитный Melee Test не создаёт counterattack, Damage или собственного action slot NPC. Charge/outnumbering/higher-ground по PG118 относятся к атакам, поэтому не добавляются автоматически к защитному Melee Test.

GM93 определяет готовые Attack rows как профили атак и предупреждает об отличии NPC weapon effects от PC Traits. Для первого чанка Melee opposition сверена по полным WS/Skills; совпадение с числом атаки не является общим правилом переноса Attack profile на защиту.

## Принятый чанк: четыре существующих loadouts

| Canonical profile | Источник | Melee opposition | Printed Athletics | Прежняя выбранная Protection |
|---|---|---|---|---|
| empire_state_trooper_halberd | GM100 | WS3/Default3:3d/3, cap6 | 3d/3, cap6 | Defence3d/4, no shield |
| empire_state_trooper_spear | GM100 | WS3/Default3:3d/3, cap6 | 3d/3, cap6 | Defence3d/4, no shield |
| empire_knight_lance | GM101 | WS4/Melee4:4d/4, cap8 | 2d/3, cap6 от Ag3 | Defence4d/4, unmounted/no shield |
| knight_white_wolf_hammer | GM116 | WS4/Melee4:4d/4, cap8 | 2d/3, cap6 от Ag3 | Defence4d/3, unmounted/no shield |

Athletics уже сохранена в `PcBookNpcEntry.unselected_protection`. Новые NPC definitions или variants не нужны; каталог остаётся57. Canonical identities и обычная выбранная Protection не переписываются. При incoming Melee используется прежний Defence; новая настройка действует только против Close Shooting, поэтому смешанная party не меняет защиту NPC от меча на защиту от пистолета.

**Предел Athletics Knights:** готовые2d/3 не означают Characteristic2. У обоих Ag3 и heavy armour; PG97 даёт–1d на Agility Tests, PG107 ограничивает максимум двумя исходными Characteristics, то есть6. Уменьшение до printed2dice соответствует уже учтённому штрафу — вывод из совместного чтения карточки и armour rule; второй–1d не применяется. Прежняя невыбранная metadata хранила InlineProfile(2,3) с default cap4; в M56 исправлена на InlineProfile(2,3,6) для двух unshielded loadouts. Это не изменение прежних выбранных Defence profiles или разрешение произвольного Protection cap у authored NPC. Для Troopers Athletics3d/3/Ag3 максимум тоже6.

State Trooper Supporting Action требует входа врага в Close и подходящего союзника в соседней Zone; fixed Close/noMove/noExternal сцена его не запускает. Mounted/Charge/Order/Steed и Wolf Hammer Charge effects остаются вне своих условий. У Knights W1Drained/W2defeat сохраняются. К Wolf Hammer не добавляются PC Greathammer Traits по названию оружия. Более сложные Brewguard/Bestigor/Miner и authored overrides не включаются автоматически.

## Принятый публичный контракт

Добавлена optional closed настройка на уровне scenario/template текущего PC JSON1:

```json
"npc_close_shooting_protection_policies": [
  {"actor_id": "trooper1", "skill": "melee"},
  {"actor_id": "knight1", "skill": "athletics"}
]
```

Каждая запись содержит ровно actor_id и skill; skill допускает **melee либо athletics**, только для полного canonical источника одного из четырёх loadouts выше. Политика не принимает произвольные dice/threshold/cap, source IDs или Attack-only modifiers. Полные числовые профили берутся из сверенных catalog facts: Athletics из существующей metadata, Melee из явно подтверждённого WS/Skill, не из произвольного Attack Test.

Поле отсутствует — остаётся прежняя выбранная Protection, со всеми прежними ограничениями M54/M55. Если поле присутствует, список непустой; null/пустой список/unknown fields/aliases/duplicates/неизвестные или PC actor IDs отклоняются. Новый override имеет смысл только при наличии Pistol-PC в party. Для каждого actor разрешена одна запись и один фиксированный Skill, без автоматического выбора наиболее выгодного результата.

Typed source хранит optional tuple точных policy values; отсутствие настройки сохраняется как отсутствие в wire.188прежнихJSON M9–M55 не требуют миграции. При bounded subset generation удаляются записи исключённых NPC, без переназначения и изменения Skills; если записей не осталось, поле отсутствует. Полный template проходит admission раньше удаления NPC: неподдержанный override нельзя скрыть zero count. Family/version/counters прежние.

Внутренний owner выбирает полный канонический Test по incoming Skill и source policy. В K1 уже есть Close ranged Melee eligibility/trace; новая возможность не требует менять Attack в counterattack, весь NPC Protection tuple или состояние снаряжения. Full native source и actual Protection preparation должны подтверждать definition/actor/Skill/profile/политику. Cached IDs/поддельный профиль/равный enum alias не являются разрешением.

## Игровые границы

- Override действует только против aware/non-Defenceless Close Shooting. Unaware/Defenceless не получают Test; отсутствие opposition сохраняет прежние Damage/Wound последствия. Выбор Melee не требует собственного хода NPC и не расходует его Attack action.
- При равных successes выигрывает атакующий по прежнему правилу. Выигравший защитный Melee не наносит Damage стрелку; Close miss вызывает прежний Staggered стрелка только при его отсутствии.
- Melee opposition не получает атакующие outnumbering/higher-ground/Charge, PC Sword/Greathammer Traits, Damage modifiers или чужие Help snapshots. Cap подтверждается исходным Characteristic, а не удвоением уже уменьшенного armour printed pool; новый произвольный cap contract не вводится. Source definition Protection остаётся прежней, policy не принимает numeric cap.
- W1Knights/Drained сохраняется: нет bonus dice и бесплатного Glorious, penalties остаются; новая policy не снимает Condition. Prone NPC даёт–1d самому Shooting, а не защитный Melee bonus. Остальные поддержанные source-aware Conditions сохраняют точную область.
- Собственные NPC Attack/Help/Recover и target priorities не меняются. Pistol+Shield/Reload и Wound/Fate continuation используют принятые M54/M55 правила. Policy выбирает защиту, не оптимизирует всю тактику.

## Меньшая альтернатива

Сначала разрешить только **athletics** для того же чанка и с тем же optional field. Все числа уже напечатаны и сохранены; это открывает эти четыре loadouts для Pistol без нового Melee Test path. Melee choice будет отклоняться до отдельного расширения. Этот вариант меньше по реализации, но не использует прямо разрешённую PG94 Melee opposition, особенно полезную Knights. Поддерживать скрытый автоматический fallback вместо явной политики не предлагается.

## Законченная функция и адресная приёмка

Веха включает source/policy admission → canonical profile selection и proof binding → native/trials/count generation/current JSON1/CLI, с общими примерами всех четырёх loadouts. Не выделять отдельную веху на каждый слой/противника.

1. Четыре полных canonical источника, обе Skills и обычная Defence против Melee; неизменные57definitions/188JSON. Knights Athletics2d/3/cap6 без второго armour penalty; Troopers3d/3/cap6, Melee caps6/8. Invalid profile/actor/duplicate/Skill/alias и malformed optional field отвергаются до RNG, включая full template.
2. Literal Close Shooting с выбранной Melee/Athletics: верные dice/threshold/cap, eligibility trace, HIT/MISS/tie/both-fail, отсутствие counterattack/Damage/free action. За пределами Close новый путь недопустим; kernel boundary проверить существующими protection tests.
3. Mixed party не меняет Defence от входящего Melee; без policy действует прежняя eligibility. Нет Attack-only bonuses, PC Traits или переноса Help в защитный Melee. Default NPC Attack profile/действия остаются прежними.
4. Knights W1Drained→дальнейшая Protection→W2defeat; Prone penalty стрелку, Unaware/Defenceless precedence и источники фактических Wound/Fate. Native journal и immutable source readmission отвергают поддельный Skill/profile, replay и замену policy.
5. Simulation/balance offline schema/full root/candidate echoes; subset filtering по actor без переназначения; useful actual CLI-пример чанка. Один actual process representative для полного нового policy source/records, без повторения старой backend matrix.

По умолчанию новые проверки и ближайшие K1Protection/PCPistol/Shield/Wounds зависимости. Full project/wheel не следуют автоматически из нового поля/ADR: package discovery/resources/entry points не меняются. Документационная подготовка игровых тестов не требует.

## Согласование и реализация

Пользователь выбрал **Melee + Athletics для четырёх loadouts**. [Typed policy/profile factory](../../src/towr/domain/pc_npc_close_shooting_models.py) подтверждает полный canonical источник, [source admission](../../src/towr/domain/pc_melee_models.py) проверяет весь roster до RNG. [Owner](../../src/towr/domain/pc_melee_result_models.py) выбирает новый профиль только при Shooting, сохраняя обычную Defence от Melee. [Codec](../../src/towr/adapters/_pc_melee_scenario_json.py) сохраняет optional absence/полный echo, [generation](../../src/towr/application/pc_melee_balance_models.py) фильтрует actor policies без переназначения. Новый proof variant/counterattack/action clock не введён.

31новый тест прошёл составными адресными прогонами:9source,8JSON/services,13native и1actual process. Проверены близкие PC/K1 компоненты; первоначальные ошибки тестовых ожиданий/fixtures исправлены и затронутые проверки повторены.188прежнихJSON сохранены побайтно,57выбранных definitions не переписаны. Подробные команды/ограничения — в [статусе](../project-status.md), actual [CLI-примеры](../examples/m56/README.md), [очередь](../roadmap.md). Full project/wheel не запускались.

## Расширение источников M57

После M56 пользователь поручил продолжить следующий согласованный в очереди чанк. Адресно сверены GM158–159: Orc Boy/Big ’Un Choppas/Spear без щитов. Все четыре имеют Melee3d/4/cap6 и Athletics3d/3/cap6; Big ’Un S4 не меняет WS3. GM158 Help относится только к Melee attack/Attack Test. Существенной новой неоднозначности/тактики не обнаружено: M57 расширяет canonical factory по этому образцу, без нового поля/Skill/version или отдельного архитектурного решения. Первоначальный M56 scope/результаты выше сохраняют историю; M57 разрешила восемь loadouts. [Текущее правило](../rules/combat.md#pc-close-shooting-protection-m57), [примеры M57](../examples/m57/README.md).

## Расширение источников M58

Следующий порученный чанк подключён по той же policy: Nasty Skulker, Dwarf Brewguard/Warhammer, Dwarf Miner/Pickaxe и Bestigor/Massive Axe, всего12источников. Полные WS/Skills подтверждают защитные Melee4d/4,4d/3,4d/3,4d/4; alternate Athletics Miner/Bestigor получила истинные cap4/cap8 от Ag2/Ag4. Generic grudge Miner применяется к выбранному Melee и подчиняется Drained, Distracted действует на оба Skills. Bestigor Blood Rage и W1 Glorious сохраняют Attack-only scope; новый выбор тактики/поле/формат не введены. [Текущее правило](../rules/combat.md#pc-close-shooting-protection-m58), [примеры M58](../examples/m58/README.md).
