# M20: запасное одноручное оружие

Двуручный primary может сопровождаться явно заданным1H backup. PC выхватывает его в собственный ход после потери возможности2H применения, сохраняя книжные Wounds/Help/Fate/Recover. [Контракт ADR-0075](../../decisions/ADR-0075-pc-backup-weapon-policy.md), [правила](../../rules/equipment.md#исполняемая-pc-граница-m20).

Текущий PC JSON1 требует у каждого участника `backup_weapon_policy`: null либо

```json
{
  "weapon": "sword",
  "preferred_hand": "right"
}
```

Допустимы `staff`, `sword`, `dagger`, `axe`, `warhammer`, `morning_star`; preferred_hand — только `left`/`right`. Non-null требует2H primary и Strength≥2 для двух carried weapons. У остальных участников задаётся null; пропущенное поле отклоняется. Все прежние примеры обновлены null без изменения их gameplay/counters, wire version и метрики сохраняются.

Fixed strategy не переключает оружие ради более выгодного Trait или просто потому, что primary выпал. При actual недоступном2H хвате configured backup с одной пригодной рукой позволяет продолжить до своего хода. До draw защита — Athletics. Живой не-Defenceless PC до standard action оставляет primary и выхватывает backup; здоровая пригодная рука предпочтительнее травмированной. Incidental draw не расходует standard slot, но вызывает положенные Critical12/14/15. Clutch18 сохраняется, Defenceless20 не может draw.

После переключения применяются Damage/Traits/Defence/Help запасного оружия; после его drop Recover подбирает именно backup. Возврата primary/dual wield/off-turn draw нет. При отсутствии policy действует M19-stop; если до draw не осталось пригодных рук, сохраняется точный actual unsupported. Переключение не гарантирует выживание.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m20/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m20/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [actual CLI result](pc-melee-simulation.result.json): свежий слабый PC с Pickaxe, Strength2 и запасным Sword против трёх сильных Minions; все числовые профили авторские, не бестиарий. Decline optional Fate, seed42,6trials,budget4rounds:0objective wins,5party defeats,1unsupported,33standard actions,11started/5completed rounds. Draw не считается standard action и не получает отдельного aggregate counter. Нативные тесты отдельно подтверждают реальные draw/continuation proofs.

[Balance request](pc-melee-balance.request.json) и [actual CLI result](pc-melee-balance.result.json) фиксируют ту же party и меняют только1–3Minions, по4trials на кандидата:

| Minions | Objective | Party defeated | Round limit | Unsupported | Actions |
|---|---|---|---|---|---|
| 1 | 0 | 3 | 1 | 0 | 28 |
| 2 | 0 | 4 | 0 | 0 | 22 |
| 3 | 0 | 3 | 0 | 1 | 23 |

Unsupported trials входят в знаменатель и исключают третьего кандидата из выбора. Нулевой objective rate сам по себе не является unsupported; равенство первых двух разрешается прежним стабильным порядком. Полные primary/backup/policy/Fate остаются в root request и candidate sources. Balance не хранит журнал боя.

Эти малые наблюдения показывают контракт и границу продолжения, а не вероятность победы, пользу запасного оружия или оптимальную тактику. General inventory, смена по желанию, запасное2H, Brawn, другие ranges и Greatsword остаются за границей.
