# M57: Orc Boy и Big ’Un против Pistol

Четыре существующих loadouts получили явную Melee/Athletics Protection против Close Shooting: Orc Boy Choppas/Spear и Big ’Un Choppas/Spear без щитов. Это продолжение [контракта M56](../../decisions/ADR-0101-pc-close-shooting-npc-protection-choice.md) без новых полей/Skills/version; обычная Defence от Melee сохраняется. [Основное правило](../../rules/combat.md#pc-close-shooting-protection-m57).

У всех Melee3d/4/cap6 и Athletics3d/3/cap6. Big ’Un наследует WS3/Ag3 от Orc Boy; его Strength4 даёт+1Damage и Brute W1Drained/W2defeat, не defensive4dice/cap8. Щиты не добавляются: это прежние no-shield loadouts.

В нынешнем PC JSON1 используются те же actor policies:

```json
"npc_close_shooting_protection_policies": [
  {"actor_id": "orc1", "skill": "melee"},
  {"actor_id": "unshielded_orc1", "skill": "athletics"},
  {"actor_id": "big_un1", "skill": "melee"},
  {"actor_id": "unshielded_big_un1", "skill": "athletics"}
]
```

Source остаётся полным и canonical, без arbitrary dice/threshold/cap. Включая M56, policy допускает8loadouts при каталоге57. Отсутствие/closed nonempty list/полный template admission/actor filtering сохраняются,192прежнихJSON не мигрируются.

Пример также задаёт две существующие пары Help: Orc Choppas→Big ’Un Choppas и Orc Spear→Big ’Un Spear, с helpers раньше recipients в NPC order. Power of the Waaagh! даёт free success только назначенному Melee Attack Test. Защитный Melee не получает этот бонус; snapshot не переносится и не расходуется на defence. При исключении любого endpoint пара удаляется по прежней generation policy. Charge+1Damage и PC weapon Traits не добавляются к opposition.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m57/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m57/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): mixed party Pistol+Shield/Sword+Shield с authored armour_bonus1 у обоих против всех4NPC; seed42,6trials,8rounds. Получены1objective/2party defeated/2limit/1unsupported,156actions,40started/36completed rounds;5trials с поражением хотя бы одного PC.

Native разбор trial3 подтвердил старую границу M54: третья рана PC1 даёт W18/clutch stomach, а фактически необходимый Reload требует вторую свободную руку. Stop — pistol_reload_hands_unavailable, не отказ новой NPC Protection; costs/losses сохраняются по prefix.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json): оба Orc Boy фиксированы по одному, каждый Big ’Un — по0–1; четыре однородные count groups,4состава по2trials.

| Big ’Un Choppas | Big ’Un Spear | Objective | Party defeated | Limit | Unsupported | Actions |
|---|---|---|---|---|---|---|
| 0 | 0 | 2 | 0 | 0 | 0 | 10 |
| 0 | 1 | 2 | 0 | 0 | 0 | 39 |
| 1 | 0 | 1 | 0 | 0 | 1 | 38 |
| 1 | 1 | 1 | 0 | 1 | 0 | 60 |

Для состава(1,1,1,0) native trial0 остановился на прежнем M54 Reload boundary после W3/table16/unusable arm. Unsupported остаётся в знаменателе; это не приписывается победе/поражению. Малая выборка показывает интерфейс и выбранную тактику, а не истинные вероятности или оптимальный состав.
