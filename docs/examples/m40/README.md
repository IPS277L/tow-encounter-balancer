# M40: Demigryph, Centigor и White Wolf / Rending Claws

Три совместимых боевых варианта используют прежний PC JSON1 и текущие Attack/Recover/Fate policies. [Правило](../../rules/npc-profile-catalog.md#creature-chunk-m40) связывает GM1.1 Demigryph175/Centigor149/White Wolf136 с реализацией. Каталог содержит39loadouts.

| Loadout | Attack | Protection | Раны и защита |
|---|---|---|---|
| Demigryph, без всадника | Wicked Claws natural4d/4 Damage5 | Athletics4d/3 | Brute3, T4/Res4 без брони; W1–2Drained |
| Centigor / Jagged Spear+shield | 1H4d/4 Damage4, maximumShort | Athletics4d/3 | Brute2, T4/Res5 armoured, щит уже включён; W1Prone |
| White Wolf / Rending Claws | natural3d/4 Damage6 | Athletics4d/4 | Brute2, T5/Res5 без брони; W1Drained |

Все Fast, но бой остаётся в Close без перемещений. Last Wound defeats. Natural attacks имеют hands=null и не вооружают существо; explicit pool_cap остаётся null. Centigor при подтверждении первой раны падает Prone, затем продолжает обычный Attack. Следующий PC Melee получает+1d higher ground. Старый Staggered сначала снимается раной; новый Prone не наносит дополнительной раны. NPC Recover не добавляется.

Rending Claws допускают Give Ground: запрет принадлежит отдельной Clamping Jaws атаке. Pin and Tear требует successful Charge Clamping Jaws и в этом loadout не срабатывает. У unmounted Demigryph нет rider double attack; ни одно новое существо не получает Bear Enduring Strength. Полные Fearsome/Charge/terrain/rider условия сохранены в metadata; fixed SUFFER_WOUND/noMove сцена их не вызывает.

```python
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc

demigryph = create_pc_book_npc(PcBookNpcProfile.DEMIGRYPH, "demigryph1")
centigor = create_pc_book_npc(PcBookNpcProfile.CENTIGOR_SPEAR, "centigor1")
wolf = create_pc_book_npc(PcBookNpcProfile.WHITE_WOLF_RENDING_CLAWS, "white_wolf_claws1")
```

Примеры используют два PC с Axe, optional Fate declined и пустые Help/extra-Attack policies. Активации и PC target priority: Demigryph(s) → Centigor → White Wolf Claws.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m40/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m40/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): по одному NPC каждого вида, seed42/6trials/budget5rounds. Получены0objective/5party defeated/1limit/0unsupported,108actions,27started/22completed rounds; PC1defeated6/PC2defeated5. Fate/Help/ally Recover/NPC exit/extra-Attack counters0.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json):1–2Demigryphs,0–1Centigor,0–1White Wolf Claws; восемь составов по2trials.

| Demigryphs | Centigors | White Wolf Claws | Objective | Party defeated | Limit | Actions |
|---|---|---|---|---|---|---|
| 1 | 0 | 0 | 2 | 0 | 0 | 18 |
| 1 | 0 | 1 | 0 | 0 | 2 | 33 |
| 1 | 1 | 0 | 0 | 0 | 2 | 34 |
| 1 | 1 | 1 | 0 | 2 | 0 | 33 |
| 2 | 0 | 0 | 0 | 0 | 2 | 34 |
| 2 | 0 | 1 | 0 | 2 | 0 | 33 |
| 2 | 1 | 0 | 0 | 2 | 0 | 30 |
| 2 | 1 | 1 | 0 | 2 | 0 | 32 |

Unsupported везде0; при top_k2 выбраны1/0/0 и1/0/1. Малые выборки иллюстрируют интерфейс, а не истинную вероятность или оптимальную стратегию; Limit остаётся отдельным исходом в общем знаменателе.

Новых полей/метрик/версии/миграции нет. Все36прежнихentries и124JSON documents M9–M39 сохраняются без изменений.
