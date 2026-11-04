# M10: группа PC против Minions

Два немагических PC с самостоятельными профилями, Fate и оружием в одной Close Zone против authored numeric Minions. [Граница ADR-0066](../../decisions/ADR-0066-pc-party-melee-encounter.md) сохраняет Wounds1–10, lethal24+ после явного отказа Near Miss, self Recover и точный unsupported при11–23. Отдельный погибший PC не завершает бой живого товарища.

Из корня репозитория:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m10/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m10/pc-melee-balance.request.json
```

Те же команды доступны через `towr` после установки. Это обновлённый единственный PC JSON1: uniform `party` обязателен даже для одного PC; прежний одиночный формат не поддерживается. Magic JSON6 не меняется.

В [simulation request](pc-melee-simulation.request.json) первый PC использует Sword, второй — Staff в правой руке, Toughness4/Endurance5 и независимый Fate2. У второго PC обратный порядок целей. Сначала полные ходы PC в `pc_activation_order`, затем Minions в `enemy_activation_order`; общий `enemy_target_priority` заставляет Minions сначала атаковать товарища, затем первого PC, пропуская погибшего. Seed42,16 независимых trials, до6раундов. Все Close/awareness/scene facts заданы явно; outnumbering пересчитывается для обеих сторон.

[Balance request](pc-melee-balance.request.json) фиксирует более устойчивую группу и перебирает1–3 supplied Minions. По16 trials на состав, общий бюджет48. Состав PC, их ресурсы, policies и обе PC-side очереди сохраняются; enemy priority/defeat decisions каждого PC фильтруются по выбранному subset. Главная метрика — победа группы; подтверждённые потери показываются отдельно, без скрытого дополнительного критерия selection.

Результат содержит полный request, четыре исхода и агрегаты действий/раундов. `party_defeated` — гибель всех PC после завершённых lifecycle, `objective_achieved` — defeat всех Minions. `any_pc_defeated_count` считает trials хотя бы с одной подтверждённой смертью, `pc_defeat_counts` содержит count для каждого PC в исходном порядке. При limit/unsupported это наблюдённые потери до остановки; дальнейшая судьба оставшихся неизвестна. Для вычисления доли каждого показателя denominator — все `summary.trials`, без исключения unsupported.

Сохранённые [simulation result](pc-melee-simulation.result.json) и [balance result](pc-melee-balance.result.json) получены реальными командами на указанном в них runtime. Наблюдения конкретного seed/trials не закрепляют игровые вероятности. Любое unsupported исключает кандидата из selection; отчёт сохраняет все оценённые составы.

В сохранённом simulation наблюдаются14побед и2unsupported из16, подтверждённых смертей0. Balance даёт16побед из16для каждого из трёх составов; при равной дистанции от target выбираются counts1, затем2 по порядку кандидатов. Это конкретные наблюдения, а не подтверждение нулевого риска потерь или оптимальности стратегии.

Политики `attack_or_recover_self`, `decline_optional_fate`, `d10_low_left_high_right` задаются для каждого PC явно. Общие ограничения и строгий JSON/error контракт описаны в [одиночном примере](../m9/README.md). Помощь товарищам, активное Fate, лечение, другие NPC types, остальные оружие/Talents, campaign и save/resume не входят в M10.
