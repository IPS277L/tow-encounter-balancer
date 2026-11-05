# M27: естественные атаки Horse, Giant Wolf и Giant Boar

Три самостоятельных unmounted существа, уже находящиеся в Close Range. [Правило и источники](../../rules/npc-profile-catalog.md#natural-creatures-m27), [ADR-0080](../../decisions/ADR-0080-natural-melee-attacks-and-creature-chunk.md).

| Profile ID | Melee-атака | Protection | Resilience |
|---|---|---|---|
| HORSE | Hooves3d/3 Damage3 | Athletics4d/4 | 3 |
| GIANT_WOLF | Clamping Jaws3d/3 Damage3, цель не может Give Ground | Athletics4d/4 | 3 |
| GIANT_BOAR | Goring Tusks3d/4 Damage3 | Athletics3d/3 | 5 armoured при Toughness3 |

```python
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc

horse = create_pc_book_npc(PcBookNpcProfile.HORSE, "horse1")
wolf = create_pc_book_npc(PcBookNpcProfile.GIANT_WOLF, "wolf1")
boar = create_pc_book_npc(PcBookNpcProfile.GIANT_BOAR, "boar1")
assert wolf.definition.attacks[0].hands is None
assert wolf.state.wields_weapon is False
```

В текущем PC JSON1 **обязательное** `attack.hands` может быть `"1h"`, `"2h"` либо `null`. Явный `null` означает natural Melee, не пропущенный/неизвестный хват. Source получает unarmed fresh state/Athletics/noShield; выдавать такой профиль за вооружённого или выбирать ему Defence нельзя. Вооружённый PC по-прежнему может применять Defence против естественной Melee-атаки. Старые1h/2h inputs сохраняют прежний смысл; версия/метрики не менялись.

Giant Wolf действительно запрещает цели Give Ground через actual kernel, даже при `facts.can_leave_zone=true`; атакованный Wolf не получает чужой запрет. Natural armour Boar считается armoured по PG97, поэтому PC Axe/Halberd/Greataxe получают обычный бонус против неё. Boar здесь не получает Charge-бонус.

Все три — Fast Minions, но movement/Charge/riders в этом срезе не исполняются. Noble Steed, Goblin Wolf Rider и Orc Boar Boyz сохранены inactive с полными условиями; собственный Goring Tusks Charge trait сохранён отдельно. Horse — базовый: optional Bretonnian Warhorse/Elven Steed/Skeletal Steed явно unselected в catalog metadata. Никаких фиктивных1H-оружий, PC Sword Traits, drop/pickup зубов или скрытых riders.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m27/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m27/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [actual CLI result](pc-melee-simulation.result.json): два PC со Staff против Horse/Wolf/Boar, seed42,6trials,budget5rounds; optional Fate declined, backup/exit policy null. Получены6objective, без party defeat/limit/unsupported/PC deaths;44actions,16started/10completed rounds. Все optional/support/exit counters нулевые.

[Balance request](pc-melee-balance.request.json) и [actual CLI result](pc-melee-balance.result.json):1–2Horses,0–1Wolf,0–1Boar, по3trials на8составов, fixed party/profiles/policies:

| Horses | Wolf | Boar | Objective | Other outcomes | Actions |
|---|---|---|---|---|---|
| 1 | 0 | 0 | 3 | 0 | 7 |
| 1 | 0 | 1 | 3 | 0 | 15 |
| 1 | 1 | 0 | 3 | 0 | 13 |
| 1 | 1 | 1 | 3 | 0 | 19 |
| 2 | 0 | 0 | 3 | 0 | 13 |
| 2 | 0 | 1 | 3 | 0 | 19 |
| 2 | 1 | 0 | 3 | 0 | 19 |
| 2 | 1 | 1 | 3 | 0 | 33 |

При top_k2 выбраны1Horse без других существ и1Horse+1Boar. Это малая воспроизводимая выборка, не истинная вероятность или оптимальная сложность. Подбор сохраняет полный natural source, включая null hands/actual weapon flags, и агрегаты без native journals.

Прежние36PC request/result pairs M9–M26 не мигрируются. Другие bounded Melee/Mixed/Magic/Ranged families сохраняют свои текущие weapon-only форматы: natural source там отклоняется явно, включая cached None до сериализации. Эффекты mounts/Charge/terrain нельзя считать поддержанными на основании этого примера.
