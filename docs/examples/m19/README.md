# M19: двуручное Close-оружие PC

Добавлены Pickaxe, Flail, Billhook, Halberd, Glaive, Greataxe, Greathammer. [Правила](../../rules/equipment.md#исполняемая-pc-граница-m19), [контракт ADR-0074](../../decisions/ADR-0074-pc-two-handed-close-weapons.md). Staff/Sword/Dagger/Axe/Warhammer/Morning Star сохраняются.

В нынешнем PC JSON1 у этих семи видов `party[].initial_weapon_hand` обязательно равен `both`; у одноручных допустимы только `left`/`right`. Новых полей/метрик/версии нет. Минимальный фрагмент участника:

```json
{
  "pc": {"weapon": "greataxe"},
  "initial_weapon_hand": "both"
}
```

Это фрагмент: остальные поля definition и участника остаются обязательными. Двуручный хват не является третьей анатомической стороной. Drop любой руки роняет весь предмет; Recover восстанавливает хват обеими. Использование разбитой руки12 вызывает Critical. После полной обработки ран16/18/20, лишающих возможности2H применения, trial останавливается как UNSUPPORTED_PATH, сохраняя actual prefix. Near Miss сначала может отменить рану; обязательный drop при16/20 или дальнейшее удержание одной рукой не выдумываются.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m19/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m19/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [actual CLI result](pc-melee-simulation.result.json) показывают четырёх PC с Greataxe/Greathammer/Flail/Glaive против одного armoured Minion и одного armoured Brute. Индивидуальные Glorious/Near Miss policies и роль ally Recover фиксированы. Seed42,6trials,budget5rounds:6objective wins,40actions,11started/5completed rounds,17Glorious spends. Потери, Near Miss, Help и actual ally Recover actions равны0. Это лёгкий пример применения каталога; наличие policy не гарантирует её активацию.

[Balance request](pc-melee-balance.request.json) и [actual CLI result](pc-melee-balance.result.json) намеренно используют **другую party**: слабого PC с Pickaxe и отказом от optional Fate против1–3сильных Minions. Это авторские числовые профили, не бестиарий. По4trials,общийbudget12trials:

| Minions | Objective | Party defeated | Round limit | Unsupported | Actions |
|---|---|---|---|---|---|
| 1 | 0 | 3 | 1 | 0 | 28 |
| 2 | 0 | 1 | 0 | 3 | 20 |
| 3 | 0 | 1 | 0 | 3 | 16 |

Кандидаты с actual unsupported исключаются из выбора, а их trials остаются в знаменателе. Нулевой objective rate сам по себе не делает кандидата unsupported. Поиск меняет только число NPC, сохраняя PC/оружие/хват/Fate/стратегию и полный request echo; balance не хранит journal.

Результаты малой выборки не являются оценкой истинной вероятности или оптимальной тактикой. Greatsword, запасное оружие/переключение, dual wield, другие ranges, mounts и внебоевые Traits не подключены.
