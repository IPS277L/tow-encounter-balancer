# ADR-0107: PC bows, Short opening и переход к melee

Дата: 2026-11-10. Статус: **принято и реализовано M65**. Пользователь выбрал Short opening + три bows + backup.

## Источники и причина выбора

Адресно прочитаны BOOK-PLAYER-GUIDE1.4 III Defence/Shooting68, IV Ranged Weapons94–95 и V The Battlefield114, Speed115, Combat Actions116, Manoeuvre117, Recover/Attack Tests118, Failed Attacks/Giving Ground119. Переиспользуются принятые M19/M20/M54/M60/M64, shared K1 ranged profiles/preparation/reload и текущие Wounds/Fate owners.

PG94 запрещает использовать ranged weapon при любом enemy в Close, если Close не входит в optimum этого оружия. У всех двуручных строк PG95 Close вне optimum. Поэтому запланированное после M64 простое добавление луков/арбалетов к неподвижной all-Close сцене не подходит. Это уточнение очереди, а не обнаруженный runtime bug или разрешение ослабить книжный guard.

PG114 различает Close (в пределах досягаемости) и Short (в той же Zone); соседняя Zone — Medium. Для первого выстрела из лука не обязательно вводить несколько Zone. PG116 разрешает один free move на своём ходу и incidental draw/swap. Сближение внутри одной Zone не равно Charge и не даёт +1d Charge. Outnumbering PG118 считается по Zone, а не только по Close-парам. Close miss PG94/119 не распространяется на неудачный Short shot.

## Принятая законченная функция

Открывающий обстрел на Short → свободное сближение NPC → продолжение PC на carried melee backup. Три совместимых лука используют одну free-reload ветвь:

| PC weapon | Optimum | Damage | Trait / зарядка |
|---|---|---|---|
| Shortbow | Short–Medium | 3 | +1d Shooting по Short; free reload |
| Warbow | Medium–Long | 3 | по Short обычный −1d вне optimum; free reload |
| Longbow | Medium–Long | 4 | по Short обычный −1d вне optimum; free reload |

Все2H; Blackpowder/Engineering Lore/kit не нужны. Начальный Short допустим для всех трёх, но Warbow/Longbow получают штраф. Positive Shortbow Trait подчиняется cap и Drained. Это осмысленный чанк общей механики, не три отдельные вехи. Crossbow/Repeater Crossbow остаются следующим чанком: у них отдельные Exacting/conditional Reload и armour Trait.

Первый Short-сценарий ограничен одной свободной Zone. Все PC находятся одной компактной группой; каждый NPC начинает на Short от этой группы. PC не отступают и не перемещаются. Живой NPC на своём ходу перед обычной Melee Attack свободно подходит к группе, если ещё не подошёл. После такого подхода он Close ко всем PC. Такое расположение и отсутствие преград подтверждает caller; Close не объявляется транзитивным свойством произвольных персонажей.

NPC следуют прежнему enemy_target_priority и не получают дополнительного action/Charge bonus. Убитый до своего хода NPC не двигается. Подход не происходит при source admission, при чужом ходе, после завершения боя или после резервирования action. Использование free move сохраняется в source-bound proof, Conditions/turn/proximity owner; повторное применение/чужой actor/изменённая исходная дистанция отвергаются. Existing K1 FreeMovementRequest требует пересечения Zone boundary — нельзя подделывать маршрут для подхода внутри Zone. Нужен небольшой явный typed proof этого incidental подхода, без общего языка правил или координатной системы.

На собственном ходу PC с луком после обязательных Wound/critical continuations переходит на объявленный1H backup, если **любой живой NPC уже Close**, либо если обе пригодные руки для лука больше недоступны. Близкий враг запрещает стрелять и в другую Short-цель. Переход односторонний, incidental, не занимает обычное действие; actual Recover при необходимости всё равно занимает своё действие. Drop/draw/использование рук имеют прежние Critical последствия. Не надо сначала подбирать выпавший лук, если требуется доступный backup. Нет автоматического kiting, стрельбы вопреки guard или возврата к луку после draw.

