# M50: Bear / Crushing Weight

Crushing Weight — альтернативная естественная атака Bear: Close3d3Damage7, hands=null, cap8 отWS4; Athletics3d3 Protection, Brute3/T5Res6 armoured/noShield. W1–2 дают Drained, W3 — defeat. [Правило](../../rules/npc-profile-catalog.md#bear-crushing-weight-m50), [принятый контракт](../../decisions/ADR-0095-pc-bear-crushing-weight-pre-stagger-prone.md).

```python
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc

crushing = create_pc_book_npc(PcBookNpcProfile.BEAR_CRUSHING_WEIGHT, "crushing_bear1")
sweeping = create_pc_book_npc(PcBookNpcProfile.BEAR_SWEEPING_CLAWS, "bear1")
```

В current PC JSON1 новая атака содержит закрытый descriptor:

```json
"secondary_effects": [
  {
    "kind": "prone_before_give_ground",
    "rule_id": "RULE-PROFILE-CREATURE-010:crushing-weight-prone",
    "affects_monstrosities": true
  }
]
```

Все поля обязательны. Этот descriptor и explicit cap8 разрешены только полной canonical Crushing Weight Attack; произвольные authored NPC его не получают. Прежний `condition_on_hit`/Drained сохраняет свой порядок после Damage. Верхнеуровневые поля, счётчики и версия1 прежние;164старыхJSON не мигрируются.

На попадании цель получает Prone до Staggered/Wound. Даже слабый удар может повалить; MISS этого не делает. Уже брошенный Attack не получает задним числом higher-ground бонус. Near Miss отменяет Wound, сохраняя Prone от попадания. Ordinary self/ally Recover может его снять; история попадания не накладывает его заново. Прежние ongoing Wound-Prone ограничения сохраняются.

`npc_extra_attack_actor_ids` теперь допускает оба Bear loadouts:

```json
"npc_extra_attack_actor_ids": ["crushing_bear1", "bear1"]
```

После successful первой Attack и всех Wound/Fate/body последствий Bear атакует первого другого живого PC по текущему приоритету. Crushing Weight применяется и во второй Attack; третьего действия нет. `[]` отказывается только от второй Attack, сохраняя Prone на попадании. Existing extra-Attack counters считают реальные выполненные действия; неподдержанная обязательная ветвь оставляет фактический prefix.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m50/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m50/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): два PCs со Staff против1Crushing+1Sweeping Bear, оба включены в extra-Attack list; seed42/6trials/5rounds. Получены0objective/1party defeated/5limit/0unsupported,118actions,30started/29completed rounds. Во всех6trials была дополнительная Attack:19всего,5уCrushing/14уSweeping. Хотя бы один PC потерян в4trials (pc1:4,pc2:1). Optional PC Fate declined; остальные optional NPC policies пусты.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json):1–2Crushing+0–1Sweeping Bears, четыре состава по2trials.

| Crushing | Sweeping | Objective | Party defeated | Limit | Actions | Extra attacks | Trials с потерями PC |
|---|---|---|---|---|---|---|---|
| 1 | 0 | 2 | 0 | 0 | 19 | 2 | 0 |
| 1 | 1 | 0 | 0 | 2 | 40 | 5 | 1 |
| 2 | 0 | 0 | 0 | 2 | 41 | 4 | 0 |
| 2 | 1 | 0 | 2 | 0 | 49 | 11 | 2 |

Unsupported везде0; top2:1/0, затем1/1. Подбор фильтрует existing actor list без переназначения. ROUND_LIMIT и отдельные PC losses отличаются от поражения всей party. Малые выборки демонстрируют интерфейс и тактику, не истинные вероятности или найденный оптимум.
