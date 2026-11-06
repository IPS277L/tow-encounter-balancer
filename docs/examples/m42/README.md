# M42: Brewguard и Distracted, привязанный к атакующему

Dwarf Brewguard / Warhammer: Close4d/3 Damage3,1H; Defence4d/3, Brute2/T4Res5 armoured/noShield. [Правило](../../rules/npc-profile-catalog.md#brewguard-distracted-m42), [принятая трактовка A](../../decisions/ADR-0088-pc-brewguard-distracted-focus.md). Каталог содержит42боевых варианта.

GM104 W1 формулируется как «Attacker inflicts Distracted condition». Пользователь уточнил: раненый Brewguard разово отвлекается на PC, фактически нанёсшего первую рану. В Melee по этому PC и Protection против него штрафа нет; против остальных действует ordinary−1d. Helper не становится focus, выбор цели остаётся прежним.

| Событие | Состояние Distracted |
|---|---|
| Actual Wound0→1 и её profile ACK | Наложено с focus=attacker |
| Focus жив и Defenceless | Сохраняется |
| Raw lethal roll, Fate ещё не решён | Сохраняется до completion |
| Near Miss отменил смертельную рану | Сохраняется |
| Подтверждённая смерть focus | Снимается обязательным expiry proof |
| Brewguard остаётся с W1 после снятия | Повторно не накладывается |

Наложение и снятие не являются действиями, не требуют RNG и не создают TurnEnd. Один owner хранит actual source/focus receipts, чтобы не менять уже завершённую Protection и не перенести штраф на неправильного PC. Willpower Recover, Cooler Heads Leadership action, внешняя замена Distracted и потеря видимости в этот срез не включены. Printed альтернативы Bare Hands/Athletics сохранены unselected; Warhammer не получает PC Traits.

```python
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc

brewguard = create_pc_book_npc(PcBookNpcProfile.DWARF_BREWGUARD_WARHAMMER, "brewguard1")
```

Примеры используют два PC с Axe, Brewguard(s) → Footpad, optional Fate declined и пустые Help/extra-Attack policies. Трактовка применяется к canonical Brewguard автоматически; caller не подставляет focus отдельным source полем.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m42/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m42/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): один Brewguard и один Footpad, seed42/6trials/budget5rounds. Получены6objective/0party defeated/0limit/0unsupported,56actions,18started/12completed rounds, подтверждённых PC deaths0. Fate/Help/ally Recover/NPC exit/extra-Attack counters0.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json):0–2Brewguards+1Footpad, три состава по2trials.

| Brewguards | Footpads | Objective | Party defeated | Limit | Actions |
|---|---|---|---|---|---|
| 0 | 1 | 2 | 0 | 0 | 2 |
| 1 | 1 | 2 | 0 | 0 | 12 |
| 2 | 1 | 0 | 0 | 2 | 35 |

Unsupported везде0; при top_k2 выбраны0/1 и1/1. Малые выборки иллюстрируют интерфейс, а не истинную вероятность/оптимум. PC JSON1, поля, метрики и стратегии прежние; все41старыхentries и132JSON documents M9–M41 сохраняются без миграции.
