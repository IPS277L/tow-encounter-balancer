# ADR-0073: стандартный Recover союзного PC

Дата: 2026-11-04. Статус: **M17 реализована и адресно проверена в указанной границе**.

## Решение и конечная граница

После M16 пользователь поручил продолжить Recover для союзника. Первый срез — стандартные преимущества снятия допустимых Staggered/Prone в существующей Close Zone. Раны не лечатся, Defenceless/Critically Injured не снимаются, мёртвые не возвращаются. Альтернативные Treat Wound/Condition Test, mounting, ally pickup и campaign не добавляются.

У каждого PC обязательно nullable `ally_recover_policy`. Только `recover_ally_or_attack_or_recover_self` требует объект `{beneficiary_id}`; остальные роли требуют null. Получатель — другой PC этой party, любого порядка/роли. Взаимные назначения разрешены: каждое действие всё равно ограничено настоящим turn/slot, общего recursive healing loop нет. Help/Fate policies сохраняются, новый role не совмещается с Help role.

Прежний self Recover необходим, если нужно подняться из removable Prone или вернуть оружие. В таком случае каждый condition benefit сначала выбирает допустимую собственную Condition, а свободный benefit может получить союзник. Иначе, если союзник жив и имеет removable Staggered/Prone, выбирается Recover: приоритет по каждому benefit у союзника, оставшийся можно использовать на себя. Без подходящей цели сохраняется прежняя Attack/Recover. Собственный pickup при этом остаётся частью того же действия. Это явная стратегия симуляции, не новый книжный порядок и не optimal AI.

## Источники и последствия

Адресно проверены локальные extracted Player’s Guide1.4, гл.V Recover118, Conditions122, Wounds13–15 Table190 и17/19 Table191. Стандартные преимущества Recover можно направлять на себя или союзника в Close Range независимо по Condition. Ongoing причина запрещает снятие Condition до устранения причины: Prone17 и Staggered15/19 не снимаются. Prone13 можно убрать, получив Critically Injured на фактически поднятом персонаже. Используются RULE-COMBAT-004 и существующие Health rules; новых Rule IDs/house rules и полного повторного чтения книг нет.

Receiving aid не является действием получателя. Поэтому снятие его Prone13 создаёт только соответствующий Wound source; нельзя запускать W14/W15 restrictions, как если бы получатель сам действовал. Его mandatory Critical Test остаётся в конце его собственного хода, без ретроактивной проверки на ходу помощника. Actor выполняет настоящий Recover: сохраняются W14 exception, W15 consequence, собственный pickup/hand12 и end phase. Сам standard Recover не делает Test, не расходует Glorious и не погашает Next-Test Grim; отдельный Critical Endurance actor может использовать Fate обычным путём.

## Владение состоянием и доказательства

`PcRecoverProof` сохраняется. Pure `_validate_recover_action` проверяет slot/availability до RNG; `_expected_recover_execution` формирует прежние receipts по готовому resolution без повторного исполнения. Общий executor по-прежнему разрешает standard/treat/remove choices и делегирует сборку результата. Домен PC собирает canonical standard resolution из exact choices и сравнивает весь proof, включая headers/slot/clock/условия/типы/prefix.

Каждый `RecoverConditionChange` применяется к указанному entity ID и его прежнему snapshot. Удаляются только соответствующие `UNTIL_REMOVED` effects фактического получателя; Wounds, treatment/daily history, Fate, body facts, прочие Conditions и weapon союзника сохраняются. Только actor может подобрать своё оружие. `in_close_range=True` взят из текущего single-Close-Zone контракта; self range равен null. Чужая цель, stale/range/clock/receipt, пропущенная/лишняя change и равноценный нетипизированный кэш отклоняются.

## Trials и JSON1

Trial содержит source-ordered `ally_recover_action_counts`. Считается один actual Recover actor, в котором есть хотя бы одна condition change другого PC, включая mixed self/ally. Self-only Recover не входит; снятие двух Conditions не удваивает action count. Это число действий, а не лечение ран или гарантия улучшения состояния: подъём при13 может создать Critical.

Summary содержит те же суммы, `ally_recover_action_trial_count` и производный `total_ally_recover_action_count`, отдельно от Help/Fate. Полный denominator и observed prefix limit/unsupported сохраняются. Проверяются role/order/types/union/turn/action bounds; Help и ally Recover не могут заявлять одно действие дважды.

У healer, действующего до получателя, первая возможность помощи наступает не раньше второго раунда: initial PC здоровы, NPC-side следует после всех PC. Для него aggregate cap `min(total_started_rounds - trials, recover_trials * (max_rounds - 1))`; для более позднего healer — прежний `min(total_started_rounds - (trials - recover_trials), recover_trials * max_rounds)`. Это необходимые арифметические ограничения, а не повторная симуляция всех возможных боёв.

Перед извлечением observations требуется точный `PcMeleeScenarioResult` и полный canonical journal. Подкласс с переопределённым `executed_actions` отклоняется: повторный `replace` того же subclass сам по себе не защищал счётчик.

Balance фиксирует party/beneficiary/Fate и меняет только enemy counts, получает агрегаты и сохраняет прежнее ranking. Единственный PC JSON1 требует новый nullable config и три summary-поля. Все M9–M16 пары мигрированы с null/нулями без смены gameplay/prior counters; старой omitted-field формы нет. [M17 examples](../examples/m17/README.md) исполняют новую роль.

## Проверка

Нативные случаи: союзный Staggered до/после хода получателя; self Staggered + ally Prone13 с Critical только ally и его end; self Prone13 + ally Staggered с Critical только actor; own pickup + ally clear одним действием; W14/W15 actor consequences. Ongoing/Defenceless/dead/Next-Test/receiving-aid boundaries проверены отдельно чистыми проекциями. Для стандартной начальной party Prone13 после уже завершённого хода обычно снят самим Recover; позднее добавление Critical не объявляется отдельным native-сценарием без источника.

При `PYTHONPATH=src` `.venv/Scripts/python.exe .cache/m17_check_subsystem.py` выполнила **520 tests OK/140.865s**,52модуля PC M9–M17, общего Recover/Protection/Help/Turn/Test/Fate/Wounds и затронутых M8 Recover callers;0failures/errors/skips. Log `.cache/m17-pc-subsystem.log`. Код и тесты заморожены до запуска: это единый зелёный адресный прогон, не полный regression проекта.

В составе12новых native/pure PC tests,7statistics,5integration с actual Windows spawn/search/cache guards,5новых common completion tests и50current codec/schema tests. Независимые ревью проверили источник и проекцию; найденные opening-round budget и result-subclass gaps исправлены регрессиями до checkpoint. Оба M17 CLI requests исполнены с lossless echo. Старые16пар мигрированы с сохранением gameplay/counters. Общий Recover refactor проверен также M8 callers; сборка/dependencies/resources/entry points не менялись, full/wheel не запускались.

Launcher/log локальны для `.cache`; в чистой копии можно повторить адресные модули функции напрямую:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest tests.unit.test_m17_pc_ally_recover tests.unit.test_m17_pc_ally_recover_statistics tests.integration.test_m17_pc_ally_recover tests.unit.test_k1_recover_resolution tests.unit.test_k1_recover_completion tests.unit.test_m9_pc_melee_json tests.unit.test_m9_pc_melee_json_schemas -v
```

Эти модули входят в выполненный checkpoint; блок не означает отдельного дополнительного прогона.
