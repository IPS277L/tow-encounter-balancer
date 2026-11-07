# ADR-0098: PC со щитом, занятые руки и восстановление снаряжения

Дата: 2026-11-07. Статус: **принято пользователем и реализовано; M53 завершена**. Выбраны полный weapon-first путь и restore_before_attack: отдельный standard Recover для dropped shield при свободной здоровой руке, weapon pickup первым.

## Источники и граница

Адресно сверены локальные BOOK-PLAYER-GUIDE1.4: гл.III Skills / Defence68; гл.IV Equipment / Melee Weapons92–93, Ranged Weapons94, Armour97; гл.V Actions116 / Recover и Attack118; Wounds Table190–191. Независимая read-only сверка подтвердила основные выводы. Лор о парировании не сужает напечатанный Trait Sword. Это адресная сверка, не полное перечитывание книги.

Реализована законченная функция **одноручное оружие + один щит** в нынешнем fixed Close PC-сценарии. Доступны шесть текущих1H оружий: Dagger, Staff, Axe, Sword, Warhammer, Morning Star. Shield не является вторым melee weapon; запрет dual wield Morning Star не запрещает этот комплект. Двуручный primary, переносимый shield для будущего backup, dual wield, shield bash, новый NPC ranged каталог и общий inventory не добавляются.

## Книжные эффекты щита

- PG97: щит даёт **+1 Resilience**, carried/held, а не worn. Бонус отдельный от нынешнего authored armour_bonus; второй раз в него не включается. Рабочий shield делает цель armoured даже без носимой брони. Ignores-armour использует Toughness, без бонусов брони и щита.
- PG68: held shield разрешает **Defence против Shooting/Throwing**. Сам щит не даёт дополнительного куба Defence. Для нынешнего NPC каталога этот новый путь достигается через Net; Shooting NPC автоматически не разрешаются.
- PG93: реально wielded пригодный Sword даёт +1d Defence, если PC не Staggered. Trait не ограничен Melee, поэтому действует и при Shield Defence против Throwing. Если Sword выпал/недоступен, его бонус исчезает, даже если shield сохранился. Drained подавляет этот bonus die.
- По Brawn/Trample остаётся Endurance, как в M51; наличие shield не разрешает Defence против Brawn. Числовой shield Resilience применим к обычному Damage, включая Trample; у primary Net Damage отсутствует.
- Unaware/Defenceless не Opposes. Наличие предмета не создаёт Test, Fate window или обход automatic Wound.

Fixed Protection policy M53: по Melee — Defence, если есть пригодное оружие или shield, иначе Athletics; по Throwing — Defence только с рабочим shield, иначе Athletics; по Brawn — Endurance. Не сравнивать профили автоматически ради более выгодного результата. Actual Skill, предметы, руки, Help и Fate связывать с текущим incoming Test.

## Source/JSON и состояние

Участник получает optional typed shield loadout, отсутствующий в прежних сценах. В текущем PC JSON1 реализовано conditional participant field:

```json
"shield": {
  "initial_hand": "left",
  "hand_conflict_policy": "weapon_first",
  "recovery_policy": "restore_before_attack"
}
```

Все вложенные поля обязательны, hand — точный left/right, противоположный initial_weapon_hand. Primary должен быть1H, initial grip — настоящий одинарный. В первом срезе shield не сочетается с2H/backup policy; он не выдаётся бесплатно при смене оружия. У участника без shield поле отсутствует; null/default-предмет не подставляется. В native модели optional значение означает отсутствие комплекта. Прежние176JSON M9–M52 не мигрируются; каталог57NPC остаётся прежним. Формат PC JSON1 и агрегаты не меняются.

Рантайм отделяет факт предмета от действующей защиты: **held**, **dropped**, **unavailable** и фактическая рука. `unavailable` после потери/недоступности руки не утверждает, что shield физически лежит на земле. Такой marker не даёт Resilience/Defence и не разрешает бесплатный pickup. Смена предметов, обязательная потеря и Recover pickup подтверждаются отдельными typed proofs либо точным body consequence; произвольный holds_shield флаг не заменяет историю.

Dynamic Resilience готовится из authored Toughness/armour_bonus и действующего shield **до каждой атаки**. Рана, выпавшая от этой атаки, не меняет задним числом её исходный Damage/Protection. После её mandatory consequences следующий Test использует новое снаряжение.

## Решение 1: конфликт рук и последствия ран

**Принят полный weapon-first срез:** продолжать выбранную борьбу, используя здоровую руку для оружия. Не считать руку свободной только потому, что она не держит weapon: там может быть shield или clutch stomach. Добровольные drop/swap — на собственном ходу по PG116; немедленной перестановки вне хода после чужой атаки нет.

| Последствие | Предлагаемое исполнение |
|---|---|
| 4, failed Endurance; 8; 12 | Random hand выбирается прежней policy; выпадает фактический weapon **или shield**, а не всегда weapon. Пустая рука не роняет предмет из другой руки. Near Miss отменяет саму Wound-причину |
| 12, injured hand | Не поднимать shield в травмированную руку до treatment. Это тактика, избегающая спорного passive-use/Critical; Attack/реальное использование руки сохраняют книжные последствия. Если для weapon нужна здоровая shield-рука, на своём ходу сначала оставить shield, затем восстановить weapon |
| 16, unusable arm | Shield в этой руке немедленно перестаёт быть рабочим после body ACK и получает unavailable marker. Книга не приказывает явно drop: ground location/pickup не выдумываются. Weapon в недоступной руке продолжает существующий1H путь смены руки; здоровая shield-рука предварительно освобождается на своём ходу |
| 18, clutch stomach | Сохранить прежнюю weapon-first цель: выбрать доступную неоружейную руку, при необходимости фактически drop shield и clutch этой рукой. Если она недоступна, применить существующий выбор другой руки/Defenceless. Reconciliation последующей утраты clutch-руки тоже учитывает shield, не создаёт третью руку |
| 20, lost arm | Shield в потерянной руке недоступен, без действия или бесплатной замены другой рукой. Книжные Defenceless/Critical сохраняются. Weapon/drop/body последствия не отменяются ради щита |

