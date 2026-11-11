# M58: Skulker, Brewguard, Miner и Bestigor против Pistol

Четыре существующих loadouts подключены к прежней Close Shooting Melee/Athletics policy, всего12sources. От Melee сохраняется обычная Defence. [Основное правило](../../rules/combat.md#pc-close-shooting-protection-m58), [контракт и расширения](../../decisions/ADR-0101-pc-close-shooting-npc-protection-choice.md).

| NPC | Melee opposition | Athletics |
|---|---|---|
| Nasty Skulker/Long knives | 4d/4, cap8 | 3d/3, cap6 |
| Brewguard/Warhammer | 4d/3, cap8 | 2d/3, cap4 |
| Miner/Pickaxe | 4d/3, cap8 | 1d/3, cap4 |
| Bestigor/Massive Axe | 4d/4, cap8 | 3d/3, cap8 |

Miner/Bestigor printed Athletics уже уменьшена heavy armour; maximum определяется Ag2/Ag4. Повторного armour penalty нет. Defensive Bestigor4d/4 берётся из WS4/Melee4, а не из printed Axe Attack3d/4.

В нынешнем PC JSON1 применяется тот же optional список:

```json
"npc_close_shooting_protection_policies": [
  {"actor_id": "skulker1", "skill": "melee"},
  {"actor_id": "brewguard1", "skill": "melee"},
  {"actor_id": "miner1", "skill": "melee"},
  {"actor_id": "bestigor1", "skill": "athletics"}
]
```

Пример задаёт существующий grudge Miner→PC1 и включает Bestigor в voluntary Blood Rage list. Grudge даёт+1d к выбранному защитному Melee против focus; Athletics бонус не получает, Drained его подавляет. Distracted даёт−1d против другого PC. Relationship и текущий Distracted сохраняют отдельные источники; Brewguard W1 focus/confirmed-death expiry работают и с новыми Skills.

Blood Rage Bestigor даёт+1d только Melee attacks, voluntary Staggered — только при своей Attack. Ни Rage bonus, ни W1 nextAttack Glorious не применяются/не расходуются в защитной opposition. Skulker Backstabba действует только на его собственную unopposed Attack. Нет defensive counterattack, PC weapon Traits, автоматического Cooler Heads или нового выбора тактики.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m58/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m58/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): mixed party Pistol+Shield/Sword+Shield с authored armour_bonus1 у обоих против всех4NPC; seed42,6trials,8rounds. Получены0objective/4party defeated/1limit/1unsupported,140actions,35started/30completed rounds;5trials с поражением хотя бы одного PC.

Native разбор trial2 подтвердил прежний M54stop: третья рана PC1/table18/clutch stomach делает фактически нужный Reload недоступным из-за второй руки. Reason pistol_reload_hands_unavailable не относится к новой NPC Protection; исполненные costs/losses сохраняются по prefix.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json): Skulker и Miner фиксированы по одному, Brewguard и Bestigor — по0–1; четыре однородные count groups,4состава по2trials. Исключение NPC удаляет его protection/grudge/Rage settings по прежним правилам без переназначения.

| Brewguard | Bestigor | Objective | Party defeated | Limit | Unsupported | Actions |
|---|---|---|---|---|---|---|
| 0 | 0 | 2 | 0 | 0 | 0 | 7 |
| 0 | 1 | 1 | 1 | 0 | 0 | 36 |
| 1 | 0 | 2 | 0 | 0 | 0 | 38 |
| 1 | 1 | 0 | 2 | 0 | 0 | 44 |

Малая выборка показывает интерфейс и выбранную тактику, а не истинные вероятности или оптимальный состав. Unsupported остаётся в знаменателе. Новых полей/version/counters нет;196прежнихJSON сохранены побайтно, каталог57selected definitions не переписан.
