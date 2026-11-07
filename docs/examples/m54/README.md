# M54: PC с Pistol и перезарядкой

Pistol стреляет в Close через Shooting на Ballistic Skill: Damage5, ignores armour. После HIT/MISS он разряжен. Следующие действия Reload используют Dexterity на Initiative и накапливают3successes; провал не стирает progress. Завершение Reload занимает своё действие, следующий выстрел происходит позже. Обычный необходимый self Recover сохраняет приоритет и не заряжает оружие.

В первом срезе один initially loaded Pistol без shield/backup у стрелка. Blackpowder Lore, полный Blackpowder Kit и достаточное снабжение подтверждены явно. NPC уже имеют lawful выбранную Athletics либо Defence со щитом; отсутствующая защита не достраивается автоматически. Смешанная party с прежними melee/shield PCs допустима. [Правило и границы](../../rules/equipment.md#pc-pistol-reload-m54), [принятый контракт](../../decisions/ADR-0099-pc-pistol-and-exacting-reload.md).

В текущем PC JSON1 дополнительные поля находятся внутри `party[].pc`; остальные прежние характеристики тоже обязательны:

```json
"weapon": "pistol",
"pistol": {
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

Это авторский пример PC, числа не являются общими значениями по умолчанию. Объект полный и закрытый; missing/null/false preconditions отвергаются. Для других weapons объект запрещён;180прежнихJSON M9–M53 сохранены побайтно.

Принятая GM/scenario policy требует две пригодные руки для Reload: одна держит Pistol, другая свободна. Книга не определяет это число рук. Травмированная12рука допустима с Critical. Loaded shot одной оставшейся рукой разрешён; UNSUPPORTED_PATH возникает лишь перед действительно требуемым недоступным Reload на своём незанятом ходу. Drop/Recover не сбрасывают заряд/цикл/progress; terminal objective не требует перезарядки. Aim/Rapid Reload/Pistol+Shield и новый ranged Help вне среза.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m54/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m54/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): один PC с приведёнными firearm Skills и armour_bonus0 против2Footpads и1Net Goblin; seed42,6trials,8rounds. Получены0objective/4party defeated/2limit/0unsupported,112actions,43started/39completed rounds;4trials с поражением PC. Native journal хранит отдельные shot/Reload proofs; compact result считает их обычными действиями без новых counters.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json):1–2Footpads и0–1Net Goblin, четыре состава по2trials. Party/weapon/тактика фиксированы.

| Footpads | Net Goblins | Objective | Party defeated | Limit | Actions |
|---|---|---|---|---|---|
| 1 | 0 | 2 | 0 | 0 | 2 |
| 1 | 1 | 1 | 0 | 1 | 21 |
| 2 | 0 | 1 | 0 | 1 | 21 |
| 2 | 1 | 0 | 2 | 0 | 36 |

Unsupported во всех составах0. Выборки показывают интерфейс и выбранную тактику; они не определяют истинные вероятности или оптимальный состав.
