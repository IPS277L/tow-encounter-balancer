# M53: PC со щитом

Рабочий щит даёт +1Resilience отдельно от authored armour_bonus и разрешает Defence против Throwing. Сам щит не добавляет куба. Если PC также держит пригодный Sword и не Staggered, его +1d Defence действует и против Net. Dropped/unusable Sword этого бонуса не даёт. Против Brawn/Trample сохраняется Endurance.

Поддержаны шесть нынешних1H weapons: Dagger, Staff, Axe, Sword, Warhammer, Morning Star. Shield занимает другую руку. [Полное правило](../../rules/equipment.md#pc-shield-m53), [принятый контракт](../../decisions/ADR-0098-pc-shield-and-hand-equipment.md).

```python
from towr.domain.pc_melee_models import (
    PcShieldLoadout, PcShieldHandConflictPolicy, PcShieldRecoveryPolicy, PcWeaponHand,
)

shield = PcShieldLoadout(
    PcWeaponHand.LEFT,
    PcShieldHandConflictPolicy.WEAPON_FIRST,
    PcShieldRecoveryPolicy.RESTORE_BEFORE_ATTACK,
)
# PcMeleeParticipant: initial_weapon_hand=PcWeaponHand.RIGHT, shield=shield.
```

В текущем PC JSON1 новый объект находится на уровне party participant:

```json
"shield": {
  "initial_hand": "left",
  "hand_conflict_policy": "weapon_first",
  "recovery_policy": "restore_before_attack"
}
```

Все три поля обязательны. Initial hand противоположна оружейной;2H и backup policy с shield в этом срезе запрещены. У PC без щита поле отсутствует; null не создаёт допустимый source. Прежние176JSON не мигрируются.

Выпадает предмет фактически выбранной случайной руки: weapon или shield. Если после раны здоровая shield-рука нужна оружию, PC на своём ходу сначала оставляет shield, затем меняет оружейную руку или подбирает weapon. После чужой атаки немедленного swap нет. При16/20 shield недоступной руки теряет защиту без выдуманного ground pickup; после12 щит не поднимается травмированной рукой.18 drop/clutch учитывает занятость щитом.

Dropped shield возвращается отдельным standard Recover, если есть свободная здоровая рука. Если выпали оба предмета, первый Recover возвращает weapon, следующий подходящий — shield: один object interaction за действие. Прежние стандартные Staggered/Prone benefits сохраняются. Если свободной руки нет, бесполезного Recover нет. W14 вызывает Critical при добровольном shield release; W15 разрешает сам drop, но дальнейший swap/Recover сохраняет его последствия.

Resilience и Protection берутся до конкретной атаки. Её последующая рана/потеря щита не меняет уже рассчитанный Damage; следующая атака видит новое снаряжение. Net/Wound Conditions не исчезают от подбора предмета. Результаты и стоимость Recover входят в обычные агрегаты; отдельного shield counter в JSON нет.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m53/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m53/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): два PC Sword+shield с authored Strength1/Melee1/armour_bonus0 против2Net Goblins+1Footpad; seed42,6trials,4rounds. Получены1objective/0party defeated/5limit/0unsupported,100actions,24started/23completed rounds; потерь PC нет.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json):1–2Net Goblins и0–1Footpad, четыре состава по2trials. Party/shield/тактика фиксированы, меняется состав NPC.

| Net Goblins | Footpads | Objective | Party defeated | Limit | Actions |
|---|---|---|---|---|---|
| 1 | 0 | 1 | 0 | 1 | 14 |
| 1 | 1 | 1 | 0 | 1 | 20 |
| 2 | 0 | 2 | 0 | 0 | 16 |
| 2 | 1 | 1 | 0 | 1 | 32 |

Unsupported и потери PC везде0. Малые выборки показывают интерфейс и выбранную тактику; они не задают истинные вероятности или оптимальный состав.
