# ADR-0109: Handgun/Repeater Handgun в первом volley→backup

Дата: 2026-11-11. Статус: **принято и реализовано M67**. Пользователь поручил продолжить подготовленный чанк обоих Handgun в прежнем volley→backup срезе.

## Книжные источники и функция

Адресно перечитана BOOK-PLAYER-GUIDE1.4 IV Ranged Weapons95 и III Lore82/IV Blackpowder Kit99 по относящимся фрагментам. Переиспользуются PG94/107/110/114–119/123 и принятые M54/M60/M64–M66. Shared combat/reload profiles уже содержат обе строки, поэтому kernel каталог не дублируется.

| PC weapon | Hands / optimum | Damage | Расход |
|---|---|---|---|
| Handgun | 2H / Medium–Long | 5, ignores armour | каждый HIT/MISS → Reload3 |
| Repeater Handgun | 2H / Short–Long | 5, ignores armour | optional +3d → Reload5 |

Реализован законченный чанк обоих2H firearms через native/source/JSON/trials/count search/CLI в **нынешнем Short opening → approach NPC → melee backup**. Для Handgun Short допустим, но вне optimum: обычный −1d. Repeater Handgun на Short не получает этого штрафа. Любой Close enemy запрещает Shoot обоим. Ни одно оружие не получает Crossbow armoured Damage Trait; ignores armour использует прежнюю принятую firearm-логику текущей Toughness.

Repeater when_available выбирает +3d до initial roll/Fate, если PC не Drained; never/Drained — ordinary shot без нового reload cycle. Это bonus dice с обычным cap, не bypass/три Attack/несколько целей. При обрезанном cap выбранный бонус всё равно открывает именно5-success cycle. Обычный Handgun разряжается независимо от HIT/MISS/Drained. Бонус Lore не подставляется: Blackpowder здесь prerequisite, а не автоматический +1d к specialist Test.

## Действующая тактика сохраняется

NPC продолжают подходить на своём ходу. После подхода PC на собственном ходу использует declared1H backup даже при loaded Repeater never; при недоступном2H хвате действует тот же backup/точный stop. Shield запрещён, initial grip=BOTH; carry Strength≥2/preferred hand/6существующих melee backups прежние. Actual hand/drop/Recover/mandatory Wounds/Critical/Defenceless/terminal priorities не меняются. Retained loaded/empty3/5 state не запускает Shooting/Reload у active Sword.

Public example показывает первый volley и melee continuation. Полный fresh Shoot→Reload→Shoot, NPC ожидание/другая approach policy, PC movement/kiting, другие Zone, named NPC/Abilities/NPC shooters в Short-варианте не добавляются. Shared/PC Reload source binding3vs5 проверяется адресно в focused собственном K1 контексте, без объявления его новым encounter путём. Старые1H Pistol/Repeaters продолжают свои действующие Close Shoot/Reload/shield policies.

Blunderbuss требует отдельного nearby-Stagger source/исполнения, Hochland — mandatory Aim; включать их ради размера чанка и отключать эти Traits нельзя. Sling также не входит в эту функцию.

## Один текущий source и native граница

Добавлены PcMeleeWeapon.HANDGUN/REPEATER_HANDGUN в PC_RANGED_WEAPONS и общую2H ranged группу. Firearm facts проверяются отдельно от1H/2H и free-reload/Exacting/Repeater. Группы3free bows/2Crossbow и source прежних8ranged сохраняются.

Handgun использует существующий `pc.ranged` с9required fields:

```json
"weapon": "handgun",
"ranged": {
  "ballistic_skill": 3,
  "shooting": 4,
  "initiative": 3,
  "dexterity": 4,
  "has_blackpowder_lore": true,
  "has_blackpowder_kit": true,
  "ammunition_supply_confirmed": true,
  "initially_loaded": true,
  "reload_hand_policy": "two_available_hands"
}
```

