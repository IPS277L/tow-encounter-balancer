# Текущий статус проекта

Дата обновления: 2026-11-04.

## Текущий этап

**M17 завершена в выбранной границе.** Standard Recover PC снимает разрешённые Staggered/Prone у явно выбранного союзника, вместе с прежними Help/Fate/ранами. [Контракт ADR-0073](decisions/ADR-0073-pc-ally-standard-recover.md), [запускаемые примеры](examples/m17/README.md).

Необходимый собственный подъём/pickup сохраняет self-first; иначе новая роль выбирает Recover с ally-first по каждому benefit, оставшийся можно направить на себя. У Conditions могут быть разные получатели; pickup относится только к actor. Изменения применяются по entity ID, сохраняя unrelated Wounds/Fate/daily/body/effects. Ongoing причины не стираются. Снятие Prone13 создаёт Critical у фактически поднятого PC; receiving aid не становится его action14/15 и не запускает ретроактивный end Test.

Общий Recover завершает прежние receipts через pure helper; PC сравнивает полный canonical proof. Standard action не делает Test/Glorious и не потребляет Next-Test Grim, но отдельный Critical Endurance actor остаётся. Trials/aggregate-only search считают один action с actual nonself condition change, включая mixed self/ally; self-only не входит. Party/role/beneficiary/Fate фиксируются при подборе enemy counts, ranking по objective rate прежний.

Текущий PC JSON1 требует nullable `ally_recover_policy`: объект `{beneficiary_id}` только при `recover_ally_or_attack_or_recover_self`, иначе null. Ally — другой PC этой party, любого порядка/роли; взаимные назначения разрешены. Help у новой роли равен null. Все M9–M16 JSON-пары мигрированы с null/нулями без смены gameplay/counters; omitted-field compatibility нет. Остальные families/версии не менялись.

## Последняя проверка

При `PYTHONPATH=src` `.venv/Scripts/python.exe .cache/m17_check_subsystem.py` — **520 tests OK/140.865s**,52модуля PC M9–M17, общего Recover/Protection/Help/Turn/Test/Fate/Wounds и затронутых M8 Recover callers;0failures/errors/skips. Log `.cache/m17-pc-subsystem.log`. Код/тесты заморожены до запуска; после него менялась только документация. Это единый зелёный адресный прогон, не полный regression проекта.

В составе12новых native/pure PC tests,7statistics,5integration с actual Windows spawn/count search/cache guards,5новых common completion tests и50current codec/schema tests. Нативно проверены earlier/later Staggered, mixed self/ally Prone13 с Critical только нужному entity/его end phase, own pickup+ally clear, actorW14/W15. Ongoing/Defenceless/dead/Grim/receiving-aid границы честно проверены pure. Полный поздний Prone13 сценарий не объявляется достижимым там, где получатель уже сам обязан был подняться.

Ревью выявило и регрессиями закрыто до checkpoint: healer до ещё здорового получателя теряет первый раунд возможной ally Recovery; Help/Recover не могут делить одно action; subclass результата не может подменять executed_actions. Только exact PcMeleeScenarioResult с принятым journal становится observation. Canonical source/range/header/slot/type/replay guards проверены.

Общий Recover refactor покрыт K1 и M8 callers; сборка/dependencies/resources/entry points не менялись. Full regression/wheel не запускались, успешные дорогие проверки не повторялись. В ADR-0073 есть адресная unittest-команда для чистой копии без `.cache`.

Оба M17 requests исполнены CLI через `.cache/m17_execute_examples.py` с lossless request echo на финальном коде. Наблюдения фиксированной стратегии находятся в README/JSON примеров и не объявляются вероятностями/оптимумом. `.cache/m17_verify_docs.py` проверил12изменённых Markdown/1008локальных targets,18current request/result pairs/схемы/UTF-8; `.cache/m17_verify_wire_examples.py` подтвердил сохранение16старых пар и gameplay/prior counters относительно HEAD. `git diff --check` успешен.

## Ограничения

Здоровая initial party со Staff/Sword, numeric Melee Minions/Brutes без on-Wound abilities, одна Close Zone и fixed orders/priorities. Сохраняются Wounds1–23/lethal24+, source-aware ongoing Conditions и mandatory Critical/Defenceless end phase; невозможная повторная анатомия даёт actual pending GM-stop.

Ally Recover — только standard Staggered/Prone: не лечение ран, не cure Defenceless/Critical, не resurrection, не alternative Condition Test, не ally pickup/mounting. Counter считает действия с actual allied change, не снятые Conditions и не гарантированное улучшение здоровья. В opening round before-beneficiary healer не может уже иметь раненого получателя: все PC начинают здоровыми, NPC-side следует после PC-side; это учтено в bounds.

Остаются нынешние fixed Help targets/Skills, Glorious/Near Miss criteria без auto refresh; другие Help/Fate/Lucky/optimal AI, лечение, campaign/general inventory, другие PC weapons и полный NPC catalog не подключены. При limit/unsupported costs/потери отражают лишь observed prefix.

## Следующий шаг

Рекомендовано расширение PC вооружения за пределы Staff/Sword. До реализации выбрать первый книжный набор и необходимые свойства, сохраняя source и Help/Fate/Recover взаимодействия. M18 ещё не согласована; остальной каталог не включать автоматически. [Очередь](roadmap.md), [индекс вопросов](open-questions.md).

Перед M17 рабочее дерево было чистым; пользователь сохранил M16 в Git. Изменения M17 незакоммичены; commit/push выполняет пользователь.