Если Sword выпал, а рабочий shield остался, PC может Oppose Defence, но без Sword Trait. Если shield выпал, Sword даёт Defence против Melee; против Net используется Athletics. Две занятые руки нельзя использовать для нового предмета без реального освобождения. Действие отсутствующей/неработающей рукой не создаётся.

**Меньшая альтернатива:** поддержать обычный shield и прямые drops, но при первом конфликте shield с нужной оружейной/clutch рукой либо unusable/lost shield-arm сохранять полный Wound/Fate/body prefix и завершать trial как UNSUPPORTED_PATH. Это ограничение симуляции, не поражение PC и не упрощение Wound. Меньшая альтернатива пользователем не выбрана.

Для16/20 недоступность действия предметом — вывод из анатомического правила; текст не описывает отдельное passive shielding. Полный предложенный срез явно снимает защитные эффекты недоступной руки. При12 автоматический Critical только за passive holding не вводится: щит выпал, и выбранная тактика его этой рукой не возвращает. Generic passive-use трактовка остаётся вне среза.

## Решение 2: когда возвращать выпавший щит

PG116/118 требуют настоящий **standard Recover** для pickup в Close enemy. Нельзя назвать dropped shield переносимым и вернуть его free draw. Один Recover имеет один object interaction; из текста не выводится безусловный pickup двух предметов одновременно.

**Принят restore_before_attack:** после обязательных последствий и проверки Defenceless восстанавливать dropped shield отдельным Recover, если есть свободная здоровая пригодная рука; он становится ещё одной явной причиной self Recover. Если выпали оба предмета, первым возвращать weapon, на следующем подходящем Recover — shield. Standard Staggered/Prone benefits того же действия сохраняются с прежними self/ally priorities; оружейный pickup использует object interaction первым. Если щит нельзя взять без нарушения weapon-first/clutch, не делать бесполезный Recover и продолжать разрешённую тактику.

**Альтернатива restore_with_standard_recover:** потеря одного shield не вызывает дополнительного действия; при уже выбранном standard Recover его можно вернуть свободным object interaction после приоритета weapon. PC чаще продолжает Attack без щита. Оба варианта являются стратегией, а не нормой книги. В runtime реализован только выбранный restore_before_attack; альтернативная policy не добавлена.

Pickup использует реальную руку и положение dropped предмета в Close-сцене. Нельзя восстановить unavailable shield, залечить рану Recover или удалить независимые Net/Wound Conditions. Получение ally Recover benefits само по себе не подбирает предмет получателя; чужой подбор/передача щита не входят в функцию.

## Интеграция и проверка принятой границы

Владелец PC связывает shield facts с actual drop/body/pickup/swap proofs; общие CombatAction/Recover primitives остаются прежними. Hand selection/usable weapon/Sword Trait/Protection Help должны учитывать занятость shield-руки. Defence Help относится к actual выбранному Test и не переходит в Athletics/Endurance после потери shield/смены source; unused Help не дублируется. Для ран12/14/15 сохраняются реальные Critical consequences использования руки и incidental/combat actions; forced drop не превращается в добровольную перестановку. Добровольный shield release вызывает Critical от14;15 явно разрешает сам drop, но последующий swap/Recover сохраняет его обычную Critical consequence. Это различие проверено literal journal tests.

План адресной приёмки:

1. Source hands/1H/закрытый shield object/optional absence, типы/unknown fields до RNG; прежние57NPC/176JSON неизменны.
2. Sword+shield/без Sword/без shield/Drained/Staggered против Melee и Net; Brawn Endurance; dynamic+1 Resilience/armoured/ignores-armour, без ретроактивного пересчёта первой атаки.
3. Literal4/8/12 drops каждой руки и failed/success Endurance/Near Miss;16/18/20 body sources, оружейная рука/clutch, отсутствие внеочередного swap, выбранные продолжения/точные stops.
4. Actual standard Recover/один предмет/weapon priority/selected shield recovery strategy; недоступная/травмированная рука, независимые Conditions, Critical/Defenceless/end phases, replay/alias/equipment forgery.
5. Help/Fate/trials/count search, current JSON1/full candidate echoes и полезные CLI-примеры. Один process representative при изменении transported states; ближайшие PC hand/weapon/Recover/Protection regressions. Full/wheel только по основаниям AGENTS.md.

## Согласование и результат

Пользователь выбрал полную обработку конфликтов рук и отдельный Recover ради dropped shield. Native body/equipment/Protection/Recover, conditional current JSON1 и CLI реализованы без миграции176прежнихJSON. Каталог NPC остаётся57. Меньшая stop-граница и restore_with_standard_recover не реализуются как скрытые альтернативы.

Независимое ревью выявило пропуск W14 Critical на добровольном release; он исправлен с сохранением W15 drop exception и проверен. Source/JSON, literal native, ближайшие PC зависимости и один реальный sequential/process representative прошли. Поддельное восстановление shield без pickup receipt отвергается при actual full-prefix admission; raw immutable snapshots сами по себе не являются сохранённым боем или save/resume API. [Статус и команды](../project-status.md), [публичные примеры](../examples/m53/README.md), [очередь](../roadmap.md).
