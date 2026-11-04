# Текущий статус проекта

Дата обновления: 2026-11-04.

## Текущий этап

**M15 завершена в выбранной границе.** PC melee поддерживает физический Melee Help для конкретной атаки более позднего обычного союзника в текущем раунде. Настоящие action slot/Test/Glorious, бонусы zero/multiple/pool cap, hand/heavy/Critical последствия и точные application receipts исполняются в прежнем общем бою. [Контракт ADR-0071](decisions/ADR-0071-pc-melee-help-policy.md), [запускаемые примеры](examples/m15/README.md).

Роль помощника и получатель заданы явно; self Recover имеет приоритет, недоступная помощь возвращает прежнюю Attack/Recover. Бонус связан с точным intended Test, не переносится на другой actor/Test/round и не блокирует победу, если остался unused. Clock сохраняет все PC turns перед NPC; изменения получателя между Help и Attack от NPC здесь недостижимы и проверены отдельно на границе подготовки.

Новой mutable очереди бонусов нет: owner history хранит actual Help и canonical application chain. Trials/aggregate-only balance считают фактические Help actions отдельно от Glorious spends/Near Miss burns. Подбор фиксирует роли и по-прежнему ранжирует по objective rate; optimal Help/Attack AI не добавлен.

Единственная PC JSON1 требует `help_policy`: null при `attack_or_recover_self`, объект `{beneficiary_id}` при `help_ally_or_attack_or_recover_self`. Получатель — другой ordinary PC той же party с более поздним ходом. Несколько помощников допустимы, chains нет. M9–M14 JSON-пары мигрированы с null/нулевыми Help counters, сохранив игровые результаты. Fate configurations/JSON1 и Magic JSON6 остаются текущими, legacy compatibility нет.

## Последняя проверка

При `PYTHONPATH=src` `.venv/Scripts/python.exe .cache/m15_check_subsystem.py` — **357 tests OK/60.430s**,35модулей PC M9–M15 и ближайших K1 Help/Turn/Test/Fate/Drained/Wound consumers;0failures/errors/skips. Log `.cache/m15-pc-subsystem.log`. Source и tests заморожены до запуска, после него менялась только документация. Это единый зелёный адресный прогон, не полный regression проекта.

В составе14новых Help native/pure tests,6statistics,4integration с actual Windows spawn/count search/cache guards,5новых common Help completion tests и42current codec/schema tests. Независимые review проверили книгу, intended Test/prefix, Drained, физическую руку/Fate/type guards. Ошибка aggregate round allocation исправлена отдельной regression до checkpoint: trials без Help не отдают свои обязательные раунды боям с помощью.

Общий Help completion извлекает прежние bonus/slot/clock transitions без новых бросков; availability проверяется до RNG. Сборка/dependencies/resources/entry points не менялись, full regression/wheel не запускались. Прежние M14 результаты проверки сохранены в ADR-0070.

Оба M15 request реально исполнены CLI через `.cache/m15_execute_examples.py` с полным совпадением request echo. После freeze `.cache/m15_verify_frozen_examples.py` подтвердил точное совпадение обоих сохранённых reports с финальным кодом. Simulation12trials:5objective/0party_defeated/7round_limit/0unsupported,38Help actions,33Glorious spends,11Near Miss burns;6боёв с подтверждённой смертью companion. Это наблюдения фиксированной стратегии, не фиксированные вероятности или найденный оптимум. `.cache/m15_verify_docs.py` проверил13изменённых Markdown/978локальных targets,14current request-result pairs/схемы/UTF-8; `.cache/m15_verify_wire_examples.py` подтвердил сохранение gameplay старых12пар относительно HEAD. `git diff --check` успешен.

## Ограничения

Здоровая initial party со Staff/Sword, numeric Melee Minions/Brutes без on-Wound abilities, одна Close Zone и fixed orders/priorities. Сохраняются Wounds1–23/lethal24+, source-aware ongoing Conditions и mandatory Critical/Defenceless end phase. Невозможная повторная анатомия даёт actual pending GM-stop без выдуманной замены.

Help пока только same-Skill Melee для Attack текущего раунда; Protection, другие Skills/GM approval, цепочки помощников и optimal AI отсутствуют. Помощник использует пригодную руку/оружие, Deafened не помогает, Drained получателя не получает positive bonus dice. Help counters включают failed/unused actions, а не суммарные бонусные кубы. Последствия при limit/unsupported отражают лишь observed prefix.

Остаются прежние границы Fate: отдельные Glorious/Near Miss criteria, без auto refresh; другие Fate/Lucky options не подключены. Near Miss не отменяет смерть от отдельного Critical Test. Нет лечения, campaign/general inventory, ally Recover, других PC weapons и полного NPC catalog.

## Следующий шаг

Рекомендовано Help для Protection союзного PC. Перед реализацией адресно закрепить relevant Skill, intended incoming Test и тактику выбора; уже выданные bonuses не переназначать. M16 ещё не согласована; прочие действия не включать автоматически. [Очередь](roadmap.md), [индекс вопросов](open-questions.md).

Перед M15 рабочее дерево было чистым: пользователь сохранил M14 в Git. Изменения M15 незакоммичены; commit/push выполняет пользователь.
