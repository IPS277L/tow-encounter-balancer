# M30: три Brutes с Drained после первой раны

Совместимый чанк на существующем PC melee исполнении. [Правило и источники](../../rules/npc-profile-catalog.md#brute-chunk-m30). Всего в каталоге 19 fixed combat loadouts.

| Profile ID | Выбранная атака | Protection | Resilience |
|---|---|---|---|
| EMPIRE_KNIGHT_LANCE | пеший Lance, Close4d/4 Damage4,1H | Defence4d/4 | Toughness3 + armour2 =5, без щита |
| KNIGHT_WHITE_WOLF_HAMMER | пеший Wolf Hammer, Close4d/4 Damage5,2H | Defence4d/3 | Toughness3 + armour2 =5 |
| BIG_UN_CHOPPAS | Couple of Choppas, Close3d/4 Damage5,2H | Defence3d/4 | Toughness4 + armour1 =5, без щита |

Все — Normal Speed, Brute2: первая фактическая рана накладывает Drained самому NPC, вторая означает defeat. Это не on-hit эффект против PC; `attack.secondary_effects` остаётся `[]`. Drained подавляет положительные bonus dice, но не базовые кубы и не Damage. Раненый NPC продолжает обычный Attack в свой ход.

```python
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc

knight = create_pc_book_npc(PcBookNpcProfile.EMPIRE_KNIGHT_LANCE, "empire_knight1")
wolf_knight = create_pc_book_npc(PcBookNpcProfile.KNIGHT_WHITE_WOLF_HAMMER, "wolf_knight1")
big_un = create_pc_book_npc(PcBookNpcProfile.BIG_UN_CHOPPAS, "big_un1")
```

Выбрана неподвижная Close-сцена без всадников, Charge и NPC Help. Полные условия Noble Steed, For the Order, Furious Charge и Power of the Waaagh! сохранены в metadata. Щиты не выбраны; их +1 уже вычтен из напечатанной Resilience Empire Knight и Big ’Un. Mounted +1 не добавлялся. Альтернативная Athletics Protection сохранена в metadata, но здесь используется Defence. Big ’Un получает только +1 Damage за повышенную Strength относительно Orc Boy: итог5, без повторного бонуса за два Choppas.

PG1.4 Equipment93 задаёт Lance Close/1H и бонус за mounted Charge, но не запрещает обычную пешую атаку. Dual wield с Lance не разрешён и в этом loadout не используется. Knight of the White Wolf — рыцарь, отдельный от существа White Wolf из M29.

Текущий JSON1, команды, метрики и стратегии Fate/Recover сохранены; старые запросы и результаты не мигрировались. Будущий NPC Recover при сохраняющейся profile Wound остаётся открытой границей.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m30/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m30/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): два PC со Staff против одного NPC каждого нового loadout; seed42,6trials,5rounds. Получены0objective/4party defeated/2round limit/0unsupported,109actions,27started/23completed rounds. В6trials погибpc1, в4 — pc2. Optional Fate/support/exit counters равны0. Фиксированные priorities идут Empire Knight → Knight of the White Wolf → Big ’Un.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json): 1–2 Empire Knights,0–1 Wolf Knights,0–1 Big ’Uns, по2trials на8составов, тот же budget и порядок.

| Empire Knights | Wolf Knights | Big ’Uns | Objective | Party defeated | Round limit |
|---|---|---|---|---|---|
| 1 | 0 | 0 | 2 | 0 | 0 |
| 1 | 0 | 1 | 1 | 0 | 1 |
| 1 | 1 | 0 | 0 | 0 | 2 |
| 1 | 1 | 1 | 0 | 2 | 0 |
| 2 | 0 | 0 | 0 | 0 | 2 |
| 2 | 0 | 1 | 0 | 2 | 0 |
| 2 | 1 | 0 | 0 | 1 | 1 |
| 2 | 1 | 1 | 0 | 2 | 0 |

Unsupported во всех составах0. При top_k2 выбраны составы1/0/1 и1/0/0. Это малая воспроизводимая выборка для заданной группы/стратегии, а не оценка истинной вероятности или оптимального состава. Round limit и потери остаются в агрегатах и знаменателе trials.
