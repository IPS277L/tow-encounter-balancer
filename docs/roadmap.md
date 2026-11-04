# План разработки

Это очередь функций, а не журнал промежуточных шагов. Подробная [история этапов](roadmap-history.md) сохранена отдельно. Проверенные результаты и точка продолжения — в [статусе](project-status.md).

## Реализованная основа

- R1: разбор выбранных книг PG1.4/GM1.1, нормализованные правила и трассировка.
- K1: Test/Attack/Conditions/Wounds, магия и специализированные consumers; наличие consumer не означает интеграцию во все сценарии.
- M2–M7: ограниченные Minion-сценарии, независимые прогоны, подбор составов и JSON/CLI.
- M8: один Champion-Wizard/Curse, явные scene facts, opt-in continuations, native журнал, generation и текущий JSON6. Ограниченная веха завершена; [граница и приёмка](m8-completion.md).
- M9: один книжный PC/Staff или Sword против Minions, Wounds1–10, явный Fate decline, source-bound бой, trials, подбор численности и current JSON1/CLI. [Граница и приёмка ADR-0065](decisions/ADR-0065-first-pc-melee-encounter.md).
- M10: группа PC в общем owner/clock, отдельные ресурсы/раны, продолжение после частичных потерь, trials/статистика и fixed-party count search в той же PC JSON1 family. [Граница и приёмка ADR-0066](decisions/ADR-0066-pc-party-melee-encounter.md).
- M11: static numeric Brutes и mixed Minion/Brute reserve, source-bound profile Wounds до/на лимите, trials/подбор и явные policy/limit в текущем PC JSON1. [Граница и приёмка ADR-0067](decisions/ADR-0067-pc-melee-profile-brutes.md).
- M12: все PC Wounds11–23, body/hand consequences, Critical/Defenceless turns, source-aware ongoing Conditions и forced Wounds через тот же owner/trials/JSON1. [Граница и составная приёмка ADR-0068](decisions/ADR-0068-pc-heavy-wound-continuation.md).
- M13: явная Near Miss policy с порогом таблицы и резервом Fate; фактический burn в бою, независимые trials, расход ресурса в aggregate-only balance и текущем JSON1. [Контракт ADR-0069](decisions/ADR-0069-pc-near-miss-policy.md).
- M14: Glorious после actual initial roll для всех PC Test windows, отдельный session-spend резерв, совместимость с Near Miss в `configured`, новые costs в trials/balance и текущей JSON1. [Контракт ADR-0070](decisions/ADR-0070-pc-glorious-test-policy.md).

## Последняя законченная функция

[Glorious Test M14](decisions/ADR-0070-pc-glorious-test-policy.md) реализован через owner/trials/подбор и текущий JSON1, совместно с Near Miss. [Примеры](examples/m14/README.md) выполнены реальными командами; оба типа расхода каждого PC видны отдельно. Фактическая составная адресная приёмка — в статусе и ADR-0070; прежние full/wheel не повторяются автоматически.

## M8 завершена

Ограниченная M8 прошла финальную регрессию и проверку установленного пакета. [Checklist](m8-completion.md) хранит точный scope и фактические результаты. Все Wounds/Miscasts и полный каталог spells не требуются для её закрытия: точные unsupported stops входят в исходный контракт.

Нового обязательного consumer или повторной проверки для закрытия M8 нет. Следующим направлением пользователь выбрал PC-сценарий ниже.

<a id="next-milestone-proposal"></a>

## M9 — первый книжный PC-сценарий

Направление выбрано пользователем 2026-11-04: **один немагический персонаж игрока против numeric Minions**, от заданного боя до массовой оценки и подбора численности. M9 по [ADR-0065](decisions/ADR-0065-first-pc-melee-encounter.md) завершена, включая full source и installed delivery. Это первый книжный PC-срез вместо P1 `wound_limit`; нижеследующие критерии сохраняют конечную границу M9.

