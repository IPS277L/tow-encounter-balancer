# M29: Drained от попадания, Giant Spider и White Wolf

Чанк из двух существ и общего source-aware on-hit контракта. [Правило](../../rules/npc-profile-catalog.md#on-hit-drained-m29), [ADR-0081](../../decisions/ADR-0081-pc-on-hit-drained-and-independent-condition-sources.md).

| Profile ID | Атака / Protection | Профиль |
|---|---|---|
| GIANT_SPIDER | Poisonous Fangs3d/3 Damage3,natural,on-hit Drained / Athletics4d/3 | Fast Minion,T3Res3 |
| WHITE_WOLF_CLAMPING_JAWS | Clamping Jaws3d/4 Damage5,natural,запрет Give Ground / Athletics4d/4 | Fast Brute2,T5Res5,W1Drained/W2defeat |

```python
from towr.domain.pc_npc_catalog import PcBookNpcProfile, create_pc_book_npc

spider = create_pc_book_npc(PcBookNpcProfile.GIANT_SPIDER, "spider1")
wolf = create_pc_book_npc(PcBookNpcProfile.WHITE_WOLF_CLAMPING_JAWS, "white_wolf1")
```

Drained от Spider возникает при попадании, даже без раны и после отмены раны через Near Miss. Он не меняет уже выполненные Attack/Protection Tests, но влияет на последующие Tests. Каждое попадание сохраняет отдельный причинный источник, даже если PC уже Drained; Condition flag один и штраф не складывается. Истечение W6 снимает только источник раны. В native PC state причины доступны через `hit_condition_sources`; они не выдаются за фиктивные Wounds/deadlines и проверяются полным replay перед trials/агрегатами.

По выбору пользователя PC сохраняет Attack/обычный Recover. Обычный Recover Drained не снимает; книжный Endurance Test требует альтернативного Recover вместо стандартных преимуществ. Такой выбор/новая стратегия пока не добавлены. Название Poisonous не означает автоматически disease, заданную длительность или запрет восстановления. Результат боя — combat prefix, post-battle automatic Recover не моделируется.

White Wolf W1 накладывает Drained **самому Wolf**, не его жертве. Его own turn продолжается с подавлением bonus dice; W2 даёт defeat. Rending Claws unselected, Charge/Pin and Tear не выполняются, Fearsome от Give Ground не срабатывает при выбранных Clamping Jaws. Spider terrain/rider abilities сохранены inactive для неподвижной unmounted сцены.

В текущем PC JSON1 внутри `definition.attack` теперь обязателен `secondary_effects`. Для Spider:

```json
"secondary_effects": [
  {
    "kind": "condition_on_hit",
    "condition": "drained",
    "rule_id": "RULE-PROFILE-CREATURE-007:poisonous-fangs-drained",
    "classification": "unclassified"
  }
]
```

Для остальных текущих профилей — явный `[]`, включая White Wolf. Поддержано0–1такого descriptor, другие виды/Conditions/classifications отвергаются. Поле `hands` остаётся обязательным, natural атаки сохраняют null. Все прежние40request/result pairs M9–M28 мигрированы empty lists в input/echo/candidates с сохранением остальных значений; версия1/команды/метрики прежние. Другие bounded families не расширены.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m29/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m29/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [actual CLI result](pc-melee-simulation.result.json): два PC со Staff против1Spider/1White Wolf, seed42,6trials,budget5rounds; optional Fate declined/backup/exit policy null. PC сначала атакуют White Wolf, затем Spiders: это явный caller target_priority, позволяющий упражнять on-hit эффект, без изменения Attack/standard Recover стратегии. NPC activation/count order остаётся Spiders→White Wolf. Получены4objective/0party defeat/2limit/0unsupported; в2trials погиб pc1, pc2 не погиб.80actions,25started/21completed rounds, optional/support/exit counters0.

[Balance request](pc-melee-balance.request.json) и [actual CLI result](pc-melee-balance.result.json):1–2Spiders/0–1White Wolf, fixed party/policies/Wolf-first priority, по3trials на4состава:

| Spiders | White Wolf | Objective | Round limit | Other outcomes | Actions |
|---|---|---|---|---|---|
| 1 | 0 | 3 | 0 | 0 | 7 |
| 1 | 1 | 2 | 1 | 0 | 38 |
| 2 | 0 | 3 | 0 | 0 | 13 |
| 2 | 1 | 2 | 1 | 0 | 50 |

При top_k2 выбраны1Spider+1White Wolf и2Spiders+1White Wolf. Limit остаётся в знаменателе. Это малая воспроизводимая выборка при конкретной стратегии, не истинная вероятность/оптимум. Поиск фильтрует исходный target_priority по retained IDs и хранит прежние агрегаты без native journals.
