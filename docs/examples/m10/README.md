# M10: группа PC против Minions

Два немагических PC с самостоятельными профилями, Fate и оружием в одной Close Zone против authored numeric Minions. Историческая [граница ADR-0066](../../decisions/ADR-0066-pc-party-melee-encounter.md) расширена [M12](../m12/README.md): исполняются и тяжёлые раны11–23. Отдельный погибший PC не завершает бой живого товарища.

Из корня репозитория:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m10/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m10/pc-melee-balance.request.json
```

Те же команды доступны через `towr` после установки. Это обновлённый единственный PC JSON1: uniform `party` обязателен даже для одного PC; прежний одиночный формат не поддерживается. Magic JSON6 не меняется.

После [M11](../m11/README.md) каждый NPC definition обязательно содержит `injury_policy` и `wound_limit`. Здесь все противники — `minion` с лимитом1; прежний shape без этих полей отклоняется, игровых изменений этого примера нет.

В [simulation request](pc-melee-simulation.request.json) первый PC использует Sword, второй — Staff в правой руке, Toughness4/Endurance5 и независимый Fate2. У второго PC обратный порядок целей. Сначала полные ходы PC в `pc_activation_order`, затем Minions в `enemy_activation_order`; общий `enemy_target_priority` заставляет Minions сначала атаковать товарища, затем первого PC, пропуская погибшего. Seed42,16 независимых trials, до6раундов. Все Close/awareness/scene facts заданы явно; outnumbering пересчитывается для обеих сторон.

[Balance request](pc-melee-balance.request.json) фиксирует более устойчивую группу и перебирает1–3 supplied Minions. По16 trials на состав, общий бюджет48. Состав PC, их ресурсы, policies и обе PC-side очереди сохраняются; enemy priority/defeat decisions каждого PC фильтруются по выбранному subset. Главная метрика — победа группы; подтверждённые потери показываются отдельно, без скрытого дополнительного критерия selection.

Результат содержит полный request, четыре исхода и агрегаты действий/раундов. `party_defeated` — гибель всех PC после завершённых lifecycle, `objective_achieved` — defeat всех Minions. `any_pc_defeated_count` считает trials хотя бы с одной подтверждённой смертью, `pc_defeat_counts` содержит count для каждого PC в исходном порядке. При limit/unsupported это наблюдённые потери до остановки; дальнейшая судьба оставшихся неизвестна. Для вычисления доли каждого показателя denominator — все `summary.trials`, без исключения unsupported.

Сохранённые [simulation result](pc-melee-simulation.result.json) и [balance result](pc-melee-balance.result.json) получены реальными командами на указанном в них runtime. Наблюдения конкретного seed/trials не закрепляют игровые вероятности. Любое unsupported исключает кандидата из selection; отчёт сохраняет все оценённые составы.

Актуальные числа находятся в сохранённых result files. После M12 прежние heavy-gate остановки продолжаются по выбранной стратегии; исторические результаты M10 остаются в ADR-0066.

Политики `attack_or_recover_self`, `decline_optional_fate`, `d10_low_left_high_right` и `continue_fighting` задаются для каждого PC явно. Новые поля `random_side_policy`/`heavy_wound_policy` заменяют старый hand-only shape. Общие ограничения и строгий JSON/error контракт — в [одиночном примере](../m9/README.md); body/end-turn поведение — в M12. Помощь, активное Fate, лечение, общий campaign/inventory остаются вне среза.
