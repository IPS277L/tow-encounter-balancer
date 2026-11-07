# M49: Imperial Ogre и наземный Pegasus

Два самостоятельных Brutes в неподвижной Close-сцене по [принятому ADR-0094](../../decisions/ADR-0094-pc-imperial-ogre-cap-and-grounded-pegasus.md). [Правило](../../rules/npc-profile-catalog.md#ogre-grounded-pegasus-m49).

```python
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc

ogre = create_pc_book_npc(PcBookNpcProfile.IMPERIAL_OGRE_GREATHAMMER, "ogre1")
pegasus = create_pc_book_npc(PcBookNpcProfile.PEGASUS_GROUNDED, "pegasus1")
```

Ogre: Brute3/T5Res6 armoured, Greathammer Close2d4Damage8/2H, Athletics3d3 Protection, без щита. Attack имеет `{"dice":2,"threshold":4,"pool_cap":6}`: cap следует из WS3, а printed2d уже учитывает оружие. Дополнительные PC weapon penalties/Traits не применяются. При1–2ранах Speed становится Normal; в неподвижном бою это не новое действие или Condition. Rough Shove/Ogre Pistol не выбраны, связанные с ними Ogre Charge/Mighty Throw не переносятся на Greathammer.

Pegasus: Brute2/T3Res3 без брони/щита/оружия, natural Hooves Close3d3Damage3/hands=null, Athletics4d4 Protection. Оба `pool_cap:null`, обычные пределы6/8. `pegasus_grounded` явно означает, что он начинает на земле и остаётся там в сцене без движения и внешних эффектов. ПослеW1 он не может летать и уже находится на земле; отдельного landing action не возникает. Это факт выбранного сценария, а не новая книжная разновидность или полная реализация полёта. Всадника и Charge нет.

Current PC JSON1 сохраняет прежние поля и version1. Shared schema допускает cap6, но native source validation разрешает его только Attack полного canonical Ogre/Greathammer. Произвольный authored NPC или Protection с6 отвергаются. Прежние cap8/null сохраняются. Новых policies/счётчиков нет,160предыдущихJSON не мигрируются.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m49/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m49/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): два PCs со Staff против1Ogre+1Pegasus, seed42/6trials/4rounds. Получены3objective/0party defeated/3limit/0unsupported,80actions,24started/21completed rounds. PC losses0, optional Fate declined; все optional NPC policies пусты.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json):1–2Ogres+0–1Pegasus, четыре состава по2trials с фиксированной party.

| Ogres | Pegasus | Objective | Party defeated | Limit | Actions | Trials с потерями PC |
|---|---|---|---|---|---|---|
| 1 | 0 | 1 | 0 | 1 | 19 | 0 |
| 1 | 1 | 0 | 0 | 2 | 29 | 0 |
| 2 | 0 | 0 | 0 | 2 | 29 | 0 |
| 2 | 1 | 0 | 0 | 2 | 35 | 1 |

Unsupported везде0; top2:1/0, затем1/1. При2/1 потерян pc1 в одном trial, что отличается от поражения всей party. ROUND_LIMIT остаётся отдельным исходом. Малые выборки показывают интерфейс и тактику, не истинные вероятности или найденный оптимум.
