# M31: три melee-профиля гоблинов

Goblin Warrior и Night Goblin используют копьё со щитом; Nasty Skulker — Long knives. [Книжное правило](../../rules/npc-profile-catalog.md#goblin-chunk-m31), [контракт ADR-0082](../../decisions/ADR-0082-pc-goblin-melee-chunk.md). В PC каталоге22fixed loadouts.

| Profile ID | Атака | Protection | Профиль |
|---|---|---|---|
| GOBLIN_WARRIOR_SPEAR | Jagged Spear2d/3 Damage3,1H,до Short | Athletics3d/2 | Minion,T3/printed Res5 armoured,shield |
| NASTY_SKULKER | Long knives4d/4 Damage3,1H,Close | Defence4d/4 | Minion,T3/Res4 armoured,noShield |
| NIGHT_GOBLIN_SPEAR | Jagged Spear2d/3 Damage3,1H,до Short | Athletics3d/2 | Minion,T3/variant Res4 armoured,shield |

Все Normal Speed; бой остаётся в Close. Short у Spear — максимальная дальность Melee, а не минимум или Throwing optimum. Щит уже включён в printed Resilience: повторный+1 не начисляется. Night Goblin сохраняет явный variant override Res4, без восстановления поверх него ещё одной armour bonus из Typical Trappings.

```python
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc

goblin = create_pc_book_npc(PcBookNpcProfile.GOBLIN_WARRIOR_SPEAR, "goblin1")
skulker = create_pc_book_npc(PcBookNpcProfile.NASTY_SKULKER, "skulker1")
night = create_pc_book_npc(PcBookNpcProfile.NIGHT_GOBLIN_SPEAR, "night_goblin1")
```

**Dirty Coward:** повторный Staggered поражает Warrior/Night Goblin без раны. NPC бросает оружие и исключается из целей, численности и ходов; shield сохраняется. Native результат хранит `injury.defeat_cause` с actual resolution ID, target и Rule ID, `wounds=0`, `defeated=True`. Mandatory ACK выполняет drop один раз. Это NPC defeat; exit counter безопасного ухода Broken Official остаётся0. Прямой damaging Wound использует обычный Minion defeat/disposition. Промах уже Staggered атакующего нового Staggered не создаёт и бегство не вызывает.

**Backstabba:** Nasty Skulker наносит2Damage за success только в фактической unopposed Melee attack. Opposed Test с0successes у защитника сохраняет коэффициент1. Defenceless PC не может Oppose, поэтому условие возможно после тяжёлых ран; успешная атака всё равно создаёт одну forced Wound, а не по ране за success.

Horde Help и Skulking Menace/Stealth сохранены в metadata; NPC-стратегия их не выбирает. Shortbow и Weighted Net не выбраны. Сети требуют отдельной функции Throwing/primary Condition вместо Damage/запаса и восстановления; нынешние Attack/standard Recover/Fate policies не меняются.

В текущем PC JSON1 теперь обязательны:

- `enemies[*].holds_shield`: `true` для Warrior/Night Goblin, `false` для Skulker;
- `enemies[*].definition.attack.range_max`: `"short"` для Spear, `"close"` для Long knives.

Parser сохраняет явные значения, затем проверяет canonical loadout. Shield с2H/natural и подмены book profile отвергаются. `secondary_effects` остаётся `[]`: Dirty Coward — правило цели, Backstabba — подготовка Damage, а не новые on-hit descriptors. Все88прежних JSON documents мигрированы с false/close без изменения остальных значений/наблюдений; версия1/команды/метрики прежние.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m31/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m31/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): два PC со Staff против одного NPC каждого нового loadout, fixed priority Warrior → Skulker → Night Goblin; seed42,6trials,5rounds. Получены6objective/0party defeat/0limit/0unsupported,56actions,19started/13completed rounds, без потерь PC и optional/support/exit расходов.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json):1–2Warriors,0–1Skulkers,0–1Night Goblins, по2trials на8составов с тем же budget/порядком:

| Warriors | Skulkers | Night Goblins | Objective | Actions |
|---|---|---|---|---|
| 1 | 0 | 0 | 2 | 3 |
| 1 | 0 | 1 | 2 | 11 |
| 1 | 1 | 0 | 2 | 13 |
| 1 | 1 | 1 | 2 | 18 |
| 2 | 0 | 0 | 2 | 11 |
| 2 | 0 | 1 | 2 | 19 |
| 2 | 1 | 0 | 2 | 25 |
| 2 | 1 | 1 | 2 | 27 |

Остальные outcomes0. При top_k2 выбраны1/0/0 и1/0/1. Малая воспроизводимая выборка не доказывает гарантированной победы или оптимального состава. Подбор сохраняет исходные profiles/щиты/range/policies и хранит агрегаты без native journals.
