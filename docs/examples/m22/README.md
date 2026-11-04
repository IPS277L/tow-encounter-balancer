# M22: Brigand Axe / Craven Opportunist

К PC-каталогу добавлен Brigand с явно выбранным Axe-only loadout. [Книжное правило](../../rules/npc-profile-catalog.md#brigand-craven-m22), [контракт ADR-0077](../../decisions/ADR-0077-pc-brigand-craven-opportunist.md).

```python
from towr.domain.pc_npc_catalog import (
    PcBookNpcProfile, create_pc_book_npc, get_pc_book_npc_entry,
)

brigand = create_pc_book_npc(PcBookNpcProfile.BRIGAND_AXE, "brigand1")
entry = get_pc_book_npc_entry(PcBookNpcProfile.BRIGAND_AXE)
```

GM1.1 стр.97: Axe Close3d/3 Damage3,1H; Athletics3d/2; Toughness3/Resilience4 armoured, Minion. Вход хранит **базовые3d**, не постоянные5d. Metadata `active_abilities` сохраняет Craven, `unselected_attack_names` — Warbow из полной карточки. Это выбор снаряжения до боя по GM93, а не скрытое удаление второй атаки. NPC Axe не получает неуказанный PC armour-Damage Trait.

Craven Opportunist даёт +2d **вместо** обычного +1d при actual Melee outnumbering. Учитываются все пригодные союзники, включая Footpad; способность действует только на Brigand. Без превосходства или GM approval бонуса нет. Потери/Defenceless пересчитываются перед каждой Attack, Staggered сам по себе не исключает бойца. Drained убирает положительный modifier. Metadata не исполняется как произвольная программа.

Текущий JSON1/команды/метрики прежние; полные numeric definitions и зарезервированные book sources уже выражают выбранный профиль. Старые26пар M9–M21 не мигрируются. Footpad/Townsfolk и authored numeric NPC сохраняют свои правила. Это расширение PC family, не автоматическое включение Brigand во все старые NPC-сценарии.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m22/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m22/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [actual CLI result](pc-melee-simulation.result.json): два авторских PC с Axe/Staff против трёх Brigands Axe и одного Footpad, одна aware Close Zone, outnumbering approved. Optional Fate declined, backup null. Seed42,6trials,budget5rounds:5objective wins,1round limit,0party defeats/unsupported,73actions,23started/18completed rounds. В2trials погиб `pc1`, `pc2` не погибал; частичная потеря допускает продолжение группы. Fate/Help/ally Recover costs равны0.

[Balance request](pc-melee-balance.request.json) и [actual CLI result](pc-melee-balance.result.json) фиксируют party и одного Footpad, меняя1–3Brigands, по4trials:

| Brigands | Footpads | Objective | Round limit | Other outcomes | Actions |
|---|---|---|---|---|---|
| 1 | 1 | 4 | 0 | 0 | 10 |
| 2 | 1 | 4 | 0 | 0 | 24 |
| 3 | 1 | 3 | 1 | 0 | 48 |

Поиск сохраняет exact source/gear/party/Fate и пересчитывает Ability по реальному составу каждого боя. Ranking по objective rate прежний. Эти малые наблюдения не являются оценкой истинной вероятности, сравнением пользы Ability или доказательством оптимальной тактики.

Нативные детерминированные тесты отдельно подтверждают ровно5d Brigand при превосходстве, обычные4d Footpad, потерю бонуса после defeat союзника и запрет +1d/+2d stacking. Drained и Defenceless preparation cases явно помечены pure, без заявления о достижимости fresh Brigand Minion такого prefix в этой сцене.
