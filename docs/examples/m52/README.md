# M52: Weighted Net и carried Spear

Night Goblin начинает с одной сетью в руках и переносимым копьём. Сеть использует Throwing2d/3, cap6, Close–Short и две руки; попадание накладывает Burdened вместо Damage. После броска, успешного или нет, сеть израсходована, а NPC свободным действием достаёт копьё. Подбора сети в этом сценарии нет.

По уже Burdened или Defenceless цели он выбирает копьё и сохраняет неброшенную Net. Если позднее появляется другая допустимая цель текущего priority, сохранённую сеть можно снова достать и бросить. Это выбранная тактика; спорное Net→Wound взаимодействие с Defenceless остаётся вне среза. [Правило](../../rules/npc-profile-catalog.md#night-goblin-net-spear-m52), [контракт](../../decisions/ADR-0097-pc-weighted-net-and-carried-spear.md).

```python
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc
from towr.domain.pc_npc_net_policy_models import PcNpcNetMode, PcNpcNetPolicy

npc = create_pc_book_npc(PcBookNpcProfile.NIGHT_GOBLIN_NET_SPEAR, "net_goblin1")
policy = PcNpcNetPolicy("net_goblin1", 1, PcNpcNetMode.THROW_ONCE_THEN_SPEAR)
# При создании PcMeleeScenario передать npc_net_policies=(policy,).
```

`SPEAR_ONLY` позволяет отказаться от броска, сохранив тот же набор снаряжения. Horde Help при выбранной паре имеет приоритет и не тратит Net; Melee Help не переносится на Throwing. Dirty Coward продолжает действовать.

У Net/Spear loadout нет щита: T3/Res3, но printed **armoured** сохранён явно. Это важно для бонуса Axe/Halberd против брони. Athletics3d/2 Protection; Spear — Melee2d/3, Damage3,1H,maxShort,cap4. PC без щита защищается от сети Athletics, даже держа Sword/Staff.

В текущем PC JSON1 только этот enemy требует `net_policy` и два дополнительных поля definition:

```json
{
  "resilience": {"toughness": 3, "bonus": 0, "armoured": true},
  "net_attack": {
    "id": "weighted_net",
    "source_rule_id": "BOOK-GM-GUIDE:1.1:p157:night_goblin_net_spear:weighted_net",
    "skill": "throwing",
    "test_profile": {"dice": 2, "threshold": 3, "pool_cap": 6},
    "range_min": "close",
    "range_max": "short",
    "hands": "2h",
    "impact": {
      "kind": "condition",
      "condition": "burdened",
      "rule_id": "RULE-EQUIPMENT-005:weighted-net-burdened",
      "classification": "unclassified"
    }
  }
}
```

Это фрагмент definition; остальные поля присутствуют в полных requests ниже. Primary `attack` содержит Spear. Рядом с `definition`, на уровне enemy:

```json
"net_policy": {"initial_count": 1, "mode": "throw_once_then_spear"}
```

Все вложенные поля обязательны. Damage у Net отсутствует; нулевой урон не заменяет Condition impact. Остальные NPC не получают эти поля,172прежнихJSON не мигрируются. Подбор удаляет policy вместе с исключённым actor.

Burdened запрещает Manoeuvre, а не Attack/Protection. Поэтому PC сохраняет прежнюю Attack/standard Recover тактику и не получает выдуманного штрафа. Отдельного Brawn Recover в этом срезе нет. Обычный Recover, рана или expiry другого Condition не снимают сетевую причину.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m52/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m52/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): два PC со Staff, authored Strength1/Melee1, против двух Net Goblins;4rounds, seed42,6trials. Получены2objective/0party defeated/4limit/0unsupported,76actions, без потерь PC.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json):1–2Net Goblins и0–1Goblin/Spear+shield; четыре состава по2trials.

| Net Goblins | Spear Goblins | Objective | Party defeated | Limit | Actions |
|---|---|---|---|---|---|
| 1 | 0 | 2 | 0 | 0 | 7 |
| 1 | 1 | 1 | 0 | 1 | 21 |
| 2 | 0 | 1 | 0 | 1 | 21 |
| 2 | 1 | 1 | 0 | 1 | 27 |

Unsupported и потери PC везде0. Стоимость броска входит в обычные actions; draw не добавляет action. Отдельных Net counters в компактном JSON нет; stock и free transitions проверяются в native journal. Малые выборки демонстрируют интерфейс и выбранную тактику, не истинные вероятности или оптимальный состав.
