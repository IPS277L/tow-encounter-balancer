# M46: Bestigor, Blood Rage и однократный Glorious

Bestigor / Massive Axe: Close3d/4 Damage7,2H; Defence4d/3, Normal Brute2/T4Res6 armoured/noShield. Attack cap8 задан явно от WS4, Protection cap8 — обычный. [Правило](../../rules/npc-profile-catalog.md#bestigor-blood-rage-m46), [принятый контракт](../../decisions/ADR-0091-pc-bestigor-blood-rage-and-wound-glorious.md). Каталог содержит49боевых вариантов.

```python
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc

bestigor = create_pc_book_npc(PcBookNpcProfile.BESTIGOR_MASSIVE_AXE, "bestigor1")
```

Current PC JSON1 требует новое поле:

```json
"npc_blood_rage_actor_ids": ["bestigor1"]
```

Указанный Bestigor перед фактической Attack добровольно получает Staggered, если его ещё нет. Это не дополнительный action или бросок. `[]` отказывается только от добровольного наложения; любой фактический Staggered всё равно даёт ему+1d Melee. Уже Staggered не накладывается второй раз и не вызывает Wound. Бонус обычный: проходит cap/Drained, не распространяется на Defence. Actor ID должен принадлежать canonical Bestigor, список exact/unique/required, default не подставляется. Count search удаляет исключённого actor без переназначения.

После actual первой раны W1 **ровно следующая Attack Bestigor** становится Glorious. Выбранная тактика перебрасывает все доступные провалы один раз. Бонус расходуется этой Attack при любом результате, сохраняется до неё и не возобновляется каждый раунд при оставшейся W1. Protection/Help других участников его не тратят. W2 до хода даёт обычное defeat без фиктивной Attack. NPC Glorious не тратит PC Fate. Полный typed W1 source/Attack proof сохраняется внутри native journal, компактные trial records его не получают.

W0 запрещает выбор Give Ground/Prone, не даёт общей immunity к forced Prone; текущая price strategy — SUFFER_WOUND. Alternate Athletics3d3 и woodland Child of the Forest сохранены вне выбранной fixed сцены. PC weapon Traits/повторный penalty Massive Axe не добавляются. Никаких NPC Recover/лечения/новых типов Attack эта веха не включает.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m46/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m46/pc-melee-balance.request.json
```

Примеры используют два PC Axe, Bestigor(s) → Footpad, включают Blood Rage всех выбранных Bestigors и сохраняют прежний NPC target priority PC1 → PC2. Optional PC Fate declined, Help/extra-Attack/grudge policies пустые.

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): Bestigor1+Footpad1, seed42/6trials/budget5rounds. Получены6objective/0party defeated/0limit/0unsupported,53actions,18started/12completed rounds, PC deaths0. Все Fate/Help/ally Recover/NPC exit/extra-Attack counters0.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json):0–2Bestigors+1Footpad, три состава по2trials.

| Bestigors | Footpads | Objective | Party defeated | Limit | Actions |
|---|---|---|---|---|---|
| 0 | 1 | 2 | 0 | 0 | 2 |
| 1 | 1 | 2 | 0 | 0 | 18 |
| 2 | 1 | 2 | 0 | 0 | 27 |

Unsupported везде0; при top_k2 выбраны0/1 и1/1. Малые выборки иллюстрируют интерфейс, а не истинную вероятность или оптимальную тактику. Wire version1 и метрики прежние;148старыхJSON documents M9–M45 обновлены required пустыми Rage arrays с сохранением остальных значений,48прежнихcatalog entries не менялись.
