# M44: Halfling Thief и Stealth Protection

Thief / Dagger: Close2d/3 Damage1,1H; Stealth3d/5 Protection, Minion/T2Res2 без брони/щита. [Правило](../../rules/npc-profile-catalog.md#halfling-stealth-m44), [принятый контракт](../../decisions/ADR-0090-pc-halfling-stealth-protection.md). Каталог содержит44боевых варианта.

```python
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc

thief = create_pc_book_npc(PcBookNpcProfile.HALFLING_THIEF_DAGGER, "thief1")
```

Существующее поле current PC JSON1 содержит printed Protection:

```json
"protection": {
  "source_rule_id": "BOOK-GM-GUIDE:1.1:p103:halfling_thief_dagger:stealth",
  "skill": "stealth",
  "test_profile": {"dice": 3, "threshold": 5, "pool_cap": null}
}
```

Stealth разрешён только полному canonical Thief loadout. Дополнительных public policy/полей нет: PC owner подтверждает Now You See Me через typed permission с actual defender и полным definition. Awareness в текущем сценарии явно true. Unaware/Defenceless не могут Oppose; само разрешение не требует оружия/щита. Обычный cap Stealth равен6; Dagger —4. PC Dagger Traits/повторные penalties не добавляются.

Throwing Knives сохранены unselected, полная Thieving Blighter metadata не вызывает исчезновение/кражу в fixed Attack/noMove сцене. Thief использует прежние NPC turn/target priority. Help, Fate, grudge и extra Attack policies не расширены. Прежние140JSON documents M9–M43 не менялись; wire version1 и метрики прежние.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m44/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m44/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): два PC Axe против Thief1+Footpad1, seed42/6trials/budget5rounds. Получены6objective/0party defeated/0limit/0unsupported,14actions,7started/1completed rounds, PC deaths0. Fate/Help/ally Recover/NPC exit/extra-Attack counters0.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json):0–2Thieves+1Footpad, три состава по2trials.

| Thieves | Footpads | Objective | Party defeated | Limit | Actions |
|---|---|---|---|---|---|
| 0 | 1 | 2 | 0 | 0 | 2 |
| 1 | 1 | 2 | 0 | 0 | 4 |
| 2 | 1 | 2 | 0 | 0 | 11 |

Unsupported везде0; при top_k2 выбраны0/1 и1/1. Малые выборки иллюстрируют интерфейс, а не истинную вероятность или оптимальную тактику.
