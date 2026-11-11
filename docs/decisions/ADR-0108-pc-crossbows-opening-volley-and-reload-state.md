# ADR-0108: Crossbow/Repeater Crossbow в Short opening

Дата: 2026-11-10. Статус: **принято и реализовано M66**. Пользователь выбрал оба арбалета: первый volley → backup, без новой NPC тактики.

## Источники и законченная функция

Адресно перечитаны BOOK-PLAYER-GUIDE1.4 IV Ranged Weapons94–95; переиспользованы III Shooting68/Dexterity70, V107/110/114–119/123 и принятые M54/M60/M64/M65. Сверены shared ranged combat/reload profiles, PC ranged preparation, Short proximity и backup/stop selectors.

Следующий совместимый чанк — **Crossbow и Repeater Crossbow: первый залп с Short → фактическое состояние заряда → продолжение на melee backup после подхода NPC**. Оба оружия2H, не имеют Close в optimum и запрещены в прежнем all-Close source.

| PC weapon | Optimum | Damage / Trait | Расход и зарядка |
|---|---|---|---|
| Crossbow | Short–Long | 4, +1 Damage по armoured target | каждый HIT/MISS открывает Reload2 |
| Repeater Crossbow | Short–Medium | 4, optional +1d Shooting | только выбранный bonus открывает Reload3 |

Repeater Crossbow не наследует Crossbow +1 Damage: таблица PG95 не даёт ему этот Trait. Ни один не игнорирует броню. Armoured permission берётся из полного Resilience source, не из одного Toughness/bonus comparison. Damage bonus обычного Crossbow сохраняется при Drained, который запрещает bonus dice, а не Damage.

Это2H ranged с Exacting state, отдельная от free-reload bows группа. Нельзя просто включить их в PC_BOW_WEAPONS и тем самым запретить их собственные reload fields или создать FreeReloadWeaponState. Shared K1 profiles уже содержат обе строки и требуемые2/3successes; новых копий каталога/DSL не нужно.

## Достижимый public trial и выбранная тактика

В нынешней M65 сцене все живые NPC на своём ходу подходят к группе PC. Затем любой такой Close enemy запрещает Shoot из Crossbow/Repeater Crossbow, даже по другой Short-цели. PC на собственном ходу выбирает объявленный1H backup, независимо от того, осталось ли primary loaded. NPC, побеждённые до своего хода, не подходят; terminal objective не требует reload/draw.

**Новый публичный пример не будет демонстрировать цикл Shoot→Reload→Shoot.** При текущей фиксированной тактике после подхода выбирается melee, а не Reload. Состояние обычного Crossbow сохраняет opened cycle2/empty, Repeater при when_available — cycle3/empty, при never — loaded без нового cycle. После draw весь owned state сохраняется и не вызывает ложный Reload/Shooting. Это активный выбор принятой стратегии, не отключение применимого weapon Trait.

Рекомендуется добавить оба loadouts в эту существующую законченную возможность, без новой NPC wait/recovery/approach policy. Не заставлять NPC без причины ждать, не давать PC дополнительный выстрел между чужими ходами и не объявлять focused/kernel проверку реальным fresh encounter. Меньшая по игровому контенту альтернатива — сначала обсудить изменение сцены/поведения NPC для достижимой повторной стрельбы, а затем расширять оружие.

Existing1H guns и free-reload bows сохраняют свои принятые действия. No-backup/неработающий хват/Defenceless/Recover и mandatory Wound tails имеют прежние точные границы. Для обоих Crossbow2H нужны две пригодные руки даже для loaded shot; один usable arm может использовать только доступный carried1H backup. Shield запрещён, carried backup сохраняет Strength≥2/6supported1H/preferred hand. Автоматического возврата к Crossbow нет.

## Текущий source, без смены версии

Добавить PcMeleeWeapon.CROSSBOW/REPEATER_CROSSBOW. В текущем PC JSON1 сохраняется `pc.ranged` и optional short_range_opening с M65 facts/GM confirmations. Другие ranges/Zone, named NPC/Abilities или NPC ranged в Short-вариант не добавляются. Все прежние228JSON M9–M65 и каталог59 сохраняются без миграции.

Crossbow требует closed ranged object:

```json
"weapon": "crossbow",
"ranged": {
  "ballistic_skill": 3,
  "shooting": 4,
  "initiative": 3,
  "dexterity": 4,
  "ammunition_supply_confirmed": true,
  "initially_loaded": true,
  "reload_hand_policy": "two_available_hands"
}
```

Repeater Crossbow имеет тот же источник и обязательный repeater_bonus_policy=`when_available` либо `never`. У обычного Crossbow этот field запрещён. Оба запрещают firearm Lore/kit facts: PG95 относит Blackpowder requirement к firearms, а не crossbows; Engineering Lore/Kit для обычной зарядки не требуются. Не подставлять null/false facts или WS/Agility вместо явных BS/Initiative/Skills. Initially loaded — прежний fresh source premise, не новый raw-state save/resume API.

Две пригодные руки Reload — прежняя явно принятая scenario policy, распространяемая на новые2H Exacting loadouts, а не новое утверждение RAW. Описание reload characteristics остаётся полным, даже когда принятая encounter тактика после первого выстрела выбирает backup. Сам запрет Shoot в Close не объявлять запретом книжной Dexterity Reload; законный K1 Reload и выбранное encounter действие — разные проверки.

