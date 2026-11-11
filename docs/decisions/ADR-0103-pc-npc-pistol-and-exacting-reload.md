# ADR-0103: NPC Pistol и настоящий Reload против PC

Дата: 2026-11-07. Статус: **принят пользователем; M61 реализована**. Выбраны два профиля и полный Reload в описанной границе.

Дополнение M62: [ADR-0104](ADR-0104-pc-npc-shooting-help.md) разрешает Militia/Horde Help к Shooting. Запрет NPC Help ниже сохраняет исходную границу M61; актуальная граница — в [правиле M62](../rules/npc-profile-catalog.md#npc-shooting-help-m62).

## Задача и нормативные источники

Существующий PC owner допускает NPC Melee/специальные Net/Trample, а Pistol и его настоящий Shoot/Reload цикл поддерживает лишь у PC. Следующая законченная функция — противники, стреляющие в нынешнюю группу PC в fixed Close, с расходом заряда и отдельными действиями Reload. Это новый public source/action path, а не простое добавление чисел в каталог.

Адресно прочитаны BOOK-GM-GUIDE1.1, VII Allies and Antagonists92–93/98/103/124; BOOK-PLAYER-GUIDE1.4 III Dexterity/Initiative70, IV Ranged Weapons94–95 и V Conditions123. Переиспользованы III Shooting/Defence68, Tests107/Exacting110 и Lore82/Tools98–99. GM93: Characteristic задаёт число dice, Default — rating всех неуказанных Skills; Lores/Assets GM подтверждает отдельно. PG94: Reload — Exacting Dexterity, каждый Test занимает action; обе карточки указывают3successes. GM93 требует выбрать carried weapons до боя; NPC не наследует PC Traits по названию оружия.

## Принятый чанк

Два новых самостоятельных fixed loadouts, без carried melee backup/shield/Charge/движения:

| Loadout | Нормативный Attack | Reload | Protection | Wounds |
|---|---|---|---|---|
| Empire Official / Pistol, GM98 | Shooting2d/3, cap4 отBS2; Damage5,1H, ignores armour, optimum Close–Short | I3/Default3 → Dexterity3d/3, cap6;3successes | Athletics3d/3, cap6; T3/Res3 | Brute2: W1Broken, W2defeat |
| Imperial Ogre / Ogre Pistol, GM103 | Shooting3d/2, cap6 отBS3; Damage5,1H, ignores armour, optimum Close–Medium | I2/Default2 → Dexterity2d/2, cap4;3successes | Athletics3d/3, cap6; T5/Res6 armoured | Brute3: W1–2Speed Normal, W3defeat |

Числа Reload выводятся из напечатанных I/Default и общего правила, их не выбирает GM. Ogre Pistol берётся из конкретной строки Attacks GM103; Typical Trappings с названием handgun не подменяют её обычным PGHandgun, которому Close не разрешён. Не сокращать optimum Ogre доShort ради повторного использования PC Pistol profile.

Official сохраняет Heard It All Before и полный first-Wound Broken/own-turn exit путь M23/M24. Broken/exit обрабатываются раньше обычного Shoot/Reload; при отсутствии exit policy сохраняется честный прежний stop. Не считать W1 автоматическим defeat/уходом. Ogre сохраняет Speed bands и полные metadata Ogre Charge/Fearsome/Mighty Throw: в Pistol-only/noMove сцене Rough Shove/Charge/Melee Give Ground не выбираются, поэтому соответствующие triggers отсутствуют. Никаких применимых Abilities не отключать.

Noble/Duelling Pistol GM98 и Witch Hunter/Pistol GM124 — Champions: GM92 требует полноценную Wounds Table, которой у NPC в PC owner пока нет. Noble дополнительно требует Status/Look Out Sir!; Pass Sentence Witch Hunter применяется и к Pistol Wounds, пока он не Staggered. Они не входят в M61; нельзя заменить их Brutes или удалить эти эффекты. Каталог57 после полного выбранного чанка станет59, прежние definitions сохраняются.

## Выбираемая тактика и scene facts

Принята initially loaded **Shoot → Reload до3successes → Shoot**. Пока NPC жив/присутствует/имеет обычный свободный ход, loaded допускает один Attack; empty выбирает ровно один Improvise/Skill Reload Test. Неуспех сохраняет накопленный progress; завершение Reload не даёт бесплатного выстрела. HIT и MISS расходуют заряд и создают новый уникальный cycle. Никакого автоматического переключения на невыбранное melee weapon, Recover от одного Staggered или скрытой дозарядки при ране/смене раунда.

Source явно подтверждает initially_loaded, Blackpowder Lore, полный kit, достаточные supplies и `two_available_hands` Reload policy. Последняя — отдельная выбранная GM/scenario конкретизация для этих NPC, не автоматический перенос PC решения или цитата книги. В source один held1H Pistol, вторая рука свободна; Brute Wounds не создают PC hand anatomy. Нет shields/backup/equipment swap у этих loadouts. Unsupported fresh/частичные facts отклоняются до RNG.

PC сохраняет нынешнюю фиксированную допустимую защиту: Defence с рабочим shield, иначе Athletics; без автоматического нового Melee opposition выбора. Defenceless не Opposes. Применяются actual Protection Help/Fate/Grim/Glorious, Critical от настоящего hand use и полные PC Wounds/Near Miss/body/mandatory tails. Ignores armour использует Toughness, сохраняя source shield/armour и actual Defence eligibility. Shooting не получает Melee outnumber/higher ground; Prone target даёт−1d, Close MISS налагает Staggered лишь при его отсутствии. Drained подавляет bonus dice, не отрицательные modifiers и не снижает printed base.

В первом срезе новые Pistol loadouts не могут быть beneficiary в `npc_help_policies`: такой source отклоняется до RNG. Нынешние NPC Help requests/receipts фиксируют Melee; поддержка Shooting потребовала бы отдельной Skill-bound интеграции и проверки будущего Reload вместо Attack. Это явная граница комбинаций, не выполнение объявленного Help с потерянным бонусом. Остальные mixed-party NPC Help policies работают в прежних границах. Более широкий NPC Shooting Help можно расширить отдельным согласованным шагом.

## Конкретный текущий JSON1 контракт

Сохранить один current PC JSON1, без новой версии/legacy branch. Для двух новых canonical identities разрешить единственный primary `definition.attack` со следующими дополнительными обязательными полями: `skill:"shooting"`, `range_min:"close"`, `ignores_armour:true`; existing range_max хранит optimum верхнюю границу Short/Medium. Остальные поля как прежде: id/source_rule_id/test_profile/damage/hands/secondary_effects. Новые поля запрещены прежним Melee definitions; arbitrary authored Shooting и forged canonical числовые копии не допускаются.

У соответствующего `enemies[]` требуется closed object `pistol`:

```json
"pistol": {
  "initially_loaded": true,
  "has_blackpowder_lore": true,
  "has_blackpowder_kit": true,
  "ammunition_supply_confirmed": true,
  "reload_hand_policy": "two_available_hands"
}
```

Нет global пустого списка по умолчанию для всех старых сцен. Наличие полного объекта требуется только новым двум loadouts, другим запрещено. Numeric Shooting/Reload Profiles и weapon kind принадлежат canonical definition/metadata, не переопределяются GM bool facts. В native source typed policies связываются с actor/full definition по образцу existing per-enemy Net source. Source re-admission/full excluded template проверяется до RNG/действий; count projection сохраняет survivors и удаляет настройки исключённых NPC без переназначения.

Отдельные новые публичные counters не вводить: NPC Reload входит в existing total executed action count и занимает обычный round slot; existing NPC Recover/Help counters не увеличиваются. Полные root/candidate echoes сохраняют исходный `pistol` object и Shooting profile, runtime flags/progress не записываются поверх fresh source.208прежнихJSON M9–M60 сохраняются побайтно; это отсутствие необходимости миграции, а не обещание совместимости старых версий.

## Исполнение и ответственность слоёв

Добавить узкий typed NPC Pistol owner/proofs, отдельно от generic `NpcParticipantSnapshot` и PC inventory. Weapon state привязан к actor/canonical attack/instance/cycle, owned PC и несколько NPC не делят progress. Расход после actual завершённого Attack связывает original/effective request, kernel receipt и weapon state один раз; failed preparation не расходует заряд. Reload использует existing Exacting completion без второго RNG и без imports rules из domain.

Обычный Pistol переиспользует current ranged reload/combat primitives. Ogre Pistol требует самостоятельной source-bound записи shared ranged profile/reload catalog по GM103:1H/Close–Medium/Damage5/ignores armour/reload3, не изменяя13PG rows. Не использовать стандартный Pistol combat preparation с чужой дальностью. Generic NPC ranged preparation уже поддерживает printed range/ignores armour, но PC owner требует интеграции и явного снятия Melee-only gates.

Action selector, engine и canonical projection проверяют один и тот же Skill/loaded/slot. В PC owner сейчас Melee-only outnumber/Prone/Help и ignores_armour gates, single-primary admission/codec, PC-only Reload proof/action counting: все затронутые места должны перейти на actual NPC Shooting без изменения старых Melee paths. Profile Wound ACK, Broken exit, conditions/distraction/Drained и terminal prefix сохраняют порядок. Не заимствовать Blunderbuss-only `NpcRoundWeaponState` или отдельный NPC-vs-NPC simulator как скрытый runtime PC боя.

## Адресная приёмка

1. Оба canonical profiles/default-derived Reload/caps/range/traits/Wound bands; independent factories, full definition/actor/type/source aliases, shield/backup/partial facts/foreign `pistol`/Help-beneficiary guard до RNG.208старыхJSON и57прежнихdefinitions без изменений.
2. Literal HIT/MISS/Close Staggered, loaded→empty/cycle, failed/partial/overshoot Reload, следующий выстрел только отдельным действием; несколько NPC и PC Pistol с независимыми instances/cycles/progress. Failed preparation/replay/stale/foreign receipt не расходует заряд повторно.
3. PC shield Defence/без shield Athletics/Defenceless, armour/Toughness, Prone−1d/нет Melee bonuses, Protection Help и actual Fate/W10/Grim/Glorious/Critical/Near Miss. OldMelee/mixed paths остаются прежними.
4. Official W1Broken до следующего собственного хода, W2 до exit, actual exit либо прежний stop; empty gun не выбирает Reload раньше Broken. Ogre W1–2/defeat и non-Attack Wound ACK, terminal/dead/exited NPC не Reload. Profile-specific metadata сохраняет невыбранные атаки.
5. Native journal/trials/summary/action counts/count search/current schemas/full echoes/CLI пример реального NPC Reload. Один representative sequential/process с действительным Reload, без повторения полной backend matrix.

План проверки — новые modules и ближайшие M23/M24/M49/M53–M60, NPC preparation/Reload/Exacting kernel, profile-Wound/Help/Fate по затронутым взаимодействиям. Общий owner/ranged catalog требуют одного subsystem checkpoint с названным объёмом. Full project/wheel не нужны автоматически; resources/dependencies/entry points не меняются.

## Альтернатива и согласование

Меньшая альтернатива — только Official/Pistol с той же тактикой и source guards, отложив Ogre Pistol/shared GM ranged profile. Это уменьшает объём, но не устраняет основные owner/Reload/codec изменения. Champion/пространственный бой не является частью ни одного варианта.

Пользователь выбрал **«Два профиля и полный Reload»**: Official + Ogre, fixed Shoot/Reload, две руки/подтверждённые Lore-kit-supplies, без carried backup/shield/NPC Help к этим стрелкам. Вопросов для реализации M61 не осталось; меньшая альтернатива не выбрана.

## Реализация и результаты

[Runtime](../../src/towr/domain/pc_npc_pistol_models.py) хранит отдельные typed state/shot/Reload proofs, PC owner/projection/runner применяют их по actual Skill и loaded state. [Source](../../src/towr/domain/pc_npc_pistol_source_models.py) связывает confirmations с полным canonical NPC; codec/schema расширены только для двух loadouts. Добавлен Ogre Pistol в shared ranged catalog, сохранены точные13PG rows. Исправлен обнаруженный narrow aggregate guard: counts теперь принимают actual exit Official/Pistol наряду с Dagger. [Правило](../rules/npc-profile-catalog.md#npc-pistol-reload-m61), [CLI](../examples/m61/README.md).

27новых проверок прошли адресными прогонами:9source,11native,6JSON/services и1actual process. Ближайшие checkpoint72 и133tests зелёные; это отдельные составные прогоны, не full regression. Native проверяет failure/partial/completion/overshoot/следующий shot, independent PC/NPC instances, Shield/armour-ignore/Prone/Fate/W10/Near Miss, Defenceless/Critical/Official Broken и replay. Process подтверждает реальные выстрелы/Reload и равенство sequential/spawn.208прежнихJSON byte-identical,106request/result pairs M9–M61 проходят offline schemas/native admission/full root echoes. Фактические команды и результаты — в [статусе](../project-status.md). Full project/wheel не запускались.
