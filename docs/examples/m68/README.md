# M68: Sling со щитом и melee backup

Три PC начинают на Short в одной Zone против четырёх числовых Melee Minions. Sling использует Strength для Damage, BS/Shooting для Test, обычную броню и бесплатную перезарядку; на Short получает−1d. [Правило](../../rules/equipment.md#pc-sling-m68), [контракт](../../decisions/ADR-0110-pc-sling-free-reload-and-close-backup.md).

| PC | Strength | Sling / shield | Backup |
|---|---|---|---|
| pc1 | 4 | right / left | Sword/right |
| pc2 | 3 | left / right | Sword/right: сначала оставить щит |
| pc3 | 2 | right / без щита | Sword/right |

У всех BS3/Shooting4. Источник ranged содержит ровно3поля:

```json
"weapon": "sling",
"ranged": {
  "ballistic_skill": 3,
  "shooting": 4,
  "ammunition_supply_confirmed": true
}
```

I/Dexterity/Lore/kit/initially_loaded/reload_hand_policy/repeater_bonus_policy не передаются. Sling1H, initial grip left/right; shield optional на другой руке. Для carried backup требуется Strength≥2, без него допустим Strength1.

NPC подходят на своём ходу. При любом Close enemy Sling стрелять не может, даже по другой Short-цели; на своём ходу PC достаёт declared Sword. Если выбранная пригодная рука backup занята щитом, weapon-first release записывается до draw. Затем dropped shield возвращается отдельным standard Recover только в свободную здоровую руку. Actual wound/drop/clutch/mandatory/CI/Defenceless priorities прежние. У Sling нет Exacting Reload action/cycle или поля loaded; free state и instance сохраняются отдельно от active melee. После draw Sword использует Melee, range penalty Sling не переносится.

Без backup — точный ranged_close_enemy stop на собственной границе действия без выдуманной Wound; уже необходимый standard Recover имеет приоритет. Одна пригодная рука позволяет применять Sling вне Close. Старые1H Pistol/Repeaters сохраняют собственное разрешение Close/Reload, оно не определяется числом рук.

```powershell
$env:PYTHONPATH='src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m68/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m68/pc-melee-balance.request.json
```

Сохранённые результаты получены actual CLI: simulation seed42/4trials/6round budget→4objective/52actions/11started/7completed rounds, без потерь PC. Count search3–4Minions→2candidate×2trials, по2objective/21и24actions. Небольшие выборки показывают интерфейс, а не точные вероятности или оптимальность стратегии.

[Simulation request](pc-melee-simulation.request.json), [result](pc-melee-simulation.result.json); [balance request](pc-melee-balance.request.json), [result](pc-melee-balance.result.json). Current PC JSON1, прежние236JSON M9–M67/59NPC/14shared profiles сохраняются. Short opening restricted: одна Zone, ranged party, simple authored Melee Minions/Athletics; нет Medium opening/других Zone/movement/kiting/Aim/новых NPC policies.
