# M32: Empire Peasant, Town Watch и Free Company Militia

Три совместимых melee loadouts на текущем PC JSON1. [Правило и источники](../../rules/npc-profile-catalog.md#empire-chunk-m32). В M32 каталог вырос до25fixed combat loadouts; контракт, стратегии и метрики этого чанка прежние. Актуальный состав каталога — в [статусе](../../project-status.md).

| Profile ID | Выбранная атака | Protection | Профиль |
|---|---|---|---|
| EMPIRE_PEASANT | Make-Shift Weapons,Close2d/2 Damage2,1H | Athletics3d/2 | Normal Minion,T3/Res3 |
| TOWN_WATCH_POLEARM | Polearm,до Short3d/3 Damage5,2H | Athletics3d/3 | Normal Minion,T3/Res4 armoured |
| FREE_COMPANY_MILITIA_BLADES | Improvised Blades,Close3d/3 Damage3,1H | Athletics3d/3 | Normal Minion,T3/Res3 |

Щитов нет. Short у Polearm — максимальная дальность Melee; бой остаётся Close. Damage5 уже напечатано в профиле: PC weapon traits не начисляются повторно. Protection берётся из карточки, включая Athletics3d/2 Peasant, а не выводится из его атаки.

```python
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc

peasant = create_pc_book_npc(PcBookNpcProfile.EMPIRE_PEASANT, "peasant1")
watch = create_pc_book_npc(PcBookNpcProfile.TOWN_WATCH_POLEARM, "watch1")
militia = create_pc_book_npc(PcBookNpcProfile.FREE_COMPANY_MILITIA_BLADES, "militia1")
```

Полные Abilities сохранены в metadata:

- Peasant Torches and Pitchforks: Help союзной Melee attack без Test даёт+1d сверх обычного cap.
- Town Watch Whistleblower: если NPC решает подать сигнал как часть Recover, подкрепление приходит на следующий **turn**, Athletics Tests для Retreat от них Grim.
- Militia Strength in Numbers: Help любой attack союзника within Medium Range без Test даёт+1d сверх cap.
- Militia Detachment: enemy moves into Close Range State Trooper; nominated FCM либо Trooper в adjacent Zone, сам не в Close Range enemy, немедленно Charge либо ranged attack.

В этих примерах npc_help_policies=[], поэтому NPC выбирают Attack, а не Help/Recover; [M33](../m33/README.md) добавляет явный opt-in для Help. Начальная уже-Close расстановка не является Move-входом. Поэтому triggers в этом срезе отсутствуют; Staggered Watch продолжает обычный Attack, не вызывает подкрепление автоматически. Facts fresh/no_external_effects исключают также неиспользованный предбоевой Help bonus, уже отправленный сигнал и ожидающее подкрепление. Hunting Bow Peasant и Assorted Projectiles Militia unselected; у Watch другой printed attack нет.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m32/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m32/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): два PC со Staff против одного NPC каждого нового loadout; priority Peasant → Watch → Militia, seed42,6trials,5rounds. Получены6objective/0party defeat/0limit/0unsupported,42actions,15started/9completed rounds, без потерь PC и optional/support/exit расходов.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json):1–2Peasants,0–1Watch,0–1Militia, по2trials на8составов с тем же budget/порядком:

| Peasants | Watch | Militia | Objective | Actions |
|---|---|---|---|---|
| 1 | 0 | 0 | 2 | 2 |
| 1 | 0 | 1 | 2 | 4 |
| 1 | 1 | 0 | 2 | 10 |
| 1 | 1 | 1 | 2 | 14 |
| 2 | 0 | 0 | 2 | 4 |
| 2 | 0 | 1 | 2 | 11 |
| 2 | 1 | 0 | 2 | 11 |
| 2 | 1 | 1 | 2 | 20 |

Другие outcomes0. При top_k2 выбраны1/0/0 и1/0/1. Это малая воспроизводимая выборка, не доказательство гарантированной победы или оптимальности. Подбор сохраняет исходные definitions/range/gear/policies и хранит агрегаты без native journals. При приёмке M32 все92прежних JSON documents были побайтово неизменны; последующая M33 миграция добавляет []/нулевые NPC Help fields, сохраняя прежние наблюдения.
