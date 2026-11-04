# M13: Near Miss в PC melee

Бой PC против Minions/Brutes умеет расходовать Fate для отмены ран. В каждом PC явно задаются стратегия и параметры; общего default или оптимального AI нет. [Граница и инварианты](../../decisions/ADR-0069-pc-near-miss-policy.md).

```json
"fate_policy": "configured",
"near_miss_policy": {
  "minimum_table_total": 14,
  "minimum_rating_to_keep": 1
},
"glorious_policy": null
```

Здесь после броска таблицы отменяются раны с total14+, пока rating больше1. Порог включителен, остаток не пересекается. Для отказа от всех опциональных применений указываются `fate_policy: decline_optional_fate` и обе обязательные конфигурации null. Текущий [контракт M14](../m14/README.md) использует `configured`; формат остаётся единственным PC JSON1. С добавленным `glorious_policy: null` прежние результаты этого примера сохранены.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m13/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m13/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) сохраняет боевые профили, состав и seeds/trials слабой группы [M12](../m12/README.md), меняя Fate policy. [Фактический result](pc-melee-simulation.result.json):12trials,7objective/0party_defeated/5round_limit/0unsupported. В10боях сожжено15Fate:5 у `pc` и10 у `pc:companion`;5боёв содержат подтверждённую смерть companion. Победа группы не означает отсутствие потерь. Это наблюдения конкретного входа, а не фиксированные вероятности или доказательство превосходства стратегии.

[Balance request](pc-melee-balance.request.json) фиксирует ту же party и выбирает0–2Minions плюс1Brute, по8trials на состав. В [result](pc-melee-balance.result.json) победы8/6/5 из8, новые burns2/2/10 соответственно. Выбраны2,1 и1,1 по прежней близости к target objective rate. Fate cost виден в summary, но пока не является отдельной целью ранжирования.

`near_miss_burn_counts` всегда покрывает полную party в исходном порядке. `near_miss_burn_trial_count` считает бои хотя бы с одним новым burn, `total_near_miss_burn_count` — весь новый расход. Предыдущие burns из supplied Fate history не входят; каждый trial начинает с того же начального ресурса, между trials ресурс не истощается.

Near Miss выбирается до регистрации/эффектов раны и может отменить lethal или анатомическую рану. Он сохраняет прежний Staggered и не увеличивает будущий Wounds Pool. Он не спасает от смерти при отдельном провале Critical Test без новой раны. Прочие Fate options, лечение и campaign остаются вне текущей границы.
