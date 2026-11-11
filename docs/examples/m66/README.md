# M66: первый залп Crossbow/Repeater Crossbow → melee backup

Три PC начинают на Short в одной Zone. Простые числовые Minions подходят на своём ходу; после сближения PC достают запасные мечи. [Правило](../../rules/equipment.md#pc-crossbows-m66), [контракт](../../decisions/ADR-0108-pc-crossbows-opening-volley-and-reload-state.md), [Short opening](../../rules/combat.md#pc-short-opening-m65).

| PC | Primary | Первый выстрел | Состояние после него |
|---|---|---|---|
| pc1 | Crossbow | Damage4, +1 по armoured target | empty / cycle2 |
| pc2 | Repeater Crossbow / when_available | Damage4, +1d Shooting | empty / cycle3 |
| pc3 | Repeater Crossbow / never | Damage4, обычный Shooting | loaded / без нового cycle |

Все2H, initial grip=`both`, без shield, с carried Sword/right backup. Crossbow source:

```json
"weapon": "crossbow",
"ranged": {
  "ballistic_skill": 3,
  "shooting": 4,
  "initiative": 3,
  "dexterity": 4,
  "ammunition_supply_confirmed": true,
  "initially_loaded": true,
  "reload_hand_policy": "two_available_hands"
}
```

У Repeater Crossbow дополнительно обязателен `repeater_bonus_policy`: `when_available` либо `never`; у обычного Crossbow это поле запрещено. Оба запрещают firearm Lore/kit поля. Shared K1 задаёт2successes для Crossbow и3после бонуса Repeater; характеристики Reload передаются явно.

Поведение NPC остаётся M65: approach → Close. После этого оба арбалета не могут стрелять даже по другой Short-цели; на собственном ходу PC выбирает backup независимо от оставшегося заряда. Empty/loaded primary сохраняется после draw, active Sword использует Melee/Strength и не наследует Crossbow armour Trait. Без backup действует точный stop после обязательных последствий и нужного Recover.

Этот пример показывает первый залп и дальнейший melee, а не fresh Shoot→Reload→Shoot. Законный K1 Reload проверен отдельно в собственном focused контексте из реального spent state; новая NPC wait policy для повторной стрельбы не добавлялась. JSON result содержит исходный source и агрегаты; charge/proof состояния проверяются в [native tests](../../../tests/unit/test_m66_pc_crossbows.py).

У числовых NPC здесь Toughness4/bonus1 и явный `armoured:true`. Бонус обычного Crossbow проверяет этот факт и не игнорирует полную Resilience5. Repeater не получает +1Damage. Optional authored `definition.resilience.armoured` сохраняет true/false; при отсутствии поля действует прежний вывод из bonus. Canonical Net/book ограничения не расширены. Strength4 PC относится к запасному Sword, Damage арбалетов фиксирован; Toughness5/armour1 и остальные числа задаёт полный request.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m66/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m66/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): seed42,4trials,6round limit/4Minions;4objective/0party defeated/0limit/0unsupported,40actions,10started/6completed rounds, без потерь PC. [Balance request](pc-melee-balance.request.json) и [CLI result](pc-melee-balance.result.json):3–4Minions,2состава по2trials; оба дали2objective,12/15actions. Это демонстрационные выборки, не истинные вероятности и не доказательство оптимального состава.

Все228прежнихJSON M9–M65 остаются побайтно прежними. Wire version/key ranged, старые1H guns/free bows и NPC каталог59 сохраняются. Short-вариант по-прежнему ограничен authored Melee Minions/ATH, без named NPC/Abilities, shield/NPC shooters/Help, других Zone/выхода, Aim/Charge/terrain или PC kiting.
