# M65: первый залп из луков и продолжение на melee backup

Три PC начинают на Short от противников в одной Zone. NPC на своём ходу свободно подходят к группе и атакуют. На следующем собственном ходу PC меняет лук на объявленный запасной меч и продолжает бой. [Правило оружия](../../rules/equipment.md#pc-bows-m65), [Short opening](../../rules/combat.md#pc-short-opening-m65), [контракт](../../decisions/ADR-0107-pc-bows-short-opening-and-melee-backup.md).

| PC | Оружие | Shooting на Short | Damage |
|---|---|---|---|
| pc1 | Shortbow | +1d | 3 |
| pc2 | Warbow | −1d вне optimum | 3 |
| pc3 | Longbow | −1d вне optimum | 4 |

Все луки двуручные, initial grip=`both`, без shield. Боеприпасы подтверждены; зарядка бесплатна в составе выстрела. Их `ranged` содержит только:

```json
"ranged": {
  "ballistic_skill": 3,
  "shooting": 4,
  "ammunition_supply_confirmed": true
}
```

Reload/firearm/repeater поля у лука запрещены. У прежних Pistol/Repeater их source остаётся прежним. Bow Damage фиксирован и не зависит от Strength; в этих примерах Strength4 повышает Damage запасного Sword. Toughness5/armour1, explicit Fate policies и остальные числа сохранены в полном request.

Новый optional scenario object:

```json
"short_range_opening": {
  "party_clustered_confirmed": true,
  "npc_approach_clear_confirmed": true
}
```

Он требует `facts.all_opponents_close=false` и `facts.can_leave_zone=false`. Short находится внутри одной Zone; соседняя Zone — Medium. PC сгруппированы, не отступают, путь NPC свободен. Все участники осведомлены: первый залп обычный Opposed Shooting, без засадного setup turn. Простые authored Minions имеют Toughness4/armour1, Athletics Protection и одну Close Melee Attack. Это числовой сценарий GM, не новые именованные книжные NPC.

Подход не является Charge и не расходует обычное действие. Сблизившийся NPC Close ко всем PC группы. Любой такой живой враг запрещает стрелять из лука, в том числе по другой Short-цели. На собственном ходу PC использует свой `backup_weapon_policy` — здесь Sword в правой руке. Смена односторонняя; условия рук/Wounds/Recover сохраняются. Без backup бой честно остановится на реально недоступном Shoot, сохранив выполненный prefix. Старые три1H ranged weapons могут продолжать Shoot/Reload в Close и не меняют оружие только из-за сближения.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m65/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m65/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): seed42,4trials,6round limit,4NPC;4objective/0party defeated/0limit/0unsupported,55actions,12started/8completed rounds, без потерь PC. [Balance request](pc-melee-balance.request.json) и [CLI result](pc-melee-balance.result.json):3–4Minions,2состава по2trials; оба дали2objective,16/28actions. Это демонстрационные выборки, не истинные вероятности или доказательство оптимального состава.

Actual sequential/spawn representative использует этот source и два trial seed; проверены настоящие approach/draw, free-reload shots, сохранённый bow после смены оружия и полное равенство records/summary. Все224прежнихJSON M9–M64 остаются побайтно прежними; current PC JSON1 и каталог59 сохранены.

В Short-вариант пока не входят named NPC/Abilities, NPC shooters/shields/Help, другие Zone, Give Ground/выход, Charge, Aim, Cover/terrain, PC movement/kiting и новые helper роли. Прежние all-Close сценарии сохраняют свои возможности.
