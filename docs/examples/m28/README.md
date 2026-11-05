# M28: Gor dual axes, Chaos Warhound и Orc Boy Choppas

Три fixed Close loadouts с исполняемыми NPC-модификаторами. [Правило, источники и shield adjustment](../../rules/npc-profile-catalog.md#beast-orc-chunk-m28).

| Profile ID | Атака | Protection | Resilience без щита |
|---|---|---|---|
| GOR_DUAL_AXES | Crude Axes4d/3, base Damage3 + отдельный dual modifier1,1H на топор | Athletics4d/3 | T4/Res4 |
| CHAOS_WARHOUND | Pinning Claws3d/3 Damage3,natural; запрет Give Ground | Athletics4d/3 | T3/Res3 |
| ORC_BOY_CHOPPAS | Couple of Choppas3d/4 Damage4,2H | Defence3d/4 | T4/Res5 armoured |

```python
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc

gor = create_pc_book_npc(PcBookNpcProfile.GOR_DUAL_AXES, "gor1")
hound = create_pc_book_npc(PcBookNpcProfile.CHAOS_WARHOUND, "warhound1")
orc = create_pc_book_npc(PcBookNpcProfile.ORC_BOY_CHOPPAS, "orc1")
```

GM93: без щита напечатанная Resilience уменьшается на1, поэтому Gor5→4 и Orc6→5. Числа Protection не меняются. Gor несёт две Crude Axes, заняв обе руки; Orc сохраняет свою напечатанную combined2H нотацию Choppas. Оба fixed loadouts без shield, без mid-battle смены оружия/хвата. По PG97 Gor при Resilience=Toughness не armoured; у Orc остаётся light armour1. Его Athletics3d/3, Jagged Spear и Warbow явно unselected.

Primal Rage Gor даёт +1d Melee только при **его собственном** Staggered. Он складывается с обычными outnumbering/higher-ground modifiers до cap/Drained filter; Athletics Protection от него не усиливается. Dual axes дают ровно один отдельный DamageModifier+1, не PC Axe armour trait; Drained не отменяет bonus Damage. Warhound сохраняет printed3d/3 при WS4 и фактически запрещает цели Give Ground, как Giant Wolf.

Woodland terrain ignore остаётся inactive без движения/terrain. Orc Charge+1Damage и Help free success без Test сохранены в metadata, но выбранная NPC-стратегия не выполняет Charge/Help. Его printed Damage4 не увеличивается скрытым PC dual/weapon bonus. Current JSON1/схемы/метрики не менялись; source содержит полные numeric definitions и фиксирующие loadout canonical IDs. Прежние38request/result pairs сохранены.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m28/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m28/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [actual CLI result](pc-melee-simulation.result.json): два PC со Staff против Gor/Warhound/Orc, seed44,6trials,budget5rounds, optional Fate declined/backup/exit policy null. Seed44 также упражняет реальную атаку Staggered Gor в process-тесте. Получены6objective/0party defeat/0limit/0unsupported, но в1trial погиб pc1; победа группы не означает отсутствие потерь.73actions,23started/17completed rounds, optional/support/exit counters нулевые.

[Balance request](pc-melee-balance.request.json) и [actual CLI result](pc-melee-balance.result.json):1–2Gors,0–1Warhound,0–1Orc, по3trials на8составов с fixed party/profiles/policies:

| Gors | Warhound | Orc | Objective | Party defeated | Round limit | Actions |
|---|---|---|---|---|---|---|
| 1 | 0 | 0 | 3 | 0 | 0 | 7 |
| 1 | 0 | 1 | 3 | 0 | 0 | 32 |
| 1 | 1 | 0 | 3 | 0 | 0 | 35 |
| 1 | 1 | 1 | 3 | 0 | 0 | 42 |
| 2 | 0 | 0 | 3 | 0 | 0 | 29 |
| 2 | 0 | 1 | 2 | 0 | 1 | 35 |
| 2 | 1 | 0 | 3 | 0 | 0 | 37 |
| 2 | 1 | 1 | 1 | 2 | 0 | 57 |

Unsupported нулевой во всех составах. При top_k2 выбраны2Gors+1Orc и2Gors+1Warhound+1Orc. Limit и потери сохраняются в агрегатах/знаменателе. Это малая воспроизводимая выборка, не истинные вероятности или оптимальная сложность. Подбор хранит полные projected sources и агрегаты без native journals.