Основания в коде: [NpcDefinition](../src/towr/domain/npc_roster_models.py) допускает только Minion/Brute/Champion; [Melee scenario](../src/towr/domain/npc_melee_scenario_models.py) — только Minions. M9 добавила отдельную книжную PC orchestration с [TestProfile](../src/towr/domain/test_models.py), [PLAYER injury](../src/towr/domain/injury_models.py) и [Fate kernel](../src/towr/domain/fate_models.py). PC не подменяется Champion или `wound_limit` из P1.

Граница: готовый PC с явными Characteristics/Skills, Resilience и Staff/Sword, без генерации персонажа; один обычный Melee-вариант, одна Zone, явные Close/awareness/порядок/выбор целей, конечный round budget, немагические Minions без дополнительных Abilities. Пользователь дополнительно выбрал поддержку Wounds1–10; случайный hand/drop, восстановление собственного оружия и Prone через Recover, temporary expiry и next-Test Grim входят в функцию. Treatment, campaign, mounts, общий inventory, все Talents и произвольные тактики сюда не включаются. Обязательная явно выбранная стратегия `DECLINE_OPTIONAL_FATE` сохраняет ресурс и source-bound окна PC.

Выполненные конечные критерии:

1. Самостоятельный PC definition/state, книжные профили и PLAYER injury policy; общий battle owner содержит PC и NPC, сохраняя источники и однократность переходов. Решение о владельце состояния оформлено одним ADR, без массового переименования NPC API.
2. Один непрерывный бой исполняет обычные атаки обеих сторон, PC Wound lifecycle/обязательные решения и завершение ходов. Неподдержанный эффект сохраняет фактический prefix и явный stop; victory/defeat не подменяются лимитом ран P1.
3. Детерминированные примеры показывают PC win, PC defeat, round limit, unsupported, а также фактическую PC Wound с сохранением её эффекта. Если эти исходы нельзя честно получить в выбранной границе, scope пересматривается до реализации цикла.
4. Независимые trials с source/seed parity и агрегатами; unsupported остаётся в общем знаменателе и исключает кандидата из итогового подбора. Балансировщик меняет только численность заданного enemy Minion reserve.
5. Один текущий JSON/CLI контракт, runnable пример и адресная проверка нужных слоёв. Наличие отдельных K1 reducers не считается исполнением всех PC правил; полный regression/installed audit назначаются на границе этой вехи по рискам.

Контракт PC roster, решений/Fate, initial-state admission и поддержанных Wounds закреплён и реализован через нужные слои одной функцией. Обязательного остатка для закрытия M9 нет.

Меньшая альтернатива — **объяснение unsupported в действующем Magic-балансировщике**. [Одиночный результат](../src/towr/domain/npc_magic_step_models.py) уже содержит typed reason/phase и недостающие scene facts; [trial record](../src/towr/simulation/npc_magic_models.py) и [summary](../src/towr/simulation/npc_magic_summary_models.py) теряют эту причину. Конечный срез альтернативы: current6 simulation/balance report показывает counts по причинам и воспроизводимый пример trial index/seed для каждой; сумма равна unsupported total, sequential/process диагностика совпадает, полный journal в balance не передаётся, правила/исходы/selection не меняются. Это улучшает нынешний инструмент, но не добавляет PC.

Пользователь выбрал PC-сценарий; diagnostics остаётся самостоятельной возможностью дальнейшего backlog и не добавляется в M9 автоматически.

## M10 — бой группы PC против Minions

Пользователь поручил продолжить рекомендованное направление после M9. [ADR-0066](decisions/ADR-0066-pc-party-melee-encounter.md) закрепляет конечную границу: uniform roster PC, общий бой/clock, индивидуальные Fate/раны/оружие/expiry, явные порядки и приоритеты целей, dynamic outnumbering обеих сторон. Смерть отдельного PC не завершает бой оставшейся группы. Trials сохраняют подтверждённые потери по персонажам; подбор фиксирует всю party и меняет только Minion counts. Текущие PC JSON1/CLI обновляются без поддержки прежней одиночной формы.

