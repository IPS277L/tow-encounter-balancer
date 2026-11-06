# M35: Cultist, Elf Militia и Ungor

В M35 три новых книжных Minions расширили каталог до28loadouts. Актуальная граница — в [статусе](../../project-status.md). [Нормализованное правило и источники](../../rules/npc-profile-catalog.md#minion-chunk-m35).

| Профиль | Выбранная атака | Protection | Resilience/gear |
|---|---|---|---|
| Sigmarite Cultist | Warhammer Close3d/3 Damage3,1H | Athletics3d/2 | T3/Res3,без щита |
| Elf Militia | Spear maximum Short4d/3 Damage4,2H | Athletics4d/3 | T3/Res4 armoured,без щита |
| Ungor | Crude Spear Close–Short3d/3 Damage3,1H | Athletics4d/2 | T3/Res4 armoured,щит уже включён |

Вся сцена остаётся Close. Printed NPC Damage сохраняется без дополнительных PC weapon Traits. Longbow Elf и Shortbow Ungor не выбраны. Martial Prowess Elf требует другого Elf в той же Zone **вне Close Range врага**; в данной all-Close/noMove сцене условие не достигается. Child of the Forest Ungor не применяется без woodland terrain/движения. Полные условия способностей сохранены в metadata.

Ungor получает один обычный+1d против фактической Staggered цели. Собственный Staggered и состояние другого PC не дают этот бонус. Он подчиняется общему cap и Drained; после Wound, снявшей Staggered цели, следующая атака пересчитывается без него.

Cultist использует действующий no-Test Help: standard action, отдельный+1d сверх cap и обычный TurnEnd. Current PC JSON1 не получает новых полей/версии/метрик. В примере:

```json
"npc_help_policies": [
  {"helper_id": "cultist1", "beneficiary_id": "ungor1"}
]
```

PC со Staff сначала атакует Ungor, затем Elf, затем Cultist. Активации NPC: Cultist → Elf → Ungor. Если Ungor уже defeated или не может принять помощь, Cultist атакует сам; другого получателя не выбирает. Пустой список сохраняет Attack. Остальные guards/Drained fallback/exact-Test binding/расходы прежние.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m35/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m35/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): один PC против одного NPC каждого профиля, seed42/6trials/budget5rounds, optional Fate declined. Получены1objective/4party defeated/1round limit/0unsupported,62actions,24started/20completed rounds. Cultist выполнил7Help в4trials; Elf/Ungor Help counts0. PC Help/ally Recover/Fate/NPC exit counters0.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json):1–2Cultists,0–1Elf,0–1Ungor,8составов по2trials. Все Cultists настроены помогать Ungor. При его исключении пары удаляются, Cultists переходят к Attack без переназначения; source order/приоритеты фильтруются по retained IDs.

| Cultists | Elf | Ungor | Objective | Party defeated | Limit | Actions | NPC Help |
|---|---|---|---|---|---|---|---|
| 1 | 0 | 0 | 2 | 0 | 0 | 2 | 0 |
| 1 | 0 | 1 | 2 | 0 | 0 | 6 | 0 |
| 1 | 1 | 0 | 1 | 0 | 1 | 14 | 0 |
| 1 | 1 | 1 | 0 | 1 | 1 | 17 | 0 |
| 2 | 0 | 0 | 2 | 0 | 0 | 8 | 0 |
| 2 | 0 | 1 | 2 | 0 | 0 | 12 | 0 |
| 2 | 1 | 0 | 1 | 1 | 0 | 17 | 0 |
| 2 | 1 | 1 | 0 | 2 | 0 | 19 | 0 |

Unsupported везде0; при top_k2 выбраны1/1/0 и2/1/0. В этой малой balance выборке реальной Help не произошло: пары не гарантируют действие после предыдущих ходов/поражения получателя. Это наблюдение конкретных seeds, не оценка истинной вероятности, оптимальной стратегии или преимущества Help над Attack. Simulation выше содержит реальные Help actions; детерминированные тесты отдельно проверяют бонус и его источник. Прежние25entries и104JSON documents M9–M34 сохраняются без изменений.
