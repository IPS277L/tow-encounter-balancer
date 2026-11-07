# M51: Great Stag, Crown of Antlers и Trample

Great Stag имеет две естественные Close-атаки: Mighty Antlers Melee4d/3 Damage6/cap8 и Trample Brawn5d/3 Damage5/cap10. Protection Athletics5d/4; Brute3, W2Drained. [Полное правило](../../rules/npc-profile-catalog.md#great-stag-crown-trample-m51), [принятые конкретизации](../../decisions/ADR-0096-pc-great-stag-crown-and-trample.md).

```python
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc

stag = create_pc_book_npc(PcBookNpcProfile.GREAT_STAG, "great_stag1")
```

Первое действие — Antlers. Выбранный в `npc_extra_attack_actor_ids` Stag получает второе действие Trample только после нового Prone от принятой раны первой атаки или её проваленного Endurance. Проверка ждёт завершения Fate и всех обязательных последствий. Уже Prone и отменённая Near Miss рана разрешения не дают. Топтать можно только ту же живую всё ещё Prone цель; при её смерти переназначения нет. `[]` отказывается от второй атаки.

PC защищается от Trample своим Endurance; Defenceless не Opposes. Это настоящий второй Test с собственным Damage5, Fate и учётом действия. Bear в тех же сценах сохраняет свою вторую атаку по другой цели. Existing extra-Attack counts учитывают реальные действия обоих существ.

Текущий PC JSON1 требует у Great Stag `definition.trample_attack`:

```json
{
  "id": "trample",
  "source_rule_id": "BOOK-GM-GUIDE:1.1:p176:great_stag:trample",
  "skill": "brawn",
  "test_profile": {"dice": 5, "threshold": 3, "pool_cap": null},
  "damage": {"base": 5, "success_multiplier": 1},
  "range_max": "close",
  "hands": null,
  "secondary_effects": []
}
```

Все поля обязательны, профиль проверяется целиком. У остальных NPC это поле запрещено; прежние168JSON не мигрируются. Primary Antlers остаётся в `definition.attack`. Charge, Give Ground destination, Fearsome без Give Ground и всадник в неподвижной сцене не исполняются; ordinary Trample не выбирается вместо первой Antlers.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m51/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m51/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): два PC со Staff против одного Great Stag, Crown включён; seed42,6trials,5rounds. Получены5objective/0party defeated/1limit/0unsupported,75actions,27started/22completed rounds. Два Trample в двух trials; потерь PC нет. Optional PC Fate declined, остальные optional NPC policies пусты.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json): 1–2Stags и0–1Sweeping Claws Bear, все включены в extra-Attack list; четыре состава по2trials.

| Stags | Bears | Objective | Party defeated | Limit | Actions | Trample | Bear extra | Trials с потерями PC |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 | 2 | 0 | 0 | 24 | 1 | 0 | 0 |
| 1 | 1 | 0 | 1 | 1 | 38 | 0 | 4 | 2 |
| 2 | 0 | 0 | 1 | 1 | 33 | 3 | 0 | 2 |
| 2 | 1 | 0 | 2 | 0 | 42 | 0 | 3 | 2 |

Unsupported везде0; top2:1/0, затем1/1. Подбор фильтрует actor list без переназначения. Малые выборки показывают интерфейс и выбранную тактику; они не задают истинные вероятности или оптимальный состав.
