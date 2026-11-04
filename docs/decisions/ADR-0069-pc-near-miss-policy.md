# ADR-0069: активная PC Near Miss policy

Дата: 2026-11-04. Статус: **M13 реализована и адресно проверена в указанной границе**.

## Решение и граница

После завершённой M12 пользователь поручил продолжить рекомендованное направление активного Near Miss. Книга не определяет оптимальную стратегию игрока. Вместо общего AI или скрытого default вводится явная конфигурация каждого PC: `fate_policy: near_miss_at_threshold` и `near_miss_policy: {minimum_table_total, minimum_rating_to_keep}`. Первый параметр — положительное целое, второй — неотрицательное; bool и coercion не допускаются. При `decline_optional_fate` конфигурация равна `null`.

После фактического броска таблицы PC с активной policy сжигает Fate, если окно допускает Near Miss, total не ниже порога и текущий rating строго выше сохраняемого остатка. Иначе он отказывается. Остаток не ниже начального rating допустим и не делает ожогов. Искусственного максимума total нет: результаты могут превышать27. Это стратегия симуляции, не house rule и не утверждение об оптимальной игре.

Все прочие опциональные применения Fate по-прежнему отклоняются. Автоматического пополнения, общего банка группы, выбора политики балансировщиком и campaign нет. Раны, Critical Tests и невозможная повторная анатомия сохраняют M12 границу. Near Miss не отменяет смерть от отдельного Critical Test без новой раны.

## Источник

Адресно перечитаны локальные extracted Player’s Guide1.4, гл.V Rules / Burning Fate111 и Near Miss112. Burn уменьшает rating навсегда; допускается при исчерпанных обычных тратах текущей сессии. Near Miss выбирается после Wounds Table, полностью отменяет рану и её вклад в будущие броски, сохраняет прежний Staggered. Полное повторное чтение книг и новые Rule IDs не заявляются: используются RULE-FATE-001 и RULE-FATE-003:burn/near-miss.

## Владение и исполнение

Начальный `PcMeleeParticipant.fate` остаётся неизменным источником. `PcMeleeParticipantState.fate` теперь может отличаться от него только цепочкой фактических `PcWoundCompletionProof` этого боя. Общий builder связывает policy, текущий Fate, actor, actual pending roll и consumed roll/effect IDs. Engine и чистая проекция используют один и тот же выбор; нельзя подменить выбранный burn отказом или наоборот.

Существующий K1 `FateNearMissBurnRequest → CharacterWoundLifecycleCompletionResult` атомарно исполняет burn/application. Полная проверка resource/application proofs предшествует обновлению owner; арифметика rating/session allowance не дублируется. Supplied spends/burns/refreshes и порядок ресурсных событий сохраняются. Уже потраченная сессия не блокирует доступный burn. Новый burn ID детерминированно выбирается свободным среди прежних ресурсных ID; тот же Near Miss subject повторно использовать нельзя. Для нового отдельного боя caller должен задавать новое scenario ID.

Отмена не регистрирует daily Wound, не добавляет wound/body/timed effects и не расходует random side/Endurance для отменённой строки. Сохраняется прежний Staggered и уже исполненные Test-последствия, включая снятый Next-Test Grim. Pending lethal Wound проходит это окно до terminal defeat. Полные источники и типы, prefix и однократность остаются обязательными.

## Trials, balance и JSON1

Каждый trial начинает с полного supplied Fate всех PC. Компактный record хранит `near_miss_burn_counts` — полный source-ordered список новых burn counts, исключая supplied историю. Summary содержит этот список в сумме по trials, `near_miss_burn_trial_count` и производный `total_near_miss_burn_count`. Проверяются типы, партия/порядок, budget каждого PC, union и action bounds. Наблюдённые burns до limit/unsupported остаются в полном знаменателе. Перед извлечением счётчиков принимается полный source-bound result journal без повторного RNG/игрового исполнения; испорченный cached Fate не превращается в допустимое число.

Балансировщик сохраняет всю party и policies, меняет только согласованные enemy counts. Расход ресурса показывается, но не меняет прежнее ранжирование по objective rate.

Единственный текущий PC JSON1 требует `near_miss_policy` у каждого участника; schema связывает null/object с `fate_policy`. Все current M9–M12 примеры мигрированы с null и нулевыми counters. Версия не повышается, omitted-field compatibility не добавляется. Magic JSON6 не затронута. [M13](../examples/m13/README.md) содержит исполненные simulation/balance примеры с явными порогом14 и остатком1.

## Проверка

Адресный план: native deterministic threshold/reserve/exhaustion/history и lethal/body/Grim; исходные и поддельные proof/prefix; per-PC ресурсы; compact/summary bounds и cached result admission; реальные indexed sequential/process trials, aggregate-only count search, строгие schema/codec/CLI и runnable examples. Общий K1, сборка и entry points не меняются: оснований для нового full regression/wheel нет.

Приёмка составная. `.venv/Scripts/python.exe .cache/m13_check_subsystem.py` при `PYTHONPATH=src` охватила22модуля PC M9–M13 и K1 Near Miss/Wound lifecycle:197тестов,196успешно и1failure обязательного source-поля. Неявный Python default удалён, builder передаёт null явно. Model/codec/schema/native/statistics/M13 integration перепроверены74тестами OK/5.649s; затем изменённый integration module с новым supplied-history кейсом —5тестов OK/2.913s. Это не единый зелёный197-test run. Точные команды и logs — в [статусе](../project-status.md); историческая приёмка M12 остаётся в ADR-0068.

Native15tests проверяют включительность порога, резерв/нулевой ресурс, исчерпанную session allowance, сохранение supplied spends/burns, lethal/body отмену без лишнего RNG, оба PC, прежний Staggered/consumed Grim, обязательность выбранного burn, replay/чужой Fate, коллизию ID и вложенные равноценные bool/int/string-Enum подмены. Отдельная regression не позволяет повреждённому cached Fate стать compact observation. Реальные indexed sequential/process trials совпадают; count search сохраняет party/resources/policies и получает только агрегаты. Оба публичных M13 примера исполнены CLI; current10 request/result pairs проверены на schema/source echo/parse. Full regression и wheel не повторялись.
