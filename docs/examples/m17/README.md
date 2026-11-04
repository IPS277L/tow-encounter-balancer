# M17: стандартный Recover союзнику

Явная роль позволяет снять допустимые Staggered/Prone выбранного PC, сохраняя собственный обязательный Recover и другие преимущества действия. Это не лечение ран и не общий AI. [Контракт и источники](../../decisions/ADR-0073-pc-ally-standard-recover.md).

Фрагмент участника текущего PC JSON1:

```json
{
  "policy": "recover_ally_or_attack_or_recover_self",
  "help_policy": null,
  "ally_recover_policy": {"beneficiary_id": "pc:companion"}
}
```

Остальные поля участника остаются обязательными. У прежних ролей `ally_recover_policy: null`; новый role требует другой PC этой party, без ограничения порядка/роли получателя. Он может действовать раньше или позже помощника.

Если actor должен подняться из removable Prone или вернуть оружие, Recover сохраняет приоритет собственных Conditions; свободный Staggered/Prone benefit можно направить союзнику. Иначе при подходящем союзнике выбирается Recover с приоритетом ally по каждому benefit, затем self. Собственный pickup остаётся в том же действии. При dead/неподходящем получателе действует прежняя Attack/Recover.

Оngoing Staggered15/19 и Prone17 не снимаются. Подъём при ране13 даёт Critical самому поднятому PC; получение помощи не считается его действием и не запускает W14/W15. Actor получает свои обычные Recover/hand/heavy/end-phase последствия. Ничего не воскрешается, Defenceless/Critical и раны не лечатся. Standard Recover не делает Test и не тратит Fate; отдельный Critical Test в конце собственного хода остаётся настоящим Test.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m17/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m17/pc-melee-balance.request.json
```

[Simulation request](pc-melee-simulation.request.json) сохраняет состав/профили и seeds/trials [M16](../m16/README.md), меняя роль первого PC. [Фактический result](pc-melee-simulation.result.json):12trials,5objective/0party_defeated/7round_limit/0unsupported;24действия Recover с изменением союзных Conditions в10боях,32Glorious spends и13Near Miss burns. Companion подтверждённо погиб в7боях; первый PC — ни разу.

[Balance request](pc-melee-balance.request.json) выбирает0–2Minions плюс1Brute, по8trials. В [result](pc-melee-balance.result.json) победы8/7/3 из8; ally Recover actions8/17/16, Glorious spends15/21/23, Near Miss burns1/4/10. Это наблюдения фиксированной стратегии, не фиксированные вероятности или доказательство её преимущества.

`ally_recover_action_counts` покрывает всю party в исходном порядке; `ally_recover_action_trial_count` считает бои хотя бы с одним actual allied change, `total_ally_recover_action_count` — действия. Mixed self/ally или снятие двух Conditions считается один раз; self-only Recover не входит. Эти counters не равны числу вылеченных ран или чистому улучшению здоровья: подъём при13 имеет риск. Help и Fate показаны отдельно; роль/получатель фиксируются при подборе NPC.

Все M9–M16 примеры мигрированы с null и нулевыми новыми counters, сохраняя прежние игровые результаты. Версия PC family остаётся1, пропуск нового поля не поддерживается. Alternative treatment/Condition Tests, ally pickup/mounting, кампания и optimal AI остаются за границей M17.
