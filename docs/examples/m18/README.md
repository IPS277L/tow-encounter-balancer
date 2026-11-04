# M18: одноручное PC-оружие

Группа может сочетать Staff/Sword и новые Dagger, Axe, Warhammer, Morning Star. Книжные Damage/Traits исполняются в существующем owner вместе с Help/Fate/ранами/Recover. [Правила и точные ограничения](../../rules/equipment.md#исполняемая-pc-граница-m18).

В нынешнем PC JSON1 поле `party[].pc.weapon` принимает `staff`, `sword`, `dagger`, `axe`, `warhammer`, `morning_star`. Остальная форма, обязательные nullable policies и метрики сохраняются. Неизвестные значения и произвольные числовые Traits не допускаются. Новая версия формата не вводится.

Примеры задают четырёх здоровых PC с Axe/Warhammer/Morning Star/Dagger и отдельными Fate resources/policies против одного armoured Minion и одного armoured Brute. Это авторские числовые NPC, не профили бестиария. `pc4` может выполнять standard Recover для `pc3`; все сохраняют Attack/Recover fallback. Enemy priority начинает с `pc3`, PC атакуют сначала Brute. Сцена без щитов, дополнительных Abilities, terrain и mounted combat; положительный numeric resilience bonus здесь означает броню.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m18/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m18/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [actual CLI result](pc-melee-simulation.result.json): seed42,6trials, budget5rounds,6objective wins,60actions,14started/8completed rounds,21Glorious spends. PC deaths, Near Miss, Help и actual ally Recover actions равны0. Это лёгкий демонстрационный бой; наличие policy не гарантирует её применение. Границы Staggered/Help/Drained/minimum die, повреждение руки и подбор оружия проверяются отдельными детерминированными тестами.

[Balance request](pc-melee-balance.request.json) и [actual CLI result](pc-melee-balance.result.json): fixed party,0–1Minion+1Brute, два кандидата по4trials. Оба дали4objective wins;32/43actions соответственно. Ранжирование сохраняет прежние objective-rate критерии и стабильное разрешение равенства; изменение оружия не является параметром поиска. Полный request и каждый candidate scenario сохраняют выбранное оружие, ресурсы, роли и policies.

Наблюдения малой выборки не являются оценкой истинной вероятности или доказательством оптимальной тактики. Двуручное оружие, dual wield, дальности вне Close, Stealth conceal и Staff terrain trait не входят в этот исполняемый срез.
