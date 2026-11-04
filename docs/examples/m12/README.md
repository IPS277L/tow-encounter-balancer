# M12: продолжение боя после тяжёлых PC-ран

Текущий PC melee исполняет последствия PC Wounds1–23 и существующий lethal24+ lifecycle в ограниченном бою со Staff/Sword против numeric Minions/Brutes. [Контракт ADR-0068](../../decisions/ADR-0068-pc-heavy-wound-continuation.md). Лечение, кампания и общий inventory не включены.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m12/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m12/pc-melee-balance.request.json
```

После установки доступны те же команды через `towr`. [Simulation request](pc-melee-simulation.request.json) сохраняет слабую группу/смешанный roster примера M11,12trials/seed42/6раундов. [Balance request](pc-melee-balance.request.json) фиксирует более устойчивую party и перебирает0–2Minions плюс обязательного Brute3Wounds,3состава ×8trials. Составы и числовые профили — [M11](../m11/README.md); меняется исполнение тяжёлых последствий.

У каждого PC обязательны `heavy_wound_policy: "continue_fighting"` и `random_side_policy: "d10_low_left_high_right"`. Текущий JSON1 не принимает прежнее `random_hand_policy` или отсутствие новой policy. Обновлены и одиночные/Minion-only примеры. Игрок продолжает Attack/Recover с книжными последствиями, предпочитает здоровую пригодную руку и прижимает живот свободной, когда это возможно. Руки, выпадение одного известного оружия и анатомические потери хранятся с источниками в журнале боя; это не campaign sheet.

Для clutch приоритет имеет уже прижимающая либо свободная пригодная рука; это позволяет сохранить оружие в другой. Травмированная W12 рука остаётся пригодной, но её использование вызывает соответствующее Critical последствие. Непригодная/утраченная рука не выбирается; при вынужденной смене clutch можно уронить оружие, чтобы освободить оставшуюся руку.

Critically Injured вызывает одну Endurance Test в конце каждого собственного хода: провал даёт Defenceless, провал при уже имеющемся Defenceless — смерть. Endurance/Fate/next-Test Grim и expiry относятся к своему PC. Успех не лечит Condition. При Defenceless нет Attack/Recover/Opposition, но собственный ход с обязательной проверкой сохраняется. Успешный даже слабый удар наносит настоящую Wound без подмены Damage/Resilience. Defenceless не считается смертью и не входит в outnumbering; `party_defeated` означает гибель всех PC.

Выполняются Endurance и random последствия11/12/19, ограничения опасных действий12–15, непригодная/утраченная рука16/20, ongoing Prone17 и Staggered15/19, immediate clutch18 и последствия20–23. Оngoing Conditions нельзя стереть обычным Recover или новой Wound. Оружие используется/поднимается только пригодной рукой; незаявленный Brawn и лечение не подставляются.

Generic stop на тяжёлой строке убран. Если обязательной повторной анатомической потере уже не соответствует существующая цель — например, третья потеря руки после обеих утраченных — результат сохраняет actual pending `unavailable_anatomical_target`. Это требует решения GM и не заменяется случайной другой раной. Любой такой unsupported остаётся в denominator и исключает кандидата из selection.

[Simulation result](pc-melee-simulation.result.json) и [balance result](pc-melee-balance.result.json) получены реальными командами, сохраняют полный request и подтверждённые потери. Их числа — наблюдения заданных seeds/trials/policies, не фиксированные вероятности и не оценка оптимальной игры. Потери до limit/unsupported не предсказывают дальнейшую судьбу оставшихся PC.

В текущем simulation12trials дали4objective/6party_defeated/2round_limit, unsupported0;9trials содержат подтверждённые потери. До M12 этот же игровой вход останавливался12раз на тяжёлых ранах. В balance0,1 и1,1 дали8objective из8,2,1 —6objective/2round_limit; выбран сначала2,1, затем0,1 по target distance и стабильному порядку. Новые данные показывают результаты выбранной стратегии, а не «исправленную» вероятность старых stops.