Начальный grip=`both`. В native/source guards разделить2H ranged grip/Close restriction, free-reload state, firearm facts и optional bonus по actual weapon profile. Ordinary Crossbow не должен ошибочно требовать repeater policy, а Repeater Crossbow — Blackpowder facts. Existing three1H/free bows source shapes не меняются; compatibility aliases/deprecated period/новый wire version не нужны.

## Исполнение и source binding

Crossbow +1 Damage по armoured source включается один раз в полный prepared Attack и связывается с K1 canonical profile. PC owner восстанавливает unprepared damage modifiers перед profile preparation так же явно, как range dice в M65; бонус не дублируется и не остаётся после active Sword draw. Full armour Resilience не подменяется Toughness. Explicit armoured=false при положительном bonus не даёт Crossbow Trait.

Repeater bonus фиксируется до initial roll/Fate и подчиняется обычному cap. When_available при Drained становится ordinary shot без modifier/bonus flag/new cycle; cap saturation не отменяет выбранный бонус. HIT/MISS расходуют заряд ровно по actual profile trigger. Ordinary Crossbow всегда разряжается; никогда не превращать его в free-reload bow из-за2H grip или отсутствия Blackpowder Lore.

Shared K1 Exacting Reload2/3 и PC reload builder связываются с фактическим spent weapon instance/cycle. Адресная focused проверка может использовать настоящее состояние первого выстрела и отдельный собственный K1 reload контекст, но это не evidence достижимого Reload в текущем fresh M66 trial. Existing K1 failure/partial/overshoot/progress/replay checks переиспользуются; не копировать их матрицу только ради новых enum values. Case, когда уже начатый Reload применяется по правилам в подходящем контексте, не оправдывает обход actual encounter backup/Close guard.

Actual active weapon определяет Skill/Damage/Traits/hand use. Изначально это Shooting с2H grip; после draw — прежний Melee backup с retained ranged instance. W12/14/15/16/18/20, Critical, Near Miss, Glorious/Drained/Defenceless и projection identity checks сохраняют source-bound prefix. No-backup Close stop не получает фиктивную Wound; необходимый ordinary Recover исполняется по действующей policy.

## Адресная приёмка

1. Две строки/2H/full Exacting source, initially loaded и no firearm facts; bonus policy только Repeater. Shield/all-Close/partial/null/extra/foreign-type/cached source отвергаются до RNG. Прежние6ranged (3oneH +3bows) сохраняют точные source shapes.
2. Literal Short shots: Crossbow Damage4/+1armoured, printed armoured=false/full Resilience и никакого бонуса у Repeater. Trait остаётся при Drained и исчезает после Sword draw. Base/effective Fate preparation и forged/doubled Damage modifiers проверяются.
3. Ordinary HIT/MISS→один empty cycle2; Repeater when_available→cycle3, never/Drained→loaded/no cycle. +1d/cap/Fate choice/source IDs/independent actors без псевдо-патронов и автоматической дозарядки.
4. Реальный NPC approach → own-turn draw с двумя здоровыми руками; loaded Repeater never тоже переключается из-за Close. No-backup stop, чужая Short-цель при любом Close enemy, недоступный2H хват/mandatory consequences. Retained empty/loaded instance не вызывает Shooting/Reload после backup.
5. Адресная PC↔K1 Reload binding проверка источника/target2vs3; existing K1 Exacting module. Явно отделять focused context от fresh journal; не заявлять новое поведение NPC или достижимый полный public Reload cycle.
6. Native/source/JSON/trials/count search/current schemas/full root/candidate echoes и CLI первого volley→melee. Старые228JSON побайтно прежние, NPC каталог59, existing bow/gun/руки/Fate/Protection paths сохранены.

По умолчанию новые deterministic cases и ближайшие K1 ranged/preparation/Reload, M54/M60/M64/M65/hand/backup. Не повторять весь дорогой419 checkpoint автоматически. Новые enum values/профили в существующих source/state типах не требуют отдельного wheel или полной backend matrix; process regression нужен только при выявленном изменении serialization/исполнения или новом риске. До согласования — только источники/документация/ссылки, без игровых прогонов.

## Согласование

По [AGENTS.md](../../AGENTS.md): «Спрашивать при существенной неоднозначности правил, смене согласованного контракта или блокере с решением пользователя». Здесь расширяются public weapon/source boundary и2H Exacting loadouts. Пользователь выбрал **оба Crossbow в нынешнем первом volley→backup срезе**; иная сцена для полного Reload cycle не включена. Выбор получен, public source/code/schema/fixtures/examples обновлены вместе. [Статус](../project-status.md), [очередь](../roadmap.md#после-m66).

## Уточнение доставки full armoured source

Принятая проверка explicit armoured=false требует сохранять существующее native Resilience.armoured при JSON roundtrip authored numeric NPC. Поэтому optional exactbool field разрешён для authored definition.resilience, None по-прежнему пропускается; fresh current_resilience проверяется полностью. Net сохраняет required true, остальные canonical book loadouts остаются без нового поля. Это часть корректного source для одобренного Crossbow Trait, не новая NPC Ability/тактика или изменение остальных families. Предыдущие228JSON не мигрировались.

## Фактическая приёмка

247адресных tests — OK/44.185s, включая19новых native/source/JSON/services tests, shared ranged/preparation/Reload, ближайшие hands/backup/Pistol/Repeaters/bows и Net metadata guards. Оба CLI-примера исполнены. Source/offline schemas/full echoes/старые228JSON/каталог59 проверены; точные команды — в [статусе](../project-status.md). Это адресный составной checkpoint, не full project regression. Новых native state types/backend mechanism нет; process matrix и wheel по согласованной политике не повторялись.
