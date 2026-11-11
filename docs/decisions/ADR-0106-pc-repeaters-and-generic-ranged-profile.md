# ADR-0106: PC Repeaters и единый ranged source

Дата: 2026-11-08. Статус: **принято и реализовано M64**. Пользователь выбрал оба Repeaters и общий ranged source.

## Нормативная функция и источники

Следующий чанк — PC Repeater Handbow и Repeater Pistol с существующим K1 conditional Reload, через весь текущий PC encounter/trials/search/JSON1/CLI. Оба допускают Close в optimum, поэтому пространственный бой не нужен. Обычный Pistol сохраняется, его цикл Shoot→Reload3 не заменяется Repeater правилами.

Адресно прочитаны BOOK-PLAYER-GUIDE1.4 IV Ranged Weapons94–95, III Lores82/88 и IV Tools & Kits98–99. Переиспользованы Shooting68/Dexterity70, pools107/Exacting110/Conditions123 и принятые M54/M55/M60/M63. Проверены existing ranged combat/reload profiles и K1 preparation/composite source guards.

| Weapon | Optimum / hands | Damage | Бонус по выбору | Reload после бонуса |
|---|---|---|---|---|
| Repeater Handbow | Close–Short /1H | 4 | +1d Shooting | 3successes Dexterity |
| Repeater Pistol | Close–Short /1H | 5, ignores armour | +2d Shooting | 3successes Dexterity |

Это обычные bonus dice с обычным cap, не bypass. Повышение dice не является дополнительным Attack. Shared profiles уже содержат оба weapon IDs, Damage/traits и AFTER_OPTIONAL_BONUS trigger. После завершённого обычного выстрела без bonus state остаётся loaded без нового cycle; после bonus выстрела HIT/MISS открывают новый Reload cycle. Это действующий книжный/K1 контракт, не finite magazine simulator или обещание бесконечного фактического боезапаса.

PG95 требует Blackpowder Lore для firearms; Handbow — crossbow, не firearm. PG82/99 подтверждают Lore/kit для blackpowder Reload. Handbow не получает выдуманного Blackpowder/Engineering Lore или Engineering Kit requirement: обычная зарядка не равна tinkering. Ammunition supply остаётся явным premise PG94, для Handbow это болты.

## Принятый законченный scope

Добавить оба1H loadouts с optional shield и прежним carried1H backup при Strength≥2. Переиспользовать M55 release→Reload→shield Recover и M60 fallback только при empty/одной пригодной руке. Generic ranged source/state/preparation должен одинаково работать для обычного Pistol и двух Repeaters; не создавать параллельные Pistol и Handbow pipelines.

Два explicit source режима бонуса:

- `when_available`: использовать профильный бонус на каждом loaded Shoot, когда PC не Drained. Drained запрещает bonus dice, поэтому обычный shot без bonus не открывает Reload. Cap saturation не запускает скрытую оптимизацию: если бонус выбран, Reload обязателен даже когда итоговый pool не вырос из-за cap.
- `never`: обычные shots без бонуса, без открытия conditional Reload. После каждого нового Test proof/slot/receipt всё равно обязателен, даже если weapon state численно не изменился.

Это fixed тактика, не auto best-mode/поиск ожидаемой выгоды. Моменты выбора предшествуют initial roll/Fate; rerolls/исход HIT/MISS не меняют решение задним числом. Обычный Pistol не принимает repeater_bonus_policy и по-прежнему расходует заряд на каждом HIT/MISS.

Источники initially loaded, sufficient ammunition, BS/Shooting/I/Dexterity и `two_available_hands` остаются явными. Две руки Reload — прежняя выбранная GM/scenario конкретизация, предлагаемая и этим двум loadouts, не новый RAW. Для firearm в fresh source подтверждены Lore/kit; для Handbow эти fields отсутствуют. Empty state может требовать Reload даже если PC позже стал Drained: уже начатый cycle нельзя отменить обычным shot.

Когда conditional gun остаётся loaded и одна рука недоступна, loaded shot сохраняется и не запускает backup. Если предыдущий bonus открыл cycle и Reload реально невозможен одной рукой, применяется объявленный1H backup либо честный stop. Shield не сбрасывается ради несуществующего Reload в режиме never. Critical/hand/grip/drop/Recover/Defenceless/terminal/mandatory priorities прежние.

## Один текущий PC JSON1 source и миграция

Принято заменить PC `pc.pistol` общим **`pc.ranged`** для Pistol/Repeater Handbow/Repeater Pistol. Старый PC key больше не принимается; compatibility alias/параллельный старый формат/новая версия/deprecated период не нужны. Это соответствует AGENTS.md single-current-contract политике. **NPC enemies[].pistol и NPC firearm owners не переименовываются**: у них прежняя отдельная source boundary.

Пример Handbow:

```json
"weapon": "repeater_handbow",
"ranged": {
  "ballistic_skill": 3,
  "shooting": 4,
  "initiative": 3,
  "dexterity": 4,
  "ammunition_supply_confirmed": true,
  "initially_loaded": true,
  "reload_hand_policy": "two_available_hands",
  "repeater_bonus_policy": "when_available"
}
```

У Pistol и Repeater Pistol дополнительно required true `has_blackpowder_lore`/`has_blackpowder_kit`; у Handbow эти fields запрещены, не false/null заглушки. `repeater_bonus_policy` требуется только у двух Repeaters, ordinary Pistol его запрещает. Non-ranged PC не принимает ranged object. Core characteristics/skills не выводятся из WS/Agility и не подставляются parser-ом.

Native профиль — один typed PcRangedProfile, с точными optional firearm facts/bonus policy и окончательной weapon-aware проверкой в definition. PC runtime/proofs/helpers обобщить до ranged названий; активное оружие отдельно от retained owned state после backup. Не сохранять PcPistolProfile/PcPistolShotProof aliases исключительно ради старых imports. K1 shared IDs/profiles не переименовывать и не копировать.

