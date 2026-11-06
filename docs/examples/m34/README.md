# M34: смешанная помощь гоблинов и орков

Goblin Warrior/Night Goblin помогают одним bonus die сверх cap; Orc Boy/Big ’Un — одним free success. Все четыре способности используют настоящий Help action без Test/RNG. [Правило](../../rules/npc-profile-catalog.md#greenskin-help-m34), [ADR-0084](../../decisions/ADR-0084-pc-greenskin-automatic-help.md).

Прежний current PC JSON1 не меняется. Тип эффекта следует из полной canonical definition помощника, его не нужно передавать отдельным полем:

```json
"npc_help_policies": [
  {"helper_id": "goblin1", "beneficiary_id": "big_un1"},
  {"helper_id": "night_goblin1", "beneficiary_id": "big_un1"},
  {"helper_id": "orc1", "beneficiary_id": "big_un1"}
]
```

В примере один PC со Staff против Warrior/Spear/shield, Night Goblin/Spear/shield, Orc Boy/Choppas/noShield и Big ’Un/Choppas/noShield. PC сначала атакует Big ’Un; активации NPC идут Goblin → Night Goblin → Orc → Big ’Un. Source order и NPC metrics сохраняют порядок Goblin/Night/Big ’Un/Orc. Несколько помощников поддерживают одного более позднего ordinary attacker; цепочки запрещены. Пустой список оставляет Attack.

Если первая рана делает Big ’Un Drained, гоблины переходят к Attack, а Orc продолжает Help: Drained запрещает бонусные кубы, но сохраняет free success. Это выбранная пользователем тактика. Сам Drained Big ’Un тоже способен Help без Test, если настроен помощником. Все остальные guards/exact Test binding/endpoint projection/метрики сохраняются из [M33](../m33/README.md). Help не является дополнительным действием или автоматическим попаданием; free successes прибавляются к итоговым успехам обычного броска.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m34/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m34/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): seed42,6trials,budget5rounds, optional Fate declined. Получены0objective/6party defeated/0limit/0unsupported,91actions,20started/14completed rounds. NPC Help43: Goblin13/Night13/Big ’Un0/Orc17, во всех6trials. PC Help/ally Recover/Fate/NPC exit counters0.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json): Goblin всегда1, остальные0–1;8составов по2trials. При отсутствии Big ’Un все пары удаляются, оставшиеся NPC атакуют без переназначения помощи.

| Goblin | Night | Big ’Un | Orc | Objective | Party defeated | Limit | Actions | NPC Help |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 | 0 | 0 | 2 | 0 | 0 | 4 | 0 |
| 1 | 0 | 0 | 1 | 1 | 1 | 0 | 21 | 0 |
| 1 | 0 | 1 | 0 | 0 | 1 | 1 | 22 | 2 |
| 1 | 0 | 1 | 1 | 0 | 2 | 0 | 28 | 13 |
| 1 | 1 | 0 | 0 | 2 | 0 | 0 | 17 | 0 |
| 1 | 1 | 0 | 1 | 1 | 1 | 0 | 24 | 0 |
| 1 | 1 | 1 | 0 | 0 | 1 | 1 | 31 | 12 |
| 1 | 1 | 1 | 1 | 0 | 2 | 0 | 28 | 13 |

Unsupported везде0. При top_k2 выбраны1/0/0/1 и1/1/0/1. Это небольшие иллюстративные выборки; они не задают истинную вероятность или оптимальную тактику и не доказывают преимущество Help над Attack. В M34 каталог не расширялся:25loadouts; новые карточки, Net, Charge, ranged combat и NPC Recover в этот срез не добавлялись. Все100прежнихJSON documents M9–M33 сохранены без изменений.
