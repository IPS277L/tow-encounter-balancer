# M11: группа PC против Minions и Brutes

Текущие команды принимают смешанный reserve обычных числовых Melee NPC. Minion побеждается одной Wound; Brute накапливает раны до явно указанного профильного предела. Его ранение само по себе не исключает его из боя. [Контракт и граница ADR-0067](../../decisions/ADR-0067-pc-melee-profile-brutes.md).

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m towr simulate-pc-melee docs/examples/m11/pc-melee-simulation.request.json
.venv/Scripts/python.exe -m towr balance-pc-melee docs/examples/m11/pc-melee-balance.request.json
```

После установки доступны те же команды через `towr`. Вход — единственный текущий PC JSON1: каждый `enemies[].definition` обязательно содержит `injury_policy` (`minion` или `brute`) и положительный целочисленный `wound_limit`; для Minion только1. Формат без этих полей отклоняется. Примеры M9/M10 также обновлены. Другие families не изменяются.

[Simulation request](pc-melee-simulation.request.json) задаёт двух PC, двух Minions и одного authored Brute с лимитом3. Его обычная атака3d/5, Damage4, Defence3d/5, Resilience4+1; дополнительных Abilities, Traits или on-Wound изменений нет. Это числовой авторский профиль, не адаптированная запись конкретного существа из бестиария. Он действует первым среди NPC; PC выбирают его первой целью. Seed42,12 независимых trials, budget6раундов.

[Balance request](pc-melee-balance.request.json) использует более устойчивые профили PC и два отдельных composition groups: Minions0–2 и один обязательный Brute. Три состава по8trials, budget24, top_k2. Префиксы reserve и собственные приоритеты каждого PC сохраняются; definitions с разными policy/limit нельзя объединять в одну группу. Состав party и Fate не меняются.

Каждая NPC Wound хранит свой actual K1 result и обязательное подтверждение. Nonterminal Brute Wound не получает defeat disposition и не исключает actor; достигнув лимита, он получает заданное caller/GM решение, как Minion при defeat. NPC не бросают PLAYER Wounds Table и не пополняют PC daily histories. Живой Brute считается одним участником для outnumbering, независимо от числа уже полученных ран.

[Simulation result](pc-melee-simulation.result.json) и [balance result](pc-melee-balance.result.json) сохраняют полные actual requests, outcomes и потери. Значения относятся к конкретным seeds/policies/trials, не фиксируют вероятности игры. Любое observed unsupported остаётся в знаменателе и исключает кандидата из selection.

В simulation12из12прогонов остановились на тяжёлых PC-ранах; в одном prefix подтверждена смерть товарища. Эта выборка не даёт оценки победы и не считается12поражениями. В balance у состава без Minions наблюдаются8побед из8, и он выбран; у1Minion+Brute —6побед/2unsupported, у2Minions+Brute —2победы/6unsupported. Последние два состава исключены. Для более полной оценки трудных боёв потребуется расширить PC Wound continuations.

Поддерживаются только static numeric Brutes без реакции профиля на раны. Champions/Monstrosities, регенерация и специальные способности/атаки не следуют из появления Brute wound limit. PC остаются в границе [M10](../m10/README.md): Wounds1–10, lethal24+ после Near Miss decline, pending stop11–23, self Recover и явный optional Fate decline. Лимит ран NPC не применяется к PC.