Repeater Handgun дополнительно требует repeater_bonus_policy=when_available/never, у ordinary Handgun поле запрещено. Оба требуют true Lore/kit/supply/initial load; числа не выводятся из WS/Agility. Две пригодные руки Reload — прежняя явно принятая scenario policy, не новое утверждение RAW. Engineering Kit и отдельные Lore/Kit Tests не добавляются.

Current PC JSON1/key ranged/short_range_opening/armoured source прежние. Новый wire version/deprecated period/миграция232прежнихJSON M9–M66 не нужны. Catalog NPC59 и shared13PG+1GM ranged profiles не расширяются.

До M67 native Close-stop назывался PcBowCloseUnsupported/bow_close_enemy, хотя в M67 он охватывает и firearms. Принято нейтральное **PcRangedCloseUnsupported/ranged_close_enemy** и source ID suffix `:ranged:close`, с обновлением imports/union/tests/current docs без compatibility aliases. Поля actual actor/round/Close enemy IDs и смысл точной остановки прежние; фиктивная Wound не создаётся. JSON aggregates не содержат этот native reason/type и не меняются. Raw snapshots по-прежнему не save/resume API.

## Новая адресная приёмка

- Строгие source shapes обоих firearms: Lore/kit true, ordinary/repeater policy, BOTH/no shield/Short-only, cached/foreign/null/partial facts до RNG. Старые8ranged источников неизменны.
- Literal Short shots: Handgun −1d, minimum pool при низком BS, Damage5/ignores armour без Crossbow +1; Repeater +3d/обычный cap. В частности BS1/cap2 не позволяет отменить выбранный5-success reload из-за clipping. Drained сохраняет отрицательный range modifier обычного Handgun и отключает optional bonus/flag/cycle Repeater до Fate.
- HIT/MISS связывают правильный instance и cycle3vs5; never/Drained не открывают Repeater cycle. Независимые несколько PC/профилей, Glorious/source identity/replay, retained state после настоящего approach/draw. Focused legal Reload проверяет3vs5/actual Dexterity без копирования всей K1 матрицы и без fresh-cycle обещания.
- Общий ranged Close-stop сохраняет предыдущие bow/Crossbow случаи, own-turn/Recover/mandatory/terminal границы; no-backup firearm не обходит PG94. Actual melee после draw не наследует ignores armour/Repeater bonus. Reuse ближайших M54/M60/M64–M66 hand/Fate/Protection checks по риску.
- Services/count search/current schemas/full root/candidate echoes, новый CLI volley→backup и побайтная сохранность старых232JSON/каталога59. Общие kernel profiles/Reload и обычные Traits не переопределяются.

По умолчанию — новые deterministic cases и ближайшие зависимости, без автоматического повторения всего247/419 checkpoint. Wheel не нужен при прежних discovery/resources/dependencies/entry points. Native Stop переименовывается, но worker records остаются компактными: process проверку выбирать по реальному риску переноса типов, не повторять полную backend matrix. Подготовка proposal проверяет только документацию/ссылки, без игровых прогонов.

## Согласование и результат

Пользователь поручил продолжить подготовленный чанк обоих Handgun в прежнем volley→backup срезе. Согласованы новые public weapon/source варианты и нейтральное native имя Close-stop по [AGENTS.md](../../AGENTS.md). Полный повторный ranged цикл и новая тактика не добавлены.

Новые10literal native tests — OK0.717s;5integration source/JSON/services/search — OK2.395s после исправления ожидания projection в тесте: удалённые NPC правильно исключаются из target/defeat policies. Production defect не обнаружен. Ближайшие196tests единым составным прогоном — OK25.730s. Это адресные прогоны, не единый211/full regression. Actual CLI simulation и balance выполнены, фактические команды и текущая проверка — в [статусе](../project-status.md), примеры — [M67](../examples/m67/README.md). Shared K1 rules не менялись, wheel/full/backend matrix не повторялись без нового основания.

Сохранены232старыхJSON, каталог59NPC и14shared ranged profiles. Текущий PC JSON1 без compatibility aliases; renamed native stop проверен отдельно, raw snapshots не save/resume API. [Очередь](../roadmap.md#после-m67).
