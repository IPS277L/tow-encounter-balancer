# M15: помощь намеченной атаке PC

Первый Help-срез задаёт физическую помощь с Melee Test союзнику, чей ход ещё впереди в текущем раунде. Он использует настоящее действие помощника и существующие правила Fate/ран. [Контракт и ограничения](../../decisions/ADR-0071-pc-melee-help-policy.md).

Фрагмент помощника в текущем PC JSON1:

```json
{
  "actor_id": "pc",
  "policy": "help_ally_or_attack_or_recover_self",
  "help_policy": {
    "beneficiary_id": "pc:companion",
    "target": "melee_attack",
    "protection_skill": null
  }
}
```

Получатель должен быть другим PC этой party, с `policy: attack_or_recover_self`, обязательным `help_policy: null` и более поздним местом в `pc_activation_order`. Несколько помощников могут выбрать его; помощь другим помощникам пока не поддержана. Это фрагмент, остальные поля участника остаются обязательными.

PC сначала выполняет прежний self Recover, если он нужен. Иначе помогает доступному союзнику либо возвращается к Attack. Deafened запрещает Help; Defenceless не действует. Для Help используется пригодное оружие/рука; получателю нужно быть готовым к Attack, живым, без Defenceless/Drained и ещё не завершившим ход. Это ограниченная стратегия, а не общий AI или полный набор допустимых книжных вариантов.

Каждый успех Help даёт +1d на точный Attack Test получателя в этом раунде. Pool cap сохраняется. Неудача расходует действие с нулевым бонусом и не вызывает последствие промаха Attack. Помощник и получатель могут независимо применять свои Glorious policies. Если намеченный Test не происходит, бонус не переносится: например, другой PC может раньше победить последнего врага. Ходы всех PC по-прежнему предшествуют NPC.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m15/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m15/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) использует профили/состав и seeds/trials [M14](../m14/README.md), меняя роль первого PC на помощника companion. [Фактический result](pc-melee-simulation.result.json):12trials,5objective/0party_defeated/7round_limit/0unsupported;38Help actions во всех12боях,33Glorious spends и11Near Miss burns. Companion подтверждённо погиб в6боях; первый PC — ни разу.

[Balance request](pc-melee-balance.request.json) выбирает0–2Minions плюс1Brute, по8trials на состав. В [result](pc-melee-balance.result.json) победы8/6/3 из8; Help actions28/40/24, Glorious spends22/23/22, Near Miss burns1/4/8 соответственно. Это наблюдения фиксированной тактики, а не обещание её преимущества или оценка оптимального выбора Help/Attack.

`help_action_counts` содержит всех PC в исходном порядке; `help_action_trial_count` — число боёв хотя бы с одним Help; `total_help_action_count` — суммарные действия помощи. Сюда входят неудачные и неиспользованные Help. Эти числа не равны бонусным кубам: бонус может быть нулевым, ограниченным cap или остаться неприменённым. Подбор фиксирует роли/политики, ранжирует по прежней objective rate и сохраняет отдельную стоимость Fate.

Остальные примеры M9–M14 используют `help_policy: null` и нулевые Help counters, сохраняя свои результаты. Версия family остаётся1; пропущенное поле не поддерживается. Текущий [M16 контракт](../m16/README.md) требует также явные target/protection_skill и поддерживает отдельный Protection Help; здесь они равны melee_attack/null и результаты сохранены. Другие Skills/GM approval, Help chains и оптимальная тактика остаются будущими темами.