Мигрировать current source код/схемы/исполняемые примеры/тесты вместе. В220прежнихJSON M9–M63 преобразовать **только PC profile key** во всех actual root/candidate echoes; ordinary Pistol numeric fields/choice/Fate/targets/counts/metrics остаются прежними. Не переименовывать NPC pistol по случайному совпадению строки. Примеры без PC Pistol сохранить побайтно. Для изменённых документов проверить точную semantic equality с заранее ожидаемым PC-key transform, не регенерировать исторические Monte Carlo исходы без причины. Новый пример хранит фактический M64 CLI result.

## Интеграция без потери принятых правил

Actual active weapon определяет Shooting против Melee после backup; наличие owned ranged state не даёт ложного Shoot/Reload/stop. Generic typed shot proof связывает base preparation/optional choice/effective Fate request/kernel receipt и cycle. Missing/forged proof недопустим и для обычного Repeater shot с неизменившимся loaded state. New cycle ID нужен только при фактическом расходе/bonus; no-bonus Repeater не создаёт фиктивной пустой Reload истории.

Repeater bonus добавляется до initial roll/обычного cap, передаётся один раз через preparation/action/receipt. При Drained его нет вместе с flag=false/cycle=None; нельзя скрыто оставить флаг расхода при удалённом modifier. K1 требует профильную величину и согласованный flag/cycle. Сохраняются Shooting Prone penalty/no Melee bonuses, полный Trait armour-ignore только у pistols, lawful NPC Protection preflight/Stealth/override sources всех59loadouts.

M63 Melee opposition/Protection Help/Fate не тратят заряд и не запускают Repeater bonus. PC собственной Shooting Help роли не получает, Pistol/Repeater PCs сохраняют ordinary self Recover. Другой PC может помогать их настоящей Melee Attack после backup либо Protection по существующим policies. NPC firearms/Shooting Help/Reload owners и mixed count projection сохраняются. Имя класса/поле могут меняться, их runtime meaning и source binding не теряются.

## Адресная приёмка

1. Обе новые строки/обычный Pistol, conditional field guards/strict types/full source до RNG, отсутствие Blackpowder/Engineering requirement Handbow. Shield/backup/carry/opposite hands/ordinary role guards; unknown/retired PC pistol field отвергается, NPC pistol source прежний.
2. Оба режима, профильный +1/+2/обычный cap, Drained→ordinary shot, ordinary state unchanged без missing proof/replay loophole; bonus HIT/MISS→ровно один cycle, partial/failure/overshoot Reload3→следующий Shoot отдельным действием. Между initial roll и Fate режим не меняется.
3. Actual Handbow Damage4 против полной armour/shield Resilience, Repeater Pistol5/ignores armour против Toughness. NPC lawful Protection/Stealth/overrides, independent multiple PC/NPC weapon instances. Defenceless/Near Miss/Glorious/W10/Critical сохраняют prefix.
4. Shield release/pickup только при нужном Reload, one-hand loaded shot, empty unavailable Reload→backup/stop; retained owned state не стреляет после draw. Hand12/14/15/16/18/20 и M63 protection использовать адресно по рискам, не копировать полную старую матрицу для каждого weapon.
5. Native journal/trials/summary/search/current schemas/full root/candidate echoes и CLI examples двух weapons/двух режимов. Миграция220JSON подтверждена точным ожидаемым semantic transform, unaffected bytes/59NPC definitions сохранены. Чужие NPC Pistol fields не изменены.
6. Один actual sequential/spawn representative с новым source profile/type и настоящими bonus/Reload/ordinary shots: новые native class names/source shape требуют проверки передачи процессу. Старую полную module/console/backend matrix не повторять, M33spawn случайно не включать.

Checkpoint — новые native/source/JSON cases, shared conditional Reload/preparation и ближайшие M54–M55/M60–M63/руки/Fate/Protection/backup. Перед составным прогоном назвать scope. Full project/wheel не нужны автоматически: Python modules остаются внутри existing package discovery, resources/dependencies/entry points прежние; static imports/offline schema refs проверить. Старые class/module imports должны отсутствовать в current code/tests, а не маскироваться aliases.

## Меньшая альтернатива и согласование

Меньший вариант — сначала только Repeater Pistol с тем же общим ranged contract и явными режимами, отложив Handbow/non-firearm branch. Основная миграция/generic state/conditional Reload всё равно нужна. Выбран чанк обоих weapons с существующими shield/backup, без отдельной вехи на каждый слой или одно оружие.

По [AGENTS.md](../../AGENTS.md): «Спрашивать при существенной неоднозначности правил, смене согласованного контракта или блокере с решением пользователя». Здесь меняются PC profile key/native API, weapon enum/conditional facts и тактика бонуса/Reload. Выбор получен: оба Repeater, общий ranged source, текущие shield/backup policies. Миграция выполнена без legacy aliases. [Статус](../project-status.md), [очередь](../roadmap.md#после-m66).

## Результат проверки

338 адресных тестов K1 ranged/preparation/Reload/Protection и PC source/руки/backup/Fate/JSON M54–M64 прошли единым составным прогоном (38.228s);19новых native/JSON tests входят в это число. Один actual sequential/spawn representative —1OK/5.035s, содержит оба оружия, bonus/ordinary shots и настоящий Reload. CLI simulation/count search исполнены;112current request/result pairs, exact semantic migration36JSON/184unaffected bytes и59NPC проверены. Полные команды и актуальный следующий шаг — в [статусе](../project-status.md). Это не full project regression; wheel не запускался по согласованной политике.
