# ADR-0070: PC Glorious Test и совместимые явные Fate policies

Дата: 2026-11-04. Статус: **M14 реализована и адресно проверена**.

## Решение

После M13 пользователь поручил продолжить рекомендованный Glorious Test. Сохраняется нынешний PC melee против numeric Minions/Brutes. Обычное расходование Fate и постоянный Near Miss burn управляются раздельно; скрытого AI/default нет.

Обязательное `glorious_policy` — null либо `PcGloriousPolicy` с тремя явными полями:

- `skills`: непустой список без повторов из melee/defence/athletics/endurance;
- `maximum_initial_successes`: неотрицательный включительный порог собственных начальных успехов;
- `minimum_remaining_spends`: неотрицательный резерв обычных трат текущей сессии.

После фактического initial roll стратегия тратит Fate, если навык выбран, начальные успехи не выше порога, `remaining_spends` строго больше резерва и применение может изменить этот Test. Для обычного Test нужны доступные неудачные кубы; перебрасываются все такие кубы ровно один раз. Для Grim нужны доступные успешные кубы: Glorious отменяет Grim, не создавая перебросов. При нулевых успехах Grim, обычном броске без неудач, уже Glorious или исчерпанном резерве трат нет. Это ограниченная стратегия симуляции, не дополнительные книжные запреты и не утверждение об оптимальности.

Все нынешние PC Test windows поддержаны: Melee Attack, Defence/Athletics Protection, Wound Endurance и Critical Endurance, включая actionless Defenceless turn. У incoming attack по Defenceless нет выдуманного Protection Test или расхода. Результат противника не участвует в выборе; не добавляются Second Action/Retreat/Unmitigated Success/Last Stand, Talents, Lucky или общий AI.

## Источники и порядок

Адресно перечитаны локальные extracted Player’s Guide1.4, гл.V Rules / Grim & Glorious Tests108 и Spending Fate / Glorious Test111. Не перечитана вся книга заново. Используются RULE-TEST-004, RULE-FATE-001 и RULE-FATE-002:glorious-test; новые house rules не вводятся.

Книга разрешает расход после начального броска, до описания исхода; на Grim — до переброса успехов. Grim/Glorious не суммируются и отменяют друг друга. Переброшенный куб повторно не перебрасывается. K1 `roll_test_initial → spend_fate_for_glorious → complete_test` сохраняет эти окна: первоначальные значения не бросаются заново, провалившиеся замены не получают ещё одной попытки и не возвращают Fate.

Для Attack выделен `_resolve_attack_after_tests`, который завершает арифметику по уже исполненным Tests без RNG. Обычный `resolve_attack` сохраняет attacker→defender порядок и прежние tie/impact/miss правила; общий consumer не выбирает PC политику. PC сам сохраняет полные Test/spend proofs и проверяет их источники.

## Источники и состояние PC

`PcAttackProof`, `PcEnduranceProof`, `PcCriticalProof` несут optional typed `glorious` с фактическим `FateGloriousSpendResult`. Его source включает original Test и exact initial roll. Если расход выбран стратегией, decline отсутствует; иначе обязателен bound отказ. Чистая проекция заново проверяет выбор по собственным начальным кубам и актуальному Fate, весь канонический spend/result и точные вложенные типы; не использует новые броски.

Original Attack/Protection остаётся в proof. Только effective PC Test получает bound Glorious modifier; именно он участвует в реальном сравнении/уроне. Owner сохраняет initial scenario/Fate и доказывает ordered ресурсную цепочку. Protection spend записывается до последующего Near Miss на рану от этой же атаки; нельзя использовать pre-spend snapshot. Другой PC не теряет ресурс. Supplied spends/burns/refreshes сохраняются, новые event IDs выбираются свободными детерминированно. Отдельный новый бой требует нового scenario ID, subject нельзя расходовать повторно.

Резерв обычных трат не защищает от уменьшения allowance последующим Near Miss burn: это разные решения и разные величины. Обычный spend не уменьшает rating; burn уменьшает rating и корректирует доступную allowance по K1. Автоматического refresh нет.

## Один текущий контракт

PC JSON остаётся1. `fate_policy: configured` означает хотя бы одну ненулевую конфигурацию из `near_miss_policy` и `glorious_policy`; `decline_optional_fate` требует обе null. Оба поля обязательны в wire и Python source. Это заменяет привязанное к одной способности имя `near_miss_at_threshold` из ADR-0069, позволяя сочетать возможности без отдельного enum для каждой комбинации. Старое имя удалено, aliases/compatibility-период не добавляются. Superseded только orchestration/public shape69, само правило Near Miss сохраняется.

Текущие M9–M13 requests/results мигрированы с `glorious_policy: null` и нулевыми новыми counters, без изменения игровых результатов. Magic6 не затронута. [M14 examples](../examples/m14/README.md) используют обе конфигурации.

Compact trial содержит полный source-ordered `glorious_spend_counts`. Summary содержит эти суммы, `glorious_spend_trial_count` и производный `total_glorious_spend_count`, отдельно от Near Miss. Supplied предыстория исключается; каждый trial начинает с того же полного initial source, а не автоматически пополненного Fate. Проверяются exact types, party/order, union и available session budget каждого PC. Число обычных действий не ограничивает число расходов: обязательные Wound/Critical Tests могут добавляться к действию. Наблюдения до limit/unsupported остаются в полном знаменателе.

Balance получает только агрегаты, фиксирует party/policies и меняет enemy counts. Стоимость Fate показывается, но не меняет целевую функцию ранжирования по objective rate.

## Адресная приёмка

`.venv/Scripts/python.exe .cache/m14_check_subsystem.py` при `PYTHONPATH=src`: **357 tests OK/49.169s**,36модулей PC M9–M14 и ближайших K1 Test/Fate/Attack/Kernel/Ranged callers. Log `.cache/m14-pc-subsystem.log`. Это адресная подсистема, не полный regression проекта.

После дополнительного exact-type guard контейнеров PC trace и новой regression: `.venv/Scripts/python.exe -m unittest tests.unit.test_m14_pc_glorious tests.unit.test_m9_pc_melee_execution tests.unit.test_m12_pc_heavy_wounds tests.integration.test_m14_pc_glorious -v` — **46 tests OK/6.155s**, включая representative real Windows spawn. Log `.cache/m14-final-recheck.log`. Приёмка составная, не единый358-test run финальных файлов. Повтор успешной дорогой матрицы не требовался.

Проверены inclusive criteria/reserve/exhaustion, все PC Test windows, one-die Skill threshold, normal rerolls/Grim cancellation, нет повторного начального RNG/подглядывания в opposing outcome, spend→Near Miss, supplied history, isolation, source/type/replay/cached counters и mutable skills. Есть actual sequential/process parity, aggregate-only search, strict codec/schema и исполняемые CLI simulation/balance. Два независимых ревью проверили источники и тайминг. Общий completion refactor покрыт существующими callers, сборка/поставка не менялись; новый full/wheel не запускался.
