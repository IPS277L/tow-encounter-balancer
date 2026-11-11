# M69: Blunderbuss и ordered nearby Staggered

Два PC начинают на Short против четырёх числовых Melee Minions. Оба держат Blunderbuss/BOTH без shield и имеют carried Sword/right backup. Weapon source —9required ranged fields ordinary firearm: BS3/Shooting4/I3/Dexterity4, true Lore/kit/ammunition/loaded и two_available_hands. [Правило](../../rules/equipment.md#pc-blunderbuss-m69), [контракт](../../decisions/ADR-0111-pc-blunderbuss-cluster-and-nearby-stagger.md).

Blunderbuss: Damage4 с обычной бронёй, +2d на Short, Reload3 после HIT/MISS. HIT запускает Staggered у nearby NPC независимо от primary Wound; MISS — нет. Второй Staggered использует SUFFER_WOUND и existing per-PC GM defeat_decisions. Других Attack/Protection Tests/actions волна не добавляет. Повторный выстрел другого PC видит фактические последствия первой волны.

В текущем PC JSON1 явно подтверждается исходная NPC-группа и полный порядок вторичных целей:

```json
"blunderbuss_nearby": {
  "initial_npc_clustered_confirmed": true,
  "target_priority": ["minion3", "minion1", "minion4", "minion2"]
}
```

Список содержит всех NPC ровно один раз. На HIT фиксируется full source/request snapshot, исключающий primary и уже defeated NPC. Сначала завершается primary Wound/GM ACK, затем волна и все secondary GM ACK, затем обычное продолжение/итог боя. Поражение primary не отменяет волну; пустой snapshot тоже получает completion. Заменять source order после HIT или проигрывать receipt повторно нельзя. При count search порядок фильтруется по сохранённым NPC.

PC остаются на Short и не входят в волну по premises текущей сцены. Если любой живой NPC подошёл в Close, Blunderbuss не может стрелять; на своём ходу PC достаёт backup. Charge3 primary сохраняется отдельно от Sword/Melee. Это не общее отключение friendly fire: смешанные Close-группы, другие Zone, named NPC/Abilities и PC movement не включены.

```powershell
$env:PYTHONPATH='src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m69/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m69/pc-melee-balance.request.json
```

Оба результата получены actual CLI: simulation seed42/4trials/6round budget→4objective/18actions/6started/2completed rounds, без потерь PC. Count search3–4Minions→2candidate×2trials, по2objective/4actions/2started/0completed rounds. Выборки демонстрационные, не точные вероятности или оптимальный состав.

[Simulation request](pc-melee-simulation.request.json), [result](pc-melee-simulation.result.json); [balance request](pc-melee-balance.request.json), [result](pc-melee-balance.result.json). Прежние240JSON M9–M68/NPC59/shared14 сохраняются; нет новой wire version, compatibility aliases или изменений других families.
