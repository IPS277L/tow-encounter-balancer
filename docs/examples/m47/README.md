# M47: Flagellant, Feel No Pain и NPC Recover

Оба loadouts — Normal Brute2/T3Res3 без брони/щита, Athletics3d3, ordinary caps6. Flails: Close3d4Damage6/2H и−2d Melee при Staggered. Hooks and Chains: Close3d4Damage3/1H без этого штрафа. [Правило](../../rules/npc-profile-catalog.md#flagellant-feel-no-pain-m47), [принятый контракт](../../decisions/ADR-0092-pc-flagellant-feel-no-pain-and-recover.md). Каталог содержит51боевой вариант.

```python
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc

flails = create_pc_book_npc(PcBookNpcProfile.FLAGELLANT_FLAILS, "flagellant_flails1")
hooks = create_pc_book_npc(PcBookNpcProfile.FLAGELLANT_HOOKS_CHAINS, "flagellant_hooks1")
```

Current PC JSON1 требует новое поле:

```json
"npc_flagellant_policies": [
  {
    "actor_id": "flagellant_flails1",
    "feel_no_pain": "wound_at_zero",
    "recover_when_wounded": true
  }
]
```

Политика `wound_at_zero` заменяет первое Staggered от weak incoming hit либо собственного miss одной Wound только при0ранах. При1ране замена добровольно не выбирается; прямой урон не даёт второй раны. `decline` отказывается от замены. `recover_when_wounded=true` выбирает при1ране standard self Recover в обычный ход: снимает свои Staggered/Prone и лечит одну Wound. Это одно действие, с обычным TurnEnd и без RNG/Fate; Attack в тот же ход нет. `false` сохраняет Attack. `[]` отказывается от обоих новых choices, а не отключает Flails penalty/Unbreakable.

Все поля обязательны; actor должен быть canonical Flagellant, записи уникальны. Count search удаляет запись исключённого NPC без переназначения. Helper атакует сам, если его named beneficiary будет Recover. Broken блокируется только для этих canonical Flagellants; общей psychological immunity нет. Фиксированное оружие не меняется и не получает PC Traits.

Result summary содержит отдельные `npc_recover_action_trial_count`, source-ordered `npc_recover_action_counts` и `total_npc_recover_action_count`. NPC Recover входит в total actions; PC self/ally costs отдельные. Feel No Pain follow-up не считается новым действием. В record остаются компактные counts, без journal.152прежнихJSON documents M9–M46 мигрированы required пустыми policies/нулевыми Recover fields, остальные значения сохранены; wire version1 прежняя.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m47/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m47/pc-melee-balance.request.json
```

Примеры задают одного PC со Staff, обоих Flagellants с Feel No Pain+Recover и прежний target priority. Optional PC Fate declined, Help/extra-Attack/grudge/Rage policies пустые.

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json):1Flails+1Hooks, seed42/6trials/budget5rounds. Получены0objective/2party defeated/4limit/0unsupported,83actions,28started/26completed rounds. PC погиб в2trials. Во всех6trials был NPC Recover:26actions всего,19уFlails и7уHooks. Остальные Fate/Help/ally Recover/NPC exit/extra-Attack counters0.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json):1–2Flails+0–1Hooks, четыре состава по2trials.

| Flails | Hooks | Objective | Party defeated | Limit | Actions | NPC Recover |
|---|---|---|---|---|---|---|
| 1 | 0 | 0 | 0 | 2 | 20 | 7 |
| 1 | 1 | 0 | 0 | 2 | 30 | 11 |
| 2 | 0 | 0 | 1 | 1 | 30 | 11 |
| 2 | 1 | 0 | 2 | 0 | 21 | 5 |

Unsupported везде0; при top_k2 выбраны1/0 и1/1. Healing может поддерживать бой до round budget; ROUND_LIMIT остаётся отдельным исходом в общем знаменателе trials. Малые выборки иллюстрируют интерфейс и выбранную тактику, не истинную вероятность или найденный оптимум.
