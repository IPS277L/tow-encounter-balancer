# M39: Bear и вторая атака другого PC

Bear / Sweeping Claws использует natural Close4d/3 Damage5, Athletics3d/3, Brute3/T5/Res6 armoured/noShield. W1–2 дают Drained, W3 defeats. [Правило](../../rules/npc-profile-catalog.md#bear-second-attack-m39), [принятый контракт](../../decisions/ADR-0087-pc-bear-second-attack-policy.md). Каталог содержит36боевых loadouts.

Enduring Strength после успешной первой Attack разрешает второе действие против другого врага. Успех не требует раны; Near Miss не отменяет попадание. Сначала исполняются все последствия первого удара, затем Bear выбирает другого живого PC по существующему `enemy_target_priority`. Живой Defenceless PC подходит; погибшая первая цель сохраняется как исключённый адресат. Без другой живой цели второго slot/действия/броска нет.

В текущем PC JSON1 обязательна явная настройка:

```json
"npc_extra_attack_actor_ids": ["bear1"]
```

Можно включить только canonical Bear/Sweeping Claws actors. Пустой список `[]` явно отказывается от optional второй атаки; отсутствие поля ошибочно. Это выбранная тактика сценария, а не требование книги всегда использовать способность. Count search удаляет IDs исключённых Bears, не переназначает их.

Оба удара исполняются как реальные Attack в slots1/2 с разными Test/receipt IDs. Help конкретного первого Test не переносится. Один TurnEnd следует после обеих атак; третьего действия нет. Второй удар входит в общий action count и отдельно отражается в `npc_extra_attack_counts`; summary также содержит `npc_extra_attack_trial_count` и `total_npc_extra_attack_count`. Source-ordered counts включают нули для остальных NPC.

Примеры используют два PC с Axe, Bear(s) → White Wolf/Clamping Jaws, optional Fate declined и пустые Help pairs. Crushing Weight Bear, Charge, mounted и Fearsome при Give Ground не выбираются fixed Close/SUFFER_WOUND сценой. Второй удар White Wolf не предоставляется.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m39/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m39/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) и [фактический CLI result](pc-melee-simulation.result.json): один Bear и один White Wolf, seed42/6trials/budget5rounds. Получены0objective/1party defeated/5limit/0unsupported,110actions,30started/29completed rounds. **11вторых атак в5trials** входят в110actions; White Wolf extra count0. PC1defeated5/PC2defeated1, остальные Fate/Help/ally Recover/NPC exit counters0.

[Balance request](pc-melee-balance.request.json) и [фактический CLI result](pc-melee-balance.result.json):1–2Bears,0–1White Wolf, четыре состава по2trials.

| Bears | White Wolves | Objective | Party defeated | Limit | Actions | Вторые Attack | Trials со второй Attack |
|---|---|---|---|---|---|---|---|
| 1 | 0 | 2 | 0 | 0 | 15 | 1 | 1 |
| 1 | 1 | 0 | 1 | 1 | 35 | 4 | 2 |
| 2 | 0 | 0 | 0 | 2 | 40 | 9 | 2 |
| 2 | 1 | 0 | 1 | 1 | 46 | 7 | 2 |

Unsupported везде0; при top_k2 выбраны1/0 и1/1. Малые выборки иллюстрируют работу интерфейса, а не истинную вероятность или оптимальную тактику. Limit остаётся отдельным исходом в общем знаменателе.

Current PC JSON1 обновлён без периода совместимости: прежние120JSON documents M9–M38 получают обязательные `[]`/нулевые метрики; остальные прежние значения и35старыхentries сохраняются.
