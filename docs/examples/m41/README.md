# M41: Gor и Empire Knight со щитами

Два самостоятельных боевых варианта дополняют прежние dual/unshielded loadouts. [Правило](../../rules/npc-profile-catalog.md#shield-chunk-m41), GM1.1 Gor143/Empire Knight101/Profiles93. Каталог содержит41вариант.

| Loadout | Attack | Protection | Resilience |
|---|---|---|---|
| Gor / single Crude Axe+shield | Close4d/3 Damage3,1H | Athletics4d/3 | T4/Res5 armoured, Minion |
| Empire Knight / Lance+shield, пеший | Close4d/4 Damage4,1H | Defence4d/4 | T3/Res6 armoured, Brute2 |

Щит уже включён в printed Resilience. Gor получает ordinary+1d Melee при собственном Staggered, но не Damage+1 двух топоров. Knight при первой ране получает Drained и продолжает обычный Attack; W2 defeats. Mounted/Charge bonuses не применяются. Все полные условия Abilities сохраняются в metadata. Новых source полей/метрик/версии нет.

```python
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc

gor = create_pc_book_npc(PcBookNpcProfile.GOR_AXE_SHIELD, "shield_gor1")
knight = create_pc_book_npc(PcBookNpcProfile.EMPIRE_KNIGHT_LANCE_SHIELD, "shield_knight1")
```

Примеры используют два PC с Axe, optional Fate declined и пустые Help/extra-Attack policies. Активации и PC target priority: Gor(s) → Knight.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m41/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m41/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): по одному новому NPC, seed42/6trials/budget5rounds. Получены6objective/0party defeated/0limit/0unsupported,62actions,24started/18completed rounds; PC1defeated1/PC2defeated0. Fate/Help/ally Recover/NPC exit/extra-Attack counters0.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json):1–2Gors,0–1Knight, четыре состава по2trials.

| Shield Gors | Shield Knights | Objective | Party defeated | Limit | Actions |
|---|---|---|---|---|---|
| 1 | 0 | 2 | 0 | 0 | 3 |
| 1 | 1 | 2 | 0 | 0 | 21 |
| 2 | 0 | 2 | 0 | 0 | 11 |
| 2 | 1 | 0 | 0 | 2 | 30 |

Unsupported везде0; при top_k2 выбраны1/0 и1/1. Малые выборки иллюстрируют интерфейс, а не истинную вероятность или оптимальную стратегию. Все39прежнихentries и128JSON documents M9–M40 сохранены без изменений.