Без backup сохраняется фактическое состояние и честный UNSUPPORTED_PATH на настоящем собственном незанятом ходу, когда действительно нужен недоступный Shoot. Terminal objective, dead/Defenceless и незавершённые mandatory последствия имеют прежний приоритет. Наличие backup требует Strength≥2, сохраняет выбор из6существующих1H weapons и preferred hand. Shield с2H луком запрещён. Старые2H-melee и Pistol/Repeater fallback triggers не расширяются: Close для этих трёх1H firearms/Handbow разрешён и сам по себе не включает backup.

Это первый volley с дальнейшим обычным melee-боем, а не обещание повторяющейся безопасной стрельбы из лука по приближающимся волнами врагам. Сцена поддерживает оба исхода: все NPC побеждены до подхода либо оставшиеся подходят и бой продолжается после смены оружия.

## Ограничение первого Short encounter

Short opening допускает только ranged PC: три новых лука и три существующих Pistol/Repeater1H loadouts. Существующие1H источники/щит/Reload сохраняют смысл и могут продолжать Shoot после сближения. Ordinary self Recover policy прежняя; новых собственных Help/ally Recover ролей нет. Старые all-Close сцены сохраняют весь уже реализованный состав PC/NPC и прежние политики.

В Short-варианте NPC — простые authored numeric Minions с одной Close Melee Attack/Damage и Athletics Protection, без shield/особых Abilities/NPC Help/дополнительных атак/Net/Shooting/отдельных end phases. Книжные59loadouts пока не переносятся в новый пространственный вариант: их применимые range-sensitive способности нельзя неявно отключать. Count search использует несколько таких Minions, не подменяя named profiles authored числами ради обхода Abilities.

В Short opening `can_leave_zone=false`, без adjacent exit policy: Giving Ground/бегство через соседнюю Zone здесь не реализуются. Действующие Prone/Wound alternatives при repeated Stagger сохраняются. Место fallen/dropped PC предмета остаётся у неподвижной группы, не появляется remote pickup. Нет Cover, Difficult Terrain, Charge, Aim, другой Zone, скрытности/Unaware, PC movement, NPC speed differences или полноценного battlefield editor. Outnumbering по единственной Zone не меняется после сближения; Shooting его не получает.

## Текущий source и JSON1

Optional closed scenario field:

```json
"short_range_opening": {
  "party_clustered_confirmed": true,
  "npc_approach_clear_confirmed": true
}
```

Он означает описанный выше Short opening с фиксированной тактикой подхода/ответа, не автоматически выбранную стратегию. При наличии объекта требуется `facts.all_opponents_close=false` и `facts.can_leave_zone=false`. Без него прежнее `all_opponents_close=true` обязательно. Несогласованный flag, null/partial/extra fields, unsupported actor roles/NPC abilities или2H bow в прежней all-Close сцене отвергаются до RNG. Не выводить Short из одного false flag. Existing requests без нового optional поля не мигрируются; wire version остаётся PC JSON1, compatibility aliases не нужны.

Лук использует существующий PC key `ranged`, но без несуществующего Exacting Reload source:

```json
"weapon": "shortbow",
"ranged": {
  "ballistic_skill": 3,
  "shooting": 4,
  "ammunition_supply_confirmed": true
}
```

У трёх луков запрещены Initiative/Dexterity, initially_loaded, reload_hand_policy, repeater_bonus_policy и firearm facts: у них free preparation в составе выстрела, не отдельный Reload Test или заглушки false/null. У прежних трёх1H оружий их нынешний required source сохраняется. Native PcRangedProfile допускает weapon-specific absence, итоговую полноту проверяет PcMeleeDefinition; не подставлять WS/Agility или фиктивные reload characteristics. Initial grip для bows — `both`, carried backup — прежний backup_weapon_policy.

PC runtime обобщается до уже существующего shared FreeReloadWeaponState/ReloadableWeaponState. Один typed PC shot proof связывает соответствующее K1 execution с полным source и Attack; free reload не становится псевдо-cycle/Reload action. История выстрелов нужна даже при неизменном free-reload state. Actual active weapon, полный источник, Traits, hand use и retained owned state после backup сохраняются. NPC Pistol source/owner и остальные families не меняются.

