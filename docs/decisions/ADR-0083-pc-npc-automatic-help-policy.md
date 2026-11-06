# ADR-0083: явная тактика NPC Help без Test

Дата: 2026-11-05. Статус: **принято и реализовано**. Пользователь выбрал несколько явных пар, включая нескольких помощников для одного Test; M31–M32 сохранены.

## Задача и источники

Активировать Torches and Pitchforks Empire Peasant и Strength in Numbers Free Company Militia в PC melee. Сейчас NPC выбирают Attack, способности сохранены как inactive. Источники: BOOK-GM-GUIDE1.1, Allies and Antagonists / Peasant96 / Militia113; BOOK-PLAYER-GUIDE1.4, Rules / Dice Pools107 / Helping With a Test108 / Help117 / Conditions122–123.

Обе способности заменяют Help Test автоматическим+1d, а не дают free action. Peasant помогает Melee attack; Militia — любой attack союзника within Medium Range. Текущий срез melee-only/все Close удовлетворяет обоим условиям. Каждый+1d может превысить обычный bonus cap; остальные бонусы продолжают ограничиваться. Несколько помощников допустимы, книжного max helper count не найдено. Отдельный no-Test результат не должен содержать фиктивный TestResult, success trace, Glorious или Attack miss/Stagger.

## Согласованная граница M33

Вход содержит явные пары named helper_id → beneficiary_id. Helper — Peasant либо Militia; получатель — другой NPC той же opposition, с обычной Attack policy и более поздним местом в enemy_activation_order. Несколько helpers могут выбрать одного beneficiary. Helper не может иметь несколько адресатов; self Help, cycles/chains и помощь чужой стороне исключены до RNG. Нет автоматического выбора самого выгодного получателя.

Каждый подходящий helper в свой ход тратит единственный standard action slot на физическую Help, не выполняя Test. Накапливается типизированный источник с actual action receipt, helper/beneficiary, source Rule ID и точным ID будущего Melee Attack Test текущего раунда. Источники применяются в порядке исполненных действий, каждый один раз, как отдельный+1d bypasses_pool_cap=True. Обычный outnumbering и его cap остаются прежними; присутствие helpers продолжает учитываться при подсчёте численности.

После реальной Help helper проходит обычный TurnEnd. Собственный Staggered не запрещает Help и сам по себе не снимается. Drained helper не блокирует no-Test способность, поскольку своего Test нет. Deafened/Defenceless/defeated helper не может помогать; обязательные ограничения собственного хода/бегство нельзя обходить fallback-атакой. Deafened beneficiary сам по себе не иммунен к физической помощи: речь не является условием этих двух Abilities.

## Тактика допуска и fallback

Помощь выбирается только когда named beneficiary жив/не defeated/не exited, не завершил/пропустил ход, не Defenceless/Broken и сможет выбирать обычную Attack. При Drained beneficiary выбран **Attack fallback**: это выбранная тактика, а не книжный запрет помогать Drained. В остальных неподходящих случаях helper тоже выполняет прежнюю Attack, если собственные ограничения это разрешают. Не переназначать помощника на другого NPC или следующий Test.

Если после Help intended Test не состоялся, receipt остаётся неиспользованным. Следующий раунд/другой Test/другой NPC его не получают. Это exact Test binding policy по образцу M15, а не новое книжное правило «Help истекает в конце раунда». Дополнительный поздний Drained filter не должен пропустить положительный bypass bonus, даже если receipt уже создан.

## Current PC JSON1 и count search

Current PC JSON1 требует scenario.npc_help_policies: [] либо список объектов {helper_id,beneficiary_id}. Пустой список сохраняет прежний fixed Attack. Полные source/readmission/canonical book guards проверяются до RNG. В native Python поле также обязательно: явный tuple типизированных пар, включая () для отказа; ни Ability DSL, ни общий NPC AI не вводятся.

При создании count candidate сохранять entry только если в составе остаются **оба** ID. Оставшиеся mappings не переназначать; ordinary order/приоритеты/defeat decisions проецируются прежним способом. Если helper остаётся без названного beneficiary, candidate получает прежний Attack для этого actor. Это явное правило проекции source, не скрытая оптимизация тактики.

Новые NPC Help counts отделяются от прежних PC help_action_counts: source-ordered per-NPC counts, количество trials с NPC Help и total NPC Help actions. Total action budget включает real Help action. Compact trials/summary/balance хранят агрегаты, не native journals. Current JSON1/команды остаются, старые requests/echo/candidates получают [] и нулевые NPC Help metrics. Остальные значения/наблюдения сохранить; backward branches и новая wire version не нужны.

## Отклонённая альтернатива меньшего объёма

Пользователь выбрал несколько пар. Рассматривалась только одна named пара на сценарий, без нескольких helpers одному Test. Это меньше admission/aggregation проверок, но ограничивает сразу две совместимые книжные способности. Та же тактика fallback/источники/публичные поля; ограничение одной пары было бы scope, а не правилом книги.

## Приёмка

1. Настоящий Help slot/no RNG/no fake Test/no miss consequence, обычный TurnEnd и точная роль actor.
2. Peasant/Militia источники, multiple helpers, однократное применение, обычный cap плюс отдельный bypass и Drained filter.
3. Helper/beneficiary guards, fixed fallback, отсутствие implicit role reassignment, stale/wrong-round/wrong-test/cached/receipt/replay/type forgeries.
4. Full-source records/отдельные NPC costs/summary bounds, generation с retained/removed endpoints, current schemas/CLI/examples.
5. Ближайшие Help/Turn/Test/PC consumers; контроль PC subsystem при изменении общей подготовки/контракта с широкими зависимостями. Backend matrix/wheel без изменения соответствующего механизма не повторять. Историческую успешную приёмку M32 ради этого предложения не запускать заново.

Реализация: [no-Test models](../../src/towr/domain/automatic_help_models.py), [executor](../../src/towr/rules/automatic_help_resolution.py), [PC policy/preparation](../../src/towr/domain/pc_npc_help_models.py), [журнал](../../src/towr/domain/pc_melee_result_models.py), [generation](../../src/towr/application/pc_melee_balance_models.py), [statistics](../../src/towr/simulation/pc_melee_summary_models.py), [current JSON](../../src/towr/adapters/pc_melee_json.py). Нынешняя приёмка/точка продолжения — в [статусе](../project-status.md), пользовательские примеры — в [M33](../examples/m33/README.md).

Историческая приёмка M33:32новыхtests прошли, включая representative process parity. Контроль100модулей/823tests дал822OK/1failure/0errors за106.110s;23старые process/spawn/console cases исключены. Failure выявил ошибочный default() нового source field. Default удалён, builder явно передаёт(), expected source fields обновлены;35реальных адресных checks после исправления прошли составно. В первом повторе также был неверный selector (loader error), затем правильные count-search/metrics методы прошли. Pure-generation endpoint test добавлен после загрузки823suite; уникальная выборка824 — не единый новый green full run. Все50request/result pairs и96прежнихJSON documents после []/zero migration проверены;25definitions/snapshots и Ability texts сохранены с двумя capability promotions. Дальнейшее расширение effects и Drained tactic — [M34](ADR-0084-pc-greenskin-automatic-help.md).
