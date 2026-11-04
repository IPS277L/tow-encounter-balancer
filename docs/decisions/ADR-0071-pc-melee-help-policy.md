# ADR-0071: Help для намеченной атаки союзного PC

Дата: 2026-11-04. Статус: **M15 реализована и адресно проверена в указанной границе**.

M16/[ADR-0072](ADR-0072-pc-protection-help-policy.md) требует явные target/protection_skill у Help configuration и добавляет Protection Help. Ниже сохранено решение M15 на момент приёмки; его Melee поведение продолжается с target=melee_attack/skill=null.

## Решение и конечная граница

После M14 пользователь поручил продолжить рекомендованный Help между PC. Первый срез — физическая помощь оружием с Melee Test для одной намеченной Melee Attack союзника в текущем раунде. Это законченная функция через общий PC бой, Fate/раны, trials, aggregate-only count search и текущий JSON1, без общего AI.

У участника обязательно `help_policy`: null при прежнем `attack_or_recover_self` либо `{beneficiary_id}` при `help_ally_or_attack_or_recover_self`. Получатель — другой PC той же party, обычной Attack/Recover policy, стоящий позже в `pc_activation_order`. Несколько помощников могут выбрать одного получателя; Help chains и другой Skill не включаются. Неподходящий source отвергается до RNG.

Прежний self Recover имеет приоритет. Иначе Help выбирается, когда помощник способен действовать, не Deafened, с пригодной рукой/оружием; получатель жив, не Defenceless/Drained, готов к Attack вместо Recover и ещё не завершил/пропустил ход. При недоступной помощи выполняется прежняя Attack/Recover. Это явная узкая стратегия, а не книжные запреты помогать в иных обстоятельствах. Физическая помощь не требует слышать речь; использование оружия связывает действие с фактической рукой помощника.

Help использует настоящий standard action slot. Его неудача также тратит действие, создаёт нулевой snapshot и не применяет Attack miss/Stagger или Damage. Собственный Melee Help Test не получает outnumbering как Attack. Glorious, Next-Test Grim и тяжёлые ограничения действуют на него как на реальный Test/действие. Для раны12 учитывается использование руки;14/15 создают соответствующий Critical source. End phase остаётся настоящим, включая обязательный Critical Endurance.

## Источники

Адресно перечитаны локальные extracted Player’s Guide1.4, гл.V Rules / Helping With a Test108, Combat Actions / Help117, Deafened/Drained123. Для Help каждый успех даёт +1d на намеченный Test союзника; другой Skill допускает GM. Обычный pool cap сохраняется. Deafened запрещает Help, Drained запрещает bonus dice. Используются RULE-TEST-005, RULE-COMBAT-004 и существующие Condition/Fate/Wound rules; новых Rule IDs/house rules нет. Полного повторного чтения книги нет.

## Владение бонусом и доказательства

`PcHelpProof` хранит original `HelpActionExecutionRequest`, фактический result с effective Glorious Test, bound отказ или spend proof. K1 initial/spend/complete Test не перебрасывает исходный пул заново. Общий pure `_expected_help_execution` и `_complete_help_action` завершают прежние bonus/slot/clock receipts по готовому Test без RNG; `execute_help_action` проверяет доступность до бросков. Домен не импортирует rules/CLI/balance.

`PcAttackProof.help_applications` сохраняет всю canonical chain `HelpBonusApplicationResult` из реальных предшествующих Help proofs, в их порядке. Каждый snapshot связан с точным ID атаки получателя в данном раунде. Сохраняются нулевые и несколько бонусов; итоговый пул ограничивается обычным cap. Drained получателя убирает положительные модификаторы до реального броска, сохраняя source receipts. Получатель может отдельно использовать Glorious после начального броска уже подготовленного пула.

Дополнительного mutable банка бонусов нет: исполненная история — единственный источник. Повторный/чужой receipt, пропущенное/дублированное применение, смена Test/ally/round/clock, поддельный result или равноценные нетипизированные значения отклоняются полным source/prefix/type admission. Исходная party и Fate остаются authored source; Help spend включается в ту же ordered Fate chain.

