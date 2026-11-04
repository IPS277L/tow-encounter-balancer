# M16: Help для защиты союзника

Помощник заранее усиливает конкретный Protection Test союзника против первого ожидаемого живого NPC. Цель и навык задаются явно; общего бонуса на все атаки или optimal AI нет. [Контракт и границы](../../decisions/ADR-0072-pc-protection-help-policy.md).

Фрагмент помощника в текущем PC JSON1:

```json
{
  "policy": "help_ally_or_attack_or_recover_self",
  "help_policy": {
    "beneficiary_id": "pc:companion",
    "target": "first_incoming_protection",
    "protection_skill": "defence"
  }
}
```

Можно выбрать `athletics`. Помощник делает собственный Test того же навыка; получатель при выборе помощи должен использовать этот Skill для защиты. Для прежней помощи атаке нужны `target: melee_attack` и `protection_skill: null`. Все три поля ненулевой конфигурации обязательны; у обычного PC `help_policy: null`. Остальные поля участника в этом фрагменте опущены.

После приоритетного self Recover помощник смотрит на первого живого NPC в `enemy_activation_order` и текущую цель NPC по `enemy_target_priority`. Help даётся только если цель — выбранный союзник, он способен защищаться, не Drained и навык совпадает. Иначе действует прежняя Attack/Recover. Для Protection получатель может уже завершить свой PC turn; весь NPC-side всё ещё впереди. Роль, порядок и приоритеты задаёт вход.

Бонус +1d за успех привязан к Protection именно этого NPC в этом раунде, под обычным cap. Если NPC погиб до хода, бонус не переходит следующему. Если Recover вернул получателю оружие и Athletics сменился на Defence, бонус не заставляет использовать прежний Skill. Defenceless не делает Protection Test, поэтому не получает applications/Glorious window. Неиспользованный Help остаётся потраченным действием. Помощник и получатель могут независимо использовать собственные Glorious policies.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m16/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m16/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) сохраняет состав/профили и seeds/trials [M15](../m15/README.md), меняя только цель Help. [Фактический result](pc-melee-simulation.result.json):12trials,2objective/0party_defeated/10round_limit/0unsupported;42Help actions,32Glorious spends,13Near Miss burns. Companion подтверждённо погиб в5боях; первый PC — ни разу.

[Balance request](pc-melee-balance.request.json) выбирает0–2Minions плюс1Brute, по8trials. В [result](pc-melee-balance.result.json) победы6/3/1 из8; Help actions37/38/27, Glorious spends17/22/21, Near Miss burns1/2/9. Выбраны1,1 и0,1 по прежней близости к target objective rate.

Существующие `help_action_counts`, `help_action_trial_count`, `total_help_action_count` включают actual Help обоих типов, в том числе нулевой и unused; выбранный тип виден в request каждого PC. Это не число применённых кубов и не гарантия успешной защиты. Fate costs остаются отдельными. Подбор фиксирует Help policy и не назначает её автоматически при изменении числа NPC.

Примеры показывают наблюдения фиксированной тактики, а не доказательство её преимущества или оценку оптимального решения Help/Attack. Одинаковые seeds разных policies не гарантируют одинаковые последующие кубы. Полный произвольный выбор врага, другие Help Skills/GM approval и chains остаются за границей M16.
