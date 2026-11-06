# M36: три копейных варианта

State Trooper/Spear, Orc Boy/Jagged Spear+shield и Big ’Un/Jagged Spear+shield дополняют прежние Halberd/Choppas loadouts. В M36 каталог достиг31боевого варианта; актуальный состав — в [статусе](../../project-status.md). [Правило и книжные источники](../../rules/npc-profile-catalog.md#spear-chunk-m36).

| Профиль | Атака в Close, maximum Short | Protection | Resilience/gear |
|---|---|---|---|
| State Trooper | Spear3d/3 Damage3,1H | Defence3d/4 | T3/Res4 armoured,без щита |
| Orc Boy | Jagged Spear3d/4 Damage3,1H | Defence3d/4 | T4/Res6 armoured,щит |
| Big ’Un | Jagged Spear3d/4 Damage4,1H | Defence3d/4 | T4/Res6 armoured,щит,Brute2 |

Shielded Res6 уже включает щит: дополнительный+1 не прибавляется. Big ’Un наследует Strength4/Damage+1, первую Wound→Drained и вторую→defeat. Положительные bonus dice Drained убирает, free successes сохраняет. Alternative Athletics3d/3 сохранена у всех карточек, в примере до боя выбран Defence. NPC Spears не получают PC Foot Spear Traits.

Все участники находятся в Close. Supporting Action требует enemy movement и подходящего союзника в adjacent Zone; движения и таких внешних участников нет. Jagged Spear+1Damage требует Charge; Charge не исполняется. Полные способности и unused weapons/варианты сохранены в metadata, не удалены из карточек.

Current PC JSON1/счётчики прежние. Orc настроен помогать более позднему Big ’Un:

```json
"npc_help_policies": [
  {"helper_id": "spear_orc1", "beneficiary_id": "spear_big_un1"}
]
```

Настоящая Help тратит standard action без Test/RNG и даёт один free success точной будущей attack. Она продолжается и при Drained Big ’Un согласно выбранной тактике. Сам Drained Big ’Un также может Help без Test, если назначен помощником. При недоступном получателе Orc атакует сам; новую цель помощи не выбирает. Если count search удаляет любой конец пары, mapping исчезает.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m36/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m36/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): один PC с Axe против одного NPC каждого варианта. PC сначала атакует Big ’Un, затем Trooper, затем Orc; активации NPC Trooper→Orc→Big ’Un. Seed42/6trials/budget5rounds, optional Fate declined. Получены0objective/6party defeated/0limit/0unsupported,71actions,19started/13completed rounds. Orc выполнил16Help во всех6trials; остальные NPC Help counts0. PC Help/ally Recover/Fate/NPC exit counters0.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json):1–2Troopers,0–1Orc,0–1Big ’Un,8составов по2trials. При отсутствии Big ’Un оставшийся Orc атакует; роль помощника не переназначается.

| Troopers | Orc | Big ’Un | Objective | Party defeated | Limit | Actions | NPC Help |
|---|---|---|---|---|---|---|---|
| 1 | 0 | 0 | 2 | 0 | 0 | 2 | 0 |
| 1 | 0 | 1 | 0 | 2 | 0 | 16 | 0 |
| 1 | 1 | 0 | 2 | 0 | 0 | 10 | 0 |
| 1 | 1 | 1 | 0 | 2 | 0 | 24 | 4 |
| 2 | 0 | 0 | 2 | 0 | 0 | 8 | 0 |
| 2 | 0 | 1 | 0 | 2 | 0 | 23 | 0 |
| 2 | 1 | 0 | 1 | 1 | 0 | 14 | 0 |
| 2 | 1 | 1 | 0 | 2 | 0 | 26 | 5 |

Unsupported везде0. При top_k2 выбраны2/1/0 и1/0/0. Это небольшие иллюстративные выборки, не истинные вероятности/найденная оптимальная тактика или доказательство преимущества Help над Attack. Прежние28entries и108JSON documents M9–M35 сохранены без изменений; новый wire format, ranged combat, Charge, mounted rules и NPC Recover не добавлялись.
