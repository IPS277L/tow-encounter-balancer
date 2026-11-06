# M45: Sharpshooter/Axe и три варианта без щита

Совместимый чанк из четырёх fixed melee loadouts. [Правило](../../rules/npc-profile-catalog.md#melee-loadout-chunk-m45); каталог содержит48боевых вариантов.

| Profile | Attack | Protection | Resilience |
|---|---|---|---|
| Hochland Sharpshooter/Axe | Close3d3 Damage3,1H | Athletics4d4 | T4/Res5 armoured, Brute2 |
| Gor/single Crude Axe | Close4d3 Damage3,1H | Athletics4d3 | T4/Res4 без брони, Minion1 |
| Orc Boy/Jagged Spear | maxShort3d4 Damage3,1H | Defence3d4 | T4/Res5 armoured, Minion1 |
| Big ’Un/Jagged Spear | maxShort3d4 Damage4,1H | Defence3d4 | T4/Res5 armoured, Brute2 |

Все варианты без shield. У Gor/Orcs printed shield-inclusive Resilience уменьшена на1 ровно один раз. Single Gor сохраняет Primal Rage от собственного Staggered, без dual Damage+1. Orcs используют прежние явные Power Help pairs с free success, в том числе для Drained получателя. Big ’Un W1Drained/W2defeat исполняются через обычный profile ACK. Sharpshooter сохраняет Cancel Aim на W1; в Axe-only/Attack сцене Aim отсутствует. Rifle unselected, Reload/woodland/Charge условия не возникают. PC weapon Traits не добавляются.

```python
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc

sharpshooter = create_pc_book_npc(PcBookNpcProfile.HOCHLAND_SHARPSHOOTER_AXE, "sharpshooter1")
gor = create_pc_book_npc(PcBookNpcProfile.GOR_AXE, "single_gor1")
orc = create_pc_book_npc(PcBookNpcProfile.ORC_BOY_SPEAR, "unshielded_orc1")
big_un = create_pc_book_npc(PcBookNpcProfile.BIG_UN_SPEAR, "unshielded_big_un1")
```

Current PC JSON1/метрики прежние, новых public fields/policies нет. Старые144JSON documents M9–M44 не мигрируются. Примеры задают два PC с Axe, приоритет Big ’Un → Gor → Orc Boy → Sharpshooter и явный Orc Boy Help для более позднего Big ’Un. Count search удаляет Help pair, когда исключён любой endpoint, без переназначения. Optional Fate/PC Help declined, NPC extra Attack/grudge lists пустые.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m45/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m45/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): по одному NPC каждого нового loadout, seed42/6trials/budget5rounds. Получены2objective/2party defeated/2limit/0unsupported,124actions,28started/24completed rounds. Хотя бы один PC погиб в3trials; pc1 — в3, pc2 — в2. Выполнено11NPC Help actions; Fate/PC Help/ally Recover/NPC exit/extra-Attack counters0.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json):1–2Sharpshooters и0–1NPC каждого остальных loadout,16составов по2trials,32trials всего. Budget5rounds на trial. Ниже порядок столбцов соответствует generation groups.

| Sharpshooters | Single Gors | Orc Spears | Big ’Un Spears | Objective | Party defeated | Limit | Actions |
|---|---|---|---|---|---|---|---|
| 1 | 0 | 0 | 0 | 2 | 0 | 0 | 12 |
| 1 | 0 | 0 | 1 | 2 | 0 | 0 | 29 |
| 1 | 0 | 1 | 0 | 1 | 0 | 1 | 23 |
| 1 | 0 | 1 | 1 | 1 | 1 | 0 | 35 |
| 1 | 1 | 0 | 0 | 2 | 0 | 0 | 18 |
| 1 | 1 | 0 | 1 | 1 | 0 | 1 | 33 |
| 1 | 1 | 1 | 0 | 2 | 0 | 0 | 27 |
| 1 | 1 | 1 | 1 | 0 | 1 | 1 | 46 |
| 2 | 0 | 0 | 0 | 2 | 0 | 0 | 23 |
| 2 | 0 | 0 | 1 | 0 | 0 | 2 | 40 |
| 2 | 0 | 1 | 0 | 1 | 0 | 1 | 34 |
| 2 | 0 | 1 | 1 | 0 | 1 | 1 | 41 |
| 2 | 1 | 0 | 0 | 0 | 0 | 2 | 32 |
| 2 | 1 | 0 | 1 | 0 | 1 | 1 | 40 |
| 2 | 1 | 1 | 0 | 1 | 0 | 1 | 35 |
| 2 | 1 | 1 | 1 | 0 | 2 | 0 | 40 |

Unsupported везде0. При top_k2 выбраны counts1/0/1/0 и1/0/1/1. Малые выборки иллюстрируют интерфейс, а не истинную вероятность или оптимальную тактику.