Веха завершена и проверена; обязательного остатка в этой границе нет. Фактические результаты и локальные logs находятся в ADR-0066.

Конечные критерии — source-bound party battle, независимые прогоны/потери, aggregate-only подбор, строгий wire и работающие примеры. Оружие, Wounds1–10, self Recover и Fate decline остаются в границе M9; новые тактики, ally Recover, активное Fate и прочие Wounds не добавляются автоматически.

## M11 — Minions и static-profile Brutes против группы PC

Завершена по [ADR-0067](decisions/ADR-0067-pc-melee-profile-brutes.md). Явные `injury_policy`/`wound_limit` каждого NPC, nonterminal Wounds без table/lifecycle PC, сохранение живого Brute в очереди и последующий defeat с GM disposition. Существующий общий бой/подбор/JSON1 принимает смешанный reserve; состав party и поддержка её ран/Fate прежние. Профили с on-Wound behaviour, Abilities и другие типы NPC не входят. Конечная функция включает typed source guards, trials/process, count search, строгий wire и runnable mixed examples. Обязательного остатка в этой границе нет.

## M12 — все тяжёлые PC-раны

Пользователь выбрал все11–23 и продолжение Attack/Recover с книжными осложнениями по [ADR-0068](decisions/ADR-0068-pc-heavy-wound-continuation.md). Функция завершена: actual mandatory follow-ups, Critical end-turn Tests/Defenceless incapacity turns, forced Wounds, source-aware ongoing Conditions и bounded hand/body facts. Единичные строки больше не останавливают бой; физически невозможная повторная анатомия сохраняет точный pending GM-stop. Текущая PC JSON1 требует `random_side_policy` и `heavy_wound_policy`, без прежнего hand-only shape. Общий риск K1 проверен checkpoint regression; обязательного остатка M12 нет.

## M13 — активный Near Miss

Завершённый срез по [ADR-0069](decisions/ADR-0069-pc-near-miss-policy.md): caller задаёт включительный порог таблицы и минимальный остаток rating. Фактический K1 burn/application разрешается до регистрации/эффектов раны и terminal defeat; supplies сохраняются, owner доказывает каждый расход. Последовательные и процессные trials/aggregate-only count search отражают новые burns отдельно от supplied истории. Текущий PC JSON1 и прежние примеры обновлены вместе. Общий AI, другие Fate options и изменение функции ранжирования сюда не входят.

## M14 — обычные траты Fate на Glorious

Завершённый срез по [ADR-0070](decisions/ADR-0070-pc-glorious-test-policy.md): явные выбранные навыки, порог собственных initial successes и session-spend резерв; все текущие PC Test windows, включая Wound/Critical Endurance. Исходные кубы не бросаются заново, выбор не смотрит на opposing outcome, Grim отменяется до rerolls. Owner хранит полный spend→burn prefix; текущий JSON1 требует обе nullable policies с общим mode `configured`. Costs отдельно проходят независимые trials/process/aggregate-only search и CLI. Другие Fate options/optimal AI не включены.

## После M14

Более широкий NPC/spell/Miscast каталог, дополнительные тактики/Fate, лечение, общий inventory/spatial/campaign/save-resume и ally removal — отдельный backlog после M14. Решение GM для невозможной повторной анатомии и post-healing ветвей не подставляется. Следующие функции выбираются отдельно; уже закрытые границы ими автоматически не расширяются.

Рекомендуемое следующее направление — Help между PC в том же бою, с явной ролью помогающего и условиями выбора вместо автоматического оптимального AI. Перед реализацией закрепить конечную тактику и взаимодействие со следующими Tests/Fate. M15 ещё не согласована; остальные тактики и Fate options не включать автоматически.

## Контрольные точки

Для каждой функции — релевантные детерминированные и сквозные проверки. Полную регрессию назначать при объединении связанных функций, широком изменении общего ядра или выявленном риске. Проверку поставки установленного пакета выполнять перед внешним выпуском либо при изменении соответствующего механизма. Автоматической full/wheel приёмки на каждый ADR нет.
