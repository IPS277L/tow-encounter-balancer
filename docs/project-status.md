# Текущий статус проекта

Дата обновления: 2026-11-04.

## Текущий этап

**M14 завершена в выбранной границе.** Нынешний PC melee против numeric Minions/Brutes поддерживает обычные траты Fate на Glorious для Attack, Protection, Wound Endurance и Critical Endurance, включая actionless Defenceless turn. Выбор делается после собственного initial roll и до rerolls, по явно заданным навыкам, порогу успехов и резерву сессии. Near Miss применяется отдельно и может следовать за Glorious на той же атаке. [Контракт ADR-0070](decisions/ADR-0070-pc-glorious-test-policy.md), [запускаемые примеры](examples/m14/README.md).

Начальный source/Fate сохраняется; каждый spend/burn доказывает полный ordered переход только своего PC. Начальные кубы не бросаются повторно, выбор не зависит от opposing outcome. Trials/aggregate-only balance отдельно показывают новые Glorious spends и Near Miss burns, исключая supplied историю. Ранжирование по objective rate не изменено.

Единственная PC JSON1 теперь требует обе nullable `near_miss_policy` и `glorious_policy`. Mode `configured` требует хотя бы одну конфигурацию; `decline_optional_fate` — обе null. Прежнее имя `near_miss_at_threshold` удалено без alias/compatibility. Все M9–M13 JSON-примеры мигрированы с null Glorious и нулевыми новыми counters, сохранив игровые результаты. Magic JSON6 не затронута.

## Последняя проверка

При `PYTHONPATH=src`:

- `.venv/Scripts/python.exe .cache/m14_check_subsystem.py` — **357 tests OK/49.169s**,36модулей PC M9–M14 и ближайших K1 Test/Fate/Attack/Kernel/Ranged callers;0failures/errors/skips. Log `.cache/m14-pc-subsystem.log`. Это адресная подсистема, не полный regression проекта.
- После дополнительного exact-type guard контейнеров PC trace: `.venv/Scripts/python.exe -m unittest tests.unit.test_m14_pc_glorious tests.unit.test_m9_pc_melee_execution tests.unit.test_m12_pc_heavy_wounds tests.integration.test_m14_pc_glorious -v` — **46 tests OK/6.155s**, включая real Windows spawn. Log `.cache/m14-final-recheck.log`. Приёмка составная, не единый358-test run финальных файлов; успешная дорогая матрица не повторялась.

Общий completion helper извлекает прежнюю Attack arithmetic без смены правил/RNG-порядка; это проверено общими callers в357-suite. Два независимых ревью проверили source/timing/resource guards. Кэшированный mutable skills list отклоняется, чужие/повторные/равноценные нетипизированные Test/spend proofs не принимаются. Сборка/dependencies/resource discovery/entry points не менялись; нового full regression/wheel нет. Исторические M12/M13 приёмки остаются в своих ADR.

Оба M14 requests реально исполнены `python -m towr` через `.cache/m14_execute_examples.py` с полным совпадением request echo. В simulation12trials:7objective/0party_defeated/5round_limit/0unsupported,32Glorious spends во всех12боях и12Near Miss burns в10боях;6боёв с подтверждённой смертью companion. Это наблюдения выбранных seeds/trials/policies, не фиксированные вероятности и не доказательство улучшения стратегии. `.cache/m14_verify_docs.py` проверил14изменённых Markdown/942локальных targets,12request/result pairs, схемы и UTF-8/whitespace; `.cache/m14_verify_wire_examples.py` подтвердил сохранение gameplay старых10пар относительно HEAD. `git diff --check` успешен.

## Ограничения

Здоровая initial party со Staff/Sword, numeric Melee Minions/Brutes без on-Wound abilities, одна Close Zone и фиксированные orders/priorities. Сохраняется M12 поддержка Wounds1–23/lethal24+, mandatory Critical/Defenceless end phase и source-aware ongoing Conditions. Физически невозможная повторная анатомическая потеря даёт actual pending `unavailable_anatomical_target`; GM-замена не выбрана.

Резерв Glorious ограничивает обычные траты, но последующий Near Miss burn может уменьшить оставшуюся allowance ниже него. Автоматического refresh нет; каждый trial начинает с того же полного supplied Fate, а не с восстановленного ресурса. Near Miss не отменяет смерть от отдельного Critical Test без новой раны. Остальные optional Fate options, Lucky, лечение, campaign, общий inventory, ally Recover/Help, другие PC weapons и полный NPC catalog не реализованы. Потери и costs при limit/unsupported — только фактический prefix.

## Следующий шаг

Рекомендованная следующая функция — Help между PC в том же бою, с явной ролью помогающего и условиями выбора вместо оптимального AI. Перед реализацией закрепить конечную тактику и взаимодействие со следующими Tests/Fate. M15 ещё не согласована; остальные тактики не включать автоматически. [Очередь](roadmap.md), [индекс вопросов](open-questions.md).

Перед M14 рабочее дерево было чистым: пользователь уже сохранил M13 в Git. Изменения M14 остаются незакоммиченными; commit/push выполняет пользователь.
