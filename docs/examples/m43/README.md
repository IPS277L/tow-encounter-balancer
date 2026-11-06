# M43: Dwarf Miner и явный grudge

Miner / Mining Pickaxe: Close4d/3 Damage4,2H; Defence4d/3, Minion/T4Res6 armoured/noShield. [Правило](../../rules/npc-profile-catalog.md#miner-grudge-m43), [согласованный контракт](../../decisions/ADR-0089-pc-miner-grudge-policy.md). Каталог содержит43боевых варианта.

Current PC JSON1 требует новое поле:

```json
"npc_grudge_policies": [
  {"actor_id": "miner1", "focus_actor_id": "pc2"}
]
```

Связь задаёт caller как факт ведущего. `[]` явно означает отсутствие grudge в данной сцене; поле обязательно и default не подставляется. Разрешены только canonical Miner → включённый PC, не более одной пары на Miner. Подбор состава удаляет пару исключённого Miner без переназначения.

До первого хода Miner получает Distracted с указанным focus. Encounter proof не расходует action/RNG. Melee против focus получает ordinary+1d; против остальных действует−1d Distracted. Protection против focus без штрафа, но без Melee bonus; против остальных−1d. **Miner продолжает выбирать цель по прежнему enemy_target_priority**, grudge не меняет его тактику автоматически.

Подтверждённая смерть focus снимает Condition после Wound/Fate completion; Near Miss и живой Defenceless сохраняют его. Следующий раунд не накладывает эффект снова. Grudge relationship и Condition хранятся раздельно; источники Miner и Brewguard не смешиваются.

Down in the Dark запрещает врагам bonus dice от higher ground против Miner, сохраняя прочие бонусы и собственный higher-ground bonus Miner. Blasting Charge и альтернативный Athletics1d3 явно unselected; NPC Pickaxe не получает PC Traits/повторный penalty. Underground movement, Recover/refocus, новые grudge encounters/внешние замены не входят в срез.

```python
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc
from towr.domain.pc_npc_grudge_policy_models import PcNpcGrudgePolicy

miner = create_pc_book_npc(PcBookNpcProfile.DWARF_MINER_PICKAXE, "miner1")
pair = PcNpcGrudgePolicy("miner1", "pc2")
```

Примеры используют два PC с Axe и Miner(s) → Footpad. У всех включённых Miners grudge на PC2; NPC target priority остаётся PC1 → PC2. Optional Fate declined, Help/extra-Attack policies пустые.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m43/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m43/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): Miner1+Footpad1, seed42/6trials/budget5rounds. Получены6objective/0party defeated/0limit/0unsupported,26actions,11started/5completed rounds, PC deaths0. Fate/Help/ally Recover/NPC exit/extra-Attack counters0.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json):0–2Miners+1Footpad, три состава по2trials.

| Miners | Footpads | Objective | Party defeated | Limit | Actions |
|---|---|---|---|---|---|
| 0 | 1 | 2 | 0 | 0 | 2 |
| 1 | 1 | 2 | 0 | 0 | 8 |
| 2 | 1 | 2 | 0 | 0 | 20 |

Unsupported везде0; при top_k2 выбраны0/1 и1/1. Малые выборки иллюстрируют интерфейс, а не истинную вероятность или оптимум. Wire version остаётся1, метрики прежние. Все136старыхJSON documents M9–M42 обновлены обязательными пустыми grudge arrays с сохранением остальных значений; прежние42entries не изменены.