Текущая дистанция до выбранной цели и наличие любого Close enemy вычисляются из owner, а не передаются дважды caller-ом на каждую Attack. Short shooting использует lawful Athletics Protection; Close-only Melee opposition не выбирается на Short. Close miss/Stagger и ranged restrictions получают фактическую дистанцию. Glorious/Near Miss/Wounds/Prone/Drained и два занятых bow grip arms используют прежние правила.

## Адресная приёмка

1. Три строки/2H/current source shapes, Short eligibility, no firearm/Exacting facts у bows, старые gun fields неизменны. Строгие malformed/cached source guards до RNG; all-Close bow source не принимается.
2. Literal native opening: Shortbow +1d, Warbow/Longbow −1d, Drained/cap, full armour; Short MISS без Close Stagger. Free reload не создаёт action/progress/cycle, missing/replayed shot proof отвергается.
3. NPC подходит только на собственном ходе, без action/Charge bonus, перед настоящей Melee Attack; killed/terminal NPC не двигается. Идентичность actor/turn/предыдущей proximity/однократность. До подхода два произвольных участника одной Zone не объявляются Close.
4. После первого подхода нельзя продолжать bow Shoot даже по другому Short NPC. Реальный draw с двумя здоровыми руками → active Melee; отсутствие backup даёт точный stop. При утрате руки/предмета, W12/14/15/18/20, Critical/Defenceless/Near Miss сохраняется необходимый prefix; не копировать всю старую wound matrix для каждого лука.
5. Existing1H guns в Short и после подхода используют прежние bonus/Reload/shield/backup, distance alone не включает их draw. Старые all-Close M64 и2H melee продолжаются прежним путём.
6. Trials/summary/count search/current schemas/full root/candidate echoes, zero-remaining-enemy terminal guards, независимые several PC/NPC instances. Public CLI example показывает opening и реальное продолжение на melee; прежние224JSON M9–M64 остаются побайтно прежними. Каталог59 не меняется.

Checkpoint — новые deterministic native/source/JSON cases, K1 ranged/free reload, M19/M20 grip/backup, M54/M60/M64, затронутые руки/Fate/Protection. Один actual sequential/spawn representative оправдан новым proximity owner/free-reload source/proof: выбрать trace с настоящим подходом и draw, не делать полную backend matrix. Full project/wheel автоматически не требуются; перед дорогой проверкой назвать её риск/scope. Подготовка этого решения требует только сверки документации/ссылок, не повторного M64 regression.

## Альтернатива и согласование

Меньший вариант — сначала тот же Short opening/NPC free approach только с тремя существующими1H ranged weapons; луки/free-reload owner/новый Close-trigger backup вынести в следующий законченный чанк. Это полезная пространственная возможность, но откладывает использование двуручных bows и добавляет ещё одно согласование scope.

Рекомендован цельный opening + три bows + описанный melee fallback. Здесь выбор тактики при Close enemy — решение сценария, не RAW-обязанность бросить лук. По [AGENTS.md](../../AGENTS.md) «Спрашивать при существенной неоднозначности правил, смене согласованного контракта или блокере с решением пользователя»: меняются публичный source, допустимая initial дистанция, runtime proximity и trigger backup. Выбор получен: полный opening + три bows + описанный backup. Source/schema/fixtures/examples обновлены вместе. [Статус](../project-status.md), [очередь](../roadmap.md#после-m66).

## Фактическая приёмка

21новая native/source/JSON/services проверка входит в составной checkpoint419tests:417прошли,2старых M9 source ожидания обновлены под текущие fields/Short coupling; после исправления весь M9 module18tests прошёл. Это составное адресное evidence, не отдельный единый зелёный419-run или full project regression. Один actual sequential/spawn test прошёл7.785s с настоящими approach/draw и совпавшими records/summary. Оба CLI-примера исполнены. Старые224JSON, current schemas/echoes и каталог59 проверены; точные команды/ограничения — в [статусе](../project-status.md). Wheel не собирался по согласованной политике.

Pure K1 preparation сохраняет raw profile Traits; pc_conditioned_ranged_attack применяет actual PC Drained перед Fate и связывает полный effective Attack. Это штатный owner шаг, shared K1 API не менялся. Для старых requests без profile range modifiers сохраняется исходный request object; unnecessary copying не требуется.
