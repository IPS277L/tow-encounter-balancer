# M25: Empire State Trooper с Halberd и Defence

Пятый книжный loadout PC-каталога: Empire State Trooper, GM1.1, Allies and Antagonists100. Выбраны Halberd Close3d/3 Damage5,2H и Defence3d/4; Minion с Toughness3/Resilience4 (armoured). [Правило и граница Supporting Action](../../rules/npc-profile-catalog.md#state-trooper-m25).

```python
from towr.domain.pc_npc_catalog import (
    PcBookNpcProfile, create_pc_book_npc, get_pc_book_npc_entry,
)

profile = PcBookNpcProfile.EMPIRE_STATE_TROOPER_HALBERD
trooper = create_pc_book_npc(profile, "trooper1")
entry = get_pc_book_npc_entry(profile)
```

Это фиксированный выбор Protection, без переключения на Athletics. Напечатанная Athletics3d/3 сохранена в `entry.unselected_protection`; у прежних четырёх записей этот tuple пуст. Spear/Crossbow/Handgun явно unselected. NPC не получает бонус PC Halberd против брони: применяется напечатанный Damage5. Свой бонус PC Axe против брони Trooper сохраняет.

Supporting Action позволяет одному пригодному союзному State Trooper или Free Company Militia в соседней Zone, вне Close Range врага, немедленно Charge или сделать ranged attack, когда враг входит в Close Range State Trooper. В нынешней aware-сцене все PC уже в arena/Close и не перемещаются, внешних участников нет. Способность сохранена как inactive с полным условием; это не разрешение игнорировать её при будущем расширении сцены. Уход союзного Official не является входом врага.

Текущий JSON1, схемы, поля и команды не менялись. Requests содержат полные numeric definitions с `hands="2h"` и `protection.skill="defence"`; изменение этих значений под той же книжной identity отвергается. Авторские numeric profiles сохраняют прежний явный выбор Skill. Все32прежние пары M9–M24 остались неизменны.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m25/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m25/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [actual CLI result](pc-melee-simulation.result.json): два PC со Staff против одного Trooper и одного Footpad, seed42,6trials,budget5rounds, optional Fate declined/backup null/exit policy null. Получены6objective, без party defeat/limit/unsupported/PC deaths;24actions,11started/5completed rounds. Все exit/support/Fate counters нулевые.

[Balance request](pc-melee-balance.request.json) и [actual CLI result](pc-melee-balance.result.json): fixed party и loadouts,1–2Troopers/0–1Footpad, по3trials:

| Troopers | Footpad | Objective | Other outcomes | Actions |
|---|---|---|---|---|
| 1 | 0 | 3 | 0 | 7 |
| 1 | 1 | 3 | 0 | 12 |
| 2 | 0 | 3 | 0 | 16 |
| 2 | 1 | 3 | 0 | 26 |

При top_k2 выбраны1Trooper/0Footpad и1Trooper/1Footpad. Это малая воспроизводимая выборка, не истинная вероятность или оптимальная сложность. Подбор сохраняет полный выбранный профиль/Protection каждого NPC и агрегаты без native journal.
