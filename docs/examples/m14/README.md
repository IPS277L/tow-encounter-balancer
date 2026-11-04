# M14: Glorious Test вместе с Near Miss

PC может расходовать Fate на выбранные Tests и отдельно сжигать его для отмены ран. Каждая стратегия задаётся явно; резерв обычных трат и постоянный rating — разные величины. [Полный контракт](../../decisions/ADR-0070-pc-glorious-test-policy.md).

Текущий [M15 контракт](../m15/README.md) также требует `help_policy`; в этих Fate-only примерах оно равно null, Help counters нулевые, прежние игровые результаты сохранены.

Фрагмент участника текущего PC JSON1:

```json
{
  "fate_policy": "configured",
  "near_miss_policy": {
    "minimum_table_total": 14,
    "minimum_rating_to_keep": 1
  },
  "glorious_policy": {
    "skills": ["melee", "defence", "athletics", "endurance"],
    "maximum_initial_successes": 1,
    "minimum_remaining_spends": 1
  }
}
```

После собственного начального броска выбранного навыка PC тратит Fate при0–1успехах, если остаётся больше1обычной траты и есть смысл применить Glorious. На обычном Test перебрасываются все неудачные кубы один раз; на Grim при наличии успехов Glorious отменяет обязательные перебросы. Результат противника не влияет на выбор. При обычном броске без неудач или Grim без успехов ресурс не тратится. Это параметры конкретной стратегии, не оптимальный AI и не новые правила книги.

`near_miss_policy` можно сделать null и оставить только Glorious; `glorious_policy: null` оставляет только Near Miss. Для полного отказа нужны `fate_policy: decline_optional_fate` и обе null. Оба поля обязательны. Старое имя `near_miss_at_threshold` удалено; версия family остаётся1.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m14/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m14/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) использует боевые профили/состав и seeds/trials группы [M13](../m13/README.md), добавляя Glorious policy. [Фактический result](pc-melee-simulation.result.json):12trials,7objective/0party_defeated/5round_limit/0unsupported;32обычных Glorious spends во всех12боях и12Near Miss burns в10боях. По персонажам: `pc`20spends/2burns, companion12spends/10burns;6боёв с подтверждённой смертью companion. Победа группы не означает отсутствие потерь.

[Balance request](pc-melee-balance.request.json) выбирает0–2Minions плюс1Brute, по8trials. В [result](pc-melee-balance.result.json) победы8/7/4 из8; Glorious spends17/22/22 и Near Miss burns1/4/10 соответственно. Ранжирование по-прежнему использует objective rate, без отдельной цели минимизировать расход Fate.

Отчёт добавляет `glorious_spend_counts` для всей party в исходном порядке, `glorious_spend_trial_count` для боёв хотя бы с одной новой тратой и `total_glorious_spend_count`. Near Miss counters остаются отдельными. Supplied предыдущие траты не учитываются заново; каждый trial начинает с того же initial Fate, без автоматического refresh. В остановленном/лимитированном бою учитываются только фактически исполненные расходы и потери.

После обычных трат Near Miss всё ещё доступен при положительном rating. Последующий burn может уменьшить оставшуюся session allowance ниже резерва Glorious; этот резерв ограничивает только выбор обычной траты. Примеры дают наблюдения конкретных seeds/trials/policies, а не фиксированные вероятности или доказательство улучшения стратегии. Перебросы меняют дальнейшее потребление RNG, поэтому одинаковый seed двух policies не гарантирует одинаковые последующие кубы.
