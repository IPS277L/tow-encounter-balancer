# M48: Skin Wolf и Warped Form

Skin Wolf — Fast Brute3/T4Res5 armoured с естественной Claws and Fangs Close5d3Damage5 и Athletics4d3 Protection. [Правило](../../rules/npc-profile-catalog.md#skin-wolf-warped-form-m48), [принятый контракт](../../decisions/ADR-0093-pc-skin-wolf-warped-form-end-phase.md).

```python
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc

wolf = create_pc_book_npc(PcBookNpcProfile.SKIN_WOLF, "skin_wolf1")
```

Current PC JSON1 требует `npc_warped_form_policies`, включая явный отказ `[]`. Пример для двух PCs и близкого союзного Flagellant:

```json
"npc_warped_form_policies": [
  {
    "actor_id": "skin_wolf1",
    "close_actor_ids": ["pc1", "pc2", "flagellant_hooks1"],
    "npc_defeat_decisions": [
      {
        "attacker_id": "skin_wolf1",
        "target_id": "flagellant_hooks1",
        "disposition": "killed",
        "gm_approved": true
      }
    ]
  }
]
```

Close list содержит всех PCs ровно по одному и остальных действительно близких NPC в порядке разрешения. Нахождение союзных NPC в одной Zone не доказывает Close: это отдельный факт вызывающего. Caster исключён; между настроенными Wolves факты симметричны. Для каждого NPC в списке обязательна отдельная GM disposition от caster, в том же относительном порядке. Подбор удаляет исключённых NPC и их записи без переназначения.

Выбранный wounded Skin Wolf без Staggered в конце своего хода платит Staggered, лечит одну неогненную рану и применяет волну к остальным живым Close creatures. Своя цена сохраняется, второй раз на себя волна не действует. Каждый target завершает всю очередь Wound/Fate/body/profile effects до следующего; затем закрывается TurnEnd. Способность срабатывает не более одного раза за ход, не тратит действие или Recover. Неподдержанный путь сохраняет фактический prefix.

`npc_blood_rage_actor_ids` теперь допускает Skin Wolf и Bestigor. В примерах Wolves отсутствуют в этом списке: добровольный Staggered перед атакой иначе блокирует лечение в том же ходу. Бонус+1d Melee от любого actual Staggered сохраняется независимо от списка. Это явные независимые решения caller; автоматической оптимизации тактики нет.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m48/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m48/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): два PCs против одного Wolf и одного Hooks and Chains Flagellant, seed42/6trials/6rounds. Получены2objective/2party defeated/2limit/0unsupported,115actions,33started/29completed rounds. Warped Form сработала в5trials/11activations, NPC Recover — в6trials/15actions. Хотя бы один PC погиб в3trials (pc1:3, pc2:2). Optional PC Fate declined; Flagellant выбирает Feel No Pain при0 и Recover при1.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json): четыре состава по2trials, Wolves1–2/Flagellant0–1; обе Wolf policies задают симметричный Close и могут задевать друг друга.

| Wolves | Flagellant | Objective | Party defeated | Limit | Actions | Warped Form | NPC Recover |
|---|---|---|---|---|---|---|---|
| 1 | 0 | 2 | 0 | 0 | 17 | 0 | 0 |
| 1 | 1 | 1 | 0 | 1 | 37 | 1 | 4 |
| 2 | 0 | 0 | 1 | 1 | 35 | 7 | 0 |
| 2 | 1 | 0 | 2 | 0 | 31 | 5 | 2 |

Unsupported везде0; top2:1/1, затем1/0. Малые выборки иллюстрируют интерфейс и тактику; ROUND_LIMIT остаётся отдельным исходом.

Result содержит source-ordered `npc_warped_form_counts`, `npc_warped_form_trial_count` и `total_npc_warped_form_count`. Activation учитывается после cost/heal даже при последующем unsupported, не входит в actions/NPC Recover. Wave может ранить несколько существ; бюджеты Wounds/Fate/Recover учитывают эти источники.156прежнихJSON documents мигрированы только required пустыми policies/нулевыми activation fields; wire version1 прежняя.
