# M55: Pistol со щитом

PC начинает с заряженным Pistol в правой руке и щитом в левой. После выстрела при доступных руках он оставляет щит, перезаряжается до3накопленныхsuccesses, затем возвращает щит отдельным standard Recover перед следующим выстрелом. Завершение Reload не даёт бесплатный pickup или Shoot. [Принятый контракт](../../decisions/ADR-0100-pc-pistol-shield-reload-priority.md), [правило](../../rules/equipment.md#pc-pistol-shield-m55).

Используется нынешний PC JSON1 без новых полей. Полный `pc.ranged` и остальные данные стрелка берутся из [M54](../m54/README.md). На уровне party participant добавляется существующий loadout:

```json
"initial_weapon_hand": "right",
"shield": {
  "initial_hand": "left",
  "hand_conflict_policy": "weapon_first",
  "recovery_policy": "restore_before_attack"
}
```

Начальные руки противоположны. Pistol-PC сохраняет ordinary Attack/self Recover, без backup/собственных Help/ally Recover policies. Blackpowder Lore/kit/supplies подтверждены явно, NPC имеют lawful выбранную Athletics либо Defence со щитом.

Пока Pistol пуст, shield pickup запрещён даже как object interaction другого Recover: так не возникает цикл pickup/release. Weapon pickup и снимаемый Prone сохраняют приоритет; щит сбрасывается непосредственно перед доступным Reload. Если выпали оба предмета, сначала возвращается оружие, затем при необходимости выполняется Reload, и лишь после него — Recover щита. Когда Pistol loaded, действует обычный weapon→shield pickup порядок M53.

Working held shield даёт+1Resilience и разрешает Defence против Net; после release — Athletics. Pistol не имеет Sword Trait, по Brawn/Trample остаётся Endurance. W12 допускает Reload травмированной рукой с Critical, но щит этой рукой не поднимается. Недоступная рука не блокирует допустимый loaded shot: stop возникает лишь при фактически недоступном Reload/grip после необходимых продолжений. Two_available_hands — ранее выбранная GM/scenario policy. Terminal objective не требует Reload/возврата щита. Drop и Recover не меняют заряд/progress/cycle.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m55/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m55/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json):1PistolPC со щитом, BS3/Shooting4/Initiative3/Dexterity4 и armour_bonus0 против2Footpads+1Net Goblin; seed42,6trials,8rounds. Результат:0objective/4party defeated/2limit/0unsupported,117actions,40started/36completed rounds;4trials с поражением PC. Все действия Reload/Recover входят в прежний action count, отдельных counters нет.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json):1–2Footpads и0–1Net Goblin, четыре состава по2trials, party/loadout/тактика фиксированы.

| Footpads | Net Goblins | Objective | Party defeated | Limit | Actions |
|---|---|---|---|---|---|
| 1 | 0 | 2 | 0 | 0 | 2 |
| 1 | 1 | 0 | 0 | 2 | 32 |
| 2 | 0 | 0 | 0 | 2 | 32 |
| 2 | 1 | 0 | 2 | 0 | 39 |

Unsupported везде0. Малая выборка показывает интерфейс и цену выбранной тактики, а не истинные вероятности или оптимальный состав.184прежнихJSON M9–M54 сохранены побайтно.
