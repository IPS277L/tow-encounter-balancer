# M37: Razorgor и Minotaur

Три Brute3 loadouts: natural Razorgor, Minotaur с одним Axe и Minotaur с двумя Axes. [Правило и источники](../../rules/npc-profile-catalog.md#devour-chunk-m37), [ADR-0085](../../decisions/ADR-0085-pc-devour-and-wound-rage.md). В M37 каталог достиг34боевых вариантов; актуальный состав — в [статусе](../../project-status.md).

| Loadout | Атака | Protection | Resilience |
|---|---|---|---|
| Razorgor | natural Razor Tusks Close3d/4 Damage5,hands=null | Athletics3d/3 | T5/Res6 armoured |
| Minotaur Single Axe | Axe Close4d/5 Damage5,1H | Athletics4d/4 | T5/Res6 armoured,noShield |
| Minotaur Dual Axes | printed Axe4d/5 Damage5,1H каждый, отдельный dual Damage+1 | Athletics4d/4 | T5/Res6 armoured,noShield |

Два топора занимают обе руки; printed base5 не заменяется6 и не получает PC Axe Traits. Оба существа при первой/второй собственной ране получают обычный+1/+2d Melee, третья рана означает defeat. Drained от этих ран не возникает. Обычный cap остаётся6 у Razorgor и8 у Axe Minotaur.

Devour the Fallen добавляет один куб по таблице ран, если **цель до атаки** Staggered, Prone или уже Wounded. Несколько условий/ран не дают несколько бонусов. Если рана снимает прежний Staggered, бонус этой атаки сохраняется. Здоровая цель не квалифицируется из-за новой раны от того же удара. Table dice — не Test: Drained, Grim/Glorious и cap Attack Test не изменяют их. Дополнительный куб не даёт вторую рану и не накапливается отдельным ongoing effect.

Fearsome/Charge/Charging Bull сохранены с полными условиями, но fixed Attack/SUFFER_WOUND/noMove стратегия их не выбирает. Current PC JSON1, Fate/Help policies и метрики прежние. В этих примерах Help pairs пусты, optional Fate declined.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m37/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m37/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): два PC с Axe против одного NPC каждого loadout. Priority/активации NPC: Razorgor → Single Axe Minotaur → Dual Axes Minotaur. Seed42/6trials/budget5rounds. Получены0objective/6party defeated/0limit/0unsupported,76actions,18started/12completed rounds. Оба PC defeated во всех6trials; Fate/Help/ally Recover/NPC exit counters0.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json):1–2Razorgors,0–1Single Axe,0–1Dual Axes,8составов по2trials. Source, caller order, приоритеты и defeat decisions фильтруются по retained IDs.

| Razorgors | Single Axe | Dual Axes | Objective | Party defeated | Limit | Actions |
|---|---|---|---|---|---|---|
| 1 | 0 | 0 | 2 | 0 | 0 | 17 |
| 1 | 0 | 1 | 0 | 2 | 0 | 24 |
| 1 | 1 | 0 | 0 | 2 | 0 | 24 |
| 1 | 1 | 1 | 0 | 2 | 0 | 29 |
| 2 | 0 | 0 | 0 | 0 | 2 | 35 |
| 2 | 0 | 1 | 0 | 2 | 0 | 25 |
| 2 | 1 | 0 | 0 | 2 | 0 | 25 |
| 2 | 1 | 1 | 0 | 2 | 0 | 24 |

Unsupported везде0; при top_k2 выбраны1/0/0 и1/0/1. Это небольшие иллюстративные выборки, не истинная вероятность или найденная оптимальная тактика. Limit остаётся самостоятельным исходом в общем знаменателе. Все31прежниеentries и112JSON documents M9–M36 сохранены без изменений.

В M37 Greataxe оставалась unselected: printed3d приWS4 требует cap8. Отдельный корректный вариант реализован в [M38](../m38/README.md) без миграции этих JSON-примеров; старые Axe loadouts остаются самостоятельными.
