# M24: выход Broken Official

Official после первой раны получает Broken. В этом примере явно подтверждён свободный самый быстрый путь в соседнюю безопасную Zone. В свой ход NPC выполняет free movement и покидает encounter, сохраняя W1/Broken и `defeated=false`. [Правило](../../rules/npc-profile-catalog.md#official-exit-m24), [ADR-0079](../../decisions/ADR-0079-pc-broken-npc-adjacent-exit.md).

Текущий PC JSON1 требует поле scenario/template:

```json
"npc_broken_exit_policy": {
  "destination_zone_id": "safe-exit",
  "path_clear_confirmed": true,
  "fastest_route_confirmed": true
}
```

`facts.can_leave_zone` должен быть `true`, destination отличается от arena. Подтверждения означают отсутствие блокирующих врагов, препятствий и сложного рельефа на единственном переходе. Все PC остаются в arena; внешних участников нет. Вторая рана до собственного хода по-прежнему побеждает Official. Политика `null` сохраняет остановку M23 перед его бегством.

Цель выбрана пользователем: все NPC побеждены или ушли. Уход не становится defeat, standard action или потерей PC. Преследование, возврат и Recover после ухода не моделируются. Summary требует `npc_exit_counts` для всех NPC в порядке source, включая нули; `npc_exit_trial_count`, `total_npc_exit_count` и `objective_with_npc_exit_count`. Последнее — число успешных trials с хотя бы одним уходом; число успехов без ухода равно objective_achieved минус эта величина. Частичный уход может предшествовать иному исходу.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m24/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m24/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [actual CLI result](pc-melee-simulation.result.json): два PC со Staff против Official Dagger и Footpad, seed42,6trials,budget5rounds, optional Fate declined. Получены6objective/0party defeat/0limit/0unsupported, без потерь PC;26standard actions,12started/6completed rounds. В3trials Official ушёл, Footpad уходов не имеет;3победы с уходом и3без ухода. Free movement не добавлен к action count.

[Balance request](pc-melee-balance.request.json) и [actual CLI result](pc-melee-balance.result.json): fixed party/exit policy,1–2Officials и0–1Footpad, по3trials:

| Officials | Footpad | Objective | Trials с уходом | Всего уходов | Actions |
|---|---|---|---|---|---|
| 1 | 0 | 3 | 2 | 2 | 6 |
| 1 | 1 | 3 | 2 | 2 | 14 |
| 2 | 0 | 3 | 2 | 2 | 15 |
| 2 | 1 | 3 | 2 | 4 | 24 |

Все прочие outcome counts нулевые. При top_k=2 выбраны составы1Official/0Footpad и1Official/1Footpad. Это наблюдения маленькой воспроизводимой выборки, не истинная вероятность или найденная оптимальная сложность. Балансировщик сохраняет отдельные exit aggregates каждого состава без native journal.

Прежние30пар M9–M23 обновлены только обязательной `null` policy и нулевыми exit fields; прежние числа и остальные значения сохранены. Другие wire families и версия PC JSON1 не менялись.
