# M67: первый залп Handgun/Repeater Handgun → melee backup

Три PC начинают на Short в одной Zone против четырёх числовых Melee Minions. NPC подходят на своём ходу; после сближения PC достают carried Sword. [Правило](../../rules/equipment.md#pc-handguns-m67), [контракт](../../decisions/ADR-0109-pc-handguns-opening-volley.md), [Short opening](../../rules/combat.md#pc-short-opening-m65).

| PC | Primary | Первый выстрел | Состояние после него |
|---|---|---|---|
| pc1 | Handgun | Damage5, ignores armour, Short−1d | empty / cycle3 |
| pc2 | Repeater Handgun / when_available | Damage5, ignores armour, +3d Shooting | empty / cycle5 |
| pc3 | Repeater Handgun / never | Damage5, ignores armour, без бонуса | loaded / без нового cycle |

Все2H, initial grip=`both`, без shield, с Sword/right backup. Handgun использует9обязательных полей:

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

Repeater дополнительно требует `repeater_bonus_policy`: `when_available` либо `never`; обычный Handgun запрещает это поле. Blackpowder Lore/kit/supplies подтверждаются явно. Бонус выбирается до броска и Fate с обычным cap; Drained запрещает бонус Repeater и сохраняет отрицательный range modifier Handgun. Оба игнорируют armour bonus, но не Toughness, и не получают Crossbow Damage Trait.

После подхода любого живого NPC оба оружия не могут стрелять; на собственном ходу PC выбирает backup даже при loaded Repeater. Состояние primary сохраняется отдельно, Sword использует Melee/Strength без firearm Traits. Без backup возникает точный `ranged_close_enemy` stop; mandatory последствия и уже необходимый standard Recover сохраняют приоритет. Полный повторный Shoot→Reload→Shoot в fresh encounter не заявляется, Reload3vs5 проверяется отдельно на реальном spent source.

```powershell
$env:PYTHONPATH='src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m67/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m67/pc-melee-balance.request.json
```

Оба сохранённых результата получены этими CLI-командами. Simulation seed42/4trials/6round budget:4objective,34actions,10started/6completed rounds, без потерь PC. Count search3–4Minions:2candidate×2trials, по2objective;8/13actions. Эти небольшие выборки демонстрируют интерфейс, а не точные вероятности или оптимальность стратегии.

[Simulation request](pc-melee-simulation.request.json), [result](pc-melee-simulation.result.json); [balance request](pc-melee-balance.request.json), [result](pc-melee-balance.result.json). PC JSON1 прежний, старые232JSON M9–M66 не мигрируются. Остальные семьи, каталог59NPC и14shared ranged profiles сохраняются. Нет других Zone, Aim, PC movement/kiting или новых NPC policies.
