# M38: Minotaur Greataxe — 3d с пределом8

Minotaur с Greataxe использует printed3d/5 Damage8,2H, Athletics4d/4, Brute3/T5Res6 armoured/noShield. [Правило](../../rules/npc-profile-catalog.md#greataxe-cap-m38), [выбранный контракт](../../decisions/ADR-0086-pc-minotaur-greataxe-pool-cap.md). Каталог содержит35боевых вариантов.

Стартовые3куба уже включают особенность оружия; повторный штраф не применяется. Maximum8 следует из Weapon Skill4. В full source это существующее required поле:

```json
"test_profile": {"dice": 3, "threshold": 5, "pool_cap": 8}
```

Значение8 разрешено **только у атаки этой canonical книжной identity**. Protection и остальные book/authored profiles сохраняют null. Поле остаётся обязательным; неправильные cap/source/type отвергаются до RNG. `8.0` может пройти числовое сравнение JSON Schema, но typed admission отклоняет его. Schema enum:[null,8], codec/версия1/метрики без изменений; старые requests не мигрируются.

W1/W2 дают ordinary+1/+2d Melee: без прочих бонусов атака имеет4/5dice и тот же maximum8. W3defeats. Devour the Fallen добавляет один table die по состоянию цели до атаки. Drained убирает Test bonuses, сохраняя table die. Dual Damage+1 сюда не переносится. Native тест с двумя помощниками демонстрирует7ordinary+2bypass=9dice; pure проверка показывает maximum8 и последующий+2bypass=10.

Fearsome/Charging Bull полными metadata вне выбранной fixed Attack/SUFFER_WOUND/noMove стратегии. Эти примеры используют два PC с Axe, optional Fate declined и пустые Help pairs. Priority/активации NPC: Greataxe Minotaur(s) → Razorgor. Предыдущие Single/Dual Axe loadouts остаются самостоятельными entries.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m38/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m38/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): один Greataxe Minotaur и один Razorgor, seed42/6trials/budget5rounds. Получены0objective/5party defeated/1limit/0unsupported,77actions,23started/18completed rounds. PC1defeated6/PC2defeated5; Fate/Help/ally Recover/NPC exit counters0.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json):1–2Greataxe Minotaurs,0–1Razorgor,4состава по2trials.

| Greataxe Minotaurs | Razorgor | Objective | Party defeated | Limit | Actions |
|---|---|---|---|---|---|
| 1 | 0 | 2 | 0 | 0 | 20 |
| 1 | 1 | 0 | 2 | 0 | 21 |
| 2 | 0 | 0 | 2 | 0 | 21 |
| 2 | 1 | 0 | 2 | 0 | 23 |

Unsupported везде0; при top_k2 выбраны1/0 и1/1. Это небольшие иллюстративные выборки, не истинная вероятность или оптимальная тактика. Limit остаётся отдельным исходом в общем знаменателе. Все34прежниеentries и116JSON documents M9–M37 сохранены без изменений.
