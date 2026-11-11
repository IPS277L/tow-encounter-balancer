# M64: PC Repeaters и общий ranged source

Оба Repeater работают в текущем Close-бою через один PC `ranged` source. [Правило](../../rules/equipment.md#pc-repeaters-m64), [контракт](../../decisions/ADR-0106-pc-repeaters-and-generic-ranged-profile.md).

| Оружие | Damage | Бонус | Reload |
|---|---|---|---|
| Repeater Handbow | 4, обычная броня | +1d Shooting | 3 successes после бонуса |
| Repeater Pistol | 5, ignores armour | +2d Shooting | 3 successes после бонуса |

`repeater_bonus_policy: "when_available"` выбирает бонус до броска, если PC не Drained; `"never"` оставляет обычный выстрел без нового Reload cycle. Это фиксированная тактика, включая расход при насыщенном cap. Начатая зарядка завершается и после получения Drained. Reload занимает отдельное действие, completion не даёт бесплатного выстрела.

PC `pistol` заменён на `ranged` без compatibility aliases, версия PC JSON1 прежняя. Обычный Pistol использует тот же объект без `repeater_bonus_policy`, но с обязательными true Blackpowder Lore/kit. Handbow эти два поля запрещает, Repeater Pistol требует. Пример Handbow:

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

Четыре PC показывают оба оружия и режима: PC1 Handbow/when_available, PC2 Repeater Pistol/when_available, PC3 Handbow/never, PC4 Repeater Pistol/never. У всех shield в левой руке и carried Sword backup. Они встречают Imperial Ogre/Greathammer и пешего Empire Knight/Lance+Shield. Щит освобождает руку только для действительно необходимого Reload и возвращается отдельным Recover после зарядки. Loaded shot одной рукой имеет приоритет; backup применяется только при пустом оружии и недоступном Reload из-за одной пригодной руки.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m64/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m64/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): seed42,4trials,6rounds;4objective/0party defeated/0limit/0unsupported,86actions,18started/14completed rounds, без потерь PC. [Balance request](pc-melee-balance.request.json) и [CLI result](pc-melee-balance.result.json): Ogre1/Knight0–1,2состава по2trials; оба состава дали2objective,17/41actions. Это демонстрационные выборки, не оценка истинной вероятности или оптимального состава.

Native/process representative использует этот source и два trial seed: проверяет actual bonus/ordinary shots, завершённый Reload, независимые instances и равенство sequential/spawn records/summary. NPC firearm source по-прежнему называется `enemies[].pistol`. В220прежнихJSON заменён только PC key в36документах,184 сохранены побайтно; прежние результаты не пересчитывались. Aim, другие ranges и новые Shooting Help роли PC не добавлены.