Если намеченная атака не состоялась, Help не переназначается и не превращается в помощь следующего раунда. Неиспользованный snapshot остаётся в истории, не блокируя законный terminal outcome. Пример достижим нативно: помощник помогает позднему PC, другой PC раньше него побеждает последнего NPC. Существующий clock сначала даёт ходы всем PC, затем NPC; он не меняется. Приобретение раны/смерти от NPC между Help и атакой в этой границе недостижимо, поэтому такие изменения проверяются отдельно через pure eligibility/preparation, а не выдаются за native сценарий.

## Trials, подбор и текущий JSON

`executed_actions` включает Help. Trial хранит полный source-ordered `help_action_counts`; summary содержит их суммы, `help_action_trial_count` и производный `total_help_action_count`. Это число фактических Help actions, включая неудачные/неиспользованные, а не число добавленных кубов или гарантированно усиленных атак. Glorious/Near Miss costs сохраняются отдельно; не исключаются наблюдения до limit/unsupported.

Проверяются exact types, полный состав/порядок party, positive counts только у helper-role, action budget и максимум одного Help на собственный ход. Для aggregate верхняя граница на одного помощника учитывает обязательный начатый раунд каждого trial без Help: `min(total_started_rounds - (trials - help_trials), help_trials * max_rounds)`. Нельзя приписать их раунды боям с помощью.

Balance фиксирует helper/beneficiary и все Fate policies, меняет только enemy counts, получает лишь агрегаты. Функция ранжирования прежняя. Текущий PC JSON остаётся1: обязательное `help_policy` связано с action policy, три новых summary-поля обязательны. Все M9–M14 JSON-пары мигрированы с null/нулями, их игровые результаты и прежние counters сохранены; aliases/старой формы нет. [M15 examples](../examples/m15/README.md) реально запускают новую тактику.

## Адресная проверка

План: реальный Help slot/Test/zero/multiple/cap; own/beneficiary Fate, Next-Test Grim/Drained, физическая рука и heavy Critical/end phase; fallback/unused intended Test; exact source/prefix/type/replay; record/summary bounds; indexed sequential/process parity, aggregate-only search; строгий codec/schema, actual CLI examples и сохранение старых JSON-данных. Общие Help consumers и ближайшие зависимости проверяются адресно; новый full/wheel без риска поставки не требуется.

При `PYTHONPATH=src` `.venv/Scripts/python.exe .cache/m15_check_subsystem.py` выполнила **357 tests OK/60.430s**,35модулей PC M9–M15 и ближайших Help/Turn/Test/Fate/Drained/Wound consumers;0failures/errors/skips. Log `.cache/m15-pc-subsystem.log`. Production и tests были заморожены до запуска; это единый зелёный адресный прогон, не полный regression проекта. Повтор успешной дорогой матрицы не нужен. Историческая приёмка M14 остаётся в ADR-0070.

В составе есть14новых native/pure Help tests,6statistics tests,4integration tests с actual Windows spawn/count search/cache guards и5новых common completion tests.42current codec/schema tests закрывают новую корреляцию/границы. Независимые ревью источника и typed chain не нашли игрового дефекта; найденная невозможная aggregate round allocation исправлена отдельной regression до checkpoint. Оба M15 CLI requests фактически исполнены, остальные12пар мигрированы без смены gameplay/prior counters. Поставка не менялась, full/wheel не запускались.

Launcher/log находятся в локальной `.cache`; в чистой копии репозитория адресные проверки этой функции можно запустить напрямую:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest tests.unit.test_m15_pc_help tests.unit.test_m15_pc_help_statistics tests.integration.test_m15_pc_help tests.unit.test_k1_help_resolution tests.unit.test_k1_help_completion tests.unit.test_m9_pc_melee_json tests.unit.test_m9_pc_melee_json_schemas -v
```

Все перечисленные модули входят в выполненный357-test checkpoint; этот блок не означает отдельный дополнительный прогон.
