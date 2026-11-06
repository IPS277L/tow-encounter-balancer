# M33: явный NPC Help без броска

Этот пример использует Peasant и Free Company Militia: они могут потратить свой ход на физическую помощь конкретной более поздней Melee attack союзного NPC. Другие поддержанные помощники и free-success эффект добавлены в [M34](../m34/README.md). [Правило](../../rules/npc-profile-catalog.md#npc-help-m33), [ADR-0083](../../decisions/ADR-0083-pc-npc-automatic-help-policy.md).

В current PC JSON1 обязательно `npc_help_policies` в scenario/template и проецируемых candidate sources. Пустой список сохраняет прежнюю Attack-стратегию. Пример:

```json
"npc_help_policies": [
  {"helper_id": "peasant1", "beneficiary_id": "empire_knight1"},
  {"helper_id": "peasant2", "beneficiary_id": "empire_knight1"},
  {"helper_id": "militia1", "beneficiary_id": "empire_knight1"}
]
```

В Python каждую пару представляет `PcNpcHelpPolicy` из `towr.domain.pc_npc_help_models`; поле `PcMeleeScenario.npc_help_policies` обязательно, в том числе явный `()` для отказа. Helper — Peasant либо Militia, recipient — другой NPC с обычной Attack policy, стоящий позже в enemy activation order. Несколько помощников допустимы, повтор helper/self/chains/чужая сторона/неизвестные IDs отвергаются до RNG.

Каждая Help тратит настоящий standard action slot, но не делает Test и не расходует RNG/Fate. Она не вызывает Attack miss/Stagger и не снимает существующий Staggered. Каждый источник даёт ровно+1d, способный превысить обычный cap; cap остальных бонусов не снимается. После Help выполняется обычный TurnEnd. Native журнал хранит typed no-Test result и exact applications, без фиктивного TestResult.

Если recipient уже defeated/exited/завершил ход, Broken/Defenceless либо Drained, helper выбирает обычную Attack. Пропуск Drained — выбранная тактика: книга разрешает помощь, но положительный bonus не подействует. Собственный Staggered/Drained не блокирует no-Test Help; Deafened helper помогать не может. Физическая поддержка не требует, чтобы recipient слышал речь.

Источник адресован exact Test ID текущего раунда и применяется один раз. Неиспользованный receipt не переносится на другой Test/раунд/NPC. Поздний Drained filter удаляет и положительные bypass bonuses. При count search mapping сохраняется только при наличии **обоих** actors; оставшихся помощников не переназначают. В отсутствие recipient у retained helper снова ordinary Attack.

Summary содержит отдельные `npc_help_action_trial_count`, source-ordered `npc_help_action_counts` для всех NPC и `total_npc_help_action_count`. Прежние `help_action_counts` остаются PC-only. Общее число действий включает NPC Help; записи/агрегаты проверяют роли/round/trial/action budget и не хранят native journals. 96старых JSON documents получили только [] и нулевые NPC metrics; другие значения сохранены. Версия1/команды прежние.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m33/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m33/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): один PC со Staff против2Peasants/1Militia/1Empire Knight,Lance,noShield. Три helpers стоят до Knight и поддерживают его; PC сначала атакует Knight. Seed42,6trials,budget5rounds, optional Fate declined. Получены0objective/5party defeated/1round limit/0unsupported,128actions,28started/23completed rounds. Выполнены54NPC Help: по18каждым помощником, во всех6trials; Knight count0. PC Help/Recover ally/Fate/exit counters0.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json):1–2Peasants,0–1Militia,1Knight, по3trials на4состава. Порядок и named policy фильтруются по retained IDs.

| Peasants | Militia | Knight | Objective | Party defeated | Round limit | Actions | NPC Help |
|---|---|---|---|---|---|---|---|
| 1 | 0 | 1 | 1 | 1 | 1 | 39 | 7 |
| 1 | 1 | 1 | 0 | 3 | 0 | 42 | 16 |
| 2 | 0 | 1 | 0 | 3 | 0 | 44 | 16 |
| 2 | 1 | 1 | 0 | 2 | 1 | 67 | 21 |

Unsupported везде0. При top_k2 выбраны1/0/1 и1/1/1. Малые выборки не задают истинную вероятность/оптимум и не доказывают преимущество Help над теми же NPC с Attack. Сравнение стратегий требует одинаковых состава/условий и отдельного эксперимента. Limit/потери/расходы остаются в агрегатах и общем знаменателе.
